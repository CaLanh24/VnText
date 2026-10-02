"""Tests for JSON worker protocol (milestone 1)."""

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

import json
import os
import subprocess
import time
import unittest
from pathlib import Path
from unittest.mock import patch


from vntext_worker.protocol import PROTOCOL_VERSION, emit, read_commands
from vntext_worker.task_runners import _make_callbacks
import vntext_worker.worker_main as worker_main


class WorkerProtocolTests(unittest.TestCase):
    def test_emit_includes_version(self):
        import io

        buf = io.StringIO()
        old = sys.stdout
        sys.stdout = buf
        try:
            emit({"type": "ready"})
        finally:
            sys.stdout = old
        data = json.loads(buf.getvalue().strip())
        self.assertEqual(data["v"], PROTOCOL_VERSION)
        self.assertEqual(data["type"], "ready")

    def test_emit_complete_preserves_optional_diagnostic_contract(self):
        import io

        buf = io.StringIO()
        old = sys.stdout
        sys.stdout = buf
        try:
            from vntext_worker.protocol import emit_complete

            emit_complete(
                "diagnostic-task",
                ok=False,
                error="translation failed",
                complete=False,
                pending=2,
                review_only=1,
                blocked=1,
                diagnostic_path="package/.mt/diagnostic_summary.json",
                diagnostic_stage="TRANSLATE",
                diagnostic_root_cause="TRANSLATION_MISSED",
                diagnostic_affected_count=2,
                diagnostic_action="Review blockers before retrying.",
                diagnostic_status="FAILED",
                human_review_required_count=3,
                renpy_sdk_missing=True,
                patch_engine="renpy",
                patch_delivery="renpy_native_overlay",
                patch_payload_path="package/Patch_Viet_Hoa/COPY_TO_GAME_ROOT",
                patch_install_instructions="Copy overlay into the Ren'Py game root.",
            )
        finally:
            sys.stdout = old

        data = json.loads(buf.getvalue().strip())
        self.assertEqual("TRANSLATE", data["diagnostic_stage"])
        self.assertEqual("TRANSLATION_MISSED", data["diagnostic_root_cause"])
        self.assertEqual(2, data["diagnostic_affected_count"])
        self.assertEqual("package/.mt/diagnostic_summary.json", data["diagnostic_path"])
        self.assertEqual(3, data["human_review_required_count"])
        self.assertTrue(data["renpy_sdk_missing"])
        self.assertEqual("renpy", data["patch_engine"])
        self.assertEqual("renpy_native_overlay", data["patch_delivery"])
        self.assertEqual("package/Patch_Viet_Hoa/COPY_TO_GAME_ROOT", data["patch_payload_path"])
        self.assertEqual("Copy overlay into the Ren'Py game root.", data["patch_install_instructions"])

    def test_task_runner_forwards_patch_delivery_fields(self):
        with patch("vntext_worker.task_runners.emit_complete") as emit_complete:
            _progress, _log, complete = _make_callbacks("patch-task", lambda: False)
            complete(
                {
                    "ok": True,
                    "summary": "native overlay",
                    "patch_engine": "renpy",
                    "patch_delivery": "renpy_native_overlay",
                    "patch_payload_path": "package/Patch_Viet_Hoa/COPY_TO_GAME_ROOT",
                    "patch_install_instructions": "Copy overlay into the Ren'Py game root.",
                }
            )

        fields = emit_complete.call_args.kwargs
        self.assertEqual("renpy", fields["patch_engine"])
        self.assertEqual("renpy_native_overlay", fields["patch_delivery"])
        self.assertEqual("package/Patch_Viet_Hoa/COPY_TO_GAME_ROOT", fields["patch_payload_path"])
        self.assertEqual("Copy overlay into the Ren'Py game root.", fields["patch_install_instructions"])

    def test_task_runner_forwards_missing_renpy_sdk_state(self):
        with patch("vntext_worker.task_runners.emit_complete") as emit_complete:
            _progress, _log, complete = _make_callbacks("renpy-task", lambda: False)
            complete({"ok": False, "complete": False, "renpy_sdk_missing": True})

        self.assertTrue(emit_complete.call_args.kwargs["renpy_sdk_missing"])


