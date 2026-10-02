"""Proof for field-level JSON extraction and symmetric patching."""

from __future__ import annotations

import codecs
import csv
import hashlib
import json
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


class StructuredJsonRoundtripTests(unittest.TestCase):
    def test_extract_patch_reopen_and_preserve_original(self):
        with tempfile.TemporaryDirectory(prefix="vntext-structured-json-") as name:
            root = Path(name)
            source = root / "Sample_Data" / "StreamingAssets" / "Localization" / "en.json"
            source.parent.mkdir(parents=True)
            document = {
                "dialogue": "Hello from JSON",
                "choices": ["Yes", "No"],
                "metadata": {"name": "internal_identifier", "text": "Welcome to the menu"},
            }
            rendered = json.dumps(document, ensure_ascii=False, indent=2).replace("\n", "\r\n") + "\r\n"
            source.write_bytes(codecs.BOM_UTF8 + rendered.encode("utf-8"))
            original_hash = hashlib.sha256(source.read_bytes()).hexdigest()

            main, review, stats = extract_project(str(root), "deep", None, "balanced")
            json_entries = [entry for entry in main if entry.import_method == "structured_json_value"]
            self.assertEqual({entry.source_text for entry in json_entries}, {
                "Hello from JSON",
                "Yes",
                "No",
                "Welcome to the menu",
            })
            self.assertTrue(all(entry.locator.get("json_pointer") for entry in json_entries))
            self.assertTrue(all(all(entry.patch_proof.values()) for entry in json_entries))
            self.assertFalse(any(entry.source_text == "internal_identifier" for entry in main + review))

            package = root / "package"
            write_package(str(package), main, review, stats, True, enforce_symmetry=True)
            fields, rows = read_csv_rows_file(package / "translation.csv")
            translations = {
                "Hello from JSON": "Xin chào từ JSON",
                "Yes": "Có",
                "No": "Không",
                "Welcome to the menu": "Chào mừng đến menu",
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

            patched = patch_out / "COPY_TO_GAME_ROOT" / "Sample_Data" / "StreamingAssets" / "Localization" / "en.json"
            self.assertTrue(patched.is_file())
            self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(), original_hash)
            patched_doc = json.loads(patched.read_text(encoding="utf-8-sig"))
            self.assertEqual(patched_doc["dialogue"], "Xin chào từ JSON")
            self.assertEqual(patched_doc["choices"], ["Có", "Không"])
            self.assertEqual(patched_doc["metadata"]["text"], "Chào mừng đến menu")
            self.assertEqual(patched_doc["metadata"]["name"], "internal_identifier")

            report = (patch_out / "import_report.txt").read_text(encoding="utf-8")
            self.assertIn("JSON Sample_Data\\StreamingAssets\\Localization\\en.json: 4/4", report)
            self.assertIn("VERIFY translated_bytes_in_patched_files: 4/4", report)


if __name__ == "__main__":
    unittest.main()
