"""Build the anonymous bug report in its own short-lived process, so it never waits for (or disturbs) the worker that may be busy.

``python -m vntext.bug_report_cli PARAMS.json`` reads the same parameters the worker task takes (src, out, log_lines, analysis_report,
extract_status, app_version; optional: game_error=true to add the anonymous traceback facts of the patched game, manifest, patch_out) and prints one
JSON line: {"ok": true, "summary": "...", "path": "..."} or {"ok": false, "error": "..."}.  Nothing is uploaded.

``action: "game_error_scan"`` reads traceback.txt / the generated translation file of the patched game and answers with a plain-Vietnamese preview;
``action: "game_error_revert"`` takes the given blocks out of the generated file (with a backup).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

SAVED_NOTE = "Gói cũng được lưu tại {path} — bạn có thể đưa đường dẫn này cho người hỗ trợ."


def _game_error(params: dict) -> dict | None:
    if not params.get("game_error"):
        return None
    from vntext.game_error_report import scan_game
    return scan_game(str(params.get("src") or ""), params.get("manifest") or None)["report"]


def _patch_report(params: dict) -> dict | None:
    patch_out = str(params.get("patch_out") or "").strip()
    if not patch_out or not Path(patch_out).is_dir():
        return None
    from vntext.patch_report import build_patch_report
    return build_patch_report(patch_out, params.get("extract_status") or None)


def run(params: dict) -> dict:
    action = str(params.get("action") or "build")
    if action == "game_error_scan":
        src = str(params.get("src") or "").strip()
        if not src or not Path(src).is_dir():
            return {"ok": False, "error": "Hãy chọn thư mục game trước."}
        from vntext.game_error_report import scan_game
        result = scan_game(src, params.get("manifest") or None)
        return {"ok": True, "summary": "\n".join(result["lines"]), "revertable": result["revertable"],
                "blocks": [u["block"] for u in result["units"]], "traceback_found": result["report"]["traceback_found"],
                "broken": len(result["report"]["broken_overlay_lines"])}
    if action == "game_error_revert":
        from vntext.game_error_report import revert_units
        try:
            done = revert_units(str(params.get("src") or ""), [list(b) for b in params.get("blocks") or []])
        except OSError as exc:
            return {"ok": False, "error": f"Chưa gỡ được dòng lỗi: {exc}"}
        left = done["remaining_problems"]
        text = (f"Đã gỡ {done['removed_lines']} dòng khỏi tệp bản dịch trong game; game sẽ dùng câu gốc ở chỗ đó. Bản sao lưu: {done['backup']}."
                + (f" Vẫn còn {len(left)} dòng hỏng (dòng {', '.join(str(n) for n in left[:8])})." if left else ""))
        return {"ok": not left, "summary": text, "error": text if left else ""}
    src = str(params.get("src") or "").strip()
    out = str(params.get("out") or "").strip()
    if not src or not out or not Path(src).exists():
        return {"ok": False, "error": "Hãy chọn game trước khi tạo gói báo lỗi."}
    try:
        from vntext.bug_report import build_report, describe_report
        target = build_report(src, out, log_lines=[str(x) for x in (params.get("log_lines") or [])],
                              analysis_report=params.get("analysis_report") or None, extract_status=params.get("extract_status") or None,
                              app_version=str(params.get("app_version") or ""), game_error=_game_error(params), patch_report=_patch_report(params))
        saved = SAVED_NOTE.format(path=target)
        if params.get("for_send"):
            # Preview before "Gửi báo lỗi": the question is whether to send, so the manual-route advice does not belong here.
            return {"ok": True, "path": str(target), "summary": f"Đã tạo gói báo lỗi ẩn danh.\n{describe_report(target, for_send=True)}\n{saved}"}
        return {"ok": True, "path": str(target), "summary": f"Đã tạo gói báo lỗi ẩn danh: {target}\n{describe_report(target)}\n{saved}\n"
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
