"""Shared helpers for worker integration/QA tests."""

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
import queue
import threading
from collections import deque
from pathlib import Path

from vntext_worker.protocol import PROTOCOL_VERSION

WORK_ROOT = ROOT / "TEST_RUN"
GAME_COPY = WORK_ROOT / "game-copy"
DEV_RUN_ROOT = Path(os.environ.get("VNTEXT_DEV_RUN_ROOT", str(ROOT / "DEV_RUN"))).expanduser()
DEV_ENV_ROOT = Path(os.environ.get("VNTEXT_DEV_ENV_ROOT", str(ROOT / ".dev-env"))).expanduser()
MODEL_DIR = DEV_ENV_ROOT / "cache" / "models" / "opus-mt-en-vi-int8"
def venv_python() -> Path:
    override = os.environ.get("VNTEXT_WORKER_PYTHON", "").strip()
    if override:
        return Path(override)
    return ROOT / ".dev-env" / ".venv" / "Scripts" / "python.exe"


def worker_cwd() -> Path:
    override = os.environ.get("VNTEXT_WORKER_CWD", "").strip()
    if override:
        return Path(override)
    return ROOT


def worker_env(extra: dict | None = None) -> dict[str, str]:
    env = os.environ.copy()
    env.setdefault("TRANSFORMERS_OFFLINE", "1")
    env.setdefault("HF_HUB_OFFLINE", "1")
    env.setdefault("OMP_NUM_THREADS", "1")
    env.setdefault("VNTEXT_CT2_MODEL", str(MODEL_DIR))
    env.setdefault("VNTEXT_CT2_NO_DOWNLOAD", "1")
    if extra:
        env.update(extra)
    return env


def start_worker(extra_env: dict | None = None) -> subprocess.Popen:
    py = venv_python()
    if not py.is_file():
        raise RuntimeError("venv python missing")
    return subprocess.Popen(
        [str(py), "-u", "-m", "vntext_worker.worker_main"],
        cwd=str(worker_cwd()),
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        encoding="utf-8",
        env=worker_env(extra_env),
    )


class WorkerReadError(AssertionError):
    """A failed wait retains a bounded tail, including semantic errors."""

    def __init__(self, reason, events):
        self.events = list(events)[-64:]
        super().__init__(reason + "; events=" + json.dumps(self.events, ensure_ascii=True))


def _read_until(proc, matches, timeout, label):
    assert proc.stdout is not None
    if not hasattr(proc, "_worker_lines"):
        lines = queue.Queue(maxsize=128)
        proc._worker_lines = lines
        proc._worker_reader_stop = threading.Event()

        def enqueue(value):
            while not proc._worker_reader_stop.is_set():
                try:
                    lines.put(value, timeout=0.05)
                    return
                except queue.Full:
                    continue

        def pump():
            try:
                while not proc._worker_reader_stop.is_set():
                    line = proc.stdout.readline(8193)
                    if not line:
                        break
                    if len(line) > 8192:
                        enqueue(ValueError("worker event exceeds 8192 characters"))
                        break
                    enqueue(line)
            except (OSError, ValueError) as error:
                enqueue(error)
            finally:
                enqueue(None)

        proc._worker_reader = threading.Thread(target=pump, daemon=True)
        proc._worker_reader.start()
    events = deque(maxlen=64)
    deadline = time.monotonic() + timeout
    while True:
        try:
            line = proc._worker_lines.get(timeout=max(0, deadline - time.monotonic()))
        except queue.Empty:
            raise WorkerReadError("timeout waiting " + label, events)
        if line is None or isinstance(line, Exception):
            raise WorkerReadError(f"worker stream ended waiting {label}: {line}", events)
        try:
            msg = json.loads(line)
        except ValueError as error:
            raise WorkerReadError(f"invalid worker JSON: {error}", events) from error
        events.append(msg)
        # Stream each step before another command or cleanup can lose its evidence.
        encoded = json.dumps(msg, ensure_ascii=True)
        used = getattr(proc, "_worker_evidence_bytes", 0)
        if used + len(encoded.encode("utf-8")) <= 65536:
            print("WORKER_EVENT " + encoded, flush=True)
            proc._worker_evidence_bytes = used + len(encoded.encode("utf-8"))
        if matches(msg):
            print("WORKER_RESULT " + json.dumps({"wait": label, "complete": msg}, ensure_ascii=True), flush=True)
            return list(events)
        if time.monotonic() >= deadline:
            raise WorkerReadError("timeout waiting " + label, events)


def read_ready(proc: subprocess.Popen, timeout: float = 60) -> list[dict]:
    events = _read_until(proc, lambda msg: msg.get("type") == "ready", timeout, "ready")
    return events[:-1]


def run_task(proc: subprocess.Popen, task_id: str, task: str, params: dict, timeout: float = 180,
             *, prerequisites: tuple[dict, ...] = ()) -> list[dict]:
    """Send run command; return all events until matching complete."""
    assert proc.stdin is not None and proc.stdout is not None
    if prerequisites and any(item.get("type") != "complete" or item.get("ok") is not True
                             or (task == "patch" and item.get("complete") is not True)
                             for item in prerequisites):
        raise WorkerReadError("semantic prerequisite failed before " + task, prerequisites)
    print("WORKER_RUN " + json.dumps({"id": task_id, "task": task, "params": params,
                                     "pid": proc.pid, "timeout": timeout}, ensure_ascii=True), flush=True)
    proc.stdin.write(
        json.dumps({"v": PROTOCOL_VERSION, "type": "run", "id": task_id, "task": task, "params": params})
        + "\n"
    )
    proc.stdin.flush()
    return wait_task(proc, task_id, timeout)


def wait_task(proc, task_id, timeout=180):
    """Wait after an explicitly sent command/cancel using the same reader."""
    return _read_until(proc, lambda msg: msg.get("type") == "complete" and msg.get("id") == task_id,
                       timeout, "complete for " + task_id)


def complete_for(events: list[dict], task_id: str) -> dict:
    for msg in events:
        if msg.get("type") == "complete" and msg.get("id") == task_id:
            return msg
    raise AssertionError(f"no complete for {task_id}")


def stop_worker(proc: subprocess.Popen) -> None:
    if hasattr(proc, "_worker_reader_stop"):
        proc._worker_reader_stop.set()
    try:
        proc.terminate()
        proc.wait(timeout=2)
    except Exception:
        proc.kill()
        proc.wait(timeout=2)
    finally:
        if hasattr(proc, "_worker_reader"):
            proc._worker_reader.join(timeout=2)
        for stream in (proc.stdin, proc.stdout, proc.stderr):
            if stream is not None:
                stream.close()


def game_copy_asset() -> Path:
    """Return an explicitly configured external-fixture asset for opt-in E2E tests."""
    configured = str(os.environ.get("VNTEXT_GAME_COPY_ASSET") or "").strip()
    if not configured:
        raise unittest.SkipTest(
            "external Unity fixture is not configured; set VNTEXT_GAME_COPY_ASSET for opt-in E2E"
        )
    candidate = Path(configured).expanduser()
    path = candidate if candidate.is_absolute() else GAME_COPY / candidate
    path = assert_under_work(path)
    if not path.is_file():
        raise unittest.SkipTest(f"configured external fixture asset is missing: {path}")
    return path


def assert_under_work(path: Path) -> Path:
    resolved = path.resolve()
    work = WORK_ROOT.resolve()
    if work not in resolved.parents and resolved != work:
        raise AssertionError(f"path must be under {work}: {resolved}")
    return resolved
