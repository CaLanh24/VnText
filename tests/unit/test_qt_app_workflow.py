"""Integration test: Qt UI task runner + real extract progress."""

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
import time
import unittest
from pathlib import Path
from unittest.mock import patch

try:
    from PySide6.QtWidgets import QApplication
except ModuleNotFoundError:  # pragma: no cover - optional legacy Qt dep
    QApplication = None  # type: ignore[misc, assignment]

from vntext.app_tasks import run_extract_task
from vntext.ui_progress import compute_percent


class QtAppWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if QApplication is None:
            raise unittest.SkipTest("PySide6 not installed — legacy Qt workflow optional")
        cls._app = QApplication.instance() or QApplication([])

    def test_extract_via_qt_worker_reaches_100_only_on_complete(self):
        from vntext.qt_app import VNTextQtApp

        win = VNTextQtApp()
        try:
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                (root / "sample.txt").write_text("NPC: Hello there\n", encoding="utf-8")
                out = root / "package"
                win.input_field.setText(str(root))
                win.output_field.setText(str(out))

                percents: list[int] = []
                done = {"ok": False}

                def on_progress(info):
                    percents.append(compute_percent(int(info.get("done") or 0), int(info.get("total") or 0)))

                def on_complete(payload):
                    done["ok"] = bool(payload.get("ok"))

                with patch("vntext.qt_app.play_success_sound") as beep:
                    self.assertTrue(
                        win.start_task(
                            "Lấy text",
                            run_extract_task,
                            src=str(root),
                            out=str(out),
                            mode="deep",
                            level="balanced",
                            separate_review=True,
                        )
                    )
                    worker = win._runner.worker
                    self.assertIsNotNone(worker)
                    worker.progress.connect(on_progress)
                    worker.complete.connect(on_complete)

                    deadline = time.time() + 30
                    while win._runner.busy and time.time() < deadline:
                        self._app.processEvents()
                        time.sleep(0.02)
                    self._app.processEvents()

                    beep.assert_called_once()

                self.assertTrue(done["ok"])
                self.assertEqual(win.progress_bar.value(), 100)
                self.assertLessEqual(max(percents or [0]), 99)
        finally:
            win.close()


if __name__ == "__main__":
    unittest.main()
