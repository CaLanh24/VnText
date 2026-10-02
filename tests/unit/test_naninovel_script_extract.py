"""Naninovel Script objects must enter translation.csv and patch without TypeTree."""

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
from types import SimpleNamespace
from unittest.mock import patch

from vntext.entry import Entry
from vntext.extract import (
    drop_raw_covered_by_script,
    has_vietnamese_chars,
    iter_naninovel_script_entries,
    find_aligned_unity_strings,
    find_aligned_unity_strings_containing,
    naninovel_script_display_candidate,
    patchable_blob_text,
    raw_text_quality,
    strict_complete_dialogue_text,
    ui_raw_text_quality,
)
from vntext.patch import patch_naninovel_script_object

AGE_GATE = "Are you ready to continue?"
AGE_GATE_MARKER = "Sẵn sàng tiếp tục?"
STAGE_DIRECTION_LINE = "*giggle* Oh, that's what you meant. Do you have someone in mind?"


class NaninovelScriptScannerTests(unittest.TestCase):
    def test_aligned_fallback_accepts_trimmed_source_with_leading_space(self):
        import struct

        payload = b"  return"
        padding = b"\x00" * ((4 - len(payload) % 4) % 4)
        raw = struct.pack("<i", len(payload)) + payload + padding
        hits = find_aligned_unity_strings(raw, "return")
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0]["text"], "  return")

    def test_containing_fallback_finds_randpick_payload(self):
        import struct

        payload = b'tempA=RandPick2("return@continue")'
        padding = b"\x00" * ((4 - len(payload) % 4) % 4)
        raw = struct.pack("<i", len(payload)) + payload + padding
        hits = find_aligned_unity_strings_containing(raw, "return")
        self.assertEqual(len(hits), 1)
        self.assertIn("RandPick2", hits[0]["text"])

    def test_vietnamese_text_is_not_rejected_by_english_shape_gates(self):
        for text in ("Ừ", "Mẹ", "*cười* Ồ, ý em là vậy à. Em đã nhắm ai chưa?"):
            self.assertTrue(has_vietnamese_chars(text), text)
            self.assertTrue(raw_text_quality(text, for_main=True), text)
            self.assertTrue(strict_complete_dialogue_text(text), text)
            self.assertTrue(patchable_blob_text(text), text)
            self.assertTrue(ui_raw_text_quality(text), text)
        self.assertFalse(has_vietnamese_chars("Hello"))
        self.assertFalse(patchable_blob_text("foo=Đã"))

    def test_stage_direction_prefix_keeps_complete_dialogue_but_not_bare_emote(self):
        self.assertTrue(patchable_blob_text(STAGE_DIRECTION_LINE))
        self.assertFalse(patchable_blob_text("*giggle*"))

    def test_script_object_keeps_short_stage_direction_and_rejects_identifiers(self):
        self.assertTrue(naninovel_script_display_candidate("*Slight noise*"))
        self.assertTrue(naninovel_script_display_candidate("Tiếng động nhỏ"))
        self.assertTrue(naninovel_script_display_candidate("Continue"))
        self.assertFalse(naninovel_script_display_candidate("Naninovel"))
        self.assertFalse(naninovel_script_display_candidate("Opening"))
        self.assertFalse(naninovel_script_display_candidate("AB_Park"))
        self.assertFalse(naninovel_script_display_candidate("Elringus.Naninovel.Runtime"))

    def test_drop_raw_when_script_row_exists(self):
        script = Entry(
            source_text=AGE_GATE,
            file_path=r"SampleGame_Data\data.unity3d",
            context="NaninovelScript:1",
            import_method="naninovel_script_string",
        ).finalize()
        raw = Entry(
            source_text=AGE_GATE,
            file_path=r"SampleGame_Data/data.unity3d",
            context="UnityUIRepairedRaw",
            import_method="raw_fixed_slot",
            review_only=True,
        ).finalize()
        other = Entry(
            source_text="Hello",
            file_path=r"SampleGame_Data\data.unity3d",
            context="raw",
            import_method="naninovel_blob_string",
            review_only=True,
        ).finalize()
        out = drop_raw_covered_by_script([script, raw, other])
        methods = [e.import_method for e in out]
        self.assertIn("naninovel_script_string", methods)
        self.assertIn("naninovel_blob_string", methods)
        self.assertNotIn("raw_fixed_slot", methods)


class NaninovelScriptPatchRoundtripTests(unittest.TestCase):
    def test_randpick_payload_applies_all_selected_replacements(self):
        import struct

        from vntext.patch_naninovel import patch_naninovel_script_object

        payload = b'temp=RandPick2("first phrase@first phrase extended@second phrase@third phrase")'
        raw = struct.pack("<i", len(payload)) + payload
        raw += b"\x00" * ((4 - len(payload) % 4) % 4)
        unrelated = b"first phrase outside a RandPick payload"
        raw += struct.pack("<i", len(unrelated)) + unrelated
        raw += b"\x00" * ((4 - len(unrelated) % 4) % 4)

        class FakeObject:
            type = SimpleNamespace(name="MonoBehaviour")

            def __init__(self):
                self.data = raw

            def set_raw_data(self, value):
                self.data = value

            def get_raw_data(self):
                return self.data

        obj = FakeObject()
        replacements = {
            "first phrase": "câu thứ nhất",
            "first phrase extended": "câu mở rộng",
            "second phrase": "câu thứ hai",
            "third phrase": "câu thứ ba",
        }
        with patch("vntext.patch_naninovel._mono_class_name", return_value="Script"):
            changed = patch_naninovel_script_object(obj, replacements)

        self.assertEqual(changed, 1)
        self.assertIn("câu thứ nhất".encode(), obj.data)
        self.assertIn("câu mở rộng".encode(), obj.data)
        self.assertIn("câu thứ hai".encode(), obj.data)
        self.assertIn("câu thứ ba".encode(), obj.data)
        self.assertNotIn(b"first phrase@first phrase extended", obj.data)
        self.assertNotIn(b"second phrase@third phrase", obj.data)
        self.assertIn(unrelated, obj.data)

if __name__ == "__main__":
    unittest.main()
