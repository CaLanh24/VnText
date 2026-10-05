# -*- coding: utf-8 -*-

"""Phase 1: EN↔VH Naninovel Script inventory + dialogue/choice bench (50 then 500).

Does not patch game or run full play. Artifacts under TEST_RUN/nano_safe/.
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

import hashlib
import json
import struct
from collections import Counter
from pathlib import Path

import UnityPy  # noqa: E402

from sample_unity_e2e_lib import fingerprint_game  # noqa: E402
from vntext.extract import (  # noqa: E402
    _mono_script_path_id,
    _object_raw_bytes,
    _raw_looks_like_naninovel_script,
    _scan_script_object_strings,
    collect_naninovel_script_path_ids,
    iter_naninovel_display_texts,
)
from work_paths import (  # noqa: E402
    E2E_GAME_COPY,
    WORK_ROOT,
    assert_artifact_under_work,
    kill_processes_using,
    prepare_e2e_game_copy,
    register_artifact,
    resolve_game_folder,
    VH_GAME_READ_ONLY,
)

EN_ORIG = resolve_game_folder()
VH_ORIG = VH_GAME_READ_ONLY
OUT = WORK_ROOT / "nano_safe"
DATA_REL = Path("SampleGame_Data") / "data.unity3d"


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sf_invariants(path: Path) -> dict:
    """Load data.unity3d and report SerializedFile (resources.assets) invariants."""
    env = UnityPy.load(str(path))
    child = None
    for obj in env.objects:
        child = obj.assets_file
        break
    if child is None:
        raise RuntimeError(f"No SerializedFile in {path}")
    header = child.header
    original = None
    try:
        from vntext.unity_fs import _original_child_bytes

        original = _original_child_bytes(child)
    except Exception as exc:
        original = None
        err = str(exc)
    else:
        err = None
    script_pids = collect_naninovel_script_path_ids(child.objects.values())
    info = {
        "path": str(path),
        "file_size": path.stat().st_size,
        "objects": len(child.objects),
        "types": len(child.types),
        "header_version": int(header.version),
        "endian": str(header.endian),
        "data_offset": int(header.data_offset),
        "enable_type_tree": bool(getattr(child, "_enable_type_tree", False)),
        "script_monoscript_pids": sorted(script_pids),
        "child_bytes": len(original) if original is not None else None,
        "child_sha256": _sha256(original) if original is not None else None,
        "child_error": err,
    }
    if original is not None and int(header.data_offset) > 0:
        meta = original[: int(header.data_offset)]
        info["meta_sha256"] = _sha256(meta)
        info["meta_size"] = len(meta)
        # sample first grown-candidate directory entries later
    del env
    return info


def _collect_scripts(path: Path) -> dict[int, dict]:
    env = UnityPy.load(str(path))
    script_pids = collect_naninovel_script_path_ids(env.objects)
    rows: dict[int, dict] = {}
    for obj in env.objects:
        tname = str(getattr(getattr(obj, "type", None), "name", "") or "")
        if tname != "MonoBehaviour":
            continue
        sp = _mono_script_path_id(obj)
        if sp not in script_pids and not _raw_looks_like_naninovel_script(obj):
            continue
        raw = _object_raw_bytes(obj)
        texts: list[dict] = []
        for item in _scan_script_object_strings(raw):
            text = str(item.get("text") or "")
            if not text.strip():
                continue
            low = text.lstrip().lower()
            displays = list(iter_naninovel_display_texts(text))
            if not displays:
                continue
            if low.startswith("@choice"):
                role = "choice"
            elif low.startswith(("@print", "@:")) or low.startswith("@"):
                role = "dialogue"
            else:
                role = "dialogue"
            for d in displays:
                texts.append(
                    {
                        "role": role,
                        "source": d,
                        "offset": int(item.get("offset") or 0),
                        "byte_length": len(d.encode("utf-8")),
                    }
                )
        rows[int(obj.path_id)] = {
            "path_id": int(obj.path_id),
            "byte_size": int(obj.byte_size),
            "raw_len": len(raw),
            "raw_sha256": _sha256(raw),
            "script_pid": int(sp),
            "text_count": len(texts),
            "dialogue": sum(1 for t in texts if t["role"] == "dialogue"),
            "choice": sum(1 for t in texts if t["role"] == "choice"),
            "texts": texts,
        }
    del env
    return rows


def _classify(en: dict, vh: dict) -> str:
    if en["raw_sha256"] == vh["raw_sha256"]:
        return "identical"
    if en["byte_size"] == vh["byte_size"]:
        return "fit_same_size"
    if vh["byte_size"] > en["byte_size"]:
        return "must_grow"
    return "must_shrink"


def _sample_cases(en_scripts: dict, vh_scripts: dict, limit: int) -> list[dict]:
    """Build representative dialogue/choice cases from EN↔VH script pairs."""
    common = sorted(set(en_scripts) & set(vh_scripts))
    # Prefer must_grow + SGS-ish path_ids, then others
    ranked = sorted(
        common,
        key=lambda p: (
            0 if _classify(en_scripts[p], vh_scripts[p]) == "must_grow" else 1,
            -abs(vh_scripts[p]["byte_size"] - en_scripts[p]["byte_size"]),
            p,
        ),
    )
    cases: list[dict] = []
    for pid in ranked:
        en_t = {t["source"]: t for t in en_scripts[pid]["texts"] if t["role"] in {"dialogue", "choice"}}
        vh_t = {t["source"]: t for t in vh_scripts[pid]["texts"] if t["role"] in {"dialogue", "choice"}}
        # Pair by index within role for coverage target (VH text is translation)
        en_list = [t for t in en_scripts[pid]["texts"] if t["role"] in {"dialogue", "choice"}]
        vh_list = [t for t in vh_scripts[pid]["texts"] if t["role"] in {"dialogue", "choice"}]
        n = min(len(en_list), len(vh_list))
        for i in range(n):
            e, v = en_list[i], vh_list[i]
            if e["source"] == v["source"]:
                status = "keep_same"
            else:
                status = "translate"
            cases.append(
                {
                    "path_id": pid,
                    "index": i,
                    "role": e["role"],
                    "en": e["source"],
                    "vh": v["source"],
                    "en_bytes": e["byte_length"],
                    "vh_bytes": v["byte_length"],
                    "script_class": _classify(en_scripts[pid], vh_scripts[pid]),
                    "status": status,
                    "grows_string": v["byte_length"] > e["byte_length"],
                }
            )
            if len(cases) >= limit:
                return cases
    return cases


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    assert_artifact_under_work(OUT, "nano_safe")

    if not (EN_ORIG / DATA_REL).is_file() or not (VH_ORIG / DATA_REL).is_file():
        raise SystemExit("EN/VH data.unity3d missing")

    fp_en = fingerprint_game(EN_ORIG)
    (OUT / "fingerprint_en_before.json").write_text(
        json.dumps(fp_en, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    register_artifact(
        artifact_id="nano_safe_fp_en",
        path=OUT / "fingerprint_en_before.json",
        kind="fingerprint",
        created_by="bench_naninovel_en_vh",
        purpose="nano_safe_en",
    )

    print("Preparing clean game_copy from EN...", flush=True)
    copy = prepare_e2e_game_copy(label="nano_safe_bench", mode="reset")
    fp_copy = fingerprint_game(copy)
    (OUT / "fingerprint_game_copy.json").write_text(
        json.dumps(fp_copy, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    print("SerializedFile invariants...", flush=True)
    inv_en = _sf_invariants(EN_ORIG / DATA_REL)
    inv_vh = _sf_invariants(VH_ORIG / DATA_REL)
    inv = {
        "en": inv_en,
        "vh": inv_vh,
        "same_object_count": inv_en["objects"] == inv_vh["objects"],
        "same_data_offset": inv_en["data_offset"] == inv_vh["data_offset"],
        "same_meta_sha": inv_en.get("meta_sha256") == inv_vh.get("meta_sha256"),
        "child_size_delta": (inv_vh.get("child_bytes") or 0) - (inv_en.get("child_bytes") or 0),
        "file_size_delta": inv_vh["file_size"] - inv_en["file_size"],
    }
    (OUT / "serializedfile_invariants.json").write_text(
        json.dumps(inv, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({k: inv[k] for k in inv if k not in {"en", "vh"}}, ensure_ascii=False), flush=True)

    print("Collecting EN scripts...", flush=True)
    en_scripts = _collect_scripts(EN_ORIG / DATA_REL)
    print("Collecting VH scripts...", flush=True)
    vh_scripts = _collect_scripts(VH_ORIG / DATA_REL)

    common = sorted(set(en_scripts) & set(vh_scripts))
    classes = Counter(_classify(en_scripts[p], vh_scripts[p]) for p in common)
    inventory = []
    for p in common:
        c = _classify(en_scripts[p], vh_scripts[p])
        inventory.append(
            {
                "path_id": p,
                "class": c,
                "en_size": en_scripts[p]["byte_size"],
                "vh_size": vh_scripts[p]["byte_size"],
                "delta": vh_scripts[p]["byte_size"] - en_scripts[p]["byte_size"],
                "en_dialogue": en_scripts[p]["dialogue"],
                "en_choice": en_scripts[p]["choice"],
                "vh_dialogue": vh_scripts[p]["dialogue"],
                "vh_choice": vh_scripts[p]["choice"],
                "en_sha": en_scripts[p]["raw_sha256"][:16],
                "vh_sha": vh_scripts[p]["raw_sha256"][:16],
            }
        )
    inventory.sort(key=lambda r: (-abs(r["delta"]), r["path_id"]))
    inv_path = OUT / "script_inventory.json"
    inv_path.write_text(
        json.dumps(
            {
                "en_count": len(en_scripts),
                "vh_count": len(vh_scripts),
                "common": len(common),
                "classes": dict(classes),
                "scripts": inventory,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    register_artifact(
        artifact_id="nano_safe_inventory",
        path=inv_path,
        kind="report",
        created_by="bench_naninovel_en_vh",
        purpose="nano_safe_inventory",
    )
    print("inventory", dict(classes), "common", len(common), flush=True)

    cases50 = _sample_cases(en_scripts, vh_scripts, 50)
    cases500 = _sample_cases(en_scripts, vh_scripts, 500)
    for name, cases in (("cases_50", cases50), ("cases_500", cases500)):
        translate = sum(1 for c in cases if c["status"] == "translate")
        grow = sum(1 for c in cases if c["grows_string"])
        roles = Counter(c["role"] for c in cases)
        doc = {
            "count": len(cases),
            "translate": translate,
            "keep_same": sum(1 for c in cases if c["status"] == "keep_same"),
            "grows_string": grow,
            "roles": dict(roles),
            "script_classes": dict(Counter(c["script_class"] for c in cases)),
            "cases": cases,
        }
        p = OUT / f"{name}.json"
        p.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        register_artifact(
            artifact_id=f"nano_safe_{name}",
            path=p,
            kind="report",
            created_by="bench_naninovel_en_vh",
            purpose=f"nano_safe_{name}",
        )
        print(name, {k: doc[k] for k in doc if k != "cases"}, flush=True)

    # Directory sample for top grow scripts (byte_start/size EN vs VH)
    print("Directory sample for top growers...", flush=True)
    growers = [r["path_id"] for r in inventory if r["class"] == "must_grow"][:5]

    def dir_map(path: Path, pids: list[int]) -> dict:
        env = UnityPy.load(str(path))
        out = {}
        for obj in env.objects:
            if int(obj.path_id) in pids:
                out[int(obj.path_id)] = {
                    "byte_start": int(obj.byte_start),
                    "byte_size": int(obj.byte_size),
                }
        del env
        return out

    dir_cmp = {"en": dir_map(EN_ORIG / DATA_REL, growers), "vh": dir_map(VH_ORIG / DATA_REL, growers)}
    (OUT / "directory_sample_grow.json").write_text(
        json.dumps(dir_cmp, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    summary = {
        "fingerprint_en_ok": bool(fp_en),
        "game_copy": str(copy),
        "script_classes": dict(classes),
        "cases_50": len(cases50),
        "cases_500": len(cases500),
        "cases_50_translate": sum(1 for c in cases50 if c["status"] == "translate"),
        "cases_500_translate": sum(1 for c in cases500 if c["status"] == "translate"),
        "same_meta": inv["same_meta_sha"],
        "child_size_delta": inv["child_size_delta"],
        "data_offset_en": inv_en["data_offset"],
        "data_offset_vh": inv_vh["data_offset"],
        "enable_type_tree_en": inv_en["enable_type_tree"],
        "enable_type_tree_vh": inv_vh["enable_type_tree"],
    }
    (OUT / "bench_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print("SUMMARY", json.dumps(summary, ensure_ascii=False), flush=True)
    return 0 if len(cases50) >= 50 and len(cases500) >= 500 else 2


if __name__ == "__main__":
    raise SystemExit(main())
