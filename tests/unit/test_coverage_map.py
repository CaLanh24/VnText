"""Generic extract-family map regression."""

from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MAP = ROOT / "tests" / "golden" / "coverage" / "family_map.json"


class CoverageMapTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.family_map = json.loads(MAP.read_text(encoding="utf-8"))

    def test_map_is_explicitly_synthetic_and_has_no_corpus_counts(self):
        self.assertEqual(self.family_map.get("snapshot"), "synthetic-generic")
        self.assertEqual(self.family_map.get("fixture_policy"), "no bundled game or translation corpus")
        self.assertNotIn("key_count", self.family_map)

    def test_each_family_has_unique_method_and_coverage(self):
        families = self.family_map.get("families") or []
        self.assertGreaterEqual(len(families), 4)
        methods = []
        for family in families:
            with self.subTest(family=family):
                self.assertTrue(family.get("id"))
                self.assertTrue(family.get("import_method"))
                self.assertTrue(family.get("coverage"))
                methods.append(family["import_method"])
        self.assertEqual(len(methods), len(set(methods)))

    def test_raw_methods_are_explicitly_separate_from_main_families(self):
        raw = set(self.family_map.get("raw_extract_only_methods") or [])
        main = {family["import_method"] for family in self.family_map["families"]}
        self.assertTrue(raw)
        self.assertTrue(raw.isdisjoint(main))


if __name__ == "__main__":
    unittest.main()
