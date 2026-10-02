"""JSON line protocol for C# host ↔ Python worker (stdin/stdout)."""
from __future__ import annotations

import json
import sys
from typing import Any, Iterator

PROTOCOL_VERSION = 1


def emit(message: dict[str, Any]) -> None:
    payload = {"v": PROTOCOL_VERSION, **message}
    line = json.dumps(payload, ensure_ascii=False) + "\n"
    try:
        sys.stdout.write(line)
    except UnicodeEncodeError:
        sys.stdout.buffer.write(line.encode("utf-8", errors="replace"))
    sys.stdout.flush()


def emit_ready() -> None:
    emit({"type": "ready"})


def emit_log(task_id: str, text: str) -> None:
    emit({"type": "log", "id": task_id, "text": text})


def emit_progress(
    task_id: str,
    *,
    done: int,
    total: int,
    step: str = "",
    item: str = "",
    eta: str | None = None,
) -> None:
    msg: dict[str, Any] = {
        "type": "progress",
        "id": task_id,
        "done": done,
        "total": total,
        "step": step,
        "item": item,
    }
    if eta:
        msg["eta"] = eta
    emit(msg)


def emit_complete(
    task_id: str,
    *,
    ok: bool,
    summary: str = "",
    error: str = "",
    complete: bool | None = None,
    pending: int = 0,
    review_only: int = 0,
    blocked: int = 0,
    translated: int = 0,
    applied: int | None = None,
    copied_vi: int | None = None,
    human_review_required_count: int | None = None,
    renpy_sdk_missing: bool | None = None,
    pipeline_liveness: bool | None = None,
    diagnostic_path: str | None = None,
    diagnostic_stage: str | None = None,
    diagnostic_root_cause: str | None = None,
    diagnostic_affected_count: int | None = None,
    diagnostic_action: str | None = None,
    diagnostic_status: str | None = None,
    patch_engine: str | None = None,
    patch_delivery: str | None = None,
    patch_payload_path: str | None = None,
    patch_install_instructions: str | None = None,
) -> None:
    msg: dict[str, Any] = {
        "type": "complete",
        "id": task_id,
        "ok": ok,
        "summary": summary,
        "error": error,
    }
    if complete is not None:
        msg["complete"] = complete
        msg["pending"] = pending
        msg["review_only"] = review_only
        msg["blocked"] = blocked
        msg["translated"] = translated
    if applied is not None:
        msg["applied"] = int(applied)
    if copied_vi is not None:
        msg["copied_vi"] = int(copied_vi)
    if human_review_required_count is not None:
        msg["human_review_required_count"] = int(human_review_required_count)
    if renpy_sdk_missing is not None:
        msg["renpy_sdk_missing"] = bool(renpy_sdk_missing)
    if pipeline_liveness is not None:
        msg["pipeline_liveness"] = bool(pipeline_liveness)
    diagnostic_fields = {
        "diagnostic_path": diagnostic_path,
        "diagnostic_stage": diagnostic_stage,
        "diagnostic_root_cause": diagnostic_root_cause,
        "diagnostic_affected_count": diagnostic_affected_count,
        "diagnostic_action": diagnostic_action,
        "diagnostic_status": diagnostic_status,
    }
    for key, value in diagnostic_fields.items():
        if value is None or value == "":
            continue
        msg[key] = int(value) if key == "diagnostic_affected_count" else value
    patch_fields = {
        "patch_engine": patch_engine,
        "patch_delivery": patch_delivery,
        "patch_payload_path": patch_payload_path,
        "patch_install_instructions": patch_install_instructions,
    }
    for key, value in patch_fields.items():
        if value is not None and value != "":
            msg[key] = value
    emit(msg)


def emit_error(task_id: str, message: str) -> None:
    emit({"type": "error", "id": task_id, "message": message})


def parse_command_line(line: str) -> dict[str, Any] | None:
    """Parse one NDJSON command line; emit protocol errors instead of raising."""
    try:
        data = json.loads(line)
    except json.JSONDecodeError as exc:
        emit_error("", f"Invalid JSON command: {exc}")
        return None
    if not isinstance(data, dict):
        emit_error("", "Command must be a JSON object")
        return None
    if int(data.get("v", 0)) != PROTOCOL_VERSION:
        emit_error(str(data.get("id") or ""), "Unsupported protocol version")
        return None
    return data


def read_commands() -> Iterator[dict[str, Any]]:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        data = parse_command_line(line)
        if data is not None:
            yield data
