"""Regression tests for complete CT2 blocker evidence."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


def _tests_lib_on_path() -> None:
    cur = Path(__file__).resolve().parent
    while cur.name != "tests" and cur.parent != cur:
        cur = cur.parent
    lib = cur / "lib"
    if str(lib) not in sys.path:
        sys.path.insert(0, str(lib))


_tests_lib_on_path()
from bootstrap import bootstrap

TESTS, ROOT, LIB = bootstrap(__file__)

from vntext.mt_ct2_pipeline import (
    _blocker_groups,
    _blocker_record,
    _write_blocker_inventory,
)


class MtBlockerInventoryTests(unittest.TestCase):
    def test_groups_cover_quality_and_structure_signals(self):
        row = {
            "key": "k",
            "source_text": "How many guys {mName} <color=yellow>soon</color>?",
            "context": "TextAsset:Tips:line:1",
            "file_path": "Sample_Data/data.unity3d",
            "import_method": "unity_textasset_line",
        }
        groups = _blocker_groups(
            row,
            "mask_roundtrip",
            [
                "quality: content loss",
                "quality: english-token: soon",
                "placeholder mismatch",
            ],
            attempts=[
                {
                    "strategy": "literal_newlines_first",
                    "validation_reasons": ["sentinel leftover"],
                }
            ],
        )
        self.assertIn("residual_english", groups)
        self.assertIn("content_loss", groups)
        self.assertIn("structural_tag_placeholder_randpick", groups)
        self.assertIn("preprocessing_retry", groups)
        self.assertIn("retry_exhausted", groups)

    def test_inventory_persists_full_row_and_attempt_evidence(self):
        row = {
            "key": "k",
            "source_text": "Please keep {mName} here.",
            "context": "NaninovelScript:1:print",
            "file_path": "script.txt",
            "import_method": "naninovel_script",
        }
        record = _blocker_record(
            row,
            strategy="full_sentence",
            raw_output="Please keep {mName} here.",
            reasons=["quality: identity for player-visible row"],
            attempts=[
                {
                    "strategy": "batch_default",
                    "raw_output": "Please keep {mName} here.",
                    "candidate": "",
                    "validation_reasons": ["quality: identity for player-visible row"],
                    "passed": False,
                }
            ],
            full_raw="Please keep {mName} here.",
        )
        with tempfile.TemporaryDirectory() as tmp:
            package = Path(tmp)
            _write_blocker_inventory(package, [record])
            payload = json.loads(
                (package / ".mt" / "blocker_inventory.json").read_text(encoding="utf-8")
            )
        self.assertEqual(payload["blocked_rows"], 1)
        self.assertFalse(payload["complete"])
        saved = payload["rows"][0]
        self.assertEqual(saved["source"], row["source_text"])
        self.assertEqual(saved["context"], row["context"])
        self.assertEqual(saved["initial"]["raw_output"], row["source_text"])
        self.assertEqual(saved["attempts"][0]["strategy"], "batch_default")
        self.assertIn("identity", saved["groups"])


if __name__ == "__main__":
    unittest.main()
