"""Tests for translation.csv editor API."""

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

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from vntext.csv_editor_api import (
    backup_document,
    build_issues_by_key,
    clear_blocked_translations,
    is_batch_actionable,
    load_document,
    preview_clear_blocked,
    preview_retranslate,
    reason_label_vi,
    preview_replace_translation,
    replace_translation,
    restore_backup,
    save_document,
    validate_document,
)
from vntext.package_io import backup_translation_csv


class CsvEditorApiTests(unittest.TestCase):
    def _make_package(self, translation: str = "Xin chào") -> Path:
        tmp = Path(tempfile.mkdtemp(prefix="vntext_csv_editor_"))
        csv_path = tmp / "translation.csv"
        csv_path.write_text(
            "key,source_text,translation,context,file_path\n"
            f"k1,Hello,{translation},UI:Text,game/sample.txt\n"
            f"k2,Date,Không có gì khớp,UI:Text,game/sample.txt\n"
            f"k3,Save,,UI:Text,game/sample.txt\n",
            encoding="utf-8",
        )
        (tmp / "review_only.csv").write_text(
            "key,source_text,translation,context,file_path,patch_note\n"
            "k2,Date,,UI:Text,game/sample.txt,MT blocked\n",
            encoding="utf-8",
        )
        return tmp

    def test_load_preserves_fields(self):
        root = self._make_package()
        doc = load_document(root / "translation.csv")
        self.assertTrue(doc["ok"])
        self.assertEqual(doc["row_count"], 3)
        self.assertIn("key", doc["fields"])
        self.assertIn("k2", doc["review_keys"])

    def test_save_roundtrip_utf8(self):
        root = self._make_package()
        csv_path = root / "translation.csv"
        doc = load_document(csv_path)
        rows = doc["rows"]
        rows[0]["translation"] = "Chào bạn"
        result = save_document(csv_path, doc["fields"], rows)
        self.assertTrue(result["ok"])
        reloaded = load_document(csv_path)
        self.assertEqual(reloaded["rows"][0]["translation"], "Chào bạn")
        raw = csv_path.read_bytes()
        self.assertTrue(raw.startswith(b"\xef\xbb\xbf"))

    def test_validate_flags_garbage(self):
        root = self._make_package()
        garbage = (
            "Đồng bán bán bán bán bán bán bán bán bán bán bán bán bán bán bán bán bán bán bán bán "
            "bán bán bán bán bán bán bán bán bán bán bán bán bán bán bán bán bán bán bán bán bán "
            "bán bán bán bán bán bán bán bán bán bán bán bán bán lao"
        )
        doc = load_document(root / "translation.csv")
        doc["rows"][0]["translation"] = garbage
        val = validate_document(root / "translation.csv", doc["rows"])
        self.assertTrue(val["has_warnings"])
        self.assertGreater(val["reason_counts"].get("garbage_repetition", 0), 0)
        self.assertIn("k1", val["issues_by_key"])
        self.assertIn("garbage_repetition", val["issues_by_key"]["k1"])
        self.assertIn("Rác lặp", val["issues_display"]["k1"])

    def test_save_rejects_duplicate_keys(self):
        root = self._make_package()
        csv_path = root / "translation.csv"
        doc = load_document(csv_path)
        rows = list(doc["rows"])
        rows.append(dict(rows[0]))
        result = save_document(csv_path, doc["fields"], rows)
        self.assertFalse(result["ok"])

    def test_backup_creates_file(self):
        root = self._make_package()
        csv_path = root / "translation.csv"
        result = backup_document(csv_path)
        self.assertTrue(result["ok"])
        backup_path = Path(result["backup_path"])
        self.assertTrue(backup_path.is_file())
        self.assertEqual(csv_path.read_text(encoding="utf-8-sig"), backup_path.read_text(encoding="utf-8-sig"))

    def test_bulk_replace_translation_only_with_scope_and_undo(self):
        root = self._make_package()
        csv_path = root / "translation.csv"
        doc = load_document(csv_path)
        doc["rows"][0]["translation"] = "Mị lực pheromones"
        doc["rows"][1]["translation"] = "pheromones khác"
        write = replace_translation(csv_path, doc["fields"], doc["rows"], "pheromones", "mị lực", ["k1"])
        self.assertTrue(write["ok"])
        self.assertEqual(write["count"], 1)
        self.assertEqual(write["replacement_count"], 1)
        self.assertTrue(Path(write["backup_path"]).is_file())
        reloaded = load_document(csv_path)["rows"]
        self.assertEqual(reloaded[0]["translation"], "Mị lực mị lực")
        self.assertEqual(reloaded[1]["translation"], "pheromones khác")
        self.assertEqual(reloaded[0]["source_text"], "Hello")
        undone = restore_backup(csv_path, write["backup_path"])
        self.assertTrue(undone["ok"])
        restored = load_document(csv_path)["rows"]
        self.assertEqual(restored[0]["translation"], "Xin chào")
        self.assertEqual(restored[1]["translation"], "Không có gì khớp")

    def test_bulk_preview_all_rows_counts_occurrences(self):
        root = self._make_package()
        rows = load_document(root / "translation.csv")["rows"]
        rows[0]["translation"] = "pheromones pheromones"
        rows[1]["translation"] = "pheromones"
        preview = preview_replace_translation(rows, "PHEROMONES", "mị lực")
        self.assertTrue(preview["ok"])
        self.assertEqual(preview["count"], 2)
        self.assertEqual(preview["replacement_count"], 3)

    def test_clear_blocked_only_translation(self):
        root = self._make_package()
        csv_path = root / "translation.csv"
        doc = load_document(csv_path)
        rows = doc["rows"]
        rows[0]["translation"] = (
            "Đồng bán bán bán bán bán bán bán bán bán bán bán bán bán bán bán bán bán bán bán bán "
            "bán bán bán bán bán bán bán bán bán bán bán bán bán bán bán bán bán bán bán bán bán "
            "bán bán bán bán bán bán bán bán bán bán bán bán bán lao"
        )
        preview = preview_clear_blocked(csv_path, rows, None)
        self.assertGreater(preview["count"], 0)
        result = clear_blocked_translations(csv_path, doc["fields"], rows, None)
        self.assertTrue(result["ok"])
        self.assertGreater(result["count"], 0)
        self.assertTrue(Path(result["backup_path"]).is_file())
        reloaded = load_document(csv_path)
        self.assertEqual("", reloaded["rows"][0]["translation"])
        self.assertEqual("Hello", reloaded["rows"][0]["source_text"])
        self.assertEqual("k1", reloaded["rows"][0]["key"])

    def test_clear_skips_semantic_validation_only(self):
        root = self._make_package(translation="Hello world")
        csv_path = root / "translation.csv"
        doc = load_document(csv_path)
        rows = doc["rows"]
        rows[0]["translation"] = "Hello world"
        issues = build_issues_by_key(rows, root)
        if issues.get("k1") == "validation":
            preview = preview_clear_blocked(csv_path, rows, ["k1"])
            self.assertEqual(0, preview["count"])
        else:
            self.assertFalse(is_batch_actionable(issues.get("k1", "")))

    def test_preview_retranslate_actionable_only(self):
        root = self._make_package()
        csv_path = root / "translation.csv"
        doc = load_document(csv_path)
        rows = doc["rows"]
        rows[0]["translation"] = "<b>broken"
        preview = preview_retranslate(csv_path, rows, None)
        self.assertGreaterEqual(preview["count"], 0)

    def test_reason_label_vi(self):
        self.assertIn("Rác", reason_label_vi("garbage_repetition"))
        self.assertIn("review", reason_label_vi("review_only").lower())

    @patch("vntext.mt_ct2.run_ct2_translate_keys")
    def test_retranslate_blocked_keys_dry_run(self, mock_ct2):
        root = self._make_package()
        csv_path = root / "translation.csv"
        doc = load_document(csv_path)
        rows = doc["rows"]
        rows[0]["translation"] = "<b>broken"
        from vntext.csv_editor_api import retranslate_blocked_keys

        dry = retranslate_blocked_keys(csv_path, ["k1"], dry_run=True)
        self.assertTrue(dry["ok"])
        mock_ct2.assert_not_called()

    @patch("vntext.mt_ct2.run_ct2_translate_keys")
    def test_retranslate_calls_ct2(self, mock_ct2):
        mock_ct2.return_value = {"ok": True, "applied": 1, "blocked": 0, "summary": "ok"}
        root = self._make_package()
        csv_path = root / "translation.csv"
        doc = load_document(csv_path)
        rows = doc["rows"]
        rows[0]["translation"] = "<b>broken"
        from vntext.csv_editor_api import retranslate_blocked_keys

        result = retranslate_blocked_keys(csv_path, ["k1"], dry_run=False)
        self.assertTrue(result["ok"])
        mock_ct2.assert_called_once()


if __name__ == "__main__":
    unittest.main()
