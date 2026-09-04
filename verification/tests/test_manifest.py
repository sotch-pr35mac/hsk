import json
import pathlib
import sys
import tempfile
import unittest

VERIFICATION = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(VERIFICATION))

from hsk_verify.manifest import (
    check_source_artifacts,
    load_manifest,
    source_by_id,
    validate_manifest,
)


class ManifestTests(unittest.TestCase):
    def test_checked_in_manifest_is_valid_and_has_all_three_datasets(self):
        manifest = load_manifest(VERIFICATION / "sources.json")
        self.assertEqual(len(manifest["sources"]), 6)
        self.assertEqual(
            {source["dataset"] for source in manifest["sources"]},
            {
                "hsk_2015_exam",
                "proficiency_standard_2021",
                "hsk_exam_syllabus_2025",
            },
        )
        for source in manifest["sources"]:
            self.assertIn("limitations", source["derivation"])
            self.assertIn("redistribution", source["license"])

    def test_duplicate_source_ids_are_rejected(self):
        manifest = load_manifest(VERIFICATION / "sources.json")
        manifest["sources"].append(dict(manifest["sources"][0]))
        with self.assertRaises(ValueError):
            validate_manifest(manifest)

    def test_local_artifact_hash_check(self):
        manifest = load_manifest(VERIFICATION / "sources.json")
        source = source_by_id(manifest, "shawkynasr-gf0025-2021")
        source = json.loads(json.dumps(source))
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            artifact = root / "词汇.csv"
            artifact.write_text("fixture", encoding="utf-8")
            source["artifacts"][0]["sha256"] = (
                "f16d05ec6b29248d2c61adb1e9263f78e4f7bace1b955014a2d17872cfe4064d"
            )
            self.assertEqual(check_source_artifacts(source, root), [])
            artifact.write_text("changed", encoding="utf-8")
            self.assertIn("SHA-256 mismatch", check_source_artifacts(source, root)[0])


if __name__ == "__main__":
    unittest.main()
