# -*- coding: utf-8 -*-

"""VH parity play route: launch patched game_copy, click through title, capture screenshots.

Tuyến cố định (tự động, không cần tay):
  1) Mở game (windowed) với -logFile riêng
  2) Click/Enter qua age gate / title
  3) Chụp title + sau vài thao tác
  4) Đối chiếu choice CSV đã Việt hóa + asset text VI
  5) Fingerprint gốc không đổi

Không đụng game gốc / VH / VNText_Output.
"""

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

sys.path.insert(0, str(TESTS / "harness" / "crash"))
sys.path.insert(0, str(TESTS / "harness" / "vh_parity"))
sys.path.insert(0, str(TESTS / "harness" / "naninovel"))

import csv
import json
import re
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path


from windows_capture import bmp_to_png, screenshot_bmp, screenshot_hwnd  # noqa: E402
from player_log_scan import scan_player_log  # noqa: E402
from run_vh_parity_e2e import asset_vi_evidence  # noqa: E402
from sample_unity_e2e_lib import fingerprint_game  # noqa: E402
from work_paths import E2E_GAME_COPY, WORK_ROOT, kill_processes_using, register_artifact  # noqa: E402

OUT = WORK_ROOT / "vh_parity" / "play"
LOG = OUT / "play.log"
REPORT = OUT / "play_report.json"
PLAYER_LOG = OUT / "Player_play.log"
PKG_CSV = WORK_ROOT / "mt_pipeline_copy" / "translation.csv"
FP_EN = WORK_ROOT / "vh_parity" / "fingerprint_original_en.json"
VI_RX = re.compile(r"[\u00c0-\u1ef9]")


def log(msg: str) -> None:
    line = f"[{datetime.now(timezone.utc).strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    OUT.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def press_key(vk: int) -> None:
    import ctypes

    user32 = ctypes.windll.user32
    KEYEVENTF_KEYUP = 0x0002
    user32.keybd_event(vk, 0, 0, 0)
    user32.keybd_event(vk, 0, KEYEVENTF_KEYUP, 0)


def click_client(hwnd: int, x_frac: float, y_frac: float) -> None:
    """Click inside game client area (not full desktop)."""
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.windll.user32
    try:
        user32.SetProcessDPIAware()
    except Exception:
        pass

    class RECT(ctypes.Structure):
        _fields_ = [
            ("left", wintypes.LONG),
            ("top", wintypes.LONG),
            ("right", wintypes.LONG),
            ("bottom", wintypes.LONG),
        ]

    user32.ShowWindow(hwnd, 9)
    user32.SetForegroundWindow(hwnd)
    time.sleep(0.08)
    rect = RECT()
    user32.GetClientRect(hwnd, ctypes.byref(rect))
    w = max(1, rect.right - rect.left)
    h = max(1, rect.bottom - rect.top)
    cx = int(w * x_frac)
    cy = int(h * y_frac)
    pt = wintypes.POINT(0, 0)
    user32.ClientToScreen(hwnd, ctypes.byref(pt))
    user32.SetCursorPos(pt.x + cx, pt.y + cy)
    time.sleep(0.05)
    user32.mouse_event(0x0002, 0, 0, 0, 0)
    time.sleep(0.05)
    user32.mouse_event(0x0004, 0, 0, 0, 0)
    # Fallback when cursor clicks are swallowed
    lparam = (cy << 16) | (cx & 0xFFFF)
    user32.PostMessageW(hwnd, 0x0201, 0x0001, lparam)  # WM_LBUTTONDOWN
    time.sleep(0.03)
    user32.PostMessageW(hwnd, 0x0202, 0, lparam)  # WM_LBUTTONUP


def focus_game() -> int:
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.windll.user32
    hwnd = user32.FindWindowW(None, "SampleGame")
    if not hwnd:
        # Fallback: tìm theo process SampleGame.exe (title có thể đổi lúc load)
        import subprocess as sp

        try:
            out = sp.check_output(
                ["powershell", "-NoProfile", "-Command",
                 "(Get-Process SampleGame -ErrorAction SilentlyContinue | Select-Object -First 1 -ExpandProperty Id)"],
                text=True,
            ).strip()
            pid = int(out) if out.isdigit() else 0
        except Exception:
            pid = 0
        if pid:

            @ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
            def _enum(hwnd_i, _lp):
                nonlocal hwnd
                if not user32.IsWindowVisible(hwnd_i):
                    return True
                proc_id = wintypes.DWORD()
                user32.GetWindowThreadProcessId(hwnd_i, ctypes.byref(proc_id))
                if int(proc_id.value) != pid:
                    return True
                rect = wintypes.RECT()
                user32.GetClientRect(hwnd_i, ctypes.byref(rect))
                if (rect.right - rect.left) < 100 or (rect.bottom - rect.top) < 100:
                    return True
                hwnd = int(hwnd_i)
                return False

            user32.EnumWindows(_enum, 0)
    if not hwnd:
        return 0
    user32.ShowWindow(hwnd, 9)
    user32.SetForegroundWindow(hwnd)
    time.sleep(0.35)
    return int(hwnd)