class WorkerIntegrationTests(unittest.TestCase):
    def test_removed_model_is_rejected_before_model_initialization(self):
        calls: list[str] = []
        command = {
            "type": "run",
            "id": "removed-model",
            "task": "translate",
            "params": {"model": "vinai"},
        }

        with patch.object(worker_main, "emit_ready"), patch.object(
            worker_main, "read_commands", return_value=iter([command])
        ), patch.object(
            worker_main, "_ensure_ct2_on_main_thread", side_effect=lambda: calls.append("ct2-init")
        ), patch.object(
            worker_main, "_dispatch", side_effect=lambda *args: calls.append("dispatch")
        ), patch.object(worker_main, "emit_error") as emit_error, patch.object(
            worker_main, "emit_complete"
        ) as emit_complete:
            self.assertEqual(0, worker_main.main())

        self.assertEqual([], calls)
        emit_error.assert_called_once()
        emit_complete.assert_called_once()
        self.assertIn("chỉ có CT2/OPUS-MT", emit_error.call_args.args[1])

    def test_worker_exits_cleanly_on_stdin_eof(self):
        py = Path(os.environ.get("VNTEXT_WORKER_PYTHON", "")) if os.environ.get("VNTEXT_WORKER_PYTHON") else ROOT / ".venv" / "Scripts" / "python.exe"
        if not py.is_file():
            self.skipTest("venv python missing")
        env = os.environ.copy()
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        proc = subprocess.Popen(
            [str(py), "-u", "-m", "vntext_worker.worker_main"],
            cwd=str(ROOT),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            env=env,
            text=True,
            encoding="utf-8",
        )
        try:
            assert proc.stdout is not None and proc.stdin is not None
            self.assertIn("ready", proc.stdout.readline().strip())
            proc.stdin.close()
            self.assertEqual(0, proc.wait(timeout=5))
        finally:
            if proc.poll() is None:
                proc.kill()
            proc.wait(timeout=5)
            if proc.stdin is not None:
                proc.stdin.close()
            if proc.stdout is not None:
                proc.stdout.close()
            if proc.stderr is not None:
                proc.stderr.close()

    def test_sample_worker_progress_cancel(self):
        py = Path(os.environ.get("VNTEXT_WORKER_PYTHON", "")) if os.environ.get("VNTEXT_WORKER_PYTHON") else ROOT / ".venv" / "Scripts" / "python.exe"
        if not py.is_file():
            self.skipTest("venv python missing")
        proc = subprocess.Popen(
            [str(py), "-u", "-m", "vntext_worker.worker_main"],
            cwd=str(ROOT),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
        )
        try:
            assert proc.stdout is not None and proc.stdin is not None
            ready = proc.stdout.readline().strip()
            self.assertIn("ready", ready)
            task_id = "t1"
            proc.stdin.write(
                json.dumps(
                    {
                        "v": PROTOCOL_VERSION,
                        "type": "run",
                        "id": task_id,
                        "task": "sample",
                        "params": {"steps": 40, "delay_ms": 50},
                    }
                )
                + "\n"
            )
            proc.stdin.flush()
            time.sleep(0.3)
            proc.stdin.write(json.dumps({"v": PROTOCOL_VERSION, "type": "cancel", "id": task_id}) + "\n")
            proc.stdin.flush()
            saw_complete = False
            deadline = time.time() + 10
            while time.time() < deadline:
                line = proc.stdout.readline()
                if not line:
                    break
                msg = json.loads(line)
                if msg.get("type") == "complete":
                    saw_complete = True
                    self.assertFalse(msg.get("ok", True))
                    break
            self.assertTrue(saw_complete, "expected cancelled complete")
        finally:
            if proc.poll() is None:
                proc.kill()
            proc.wait(timeout=5)
            if proc.stdin is not None:
                proc.stdin.close()
            if proc.stdout is not None:
                proc.stdout.close()
            if proc.stderr is not None:
                proc.stderr.close()


if __name__ == "__main__":
    unittest.main()
