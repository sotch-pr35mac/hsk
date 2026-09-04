import pathlib
import sys
import unittest

VERIFICATION = pathlib.Path(__file__).resolve().parents[1]
FIXTURES = pathlib.Path(__file__).resolve().parent / "fixtures"
sys.path.insert(0, str(VERIFICATION))

from hsk_verify.adapters import load_records
from hsk_verify.compare import compare_records
from hsk_verify.model import Record
from hsk_verify.report import json_report, markdown_report


class CompareTests(unittest.TestCase):
    def setUp(self):
        self.authoritative = load_records(
            "canonical-jsonl", FIXTURES / "authoritative.jsonl"
        )
        self.verification = load_records(
            "shawkynasr-2021-csv", FIXTURES / "shawkynasr.csv"
        )
        self.report = compare_records(
            self.authoritative.records,
            self.verification.records,
            authoritative_metadata={"name": "fixture canonical"},
            verification_metadata={"source_id": "fixture"},
        )

    def test_reports_all_required_discrepancy_categories(self):
        self.assertEqual(len(self.report.present_in_both), 4)
        self.assertEqual(len(self.report.level_disagreements), 2)
        # Pairwise disagreements are retained for polyphonic headwords so a
        # reviewer can see every competing reading rather than an arbitrary one.
        self.assertEqual(len(self.report.pinyin_disagreements), 3)
        self.assertEqual(len(self.report.authoritative_only), 2)
        self.assertEqual(len(self.report.verification_only), 2)
        self.assertEqual(len(self.report.duplicate_disagreements), 1)

    def test_explicit_traditional_form_can_match(self):
        matches = {
            row["authoritative"]["record_id"]: row["matched_headword"]
            for row in self.report.present_in_both
        }
        self.assertEqual(matches["auth:4"], "後")

    def test_missing_pinyin_never_becomes_exact_identity(self):
        authoritative = [
            Record("a", "1", "爱", pinyin="ài", pinyin_normalized="ài")
        ]
        verification = [Record("v", "1", "爱")]
        report = compare_records(authoritative, verification)
        self.assertFalse(report.present_in_both)
        self.assertEqual(len(report.headword_only_candidates), 1)
        self.assertEqual(len(report.authoritative_only), 1)
        self.assertEqual(len(report.verification_only), 1)

    def test_json_and_markdown_disclose_noncanonical_policy(self):
        json_text = json_report(self.report)
        markdown_text = markdown_report(self.report)
        self.assertIn('"verification_can_override_authoritative": false', json_text)
        self.assertIn("never overwrites", markdown_text)
        self.assertIn("## Pinyin disagreements", markdown_text)

    def test_report_is_deterministic(self):
        self.assertEqual(json_report(self.report), json_report(self.report))
        self.assertEqual(markdown_report(self.report), markdown_report(self.report))


if __name__ == "__main__":
    unittest.main()