def choice_vi_stats(csv_path: Path) -> dict:
    with csv_path.open(encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))
    choices = [
        r
        for r in rows
        if (r.get("import_method") or "") == "naninovel_choice"
        or str(r.get("context") or "").lower().endswith(":choice")
    ]
    with_vi = 0
    samples = []
    empty = 0
    for r in choices:
        tr = (r.get("translation") or "").strip()
        src = (r.get("source_text") or "").strip()
        if not tr:
            empty += 1
            continue
        if VI_RX.search(tr):
            with_vi += 1
        if len(samples) < 10 and VI_RX.search(tr):
            samples.append({"source": src[:60], "translation": tr[:60]})
    return {
        "choice_rows": len(choices),
        "empty": empty,
        "with_vi": with_vi,
        "samples": samples,
        "ok": len(choices) >= 10 and empty == 0 and with_vi >= 20,
    }


def capture(step: str) -> dict:
    OUT.mkdir(parents=True, exist_ok=True)
    bmp = OUT / f"{step}.bmp"
    png = OUT / f"{step}.png"
    try:
        hwnd = 0
        for _ in range(5):
            hwnd = focus_game()
            if hwnd:
                break
            time.sleep(0.3)
        ok_shot = False
        if hwnd:
            ok_shot = bool(screenshot_hwnd(hwnd, bmp))
        # Không fallback full-desktop (hay bắt nhầm Cursor). Retry PrintWindow.
        if not ok_shot and hwnd:
            time.sleep(0.4)
            focus_game()
            ok_shot = bool(screenshot_hwnd(hwnd, bmp))
        if not ok_shot:
            return {"step": step, "ok": False, "error": "game_hwnd_capture_failed", "bytes": 0}
        bmp_to_png(bmp, png)
        bmp_bytes = bmp.stat().st_size if bmp.is_file() else 0
        png_bytes = png.stat().st_size if png.is_file() else 0
        ok = (bmp_bytes > 50_000) or (png_bytes > 5_000)
        return {
            "step": step,
            "png": str(png) if png.is_file() else "",
            "bmp": str(bmp) if bmp.is_file() else "",
            "ok": ok,
            "bytes": png_bytes or bmp_bytes,
            "bmp_bytes": bmp_bytes,
            "hwnd": int(hwnd),
        }
    except Exception as exc:
        return {"step": step, "ok": False, "error": str(exc)}


def play_route(game_copy: Path, total_s: int = 70) -> dict:
    kill_processes_using(game_copy)
    if PLAYER_LOG.is_file():
        PLAYER_LOG.unlink()
    exe = game_copy / "SampleGame.exe"
    args = [
        str(exe),
        "-screen-fullscreen",
        "0",
        "-screen-width",
        "1280",
        "-screen-height",
        "720",
        "-logFile",
        str(PLAYER_LOG),
    ]
    log(f"LAUNCH {' '.join(args)}")
    proc = subprocess.Popen(args, cwd=str(game_copy))
    shots: list[dict] = []
    actions: list[str] = []
    t0 = time.time()

    # Chờ cửa sổ
    hwnd = 0
    for _ in range(20):
        time.sleep(1)
        if proc.poll() is not None:
            break
        hwnd = focus_game()
        if hwnd:
            break

    # Age gate / warning
    if proc.poll() is None and hwnd:
        try:
            click_client(hwnd, 0.5, 0.5)
            actions.append("click_center_1")
        except Exception as exc:
            actions.append(f"click_fail:{exc}")
        time.sleep(2)
        hwnd = focus_game() or hwnd
        for vk in (0x0D, 0x20, 0x0D):
            if focus_game():
                press_key(vk)
            time.sleep(0.6)
        actions.append("keys_enter_space")
        time.sleep(3)
        shots.append(capture("01_title"))

    # New Game: bàn phím (Up→đầu, Down→hàng 2) + 1 Enter — không Escape spam.
    if proc.poll() is None:
        hwnd = focus_game() or hwnd
        if hwnd:
            time.sleep(1.0)
            # Focus cột menu trái
            click_client(hwnd, 0.12, 0.195)
            time.sleep(0.4)
            for _ in range(15):
                press_key(0x26)  # Up
                time.sleep(0.08)
            press_key(0x28)  # Down → New Game (Continue bị disable vẫn chiếm slot 0)
            time.sleep(0.35)
            actions.append("kb_focus_up15_down1")
            press_key(0x0D)
            time.sleep(1.2)
            # Confirm Yes nếu có
            click_client(hwnd, 0.58, 0.52)
            time.sleep(0.4)
            press_key(0x0D)
            actions.append("confirm_enter")
            time.sleep(16)
            shots.append(capture("02_after_newgame"))
            time.sleep(2)
            shots.append(capture("02b_after_newgame"))

    # Advance dialogue / tới choice
    if proc.poll() is None:
        hwnd = focus_game() or hwnd
        if hwnd:
            for _ in range(8):
                press_key(0x20)
                time.sleep(0.6)
            actions.append("space_x8")
            click_client(hwnd, 0.5, 0.75)
            time.sleep(2)
            click_client(hwnd, 0.5, 0.55)
            time.sleep(3)
            shots.append(capture("03_dialogue_or_choice"))

    # Đợi hết ngân sách thời gian
    while time.time() - t0 < total_s and proc.poll() is None:
        time.sleep(1)

    alive = proc.poll() is None
    if alive:
        proc.terminate()
        try:
            proc.wait(timeout=8)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)

    log_scan = scan_player_log(PLAYER_LOG)
    log_status = log_scan.get("status", "NOT_TESTABLE")
    log_reasons = log_scan.get("reasons", [])
    crash = log_status == "FAIL"
    vi_in_log = 0
    log_tail = ""
    if PLAYER_LOG.is_file():
        text = PLAYER_LOG.read_text(encoding="utf-8", errors="ignore")
        vi_in_log = len(VI_RX.findall(text))
        log_tail = "\n".join(text.splitlines()[-30:])

    shots_ok = sum(1 for s in shots if s.get("ok"))
    return {
        "alive_before_kill": alive,
        "exit_code": proc.returncode,
        "elapsed_s": round(time.time() - t0, 1),
        "actions": actions,
        "screenshots": shots,
        "screenshots_ok": shots_ok,
        "vi_chars_in_log": vi_in_log,
        "crash_markers": crash,
        "player_log_status": log_status,
        "player_log_reasons": log_reasons,
        "player_log_markers": log_scan.get("markers", {}),
        "player_log_scan": log_scan,
        "player_log": str(PLAYER_LOG),
        "log_tail": log_tail,
        "ok": alive and log_status == "PASS" and shots_ok >= 2,
    }


