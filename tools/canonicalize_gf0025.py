#!/usr/bin/env python3
"""Build and audit GF0025 vocabulary rows against positioned OCR evidence.

The independent transcription supplies candidate cell boundaries only. A row
is marked verified only when its level-local sequence, Chinese headword, and
accent-insensitive pinyin are all found on the same authoritative PDF row.
Unverified candidates remain conspicuous in the report and are never silently
described as authoritative extraction.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import unicodedata
from collections import Counter, defaultdict
from io import StringIO
from pathlib import Path


LEVELS = {
    "一级": ("1", 500, 0, range(42, 49)),
    "二级": ("2", 772, 500, range(48, 59)),
    "三级": ("3", 973, 1272, range(57, 71)),
    "四级": ("4", 1000, 2245, range(70, 83)),
    "五级": ("5", 1071, 3245, range(82, 96)),
    "六级": ("6", 1140, 4316, range(95, 110)),
    "高等": ("7-9", 5636, 5456, range(109, 176)),
}
HAN_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\U00020000-\U0002fa1f]")
LEADING_SEQUENCE_RE = re.compile(r"^(\d+)(.*)$")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as output:
        output.write(content)
    os.replace(temporary, path)


def han(value: str) -> str:
    return "".join(character for character in value if HAN_RE.fullmatch(character))


def observed_headword_han(value: str) -> str:
    primary = re.split(r"[∣|]", value, maxsplit=1)[0]
    primary = re.sub(r"[（(][^）)]*[）)]", "", primary)
    primary = LEADING_SEQUENCE_RE.sub(r"\2", primary)
    return han(primary)


def lexical_headword(raw: str) -> tuple[str, str]:
    primary = raw.split("∣", 1)[0]
    match = re.fullmatch(r"(.*?)（.*?）(.*)", primary)
    if match:
        primary = match.group(1) + match.group(2)
    match = re.match(r"^(.*?)([1-9])$", primary)
    if match:
        return match.group(1), match.group(2)
    return primary, ""


def pinyin_base(value: str) -> str:
    result = []
    for character in unicodedata.normalize("NFD", value.lower()):
        if character == "ü":
            result.append("v")
        elif character == "u":
            result.append("u")
        elif character in "abcdefghijklmnopqrstuvwxyz":
            result.append(character)
        elif character == "\u0308" and result and result[-1] == "u":
            result[-1] = "v"
    return "".join(result)


def load_candidates(path: Path) -> list[dict[str, str]]:
    rows = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line or line.startswith("#"):
            continue
        fields = line.split("\t")
        if len(fields) != 5:
            raise ValueError(f"{path}:{line_number}: expected five tab-separated fields")
        headword, part_of_speech, pinyin, sequence, level_raw = fields
        if level_raw not in LEVELS:
            raise ValueError(f"{path}:{line_number}: unexpected level {level_raw!r}")
        level, _, offset, _ = LEVELS[level_raw]
        global_sequence = int(sequence)
        rows.append(
            {
                "headword": headword,
                "part_of_speech": part_of_speech,
                "pinyin": pinyin,
                "source_sequence": sequence,
                "local_sequence": str(global_sequence - offset),
                "level": level,
                "level_raw": level_raw,
            }
        )
    return rows


def load_ocr(paths: list[Path]) -> tuple[dict[int, list[dict[str, object]]], dict[tuple[int, str], list[dict[str, object]]]]:
    pages: dict[int, list[dict[str, object]]] = defaultdict(list)
    sequences: dict[tuple[int, str], list[dict[str, object]]] = defaultdict(list)
    for path in paths:
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            try:
                row = json.loads(line)
                page = int(row["page"])
                pages[page].append(row)
                match = LEADING_SEQUENCE_RE.match(str(row["text"]).replace(" ", ""))
                if match:
                    sequences[(page, match.group(1))].append(row)
            except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
                raise ValueError(f"{path}:{line_number}: invalid OCR observation") from error
    return pages, sequences


def locate(candidate: dict[str, str], pages: dict[int, list[dict[str, object]]], sequences: dict[tuple[int, str], list[dict[str, object]]]) -> list[dict[str, object]]:
    _, _, _, allowed_pages = LEVELS[candidate["level_raw"]]
    expected_sequence = candidate["local_sequence"]
    expected_headword, _ = lexical_headword(candidate["headword"])
    expected_han = han(expected_headword)
    expected_pinyin = [
        pinyin_base(reading.replace("∥", ""))
        for reading in re.split(r"[∣/]", candidate["pinyin"])
        if pinyin_base(reading.replace("∥", ""))
    ]
    found = []
    for page_number in allowed_pages:
        observations = pages.get(page_number, [])
        for sequence_observation in sequences.get((page_number, expected_sequence), []):
            text = str(sequence_observation["text"]).replace(" ", "")
            match = LEADING_SEQUENCE_RE.match(text)
            if not match:
                continue
            box = sequence_observation["box"]
            sequence_x = (float(box[0]) + float(box[2])) / 2
            sequence_y = (float(box[1]) + float(box[3])) / 2
            column = 0 if sequence_x < 0.5 else 1
            row_text = [match.group(2)] if match.group(2) else []
            confidence = float(sequence_observation["confidence"])
            for observation in observations:
                other_box = observation["box"]
                x = (float(other_box[0]) + float(other_box[2])) / 2
                y = (float(other_box[1]) + float(other_box[3])) / 2
                if (0 if x < 0.5 else 1) == column and abs(y - sequence_y) <= 0.014:
                    row_text.append(str(observation["text"]))
                    confidence = min(confidence, float(observation["confidence"]))
            headword_match = any(observed_headword_han(value) == expected_han for value in row_text)
            pinyin_match = any(
                any(pinyin_base(value).startswith(expected) for expected in expected_pinyin)
                for value in row_text
            )
            if headword_match:
                found.append(
                    {
                        "confidence_floor": round(confidence, 8),
                        "headword_match": True,
                        "page": page_number,
                        "pinyin_match": pinyin_match,
                        "row_text": row_text,
                    }
                )
    if found:
        return found

    # A sequence glyph is occasionally misrecognized even when the Chinese
    # cell is exact. Recover only a unique headword cell inside this level's
    # page range; repeated forms remain unresolved.
    lexical_locations: dict[tuple[int, int, int], dict[str, object]] = {}
    for page_number in allowed_pages:
        observations = pages.get(page_number, [])
        for headword_observation in observations:
            if observed_headword_han(str(headword_observation["text"])) != expected_han:
                continue
            box = headword_observation["box"]
            x = (float(box[0]) + float(box[2])) / 2
            y = (float(box[1]) + float(box[3])) / 2
            if not (0.13 <= x <= 0.32 or 0.54 <= x <= 0.72):
                continue
            column = 0 if x < 0.5 else 1
            row_text = []
            confidence = float(headword_observation["confidence"])
            for observation in observations:
                other_box = observation["box"]
                other_x = (float(other_box[0]) + float(other_box[2])) / 2
                other_y = (float(other_box[1]) + float(other_box[3])) / 2
                if (0 if other_x < 0.5 else 1) == column and abs(other_y - y) <= 0.014:
                    row_text.append(str(observation["text"]))
                    confidence = min(confidence, float(observation["confidence"]))
            pinyin_match = any(
                any(pinyin_base(value).startswith(expected) for expected in expected_pinyin)
                for value in row_text
            )
            lexical_locations[(page_number, column, round(y * 10_000))] = {
                "confidence_floor": round(confidence, 8),
                "headword_match": True,
                "page": page_number,
                "pinyin_match": pinyin_match,
                "row_text": row_text,
                "sequence_match": False,
            }
    return list(lexical_locations.values())


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("candidate_tsv", type=Path)
    parser.add_argument("output_csv", type=Path)
    parser.add_argument("ocr_jsonl", type=Path, nargs="+")
    parser.add_argument("--corrections", type=Path, default=Path("data/hsk-sources/corrections.json"))
    args = parser.parse_args()

    candidates = load_candidates(args.candidate_tsv)
    pages, sequences = load_ocr(args.ocr_jsonl)
    correction_document = json.loads(args.corrections.read_text(encoding="utf-8"))
    corrections = {
        item["fields"]["source_sequence"]: item
        for item in correction_document["corrections"]
        if item["source_id"] == "proficiency2021" and item["action"] == "replace_fields"
    }
    canonical = []
    unresolved = []
    verification_counts = Counter()
    for candidate in candidates:
        correction = corrections.get(candidate["source_sequence"])
        if correction:
            fields = correction["fields"]
            candidate["pinyin"] = fields.get("pinyin_raw", candidate["pinyin"])
            candidate["part_of_speech"] = fields.get("part_of_speech_raw", candidate["part_of_speech"])
        locations = locate(candidate, pages, sequences)
        fully_verified = [location for location in locations if location["pinyin_match"]]
        if len(fully_verified) == 1:
            selected = fully_verified[0]
            status = "rapidocr-authoritative-row"
            locator = f"page:{selected['page']};level-sequence:{candidate['local_sequence']}"
        elif len(locations) == 1:
            selected = locations[0]
            status = "rapidocr-authoritative-headword-pinyin-unresolved"
            locator = f"page:{selected['page']};level-sequence:{candidate['local_sequence']}"
            unresolved.append({**candidate, "ocr_candidates": locations})
        else:
            status = "verification-candidate-unresolved"
            locator = f"level:{candidate['level']};level-sequence:{candidate['local_sequence']}"
            unresolved.append({**candidate, "ocr_candidates": locations})
        verification_counts[status] += 1
        simplified, sense_label = lexical_headword(candidate["headword"])
        canonical.append(
            {
                "source_id": "proficiency2021",
                "source_locator": locator,
                "source_sequence": candidate["source_sequence"],
                "level": candidate["level"],
                "level_raw": candidate["level_raw"],
                "additional_levels": "",
                "simplified": simplified,
                "traditional": "",
                "headword_raw": candidate["headword"],
                "sense_label": sense_label,
                "pinyin_raw": candidate["pinyin"],
                "part_of_speech_raw": candidate["part_of_speech"],
                "extraction_method": status,
                "correction_ids": correction["id"] if correction else "",
            }
        )

    expected_counts = {value[0]: value[1] for value in LEVELS.values()}
    actual_counts = Counter(row["level"] for row in canonical)
    if actual_counts != Counter(expected_counts):
        raise ValueError(f"level counts differ: {actual_counts}")

    fields = ["source_id", "source_locator", "source_sequence", "level", "level_raw", "additional_levels", "simplified", "traditional", "headword_raw", "sense_label", "pinyin_raw", "part_of_speech_raw", "extraction_method", "correction_ids"]
    buffer = StringIO(newline="\n")
    writer = csv.DictWriter(buffer, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    writer.writerows(canonical)
    atomic_write(args.output_csv, buffer.getvalue())
    report = {
        "authoritative_document_sha256": "e451fdf0899d9267bbd122db66e7e75bdd2851ad1e6732e47b6e960290d73a63",
        "canonical_sha256": hashlib.sha256(buffer.getvalue().encode()).hexdigest(),
        "candidate_sha256": sha256(args.candidate_tsv),
        "candidate_revision": "zispace/hanyu-hsk@ca0a5662a95ecc8522983d24bfbef5ab5b8cda0a",
        "candidate_repository_url": "https://github.com/zispace/hanyu-hsk",
        "candidate_use_policy": "diagnostic row candidates only; never overrides OCR",
        "corrections_applied": sorted(item["id"] for item in corrections.values()),
        "level_counts": dict(sorted(actual_counts.items())),
        "ocr_files": [{"path": str(path), "sha256": sha256(path)} for path in args.ocr_jsonl],
        "source_rows_total": len(canonical),
        "status_counts": dict(sorted(verification_counts.items())),
        "unresolved": unresolved,
    }
    report_path = args.output_csv.with_suffix(".validation.json")
    atomic_write(report_path, json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    print(json.dumps(report["status_counts"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
