import json
import tempfile
import unittest
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


if __name__ == "__main__": unittest.main()
