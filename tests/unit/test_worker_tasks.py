"""Tests for extract/patch worker dispatch (milestone 2)."""

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
    tools = cur / "tools"
    p = str(tools)
    if p not in sys.path:
        sys.path.insert(0, p)

_tests_lib_on_path()
from bootstrap import bootstrap
TESTS, ROOT, LIB = bootstrap(__file__)

import csv
import io
import json
import os
import subprocess
import tempfile
import time
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

WORK_ROOT = ROOT / "TEST_RUN"

from vntext_worker.protocol import PROTOCOL_VERSION, parse_command_line
from vntext.entry import Entry
from vntext.package_io import CSV_FIELDS, read_csv_rows_file, write_csv_rows_file, write_package
from cleanup_work_artifacts import cleanup_after_test
from work_paths import ambient_scope, new_scope_id, register_artifact
from vntext_worker.task_runners import run_analyze_worker, run_extract_worker


def _venv_python() -> Path:
    override = os.environ.get("VNTEXT_WORKER_PYTHON", "").strip()
    return Path(override) if override else ROOT / ".dev-env" / ".venv" / "Scripts" / "python.exe"


def _start_worker() -> subprocess.Popen:
    py = _venv_python()
    if not py.is_file():
        raise unittest.SkipTest("venv python missing")
    return subprocess.Popen(
        [str(py), "-u", "-m", "vntext_worker.worker_main"],
        cwd=str(ROOT),
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        encoding="utf-8",
    )


def _read_ready(proc: subprocess.Popen) -> None:
    assert proc.stdout is not None
    line = proc.stdout.readline().strip()
    self_msg = json.loads(line)
    if self_msg.get("type") != "ready":
        raise AssertionError(f"expected ready, got {line}")


def _collect_until(proc: subprocess.Popen, *, task_id: str, want: str, timeout: float = 30) -> dict:
    assert proc.stdout is not None
    deadline = time.time() + timeout
    while time.time() < deadline:
        line = proc.stdout.readline()
        if not line:
            break
        msg = json.loads(line)
        if msg.get("type") == want and (not task_id or msg.get("id") == task_id):
            return msg
    raise AssertionError(f"timeout waiting for {want} on task {task_id}")


def _stop_worker(proc: subprocess.Popen) -> None:
    try:
        proc.terminate()
        proc.wait(timeout=2)
    except Exception:
        proc.kill()
        proc.wait(timeout=2)
    finally:
        for stream in (proc.stdin, proc.stdout, proc.stderr):
            if stream is not None:
                stream.close()


class WorkerParserTests(unittest.TestCase):
    def test_non_object_json_emits_error(self):
        buf = io.StringIO()
        old = sys.stdout
        sys.stdout = buf
        try:
            result = parse_command_line("[1, 2]")
        finally:
            sys.stdout = old
        self.assertIsNone(result)
        out = buf.getvalue().strip()
        self.assertIn("error", out)
        self.assertIn("JSON object", out)

    def test_invalid_json_emits_error(self):
        buf = io.StringIO()
        old = sys.stdout
        sys.stdout = buf
        try:
            result = parse_command_line("{not json")
        finally:
            sys.stdout = old
        self.assertIsNone(result)
        self.assertIn("error", buf.getvalue())


class WorkerMalformedCommandTests(unittest.TestCase):
    def test_params_must_be_object(self):
        proc = _start_worker()
        try:
            assert proc.stdin is not None and proc.stdout is not None
            _read_ready(proc)
            task_id = "bad-params"
            proc.stdin.write(
                json.dumps(
                    {
                        "v": PROTOCOL_VERSION,
                        "type": "run",
                        "id": task_id,
                        "task": "extract",
                        "params": "not-an-object",
                    }
                )
                + "\n"
            )
            proc.stdin.flush()
            msg = _collect_until(proc, task_id=task_id, want="complete", timeout=5)
            self.assertFalse(msg.get("ok", True))
            self.assertIn("object", (msg.get("error") or "").lower())
        finally:
            _stop_worker(proc)

    def test_non_object_command_line_keeps_worker_alive(self):
        proc = _start_worker()
        try:
            assert proc.stdin is not None and proc.stdout is not None
            _read_ready(proc)
            proc.stdin.write("[1,2,3]\n")
            proc.stdin.flush()
            err_line = proc.stdout.readline().strip()
            self.assertIn("error", err_line)
            task_id = "after-bad"
            proc.stdin.write(
                json.dumps(
                    {
                        "v": PROTOCOL_VERSION,
                        "type": "run",
                        "id": task_id,
                        "task": "sample",
                        "params": {"steps": 2, "delay_ms": 20},
                    }
                )
                + "\n"
            )
            proc.stdin.flush()
            msg = _collect_until(proc, task_id=task_id, want="complete", timeout=10)
            self.assertTrue(msg.get("ok"))
        finally:
            _stop_worker(proc)


