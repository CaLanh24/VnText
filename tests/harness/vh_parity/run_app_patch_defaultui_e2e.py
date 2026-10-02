# -*- coding: utf-8 -*-

"""HISTORICAL / SUPERSEDED — Not part of current bootstrap or current-state evidence.

Legacy E2E: luồng Patch app (run_patch_task) gồm DefaultUI TextAsset overlay.

Giữ lại để điều tra fixture ngoài khi được chỉ định; không phải public-core
workflow và không dùng để chứng minh capability hiện tại.
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

import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path


from run_newgame_probe import analyze_log, launch, route_new_game  # noqa: E402
from run_vh_parity_e2e import asset_vi_evidence  # noqa: E402
from sample_unity_e2e_lib import fingerprint_game  # noqa: E402
from vntext.app_tasks import run_patch_task  # noqa: E402
from vh_parity_local_validate import validate_package  # noqa: E402
from work_paths import E2E_GAME_COPY, WORK_ROOT, kill_processes_using, prepare_e2e_game_copy  # noqa: E402
from cleanup_work_artifacts import cleanup_after_test  # noqa: E402


CAPABILITY_STATUS = "UNSUPPORTED"


def verify_optional_ui_values(_unity_path: Path) -> dict:
    """Fail closed: the historical UI-only game harness is not public core."""
    raise SystemExit(
        "UNSUPPORTED: legacy UI-only verification requires an explicit external game adapter"
    )

PKG = WORK_ROOT / "mt_pipeline_copy"
OUT = WORK_ROOT / "vh_parity"
TMP = OUT / "_tmp_app_patch_defaultui"
PATCH_OUT = TMP / "Patch_Viet_Hoa"
REPORT = OUT / "app_patch_defaultui_report.json"
FP_EN = OUT / "fingerprint_original_en.json"
FP_VH = OUT / "fingerprint_original_vh.json"


def main() -> int:
    if TMP.exists():
        shutil.rmtree(TMP, ignore_errors=True)
    TMP.mkdir(parents=True)

    logs: list[str] = []
    done: list[dict] = []

    kill_processes_using(E2E_GAME_COPY)
    game = prepare_e2e_game_copy(label="app_patch_defaultui", mode="reset")

    run_patch_task(
        PKG / "translation.csv",
        PKG / "manifest.json",
        str(game),
        str(PATCH_OUT),
        progress=lambda _i: None,
        log=logs.append,
        complete=done.append,
    )
    if not done or not done[0].get("ok"):
        REPORT.write_text(
            json.dumps({"ok": False, "stage": "run_patch_task", "done": done, "logs": logs[-20:]}, ensure_ascii=False, indent=2)
            + "\n",
            encoding="utf-8",
        )
        cleanup = cleanup_after_test([TMP], reason="app_patch_defaultui_fail", outcome="FAIL")
        if not cleanup.get("ok"):
            REPORT.write_text(
                json.dumps(
                    {"ok": False, "stage": "cleanup", "cleanup": cleanup, "logs": logs[-20:]},
                    ensure_ascii=False,
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
        return 1

    # Cài patch vào game_copy (không đụng game gốc)
    copy_root = PATCH_OUT / "COPY_TO_GAME_ROOT"
    rc = subprocess.call(
        [
            "robocopy",
            str(copy_root),
            str(game),
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
        raise SystemExit(f"robocopy fail {rc}")

    report_txt = (PATCH_OUT / "import_report.txt").read_text(encoding="utf-8", errors="ignore")
    defaultui_note = "DEFAULTUI_CHROME" in report_txt
    file_check = verify_optional_ui_values(game / "SampleGame_Data" / "data.unity3d")
    val = validate_package(PKG, golden_mapping=OUT / "golden_mapping.csv")

    log_path = OUT / "Player_app_patch_defaultui.log"
    if log_path.exists():
        log_path.unlink()
    proc = launch(game, log_path)
    play = route_new_game(proc, "app_patch_defaultui", total_s=85)
    log_info = analyze_log(log_path)
    log_text = log_path.read_text(encoding="utf-8", errors="ignore") if log_path.is_file() else ""
    shots_ok = sum(1 for s in play.get("shots", []) if s.get("ok"))
    naninovel_ser = "Naninovel.Script?" in log_text and "serialization layout" in log_text.lower()
    nscripts = "nScripts/Init" in log_text

    en_doc = json.loads(FP_EN.read_text(encoding="utf-8"))
    vh_doc = json.loads(FP_VH.read_text(encoding="utf-8"))
    en_after = fingerprint_game(Path(en_doc["root"]))
    vh_after = fingerprint_game(Path(vh_doc["root"]))
    fp_en_bad = sum(1 for r, d in en_doc["files"].items() if en_after.get(r) != d)
    fp_vh_bad = sum(1 for r, d in vh_doc["files"].items() if vh_after.get(r) != d)

    asset = asset_vi_evidence(game)
    ok = (
        bool(done[0].get("defaultui_ok"))
        and defaultui_note
        and file_check.get("pass")
        and val.get("pass")
        and not log_info.get("startgame_fail")
        and not nscripts
        and not naninovel_ser
        and int(log_info.get("exception_count") or 0) == 0
        and shots_ok >= 8
        and fp_en_bad == 0
        and fp_vh_bad == 0
        and asset.get("ok")
    )

    report = {
        "utc": datetime.now(timezone.utc).isoformat(),
        "ok": ok,
        "run_patch_task": done[0],
        "defaultui_note_in_report": defaultui_note,
        "file_check": file_check,
        "local_validate": {
            "pass": val.get("pass"),
            "choice": val.get("choice_coverage"),
            "menu": val.get("menu_coverage"),
        },
        "smoke": {
            "shots_ok": shots_ok,
            "startgame_fail": log_info.get("startgame_fail"),
            "nscripts_init_fail": nscripts,
            "naninovel_serialization": naninovel_ser,
            "exception_count": log_info.get("exception_count"),
            "asset_vi_ok": asset.get("ok"),
            "fp_en_bad": fp_en_bad,
            "fp_vh_bad": fp_vh_bad,
        },
        "logs_tail": logs[-15:],
    }
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    # Giữ report + Player log; dọn patch tmp nặng
    evid = OUT / "evidence"
    evid.mkdir(parents=True, exist_ok=True)
    if log_path.is_file():
        shutil.copy2(log_path, evid / "Player_app_patch_defaultui.log")
    shutil.copy2(REPORT, evid / "app_patch_defaultui_report.json")
    cleanup = cleanup_after_test([TMP], reason="app_patch_defaultui_post", outcome="PASS" if ok else "FAIL")
    report["cleanup"] = cleanup
    if not cleanup.get("ok"):
        ok = False
        report["ok"] = False
        REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        shutil.copy2(REPORT, evid / "app_patch_defaultui_report.json")
    print(json.dumps({"ok": ok, "shots": shots_ok, "defaultui": file_check.get("pass"), "fp": [fp_en_bad, fp_vh_bad]}, ensure_ascii=False), flush=True)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
