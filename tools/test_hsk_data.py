#!/usr/bin/env python3
"""Standard-library tests for tools/hsk_data.py."""

import hashlib
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

import hsk_data


def write_minimal_xlsx(path: Path) -> None:
    files = {
        "xl/workbook.xml": """<?xml version="1.0" encoding="UTF-8"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"
 xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
 <sheets><sheet name="HSK 1级" sheetId="1" r:id="rId1"/></sheets>
</workbook>""",
        "xl/_rels/workbook.xml.rels": """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
 <Relationship Id="rId1" Target="worksheets/sheet1.xml"
  Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet"/>
</Relationships>""",
        "xl/sharedStrings.xml": """<?xml version="1.0" encoding="UTF-8"?>
<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
 <si><t>序号</t></si><si><t>词语</t></si><si><t>拼音</t></si>
 <si><t>爱</t></si><si><r><t>à</t></r><r><t>i</t></r></si>
</sst>""",
        "xl/worksheets/sheet1.xml": """<?xml version="1.0" encoding="UTF-8"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>
 <row r="1"><c r="A1" t="s"><v>0</v></c><c r="B1" t="s"><v>1</v></c><c r="C1" t="s"><v>2</v></c></row>
 <row r="2"><c r="A2"><v>1</v></c><c r="B2" t="s"><v>3</v></c><c r="C2" t="s"><v>4</v></c></row>
</sheetData></worksheet>""",
    }
    with zipfile.ZipFile(path, "w") as archive:
        for name, contents in files.items():
            archive.writestr(name, contents)


def tiny_manifest(filename: str, digest_counts=None):
    return {
        "schema_version": 1,
        "sources": [
            {
                "id": "fixture",
                "source_name": "fixture",
                "issuing_authority": "test",
                "landing_page_url": "https://example.invalid/landing",
                "document_url": "https://example.invalid/file",
                "artifact_filename": filename,
                "media_type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                "expected": digest_counts or {"source_rows_total": 1, "levels": {"1": 1}},
            }
        ],
    }


