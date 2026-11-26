"""Send (or check) the bug-report channel in a short-lived process, like bug_report_cli, so the UI never waits on the network.

``python -m vntext.report_upload_cli PARAMS.json`` with {"action": "status"} or {"action": "send", "zip": "...", "test": false}; prints one JSON line
{"ok": ..., "message": ...} (status: {"ok": true, "configured": bool}).  The endpoint is never printed.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path


def run(params: dict) -> dict:
    from vntext.report_upload import is_configured, send_report
    action = str(params.get("action") or "")
    if action == "status":
        return {"ok": True, "configured": is_configured()}
    if action == "send":
        return send_report(str(params.get("zip") or ""), test_label=bool(params.get("test")))
    return {"ok": False, "message": "Tham số không hợp lệ."}


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(json.dumps({"ok": False, "message": "usage: report_upload_cli PARAMS.json"}))
        return 2
    try:
        params = json.loads(Path(argv[1]).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        print(json.dumps({"ok": False, "message": f"Không đọc được tham số: {type(exc).__name__}"}, ensure_ascii=False))
        return 2
    try:
        result = run(params if isinstance(params, dict) else {})
    except Exception as exc:  # noqa: BLE001 - report the class, never the endpoint or a raw traceback
        result = {"ok": False, "message": f"Chưa gửi được gói báo lỗi ({type(exc).__name__})."}
    sys.stdout.reconfigure(encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
