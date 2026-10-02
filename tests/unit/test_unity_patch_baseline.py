"""Generic safety tests for isolated Unity-resource helpers."""

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
import hashlib
import json
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

from unity_patch_baseline import (
    assert_path_outside_game,
    collect_unity_rel_paths,
    copy_game_files,
    fill_unity_translations,
    hash_game_files,
    inspect_patched_file,
    origin_asset_hash_keys,
    parse_import_counts,
    sha256_file,
)


class UnityPatchHelperTests(unittest.TestCase):
    def test_copy_hash_and_source_boundary_are_generic(self):
        with tempfile.TemporaryDirectory(prefix="vntext-source-guard-") as tmp:
            root = Path(tmp)
            source = root / "source"
            destination = root / "isolated"
            rel = "Sample_Data/dialogue.txt"
            original = b"Hello\n"
            (source / rel).parent.mkdir(parents=True)
            (source / rel).write_bytes(original)

            assert_path_outside_game(destination, source, "isolated output")
            with self.assertRaises(RuntimeError):
                assert_path_outside_game(source / rel, source, "source output")
            with patch("work_paths.assert_write_destination"):
                self.assertEqual(copy_game_files(source, destination, [rel]), [rel])
            self.assertEqual((source / rel).read_bytes(), original)
            hashes = hash_game_files(source, [rel, "missing.bin"])
            self.assertEqual(hashes[rel]["sha256"], hashlib.sha256(original).hexdigest())
            self.assertFalse(hashes["missing.bin"]["exists"])

    def test_csv_helpers_preserve_generic_unity_locator_rows(self):
        with tempfile.TemporaryDirectory(prefix="vntext-unity-csv-") as tmp:
            root = Path(tmp)
            source = root / "translation.csv"
            target = root / "filled.csv"
            fields = ["key", "source_text", "translation", "file_path", "import_method"]
            row = {"key": "k", "source_text": "Hello", "translation": "", "file_path": "Sample_Data/data.assets", "import_method": "unity_textasset_line"}
            with source.open("w", encoding="utf-8", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=fields)
                writer.writeheader()
                writer.writerow(row)
            before = source.read_bytes()
            with patch("work_paths.assert_write_destination"):
                self.assertEqual(fill_unity_translations(source, target), 1)
            text = target.read_text(encoding="utf-8-sig")
            self.assertIn("VI:Hello", text)
            self.assertEqual(source.read_bytes(), before)

    def test_output_inspection_and_report_parsing_do_not_need_unity_fixture(self):
        with tempfile.TemporaryDirectory(prefix="vntext-output-") as tmp:
            path = Path(tmp) / "report.json"
            path.write_text('{"ok": true}\n', encoding="utf-8")
            info = inspect_patched_file(path)
            self.assertTrue(info["openable"])
            self.assertEqual(info["kind"], "json")
            self.assertEqual(parse_import_counts("patched_lines: 1\nskipped_lines: 0\n"), {"patched_lines": "1", "skipped_lines": "0"})

    def test_catalog_metadata_is_excluded_from_source_hash_keys(self):
        self.assertEqual(origin_asset_hash_keys({"aa/catalog.json": 1, "data.assets": 2}), ["data.assets"])

    def test_unity_file_discovery_is_extension_based_without_title_names(self):
        with tempfile.TemporaryDirectory(prefix="vntext-discovery-") as tmp:
            path = Path(tmp) / "rows.csv"
            path.write_text(
                "key,file_path\n1,Sample_Data/data.assets\n2,StreamingAssets/catalog.json\n3,opaque.resource\n",
                encoding="utf-8",
            )
            self.assertEqual(collect_unity_rel_paths(path), ["Sample_Data/data.assets"])


def _report_field(report: str, name: str) -> str:
    prefix = name + ":"
    for line in report.splitlines():
        if line.startswith(prefix):
            return line.split(":", 1)[1].strip()
    raise AssertionError(f"{name} missing from import_report.txt")


if __name__ == "__main__":
    unittest.main()
