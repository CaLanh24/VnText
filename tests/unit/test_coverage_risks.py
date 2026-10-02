"""The generic extraction risk register stays explicit and reviewable."""

from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RISK_FILE = ROOT / "tests" / "golden" / "coverage" / "extract_miss_risks.json"


class CoverageRiskTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.risks = json.loads(RISK_FILE.read_text(encoding="utf-8"))

    def test_risk_register_is_non_empty(self):
        self.assertGreaterEqual(len(self.risks), 5)

    def test_each_risk_has_identity_and_evidence_rule(self):
        ids = []
        for item in self.risks:
            with self.subTest(id=item.get("id")):
                self.assertTrue(item.get("id"))
                self.assertTrue(item.get("group"))
                self.assertTrue(item.get("related_family"))
                self.assertTrue(str(item.get("how_to_know") or "").strip())
                ids.append(item["id"])
        self.assertEqual(len(ids), len(set(ids)))


if __name__ == "__main__":
    unittest.main()
