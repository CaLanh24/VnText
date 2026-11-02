import json
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

from tests.lib.work_paths import work_temp_dir
from vntext.entry import Entry
from vntext.package_io import CSV_FIELDS, write_csv_rows_file
from vntext.patch_pipeline import apply_translation_package
from vntext.patch_safety import resolve_game_source_file
from vntext.package_io import read_translation_rows


class PatchInputSafetyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=work_temp_dir("patch-input-safety"))
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.game = self.root / "generated-game"
        self.game.mkdir()
        self.source = self.game / "dialogue.txt"
        self.source.write_text("Hello\n", encoding="utf-8")
        self.entry = Entry("Hello", "dialogue.txt", "line:1", import_method="plain_text_line",
                           safety="safe", locator={"line": 1},
                           patch_proof={key: True for key in ("reader", "writer", "preflight", "reopen", "semantic_verify")}).finalize()
        self.package = self.root / "package"
        self.package.mkdir()
        self.csv = self.package / "translation.csv"
        self.manifest = self.package / "manifest.json"
        self.row = {**self.entry.to_csv_row(), "translation": "Xin chào"}
        write_csv_rows_file(self.csv, CSV_FIELDS, [self.row])
        self.manifest.write_text(json.dumps({"entries": [self.entry.to_manifest()]}), encoding="utf-8")

    def apply(self, output):
        return apply_translation_package(str(self.csv), str(self.manifest), str(self.game), str(output))

    def test_source_resolution_rejects_escape(self):
        for relative in ("../outside.txt", "/absolute.txt", "C:/outside.txt", "x/../../outside.txt"):
            with self.subTest(relative=relative), self.assertRaises(ValueError):
                resolve_game_source_file(self.game, relative)

    def test_output_must_not_be_in_game(self):
        output = self.game / "new-patch"
        with self.assertRaises(ValueError): self.apply(output)
        self.assertFalse(output.exists())
        self.assertEqual(self.source.read_text(), "Hello\n")

    def test_csv_source_must_match_manifest(self):
        write_csv_rows_file(self.csv, CSV_FIELDS, [{**self.row, "source_text": "Changed source"}])
        output = self.root / "patch"
        with self.assertRaises(ValueError): self.apply(output)
        self.assertFalse(output.exists())

    def test_duplicate_csv_identity_is_rejected(self):
        write_csv_rows_file(self.csv, CSV_FIELDS, [self.row, {**self.row, "translation": "Chào bạn"}])
        with self.assertRaises(ValueError): self.apply(self.root / "patch")

    def test_partial_extraction_is_not_final_patch(self):
        (self.package / "extract_status.json").write_text(json.dumps({"status": "PARTIAL", "complete": False}))
        with self.assertRaises(ValueError): self.apply(self.root / "patch")

    SCOPED = {
        "status": "PARTIAL", "complete": False, "main": 1, "review": 0, "errors": 0, "severity": "warning",
        "native_accounting_complete": True, "patch_scope": "VERIFIED_MAIN_SUBSET",
        "limitations": [{"code": "RUNTIME_DYNAMIC_UNRESOLVED", "count": 2, "message": "2 dynamic expressions"},
                        {"code": "ARCHIVE_SOURCE_RUNTIME_UNPROVEN", "count": 1, "message": "archive source"}],
    }

    def run_worker_patch(self):
        from vntext.app_tasks import run_patch_task
        completed = []
        run_patch_task(self.csv, self.manifest, str(self.game), str(self.package), progress=lambda _: None, log=lambda _: None,
                       complete=completed.append, patch_out_override=self.package / "Patch_Viet_Hoa")
        self.assertEqual(len(completed), 1)
        return completed[0]

    def test_scoped_partial_with_only_expected_limitations_patches_the_verified_subset_with_excluded_coverage(self):
        (self.package / "extract_status.json").write_text(json.dumps(self.SCOPED), encoding="utf-8")
        original = (self.source.read_bytes(), self.csv.read_bytes(), self.manifest.read_bytes())
        done = self.run_worker_patch()
        self.assertTrue(done["ok"], done)
        output = self.package / "Patch_Viet_Hoa"
        self.assertEqual("Xin chào" + chr(10), (output / "COPY_TO_GAME_ROOT/dialogue.txt").read_text(encoding="utf-8"))   # exact read-back of the verified row
        coverage = json.loads((output / "patch_coverage.json").read_text(encoding="utf-8"))
        self.assertEqual("VERIFIED_MAIN_SUBSET", coverage["scope"])
        self.assertIn("NOT a full-game PASS", coverage["statement"])
        self.assertEqual(["RUNTIME_DYNAMIC_UNRESOLVED", "ARCHIVE_SOURCE_RUNTIME_UNPROVEN"], [item["code"] for item in coverage["excluded_coverage"]])
        self.assertEqual(original, (self.source.read_bytes(), self.csv.read_bytes(), self.manifest.read_bytes()))
        self.assertEqual("PARTIAL", json.loads((self.package / "extract_status.json").read_text(encoding="utf-8"))["status"])   # coverage stays PARTIAL

    def test_complete_package_patches_without_excluded_coverage(self):
        (self.package / "extract_status.json").write_text(json.dumps({"status": "COMPLETE", "complete": True}), encoding="utf-8")
        done = self.run_worker_patch()
        self.assertTrue(done["ok"], done)
        self.assertFalse((self.package / "Patch_Viet_Hoa" / "patch_coverage.json").exists())

    def test_scoped_eligibility_never_widens_beyond_the_expected_limitations(self):
        from vntext.patch_gate import scoped_patch_eligible
        self.assertTrue(scoped_patch_eligible(self.SCOPED))
        unexpected = [{"code": "SOMETHING_ELSE", "count": 1, "message": "x"}]
        broken = {
            "actual error": {"errors": 1, "severity": "error"},
            "review rows": {"review": 3},
            "no-SDK / empty MAIN": {"main": 0, "review": 4},
            "accounting mismatch": {"native_accounting_complete": False},
            "unknown limitation": {"limitations": self.SCOPED["limitations"] + unexpected},
            "no limitation": {"limitations": []},
            "no scope marker": {"patch_scope": "NONE"},
            "failed": {"status": "FAILED"},
            "empty": {"status": "EMPTY"},
            "claims complete while partial": {"complete": True},
            "string count": {"main": "1"},
            "bool count": {"errors": False, "main": True},
        }
        for name, change in broken.items():
            with self.subTest(name):
                self.assertFalse(scoped_patch_eligible({**self.SCOPED, **change}))
        unpromoted = [{"code": "REVIEW_SCREEN_CANDIDATES_UNPROMOTED", "count": 8, "message": "8 static screen candidates"}]
        screen_only = {**self.SCOPED, "review": 8, "limitations": self.SCOPED["limitations"] + unpromoted}
        self.assertTrue(scoped_patch_eligible(screen_only))                                  # review rows that are ONLY unpromoted screen candidates
        self.assertFalse(scoped_patch_eligible({**screen_only, "review": 9}))                # one other review row blocks
        self.assertFalse(scoped_patch_eligible({**screen_only, "review": 7}))                # the count must match exactly
        self.assertFalse(scoped_patch_eligible({**self.SCOPED, "review": 8}))                # review rows without the evidence limitation
        (self.package / "extract_status.json").write_text(json.dumps({**self.SCOPED, "errors": 1, "severity": "error"}), encoding="utf-8")
        before = (self.source.read_bytes(), self.csv.read_bytes())
        done = self.run_worker_patch()
        self.assertFalse(done["ok"], done)
        self.assertFalse((self.package / "Patch_Viet_Hoa" / "COPY_TO_GAME_ROOT").exists())
        self.assertEqual(before, (self.source.read_bytes(), self.csv.read_bytes()))

    def test_scoped_patch_still_refuses_an_unverified_entry_or_identity_mismatch(self):
        (self.package / "extract_status.json").write_text(json.dumps(self.SCOPED), encoding="utf-8")
        write_csv_rows_file(self.csv, CSV_FIELDS, [{**self.row, "source_text": "Changed source"}])
        done = self.run_worker_patch()
        self.assertFalse(done["ok"], done)
        self.assertEqual("Hello" + chr(10), self.source.read_text())

    def test_existing_output_and_source_are_preserved(self):
        output = self.root / "patch"
        output.mkdir()
        preserved = output / "owner.txt"
        preserved.write_bytes(b"keep exact bytes")
        original = self.source.read_bytes()
        with self.assertRaises(ValueError): self.apply(output)
        self.assertEqual(preserved.read_bytes(), b"keep exact bytes")
        self.assertEqual(self.source.read_bytes(), original)

    def test_malformed_csv_is_rejected_before_patch(self):
        for raw in ("key,source_text,translation,KEY\nk,Hello,X,k\n",
                    "key,source_text,translation\nk,Hello,X,extra\n",
                    "key,source_text,translation\nk,Hello\n"):
            with self.subTest(raw=raw):
                self.csv.write_text(raw, encoding="utf-8")
                with self.assertRaises(ValueError): read_translation_rows(str(self.csv))

    def test_worker_explicit_package_output_uses_separate_patch_directory(self):
        from vntext_worker.task_runners import run_patch_worker
        original_csv = self.csv.read_bytes()
        original_manifest = self.manifest.read_bytes()
        completed = []
        with patch("vntext_worker.task_runners._make_callbacks", return_value=(lambda _: None, lambda _: None, completed.append)):
            run_patch_worker("patch-input-fixture", {"src": str(self.game), "out": str(self.package),
                             "csv_path": str(self.csv), "manifest_path": str(self.manifest)}, lambda: False)
        self.assertEqual(len(completed), 1)
        self.assertTrue(completed[0]["ok"], completed[0])
        output = self.package / "Patch_Viet_Hoa"
        self.assertEqual((output / "COPY_TO_GAME_ROOT/dialogue.txt").read_text(encoding="utf-8"), "Xin chào\n")
        self.assertEqual(self.csv.read_bytes(), original_csv)
        self.assertEqual(self.manifest.read_bytes(), original_manifest)


if __name__ == "__main__": unittest.main()
