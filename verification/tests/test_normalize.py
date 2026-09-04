import pathlib
import sys
import unittest
import unicodedata

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from hsk_verify.normalize import normalize_headword, normalize_pinyin


class NormalizeTests(unittest.TestCase):
    def test_marked_and_numbered_are_equivalent(self):
        self.assertEqual(normalize_pinyin("nǐ hǎo"), normalize_pinyin("Ni3-Hao3"))

    def test_composed_and_decomposed_are_equivalent(self):
        decomposed = unicodedata.normalize("NFD", "lǜ")
        self.assertEqual(normalize_pinyin("lǜ"), normalize_pinyin(decomposed))

    def test_umlaut_conventions_are_equivalent(self):
        self.assertEqual(normalize_pinyin("lü4"), normalize_pinyin("lu:4"))
        self.assertEqual(normalize_pinyin("lü4"), normalize_pinyin("lv4"))

    def test_neutral_tone_conventions_are_equivalent(self):
        self.assertEqual(normalize_pinyin("ma"), normalize_pinyin("ma5"))
        self.assertEqual(normalize_pinyin("ma"), normalize_pinyin("ma0"))

    def test_syllabic_interjection_tone_number_is_equivalent(self):
        self.assertEqual(normalize_pinyin("ǹg"), normalize_pinyin("ng4"))

    def test_apostrophe_variants_are_equivalent(self):
        self.assertEqual(normalize_pinyin("xī’ān"), normalize_pinyin("xi1'an1"))
        self.assertEqual(normalize_pinyin("xī’ān"), normalize_pinyin("xi1an1"))

    def test_slash_readings_form_a_sorted_set(self):
        self.assertEqual(
            normalize_pinyin("shuí/shéi/shuí"), tuple(sorted({"shéi", "shuí"}))
        )

    def test_malformed_numbered_pinyin_is_rejected(self):
        with self.assertRaises(ValueError):
            normalize_pinyin("ni3hao")

    def test_headword_does_not_convert_script(self):
        self.assertEqual(normalize_headword(" 後 "), "後")
        self.assertNotEqual(normalize_headword("後"), normalize_headword("后"))


if __name__ == "__main__":
    unittest.main()
