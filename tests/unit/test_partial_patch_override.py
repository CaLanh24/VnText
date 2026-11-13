"""Owner-confirmed safe-subset Patch (partial extraction override): positive and negative integration tests on a generated plain-text game.

The override relaxes ONLY the extraction-status check; every per-row structural/hash/schema/path check and the row-level skip rules still apply."""
import json
import tempfile
import unittest
from pathlib import Path

from tests.lib.work_paths import work_temp_dir
from vntext.entry import Entry
from vntext.package_io import CSV_FIELDS, write_csv_rows_file
from vntext.patch_gate import (audit_patch_package, partial_override_eligible, partial_patch_override,
                               validate_patch_package_identity)


def _proof():
    return {key: True for key in ("reader", "writer", "preflight", "reopen", "semantic_verify")}


class PartialPatchOverrideTests(unittest.TestCase):
    PARTIAL_UNSCOPED = {"status": "PARTIAL", "complete": False, "main": 2, "review": 3, "errors": 1, "severity": "error", "limitations": []}

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=work_temp_dir("partial-patch-override"))
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.game = self.root / "generated-game"; self.game.mkdir()
        self.source = self.game / "dialogue.txt"
        self.source.write_text("Hello\nGoodbye\n", encoding="utf-8")
        entries = [Entry("Hello", "dialogue.txt", "line:1", import_method="plain_text_line", safety="safe", locator={"line": 1}, patch_proof=_proof()).finalize(),
                   Entry("Goodbye", "dialogue.txt", "line:2", import_method="plain_text_line", safety="safe", locator={"line": 2}, patch_proof=_proof()).finalize()]
        self.package = self.root / "package"; self.package.mkdir()
        self.csv = self.package / "translation.csv"; self.manifest = self.package / "manifest.json"
        self.rows = [{**entries[0].to_csv_row(), "translation": "Xin chào"}, {**entries[1].to_csv_row(), "translation": ""}]    # second row untranslated
        write_csv_rows_file(self.csv, CSV_FIELDS, self.rows)
        self.manifest.write_text(json.dumps({"entries": [entry.to_manifest() for entry in entries]}), encoding="utf-8")
        self.status = self.package / "extract_status.json"

    def patch(self, override):
        from vntext.app_tasks import run_patch_task
        completed = []
        run_patch_task(self.csv, self.manifest, str(self.game), str(self.package), progress=lambda _: None, log=lambda _: None,
                       complete=completed.append, patch_out_override=self.package / "Patch_Viet_Hoa", partial_override=override)
        self.assertEqual(1, len(completed))
        return completed[0]

    def test_blanket_block_without_override_and_actionable_message(self):
        self.status.write_text(json.dumps(self.PARTIAL_UNSCOPED), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "Extraction is incomplete; final Patch is blocked.*safe-subset"):
            validate_patch_package_identity(self.csv, json.loads(self.manifest.read_text(encoding="utf-8")))
        done = self.patch(False)
        self.assertFalse(done["ok"], done)
        self.assertFalse((self.package / "Patch_Viet_Hoa" / "COPY_TO_GAME_ROOT").exists())

    def test_override_patches_only_the_valid_subset_and_records_accurate_coverage(self):
        self.status.write_text(json.dumps(self.PARTIAL_UNSCOPED), encoding="utf-8")
        before = (self.source.read_bytes(), self.csv.read_bytes(), self.manifest.read_bytes(), self.status.read_bytes())
        done = self.patch(True)
        self.assertTrue(done["ok"], done)
        output = self.package / "Patch_Viet_Hoa"
        patched = (output / "COPY_TO_GAME_ROOT" / "dialogue.txt").read_text(encoding="utf-8").splitlines()
        self.assertEqual("Xin chào", patched[0])
        self.assertEqual("Goodbye", patched[1])                                   # the untranslated row keeps its original text (never invented)
        coverage = json.loads((output / "patch_coverage.json").read_text(encoding="utf-8"))
        self.assertEqual("USER_SAFE_SUBSET", coverage["scope"]); self.assertTrue(coverage["owner_override"])
        self.assertIn("NOT a full-game PASS", coverage["statement"])
        self.assertEqual("USER_PARTIAL_OVERRIDE", coverage["excluded_coverage"][0]["code"])
        self.assertIsInstance(coverage["included_rows"], int)
        self.assertEqual(before, (self.source.read_bytes(), self.csv.read_bytes(), self.manifest.read_bytes(), self.status.read_bytes()))   # nothing user-owned changes
        self.assertEqual("PARTIAL", json.loads(self.status.read_text(encoding="utf-8"))["status"])                                          # coverage is never promoted

    def test_override_never_bypasses_per_row_identity_or_other_statuses(self):
        self.status.write_text(json.dumps(self.PARTIAL_UNSCOPED), encoding="utf-8")
        manifest = json.loads(self.manifest.read_text(encoding="utf-8"))
        write_csv_rows_file(self.csv, CSV_FIELDS, [{**self.rows[0], "source_text": "Changed source"}, self.rows[1]])
        with partial_patch_override(True), self.assertRaisesRegex(ValueError, "source identity mismatch"):
            validate_patch_package_identity(self.csv, manifest)
        write_csv_rows_file(self.csv, CSV_FIELDS, self.rows)
        for status in ({"status": "FAILED", "complete": False}, {"status": "EMPTY", "complete": False}, {"status": "COMPLETE", "complete": False}, {"complete": False}):
            self.status.write_text(json.dumps(status), encoding="utf-8")
            self.assertFalse(partial_override_eligible(status), status)
            with partial_patch_override(True), self.assertRaisesRegex(ValueError, "Extraction is incomplete"):
                validate_patch_package_identity(self.csv, manifest)

    def test_override_does_not_leak_after_the_task_and_zero_safe_rows_is_not_a_fake_patch(self):
        self.status.write_text(json.dumps(self.PARTIAL_UNSCOPED), encoding="utf-8")
        manifest = json.loads(self.manifest.read_text(encoding="utf-8"))
        self.assertTrue(self.patch(True)["ok"])
        with self.assertRaisesRegex(ValueError, "Extraction is incomplete"):                  # the context var is reset: no sticky override
            validate_patch_package_identity(self.csv, manifest)
        write_csv_rows_file(self.csv, CSV_FIELDS, [{**self.rows[0], "translation": ""}, self.rows[1]])   # no translated row at all
        with partial_patch_override(True):
            audit = audit_patch_package(self.csv, self.manifest)
        self.assertEqual(0, audit["eligible"])                                                 # the worker refuses to build a patch from this (see run_patch_worker)

    def test_complete_package_is_unchanged_by_the_override_flag(self):
        self.status.write_text(json.dumps({"status": "COMPLETE", "complete": True}), encoding="utf-8")
        done = self.patch(True)
        self.assertTrue(done["ok"], done)
        self.assertFalse((self.package / "Patch_Viet_Hoa" / "patch_coverage.json").exists())   # full coverage is never relabelled as a subset


if __name__ == "__main__":
    unittest.main()
