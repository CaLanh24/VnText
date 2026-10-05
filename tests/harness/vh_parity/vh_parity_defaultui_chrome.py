# -*- coding: utf-8 -*-

"""HISTORICAL / SUPERSEDED — Not part of current bootstrap or current-state evidence.

Legacy E2E: Việt hóa 16 DefaultUI chrome bằng patch UI-only + full package smoke.

Giữ lại để điều tra fixture ngoài khi được chỉ định; không phải public-core
workflow. Artifact tạm dưới TEST_RUN/vh_parity/_tmp_defaultui.
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
from vh_parity_coverage_fill import audit_and_fill  # noqa: E402
from vh_parity_local_validate import validate_package  # noqa: E402
from vntext.patch import apply_translation_package  # noqa: E402
from work_paths import E2E_GAME_COPY, WORK_ROOT, kill_processes_using, prepare_e2e_game_copy  # noqa: E402


def _unsupported_optional_ui_route(*_args, **_kwargs):
    """Fail closed: legacy UI-only game adapters are outside the public core."""
    raise SystemExit(
        "UNSUPPORTED: legacy UI-only verification requires an explicit external game adapter"
    )


patch_optional_ui_chrome_only = _unsupported_optional_ui_route
update_package_csv = _unsupported_optional_ui_route
verify_optional_ui_values = _unsupported_optional_ui_route

CAPABILITY_STATUS = "UNSUPPORTED"

PKG = WORK_ROOT / "mt_pipeline_copy"
OUT = WORK_ROOT / "vh_parity"
TMP = OUT / "_tmp_defaultui"
FP_EN = OUT / "fingerprint_original_en.json"
FP_VH = OUT / "fingerprint_original_vh.json"
FULL_PATCH = TMP / "full_patch_out"
UI_PATCH = TMP / "ui_only_patch_out"
REPORT = OUT / "defaultui_chrome_report.json"


def cleanup_tmp() -> None:
    if TMP.exists():
        shutil.rmtree(TMP, ignore_errors=True)


def main() -> int:
    cleanup_tmp()
    TMP.mkdir(parents=True)

    csv_info = update_package_csv(PKG)
    print(f"CSV updated keys={len(csv_info['applied'])} bak={csv_info['backup']}", flush=True)

    # 1) Patch UI-only trên game copy sạch — chứng minh không đụng Naninovel/.bundle
    kill_processes_using(E2E_GAME_COPY)
    game = prepare_e2e_game_copy(label="defaultui_ui_only", mode="reset")
    ui_res = patch_optional_ui_chrome_only(
        package_dir=PKG,
        game_root=game,
        output_dir=UI_PATCH,
    )
    print(f"UI-only output_rels={ui_res['output_rels']}", flush=True)
    file_check = verify_optional_ui_values(game / "SampleGame_Data" / "data.unity3d")
    print(f"UI-only file_check pass={file_check['pass']} bad={file_check['bad']}", flush=True)
    if not file_check["pass"]:
        REPORT.write_text(
            json.dumps({"ok": False, "stage": "ui_only_file", "file_check": file_check, "ui_res": ui_res}, ensure_ascii=False, indent=2)
            + "\n",
            encoding="utf-8",
        )
        from cleanup_work_artifacts import cleanup_after_test  # noqa: E402
        cleanup = cleanup_after_test([TMP], reason="defaultui_chrome_ui_only_fail", outcome="FAIL")
        if not cleanup.get("ok"):
            REPORT.write_text(
                json.dumps(
                    {"ok": False, "stage": "cleanup", "cleanup": cleanup, "ui_res": ui_res},
                    ensure_ascii=False,
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
        return 1

    # 2) Full package trên game copy sạch (CSV đã có DefaultUI VI) + smoke New Game
    kill_processes_using(E2E_GAME_COPY)
    game = prepare_e2e_game_copy(label="defaultui_full_patch", mode="reset")
    if FULL_PATCH.exists():
        shutil.rmtree(FULL_PATCH)
    FULL_PATCH.mkdir(parents=True)
    apply_translation_package(
        str(PKG / "translation.csv"),
        str(PKG / "manifest.json"),
        str(game),
        str(FULL_PATCH),
    )
    copy_root = FULL_PATCH / "COPY_TO_GAME_ROOT"
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

    file_check2 = verify_optional_ui_values(game / "SampleGame_Data" / "data.unity3d")
    print(f"full-patch file_check pass={file_check2['pass']} bad={file_check2['bad']}", flush=True)

    # Smoke
    import vh_parity_batch_loop as bl

    log_path = OUT / "Player_defaultui_chrome.log"
    if log_path.exists():
        log_path.unlink()
    proc = launch(game, log_path)
    play = route_new_game(proc, "defaultui_chrome", total_s=85)
    log_info = analyze_log(log_path)
    log_text = log_path.read_text(encoding="utf-8", errors="ignore") if log_path.is_file() else ""
    shots_ok = sum(1 for s in play.get("shots", []) if s.get("ok"))
    naninovel_ser = "Naninovel.Script?" in log_text and "serialization layout" in log_text.lower()
    nscripts = "nScripts/Init" in log_text

    # Fingerprint
    en_doc = json.loads(FP_EN.read_text(encoding="utf-8"))
    vh_doc = json.loads(FP_VH.read_text(encoding="utf-8"))
    en_after = fingerprint_game(Path(en_doc["root"]))
    vh_after = fingerprint_game(Path(vh_doc["root"]))
    fp_en_bad = sum(1 for r, d in en_doc["files"].items() if en_after.get(r) != d)
    fp_vh_bad = sum(1 for r, d in vh_doc["files"].items() if vh_after.get(r) != d)

    smoke_ok = (
        file_check2["pass"]
        and not log_info.get("startgame_fail")
        and not nscripts
        and not naninovel_ser
        and int(log_info.get("exception_count") or 0) == 0
        and shots_ok >= 8
        and fp_en_bad == 0
        and fp_vh_bad == 0
        and asset_vi_evidence(game).get("ok")
    )

    # Coverage + validate
    cov_report = audit_and_fill(apply=False)
    val = validate_package(PKG, golden_mapping=OUT / "golden_mapping.csv")

    report = {
        "utc": datetime.now(timezone.utc).isoformat(),
        "csv_update": csv_info,
        "ui_only": {"rels": ui_res["output_rels"], "file_check": file_check},
        "full_patch_file_check": file_check2,
        "smoke": {
            "shots_ok": shots_ok,
            "startgame_fail": log_info.get("startgame_fail"),
            "nscripts_init_fail": nscripts,
            "naninovel_serialization": naninovel_ser,
            "exception_count": log_info.get("exception_count"),
            "asset_vi_ok": asset_vi_evidence(game).get("ok"),
            "fp_en_bad": fp_en_bad,
            "fp_vh_bad": fp_vh_bad,
            "ok": smoke_ok,
        },
        "coverage": {
            "pass": cov_report.get("pass"),
            "missing": cov_report.get("missing_need_vi"),
            "app_vi": cov_report.get("app_translated_vi"),
            "vh_total": cov_report.get("vh_translated_total"),
        },
        "local_validate": {
            "pass": val.get("pass"),
            "structural": val.get("structural"),
            "identity_bad": val.get("identity_bad"),
            "pending": val.get("pending"),
            "choice": val.get("choice_coverage"),
            "menu": val.get("menu_coverage"),
        },
        "ok": bool(
            smoke_ok
            and cov_report.get("pass")
            and val.get("pass")
            and cov_report.get("missing_need_vi") == 0
        ),
    }
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (OUT / "coverage_fill_final.json").write_text(
        json.dumps(cov_report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({"ok": report["ok"], "smoke": smoke_ok, "coverage_missing": cov_report.get("missing_need_vi"), "validate": val.get("pass")}, ensure_ascii=False), flush=True)

    # Dọn tmp nặng; giữ report
    from cleanup_work_artifacts import cleanup_after_test  # noqa: E402

    cleanup = cleanup_after_test([TMP], reason="defaultui_chrome_post_test", outcome="PASS" if report["ok"] else "FAIL")
    report["cleanup"] = cleanup
    if not cleanup.get("ok"):
        report["ok"] = False
        REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    # xóa Player log lớn nếu cần — giữ file nhỏ
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
