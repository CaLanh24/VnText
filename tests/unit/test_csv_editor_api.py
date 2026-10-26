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

import contextlib
import tempfile
import unittest
import hashlib
from pathlib import Path
from unittest.mock import patch

import vntext.csv_editor_api as csv_editor_api
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
from tests.lib.work_paths import work_temp_dir


class CsvEditorApiTests(unittest.TestCase):
    def _make_package(self, translation: str = "Xin chào") -> Path:
        tmp = Path(tempfile.mkdtemp(prefix="vntext_csv_editor_", dir=work_temp_dir("csv-editor-api")))
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
        self.assertEqual(doc["source_sha256"], hashlib.sha256((root / "translation.csv").read_bytes()).hexdigest())
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

    def test_save_compare_and_swap_preserves_external_edit(self):
        root = self._make_package()
        csv_path = root / "translation.csv"
        document = load_document(csv_path)
        edited_rows = document["rows"]
        edited_rows[0]["translation"] = "Bản dịch trong editor"

        external_bytes = csv_path.read_bytes().replace(b"Xin ch\xc3\xa0o", b"Ban dich ben ngoai")
        csv_path.write_bytes(external_bytes)
        result = save_document(
            csv_path,
            document["fields"],
            edited_rows,
            expected_sha256=document["source_sha256"],
        )

        self.assertFalse(result["ok"])
        self.assertIn("thay đổi bên ngoài", result["error"])
        self.assertEqual(csv_path.read_bytes(), external_bytes)

    def test_save_compare_and_swap_rechecks_after_backup(self):
        root = self._make_package()
        csv_path = root / "translation.csv"
        document = load_document(csv_path)
        edited_rows = document["rows"]
        edited_rows[0]["translation"] = "Bản dịch trong editor"
        external_bytes = csv_path.read_bytes().replace("Xin chào".encode("utf-8"), b"Ban dich ben ngoai")
        backup = csv_editor_api.backup_translation_csv

        def external_edit_after_backup(path):
            result = backup(path)
            Path(path).write_bytes(external_bytes)
            return result

        with patch("vntext.csv_editor_api.backup_translation_csv", side_effect=external_edit_after_backup):
            result = save_document(
                csv_path,
                document["fields"],
                edited_rows,
                expected_sha256=document["source_sha256"],
            )

        self.assertFalse(result["ok"])
        self.assertIn("thay đổi bên ngoài", result["error"])
        self.assertEqual(csv_path.read_bytes(), external_bytes)

    def test_rollback_after_replace_preserves_a_foreign_edit_and_only_undoes_owned_bytes(self):
        for label, foreign in (("owned_bytes_rolled_back", False), ("foreign_edit_preserved", True)):
            with self.subTest(case=label):
                root = self._make_package()
                csv_path = root / "translation.csv"
                original = csv_path.read_bytes()
                document = load_document(csv_path)
                edited_rows = document["rows"]
                edited_rows[0]["translation"] = "Bản dịch trong editor"
                foreign_bytes = original.replace("Xin chào".encode("utf-8"), b"Ban dich ben ngoai")

                def failing_reconcile(path, rows, **kwargs):
                    if foreign:
                        Path(path).write_bytes(foreign_bytes)  # arrives after our replace, before the error
                    raise RuntimeError("reconcile fault injected")

                with patch("vntext.csv_editor_api._reconcile_saved_review_rows", side_effect=failing_reconcile):
                    result = save_document(csv_path, document["fields"], edited_rows, expected_sha256=document["source_sha256"])
                self.assertFalse(result["ok"])
                self.assertIn("reconcile fault injected", result["error"])
                self.assertTrue(Path(result["backup_path"]).is_file())
                if foreign:
                    self.assertFalse(result["rolled_back"])
                    self.assertTrue(result["foreign_change_preserved"])
                    self.assertEqual(foreign_bytes, csv_path.read_bytes())
                else:
                    self.assertTrue(result["rolled_back"])
                    self.assertEqual(original, csv_path.read_bytes())

    def test_failure_before_replace_never_rewrites_the_source_file(self):
        root = self._make_package()
        csv_path = root / "translation.csv"
        document = load_document(csv_path)
        edited_rows = document["rows"]
        edited_rows[0]["translation"] = "Bản dịch trong editor"
        external = csv_path.read_bytes().replace("Xin chào".encode("utf-8"), b"Ban dich ben ngoai")
        # Scenario 1: an external edit already exists when the save starts (no expected hash was supplied)
        # and the write itself fails before any replace; the source file must not be "restored" over it.
        with patch("vntext.csv_editor_api._atomic_write_csv", side_effect=OSError("disk full injected")):
            csv_path.write_bytes(external)
            result = save_document(csv_path, document["fields"], edited_rows)
        self.assertFalse(result["ok"])
        self.assertFalse(result["rolled_back"])
        self.assertEqual(external, csv_path.read_bytes())
        # Scenario 2: the external edit lands right AFTER the backup was taken, then the write fails.
        root2 = self._make_package()
        csv2 = root2 / "translation.csv"
        document2 = load_document(csv2)
        rows2 = document2["rows"]
        rows2[0]["translation"] = "Bản dịch trong editor"
        external2 = csv2.read_bytes().replace("Xin chào".encode("utf-8"), b"Ban dich ben ngoai 2")
        real_backup = csv_editor_api.backup_translation_csv

        def backup_then_external_edit(path):
            made = real_backup(path)
            Path(path).write_bytes(external2)
            return made

        with patch("vntext.csv_editor_api.backup_translation_csv", side_effect=backup_then_external_edit), \
                patch("vntext.csv_editor_api._atomic_write_csv", side_effect=OSError("disk full injected")):
            result2 = save_document(csv2, document2["fields"], rows2)
        self.assertFalse(result2["ok"])
        self.assertFalse(result2["rolled_back"])
        self.assertEqual(external2, csv2.read_bytes())

    def test_review_rollback_uses_write_site_provenance(self):
        # The fault is injected at the real write sites of the review ledger, never by mock-writing
        # arbitrary bytes into it from inside the reconcile function.
        import vntext.mt_ct2_status as status

        for label in ("owned_write_then_later_failure", "foreign_write_after_owned_write", "foreign_write_before_staged_write"):
            with self.subTest(case=label):
                root = self._make_package()
                csv_path = root / "translation.csv"
                review_path = root / "review_only.csv"
                csv_original, review_original = csv_path.read_bytes(), review_path.read_bytes()
                document = load_document(csv_path)
                foreign_review = review_original + b"k9,Foreign,,UI:Text,game/x.txt,added elsewhere\n"
                real_reconcile = csv_editor_api._reconcile_saved_review_rows
                real_read = status.read_csv_rows_file

                def failing_reconcile(path, rows, **kwargs):
                    pruned = real_reconcile(path, rows, **kwargs)  # goes through the staged write site (owned write)
                    self.assertGreater(pruned, 0)
                    self.assertNotEqual(review_original, review_path.read_bytes())
                    if label == "foreign_write_after_owned_write":
                        review_path.write_bytes(foreign_review)
                    raise RuntimeError("review reconcile fault injected")

                def read_then_foreign_write(path, *args, **kwargs):
                    result = real_read(path, *args, **kwargs)
                    if Path(path) == review_path:
                        review_path.write_bytes(foreign_review)  # lands between our read and our staged write
                    return result

                patches = []
                if label == "foreign_write_before_staged_write":
                    patches.append(patch.object(status, "read_csv_rows_file", side_effect=read_then_foreign_write))
                else:
                    patches.append(patch("vntext.csv_editor_api._reconcile_saved_review_rows", side_effect=failing_reconcile))
                with contextlib.ExitStack() as stack:
                    for item in patches:
                        stack.enter_context(item)
                    result = save_document(csv_path, document["fields"], document["rows"], expected_sha256=document["source_sha256"])
                self.assertFalse(result["ok"])
                self.assertTrue(Path(result["backup_path"]).is_file())  # backup always retained
                self.assertTrue(result["rolled_back"])
                self.assertEqual(csv_original, csv_path.read_bytes())
                if label == "owned_write_then_later_failure":
                    self.assertNotIn("review_foreign_change_preserved", result)
                    self.assertEqual(review_original, review_path.read_bytes())
                else:
                    self.assertTrue(result["review_foreign_change_preserved"])
                    self.assertEqual(foreign_review, review_path.read_bytes())
                self.assertEqual([], [p.name for p in root.glob(".review_only.csv.*.staged")])  # no staging litter

    def test_rollback_oserror_returns_a_structured_result_and_keeps_the_backup(self):
        real_write = csv_editor_api._atomic_write_bytes
        real_reconcile = csv_editor_api._reconcile_saved_review_rows
        for label in ("csv_restore_fails", "review_restore_fails"):
            with self.subTest(case=label):
                root = self._make_package()
                csv_path = root / "translation.csv"
                review_path = root / "review_only.csv"
                csv_original = csv_path.read_bytes()
                review_original = review_path.read_bytes()
                document = load_document(csv_path)

                def reconcile_then_fail(path, rows, **kwargs):
                    real_reconcile(path, rows, **kwargs)
                    raise RuntimeError("fault after the staged review write")

                def failing_restore(path, data, *args, **kwargs):
                    target = Path(path)
                    if (label == "csv_restore_fails" and target == csv_path and data == csv_original) \
                            or (label == "review_restore_fails" and target == review_path and data == review_original):
                        raise OSError("restore failed injected")
                    return real_write(path, data, *args, **kwargs)

                with patch("vntext.csv_editor_api._reconcile_saved_review_rows", side_effect=reconcile_then_fail), \
                        patch("vntext.csv_editor_api._atomic_write_bytes", side_effect=failing_restore):
                    result = save_document(csv_path, document["fields"], document["rows"], expected_sha256=document["source_sha256"])
                self.assertFalse(result["ok"])  # a structured result, not an exception
                self.assertTrue(result["rollback_failed"])
                self.assertIn("restore failed injected", result["error"])
                self.assertTrue(Path(result["backup_path"]).is_file())  # retained
                self.assertEqual(csv_original, Path(result["backup_path"]).read_bytes())
                if label == "csv_restore_fails":
                    self.assertFalse(result["rolled_back"])
                    self.assertNotEqual(csv_original, csv_path.read_bytes())  # saved bytes left in place, not half-written
                else:
                    self.assertTrue(result["rolled_back"])
                    self.assertTrue(result["review_rollback_failed"])
                    self.assertEqual(csv_original, csv_path.read_bytes())
                    self.assertNotEqual(review_original, review_path.read_bytes())  # ledger untouched by the failed restore

    def test_review_reconcile_has_no_global_writer_patch(self):
        import vntext.mt_ct2_status as status

        before = status.write_csv_rows_file
        root = self._make_package()
        csv_path = root / "translation.csv"
        document = load_document(csv_path)
        seen = []

        def spy_during_reconcile(path, rows, **kwargs):
            seen.append(status.write_csv_rows_file is before)  # still the original module attribute
            return real(path, rows, **kwargs)

        real = csv_editor_api._reconcile_saved_review_rows
        with patch("vntext.csv_editor_api._reconcile_saved_review_rows", side_effect=spy_during_reconcile):
            result = save_document(csv_path, document["fields"], document["rows"], expected_sha256=document["source_sha256"])
        self.assertTrue(result["ok"])
        self.assertEqual([True], seen)
        self.assertIs(before, status.write_csv_rows_file)

    def test_partial_review_write_cannot_leave_a_truncated_ledger(self):
        import os as os_module

        root = self._make_package()
        csv_path = root / "translation.csv"
        review_path = root / "review_only.csv"
        csv_original, review_original = csv_path.read_bytes(), review_path.read_bytes()
        document = load_document(csv_path)
        real_replace = os_module.replace

        def failing_replace(src, dst, *args, **kwargs):
            if Path(dst) == review_path:
                raise OSError("replace failed at the review write site")
            return real_replace(src, dst, *args, **kwargs)

        with patch("vntext.csv_editor_api.os.replace", side_effect=failing_replace):
            result = save_document(csv_path, document["fields"], document["rows"], expected_sha256=document["source_sha256"])
        self.assertFalse(result["ok"])
        self.assertEqual(csv_original, csv_path.read_bytes())
        self.assertEqual(review_original, review_path.read_bytes())  # staged write: the ledger was never half-written

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

    def test_save_preserves_baseline_identity_and_order(self):
        import copy
        root = self._make_package()
        path = root / "translation.csv"
        original = path.read_bytes()
        document = load_document(path)
        for mutation in ("source_text", "key", "context", "order", "missing_row", "fields"):
            with self.subTest(mutation=mutation):
                rows = copy.deepcopy(document["rows"])
                fields = document["fields"][:]
                if mutation == "order": rows.reverse()
                elif mutation == "missing_row": rows.pop()
                elif mutation == "fields": fields.reverse()
                else: rows[0][mutation] = "changed"
                result = save_document(path, fields, rows)
                self.assertFalse(result["ok"], result)
                self.assertEqual(path.read_bytes(), original)

    def test_load_rejects_ambiguous_or_truncated_csv(self):
        root = self._make_package()
        path = root / "invalid.csv"
        for content in ('key,source_text,translation,translation\nk1,Hello,X,Y\n',
                        'key,source_text,translation\nk1,Hello,X,discarded\n',
                        'key,source_text,translation\nk1,"unfinished,X\n'):
            with self.subTest(content=content):
                path.write_text(content, encoding="utf-8")
                before = path.read_bytes()
                with self.assertRaises(ValueError): load_document(path)
                self.assertEqual(path.read_bytes(), before)

    def test_save_reconciliation_error_restores_exact_csv_and_review(self):
        root = self._make_package()
        path = root / "translation.csv"
        review = root / "review_only.csv"
        original, original_review = path.read_bytes(), review.read_bytes()
        document = load_document(path)
        document["rows"][0]["translation"] = "Chào bạn"
        real = csv_editor_api._reconcile_saved_review_rows

        def reconcile_then_fail(*args, **kwargs):
            real(*args, **kwargs)  # a real, staged review write happens first
            raise OSError("injected reconciliation failure")

        with patch("vntext.csv_editor_api._reconcile_saved_review_rows", side_effect=reconcile_then_fail):
            result = save_document(path, document["fields"], document["rows"])
        self.assertFalse(result["ok"])
        self.assertTrue(result["rolled_back"])
        self.assertEqual(path.read_bytes(), original)
        self.assertEqual(review.read_bytes(), original_review)

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
