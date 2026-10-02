"""Test phân loại pending và semantic audit."""

from __future__ import annotations

import sys
from pathlib import Path

def _tests_lib_on_path() -> None:
    cur = Path(__file__).resolve().parent
    while cur.name != "tests" and cur.parent != cur:
        cur = cur.parent
    lib = cur / "lib"
    p = str(lib)
    if p not in sys.path:
        sys.path.insert(0, p)

_tests_lib_on_path()
from bootstrap import bootstrap
TESTS, ROOT, LIB = bootstrap(__file__)

import unittest

from vntext.mt_classify import classify_row, is_sound_effect_line
from vntext.mt_pipeline_audit import measure_semantic_on_translated


class PipelineAuditTests(unittest.TestCase):
    def test_sound_effect_detector(self):
        self.assertTrue(is_sound_effect_line("Ah...! Nnh...!♡"))
        self.assertFalse(is_sound_effect_line("Hello world, how are you?"))

    def test_semantic_audit_reports_measured(self):
        rows = [
            {
                "key": "k1",
                "source_text": "Hello",
                "translation": "Xin chào",
                "context": "TextAsset:x:1",
                "file_path": "game/x",
                "import_method": "unity_textasset_line",
            }
        ]
        result = measure_semantic_on_translated(rows, __import__("pathlib").Path("."))
        self.assertTrue(result["measured"])
        self.assertEqual(1, result["rows_scanned"])
        self.assertIn("note", result)


if __name__ == "__main__":
    unittest.main()
