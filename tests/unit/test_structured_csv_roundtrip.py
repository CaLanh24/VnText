"""Proof for field-level CSV extraction and symmetric patching."""

from __future__ import annotations

import codecs
import csv
import hashlib
import io
import sys
import tempfile
import unittest
from pathlib import Path


def _tests_lib_on_path() -> None:
    cur = Path(__file__).resolve().parent
    while cur.name != "tests" and cur.parent != cur:
        cur = cur.parent
    lib = cur / "lib"
    value = str(lib)
    if value not in sys.path:
        sys.path.insert(0, value)


_tests_lib_on_path()
from bootstrap import bootstrap

TESTS, ROOT, LIB = bootstrap(__file__)

from vntext.extract_pipeline import extract_project
from vntext.package_io import read_csv_rows_file, write_csv_rows_file, write_package
from vntext.patch import apply_translation_package


class StructuredCsvRoundtripTests(unittest.TestCase):
    def test_extract_patch_reopen_and_preserve_original(self):
        with tempfile.TemporaryDirectory(prefix="vntext-structured-csv-") as name:
            root = Path(name)
            source = root / "StreamingAssets" / "Localization" / "dialogue.csv"
            source.parent.mkdir(parents=True)
            rendered = io.StringIO(newline="")
            writer = csv.writer(rendered, lineterminator="\r\n")
            writer.writerows(
                [
                    ["id", "text", "description"],
                    ["line_1", "Hello from CSV", "Short description"],
                    ["line_2", "Yes", "No"],
                ]
            )
            source.write_bytes(codecs.BOM_UTF8 + rendered.getvalue().encode("utf-8"))
            original_hash = hashlib.sha256(source.read_bytes()).hexdigest()

            main, review, stats = extract_project(str(root), "deep", None, "balanced")
            csv_entries = [entry for entry in main if entry.import_method == "structured_csv_cell"]
            self.assertEqual(
                {entry.source_text for entry in csv_entries},
                {"Hello from CSV", "Short description", "Yes", "No"},
            )
            self.assertTrue(
                all(
                    {"row_index", "column_index"}.issubset(entry.locator)
                    and all(entry.patch_proof.values())
                    for entry in csv_entries
                )
            )
            self.assertFalse(any(entry.source_text == "line_1" for entry in main + review))

            package = root / "package"
            write_package(str(package), main, review, stats, True, enforce_symmetry=True)
            fields, rows = read_csv_rows_file(package / "translation.csv")
            translations = {
                "Hello from CSV": "Xin chào từ CSV",
                "Short description": "Mô tả ngắn",
                "Yes": "Có",
                "No": "Không",
            }
            for row in rows:
                row["translation"] = translations[row["source_text"]]
            write_csv_rows_file(package / "translation.csv", fields, rows)

            patch_out = root / "patch"
            apply_translation_package(
                str(package / "translation.csv"),
                str(package / "manifest.json"),
                str(root),
                str(patch_out),
            )

            patched = patch_out / "COPY_TO_GAME_ROOT" / "StreamingAssets" / "Localization" / "dialogue.csv"
            self.assertTrue(patched.is_file())
            self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(), original_hash)
            with patched.open("r", encoding="utf-8-sig", newline="") as handle:
                result = list(csv.DictReader(handle))
            self.assertEqual(result[0]["text"], "Xin chào từ CSV")
            self.assertEqual(result[0]["description"], "Mô tả ngắn")
            self.assertEqual(result[1]["text"], "Có")
            self.assertEqual(result[1]["description"], "Không")
            self.assertIn("CSV StreamingAssets\\Localization\\dialogue.csv: 4/4", (patch_out / "import_report.txt").read_text(encoding="utf-8"))
            self.assertIn("VERIFY translated_bytes_in_patched_files: 4/4", (patch_out / "import_report.txt").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
