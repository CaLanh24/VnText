# -*- coding: utf-8 -*-

"""VH parity E2E after full MT: patch mt_pipeline_copy → game_copy → smoke launch.

Không đụng game gốc / VH gốc / VNText_Output.
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
import shutil
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path


from sample_unity_e2e_lib import fingerprint_game  # noqa: E402
from unity_patch_baseline import read_game_folder  # noqa: E402
from work_paths import E2E_GAME_COPY, WORK_ROOT, prepare_e2e_game_copy, register_artifact  # noqa: E402
from vntext_studio import apply_translation_package  # noqa: E402

PKG = WORK_ROOT / "mt_pipeline_copy"
MT_CSV = PKG / "translation.csv"
MANIFEST = PKG / "manifest.json"
OUT = WORK_ROOT / "vh_parity" / "e2e"
PATCH_OUT = OUT / "patch_out"
REPORT = OUT / "e2e_report.json"
LOG = OUT / "e2e.log"
FP_EN = WORK_ROOT / "vh_parity" / "fingerprint_original_en.json"
VI_RX = re.compile(r"[\u00c0-\u1ef9]")
CHOICE_KEYS_SAMPLE = 12


def log(msg: str) -> None:
    line = f"[{datetime.now(timezone.utc).strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def load_fp(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def choice_stats(csv_path: Path) -> dict:
    with csv_path.open(encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))
    choices = [
        r
        for r in rows
        if (r.get("import_method") or "") == "naninovel_choice"
        or str(r.get("context") or "").lower().endswith(":choice")
    ]
    translated = 0
    identity = 0
    empty = 0
    samples = []
    for r in choices:
        src = (r.get("source_text") or "").strip()
        tr = (r.get("translation") or "").strip()
        if not tr:
            empty += 1
        elif tr == src:
            identity += 1
        else:
            translated += 1
        if len(samples) < CHOICE_KEYS_SAMPLE:
            samples.append(
                {
                    "key": r.get("key"),
                    "source": src[:80],
                    "translation": tr[:80],
                    "has_vi": bool(VI_RX.search(tr)),
                }
            )
    return {
        "choice_rows": len(choices),
        "translated": translated,
        "identity": identity,
        "empty": empty,
        "samples": samples,
    }


def launch_smoke(game_copy: Path, seconds: int = 28) -> dict:
    exe = game_copy / "SampleGame.exe"
    proc = subprocess.Popen(
        [str(exe)],
        cwd=str(game_copy),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    time.sleep(seconds)
    alive = proc.poll() is None
    if alive:
        proc.terminate()
        try:
            proc.wait(timeout=8)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)
    crash = False
    log_path = Path.home() / "AppData" / "LocalLow" / "VNTextStudio" / "SampleGame" / "Player.log"
    vi_hits = 0
    if log_path.is_file():
        text = log_path.read_text(encoding="utf-8", errors="ignore")
        vi_hits = len(VI_RX.findall(text))
        crash = "Crash!!!" in text or "Fatal error" in text
    return {
        "alive_after_wait": alive,
        "exit_code": proc.returncode,
        "vi_chars_in_log": vi_hits,
        "crash_markers": crash,
        "player_log": str(log_path) if log_path.is_file() else "",
    }


def asset_vi_evidence(game_copy: Path) -> dict:
    """Chứng minh patch đã đưa chữ VI vào StreamingAssets text (không dựa Player.log)."""
    text_dir = game_copy / "SampleGame_Data" / "StreamingAssets" / "text"
    files = list(text_dir.glob("*.txt")) if text_dir.is_dir() else []
    with_vi = 0
    note_files = 0
    ban_files = 0
    samples: list[dict] = []
    for path in files:
        raw = path.read_text(encoding="utf-8", errors="ignore")
        if VI_RX.search(raw):
            with_vi += 1
            if len(samples) < 5:
                for line in raw.splitlines():
                    if VI_RX.search(line) and "♪" not in line:
                        samples.append({"file": path.name, "line": line[:100]})
                        break
        if "♪" in raw:
            note_files += 1
        if "bán bán" in raw.casefold():
            ban_files += 1
    anal = text_dir / "sample_anal.txt"
    anal_ok = anal.is_file() and "Đau quá" in anal.read_text(encoding="utf-8", errors="ignore")
    return {
        "text_files": len(files),
        "files_with_vi": with_vi,
        "files_with_note": note_files,
        "files_with_banban": ban_files,
        "sample_anal_has_dau_qua": anal_ok,
        "samples": samples,
        "ok": len(files) >= 20 and with_vi >= 30 and note_files == 0 and ban_files == 0 and anal_ok,
    }


def main() -> int:
    if LOG.is_file():
        LOG.unlink()
    OUT.mkdir(parents=True, exist_ok=True)
    if PATCH_OUT.exists():
        shutil.rmtree(PATCH_OUT)
    PATCH_OUT.mkdir(parents=True, exist_ok=True)

    if not MT_CSV.is_file() or not MANIFEST.is_file():
        log(f"FAIL missing package under {PKG}")
        return 2

    report: dict = {"started": datetime.now(timezone.utc).isoformat()}
    choices = choice_stats(MT_CSV)
    report["choice_stats"] = choices
    log(f"Choice stats: {choices['choice_rows']} translated={choices['translated']} empty={choices['empty']}")
    if choices["empty"] > 0 or choices["choice_rows"] < 10:
        log("FAIL: choice chưa đủ dịch trước patch")
        report["verdict"] = "FAIL_CHOICE"
        REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        return 1

    fp_doc = load_fp(FP_EN)
    orig = Path(fp_doc["root"])
    if not orig.is_dir():
        orig = read_game_folder()
    before = fingerprint_game(orig)
    for rel, digest in fp_doc["files"].items():
        if before.get(rel) != digest:
            log(f"FAIL original changed before E2E: {rel}")
            report["verdict"] = "FAIL_ORIGINAL"
            REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
            return 1
    report["original_fingerprint_before"] = "PASS"

    log("Reset game_copy...")
    game_copy = prepare_e2e_game_copy(label="VH_PARITY_E2E", mode="reset")
    log(f"game_copy={game_copy}")

    log("Patch...")
    result = apply_translation_package(
        str(MT_CSV),
        str(MANIFEST),
        str(game_copy),
        str(PATCH_OUT),
        progress_callback=lambda _info: None,
    )
    report["patch"] = {
        k: result.get(k)
        for k in ("ok", "patched_files", "applied", "skipped", "errors", "summary")
        if isinstance(result, dict) and k in result
    } if isinstance(result, dict) else {"raw_type": str(type(result))}
    log(f"Patch done: {report['patch']}")

    copy_root = PATCH_OUT / "COPY_TO_GAME_ROOT"
    if not copy_root.is_dir():
        log(f"FAIL missing {copy_root}")
        report["verdict"] = "FAIL_PATCH_OUT"
        REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        return 1

    rc = subprocess.call(
        [
            "robocopy",
            str(copy_root),
            str(game_copy),
            "/E",
            "/NFL",
            "/NDL",
            "/NJH",
            "/NJS",
            "/nc",
            "/ns",
            "/np",
            "/R:2",
            "/W:2",
        ]
    )
    if rc >= 8:
        log(f"FAIL robocopy install rc={rc}")
        report["verdict"] = "FAIL_INSTALL"
        REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        return 1
    log("Installed patch into game_copy")

    after = fingerprint_game(orig)
    for rel, digest in before.items():
        if after.get(rel) != digest:
            log(f"FAIL original modified: {rel}")
            report["verdict"] = "FAIL_ORIGINAL_AFTER"
            REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
            return 1
    report["original_fingerprint_after"] = "PASS"

    assets = asset_vi_evidence(game_copy)
    report["asset_vi"] = assets
    log(f"Asset VI: {assets}")
    if not assets.get("ok"):
        log("FAIL: StreamingAssets text thiếu VI sạch sau patch")
        report["verdict"] = "FAIL_ASSET_VI"
        REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        return 1

    log("Launch smoke...")
    smoke = launch_smoke(game_copy, seconds=40)
    report["smoke"] = smoke
    log(f"Smoke: {smoke}")

    ok = (
        smoke.get("alive_after_wait")
        and not smoke.get("crash_markers")
        and choices["empty"] == 0
        and report.get("original_fingerprint_after") == "PASS"
        and assets.get("ok")
    )
    report["verdict"] = "PASS" if ok else "FAIL"
    report["finished"] = datetime.now(timezone.utc).isoformat()
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    register_artifact(
        artifact_id="vh_parity_e2e",
        path=OUT,
        kind="report",
        created_by="run_vh_parity_e2e",
        purpose="VH parity patch+launch evidence",
        status="ACTIVE",
    )
    log(f"Verdict={report['verdict']}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