def main() -> int:
    if LOG.is_file():
        LOG.unlink()
    OUT.mkdir(parents=True, exist_ok=True)
    report: dict = {"started": datetime.now(timezone.utc).isoformat()}

    game = E2E_GAME_COPY
    if not (game / "SampleGame.exe").is_file():
        log(f"FAIL missing game_copy exe: {game}")
        report["verdict"] = "FAIL_NO_COPY"
        REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        return 2

    fp_doc = json.loads(FP_EN.read_text(encoding="utf-8"))
    orig = Path(fp_doc["root"])
    before = fingerprint_game(orig)
    for rel, digest in fp_doc["files"].items():
        if before.get(rel) != digest:
            log(f"FAIL original changed: {rel}")
            report["verdict"] = "FAIL_ORIGINAL"
            REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
            return 1
    report["original_fingerprint_before"] = "PASS"

    assets = asset_vi_evidence(game)
    report["asset_vi"] = assets
    log(f"asset_vi ok={assets.get('ok')} vi_files={assets.get('files_with_vi')}")
    if not assets.get("ok"):
        report["verdict"] = "FAIL_ASSET_VI"
        REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        return 1

    choices = choice_vi_stats(PKG_CSV)
    report["choice_vi"] = choices
    log(f"choice_vi ok={choices.get('ok')} with_vi={choices.get('with_vi')}/{choices.get('choice_rows')}")
    if not choices.get("ok"):
        report["verdict"] = "FAIL_CHOICE_VI"
        REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        return 1

    log("Play route...")
    play = play_route(game, total_s=70)
    report["play"] = play
    log(
        "Play: "
        f"alive={play.get('alive_before_kill')} shots={play.get('screenshots_ok')} "
        f"log_status={play.get('player_log_status')} "
        f"log_reasons={play.get('player_log_reasons')}"
    )

    after = fingerprint_game(orig)
    for rel, digest in before.items():
        if after.get(rel) != digest:
            log(f"FAIL original modified after play: {rel}")
            report["verdict"] = "FAIL_ORIGINAL_AFTER"
            REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
            return 1
    report["original_fingerprint_after"] = "PASS"

    ok = (
        assets.get("ok")
        and choices.get("ok")
        and play.get("ok")
        and report.get("original_fingerprint_after") == "PASS"
    )
    if play.get("player_log_status") == "NOT_TESTABLE":
        report["verdict"] = "NOT_TESTABLE_PLAYER_LOG"
    elif play.get("player_log_status") == "FAIL":
        report["verdict"] = "FAIL_PLAYER_LOG"
    else:
        report["verdict"] = "PASS" if ok else "FAIL"
    report["finished"] = datetime.now(timezone.utc).isoformat()
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    register_artifact(
        artifact_id="vh_parity_play",
        path=OUT,
        kind="report",
        created_by="run_vh_parity_play",
        purpose="Fixed-route play screenshots + VI evidence",
        status="ACTIVE",
    )
    log(f"Verdict={report['verdict']}")
    if report["verdict"] == "NOT_TESTABLE_PLAYER_LOG":
        return 2
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
