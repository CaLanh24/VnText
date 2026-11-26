"""Build the anonymous bug report in its own short-lived process, so it never waits for (or disturbs) the worker that may be busy.

``python -m vntext.bug_report_cli PARAMS.json`` reads the same parameters the worker task takes (src, out, log_lines, analysis_report,
extract_status, app_version) and prints one JSON line: {"ok": true, "summary": "..."} or {"ok": false, "error": "..."}.  Nothing is uploaded.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path


def run(params: dict) -> dict:
    src = str(params.get("src") or "").strip()
    out = str(params.get("out") or "").strip()
    if not src or not out or not Path(src).exists():
        return {"ok": False, "error": "Hãy chọn game trước khi tạo gói báo lỗi."}
    try:
        from vntext.bug_report import build_report, describe_report
        target = build_report(src, out, log_lines=[str(x) for x in (params.get("log_lines") or [])],
                              analysis_report=params.get("analysis_report") or None, extract_status=params.get("extract_status") or None,
                              app_version=str(params.get("app_version") or ""))
        return {"ok": True, "path": str(target), "summary": f"Đã tạo gói báo lỗi ẩn danh: {target}\n{describe_report(target)}\n"
                "Gửi tệp này bằng nút 'Gửi báo lỗi' (nếu có), hoặc đính kèm vào một issue mới: https://github.com/CaLanh24/VnText/issues/new"}
    except Exception as exc:  # noqa: BLE001 - report the cause instead of dying silently
        return {"ok": False, "error": f"Không tạo được gói báo lỗi: {exc}"}


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(json.dumps({"ok": False, "error": "usage: bug_report_cli PARAMS.json"}))
        return 2
    try:
        params = json.loads(Path(argv[1]).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        print(json.dumps({"ok": False, "error": f"Không đọc được tham số: {exc}"}, ensure_ascii=False))
        return 2
    result = run(params if isinstance(params, dict) else {})
    sys.stdout.reconfigure(encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
