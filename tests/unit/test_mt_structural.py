"""Unit tests for mt_check structural rules and mt_apply frozen-safe writes."""

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


from vntext import mt_check
from vntext.mt_apply import apply_batch
from vntext.mt_paths import paths_for_csv


def _write_csv(path: Path, rows: list[dict]):
    fields = [
        "key", "source_text", "translation", "context", "file_path",
        "object_info", "import_method", "safety", "backend", "byte_limit", "patch_note",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, lineterminator="\r\n")
        w.writeheader()
        for row in rows:
            w.writerow({name: row.get(name, "") for name in fields})


class MtStructuralTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.csv_path = Path(self.tmp.name) / "translation.csv"
        self.row = {
            "key": "k1",
            "source_text": "Hello {NAME}, welcome",
            "translation": "",
            "context": "TextAsset:dialog",
            "file_path": "x.txt",
        }
        self.frozen_row = {
            "key": "k2",
            "source_text": "Saved line",
            "translation": "Dong da luu",
            "context": "TextAsset:dialog",
            "file_path": "x.txt",
        }
        _write_csv(self.csv_path, [self.row, self.frozen_row])

    def tearDown(self):
        self.tmp.cleanup()

    def test_structural_placeholder_mismatch_blocks(self):
        bad = "Xin chao NAME, welcome"
        problems = mt_check.structural_problems(self.row, bad)
        self.assertTrue(any("placeholder" in p for p in problems))

    def test_structural_randpick_variant_count(self):
        rp_row = {
            **self.row,
            "key": "rp1",
            "source_text": "A,B,C",
            "context": "NaninovelScript:Main",
        }
        problems = mt_check.structural_problems(rp_row, "Mot,Hai")
        self.assertTrue(any("RandPick" in p or "synonym" in p for p in problems))

    def test_apply_refuses_overwrite_without_flag(self):
        result = apply_batch(
            self.csv_path,
            {"k2": "Ghi de"},
            allow_overwrite=False,
        )
        self.assertFalse(result.ok)
        self.assertIn("overwrite", result.message)

    def test_apply_blocks_structural_violation(self):
        result = apply_batch(
            self.csv_path,
            {"k1": "Xin chao NAME"},
            allow_overwrite=False,
        )
        self.assertFalse(result.ok)
        self.assertTrue(result.problems)

    def test_apply_fills_empty_row(self):
        result = apply_batch(
            self.csv_path,
            {"k1": "Xin chao {NAME}, chao mung"},
            allow_overwrite=False,
        )
        self.assertTrue(result.ok)
        self.assertEqual(result.applied, 1)
        with self.csv_path.open(encoding="utf-8-sig", newline="") as f:
            rows = list(csv.DictReader(f))
        by_key = {r["key"]: r for r in rows}
        self.assertEqual(by_key["k1"]["translation"], "Xin chao {NAME}, chao mung")
        self.assertEqual(by_key["k2"]["translation"], "Dong da luu")

    def test_frozen_key_refused(self):
        paths = paths_for_csv(self.csv_path)
        paths.mt_dir.mkdir(parents=True, exist_ok=True)
        frozen = {"k2": "deadbeef"}
        result = apply_batch(
            self.csv_path,
            {"k2": "Khac"},
            allow_overwrite=True,
            frozen=frozen,
        )
        self.assertFalse(result.ok)
        self.assertIn("frozen", result.message)


if __name__ == "__main__":
    unittest.main()
