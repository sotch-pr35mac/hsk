import pathlib
import sys
import unittest

VERIFICATION = pathlib.Path(__file__).resolve().parents[1]
FIXTURES = pathlib.Path(__file__).resolve().parent / "fixtures"
sys.path.insert(0, str(VERIFICATION))

from hsk_verify.adapters import load_records


class AdapterTests(unittest.TestCase):
    def test_shawkynasr_layout(self):
        result = load_records("shawkynasr-2021-csv", FIXTURES / "shawkynasr.csv")
        self.assertEqual(len(result.records), 5)
        self.assertEqual(result.records[0].level, "2")
        self.assertEqual(result.records[0].pinyin_normalized, "ài")
        self.assertFalse(result.issues)

    def test_shawkynasr_source_boundaries_and_optional_forms(self):
        from hsk_verify.adapters import _shawkynasr_pinyin

        self.assertEqual(_shawkynasr_pinyin("chū∥·lái"), "chūlái")
        self.assertEqual(
            _shawkynasr_pinyin("chà(yì)diǎnr"), "chàdiǎnr/chàyìdiǎnr"
        )

    def test_punpuf_excludes_dictionary_enrichment_from_identity(self):
        result = load_records("punpuf-2025-tsv", FIXTURES / "punpuf.tsv")
        self.assertEqual([record.simplified for record in result.records], ["点", "点"])
        self.assertTrue(all(record.traditional is None for record in result.records))
        self.assertTrue(all("definition" not in record.public_dict() for record in result.records))
        self.assertEqual(result.records[0].pinyin_normalized, "diǎn")

    def test_profesorm_expands_parenthesized_levels(self):
        result = load_records("profesorm-2025-csv", FIXTURES / "profesorm.csv")
        self.assertEqual([record.level for record in result.records], ["1", "3", "5", "6"])

    def test_krmanik_rows_have_no_pinyin(self):
        result = load_records(
            "krmanik-headword-directory", FIXTURES / "krmanik"
        )
        self.assertEqual(len(result.records), 3)
        self.assertEqual(result.records[1].simplified, "点")
        self.assertTrue(all(record.pinyin_normalized is None for record in result.records))


if __name__ == "__main__":
    unittest.main()
