"""Shared task/patch completion contracts for the public UI compatibility layer."""

from __future__ import annotations

import csv
import json
import queue
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from vntext.app_tasks import run_patch_task
from vntext.app_ui import VNTextApp


class SharedTaskBridgeTests(unittest.TestCase):
    def test_bridge_preserves_log_progress_complete_and_stop_order(self):
        app = VNTextApp.__new__(VNTextApp)
        app.messages = queue.Queue()

        def start_task(_name, work, _status):
            work()
            return True

        app.start_task = start_task

        def runner(*, progress, log, complete, value):
            log(f"log {value}")
            progress({"done": 1, "total": 1, "phase": "extract"})
            complete({"ok": True, "summary": "done"})

        self.assertTrue(app._start_shared_task("Extract", runner, status="start", value=7))
        events = [app.messages.get_nowait() for _ in range(4)]
        self.assertEqual(events[0], "log 7")
        self.assertEqual(events[1], ("PROGRESS", {"done": 1, "total": 1, "phase": "extract"}))
        self.assertEqual(events[2], ("COMPLETE", {"ok": True, "summary": "done"}))
        self.assertEqual(events[3], "__STOP__")


class PatchCompletionContractTests(unittest.TestCase):
    def test_readback_timeout_is_terminal_failure_with_report_paths(self):
        with tempfile.TemporaryDirectory(prefix="vntext-patch-contract-") as temp:
            root = Path(temp)
            package = root / "package"
            package.mkdir()
            csv_path = package / "translation.csv"
            manifest_path = package / "manifest.json"
            with csv_path.open("w", encoding="utf-8-sig", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=["key", "source_text", "translation"])
                writer.writeheader()
                writer.writerow({"key": "k", "source_text": "Hello", "translation": "Xin chào"})
            manifest_path.write_text(json.dumps({"entries": []}), encoding="utf-8")
            game = root / "game"
            game.mkdir()
            patch_out = package / "patch-output"

            def fake_apply(_csv, _manifest, _src, out, _progress):
                output = Path(out)
                output.mkdir(parents=True, exist_ok=True)
                (output / "patch_verification.json").write_text(
                    json.dumps(
                        {
                            "schema_version": 1,
                            "status": "TIMEOUT",
                            "reason": "bounded read-back deadline",
                            "counts": {"TIMEOUT": 1},
                            "results": [{"status": "TIMEOUT", "reason": "bounded read-back deadline"}],
                        }
                    ),
                    encoding="utf-8",
                )
                (output / "import_report.txt").write_text(
                    "patch_verification_status: TIMEOUT\n", encoding="utf-8"
                )

            completions: list[dict] = []
            with patch("vntext.app_tasks.apply_translation_package", fake_apply):
                run_patch_task(
                    csv_path,
                    manifest_path,
                    str(game),
                    str(package),
                    progress=lambda _info: None,
                    log=lambda _line: None,
                    complete=completions.append,
                    patch_out_override=patch_out,
                    include_installer=False,
                    write_manifest_file=False,
                )

            self.assertEqual(len(completions), 1)
            self.assertFalse(completions[0]["ok"])
            self.assertFalse(completions[0]["complete"])
            self.assertIn("TIMEOUT", completions[0]["error"])
            self.assertEqual(
                completions[0]["patch_verification_report"],
                str(patch_out / "patch_verification.json"),
            )
            self.assertEqual(completions[0]["import_report"], str(patch_out / "import_report.txt"))


if __name__ == "__main__":
    unittest.main()
