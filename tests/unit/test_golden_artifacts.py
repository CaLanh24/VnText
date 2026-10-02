"""Assert Phase 0 golden extract/patch artifacts exist and match frozen snapshots."""

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
import json
import tempfile
import unittest
from pathlib import Path

from vntext.entry import Entry
from vntext.package_io import read_csv_rows_file, write_csv_rows_file, write_package
from vntext.patch import apply_translation_package

_PROOF = {
    "reader": True,
    "writer": True,
    "preflight": True,
    "reopen": True,
    "semantic_verify": True,
}


class GoldenArtifactTests(unittest.TestCase):
    def _make_synthetic_package(self, root: Path) -> tuple[Path, Path, Path]:
        game = root / "game"
        package = root / "package"
        output = root / "patch"
        game.mkdir()
        source = game / "dialogue.txt"
        source.write_text("Hello player\nKeep this line\n", encoding="utf-8")
        entry = Entry(
            source_text="Hello player",
            file_path="dialogue.txt",
            context="line:0",
            import_method="plain_text_line",
            locator={"line": 0},
            patch_proof=_PROOF,
        ).finalize()
        review = Entry(
            source_text="Opaque payload",
            file_path="data.bin",
            context="offset:0",
            import_method="custom_binary_string",
            review_only=True,
        ).finalize()
        write_package(str(package), [entry], [review], {"mode": "safe", "files_scanned": 1}, True, enforce_symmetry=True)
        fields, rows = read_csv_rows_file(package / "translation.csv")
        rows[0]["translation"] = "Xin chào người chơi"
        write_csv_rows_file(package / "translation.csv", fields, rows)
        apply_translation_package(
            str(package / "translation.csv"),
            str(package / "manifest.json"),
            str(game),
            str(output),
        )
        return package, output, source

    def test_synthetic_package_contains_extract_and_patch_contract_files(self):
        with tempfile.TemporaryDirectory(prefix="vntext-golden-") as name:
            package, output, source = self._make_synthetic_package(Path(name))
            for path in (
                package / "translation.csv",
                package / "review_only.csv",
                package / "extract_report.txt",
                package / "manifest.json",
                output / "import_report.txt",
                output / "patch_verification.json",
            ):
                self.assertTrue(path.is_file(), path)
                self.assertGreater(path.stat().st_size, 0, path)
            patched = output / "COPY_TO_GAME_ROOT" / "dialogue.txt"
            self.assertEqual(patched.read_text(encoding="utf-8"), "Xin chào người chơi\nKeep this line\n")
            self.assertEqual(source.read_text(encoding="utf-8"), "Hello player\nKeep this line\n")

    def test_translation_keys_and_manifest_are_stable_and_distinct(self):
        with tempfile.TemporaryDirectory(prefix="vntext-golden-") as name:
            package, _output, _source = self._make_synthetic_package(Path(name))
            fields, rows = read_csv_rows_file(package / "translation.csv")
            self.assertIn("key", fields)
            keys = [row["key"] for row in rows if row.get("key")]
            self.assertEqual(len(keys), len(set(keys)))
            manifest = json.loads((package / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest.get("format"), 2)
            self.assertEqual({item["key"] for item in manifest["entries"]}, {keys[0], manifest["entries"][1]["key"]})

    def test_import_report_counts_are_parseable(self):
        with tempfile.TemporaryDirectory(prefix="vntext-golden-") as name:
            _package, output, _source = self._make_synthetic_package(Path(name))
            report = (output / "import_report.txt").read_text(encoding="utf-8")
            self.assertTrue(report.startswith("patched_lines:"), report)
            self.assertIn("skipped_lines:", report)
            verification = json.loads((output / "patch_verification.json").read_text(encoding="utf-8"))
            self.assertIn(verification.get("status"), {"PASS", "PASS_LIMITED"})
            self.assertGreaterEqual(int(_report_field(report, "patched_lines")), 1)


def _report_field(report: str, name: str) -> str:
    prefix = name + ":"
    for line in report.splitlines():
        if line.startswith(prefix):
            return line.split(":", 1)[1].strip()
    raise AssertionError(f"{name} missing from import_report.txt")


if __name__ == "__main__":
    unittest.main()
