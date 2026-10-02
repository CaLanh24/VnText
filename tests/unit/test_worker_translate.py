"""Worker translate tests — CTranslate2 OPUS-MT en→vi (milestone 3)."""

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
import os
import subprocess
import tempfile
import time
import unittest
from unittest.mock import MagicMock, patch
from pathlib import Path

from vntext_worker.protocol import PROTOCOL_VERSION
from work_paths import work_temp_dir


WORK = work_temp_dir("worker_translate")
DEV_RUN_ROOT = Path(os.environ.get("VNTEXT_DEV_RUN_ROOT", str(ROOT / "DEV_RUN"))).expanduser()
MODEL_DIR = DEV_RUN_ROOT / "cache" / "models" / "opus-mt-en-vi-int8"


def _venv_python() -> Path:
    override = os.environ.get("VNTEXT_WORKER_PYTHON", "").strip()
    return Path(override) if override else ROOT / ".venv" / "Scripts" / "python.exe"


def _start_worker(extra_env: dict | None = None) -> subprocess.Popen:
    py = _venv_python()
    if not py.is_file():
        raise unittest.SkipTest("venv python missing")
    env = os.environ.copy()
    env.setdefault("TRANSFORMERS_OFFLINE", "1")
    env.setdefault("HF_HUB_OFFLINE", "1")
    env.setdefault("OMP_NUM_THREADS", "1")
    env.setdefault("VNTEXT_CT2_MODEL", str(MODEL_DIR))
    env.setdefault("VNTEXT_CT2_NO_DOWNLOAD", "1")
    if extra_env:
        env.update(extra_env)
    return subprocess.Popen(
        [str(py), "-u", "-m", "vntext_worker.worker_main"],
        cwd=str(ROOT),
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        encoding="utf-8",
        env=env,
    )


def _read_ready(proc: subprocess.Popen) -> None:
    assert proc.stdout is not None
    line = proc.stdout.readline().strip()
    msg = json.loads(line)
    if msg.get("type") != "ready":
        raise AssertionError(f"expected ready, got {line}")


def _run_task(proc: subprocess.Popen, task_id: str, task: str, params: dict, timeout: float = 120) -> dict:
    assert proc.stdin is not None and proc.stdout is not None
    proc.stdin.write(
        json.dumps({"v": PROTOCOL_VERSION, "type": "run", "id": task_id, "task": task, "params": params})
        + "\n"
    )
    proc.stdin.flush()
    deadline = time.time() + timeout
    while time.time() < deadline:
        line = proc.stdout.readline()
        if not line:
            break
        msg = json.loads(line)
        if msg.get("type") == "complete" and msg.get("id") == task_id:
            return msg
    raise AssertionError(f"timeout waiting complete for {task_id}")


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