class PipelineTests(unittest.TestCase):
    def test_xlsx_extraction_preserves_location_and_rich_text(self):
        with tempfile.TemporaryDirectory() as name:
            workbook = Path(name) / "fixture.xlsx"
            write_minimal_xlsx(workbook)
            rows = hsk_data.extract_xlsx_rows("fixture", workbook)

        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[1]["source_locator"], "sheet:HSK 1级;row:2")
        self.assertEqual(rows[1]["cells"], [
            {"column": "A", "value": "1"},
            {"column": "B", "value": "爱"},
            {"column": "C", "value": "ài"},
        ])

    def test_xlsx_profile_parses_only_data_rows(self):
        with tempfile.TemporaryDirectory() as name:
            workbook = Path(name) / "fixture.xlsx"
            write_minimal_xlsx(workbook)
            raw = hsk_data.extract_xlsx_rows("fixture", workbook)
        profile = {
            "schema_version": 1,
            "input_kind": "xlsx-rows",
            "columns": {"source_sequence": "A", "simplified": "B", "pinyin": "C"},
            "sheet_levels": {".*1级.*": "1"},
            "skip_headwords": ["词语"],
        }
        parsed, rejected = hsk_data.parse_raw_records(raw, profile)
        self.assertEqual(rejected, [])
        self.assertEqual(parsed[0]["simplified"], "爱")
        self.assertEqual(parsed[0]["pinyin_raw"], "ài")
        self.assertEqual(parsed[0]["level"], "1")

    def test_pdf_lines_are_page_stable_and_normalized(self):
        records = hsk_data.extract_pdf_lines("fixture", "  1  爱  ài  1  \r\n\r\n\f2 学习 xuéxí 1\n")
        self.assertEqual([row["source_locator"] for row in records], ["page:1;line:1", "page:2;line:1"])
        self.assertEqual(hsk_data.pdf_quality(records)["nonblank_lines"], 2)
        self.assertGreaterEqual(hsk_data.pdf_quality(records)["han_characters"], 3)

    def test_lock_detects_artifact_drift(self):
        with tempfile.TemporaryDirectory() as name:
            directory = Path(name)
            artifact = directory / "fixture.bin"
            artifact.write_bytes(b"authoritative bytes")
            manifest = tiny_manifest(artifact.name)
            lock = hsk_data.build_lock(manifest, directory, "2026-09-04")
            self.assertEqual(lock["sources"][0]["sha256"], hashlib.sha256(artifact.read_bytes()).hexdigest())
            hsk_data.verify_lock(manifest, lock, directory)
            artifact.write_bytes(b"changed")
            with self.assertRaisesRegex(hsk_data.PipelineError, "SHA-256 mismatch"):
                hsk_data.verify_lock(manifest, lock, directory)

    def test_corrections_are_explicit_and_traceable(self):
        record = {
            field: "" for field in hsk_data.CANONICAL_FIELDS
        }
        record.update({"source_id": "fixture", "source_locator": "page:1;line:2", "level": "1", "simplified": "爰"})
        corrections = [{
            "id": "fixture-001",
            "source_id": "fixture",
            "source_locator": "page:1;line:2",
            "action": "replace_fields",
            "fields": {"simplified": "爱"},
            "reason": "fixture",
            "evidence": "fixture",
        }]
        corrected = hsk_data.apply_corrections([record], corrections)
        self.assertEqual(corrected[0]["simplified"], "爱")
        self.assertEqual(corrected[0]["correction_ids"], "fixture-001")

    def test_validation_checks_counts_and_forbidden_characters(self):
        source = tiny_manifest("fixture")["sources"][0]
        record = {field: "" for field in hsk_data.CANONICAL_FIELDS}
        record.update({"source_id": "fixture", "source_locator": "sheet:x;row:1", "level": "1", "simplified": "爱"})
        report = hsk_data.validate_records(source, [record])
        self.assertEqual(report["level_counts"], {"1": 1})
        record["simplified"] = "\ufeff爱"
        with self.assertRaisesRegex(hsk_data.PipelineError, "BOM"):
            hsk_data.validate_records(source, [record])

    def test_serialization_is_deterministic_utf8_lf(self):
        record = {field: "" for field in hsk_data.CANONICAL_FIELDS}
        record.update({"source_id": "fixture", "source_locator": "sheet:x;row:1", "level": "1", "simplified": "爱"})
        first = hsk_data.canonical_csv_bytes([record])
        second = hsk_data.canonical_csv_bytes([dict(reversed(list(record.items())))])
        self.assertEqual(first, second)
        self.assertNotIn(b"\r\n", first)
        self.assertIn("爱".encode("utf-8"), first)

    def test_unreviewed_profile_cannot_create_canonical_data(self):
        with tempfile.TemporaryDirectory() as name:
            directory = Path(name)
            manifest_path = directory / "manifest.json"
            raw_path = directory / "raw.jsonl"
            profile_path = directory / "profile.json"
            corrections_path = directory / "corrections.json"
            manifest_path.write_text(json.dumps(tiny_manifest("fixture.xlsx")), encoding="utf-8")
            hsk_data.write_jsonl(raw_path, [])
            profile_path.write_text(json.dumps({
                "schema_version": 1,
                "source_id": "fixture",
                "reviewed": False,
                "input_kind": "xlsx-rows",
                "columns": {"simplified": "A"},
            }), encoding="utf-8")
            corrections_path.write_text(json.dumps({"schema_version": 1, "corrections": []}), encoding="utf-8")
            with self.assertRaisesRegex(hsk_data.PipelineError, "not marked reviewed"):
                hsk_data.canonicalize(
                    hsk_data.read_json(manifest_path), "fixture", raw_path, profile_path,
                    corrections_path, directory / "canonical.csv"
                )


if __name__ == "__main__":
    unittest.main()
