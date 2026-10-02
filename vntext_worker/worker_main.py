"""Python worker entry — JSON stdin/stdout, long-lived process."""
from __future__ import annotations

import sys
import threading
from typing import Any

from vntext_worker.protocol import emit_complete, emit_error, emit_ready, read_commands
from vntext_worker.sample_worker import run_sample_task
from vntext_worker.task_runners import (
    run_analyze_worker,
    run_extract_worker,
    run_patch_worker,
    run_translate_worker,
)


def _normalize_params(raw: Any, task_id: str) -> dict[str, Any] | None:
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        msg = "params must be a JSON object"
        emit_error(task_id, msg)
        emit_complete(task_id, ok=False, error=msg)
        return None
    return raw


def _dispatch(task_id: str, task: str, params: dict[str, Any], cancel_event: threading.Event) -> None:
    is_cancelled = cancel_event.is_set
    try:
        if task == "sample":
            run_sample_task(
                task_id,
                steps=int(params.get("steps", 20)),
                delay_ms=int(params.get("delay_ms", 80)),
                is_cancelled=is_cancelled,
            )
        elif task == "extract":
            run_extract_worker(task_id, params, is_cancelled)
        elif task == "analyze":
            run_analyze_worker(task_id, params, is_cancelled)
        elif task == "translate":
            run_translate_worker(task_id, params, is_cancelled)
        elif task == "patch":
            run_patch_worker(task_id, params, is_cancelled)
        else:
            emit_error(task_id, f"Unknown task: {task}")
            emit_complete(task_id, ok=False, error=f"Unknown task: {task}")
    except Exception as exc:
        emit_error(task_id, str(exc))
        emit_complete(task_id, ok=False, error=str(exc))


def _ensure_ct2_on_main_thread() -> None:
    """Init CT2 on the command thread before translate runs in a worker thread."""
    from vntext.mt_ct2 import get_translator, model_status

    status = model_status()
    if not status.get("ready"):
        raise RuntimeError(status.get("message") or "Model CTranslate2 chưa sẵn sàng")
    get_translator()


def _configure_stdio_utf8() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except (OSError, ValueError):
                pass


def main() -> int:
    _configure_stdio_utf8()
    emit_ready()
    # Initialize CT2 synchronously only on the translate command path. Loading
    # the native runtime in a background thread races file I/O in patch/extract
    # tasks on Windows; _ensure_ct2_on_main_thread() still preserves translate
    # readiness semantics.
    active_cancel: threading.Event | None = None
    active_thread: threading.Thread | None = None
    active_id = ""

    for cmd in read_commands():
        ctype = cmd.get("type")
        if ctype == "ping":
            emit_ready()
            continue
        if ctype == "cancel":
            cid = str(cmd.get("id") or "")
            if active_cancel is not None and (not cid or cid == active_id):
                active_cancel.set()
            continue
        if ctype != "run":
            emit_error(str(cmd.get("id") or ""), f"Unknown command type: {ctype}")
            continue

        task_id = str(cmd.get("id") or "")
        task = str(cmd.get("task") or "")
        params = _normalize_params(cmd.get("params"), task_id)
        if params is None:
            continue

        if active_thread is not None and active_thread.is_alive():
            # A task emits its terminal ``complete`` event immediately before
            # returning from the dispatch thread.  The host can therefore
            # submit the next command after reading ``complete`` while the
            # thread is still in its final interpreter instructions.  Give
            # that already-finished task a bounded join before declaring the
            # worker busy; a genuinely active task still keeps the protocol
            # single-flight.
            active_thread.join(timeout=0.5)
        if active_thread is not None and active_thread.is_alive():
            emit_error(task_id, "Worker busy")
            emit_complete(task_id, ok=False, error="Worker busy")
            continue

        if task == "translate":
            model = str(params.get("model") or "ct2").strip().lower()
            if model != "ct2":
                msg = f"Model dịch không được hỗ trợ: {model}; hiện chỉ có CT2/OPUS-MT."
                emit_error(task_id, msg)
                emit_complete(task_id, ok=False, error=msg)
                continue
            try:
                _ensure_ct2_on_main_thread()
            except Exception as exc:
                msg = str(exc)
                emit_error(task_id, msg)
                emit_complete(task_id, ok=False, error=msg)
                continue

        active_id = task_id
        active_cancel = threading.Event()
        active_thread = threading.Thread(
            target=_dispatch,
            args=(task_id, task, params, active_cancel),
            daemon=True,
        )
        active_thread.start()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
