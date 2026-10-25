"""Python worker entry — JSON stdin/stdout, long-lived process."""
from __future__ import annotations

import importlib
import sys
import threading
import time
from typing import Any

from vntext_worker.protocol import (
    emit_cancel_ack,
    emit_complete,
    emit_error,
    emit_log,
    emit_progress,
    emit_ready,
    read_commands,
)
from vntext_worker.sample_worker import run_sample_task
from vntext_worker.task_runners import (
    run_analyze_worker,
    run_extract_worker,
    run_patch_worker,
    run_translate_worker,
)


_CT2_PRELOAD_ERROR = ""


def _preload_ct2_runtime() -> None:
    """Load CT2 on the worker's main thread before tasks use the Python API.

    CT2's native runtime can stall when the first import happens inside the
    background task thread on some Windows setups. Keep the dependency optional
    for extract/patch tasks: store a clear readiness error and still start the
    JSON worker if import fails.
    """
    global _CT2_PRELOAD_ERROR
    try:
        importlib.import_module("ctranslate2")
    except Exception as exc:
        _CT2_PRELOAD_ERROR = f"{type(exc).__name__}: {exc}"
    else:
        _CT2_PRELOAD_ERROR = ""


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
        elif task in {"image_batch", "image_inventory", "image_extract", "image_render", "image_delivery", "image_apply", "image_rollback"}:
            from vntext_worker.image_tasks import run_image_worker
            run_image_worker(task_id, task, params, is_cancelled)
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


def _prepare_and_dispatch(task_id: str, task: str, params: dict[str, Any], cancel_event: threading.Event) -> None:
    # Model loading can be slow. The CT2 Python module is preloaded on the main
    # thread at startup; keep model/file initialization inside this single-flight
    # task thread so the command loop can still accept cancel/ping.
    if task in {"translate", "image_batch"}:
        try:
            emit_log(task_id, "Đang kiểm tra trạng thái mô hình CTranslate2…")
            emit_progress(task_id, done=0, total=0, step="Đang kiểm tra mô hình dịch offline…")
            ct2_initialized = _ensure_ct2_ready(task_id, cancel_event.is_set)
        except Exception as exc:
            if task != "image_batch":
                message = str(exc)
                emit_error(task_id, message)
                emit_complete(task_id, ok=False, error=message)
                return
            # Image OCR remains useful without CT2; the image runner records the
            # concrete model failure only if translation was explicitly asked.
    if task == "translate" and (cancel_event.is_set() or ct2_initialized is False):
        emit_complete(task_id, ok=False, error="cancelled during model initialization")
        return
    emit_log(task_id, f"Đã sẵn sàng chạy tác vụ {task}.")
    if task == "translate":
        emit_progress(task_id, done=0, total=0, step="Đang chuẩn bị dịch…")
    _dispatch(task_id, task, params, cancel_event)


def _ensure_ct2_ready(task_id: str = "", is_cancelled=None) -> bool:
    """Initialize CT2 in the serialized task thread before its workflow starts."""
    import os

    if _CT2_PRELOAD_ERROR:
        message = (
            "Không nạp được runtime CTranslate2 "
            f"({_CT2_PRELOAD_ERROR}); Dịch tự động đang bị khóa."
        )
        if task_id:
            emit_log(task_id, f"CT2_PRELOAD_ERROR {message}")
        raise RuntimeError(message)

    from vntext.mt_ct2 import get_translator, model_status

    if task_id:
        runtime = {
            "pid": os.getpid(),
            "argv": sys.argv,
            "executable": sys.executable,
            "prefix": sys.prefix,
            "base_prefix": sys.base_prefix,
            "sys_path": sys.path,
            "worker_module": __file__,
            "model_status_module": getattr(model_status, "__module__", ""),
            "cwd": os.getcwd(),
            "pythonhome": os.environ.get("PYTHONHOME", ""),
            "pythonpath": os.environ.get("PYTHONPATH", ""),
            "localappdata": os.environ.get("LOCALAPPDATA", ""),
            "vntext_localappdata": os.environ.get("VNTEXT_LOCALAPPDATA", ""),
            "worker_cwd": os.environ.get("VNTEXT_WORKER_CWD", ""),
            "worker_python": os.environ.get("VNTEXT_WORKER_PYTHON", ""),
            "model_dir_env": os.environ.get("VNTEXT_MODEL_DIR", "") or os.environ.get("VNTEXT_CT2_MODEL", ""),
        }
        emit_log(task_id, f"CT2_INIT_BEFORE model_status: {runtime}")
    started = time.monotonic()
    try:
        if task_id:
            status = model_status(progress_callback=lambda message: emit_log(task_id, f"CT2_INIT_MODEL_STATUS {message}"))
        else:
            status = model_status()
    except Exception as exc:
        elapsed_ms = round((time.monotonic() - started) * 1000)
        if task_id:
            emit_log(task_id, f"CT2_INIT_MODEL_STATUS_ERROR elapsed_ms={elapsed_ms} {type(exc).__name__}: {exc}")
        raise
    elapsed_ms = round((time.monotonic() - started) * 1000)
    if task_id:
        emit_log(
            task_id,
            "CT2_INIT_AFTER model_status: "
            f"elapsed_ms={elapsed_ms} ready={status.get('ready')} "
            f"runtime_ready={status.get('runtime_ready')} version={status.get('runtime_version')} "
            f"path={status.get('path')} message={status.get('message')}",
        )
    if not status.get("ready"):
        raise RuntimeError(status.get("message") or "Model CTranslate2 chưa sẵn sàng")
    if is_cancelled is not None and is_cancelled():
        if task_id:
            emit_log(task_id, "Đã nhận yêu cầu hủy sau khi kiểm tra model; bỏ qua nạp bộ dịch.")
        return False
    if task_id:
        emit_log(task_id, "Mô hình đã có; đang nạp bộ dịch offline…")
        emit_progress(task_id, done=0, total=0, step="Đang nạp mô hình dịch offline…")
    get_translator()
    if task_id:
        emit_log(task_id, "Đã nạp xong bộ dịch offline.")
    return True


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
    _preload_ct2_runtime()
    emit_ready()
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
                emit_cancel_ack(cid or active_id, "accepted")
            else:
                emit_cancel_ack(cid, "stale")
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
        emit_log(task_id, f"Đã nhận tác vụ {task}.")
        active_id = task_id
        active_cancel = threading.Event()
        active_thread = threading.Thread(
            target=_prepare_and_dispatch,
            args=(task_id, task, params, active_cancel),
            daemon=True,
        )
        active_thread.start()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
