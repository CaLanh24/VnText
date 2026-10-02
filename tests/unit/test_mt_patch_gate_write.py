"""Patch Gate phải chặn ghi bản dịch rác vào CSV."""

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

import csv
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from vntext.mt_classify import classify_row
from vntext.mt_ct2 import _apply_mapping_memory, run_ct2_translate_keys
from vntext.package_io import read_csv_rows_file


class PatchGateWriteTests(unittest.TestCase):
    def _row(self, key: str, src: str, trans: str = "", ctx: str = "UI:Text") -> dict:
        return {
            "key": key,
            "source_text": src,
            "translation": trans,
            "context": ctx,
            "file_path": "game/sample.txt",
            "import_method": "unity_textasset_line",
        }

    def test_apply_mapping_rejects_garbage_repetition(self):
        garbage = (
            "bán bán bán bán bán bán bán bán bán bán bán bán bán bán bán bán bán bán bán "
            "bán bán bán bán bán bán bán bán bán bán bán bán bán bán bán bán bán bán bán "
            "bán bán bán bán bán bán bán bán bán bán bán bán lao"
        )
        row = self._row("k1", "Block")
        by_key = {"k1": row}
        applied, blocked, review = _apply_mapping_memory(
            by_key, {"k1": garbage}, allow_overwrite=True, whitelist=set(),
        )
        self.assertEqual(0, applied)
        self.assertEqual(1, blocked)
        self.assertEqual("", row["translation"])
        self.assertTrue(review)

    def test_ct2_junk_flags_character_as_ky_tu_and_vui_vui(self):
        from vntext.patch_gate import is_ct2_junk_translation

        self.assertTrue(
            is_ct2_junk_translation(
                "Every character described is over 18 years old.",
                "Mỗi ký tự là hơn 18 năm ký tự",
            )
        )
        self.assertTrue(
            is_ct2_junk_translation(
                "Please select the daily routine play type",
                "Vui vui lòng chọn mỗi ngày",
            )
        )
        self.assertTrue(
            is_ct2_junk_translation(
                "Eh..? you pervert!",
                "Bạn có làm vui vui vô - hạnh không?",
            )
        )
        self.assertTrue(
            is_ct2_junk_translation(
                "In anger, the player began to scream.",
                "Mặc ít, đưa điện Mặc mặc ít, ít ít? Người chơi hét.",
            )
        )
        self.assertTrue(
            is_ct2_junk_translation(
                "Awww... you pervert!",
                "www. www.org@ kde. org",
            )
        )
        self.assertTrue(is_ct2_junk_translation("The player felt sad", "Name"))
        self.assertTrue(
            is_ct2_junk_translation(
                "<color=white>CafeManager</color>",
                "<color=white>teppi82@ gmail</color>",
            )
        )
        self.assertFalse(
            is_ct2_junk_translation("Awww...", "Awww...")
        )

    def test_apply_mapping_accepts_valid_ui_label(self):
        row = self._row("k1", "Block")
        by_key = {"k1": row}
        applied, blocked, _review = _apply_mapping_memory(
            by_key, {"k1": "Khối"}, allow_overwrite=True, whitelist=set(),
        )
        self.assertEqual(1, applied)
        self.assertEqual(0, blocked)
        self.assertEqual("Khối", row["translation"])

    def test_classify_ui_label_has_no_bundled_override(self):
        row = self._row("k1", "Block")
        action, reason = classify_row(row)
        self.assertEqual("translate", action)
        self.assertEqual("player-visible text", reason)

    def test_classify_short_ui_without_glossary_stays_a_candidate(self):
        row = self._row("k1", "Options")
        action, _reason = classify_row(row)
        self.assertEqual("translate", action)

    def test_classify_sound_effect_copy_literal(self):
        row = self._row("k1", "Ah...! Nnh...!♡", ctx="TextAsset:x:line:1")
        action, reason = classify_row(row)
        self.assertEqual("copy_literal", action)
        self.assertIn("onomatopoeia", reason)

    def test_apply_mapping_accepts_literal_copy(self):
        row = self._row("k1", "Ah...! Nnh...!♡", ctx="TextAsset:x:line:1")
        by_key = {"k1": row}
        applied, blocked, _ = _apply_mapping_memory(
            by_key, {"k1": "Ah...! Nnh...!♡"}, allow_overwrite=True, whitelist=set(),
        )
        self.assertEqual(1, applied)
        self.assertEqual(0, blocked)

    @patch("vntext.mt_ct2_model.get_translator")
    @patch("vntext.mt_ct2_io._batch_translate_chunk")
    def test_retranslate_rejects_ct2_garbage(self, mock_batch, mock_get):
        mock_get.return_value = MagicMock(config={"batch_size": 8})
        garbage = (
            "bán bán bán bán bán bán bán bán bán bán bán bán bán bán bán bán bán bán bán "
            "bán bán bán bán bán bán bán bán bán bán bán bán bán bán bán bán bán bán bán "
            "bán bán bán bán bán bán bán bán bán bán bán bán lao"
        )
        mock_batch.return_value = {"k1": garbage}

        tmp = Path(tempfile.mkdtemp(prefix="vntext_gate_"))
        csv_path = tmp / "translation.csv"
        csv_path.write_text(
            "key,source_text,translation,context,file_path,import_method\n"
            f"k1,Hello,{garbage},UI:Text,game/sample.txt,unity_textasset_line\n",
            encoding="utf-8",
        )
        result = run_ct2_translate_keys(csv_path, ["k1"], backup=False)
        self.assertFalse(result.get("ok"))
        self.assertEqual(0, result.get("applied"))
        _fields, rows = read_csv_rows_file(csv_path)
        self.assertEqual("", rows[0]["translation"])

    @patch("vntext.mt_ct2_model.get_translator")
    @patch("vntext.mt_ct2_io._batch_translate_chunk")
    def test_retranslate_writes_valid_translation(self, mock_batch, mock_get):
        mock_get.return_value = MagicMock(config={"batch_size": 8})
        mock_batch.return_value = {"k1": "Xin chào bạn"}

        tmp = Path(tempfile.mkdtemp(prefix="vntext_gate_ok_"))
        csv_path = tmp / "translation.csv"
        csv_path.write_text(
            "key,source_text,translation,context,file_path,import_method\n"
            "k1,Hello,,TextAsset:scene:line:1,game/sample.txt,unity_textasset_line\n",
            encoding="utf-8",
        )
        result = run_ct2_translate_keys(csv_path, ["k1"], backup=False)
        self.assertTrue(result.get("ok"))
        self.assertGreaterEqual(result.get("applied", 0), 1)
        _fields, rows = read_csv_rows_file(csv_path)
        self.assertTrue(str(rows[0]["translation"]).strip())

    @patch("vntext.mt_ct2_model.get_translator")
    def test_retranslate_uses_package_memory_before_ct2(self, mock_get):
        mock_get.return_value = MagicMock(config={"batch_size": 8})
        mock_get.return_value.translate_many.side_effect = AssertionError(
            "translation memory miss: CT2 should not be called"
        )

        tmp = Path(tempfile.mkdtemp(prefix="vntext_memory_retranslate_"))
        csv_path = tmp / "translation.csv"
        csv_path.write_text(
            "key,source_text,translation,context,file_path,import_method\n"
            "seed,Start game,Bắt đầu game,NaninovelScript:1,game/sample.txt,naninovel_script_string\n"
            "k1,Start game,,NaninovelScript:2,game/sample.txt,naninovel_script_string\n",
            encoding="utf-8",
        )
        result = run_ct2_translate_keys(csv_path, ["k1"], backup=False)
        self.assertTrue(result.get("ok"))
        self.assertEqual(1, result.get("applied"))
        mock_get.return_value.translate_many.assert_not_called()
        _fields, rows = read_csv_rows_file(csv_path)
        self.assertEqual("Bắt đầu game", rows[1]["translation"])


if __name__ == "__main__":
    unittest.main()
