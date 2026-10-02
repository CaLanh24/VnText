"""Integration test: VNTextApp message queue + real extract progress."""

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
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch


import tkinter as tk

from vntext.ui_progress import compute_percent
from vntext_studio import VNTextApp, extract_project, write_package


class AppWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # The legacy Tk UI is optional in the pruned portable worker runtime.
        # Skip honestly when Tcl/Tk is unavailable instead of turning an
        # environment limitation into a product failure.
        try:
            probe = tk.Tk()
            probe.withdraw()
            probe.destroy()
        except tk.TclError as exc:
            raise unittest.SkipTest(f"Tk runtime unavailable: {exc}")

    def test_extract_via_message_queue_reaches_100_only_on_complete(self):
        app = VNTextApp()
        try:
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                (root / "sample.txt").write_text("NPC: Hello there\n", encoding="utf-8")
                out = root / "package"
                app.input_path.set(str(root))
                app.output_path.set(str(out))

                percents = []
                done_flags = []

                def work():
                    try:
                        def progress(info):
                            app.messages.put(("PROGRESS", info))
                            percents.append(compute_percent(int(info.get("done") or 0), int(info.get("total") or 0)))

                        main, review, stats = extract_project(str(root), "deep", progress, "balanced")
                        write_package(str(out), main, review, stats, True)
                        summary = f"Xong: {len(main)} dong"
                        app.messages.put(("COMPLETE", {"ok": True, "summary": summary}))
                    except Exception as exc:
                        app.messages.put(("COMPLETE", {"ok": False, "error": str(exc)}))
                    finally:
                        app.messages.put("__STOP__")

                with patch("vntext.app_ui.play_success_sound") as beep:
                    self.assertTrue(app.start_task("Lay text", work, "Dang test..."))
                    deadline = time.time() + 30
                    while app._busy and time.time() < deadline:
                        app._poll()
                        time.sleep(0.05)
                    app._poll()
                    done_flags.append(app._progress.last_info)
                    beep.assert_called_once()

                self.assertFalse(app._busy)
                self.assertEqual(app.progress["value"], 100)
                self.assertLessEqual(max(percents or [0]), 99)
        finally:
            app.destroy()


if __name__ == "__main__":
    unittest.main()