def _write_csv(path: Path, rows: list[dict]) -> None:
    fields = [
        "key", "source_text", "translation", "context", "file_path",
        "object_info", "import_method", "safety", "backend", "byte_limit", "patch_note",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields, lineterminator="\r\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({name: row.get(name, "") for name in fields})


class WorkerTranslateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not (MODEL_DIR / "model.bin").is_file():
            raise RuntimeError(f"pre-provisioned OPUS-MT INT8 model is missing: {MODEL_DIR}")

    def setUp(self):
        WORK.mkdir(parents=True, exist_ok=True)

    def test_translate_success(self):
        src = WORK / "success_src"
        src.mkdir(parents=True, exist_ok=True)
        (src / "sample.txt").write_text("NPC: Hello there\n", encoding="utf-8")
        out = WORK / "success_pkg"

        proc = _start_worker()
        try:
            _read_ready(proc)
            extract = _run_task(
                proc,
                "tr-extract",
                "extract",
                {
                    "src": str(src),
                    "out": str(out),
                    "mode": "deep",
                    "level": "balanced",
                    "separate_review": True,
                },
            )
            self.assertTrue(extract.get("ok"), extract.get("error"))

            translate = _run_task(proc, "tr-translate", "translate", {"out": str(out)}, timeout=90)
            self.assertTrue(translate.get("ok"), translate.get("error"))
            self.assertTrue(translate.get("complete"), translate)
            self.assertTrue(translate.get("pipeline_liveness"), translate)
            self.assertEqual(translate.get("pending"), 0)
            self.assertEqual(translate.get("review_only"), 0)
            self.assertGreater(translate.get("translated", 0), 0)

            csv_path = out / "translation.csv"
            with csv_path.open(encoding="utf-8-sig", newline="") as fh:
                rows = list(csv.DictReader(fh))
            self.assertTrue(any(str(r.get("translation") or "").strip() for r in rows))
        finally:
            _stop_worker(proc)

    def test_translate_cancel(self):
        src = WORK / "cancel_src"
        out = WORK / "cancel_pkg"
        rows = [
            {
                "key": f"k{i}",
                "source_text": f"NPC line {i}: Hello traveler",
                "translation": "",
                "context": "line:1",
                "file_path": "sample.txt",
                "import_method": "plain_text_line",
                "safety": "safe",
                "backend": "plain_text",
            }
            for i in range(12)
        ]
        _write_csv(out / "translation.csv", rows)
        (out / "manifest.json").write_text('{"entries":[]}', encoding="utf-8")

        proc = _start_worker({"VNTEXT_CT2_TEST_DELAY_MS": "250"})
        try:
            assert proc.stdin is not None
            _read_ready(proc)
            proc.stdin.write(
                json.dumps(
                    {
                        "v": PROTOCOL_VERSION,
                        "type": "run",
                        "id": "tr-cancel",
                        "task": "translate",
                        "params": {"out": str(out)},
                    }
                )
                + "\n"
            )
            proc.stdin.flush()
            time.sleep(0.35)
            proc.stdin.write(json.dumps({"v": PROTOCOL_VERSION, "type": "cancel", "id": "tr-cancel"}) + "\n")
            proc.stdin.flush()
            deadline = time.time() + 20
            msg = None
            while time.time() < deadline:
                line = proc.stdout.readline()
                if not line:
                    break
                parsed = json.loads(line)
                if parsed.get("type") == "complete" and parsed.get("id") == "tr-cancel":
                    msg = parsed
                    break
            self.assertIsNotNone(msg)
            self.assertFalse(msg.get("ok", True))
            self.assertIn("cancel", (msg.get("error") or "").lower())
        finally:
            _stop_worker(proc)

    def test_translate_model_error(self):
        out = WORK / "model_err_pkg"
        _write_csv(
            out / "translation.csv",
            [{
                "key": "k1",
                "source_text": "Hello",
                "translation": "",
                "context": "line:1",
                "file_path": "x.txt",
            }],
        )
        proc = _start_worker(
            {
                "VNTEXT_CT2_MODEL": str(WORK / "missing_model"),
                "VNTEXT_CT2_NO_DOWNLOAD": "1",
            }
        )
        try:
            _read_ready(proc)
            msg = _run_task(proc, "tr-model", "translate", {"out": str(out)}, timeout=20)
            self.assertFalse(msg.get("ok", True))
            self.assertTrue(msg.get("error"))
        finally:
            _stop_worker(proc)

    def test_translate_complete_false_when_review_only_exists(self):
        out = WORK / "review_pkg"
        _write_csv(
            out / "translation.csv",
            [{
                "key": "k1",
                "source_text": "Hello",
                "translation": "Xin chào",
                "context": "line:1",
                "file_path": "x.txt",
                "import_method": "plain_text_line",
                "safety": "safe",
                "backend": "plain_text",
            }],
        )
        _write_csv(
            out / "review_only.csv",
            [{
                "key": "k_rev",
                "source_text": "{HARD}=blocked tag",
                "translation": "",
                "context": "line:2",
                "file_path": "x.txt",
                "import_method": "plain_text_line",
                "safety": "review",
                "backend": "plain_text",
            }],
        )
        (out / "manifest.json").write_text('{"entries":[]}', encoding="utf-8")

        proc = _start_worker()
        try:
            _read_ready(proc)
            msg = _run_task(proc, "tr-review", "translate", {"out": str(out)}, timeout=20)
            # Còn review_only → complete=false; không có tiến độ mới → ok=false (không PASS giả).
            self.assertFalse(msg.get("complete", True))
            self.assertEqual(msg.get("pending"), 0)
            self.assertEqual(msg.get("review_only"), 1)
            self.assertEqual(msg.get("translated"), 1)
            self.assertFalse(msg.get("ok", True), msg.get("error"))
            self.assertIn("dịch", (msg.get("error") or msg.get("summary") or "").lower())
        finally:
            _stop_worker(proc)

    def test_retranslate_completion_is_not_success_when_post_validation_is_blocked(self):
        from vntext.app_tasks import run_translate_keys_ct2_task

        events: list[dict] = []
        logs: list[str] = []
        with patch(
            "vntext.app_tasks.run_ct2_translate_keys",
            return_value={"ok": True, "applied": 1, "blocked": 0, "summary": "Dịch lại: applied=1"},
        ), patch(
            "vntext.csv_editor_api.validate_document",
            return_value={
                "summary": "Hợp lệ 1, bị chặn 1",
                "reason_counts": {"review_only": 1},
                "patch_eligible": 1,
                "patch_blocked": 1,
            },
        ):
            run_translate_keys_ct2_task(
                WORK / "review_pkg" / "translation.csv",
                WORK / "review_pkg",
                ["k1"],
                progress=lambda _event: None,
                log=logs.append,
                complete=events.append,
            )

        self.assertEqual(len(events), 1)
        self.assertFalse(events[0]["ok"])
        self.assertFalse(events[0]["complete"])
        self.assertEqual(events[0]["review_only"], 1)
        self.assertIn("còn dòng cần xem lại", events[0]["error"])

    def test_retranslate_completion_keeps_unrelated_synonym_pending(self):
        """A key-scoped retry cannot promote unresolved package rows."""

        from vntext.app_tasks import run_translate_keys_ct2_task

        events: list[dict] = []
        with tempfile.TemporaryDirectory(prefix="vntext-retranslate-pending-") as name:
            package = Path(name)
            csv_path = package / "translation.csv"
            fields = ["key", "source_text", "translation", "context", "file_path"]
            with csv_path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=fields)
                writer.writeheader()
                writer.writerow(
                    {
                        "key": "synonym-row",
                        "source_text": "one,two",
                        "translation": "",
                        "context": "",
                        "file_path": "_synonyms.txt",
                    }
                )

            with patch(
                "vntext.app_tasks._run_traced_translation",
                return_value={"ok": True, "applied": 1, "blocked": 0, "summary": "Dịch lại: applied=1"},
            ), patch(
                "vntext.csv_editor_api.validate_document",
                return_value={"reason_counts": {}, "patch_eligible": 1, "patch_blocked": 0},
            ):
                run_translate_keys_ct2_task(
                    csv_path,
                    package,
                    ["some-other-key"],
                    progress=lambda _event: None,
                    log=lambda _message: None,
                    complete=events.append,
                )

            self.assertEqual(len(events), 1)
            self.assertFalse(events[0]["ok"])
            self.assertFalse(events[0]["complete"])
            self.assertEqual(events[0]["pending"], 1)
            self.assertIn("pending=1", events[0]["error"])

    def test_retranslate_does_not_clear_persisted_blocked_without_package_proof(self):
        """A key-scoped result cannot erase an earlier package blocker."""

        from vntext.app_tasks import run_translate_keys_ct2_task
        from vntext.mt_ct2_status import snapshot_translate_status, write_translate_status

        events: list[dict] = []
        with tempfile.TemporaryDirectory(prefix="vntext-retranslate-blocked-retain-") as name:
            package = Path(name)
            csv_path = package / "translation.csv"
            _write_csv(
                csv_path,
                [
                    {
                        "key": "blocked-row",
                        "source_text": "Hello traveler",
                        "translation": "Xin chào",
                        "context": "",
                        "file_path": "dialogue.txt",
                    }
                ],
            )
            write_translate_status(package, csv_path, blocked=1)
            (package / "manifest.json").write_text('{"entries":[]}', encoding="utf-8")
            with patch(
                "vntext.app_tasks._run_traced_translation",
                return_value={"ok": True, "applied": 1, "blocked": 0, "summary": "Dịch lại: applied=1"},
            ), patch(
                "vntext.csv_editor_api.validate_document",
                return_value={"reason_counts": {}, "patch_eligible": 1, "patch_blocked": 0},
            ):
                run_translate_keys_ct2_task(
                    csv_path,
                    package,
                    ["blocked-row"],
                    progress=lambda _event: None,
                    log=lambda _message: None,
                    complete=events.append,
                )

            persisted = snapshot_translate_status(package, csv_path)

        self.assertEqual(len(events), 1)
        self.assertFalse(events[0]["ok"])
        self.assertFalse(events[0]["complete"])
        self.assertEqual(events[0]["blocked"], 1)
        self.assertEqual(persisted["blocked"], 1)

    def test_retranslate_clears_blocked_after_package_wide_validation(self):
        """A complete package validation is the only retry clear proof."""

        from vntext.app_tasks import run_translate_keys_ct2_task
        from vntext.mt_ct2_status import snapshot_translate_status, write_translate_status

        events: list[dict] = []
        with tempfile.TemporaryDirectory(prefix="vntext-retranslate-blocked-clear-") as name:
            package = Path(name)
            csv_path = package / "translation.csv"
            _write_csv(
                csv_path,
                [
                    {
                        "key": "blocked-row",
                        "source_text": "Hello traveler",
                        "translation": "Xin chào",
                        "context": "",
                        "file_path": "dialogue.txt",
                    }
                ],
            )
            write_translate_status(package, csv_path, blocked=1)
            (package / "manifest.json").write_text('{"entries":[]}', encoding="utf-8")
            with patch(
                "vntext.app_tasks._run_traced_translation",
                return_value={"ok": True, "applied": 1, "blocked": 0, "summary": "Dịch lại: applied=1"},
            ), patch(
                "vntext.csv_editor_api.validate_document",
                return_value={
                    "ok": True,
                    "reason_counts": {},
                    "patch_eligible": 1,
                    "patch_blocked": 0,
                },
            ):
                run_translate_keys_ct2_task(
                    csv_path,
                    package,
                    ["blocked-row"],
                    progress=lambda _event: None,
                    log=lambda _message: None,
                    complete=events.append,
                )

            persisted = snapshot_translate_status(package, csv_path)

        self.assertEqual(len(events), 1)
        self.assertTrue(events[0]["ok"], events[0])
        self.assertTrue(events[0]["complete"], events[0])
        self.assertEqual(events[0]["blocked"], 0)
        self.assertEqual(persisted["blocked"], 0)

    def test_retranslate_rejects_optimistic_measured_status(self):
        """A caller-supplied zero snapshot cannot bypass the live CSV gate."""

        from vntext.app_tasks import run_translate_keys_ct2_task

        events: list[dict] = []
        with tempfile.TemporaryDirectory(prefix="vntext-retranslate-measured-status-") as name:
            package = Path(name)
            csv_path = package / "translation.csv"
            _write_csv(
                csv_path,
                [
                    {
                        "key": "pending-row",
                        "source_text": "one,two",
                        "translation": "",
                        "context": "",
                        "file_path": "_synonyms.txt",
                    }
                ],
            )
            (package / "manifest.json").write_text('{"entries":[]}', encoding="utf-8")
            with patch(
                "vntext.app_tasks._run_traced_translation",
                return_value={"ok": True, "applied": 1, "blocked": 0, "summary": "Dịch lại: applied=1"},
            ), patch(
                "vntext.csv_editor_api.validate_document",
                return_value={"reason_counts": {}, "patch_eligible": 1, "patch_blocked": 0},
            ), patch(
                "vntext.mt_ct2_status.snapshot_translate_status",
                return_value={"pending": 0, "review_only": 0, "blocked": 0, "translated": 1},
            ):
                run_translate_keys_ct2_task(
                    csv_path,
                    package,
                    ["pending-row"],
                    progress=lambda _event: None,
                    log=lambda _message: None,
                    complete=events.append,
                )

        self.assertEqual(len(events), 1)
        self.assertFalse(events[0]["ok"])
        self.assertFalse(events[0]["complete"])
        self.assertIn("không khớp", events[0]["error"])

    def test_retranslate_invalid_blocked_count_fails_closed(self):
        """Negative backend counts must not be coerced into completion."""

        from vntext.app_tasks import run_translate_keys_ct2_task

        events: list[dict] = []
        with tempfile.TemporaryDirectory(prefix="vntext-retranslate-invalid-count-") as name:
            package = Path(name)
            csv_path = package / "translation.csv"
            _write_csv(
                csv_path,
                [
                    {
                        "key": "row",
                        "source_text": "Hello traveler",
                        "translation": "Xin chào",
                        "context": "",
                        "file_path": "dialogue.txt",
                    }
                ],
            )
            (package / "manifest.json").write_text('{"entries":[]}', encoding="utf-8")
            with patch(
                "vntext.app_tasks._run_traced_translation",
                return_value={"ok": True, "applied": 1, "blocked": -1, "summary": "Dịch lại: applied=1"},
            ), patch(
                "vntext.csv_editor_api.validate_document",
                return_value={"reason_counts": {}, "patch_eligible": 1, "patch_blocked": 0},
            ):
                run_translate_keys_ct2_task(
                    csv_path,
                    package,
                    ["row"],
                    progress=lambda _event: None,
                    log=lambda _message: None,
                    complete=events.append,
                )

        self.assertEqual(len(events), 1)
        self.assertFalse(events[0]["ok"])
        self.assertFalse(events[0]["complete"])
        self.assertIn("blocked âm", events[0]["error"])

    def test_retranslate_status_read_retries_without_optimistic_completion(self):
        """A transient status read must not turn a retry into complete=true."""

        from vntext.app_tasks import run_translate_keys_ct2_task

        events: list[dict] = []
        with tempfile.TemporaryDirectory(prefix="vntext-retranslate-status-retry-") as name:
            package = Path(name)
            csv_path = package / "translation.csv"
            _write_csv(
                csv_path,
                [
                    {
                        "key": "pending-row",
                        "source_text": "Hello traveler",
                        "translation": "",
                        "context": "",
                        "file_path": "dialogue.txt",
                    }
                ],
            )
            (package / "manifest.json").write_text('{"entries":[]}', encoding="utf-8")
            status_reads = [
                OSError("transient status read"),
                {"pending": 1, "review_only": 0, "blocked": 0, "translated": 0},
            ]
            with patch(
                "vntext.app_tasks._run_traced_translation",
                return_value={"ok": True, "applied": 1, "blocked": 0, "summary": "Dịch lại: applied=1"},
            ), patch(
                "vntext.csv_editor_api.validate_document",
                return_value={"reason_counts": {}, "patch_eligible": 0, "patch_blocked": 0},
            ), patch(
                "vntext.mt_ct2_status.snapshot_translate_status",
                side_effect=status_reads,
            ):
                run_translate_keys_ct2_task(
                    csv_path,
                    package,
                    ["pending-row"],
                    progress=lambda _event: None,
                    log=lambda _message: None,
                    complete=events.append,
                )

        self.assertEqual(len(events), 1)
        self.assertFalse(events[0]["ok"])
        self.assertFalse(events[0]["complete"])
        self.assertEqual(events[0]["pending"], 1)
        self.assertIn("pending=1", events[0]["error"])

    def test_retranslate_malformed_status_fails_closed_without_overwrite(self):
        """Corrupt persisted status must surface an incomplete callback."""

        from vntext.app_tasks import run_translate_keys_ct2_task

        events: list[dict] = []
        with tempfile.TemporaryDirectory(prefix="vntext-retranslate-status-corrupt-") as name:
            package = Path(name)
            csv_path = package / "translation.csv"
            _write_csv(
                csv_path,
                [
                    {
                        "key": "corrupt-row",
                        "source_text": "Hello traveler",
                        "translation": "",
                        "context": "",
                        "file_path": "dialogue.txt",
                    }
                ],
            )
            (package / "manifest.json").write_text('{"entries":[]}', encoding="utf-8")
            status_path = package / ".mt" / "translate_status.json"
            status_path.parent.mkdir(parents=True)
            status_path.write_text('{"blocked":', encoding="utf-8")
            with patch(
                "vntext.app_tasks._run_traced_translation",
                return_value={"ok": True, "applied": 1, "blocked": 0, "summary": "Dịch lại: applied=1"},
            ), patch(
                "vntext.csv_editor_api.validate_document",
                return_value={"reason_counts": {}, "patch_eligible": 0, "patch_blocked": 0},
            ):
                run_translate_keys_ct2_task(
                    csv_path,
                    package,
                    ["corrupt-row"],
                    progress=lambda _event: None,
                    log=lambda _message: None,
                    complete=events.append,
                )

            self.assertEqual(status_path.read_text(encoding="utf-8"), '{"blocked":')

        self.assertEqual(len(events), 1)
        self.assertFalse(events[0]["ok"])
        self.assertFalse(events[0]["complete"])
        self.assertGreater(events[0]["pending"], 0)
        self.assertGreater(events[0]["review_only"], 0)
        self.assertGreater(events[0]["blocked"], 0)
        self.assertIn("Không đo được trạng thái package", events[0]["error"])

    def test_retranslate_trace_uses_concrete_resolved_model_revision(self):
        from vntext.app_tasks import run_translate_keys_ct2_task

        events: list[dict] = []
        with tempfile.TemporaryDirectory(prefix="vntext-retranslate-model-") as model_temp, tempfile.TemporaryDirectory(
            prefix="vntext-retranslate-package-"
        ) as temp:
            resolved = Path(model_temp)
            package = Path(temp)
            csv_path = package / "translation.csv"
            with patch("vntext.mt_ct2_model.resolve_model_dir", return_value=resolved), patch(
                "vntext.app_tasks._run_traced_translation",
                return_value={"ok": True, "applied": 1, "summary": "Dịch lại: applied=1"},
            ) as traced, patch(
                "vntext.csv_editor_api.validate_document",
                return_value={"reason_counts": {}, "patch_eligible": 1, "patch_blocked": 0},
            ):
                run_translate_keys_ct2_task(
                    csv_path,
                    package,
                    ["k1"],
                    progress=lambda _event: None,
                    log=lambda _message: None,
                    complete=events.append,
                )

        self.assertEqual(len(events), 1)
        self.assertTrue(events[0]["ok"])
        self.assertEqual(traced.call_args.kwargs["model_dir"], str(resolved.resolve()))

    def test_translate_empty_csv(self):
        out = WORK / "empty_pkg"
        out.mkdir(parents=True, exist_ok=True)
        fields = [
            "key", "source_text", "translation", "context", "file_path",
            "object_info", "import_method", "safety", "backend", "byte_limit", "patch_note",
        ]
        with (out / "translation.csv").open("w", encoding="utf-8-sig", newline="") as fh:
            csv.DictWriter(fh, fieldnames=fields, lineterminator="\r\n").writeheader()

        proc = _start_worker()
        try:
            _read_ready(proc)
            msg = _run_task(proc, "tr-empty", "translate", {"out": str(out)}, timeout=20)
            self.assertFalse(msg.get("ok", True))
            self.assertIn("dòng", (msg.get("error") or "").lower())
        finally:
            _stop_worker(proc)

    def test_workflow_extract_translate_patch(self):
        src = WORK / "wf_src"
        src.mkdir(parents=True, exist_ok=True)
        (src / "sample.txt").write_text("NPC: Hello there\n", encoding="utf-8")
        out = WORK / "wf_pkg"

        proc = _start_worker()
        try:
            _read_ready(proc)
            self.assertTrue(
                _run_task(
                    proc,
                    "wf-extract",
                    "extract",
                    {
                        "src": str(src),
                        "out": str(out),
                        "mode": "deep",
                        "level": "balanced",
                        "separate_review": True,
                    },
                ).get("ok")
            )
            self.assertTrue(_run_task(proc, "wf-translate", "translate", {"out": str(out)}, timeout=90).get("ok"))
            patch = _run_task(
                proc,
                "wf-patch",
                "patch",
                {"src": str(src), "out": str(out)},
                timeout=60,
            )
            self.assertTrue(patch.get("ok"), patch.get("error"))
            patched = out / "Patch_Viet_Hoa" / "COPY_TO_GAME_ROOT" / "sample.txt"
            self.assertTrue(patched.is_file())
            self.assertTrue(patched.read_text(encoding="utf-8-sig").strip())
        finally:
            _stop_worker(proc)

    def test_translate_resume_keeps_good_rows(self):
        """Resume: bản dịch tốt giữ nguyên; lần 2 chỉ điền dòng còn trống."""
        out = WORK / "resume_pkg"
        if out.exists():
            import shutil

            shutil.rmtree(out)
        kept = "Bản dịch tốt giữ nguyên — không ghi đè"
        rows = [
            {
                "key": "keep1",
                "source_text": "NPC: Hello there",
                "translation": kept,
                "context": "line:1",
                "file_path": "sample.txt",
                "import_method": "plain_text_line",
                "safety": "safe",
                "backend": "plain_text",
            },
            {
                "key": "blank1",
                "source_text": "NPC: Welcome home",
                "translation": "",
                "context": "line:2",
                "file_path": "sample.txt",
                "import_method": "plain_text_line",
                "safety": "safe",
                "backend": "plain_text",
            },
            {
                "key": "blank2",
                "source_text": "NPC: See you later",
                "translation": "",
                "context": "line:3",
                "file_path": "sample.txt",
                "import_method": "plain_text_line",
                "safety": "safe",
                "backend": "plain_text",
            },
        ]
        _write_csv(out / "translation.csv", rows)
        (out / "manifest.json").write_text('{"entries":[]}', encoding="utf-8")

        # Pass 1: chỉ dịch tối đa 1 dòng trống → còn pending.
        proc = _start_worker({"VNTEXT_CT2_MAX_ROWS": "1"})
        try:
            _read_ready(proc)
            msg1 = _run_task(proc, "tr-resume-1", "translate", {"out": str(out)}, timeout=120)
            self.assertTrue(msg1.get("ok"), msg1.get("error"))
        finally:
            _stop_worker(proc)

        with (out / "translation.csv").open(encoding="utf-8-sig", newline="") as fh:
            mid = {r["key"]: r for r in csv.DictReader(fh)}
        self.assertEqual(mid["keep1"]["translation"], kept)
        filled_mid = sum(
            1 for k in ("blank1", "blank2") if str(mid[k].get("translation") or "").strip()
        )
        self.assertEqual(filled_mid, 1, mid)

        # Pass 2: resume — giữ keep1 + dòng đã dịch; điền nốt blank còn lại.
        proc = _start_worker()
        try:
            _read_ready(proc)
            msg2 = _run_task(proc, "tr-resume-2", "translate", {"out": str(out)}, timeout=120)
            self.assertTrue(msg2.get("ok"), msg2.get("error"))
        finally:
            _stop_worker(proc)

        with (out / "translation.csv").open(encoding="utf-8-sig", newline="") as fh:
            by_key = {r["key"]: r for r in csv.DictReader(fh)}
        self.assertEqual(by_key["keep1"]["translation"], kept)
        self.assertTrue(str(by_key["blank1"].get("translation") or "").strip())
        self.assertTrue(str(by_key["blank2"].get("translation") or "").strip())
        # Không ghi đè bản dịch pass-1 của blank đã điền.
        filled_first = mid["blank1"]["translation"] or mid["blank2"]["translation"]
        key_first = "blank1" if mid["blank1"]["translation"] else "blank2"
        self.assertEqual(by_key[key_first]["translation"], filled_first)


if __name__ == "__main__":
    unittest.main()
