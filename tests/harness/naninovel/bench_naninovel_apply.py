# -*- coding: utf-8 -*-

"""Apply Naninovel VH Script blobs (coverage) via safe rewriter; bench 50 then 500."""

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

import gc
import hashlib
import json
import re
import shutil
from collections import Counter
from pathlib import Path

import UnityPy  # noqa: E402

from vntext.extract import (  # noqa: E402
    _mono_script_path_id,
    _naninovel_command_role,
    _object_raw_bytes,
    _raw_looks_like_naninovel_script,
    _scan_script_object_strings,
    collect_naninovel_script_path_ids,
    iter_naninovel_display_texts,
    looks_like_code_or_asset_token,
)
from vntext.patch import save_unity_env  # noqa: E402
from vntext.unity_fs import _original_child_bytes  # noqa: E402
from work_paths import (  # noqa: E402
    E2E_GAME_COPY,
    WORK_ROOT,
    kill_processes_using,
    prepare_e2e_game_copy,
    register_artifact,
    resolve_game_folder,
    VH_GAME_READ_ONLY,
)

EN = resolve_game_folder()
VH = VH_GAME_READ_ONLY
OUT = WORK_ROOT / "nano_safe"
BLOB_DIR = OUT / "vh_script_blobs"
DATA_REL = Path("SampleGame_Data") / "data.unity3d"
VI_RX = re.compile(
    r"[àáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđ]",
    re.I,
)
INV = OUT / "script_inventory.json"


def _resources(env):
    return list(env.files.values())[0].files["resources.assets"]


def _is_player_line(d: str) -> bool:
    if not d or looks_like_code_or_asset_token(d):
        return False
    if len(d) < 12:
        return False
    if d.casefold() in {"tip", "tips", "return", "start", "stop"}:
        return False
    if "." in d and " " not in d:
        return False
    if d.startswith(("B_", "AB_", "nScripts/", "Assets/", "Naninovel.")):
        return False
    return (" " in d and (d[:1].isalpha() or d[:1] in "\"'(<")) or "[br]" in d.lower()


def _script_displays(raw: bytes) -> list[dict]:
    rows = []
    seen = set()
    for item in _scan_script_object_strings(raw):
        text = str(item.get("text") or "").strip()
        if not text:
            continue
        role = _naninovel_command_role(text)
        displays = list(iter_naninovel_display_texts(text))
        if not displays:
            continue
        for d in displays:
            if not _is_player_line(d) or d in seen:
                continue
            seen.add(d)
            r = "choice" if role == "choice" else "dialogue"
            rows.append({"role": r, "text": d})
    return rows


def _export_vh_blobs(pids: list[int]) -> dict[int, Path]:
    BLOB_DIR.mkdir(parents=True, exist_ok=True)
    env = UnityPy.load(str(VH / DATA_REL))
    script_pids = collect_naninovel_script_path_ids(env.objects)
    want = set(pids)
    out: dict[int, Path] = {}
    for obj in env.objects:
        pid = int(obj.path_id)
        if pid not in want:
            continue
        tname = str(getattr(getattr(obj, "type", None), "name", "") or "")
        if tname != "MonoBehaviour":
            continue
        sp = _mono_script_path_id(obj)
        if sp not in script_pids and not _raw_looks_like_naninovel_script(obj):
            continue
        raw = _object_raw_bytes(obj)
        path = BLOB_DIR / f"{pid}.bin"
        path.write_bytes(raw)
        out[pid] = path
    del env
    gc.collect()
    return out


def _build_cases(en_raw: dict[int, bytes], vh_raw: dict[int, bytes], limit: int) -> list[dict]:
    """Coverage cases = VH player-facing VI lines absent from EN (true translations)."""
    cases = []
    for pid in sorted(set(en_raw) & set(vh_raw)):
        en_set = {r["text"] for r in _script_displays(en_raw[pid])}
        for v in _script_displays(vh_raw[pid]):
            if not VI_RX.search(v["text"]):
                continue
            if v["text"] in en_set:
                continue
            cases.append(
                {
                    "path_id": pid,
                    "role": v["role"],
                    "en": "",
                    "vh": v["text"],
                }
            )
            if len(cases) >= limit:
                return cases
    return cases


def _apply_blobs_to_copy(game: Path, blob_paths: dict[int, Path]) -> dict:
    env = UnityPy.load(str(game / DATA_REL))
    hit = 0
    for obj in env.objects:
        pid = int(obj.path_id)
        if pid not in blob_paths:
            continue
        obj.set_raw_data(blob_paths[pid].read_bytes())
        hit += 1
    staged = OUT / "data_apply_vh_scripts.unity3d"
    save_unity_env(env, staged)
    del env
    gc.collect()
    shutil.copy2(staged, game / DATA_REL)
    # verify sizes
    env2 = UnityPy.load(str(game / DATA_REL))
    res = _resources(env2)
    raw = _original_child_bytes(res)
    verified = 0
    for obj in res.objects.values():
        pid = int(obj.path_id)
        if pid in blob_paths and int(obj.byte_size) == blob_paths[pid].stat().st_size:
            verified += 1
    report = {
        "applied": hit,
        "verified_size": verified,
        "resources_bytes": len(raw),
        "resources_sha256": hashlib.sha256(raw).hexdigest()[:32],
    }
    del env2, res, raw
    gc.collect()
    return report


