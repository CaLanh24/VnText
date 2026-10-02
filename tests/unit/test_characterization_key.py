"""Characterization freeze: make_key / Entry.finalize output as of Phase 0."""

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


from vntext_studio import Entry, make_key


class MakeKeyCharacterizationTests(unittest.TestCase):
    def test_generic_fixture_keys_are_stable(self):
        cases = [
            (
                "SampleGame_Data/sharedassets0.assets",
                "m_text",
                "Start",
                "unity_ui_text",
                "ad817f476e2cc21d",
            ),
            (
                "SampleGame_Data/data.unity3d",
                "NaninovelLenString@0x10",
                "Are you okay?",
                "naninovel_script_string",
                "ade9226700c8dc0b",
            ),
            (
                "foo.txt",
                "line:1",
                "Xin chao the gioi",
                "plain_text_line",
                "9508b6f9c86556fc",
            ),
            (
                "bar.assets",
                "TextAsset:Lang:line:2",
                "Continue",
                "unity_textasset_line",
                "e3a67b581224bba5",
            ),
        ]
        for file_path, context, text, method, expected in cases:
            with self.subTest(method=method, text=text):
                self.assertEqual(make_key(file_path, context, text, method), expected)

    def test_finalize_assigns_make_key_when_empty(self):
        entry = Entry(
            source_text="Hello",
            file_path="a.assets",
            context="m_text",
            import_method="unity_ui_text",
        ).finalize()
        self.assertEqual(entry.key, "c6ae78a92430f318")
        self.assertEqual(
            entry.key,
            make_key(entry.file_path, entry.context, entry.source_text, entry.import_method),
        )

    def test_finalize_preserves_existing_key(self):
        entry = Entry(
            source_text="Hello",
            file_path="a.assets",
            context="m_text",
            import_method="unity_ui_text",
            key="preset-key-xxxx",
        ).finalize()
        self.assertEqual(entry.key, "preset-key-xxxx")

    def test_same_text_different_context_different_key(self):
        a = make_key("f.assets", "m_text", "Start", "unity_ui_text")
        b = make_key("f.assets", "title", "Start", "unity_ui_text")
        self.assertNotEqual(a, b)


if __name__ == "__main__":
    unittest.main()
