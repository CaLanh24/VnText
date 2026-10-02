# -*- coding: utf-8 -*-
"""Tests for intentional_keep ledger + naninovel technical rows."""

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

import json
import unittest

from vntext.intentional_keep import (
    apply_intentional_keep_batch,
    intentional_keep_reason,
    is_player_visible_row,
    load_intentional_keep_ledger,
)
from vntext.mt_classify import classify_row
from work_paths import work_temp_dir


FOUR_KEYS = [
    (
        "1a32f009a1de70c1",
        "Never edit the above lines; auto-save metadata depends on this block.",
        "NaninovelScript:fixture:1",
        "editor_autosave_note",
    ),
    (
        "2b43f119b2ef80d2",
        "{tempA}.Start",
        "NaninovelScript:fixture:2",
        "naninovel_label_ref",
    ),
    (
        "3c54a22ac3f091e3",
        "score*2<rand&&score<60",
        "NaninovelScript:fixture:3",
        "condition_expression",
    ),
    (
        "4d65b33bd401a2f4",
        "{sampleSprite}_After.SlideIn",
        "NaninovelScript:fixture:4",
        "naninovel_tween_id",
    ),
]


class IntentionalKeepTests(unittest.TestCase):
    def test_non_lexical_vocalisations_have_explicit_keep_reason(self):
        for source in ("Aha ha ha.",):
            row = {
                "source_text": source,
                "translation": source,
                "context": "NaninovelScript:fixture:5",
                "import_method": "naninovel_print",
            }
            self.assertEqual(intentional_keep_reason(row), "vocalization_sfx", source)

    def test_numbered_series_marker_keep_is_generic_and_case_insensitive(self):
        for source in ("DEMO Series 1", "demo series 1"):
            row = {
                "source_text": source,
                "translation": "",
                "context": "NaninovelScript:fixture:6",
                "import_method": "naninovel_print",
            }
            self.assertEqual(intentional_keep_reason(row), "scene_marker", source)

    def test_four_review_keys_are_technical_not_player_visible(self):
        for key, src, ctx, expected_reason in FOUR_KEYS:
            row = {
                "key": key,
                "source_text": src,
                "translation": "",
                "context": ctx,
                "import_method": "naninovel_script_string",
                "file_path": r"SampleGame_Data\data.unity3d",
            }
            self.assertEqual(classify_row(row)[0], "skip_technical", key)
            self.assertEqual(intentional_keep_reason(row), expected_reason, key)
            self.assertFalse(is_player_visible_row(row), key)

    def test_apply_intentional_keep_reconciles_review_only(self):
        staging = work_temp_dir("intentional_keep")
        fields = [
            "key",
            "source_text",
            "translation",
            "context",
            "file_path",
            "object_info",
            "import_method",
            "safety",
            "backend",
            "byte_limit",
            "patch_note",
        ]
        rows = [
            {
                "key": key,
                "source_text": src,
                "translation": "",
                "context": ctx,
                "file_path": r"Sample_Data\data.unity3d",
                "object_info": f"MonoBehaviour:{ctx.split(':')[1]}:Script",
                "import_method": "naninovel_script_string",
                "safety": "safe",
                "backend": "naninovel_script_object",
                "byte_limit": "",
                "patch_note": "",
            }
            for key, src, ctx, _ in FOUR_KEYS
        ]
        from vntext.package_io import read_csv_rows_file, write_csv_rows_file

        write_csv_rows_file(staging / "translation.csv", fields, rows)
        write_csv_rows_file(
            staging / "review_only.csv",
            fields,
            [
                {
                    **r,
                    "patch_note": "MT blocked: test",
                }
                for r in rows
            ],
        )
        (staging / "manifest.json").write_text('{"entries":[]}\n', encoding="utf-8")

        res = apply_intentional_keep_batch(staging)
        self.assertEqual(res["applied"], 4)
        self.assertEqual(res["pruned_review"], 4)

        _, after = read_csv_rows_file(staging / "translation.csv")
        by = {r["key"]: r for r in after}
        for key, src, _, _ in FOUR_KEYS:
            self.assertEqual(by[key]["translation"], src)

        ledger = load_intentional_keep_ledger(staging)
        self.assertEqual(len(ledger.get("keys") or {}), 4)
        self.assertFalse((staging / "review_only.csv").read_text(encoding="utf-8-sig").strip().splitlines()[1:])


if __name__ == "__main__":
    unittest.main()