def _coverage(cases: list[dict], patched_raw: dict[int, bytes]) -> dict:
    ok = 0
    missing = []
    structural = 0
    for c in cases:
        raw = patched_raw.get(c["path_id"])
        if not raw:
            missing.append({"path_id": c["path_id"], "reason": "no_object"})
            continue
        # VH text must appear as UTF-8 substring (AlignedString payload)
        needle = c["vh"].encode("utf-8")
        if needle in raw:
            ok += 1
        else:
            missing.append({"path_id": c["path_id"], "vh": c["vh"][:80], "en": c["en"][:80]})
        # garbage: replacement left EN when should be VI
        if c["en"].encode("utf-8") in raw and needle not in raw:
            structural += 1
    return {
        "total": len(cases),
        "hit": ok,
        "miss": len(missing),
        "coverage": (ok / len(cases)) if cases else 0.0,
        "structural_miss_sample": missing[:20],
        "structural_flag": structural,
    }


def _load_patched_scripts(game: Path, pids: set[int]) -> dict[int, bytes]:
    env = UnityPy.load(str(game / DATA_REL))
    out = {}
    for obj in env.objects:
        pid = int(obj.path_id)
        if pid in pids:
            out[pid] = _object_raw_bytes(obj)
    del env
    gc.collect()
    return out


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    inv = json.loads(INV.read_text(encoding="utf-8"))
    # All scripts that differ (need VH blob)
    pids = [int(s["path_id"]) for s in inv["scripts"] if s["class"] != "identical"]
    print(f"Export VH blobs for {len(pids)} scripts...", flush=True)
    blob_paths = _export_vh_blobs(pids)
    print(f"exported={len(blob_paths)}", flush=True)

    # Load EN+VH raw for case building (from blobs + EN load once)
    print("Load EN script raw for cases...", flush=True)
    env_en = UnityPy.load(str(EN / DATA_REL))
    en_raw = {}
    for obj in env_en.objects:
        pid = int(obj.path_id)
        if pid in blob_paths:
            en_raw[pid] = _object_raw_bytes(obj)
    del env_en
    gc.collect()
    vh_raw = {pid: p.read_bytes() for pid, p in blob_paths.items()}

    cases50 = _build_cases(en_raw, vh_raw, 50)
    cases500 = _build_cases(en_raw, vh_raw, 500)
    print(
        f"cases50={len(cases50)} roles={dict(Counter(c['role'] for c in cases50))} "
        f"cases500={len(cases500)} roles={dict(Counter(c['role'] for c in cases500))}",
        flush=True,
    )
    (OUT / "apply_cases_50.json").write_text(
        json.dumps({"count": len(cases50), "cases": cases50}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (OUT / "apply_cases_500.json").write_text(
        json.dumps({"count": len(cases500), "cases": cases500}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    kill_processes_using(E2E_GAME_COPY)
    copy = prepare_e2e_game_copy(label="nano_apply_vh", mode="reset")
    print("Apply VH script blobs...", flush=True)
    apply_rep = _apply_blobs_to_copy(copy, blob_paths)
    print(json.dumps(apply_rep, ensure_ascii=False), flush=True)

    need_pids = {c["path_id"] for c in cases500}
    patched = _load_patched_scripts(copy, need_pids)
    cov50 = _coverage(cases50, patched)
    cov500 = _coverage(cases500, patched)
    report = {
        "apply": apply_rep,
        "exported_blobs": len(blob_paths),
        "coverage_50": {k: cov50[k] for k in cov50 if k != "structural_miss_sample"},
        "coverage_500": {k: cov500[k] for k in cov500 if k != "structural_miss_sample"},
        "miss_sample_50": cov50["structural_miss_sample"][:10],
        "miss_sample_500": cov500["structural_miss_sample"][:10],
    }
    (OUT / "apply_coverage_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    register_artifact(
        artifact_id="nano_apply_coverage",
        path=OUT / "apply_coverage_report.json",
        kind="report",
        created_by="bench_naninovel_apply",
        purpose="nano_safe_apply",
    )
    print("COVERAGE", json.dumps(report["coverage_50"], ensure_ascii=False), json.dumps(report["coverage_500"], ensure_ascii=False), flush=True)

    ok = (
        len(cases50) >= 50
        and len(cases500) >= 500
        and cov50["coverage"] >= 0.98
        and cov500["coverage"] >= 0.98
        and apply_rep["verified_size"] == apply_rep["applied"]
    )
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
