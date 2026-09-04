#!/usr/bin/env python3
"""Deterministic extraction pipeline for authoritative HSK source documents.

The pipeline deliberately separates byte acquisition, lossless extraction,
source-specific parsing, reviewed corrections, and canonical serialization.
It uses only the Python standard library; native PDF extraction is delegated to
Poppler's ``pdftotext -layout`` and its exact version is recorded.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unicodedata
import urllib.error
import urllib.request
import zipfile
from collections import Counter
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Mapping, MutableMapping, Optional, Sequence, Tuple
from xml.etree import ElementTree as ET


SCHEMA_VERSION = 1
CANONICAL_FIELDS = (
    "source_id",
    "source_locator",
    "source_sequence",
    "level",
    "level_raw",
    "additional_levels",
    "simplified",
    "traditional",
    "headword_raw",
    "sense_label",
    "pinyin_raw",
    "part_of_speech_raw",
    "extraction_method",
    "correction_ids",
)
REQUIRED_CANONICAL_FIELDS = ("source_id", "source_locator", "level", "simplified")
HAN_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\U00020000-\U0002fa1f]")


class PipelineError(RuntimeError):
    """An expected, actionable pipeline failure."""


def read_json(path: Path) -> Any:
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, json.JSONDecodeError) as error:
        raise PipelineError(f"cannot read JSON {path}: {error}") from error


def json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def write_bytes_if_changed(path: Path, contents: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_bytes() == contents:
        return
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_bytes(contents)
    os.replace(temporary, path)


def write_json(path: Path, value: Any) -> None:
    write_bytes_if_changed(path, json_bytes(value))


def write_jsonl(path: Path, records: Iterable[Mapping[str, Any]]) -> None:
    buffer = io.StringIO(newline="\n")
    for record in records:
        buffer.write(json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
        buffer.write("\n")
    write_bytes_if_changed(path, buffer.getvalue().encode("utf-8"))


def read_jsonl(path: Path) -> List[Dict[str, Any]]:
    records: List[Dict[str, Any]] = []
    try:
        with path.open("r", encoding="utf-8") as handle:
            for number, line in enumerate(handle, 1):
                if not line.strip():
                    continue
                value = json.loads(line)
                if not isinstance(value, dict):
                    raise PipelineError(f"{path}:{number}: expected a JSON object")
                records.append(value)
    except (OSError, json.JSONDecodeError) as error:
        raise PipelineError(f"cannot read JSONL {path}: {error}") from error
    return records


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            block = handle.read(1024 * 1024)
            if not block:
                return digest.hexdigest()
            digest.update(block)


def normalize_cell(value: str) -> str:
    return unicodedata.normalize("NFC", value.replace("\r\n", "\n").replace("\r", "\n")).strip()


def manifest_sources(manifest: Mapping[str, Any]) -> List[Mapping[str, Any]]:
    if manifest.get("schema_version") != SCHEMA_VERSION:
        raise PipelineError(f"unsupported manifest schema: {manifest.get('schema_version')!r}")
    sources = manifest.get("sources")
    if not isinstance(sources, list) or not sources:
        raise PipelineError("manifest.sources must be a non-empty array")
    identifiers: set[str] = set()
    for source in sources:
        if not isinstance(source, dict):
            raise PipelineError("every manifest source must be an object")
        required = (
            "id",
            "source_name",
            "issuing_authority",
            "landing_page_url",
            "document_url",
            "artifact_filename",
            "media_type",
            "expected",
        )
        missing = [field for field in required if not source.get(field)]
        if missing:
            raise PipelineError(f"source is missing {', '.join(missing)}")
        if source["id"] in identifiers:
            raise PipelineError(f"duplicate source id: {source['id']}")
        identifiers.add(source["id"])
        expected = source["expected"]
        if not isinstance(expected.get("levels"), dict) or not expected.get("source_rows_total"):
            raise PipelineError(f"{source['id']}: expected counts are incomplete")
    return sources


def get_source(manifest: Mapping[str, Any], source_id: str) -> Mapping[str, Any]:
    for source in manifest_sources(manifest):
        if source["id"] == source_id:
            return source
    raise PipelineError(f"unknown source id: {source_id}")


def validate_iso_date(value: str, label: str) -> None:
    try:
        dt.date.fromisoformat(value)
    except ValueError as error:
        raise PipelineError(f"{label} must use YYYY-MM-DD: {value!r}") from error


def tool_version(command: Sequence[str]) -> str:
    try:
        result = subprocess.run(command, check=True, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    except (OSError, subprocess.CalledProcessError) as error:
        raise PipelineError(f"cannot determine tool version using {' '.join(command)}: {error}") from error
    return result.stdout.strip().splitlines()[0]


def build_lock(manifest: Mapping[str, Any], artifact_dir: Path, retrieval_date: str) -> Dict[str, Any]:
    validate_iso_date(retrieval_date, "retrieval date")
    locked: List[Dict[str, Any]] = []
    missing: List[str] = []
    for source in manifest_sources(manifest):
        artifact = artifact_dir / source["artifact_filename"]
        if not artifact.is_file():
            missing.append(str(artifact))
            continue
        locked.append(
            {
                "artifact_filename": source["artifact_filename"],
                "document_url": source["document_url"],
                "retrieval_date": retrieval_date,
                "sha256": sha256_file(artifact),
                "size_bytes": artifact.stat().st_size,
                "source_id": source["id"],
            }
        )
    if missing:
        raise PipelineError("missing authoritative artifacts:\n  " + "\n  ".join(missing))
    return {"schema_version": SCHEMA_VERSION, "sources": locked}


def verify_lock(
    manifest: Mapping[str, Any], lock: Mapping[str, Any], artifact_dir: Path, source_ids: Optional[Sequence[str]] = None
) -> None:
    if lock.get("schema_version") != SCHEMA_VERSION:
        raise PipelineError("source lock has an unsupported schema")
    entries = {entry.get("source_id"): entry for entry in lock.get("sources", []) if isinstance(entry, dict)}
    problems: List[str] = []
    selected = [source for source in manifest_sources(manifest) if source_ids is None or source["id"] in source_ids]
    if source_ids is not None and {source["id"] for source in selected} != set(source_ids):
        raise PipelineError("requested source identifiers are not all present in the manifest")
    for source in selected:
        entry = entries.get(source["id"])
        artifact = artifact_dir / source["artifact_filename"]
        if entry is None:
            problems.append(f"{source['id']}: missing lock entry")
            continue
        if entry.get("artifact_filename") != source["artifact_filename"]:
            problems.append(f"{source['id']}: locked filename differs from manifest")
        if entry.get("document_url") != source["document_url"]:
            problems.append(f"{source['id']}: locked URL differs from manifest")
        if not artifact.is_file():
            problems.append(f"{source['id']}: artifact is absent: {artifact}")
            continue
        actual_hash = sha256_file(artifact)
        if actual_hash != entry.get("sha256"):
            problems.append(f"{source['id']}: SHA-256 mismatch ({actual_hash} != {entry.get('sha256')})")
        if artifact.stat().st_size != entry.get("size_bytes"):
            problems.append(f"{source['id']}: byte-size mismatch")
    selected_ids = {source["id"] for source in selected}
    if source_ids is None and set(entries) != selected_ids:
        problems.append("lock source identifiers do not exactly match manifest")
    elif source_ids is not None and not selected_ids.issubset(entries):
        problems.append("lock does not contain every requested source identifier")
    if problems:
        raise PipelineError("source lock verification failed:\n  " + "\n  ".join(problems))


def download_sources(manifest: Mapping[str, Any], artifact_dir: Path) -> None:
    artifact_dir.mkdir(parents=True, exist_ok=True)
    for source in manifest_sources(manifest):
        destination = artifact_dir / source["artifact_filename"]
        temporary = destination.with_name(f".{destination.name}.download")
        request = urllib.request.Request(source["document_url"], headers={"User-Agent": "hsk-data-pipeline/1"})
        try:
            with urllib.request.urlopen(request, timeout=90) as response, temporary.open("wb") as output:
                shutil.copyfileobj(response, output)
        except (OSError, urllib.error.URLError) as error:
            temporary.unlink(missing_ok=True)
            raise PipelineError(f"download failed for {source['id']}: {error}") from error
        os.replace(temporary, destination)
        print(f"downloaded {source['id']} -> {destination}")


def column_name(reference: str) -> str:
    match = re.match(r"([A-Z]+)", reference)
    return match.group(1) if match else reference


def xml_text(element: ET.Element) -> str:
    return "".join(node.text or "" for node in element.iter() if node.tag.endswith("}t"))


def xlsx_shared_strings(archive: zipfile.ZipFile) -> List[str]:
    try:
        root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
    except KeyError:
        return []
    return [normalize_cell(xml_text(item)) for item in root if item.tag.endswith("}si")]


def xlsx_sheets(archive: zipfile.ZipFile) -> List[Tuple[str, str]]:
    workbook = ET.fromstring(archive.read("xl/workbook.xml"))
    relationships = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
    targets = {relation.attrib["Id"]: relation.attrib["Target"] for relation in relationships}
    sheets: List[Tuple[str, str]] = []
    for sheet in workbook.iter():
        if not sheet.tag.endswith("}sheet"):
            continue
        relationship_id = next((value for key, value in sheet.attrib.items() if key.endswith("}id")), None)
        if relationship_id is None or relationship_id not in targets:
            raise PipelineError(f"cannot resolve XLSX sheet relationship for {sheet.attrib.get('name')!r}")
        target = targets[relationship_id].lstrip("/")
        if not target.startswith("xl/"):
            target = f"xl/{target}"
        sheets.append((sheet.attrib["name"], target))
    return sheets


def extract_xlsx_rows(source_id: str, artifact: Path) -> List[Dict[str, Any]]:
    try:
        with zipfile.ZipFile(artifact) as archive:
            shared = xlsx_shared_strings(archive)
            extracted: List[Dict[str, Any]] = []
            for sheet_name, target in xlsx_sheets(archive):
                root = ET.fromstring(archive.read(target))
                for row in (node for node in root.iter() if node.tag.endswith("}row")):
                    cells: List[Dict[str, str]] = []
                    for cell in (node for node in row if node.tag.endswith("}c")):
                        reference = cell.attrib.get("r", "")
                        cell_type = cell.attrib.get("t")
                        value_node = next((node for node in cell if node.tag.endswith("}v")), None)
                        if cell_type == "inlineStr":
                            value = xml_text(cell)
                        elif value_node is None or value_node.text is None:
                            value = ""
                        elif cell_type == "s":
                            try:
                                value = shared[int(value_node.text)]
                            except (ValueError, IndexError) as error:
                                raise PipelineError(f"invalid shared-string index at {sheet_name}!{reference}") from error
                        else:
                            value = value_node.text
                        value = normalize_cell(value)
                        if value:
                            cells.append({"column": column_name(reference), "value": value})
                    if cells:
                        row_number = int(row.attrib.get("r", len(extracted) + 1))
                        extracted.append(
                            {
                                "cells": cells,
                                "extraction_method": "xlsx-xml",
                                "row_number": row_number,
                                "sheet_name": normalize_cell(sheet_name),
                                "source_id": source_id,
                                "source_locator": f"sheet:{normalize_cell(sheet_name)};row:{row_number}",
                            }
                        )
            return extracted
    except (OSError, zipfile.BadZipFile, KeyError, ET.ParseError) as error:
        raise PipelineError(f"cannot extract XLSX {artifact}: {error}") from error


def run_pdftotext(artifact: Path, output: Path, executable: str = "pdftotext") -> str:
    version = tool_version([executable, "-v"])
    command = [executable, "-layout", "-enc", "UTF-8", str(artifact), str(output)]
    try:
        subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except (OSError, subprocess.CalledProcessError) as error:
        raise PipelineError(f"native PDF extraction failed using {' '.join(command)}: {error}") from error
    return version


def extract_pdf_lines(source_id: str, text: str, method: str = "pdftotext-layout") -> List[Dict[str, Any]]:
    records: List[Dict[str, Any]] = []
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    for page_number, page in enumerate(normalized.split("\f"), 1):
        for line_number, line in enumerate(page.splitlines(), 1):
            line = unicodedata.normalize("NFC", line.rstrip())
            if not line.strip():
                continue
            records.append(
                {
                    "extraction_method": method,
                    "line_number": line_number,
                    "page_number": page_number,
                    "source_id": source_id,
                    "source_locator": f"page:{page_number};line:{line_number}",
                    "text": line,
                }
            )
    return records


def import_pymupdf() -> Any:
    try:
        import fitz  # type: ignore
    except ImportError as error:
        raise PipelineError(
            "PyMuPDF is unavailable; run this command with a pinned environment containing PyMuPDF"
        ) from error
    return fitz


def extract_hsk_exam_table(source_id: str, artifact: Path) -> Tuple[List[Dict[str, Any]], str]:
    """Extract the fixed five-column vocabulary table from the 1219 syllabus.

    The 11,000 records occupy PDF pages 80--354 (one-indexed), 40 records per
    page. Geometry avoids diagonal watermark text interleaved by plain-text
    reading order. Every retained span remains in the raw record for audit.
    """
    fitz = import_pymupdf()
    document = fitz.open(artifact)
    if document.page_count < 354:
        raise PipelineError(f"{source_id}: expected at least 354 PDF pages, found {document.page_count}")
    output: List[Dict[str, Any]] = []
    for page_index in range(79, 354):
        page = document[page_index]
        spans: List[Dict[str, Any]] = []
        for block in page.get_text("dict", sort=True).get("blocks", []):
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    text = normalize_cell(str(span.get("text", "")))
                    if not text or float(span.get("size", 0)) >= 20:
                        continue
                    bbox = [round(float(value), 3) for value in span["bbox"]]
                    spans.append(
                        {
                            "bbox": bbox,
                            "font": str(span.get("font", "")),
                            "size": round(float(span.get("size", 0)), 3),
                            "text": text,
                        }
                    )
        sequence_spans = [
            span
            for span in spans
            if 65 <= span["bbox"][0] < 115 and re.fullmatch(r"[0-9]{1,5}", span["text"])
        ]
        for sequence_span in sequence_spans:
            center_y = (sequence_span["bbox"][1] + sequence_span["bbox"][3]) / 2
            row_spans = [
                span
                for span in spans
                if abs(((span["bbox"][1] + span["bbox"][3]) / 2) - center_y) < 3.5
            ]
            row_spans.sort(key=lambda span: span["bbox"][0])

            def column(first: float, last: float) -> str:
                return "".join(span["text"] for span in row_spans if first <= span["bbox"][0] < last)

            sequence = int(sequence_span["text"])
            output.append(
                {
                    "extraction_method": "pymupdf-native-table",
                    "fields": {
                        "headword_raw": column(215, 300),
                        "level_raw": column(115, 215),
                        "part_of_speech_raw": column(430, 590),
                        "pinyin_raw": column(300, 430),
                        "source_sequence": str(sequence),
                    },
                    "page_number": page_index + 1,
                    "row_spans": row_spans,
                    "source_id": source_id,
                    "source_locator": f"page:{page_index + 1};sequence:{sequence}",
                }
            )
    sequences = [int(record["fields"]["source_sequence"]) for record in output]
    if sequences != list(range(1, 11001)):
        missing = sorted(set(range(1, 11001)) - set(sequences))
        duplicates = sorted(sequence for sequence, count in Counter(sequences).items() if count > 1)
        raise PipelineError(
            f"{source_id}: table sequence is not exactly 1..11000; missing={missing[:20]}, duplicates={duplicates[:20]}"
        )
    return output, str(fitz.VersionBind)


def pdf_quality(records: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    joined = "\n".join(str(record.get("text", "")) for record in records)
    return {
        "han_characters": len(HAN_RE.findall(joined)),
        "nonblank_lines": len(records),
        "replacement_characters": joined.count("\ufffd"),
    }


def extract_source(
    manifest: Mapping[str, Any], source_id: str, artifact_dir: Path, raw_dir: Path, pdftotext: str,
    pdf_engine: str = "auto",
) -> Tuple[Path, Dict[str, Any]]:
    source = get_source(manifest, source_id)
    artifact = artifact_dir / source["artifact_filename"]
    if not artifact.is_file():
        raise PipelineError(f"missing authoritative artifact: {artifact}")
    output = raw_dir / f"{source_id}.jsonl"
    if source["media_type"] == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet":
        records = extract_xlsx_rows(source_id, artifact)
        metadata = {"engine": "python-stdlib-zipfile-etree", "engine_version": sys.version.split()[0], "rows": len(records)}
    elif source["media_type"] == "application/pdf" and (
        pdf_engine == "pymupdf-table" or (pdf_engine == "auto" and source_id == "hsk_exam2025")
    ):
        records, version = extract_hsk_exam_table(source_id, artifact)
        metadata = {
            "engine": "pymupdf-native-table",
            "engine_version": version,
            "page_range": "80-354",
            "rows": len(records),
        }
    elif source["media_type"] == "application/pdf":
        with tempfile.TemporaryDirectory(prefix="hsk-pdf-") as temporary:
            text_path = Path(temporary) / "layout.txt"
            version = run_pdftotext(artifact, text_path, pdftotext)
            text = text_path.read_text(encoding="utf-8")
        records = extract_pdf_lines(source_id, text)
        metadata = {"engine": "pdftotext-layout", "engine_version": version, **pdf_quality(records)}
        minimum_han = int(source.get("native_extraction", {}).get("minimum_han_characters", 1))
        if metadata["han_characters"] < minimum_han:
            raise PipelineError(
                f"{source_id}: native extraction yielded {metadata['han_characters']} Han characters; "
                f"minimum is {minimum_han}. Isolate OCR to documented vocabulary pages."
            )
    else:
        raise PipelineError(f"{source_id}: unsupported media type {source['media_type']!r}")
    write_jsonl(output, records)
    metadata.update(
        {
            "artifact_sha256": sha256_file(artifact),
            "output_sha256": sha256_file(output),
            "source_id": source_id,
        }
    )
    write_json(raw_dir / f"{source_id}.metadata.json", metadata)
    return output, metadata


def compiled_patterns(profile: Mapping[str, Any]) -> List[re.Pattern[str]]:
    patterns = profile.get("row_patterns")
    if not isinstance(patterns, list) or not patterns:
        raise PipelineError("profile.row_patterns must contain at least one regular expression")
    result: List[re.Pattern[str]] = []
    for pattern in patterns:
        try:
            result.append(re.compile(pattern))
        except re.error as error:
            raise PipelineError(f"invalid row pattern {pattern!r}: {error}") from error
    return result


def match_text_row(record: Mapping[str, Any], patterns: Sequence[re.Pattern[str]]) -> Optional[Dict[str, str]]:
    text = str(record.get("text", ""))
    for pattern in patterns:
        match = pattern.fullmatch(text.strip())
        if match:
            return {name: normalize_cell(value or "") for name, value in match.groupdict().items()}
    return None


def row_cells(record: Mapping[str, Any]) -> Dict[str, str]:
    return {str(cell["column"]): str(cell["value"]) for cell in record.get("cells", [])}


def level_for_sheet(sheet_name: str, profile: Mapping[str, Any]) -> Optional[str]:
    for pattern, level in profile.get("sheet_levels", {}).items():
        if re.fullmatch(pattern, sheet_name, re.IGNORECASE):
            return str(level)
    return None


def canonical_record(raw: Mapping[str, Any], fields: Mapping[str, str], default_level: Optional[str] = None) -> Dict[str, Any]:
    return {
        "correction_ids": "",
        "extraction_method": raw.get("extraction_method", ""),
        "additional_levels": fields.get("additional_levels") or "",
        "headword_raw": fields.get("headword_raw") or fields.get("simplified") or fields.get("headword") or "",
        "level": fields.get("level") or default_level or "",
        "level_raw": fields.get("level_raw") or fields.get("level") or default_level or "",
        "part_of_speech_raw": fields.get("part_of_speech") or fields.get("part_of_speech_raw") or "",
        "pinyin_raw": fields.get("pinyin") or fields.get("pinyin_raw") or "",
        "simplified": fields.get("simplified") or fields.get("headword") or "",
        "source_id": raw.get("source_id", ""),
        "source_locator": raw.get("source_locator", ""),
        "source_sequence": fields.get("sequence") or fields.get("source_sequence") or "",
        "sense_label": fields.get("sense_label") or "",
        "traditional": fields.get("traditional") or "",
    }


def parse_raw_records(raw: Sequence[Mapping[str, Any]], profile: Mapping[str, Any]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    if profile.get("schema_version") != SCHEMA_VERSION:
        raise PipelineError("unsupported parser profile schema")
    kind = profile.get("input_kind")
    parsed: List[Dict[str, Any]] = []
    rejected: List[Dict[str, Any]] = []
    if kind == "pdf-lines":
        patterns = compiled_patterns(profile)
        page_ranges = profile.get("page_ranges", [])
        for record in raw:
            page = int(record.get("page_number", 0))
            if page_ranges and not any(int(first) <= page <= int(last) for first, last in page_ranges):
                continue
            fields = match_text_row(record, patterns)
            if fields is None:
                if HAN_RE.search(str(record.get("text", ""))):
                    rejected.append(dict(record))
                continue
            parsed.append(canonical_record(record, fields))
    elif kind == "hsk-table-rows":
        sense_pattern = re.compile(str(profile.get("sense_suffix_pattern", r"^(?P<headword>.+?)(?P<sense>[1-9])$")))
        for record in raw:
            fields = {key: normalize_cell(str(value)) for key, value in record.get("fields", {}).items()}
            level_raw = fields.get("level_raw", "")
            levels = re.findall(r"7-9|[1-6]", level_raw)
            headword_raw = fields.get("headword_raw", "")
            if not levels or not headword_raw or not fields.get("pinyin_raw"):
                rejected.append(dict(record))
                continue
            simplified = headword_raw
            sense_label = ""
            sense_match = sense_pattern.fullmatch(headword_raw)
            if sense_match and HAN_RE.search(sense_match.group("headword")):
                simplified = sense_match.group("headword")
                sense_label = sense_match.group("sense")
            parsed.append(
                canonical_record(
                    record,
                    {
                        **fields,
                        "additional_levels": ";".join(levels[1:]),
                        "headword_raw": headword_raw,
                        "level": levels[0],
                        "sense_label": sense_label,
                        "simplified": simplified,
                    },
                )
            )
    elif kind == "xlsx-rows":
        columns = profile.get("columns")
        if not isinstance(columns, dict) or "simplified" not in columns:
            raise PipelineError("XLSX profile.columns must map at least simplified to a column")
        skip_values = {normalize_cell(value) for value in profile.get("skip_headwords", [])}
        skip_rows = {int(value) for value in profile.get("skip_rows", [])}
        for record in raw:
            if int(record.get("row_number", 0)) in skip_rows:
                continue
            cells = row_cells(record)
            fields = {field: normalize_cell(cells.get(str(column), "")) for field, column in columns.items()}
            if not fields.get("simplified") or fields["simplified"] in skip_values:
                continue
            default_level = level_for_sheet(str(record.get("sheet_name", "")), profile)
            if not fields.get("level") and default_level is None:
                rejected.append(dict(record))
                continue
            if "sequence_from_row_offset" in profile:
                fields["source_sequence"] = str(
                    int(record.get("row_number", 0)) + int(profile["sequence_from_row_offset"])
                )
            parsed.append(canonical_record(record, fields, default_level))
    else:
        raise PipelineError(f"unsupported profile input_kind: {kind!r}")
    return parsed, rejected


def load_corrections(path: Path, source_id: str) -> List[Mapping[str, Any]]:
    ledger = read_json(path)
    if ledger.get("schema_version") != SCHEMA_VERSION:
        raise PipelineError("unsupported correction-ledger schema")
    corrections = [item for item in ledger.get("corrections", []) if item.get("source_id") == source_id]
    seen: set[str] = set()
    for correction in corrections:
        required = ("id", "action", "reason", "evidence")
        missing = [field for field in required if not correction.get(field)]
        if missing:
            raise PipelineError(f"correction lacks {', '.join(missing)}: {correction!r}")
        if correction["id"] in seen:
            raise PipelineError(f"duplicate correction id: {correction['id']}")
        seen.add(correction["id"])
    return corrections


def apply_corrections(records: List[Dict[str, Any]], corrections: Sequence[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    output = [dict(record) for record in records]
    for correction in corrections:
        action = correction["action"]
        locator = correction.get("source_locator")
        indexes = [index for index, record in enumerate(output) if record["source_locator"] == locator]
        if action == "insert":
            if locator is None or not correction.get("fields"):
                raise PipelineError(f"{correction['id']}: insert needs source_locator and fields")
            inserted = {field: "" for field in CANONICAL_FIELDS}
            inserted.update(correction["fields"])
            inserted["source_locator"] = locator
            inserted["correction_ids"] = correction["id"]
            output.append(inserted)
            continue
        if len(indexes) != 1:
            raise PipelineError(f"{correction['id']}: expected one record at {locator!r}, found {len(indexes)}")
        index = indexes[0]
        if action == "exclude":
            del output[index]
        elif action == "replace_fields":
            fields = correction.get("fields")
            if not isinstance(fields, dict) or not fields:
                raise PipelineError(f"{correction['id']}: replace_fields needs non-empty fields")
            unknown = set(fields) - set(CANONICAL_FIELDS)
            if unknown:
                raise PipelineError(f"{correction['id']}: unknown canonical fields: {sorted(unknown)}")
            output[index].update(fields)
            existing = [value for value in str(output[index].get("correction_ids", "")).split(";") if value]
            output[index]["correction_ids"] = ";".join(existing + [correction["id"]])
        else:
            raise PipelineError(f"{correction['id']}: unsupported action {action!r}")
    return output


def canonical_csv_bytes(records: Sequence[Mapping[str, Any]]) -> bytes:
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=CANONICAL_FIELDS, extrasaction="raise", lineterminator="\n")
    writer.writeheader()
    for record in records:
        writer.writerow({field: unicodedata.normalize("NFC", str(record.get(field, ""))) for field in CANONICAL_FIELDS})
    return buffer.getvalue().encode("utf-8")


def read_canonical_csv(path: Path) -> List[Dict[str, str]]:
    try:
        with path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            if tuple(reader.fieldnames or ()) != CANONICAL_FIELDS:
                raise PipelineError(f"{path}: unexpected canonical CSV header")
            return [dict(row) for row in reader]
    except OSError as error:
        raise PipelineError(f"cannot read canonical CSV {path}: {error}") from error


def validate_records(source: Mapping[str, Any], records: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    errors: List[str] = []
    for index, record in enumerate(records, 1):
        for field in REQUIRED_CANONICAL_FIELDS:
            if not str(record.get(field, "")).strip():
                errors.append(f"row {index}: blank {field}")
        if record.get("source_id") != source["id"]:
            errors.append(f"row {index}: source_id differs from {source['id']}")
        text = "".join(str(record.get(field, "")) for field in CANONICAL_FIELDS)
        if "\ufeff" in text or "\ufffd" in text or "\x00" in text:
            errors.append(f"row {index}: BOM, replacement, or NUL character")
        if not HAN_RE.search(str(record.get("simplified", ""))):
            errors.append(f"row {index}: simplified headword contains no Han character")
    expected = source["expected"]
    levels = Counter(str(record.get("level", "")) for record in records)
    expected_levels = {str(level): int(count) for level, count in expected["levels"].items()}
    if len(records) != int(expected["source_rows_total"]):
        errors.append(f"total count {len(records)} != {expected['source_rows_total']}")
    if dict(sorted(levels.items())) != dict(sorted(expected_levels.items())):
        errors.append(f"level counts {dict(sorted(levels.items()))} != {dict(sorted(expected_levels.items()))}")
    identity_counts = Counter(
        (record.get("simplified"), record.get("traditional"), record.get("pinyin_raw"), record.get("level"))
        for record in records
    )
    duplicates = [list(identity) + [count] for identity, count in identity_counts.items() if count > 1]
    expanded_levels: Counter[str] = Counter()
    for record in records:
        expanded_levels[str(record.get("level", ""))] += 1
        expanded_levels.update(level for level in str(record.get("additional_levels", "")).split(";") if level)
    expected_expanded = expected.get("expanded_level_assignments_for_review")
    if expected_expanded is not None:
        normalized_expected_expanded = {str(level): int(count) for level, count in expected_expanded.items()}
        if dict(sorted(expanded_levels.items())) != dict(sorted(normalized_expected_expanded.items())):
            errors.append(
                f"expanded level counts {dict(sorted(expanded_levels.items()))} "
                f"!= {dict(sorted(normalized_expected_expanded.items()))}"
            )
    report = {
        "duplicate_lexical_rows": sorted(duplicates),
        "errors": errors,
        "expanded_level_assignment_counts": dict(sorted(expanded_levels.items())),
        "expanded_level_assignments_total": sum(expanded_levels.values()),
        "level_counts": dict(sorted(levels.items())),
        "source_id": source["id"],
        "source_rows_total": len(records),
    }
    if errors:
        raise PipelineError(f"{source['id']} validation failed:\n  " + "\n  ".join(errors[:50]))
    return report


def canonicalize(
    manifest: Mapping[str, Any], source_id: str, raw_path: Path, profile_path: Path, corrections_path: Path, output: Path
) -> Dict[str, Any]:
    source = get_source(manifest, source_id)
    profile = read_json(profile_path)
    if profile.get("source_id") != source_id:
        raise PipelineError(f"parser profile source_id differs from {source_id}")
    if profile.get("reviewed") is not True:
        raise PipelineError(f"{profile_path} is not marked reviewed; inspect the authoritative rows first")
    parsed, rejected = parse_raw_records(read_jsonl(raw_path), profile)
    corrections = load_corrections(corrections_path, source_id)
    corrected = apply_corrections(parsed, corrections)
    report = validate_records(source, corrected)
    write_bytes_if_changed(output, canonical_csv_bytes(corrected))
    report.update(
        {
            "canonical_sha256": sha256_file(output),
            "corrections_applied": [correction["id"] for correction in corrections],
            "parser_profile_sha256": sha256_file(profile_path),
            "raw_sha256": sha256_file(raw_path),
            "rejected_candidate_rows": len(rejected),
        }
    )
    return report


def compare_file(expected: Path, actual: Path) -> None:
    if not expected.exists():
        raise PipelineError(f"tracked output does not exist: {expected}")
    if expected.read_bytes() != actual.read_bytes():
        raise PipelineError(f"reproducibility check failed: {expected} differs from regenerated output")


def cmd_validate_config(args: argparse.Namespace) -> None:
    manifest = read_json(args.manifest)
    sources = manifest_sources(manifest)
    ledger = read_json(args.corrections)
    if ledger.get("schema_version") != SCHEMA_VERSION or not isinstance(ledger.get("corrections"), list):
        raise PipelineError("invalid correction ledger")
    for profile_path in sorted(args.profiles.glob("*.json")):
        profile = read_json(profile_path)
        get_source(manifest, profile.get("source_id", ""))
        if profile.get("input_kind") == "pdf-lines":
            compiled_patterns(profile)
        elif profile.get("input_kind") not in ("xlsx-rows", "hsk-table-rows"):
            raise PipelineError(f"{profile_path}: unsupported input_kind")
    print(f"validated {len(sources)} sources, {len(list(args.profiles.glob('*.json')))} profiles")


def cmd_lock(args: argparse.Namespace) -> None:
    lock = build_lock(read_json(args.manifest), args.artifact_dir, args.retrieval_date)
    if args.output:
        write_json(args.output, lock)
        print(f"wrote {args.output}")
    else:
        sys.stdout.buffer.write(json_bytes(lock))


def cmd_verify_sources(args: argparse.Namespace) -> None:
    verify_lock(read_json(args.manifest), read_json(args.lock), args.artifact_dir, args.source)
    print("all authoritative artifacts match the source lock")


def cmd_download(args: argparse.Namespace) -> None:
    download_sources(read_json(args.manifest), args.artifact_dir)


def cmd_extract(args: argparse.Namespace) -> None:
    manifest = read_json(args.manifest)
    identifiers = [args.source] if args.source else [source["id"] for source in manifest_sources(manifest)]
    if args.lock:
        verify_lock(manifest, read_json(args.lock), args.artifact_dir, identifiers)
    for source_id in identifiers:
        output, metadata = extract_source(
            manifest, source_id, args.artifact_dir, args.raw_dir, args.pdftotext, args.pdf_engine
        )
        print(f"extracted {source_id} -> {output} ({metadata})")


def cmd_canonicalize(args: argparse.Namespace) -> None:
    manifest = read_json(args.manifest)
    report = canonicalize(manifest, args.source, args.raw, args.profile, args.corrections, args.output)
    if args.report:
        write_json(args.report, report)
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))


def cmd_validate(args: argparse.Namespace) -> None:
    source = get_source(read_json(args.manifest), args.source)
    report = validate_records(source, read_canonical_csv(args.canonical))
    if args.report:
        write_json(args.report, report)
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))


def cmd_check(args: argparse.Namespace) -> None:
    manifest = read_json(args.manifest)
    lock = read_json(args.lock)
    identifiers = args.source or [source["id"] for source in manifest_sources(manifest)]
    verify_lock(manifest, lock, args.artifact_dir, identifiers)
    with tempfile.TemporaryDirectory(prefix="hsk-repro-") as temporary_name:
        temporary = Path(temporary_name)
        raw_dir = temporary / "raw"
        for source in (get_source(manifest, source_id) for source_id in identifiers):
            source_id = source["id"]
            regenerated_raw, _ = extract_source(
                manifest, source_id, args.artifact_dir, raw_dir, args.pdftotext, args.pdf_engine
            )
            compare_file(args.tracked_raw_dir / regenerated_raw.name, regenerated_raw)
            regenerated_csv = temporary / f"{source_id}.csv"
            canonicalize(
                manifest,
                source_id,
                regenerated_raw,
                args.profiles / f"{source_id}.json",
                args.corrections,
                regenerated_csv,
            )
            compare_file(args.canonical_dir / regenerated_csv.name, regenerated_csv)
    print("all raw and canonical outputs regenerate byte-for-byte")


def path_argument(value: str) -> Path:
    return Path(value)


def parser() -> argparse.ArgumentParser:
    root = Path(__file__).resolve().parents[1]
    provenance = root / "data" / "hsk-sources"
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--manifest", type=path_argument, default=provenance / "sources.json")
    subparsers = result.add_subparsers(dest="command", required=True)

    validate_config = subparsers.add_parser("validate-config", help="validate manifest, correction ledger, and profiles")
    validate_config.add_argument("--corrections", type=path_argument, default=provenance / "corrections.json")
    validate_config.add_argument("--profiles", type=path_argument, default=provenance / "profiles")
    validate_config.set_defaults(function=cmd_validate_config)

    download = subparsers.add_parser("download", help="download authoritative artifacts (never updates the lock)")
    download.add_argument("--artifact-dir", type=path_argument, required=True)
    download.set_defaults(function=cmd_download)

    lock = subparsers.add_parser("lock", help="fingerprint all authoritative artifacts")
    lock.add_argument("--artifact-dir", type=path_argument, required=True)
    lock.add_argument("--retrieval-date", required=True)
    lock.add_argument("--output", type=path_argument)
    lock.set_defaults(function=cmd_lock)

    verify = subparsers.add_parser("verify-sources", help="verify artifact bytes against the reviewed lock")
    verify.add_argument("--artifact-dir", type=path_argument, required=True)
    verify.add_argument("--lock", type=path_argument, required=True)
    verify.add_argument("--source", action="append", help="verify only this source (repeatable)")
    verify.set_defaults(function=cmd_verify_sources)

    extract = subparsers.add_parser("extract", help="losslessly extract source rows/lines")
    extract.add_argument("--artifact-dir", type=path_argument, required=True)
    extract.add_argument("--raw-dir", type=path_argument, required=True)
    extract.add_argument("--lock", type=path_argument)
    extract.add_argument("--source")
    extract.add_argument("--pdftotext", default="pdftotext")
    extract.add_argument("--pdf-engine", choices=("auto", "pdftotext", "pymupdf-table"), default="auto")
    extract.set_defaults(function=cmd_extract)

    canonical = subparsers.add_parser("canonicalize", help="parse, correct, validate, and serialize one dataset")
    canonical.add_argument("--source", required=True)
    canonical.add_argument("--raw", type=path_argument, required=True)
    canonical.add_argument("--profile", type=path_argument, required=True)
    canonical.add_argument("--corrections", type=path_argument, default=provenance / "corrections.json")
    canonical.add_argument("--output", type=path_argument, required=True)
    canonical.add_argument("--report", type=path_argument)
    canonical.set_defaults(function=cmd_canonicalize)

    validate = subparsers.add_parser("validate", help="validate one canonical dataset against official counts")
    validate.add_argument("--source", required=True)
    validate.add_argument("--canonical", type=path_argument, required=True)
    validate.add_argument("--report", type=path_argument)
    validate.set_defaults(function=cmd_validate)

    check = subparsers.add_parser("check", help="regenerate every output and compare bytes")
    check.add_argument("--artifact-dir", type=path_argument, required=True)
    check.add_argument("--lock", type=path_argument, required=True)
    check.add_argument("--tracked-raw-dir", type=path_argument, required=True)
    check.add_argument("--canonical-dir", type=path_argument, required=True)
    check.add_argument("--profiles", type=path_argument, default=provenance / "profiles")
    check.add_argument("--corrections", type=path_argument, default=provenance / "corrections.json")
    check.add_argument("--pdftotext", default="pdftotext")
    check.add_argument("--pdf-engine", choices=("auto", "pdftotext", "pymupdf-table"), default="auto")
    check.add_argument("--source", action="append", help="check only this completed source (repeatable)")
    check.set_defaults(function=cmd_check)
    return result


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parser().parse_args(argv)
    try:
        args.function(args)
    except PipelineError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
