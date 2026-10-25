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
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch


from vntext_worker.protocol import PROTOCOL_VERSION, emit, emit_cancel_ack, read_commands
from vntext_worker.task_runners import _make_callbacks
import vntext_worker.worker_main as worker_main
from tests.lib.dev_environment import worker_python


class WorkerProtocolTests(unittest.TestCase):
    def test_progress_bridge_preserves_zero_eta_and_omits_missing_eta(self):
        progress, _, _ = _make_callbacks("eta-task", lambda: False)
        for value, expected in [(0, "0"), (0.0, "0.0"), (None, None), ("", None)]:
            with self.subTest(value=value), patch("vntext_worker.task_runners.emit_progress") as emit_progress:
                progress({"done": 1, "total": 1, "eta": value})
                self.assertEqual(emit_progress.call_args.kwargs["eta"], expected)

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

    def test_cancel_ack_is_separate_from_terminal_completion(self):
        with patch("vntext_worker.protocol.emit") as emit_message:
            emit_cancel_ack("cancel-fixture", "accepted")
        emit_message.assert_called_once_with({
            "type": "cancel_ack", "id": "cancel-fixture", "state": "accepted"
        })

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

    def test_extract_status_reaches_real_protocol_emitter(self):
        import io
        from contextlib import redirect_stdout

        output = io.StringIO()
        with redirect_stdout(output):
            _progress, _log, complete = _make_callbacks("extract-task", lambda: False)
            complete({"ok": False, "complete": False, "extract_status": "PARTIAL"})
        event = json.loads(output.getvalue())
        self.assertEqual("PARTIAL", event["extract_status"])
        self.assertFalse(event["complete"])
        self.assertFalse(event["ok"])

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
    def test_ct2_preload_runs_on_main_thread_and_failure_is_recorded(self):
        prior_error = worker_main._CT2_PRELOAD_ERROR
        try:
            def import_on_main_thread(module_name):
                self.assertEqual("ctranslate2", module_name)
                self.assertIs(threading.current_thread(), threading.main_thread())
                return object()

            with patch.object(worker_main.importlib, "import_module", side_effect=import_on_main_thread):
                worker_main._preload_ct2_runtime()
            self.assertEqual("", worker_main._CT2_PRELOAD_ERROR)

            with patch.object(
                worker_main.importlib,
                "import_module",
                side_effect=ModuleNotFoundError("No module named 'ctranslate2'"),
            ):
                worker_main._preload_ct2_runtime()
            self.assertIn("ModuleNotFoundError", worker_main._CT2_PRELOAD_ERROR)
            self.assertIn("No module named", worker_main._CT2_PRELOAD_ERROR)
        finally:
            worker_main._CT2_PRELOAD_ERROR = prior_error

    def test_extract_does_not_initialize_ct2_before_ocr(self):
        command = {"type": "run", "id": "ocr-only", "task": "extract", "params": {}}
        dispatched = threading.Event()
        with patch.object(worker_main, "_preload_ct2_runtime"), patch.object(worker_main, "emit_ready"), patch.object(
            worker_main, "read_commands", return_value=iter([command])
        ), patch.object(worker_main, "_ensure_ct2_ready") as initialize_ct2, patch.object(
            worker_main, "_dispatch", side_effect=lambda *_args: dispatched.set()
        ):
            self.assertEqual(0, worker_main.main())
            self.assertTrue(dispatched.wait(2), "extract task dispatch did not complete in the test")
        initialize_ct2.assert_not_called()

    def test_cancel_is_read_while_ct2_initialization_is_slow(self):
        entered = threading.Event()
        release = threading.Event()
        acknowledged = threading.Event()
        completed = threading.Event()
        logs: list[str] = []
        progress: list[dict] = []
        lifecycle: list[str] = []

        def preload():
            lifecycle.append("preload")

        def ready():
            lifecycle.append("ready")

        def commands():
            yield {"type": "run", "id": "slow-translate", "task": "translate", "params": {"model": "ct2"}}
            self.assertTrue(entered.wait(3), "model initialization did not start")
            yield {"type": "cancel", "id": "slow-translate"}
            release.set()

        def initialize(*_args):
            entered.set()
            self.assertTrue(release.wait(3), "command loop did not read cancel while model initialization was blocked")

        with patch.object(worker_main, "_preload_ct2_runtime", side_effect=preload), patch.object(
            worker_main, "emit_ready", side_effect=ready
        ), patch.object(
            worker_main, "read_commands", side_effect=commands
        ), patch.object(worker_main, "_ensure_ct2_ready", side_effect=initialize), patch.object(
            worker_main, "_dispatch"
        ) as dispatch, patch.object(
            worker_main, "emit_cancel_ack", side_effect=lambda *_args: acknowledged.set()
        ), patch.object(
            worker_main, "emit_error"
        ) as emit_error, patch.object(
            worker_main, "emit_complete", side_effect=lambda *_args, **_kwargs: completed.set()
        ) as emit_complete, patch.object(
            worker_main, "emit_log", side_effect=lambda _task_id, text: logs.append(text)
        ), patch.object(
            worker_main, "emit_progress", side_effect=lambda _task_id, **fields: progress.append(fields)
        ):
            self.assertEqual(0, worker_main.main())
            self.assertTrue(acknowledged.wait(2), "cancel acknowledgement was not emitted promptly")
            self.assertTrue(completed.wait(2), "cancel during initialization did not reach a terminal outcome")

        dispatch.assert_not_called()
        emit_error.assert_not_called()
        emit_complete.assert_called_once_with("slow-translate", ok=False, error="cancelled during model initialization")
        self.assertTrue(any("Đang kiểm tra trạng thái mô hình" in line for line in logs))
        self.assertTrue(any(item["step"] == "Đang kiểm tra mô hình dịch offline…" for item in progress))
        self.assertEqual(["preload", "ready"], lifecycle)

    def test_ct2_preload_failure_keeps_worker_ready_and_reports_clear_translation_error(self):
        dispatched = threading.Event()
        lifecycle: list[str] = []

        def preload_failure():
            lifecycle.append("preload")
            worker_main._CT2_PRELOAD_ERROR = "ImportError: missing runtime"

        def ready():
            lifecycle.append("ready")

        try:
            for task in ("extract", "patch"):
                dispatched.clear()
                command = {"type": "run", "id": f"{task}-after-ct2-error", "task": task, "params": {}}
                with patch.object(worker_main, "_preload_ct2_runtime", side_effect=preload_failure), patch.object(
                    worker_main, "emit_ready", side_effect=ready
                ), patch.object(worker_main, "read_commands", return_value=iter([command])), patch.object(
                    worker_main, "_dispatch", side_effect=lambda *_args: dispatched.set()
                ):
                    self.assertEqual(0, worker_main.main())
                    self.assertTrue(dispatched.wait(2), f"{task} must still dispatch when optional CT2 runtime is absent")

            logs: list[str] = []
            with patch("vntext_worker.worker_main.emit_log", side_effect=lambda _task, message: logs.append(message)), patch(
                "vntext.mt_ct2.model_status"
            ) as model_status:
                with self.assertRaisesRegex(RuntimeError, "ImportError: missing runtime"):
                    worker_main._ensure_ct2_ready("missing-ct2")
            model_status.assert_not_called()
            self.assertTrue(any("CT2_PRELOAD_ERROR" in line for line in logs))
            self.assertEqual(["preload", "ready", "preload", "ready"], lifecycle)
        finally:
            worker_main._CT2_PRELOAD_ERROR = ""

    def test_ct2_initialization_reports_model_load_boundaries(self):
        logs: list[str] = []
        progress: list[dict] = []
        with patch("vntext.mt_ct2.model_status", return_value={"ready": True}), patch(
            "vntext.mt_ct2.get_translator"
        ) as get_translator, patch.object(
            worker_main, "emit_log", side_effect=lambda _task_id, text: logs.append(text)
        ), patch.object(
            worker_main, "emit_progress", side_effect=lambda _task_id, **fields: progress.append(fields)
        ):
            worker_main._ensure_ct2_ready("model-boundaries")

        get_translator.assert_called_once_with()
        self.assertEqual(1, len(progress))
        self.assertEqual("Đang nạp mô hình dịch offline…", progress[0]["step"])
        before = next(line for line in logs if line.startswith("CT2_INIT_BEFORE model_status:"))
        after = next(line for line in logs if line.startswith("CT2_INIT_AFTER model_status:"))
        self.assertIn("executable", before)
        self.assertIn("sys_path", before)
        self.assertIn("worker_module", before)
        self.assertIn("model_status_module", before)
        self.assertIn("vntext_localappdata", before)
        self.assertIn("elapsed_ms=", after)
        self.assertTrue(any("đang nạp bộ dịch offline" in line for line in logs))
        self.assertTrue(any("Đã nạp xong bộ dịch offline." in line for line in logs))

    def test_cancel_after_model_status_skips_translator_load(self):
        logs: list[str] = []
        with patch("vntext.mt_ct2.model_status", return_value={"ready": True}), patch(
            "vntext.mt_ct2.get_translator"
        ) as get_translator, patch.object(
            worker_main, "emit_log", side_effect=lambda _task_id, text: logs.append(text)
        ), patch.object(
            worker_main, "emit_progress"
        ):
            initialized = worker_main._ensure_ct2_ready("cancel-after-status", lambda: True)

        self.assertFalse(initialized)
        get_translator.assert_not_called()
        self.assertTrue(any("hủy sau khi kiểm tra model" in line for line in logs))

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
            worker_main, "_ensure_ct2_ready", side_effect=lambda *_args: calls.append("ct2-init")
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
        py = worker_python()
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
        py = worker_python()
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
