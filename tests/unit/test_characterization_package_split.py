"""Characterization freeze: which entries go to translation.csv vs side files."""

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


from vntext_studio import Entry, is_direct_asset_patchable, split_asset_patchable_entries


def _entry(letter: str, method: str, review_only: bool = False) -> Entry:
    return Entry(
        source_text=letter,
        file_path="f",
        context="c",
        import_method=method,
        review_only=review_only,
    )


class PackageSplitCharacterizationTests(unittest.TestCase):
    def test_is_direct_asset_patchable_matches_phase0(self):
        expected = {
            "A": True,   # unity_textasset_line
            "B": True,   # unity_textasset_table_cell
            "C": True,   # unity_textasset_script
            "D": True,   # unity_typetree_field
            "E": True,   # unity_ui_text
            "F": True,   # naninovel_script_string
            "G": True,   # plain_text_line
            "H": False,  # raw_fixed_slot
            "I": False,  # naninovel_blob_string
            "J": False,  # naninovel_raw_candidate
            "K": False,  # raw_review_only
            "L": False,  # unity_typetree_field + review_only
            "M": False,  # external_dump_reimport
        }
        fixtures = [
            _entry("A", "unity_textasset_line"),
            _entry("B", "unity_textasset_table_cell"),
            _entry("C", "unity_textasset_script"),
            _entry("D", "unity_typetree_field"),
            _entry("E", "unity_ui_text"),
            _entry("F", "naninovel_script_string"),
            _entry("G", "plain_text_line"),
            _entry("H", "raw_fixed_slot"),
            _entry("I", "naninovel_blob_string"),
            _entry("J", "naninovel_raw_candidate"),
            _entry("K", "raw_review_only"),
            _entry("L", "unity_typetree_field", review_only=True),
            _entry("M", "external_dump_reimport"),
        ]
        for entry in fixtures:
            with self.subTest(letter=entry.source_text, method=entry.import_method):
                self.assertEqual(is_direct_asset_patchable(entry), expected[entry.source_text])

    def test_split_asset_patchable_entries_matches_phase0(self):
        main = [
            _entry("A", "unity_textasset_line"),
            _entry("B", "unity_textasset_table_cell"),
            _entry("C", "unity_textasset_script"),
            _entry("D", "unity_typetree_field"),
            _entry("E", "unity_ui_text"),
            _entry("F", "naninovel_script_string"),
            _entry("G", "plain_text_line"),
            _entry("H", "raw_fixed_slot"),
            _entry("I", "naninovel_blob_string"),
            _entry("J", "naninovel_raw_candidate"),
            _entry("K", "raw_review_only"),
            _entry("M", "external_dump_reimport"),
        ]
        review = [_entry("L", "unity_typetree_field", review_only=True)]
        patchable, raw_unpatchable, review_out = split_asset_patchable_entries(main, review)

        self.assertEqual(
            [(e.source_text, e.import_method, e.review_only) for e in patchable],
            [
                ("A", "unity_textasset_line", False),
                ("B", "unity_textasset_table_cell", False),
                ("C", "unity_textasset_script", False),
                ("D", "unity_typetree_field", False),
                ("E", "unity_ui_text", False),
                ("F", "naninovel_script_string", False),
                ("G", "plain_text_line", False),
            ],
        )
        self.assertEqual(
            [(e.source_text, e.import_method, e.review_only) for e in raw_unpatchable],
            [
                ("H", "raw_fixed_slot", True),
                ("I", "naninovel_blob_string", True),
                ("J", "naninovel_raw_candidate", True),
                ("K", "raw_review_only", True),
            ],
        )
        self.assertEqual(
            [(e.source_text, e.import_method, e.review_only) for e in review_out],
            [
                ("M", "external_dump_reimport", True),
                ("L", "unity_typetree_field", True),
            ],
        )


if __name__ == "__main__":
    unittest.main()
