"""Managed-text key/value lines must keep the space after the colon."""

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
from pathlib import Path


from vntext.extract import key_value_line_prefix, parse_textasset_translatable_line


class TextAssetKeyValuePrefixTests(unittest.TestCase):
    def test_prefix_keeps_space_after_colon(self):
        parsed = parse_textasset_translatable_line("TitleMenu.NewGame: NEW GAME\n")
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed["text"], "NEW GAME")
        self.assertEqual(parsed["prefix"], "TitleMenu.NewGame: ")
        self.assertEqual(parsed["prefix"] + "Chơi mới", "TitleMenu.NewGame: Chơi mới")

    def test_helper_uses_original_separator(self):
        raw = "TitleMenu.Continue: CONTINUE"
        prefix = key_value_line_prefix(raw, "CONTINUE", "TitleMenu.Continue")
        self.assertEqual(prefix, "TitleMenu.Continue: ")
        self.assertTrue(prefix.endswith(" "))


if __name__ == "__main__":
    unittest.main()
