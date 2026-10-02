"""Tests for real-data progress formatting and completion rules."""

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


from vntext.ui_progress import ProgressController, compute_percent, format_progress_lines
from vntext.extract import extract_project
from vntext.package_io import write_package


class UiProgressTests(unittest.TestCase):
    def test_never_reports_100_before_complete(self):
        self.assertEqual(compute_percent(10, 10, allow_complete=False), 99)
        self.assertEqual(compute_percent(10, 10, allow_complete=True), 100)

    def test_eta_only_when_real_total(self):
        lines = format_progress_lines({"done": 2, "total": 10, "elapsed": 20, "eta": 80, "phase": "extract", "file": "a.txt"})
        self.assertIn("Đã chạy", lines["time"])
        self.assertIn("~", lines["eta"])
        lines_no_total = format_progress_lines({"done": 0, "total": 0, "elapsed": 5, "eta": 0, "phase": "idle"})
        self.assertEqual(lines_no_total["eta"], "—")

    def test_complete_sets_100(self):
        ctrl = ProgressController()
        ctrl.begin("Lay text")
        ctrl.update({"done": 5, "total": 5, "elapsed": 3, "phase": "extract", "file": "done"})
        snap = ctrl.complete(True, summary="Xong extract")
        self.assertEqual(snap.percent, 100)
        self.assertEqual(snap.ratio, "100%")

    def test_extract_workflow_progress_never_hits_100_before_done(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "dialogue.txt").write_text("Hello world\nSecond line\n", encoding="utf-8")
            out = root / "out"
            percents = []

            def progress(info):
                percents.append(compute_percent(int(info.get("done") or 0), int(info.get("total") or 0)))

            main, review, stats = extract_project(str(root), "deep", progress, "balanced")
            write_package(str(out), main, review, stats, True)
            self.assertTrue(percents)
            self.assertLessEqual(max(percents), 99)


if __name__ == "__main__":
    unittest.main()
