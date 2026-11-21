"""Extract contract over the generated layouts: always exactly one terminal event, a stated outcome, no leftover 'running' state, never a crash."""
import json
from pathlib import Path
import tempfile
import time
import unittest

from tests.lib.work_paths import work_temp_dir
from tests.unit.test_scan_layout_matrix import LAYOUTS
from vntext.app_tasks import run_extract_task

KNOWN = {"COMPLETE", "PARTIAL", "EMPTY", "FAILED"}


class ExtractLayoutMatrixTests(unittest.TestCase):
    def test_every_layout_ends_with_one_stated_outcome(self):
        base = work_temp_dir("extract-layout-matrix")
        for name, (build, _allowed) in LAYOUTS.items():
            with self.subTest(layout=name), tempfile.TemporaryDirectory(dir=base) as temp:
                root = Path(temp) / "game root"
                root.mkdir()
                build(root)
                out = Path(temp) / "package"
                events = []
                started = time.monotonic()
                run_extract_task(str(root), str(out), "deep", "balanced", False, renpy_sdk_action="none",
                                 progress=lambda _info: None, log=lambda _text, *_a: None, complete=events.append)
                self.assertLess(time.monotonic() - started, 60)
                self.assertEqual(1, len(events), events)
                event = events[0]
                if event.get("ok"):
                    self.assertTrue((out / "translation.csv").is_file(), "an ok result has its CSV")
                else:
                    self.assertTrue(str(event.get("error") or "").strip(), "a failed or partial result says why")
                    self.assertNotEqual("RUNNING", json.loads((out / "extract_status.json").read_text())["status"]) if (out / "extract_status.json").is_file() else None
                status = event.get("extract_status")
                if status is not None:
                    self.assertIn(status, KNOWN)
                # Image scanning is announced for a real folder and never run inline.
                self.assertIn("image_scan_pending", event) if event.get("extract_status") else None
                leftovers = [p.name for p in out.glob(".vntext-*")] if out.exists() else []
                self.assertEqual([], leftovers, "no staging or lock may survive a terminal event")

    def test_cancel_before_start_leaves_no_state(self):
        base = work_temp_dir("extract-layout-matrix")
        with tempfile.TemporaryDirectory(dir=base) as temp:
            root = Path(temp) / "g"
            build, _ = LAYOUTS["loose_rpy"]
            root.mkdir()
            build(root)
            out = Path(temp) / "package"
            events = []
            run_extract_task(str(root), str(out), "deep", "balanced", False, renpy_sdk_action="none", progress=lambda _i: None, log=lambda *_a: None,
                             complete=events.append, is_cancelled=lambda: True)
            self.assertEqual(1, len(events))
            self.assertFalse(events[0]["ok"])
            self.assertEqual([], [p.name for p in out.glob(".vntext-*")] if out.exists() else [])


if __name__ == "__main__":
    unittest.main()