class WorkerExtractPatchTests(unittest.TestCase):
    def setUp(self):
        self.work = WORK_ROOT / f"worker_tasks_{uuid4().hex}"
        self.work.mkdir(parents=True, exist_ok=True)
        ambient = ambient_scope()
        self.scope_id = (
            ambient["scope_id"]
            if ambient["scope_id"] != "legacy"
            else new_scope_id("worker-tasks")
        )
        self.run_id = (
            ambient["run_id"]
            if ambient["run_id"] != "legacy"
            else new_scope_id("worker-run")
        )
        register_artifact(
            artifact_id=f"worker-tasks:{self.work.name}",
            path=self.work,
            kind="test_workspace",
            created_by="test_worker_tasks.py",
            owner="test_worker_tasks.py",
            purpose="temporary worker dispatch regression outputs",
            lifecycle="DISPOSABLE",
            scope_id=self.scope_id,
            run_id=self.run_id,
        )

    def tearDown(self):
        failed = any(
            test_case is self and error
            for test_case, error in getattr(self._outcome, "errors", [])
        )
        report = cleanup_after_test(
            [self.work],
            reason="test_worker_tasks.py",
            outcome="FAIL" if failed else "PASS",
            scope_id=self.scope_id,
            run_id=self.run_id,
        )
        if not failed and not report.get("ok"):
            self.fail(f"worker test artifact cleanup failed: {report}")

    def test_extract_dispatch_completes(self):
        src = self.work / "extract_src"
        src.mkdir(parents=True, exist_ok=True)
        (src / "sample.txt").write_text("NPC: Hello there\n", encoding="utf-8")
        out = self.work / "extract_out"

        proc = _start_worker()
        try:
            assert proc.stdin is not None
            _read_ready(proc)
            task_id = "extract-1"
            proc.stdin.write(
                json.dumps(
                    {
                        "v": PROTOCOL_VERSION,
                        "type": "run",
                        "id": task_id,
                        "task": "extract",
                        "params": {
                            "src": str(src),
                            "out": str(out),
                            "mode": "deep",
                            "level": "balanced",
                            "separate_review": True,
                        },
                    }
                )
                + "\n"
            )
            proc.stdin.flush()
            msg = _collect_until(proc, task_id=task_id, want="complete", timeout=45)
            self.assertTrue(msg.get("ok"), msg.get("error"))
            self.assertTrue((out / "translation.csv").is_file())
            self.assertTrue((out / "manifest.json").is_file())
        finally:
            _stop_worker(proc)

    def test_analyze_dispatch_writes_report_outside_game(self):
        with tempfile.TemporaryDirectory(prefix="vntext-worker-analyze-") as name:
            game = Path(name) / "SampleVN"
            data = game / "SampleVN_Data" / "StreamingAssets"
            data.mkdir(parents=True)
            (game / "SampleVN.exe").write_bytes(b"MZ fixture")
            (data / "dialogue").write_text("Hello from analyzer\n", encoding="utf-8")
            report_out = Path(name) / "analysis-output"

            proc = _start_worker()
            try:
                assert proc.stdin is not None
                _read_ready(proc)
                task_id = "analyze-1"
                proc.stdin.write(
                    json.dumps(
                        {
                            "v": PROTOCOL_VERSION,
                            "type": "run",
                            "id": task_id,
                            "task": "analyze",
                            "params": {
                                "src": str(game),
                                "report_out": str(report_out),
                                "include_sha256": False,
                                "probe_unity_objects": False,
                            },
                        }
                    )
                    + "\n"
                )
                proc.stdin.flush()
                msg = _collect_until(proc, task_id=task_id, want="complete", timeout=15)
                self.assertTrue(msg.get("ok"), msg.get("error"))
                self.assertIn("DETECTED", msg.get("summary", ""))
                report = json.loads((report_out / "unity_analysis.json").read_text(encoding="utf-8"))
                self.assertTrue(report["inventory_complete"])
                self.assertEqual(report["summary"]["resource_count"], 2)
                self.assertIn("SampleVN_Data/StreamingAssets/dialogue", {item["path"] for item in report["resources"]})
            finally:
                _stop_worker(proc)

    def test_analyze_dispatch_rejects_report_inside_game(self):
        with tempfile.TemporaryDirectory(prefix="vntext-worker-analyze-internal-") as name:
            game = Path(name) / "SampleVN"
            (game / "SampleVN_Data").mkdir(parents=True)
            report_path = game / "unity_analysis.json"

            proc = _start_worker()
            try:
                assert proc.stdin is not None
                _read_ready(proc)
                task_id = "analyze-internal"
                proc.stdin.write(
                    json.dumps(
                        {
                            "v": PROTOCOL_VERSION,
                            "type": "run",
                            "id": task_id,
                            "task": "analyze",
                            "params": {
                                "src": str(game),
                                "report_out": str(report_path),
                                "probe_unity_objects": False,
                            },
                        }
                    )
                    + "\n"
                )
                proc.stdin.flush()
                msg = _collect_until(proc, task_id=task_id, want="complete", timeout=15)
                self.assertFalse(msg.get("ok", True))
                self.assertIn("ngoài thư mục game", msg.get("error", ""))
                self.assertFalse(report_path.exists())
            finally:
                _stop_worker(proc)

    def test_cloud_repair_export_import_and_failed_import_preserves_output(self):
        package = self.work / "cloud_package"
        package.mkdir(parents=True, exist_ok=True)
        row = {field: "" for field in CSV_FIELDS}
        row.update(
            {
                "key": "cloud-worker-key",
                "source_text": "Hello {NAME}",
                "translation": "Xin chào {NAME}",
                "context": "fixture",
                "file_path": "dialogue.txt",
                "import_method": "plain_text_line",
                "safety": "safe",
                "backend": "text",
            }
        )
        write_csv_rows_file(package / "translation.csv", CSV_FIELDS, [row])
        archive = self.work / "cloud-repair.zip"
        result = self.work / "cloud-result.csv"
        active = package / "translation.cloud_repair.csv"
        write_csv_rows_file(package / "translation.csv", CSV_FIELDS, [row])

        proc = _start_worker()
        try:
            assert proc.stdin is not None
            _read_ready(proc)
            proc.stdin.write(
                json.dumps(
                    {
                        "v": PROTOCOL_VERSION,
                        "type": "run",
                        "id": "cloud-export",
                        "task": "patch",
                        "params": {
                            "cloud_action": "export",
                            "package_dir": str(package),
                            "output_zip": str(archive),
                        },
                    }
                )
                + "\n"
            )
            proc.stdin.flush()
            export_msg = _collect_until(proc, task_id="cloud-export", want="complete", timeout=20)
            self.assertTrue(export_msg.get("ok"), export_msg.get("error"))
            self.assertTrue(archive.is_file())
            self.assertTrue((package / ".mt" / "cloud_repair_export_report.json").is_file())

            with zipfile.ZipFile(archive) as zf:
                payload = zf.read("translation.csv").decode("utf-8-sig")
            rows = list(csv.DictReader(io.StringIO(payload, newline="")))
            rows[0]["translation"] = "Xin chào {NAME}!"
            write_csv_rows_file(result, CSV_FIELDS, rows)

            proc.stdin.write(
                json.dumps(
                    {
                        "v": PROTOCOL_VERSION,
                        "type": "run",
                        "id": "cloud-import-ok",
                        "task": "patch",
                        "params": {
                            "cloud_action": "import",
                            "package_zip": str(archive),
                            "result_csv": str(result),
                            "output_csv": str(active),
                        },
                    }
                )
                + "\n"
            )
            proc.stdin.flush()
            import_msg = _collect_until(proc, task_id="cloud-import-ok", want="complete", timeout=20)
            self.assertTrue(import_msg.get("ok"), import_msg.get("error"))
            with active.open(encoding="utf-8-sig", newline="") as handle:
                self.assertEqual(list(csv.DictReader(handle))[0]["translation"], "Xin chào {NAME}!")
            before_failed_import = active.read_bytes()

            rows[0]["source_text"] = "Tampered source"
            write_csv_rows_file(result, CSV_FIELDS, rows)
            proc.stdin.write(
                json.dumps(
                    {
                        "v": PROTOCOL_VERSION,
                        "type": "run",
                        "id": "cloud-import-fail",
                        "task": "patch",
                        "params": {
                            "cloud_action": "import",
                            "package_zip": str(archive),
                            "result_csv": str(result),
                            "output_csv": str(active),
                        },
                    }
                )
                + "\n"
            )
            proc.stdin.flush()
            failed_msg = _collect_until(proc, task_id="cloud-import-fail", want="complete", timeout=20)
            self.assertFalse(failed_msg.get("ok", True))
            self.assertIn("không khớp", (failed_msg.get("error") or "").lower())
            self.assertEqual(before_failed_import, active.read_bytes())
            self.assertTrue((package / ".mt" / "cloud_repair_import_report.json").is_file())
        finally:
            _stop_worker(proc)

    def test_analyze_worker_forwards_progress_and_default_hash_evidence(self):
        game = self.work / "analyze_progress_game"
        game.mkdir()
        (game / "dialogue.txt").write_text("Hello from a synthetic fixture\n", encoding="utf-8")
        (game / "strings.json").write_text('{"hello":"Hello"}', encoding="utf-8")
        report_out = self.work / "analyze_progress_report"
        events: list[dict] = []
        completed: list[dict] = []

        with patch(
            "vntext_worker.task_runners.emit_progress",
            side_effect=lambda _task_id, **info: events.append(info),
        ), patch(
            "vntext_worker.task_runners.emit_complete",
            side_effect=lambda _task_id, **payload: completed.append(payload),
        ), patch("vntext_worker.task_runners.emit_log"), patch("vntext_worker.task_runners.emit_error"):
            run_analyze_worker(
                "analyze-progress",
                {"src": str(game), "report_out": str(report_out), "probe_unity_objects": False},
                lambda: False,
            )

        self.assertTrue(completed and completed[-1]["ok"], completed)
        self.assertTrue({"unity_enumerate", "unity_classify", "unity_hash"}.issubset(
            {event.get("step") for event in events}
        ), events)
        report = json.loads((report_out / "unity_analysis.json").read_text(encoding="utf-8"))
        self.assertTrue(report["summary"]["sha256_enabled"])
        self.assertTrue(all(item["sha256"] for item in report["resources"]))

    def test_analyze_worker_cancel_during_hash_writes_no_partial_report(self):
        game = self.work / "analyze_cancel_game"
        game.mkdir()
        (game / "first.txt").write_text("Hello\n", encoding="utf-8")
        large = game / "large.bin"
        large.write_bytes(b"x" * (12 * 1024 * 1024))
        report_out = self.work / "analyze_cancel_report"
        events: list[dict] = []
        completed: list[dict] = []
        cancelled = False

        def record_progress(_task_id, **info):
            nonlocal cancelled
            events.append(info)
            if info.get("step") == "unity_hash" and int(info.get("done") or 0) >= 1024 * 1024:
                cancelled = True

        with patch("vntext_worker.task_runners.emit_progress", side_effect=record_progress), patch(
            "vntext_worker.task_runners.emit_complete",
            side_effect=lambda _task_id, **payload: completed.append(payload),
        ), patch("vntext_worker.task_runners.emit_log"), patch("vntext_worker.task_runners.emit_error"):
            run_analyze_worker(
                "analyze-cancel",
                {"src": str(game), "report_out": str(report_out), "probe_unity_objects": False},
                lambda: cancelled,
            )

        self.assertTrue(events and any(event.get("step") == "unity_hash" for event in events), events)
        self.assertTrue(completed and not completed[-1]["ok"], completed)
        self.assertEqual(completed[-1]["error"], "cancelled")
        self.assertFalse(report_out.exists(), "cancelled analysis must not retain a partial report")

    def test_extract_worker_forwards_progress_and_cancel_to_preflight(self):
        game = self.work / "extract_cancel_game"
        streaming = game / "SampleVN_Data" / "StreamingAssets"
        streaming.mkdir(parents=True)
        (game / "SampleVN.exe").write_bytes(b"MZ synthetic fixture")
        (streaming / "dialogue.txt").write_text("Hello from a synthetic fixture\n", encoding="utf-8")
        for index in range(40):
            (streaming / f"line-{index:02d}.txt").write_text(f"Hello {index}\n", encoding="utf-8")
        output = self.work / "extract_cancel_package"
        events: list[dict] = []
        completed: list[dict] = []
        cancelled = False

        def record_progress(_task_id, **info):
            nonlocal cancelled
            events.append(info)
            if info.get("step") == "unity_classify":
                cancelled = True

        with patch("vntext_worker.task_runners.emit_progress", side_effect=record_progress), patch(
            "vntext_worker.task_runners.emit_complete",
            side_effect=lambda _task_id, **payload: completed.append(payload),
        ), patch("vntext_worker.task_runners.emit_log"), patch("vntext_worker.task_runners.emit_error"):
            run_extract_worker(
                "extract-cancel",
                {"src": str(game), "out": str(output), "separate_review": True},
                lambda: cancelled,
            )

        steps = {event.get("step") for event in events}
        self.assertIn("unity_classify", steps)
        self.assertNotIn("unity_hash", steps)
        self.assertTrue(completed and not completed[-1]["ok"], completed)
        self.assertEqual(completed[-1]["error"], "cancelled")
        self.assertFalse((output / "unity_analysis.json").exists())
        self.assertFalse((output / "manifest.json").exists())

    def test_external_translation_import_uses_current_package_and_reports_partial_state(self):
        package = self.work / "external-import-package"
        entry = Entry(
            source_text="Hello {NAME}",
            file_path="fixture/dialogue.txt",
            context="external-import",
            import_method="plain_text_line",
            safety="safe",
            locator={"line": 1},
            backend="text",
            patch_proof={"reader": True, "writer": True, "preflight": True, "reopen": True, "semantic_verify": True},
        ).finalize()
        write_package(
            str(package),
            [entry],
            [],
            {"mode": "synthetic", "files_scanned": 1, "main_entries": 1, "review_entries": 0, "errors": []},
            enforce_symmetry=True,
        )
        target = package / "translation.csv"
        _, donor_rows = read_csv_rows_file(target)
        donor_rows[0]["translation"] = "Xin chào {NAME}"
        donor = self.work / "older-translation.csv"
        write_csv_rows_file(donor, CSV_FIELDS, donor_rows)

        proc = _start_worker()
        try:
            assert proc.stdin is not None
            _read_ready(proc)
            proc.stdin.write(
                json.dumps(
                    {
                        "v": PROTOCOL_VERSION,
                        "type": "run",
                        "id": "external-import-ok",
                        "task": "patch",
                        "params": {
                            "cloud_action": "external_import",
                            "target_csv": str(target),
                            "source_csv": str(donor),
                        },
                    }
                )
                + "\n"
            )
            proc.stdin.flush()
            message = _collect_until(proc, task_id="external-import-ok", want="complete", timeout=20)
            self.assertTrue(message.get("ok"), message.get("error"))
            self.assertTrue(message.get("complete"), message)
            self.assertEqual(message.get("applied"), 1)
            with target.open(encoding="utf-8-sig", newline="") as handle:
                self.assertEqual(list(csv.DictReader(handle))[0]["translation"], "Xin chào {NAME}")
            self.assertTrue((package / ".mt" / "external_translation_import_report.json").is_file())
        finally:
            _stop_worker(proc)

    def test_patch_without_translations_fails(self):
        src = self.work / "patch_src"
        src.mkdir(parents=True, exist_ok=True)
        (src / "sample.txt").write_text("NPC: Hello there\n", encoding="utf-8")
        out = self.work / "patch_pkg_empty"

        proc = _start_worker()
        try:
            assert proc.stdin is not None
            _read_ready(proc)
            proc.stdin.write(
                json.dumps(
                    {
                        "v": PROTOCOL_VERSION,
                        "type": "run",
                        "id": "extract-for-patch",
                        "task": "extract",
                        "params": {
                            "src": str(src),
                            "out": str(out),
                            "mode": "deep",
                            "level": "balanced",
                            "separate_review": True,
                        },
                    }
                )
                + "\n"
            )
            proc.stdin.flush()
            extract_msg = _collect_until(proc, task_id="extract-for-patch", want="complete", timeout=45)
            self.assertTrue(extract_msg.get("ok"), extract_msg.get("error"))

            proc.stdin.write(
                json.dumps(
                    {
                        "v": PROTOCOL_VERSION,
                        "type": "run",
                        "id": "patch-empty",
                        "task": "patch",
                        "params": {"src": str(src), "out": str(out)},
                    }
                )
                + "\n"
            )
            proc.stdin.flush()
            patch_msg = _collect_until(proc, task_id="patch-empty", want="complete", timeout=15)
            self.assertFalse(patch_msg.get("ok", True))
            self.assertIn("bản dịch", (patch_msg.get("error") or "").lower())
        finally:
            _stop_worker(proc)

    def test_patch_with_translations_succeeds(self):
        import csv

        src = self.work / "patch_src_ok"
        src.mkdir(parents=True, exist_ok=True)
        (src / "sample.txt").write_text("NPC: Hello there\n", encoding="utf-8")
        out = self.work / "patch_pkg_ok"

        proc = _start_worker()
        try:
            assert proc.stdin is not None
            _read_ready(proc)
            proc.stdin.write(
                json.dumps(
                    {
                        "v": PROTOCOL_VERSION,
                        "type": "run",
                        "id": "extract-ok",
                        "task": "extract",
                        "params": {
                            "src": str(src),
                            "out": str(out),
                            "mode": "deep",
                            "level": "balanced",
                            "separate_review": True,
                        },
                    }
                )
                + "\n"
            )
            proc.stdin.flush()
            self.assertTrue(_collect_until(proc, task_id="extract-ok", want="complete", timeout=45).get("ok"))

            csv_path = out / "translation.csv"
            with csv_path.open("r", encoding="utf-8-sig", newline="") as fh:
                reader = csv.DictReader(fh)
                rows = list(reader)
                fields = reader.fieldnames or []
            rows[0]["translation"] = "NPC: Xin chào"
            with csv_path.open("w", encoding="utf-8-sig", newline="") as fh:
                writer = csv.DictWriter(fh, fieldnames=fields)
                writer.writeheader()
                writer.writerows(rows)

            proc.stdin.write(
                json.dumps(
                    {
                        "v": PROTOCOL_VERSION,
                        "type": "run",
                        "id": "patch-ok",
                        "task": "patch",
                        "params": {"src": str(src), "out": str(out)},
                    }
                )
                + "\n"
            )
            proc.stdin.flush()
            patch_msg = _collect_until(proc, task_id="patch-ok", want="complete", timeout=30)
            self.assertTrue(patch_msg.get("ok"), patch_msg.get("error"))
            patched = out / "Patch_Viet_Hoa" / "COPY_TO_GAME_ROOT" / "sample.txt"
            self.assertTrue(patched.is_file(), f"missing patched file: {patched}")
            self.assertIn("Xin chào", patched.read_text(encoding="utf-8-sig"))
            verification = json.loads(
                (out / "Patch_Viet_Hoa" / "patch_verification.json").read_text(encoding="utf-8")
            )
            self.assertEqual(verification["counts"], {"PASS": 1})
            trace_summary = json.loads(
                (out / ".mt" / "trace_summary.json").read_text(encoding="utf-8")
            )
            self.assertEqual(trace_summary["measurements"]["patch"]["verification"], "PASS")
            self.assertEqual(trace_summary["measurements"]["patch"]["readback_passed_targets"], 1)
            self.assertEqual(trace_summary["stage_counts"], {"READ_BACK_VERIFIED": 1})
        finally:
            _stop_worker(proc)

    def test_patch_dispatch_missing_package_errors(self):
        proc = _start_worker()
        try:
            assert proc.stdin is not None
            _read_ready(proc)
            task_id = "patch-missing"
            proc.stdin.write(
                json.dumps(
                    {
                        "v": PROTOCOL_VERSION,
                        "type": "run",
                        "id": task_id,
                        "task": "patch",
                        "params": {
                            "src": str(self.work / "nope"),
                            "out": str(self.work / "no_package"),
                        },
                    }
                )
                + "\n"
            )
            proc.stdin.flush()
            msg = _collect_until(proc, task_id=task_id, want="complete", timeout=10)
            self.assertFalse(msg.get("ok", True))
            self.assertTrue(msg.get("error"))
        finally:
            _stop_worker(proc)

    def test_sample_cancel_still_works(self):
        proc = _start_worker()
        try:
            assert proc.stdin is not None
            _read_ready(proc)
            task_id = "cancel-1"
            proc.stdin.write(
                json.dumps(
                    {
                        "v": PROTOCOL_VERSION,
                        "type": "run",
                        "id": task_id,
                        "task": "sample",
                        "params": {"steps": 30, "delay_ms": 60},
                    }
                )
                + "\n"
            )
            proc.stdin.flush()
            time.sleep(0.25)
            proc.stdin.write(json.dumps({"v": PROTOCOL_VERSION, "type": "cancel", "id": task_id}) + "\n")
            proc.stdin.flush()
            msg = _collect_until(proc, task_id=task_id, want="complete", timeout=10)
            self.assertFalse(msg.get("ok", True))
        finally:
            _stop_worker(proc)


if __name__ == "__main__":
    unittest.main()
