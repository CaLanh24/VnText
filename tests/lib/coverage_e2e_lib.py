"""Shared E2E helpers for coverage cases. Copy-only; never open original exe."""

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
from datetime import datetime, timezone
from pathlib import Path


from unity_patch_baseline import (
    PATCH_UNITY_GOLDEN,
    hash_game_files,
    load_original_hashes,
    origin_asset_hash_keys,
    read_game_folder,
)
from work_paths import E2E_GAME_COPY, kill_processes_using, prepare_e2e_game_copy


def log(msg: str) -> None:
    try:
        print(msg, flush=True)
    except UnicodeEncodeError:
        print(msg.encode("ascii", "backslashreplace").decode("ascii"), flush=True)


def prepare_origin_gate() -> Path:
    orig = read_game_folder()
    recorded = load_original_hashes()
    keys = origin_asset_hash_keys(recorded)
    current = hash_game_files(orig, keys)
    expected = {key: recorded[key] for key in keys}
    if current != expected:
        raise SystemExit("original game already drifted from baseline")
    return orig


def seed_fresh_copy(label: str, dest: Path | None = None, *, mode: str = "reset") -> Path:
    dest = dest or E2E_GAME_COPY
    if Path(dest).resolve() != E2E_GAME_COPY.resolve():
        raise SystemExit(f"E2E must use {E2E_GAME_COPY}, got {dest}")
    env_mode = os.environ.get("VNTEXT_E2E_FRESH")
    if env_mode == "1":
        mode = "fresh"
    log(f"PREPARE E2E copy mode={mode} label={label} dest={dest}")
    game_copy = prepare_e2e_game_copy(label=label, mode=mode)
    orig_exe = read_game_folder() / "SampleGame.exe"
    copy_exe = game_copy / "SampleGame.exe"
    if orig_exe.resolve() == copy_exe.resolve():
        raise SystemExit("refusing to launch original exe")
    return game_copy


def write_verdict(case_id: str, payload: dict) -> Path:
    work = WORK / case_id
    work.mkdir(parents=True, exist_ok=True)
    payload = dict(payload)
    payload.setdefault("captured_at", datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
    path = work / "verdict.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    log(f"VERDICT {payload.get('verdict')} -> {path}")
    return path


def click_client(hwnd, x: int, y: int) -> None:
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.windll.user32
    user32.SetProcessDPIAware()
    point = wintypes.POINT(int(x), int(y))
    if not user32.ClientToScreen(hwnd, ctypes.byref(point)):
        raise RuntimeError("ClientToScreen failed")
    user32.SetCursorPos(point.x, point.y)
    user32.mouse_event(0x0002, 0, 0, 0, 0)
    user32.mouse_event(0x0004, 0, 0, 0, 0)


def click_client_pct(hwnd, fx: float, fy: float) -> tuple[int, int, int, int]:
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.windll.user32
    rect = wintypes.RECT()
    if not user32.GetClientRect(hwnd, ctypes.byref(rect)):
        raise RuntimeError("GetClientRect failed")
    width = int(rect.right - rect.left)
    height = int(rect.bottom - rect.top)
    x = int(width * fx)
    y = int(height * fy)
    click_client(hwnd, x, y)
    return width, height, x, y


def find_game_hwnd():
    import ctypes

    user32 = ctypes.windll.user32
    return user32.FindWindowW(None, "SampleGame")
    import ctypes

    user32 = ctypes.windll.user32
    return user32.FindWindowW(None, "SampleGame")


def kill_game() -> None:
    kill_processes_using(E2E_GAME_COPY)


def launch_and_observe(
    exe: Path,
    work: Path,
    *,
    wait_s: int = 28,
    extra_wait_s: int = 14,
    after_click=None,
) -> dict:
    if exe.resolve() == (read_game_folder() / "SampleGame.exe").resolve():
        raise SystemExit("refusing to launch original SampleGame.exe")
    kill_game()
    log_file = work / "Player.log"
    args = [
        str(exe),
        "-screen-fullscreen",
        "0",
        "-screen-width",
        "1280",
        "-screen-height",
        "720",
        "-logFile",
        str(log_file),
    ]
    log(f"LAUNCH {args}")
    proc = subprocess.Popen(args, cwd=str(exe.parent))
    waited = 0
    while waited < wait_s:
        time.sleep(2)
        waited += 2
        if proc.poll() is not None:
            log(f"PROCESS exited code={proc.poll()} after {waited}s")
            break
        log(f"PROCESS still running {waited}s pid={proc.pid}")
    if proc.poll() is None:
        try:
            click_screen_center()
            log("CLICK center to dismiss warning if present")
        except Exception as exc:
            log(f"CLICK failed: {exc}")
        time.sleep(extra_wait_s)
        waited += extra_wait_s
        if callable(after_click):
            after_click(proc)
    screenshot = work / "menu.bmp"
    png = work / "menu.png"
    still_running = proc.poll() is None
    if still_running:
        try:
            import ctypes

            user32 = ctypes.windll.user32
            hwnd = user32.FindWindowW(None, "SampleGame")
            if hwnd:
                user32.ShowWindow(hwnd, 9)
                user32.SetForegroundWindow(hwnd)
                time.sleep(0.6)
            screenshot_bmp(screenshot)
            bmp_to_png(screenshot, png)
            log(f"SCREENSHOT {screenshot} size={screenshot.stat().st_size}")
        except Exception as exc:
            log(f"SCREENSHOT failed: {exc}")
        proc.terminate()
        try:
            proc.wait(timeout=8)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)
        log("PROCESS terminated after screenshot")
    else:
        try:
            screenshot_bmp(screenshot)
            bmp_to_png(screenshot, png)
        except Exception:
            pass
    log_path = log_file
    log_tail = ""
    crash_hint = False
    if log_path.is_file():
        text = log_path.read_text(encoding="utf-8", errors="replace")
        log_tail = "\n".join(text.splitlines()[-80:])
        lower = text.lower()
        crash_hint = "crash" in lower or "exception" in lower or "fatal" in lower
    return {
        "pid": proc.pid,
        "exit_code": proc.poll(),
        "waited_s": waited,
        "still_running_at_screenshot": still_running,
        "early_exit": (not still_running) and waited < 8,
        "screenshot": str(screenshot) if screenshot.is_file() else "",
        "screenshot_png": str(png) if png.is_file() else "",
        "player_log": str(log_path) if log_path.is_file() else "",
        "player_log_crash_hint": crash_hint,
        "player_log_tail": log_tail,
    }


def finish_origin_check() -> None:
    assert_original_game_untouched()
    log("ORIGINAL_UNCHANGED=True")
