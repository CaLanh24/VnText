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


def read_ready(proc: subprocess.Popen, timeout: float = 60) -> list[dict]:
    """Read ready line; return any extra log lines emitted before ready."""
    assert proc.stdout is not None
    extras: list[dict] = []
    deadline = time.time() + timeout
    while time.time() < deadline:
        line = proc.stdout.readline()
        if not line:
            break
        msg = json.loads(line)
        if msg.get("type") == "ready":
            return extras
        extras.append(msg)
    raise AssertionError("worker did not emit ready")


def run_task(proc: subprocess.Popen, task_id: str, task: str, params: dict, timeout: float = 180) -> list[dict]:
    """Send run command; return all events until matching complete."""
    assert proc.stdin is not None and proc.stdout is not None
    proc.stdin.write(
        json.dumps({"v": PROTOCOL_VERSION, "type": "run", "id": task_id, "task": task, "params": params})
        + "\n"
    )
    proc.stdin.flush()
    events: list[dict] = []
    deadline = time.time() + timeout
    while time.time() < deadline:
        line = proc.stdout.readline()
        if not line:
            break
        msg = json.loads(line)
        events.append(msg)
        if msg.get("type") == "complete" and msg.get("id") == task_id:
            return events
    raise AssertionError(f"timeout waiting complete for {task_id}")


def complete_for(events: list[dict], task_id: str) -> dict:
    for msg in events:
        if msg.get("type") == "complete" and msg.get("id") == task_id:
            return msg
    raise AssertionError(f"no complete for {task_id}")


def stop_worker(proc: subprocess.Popen) -> None:
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
