"""Capture a Unity patch baseline on COPIES of golden game files.

Never writes into the original game folder. Does not change app logic.
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

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path


from unity_patch_baseline import (
    EXTRACT_GOLDEN,
    FILL_PREFIX,
    GAME_COPY,
    PATCH_OUT,
    PATCH_UNITY_GOLDEN as EXPECTED_PATCH_UNITY_GOLDEN,
    WORK,
    assert_path_outside_game,
    collect_unity_rel_paths,
    copy_game_files,
    extra_support_rel_paths,
    fill_unity_translations,
    hash_game_files,
    inspect_patched_file,
    list_output_files,
    baseline_provenance,
    origin_asset_hash_keys,
    parse_import_counts,
    read_game_folder,
)


def _progress(info):
    if not isinstance(info, dict):
        print(info, flush=True)
        return
    print(
        f"PROGRESS {info.get('phase', '')} {info.get('done', 0)}/{info.get('total', 0)} "
        f"| {info.get('file', '')}",
        flush=True,
    )


def main(reuse_output: bool = False) -> Path:
    # Expected golden is read-only; every capture is an actual observation.
    from work_paths import E2E_GAME_COPY, assert_artifact_under_work, processes_using
    GAME_COPY = E2E_GAME_COPY
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
    PATCH_UNITY_GOLDEN = WORK / ("actual_" + stamp)
    assert_artifact_under_work(PATCH_UNITY_GOLDEN, "Unity actual capture")
    assert_artifact_under_work(PATCH_OUT, "Unity patch output")
    if processes_using(GAME_COPY):
        raise RuntimeError("canonical game copy is in use; close it before capture")
    game_folder = read_game_folder()
    if not game_folder.is_dir():
        raise SystemExit(f"Game folder not found: {game_folder}")

    assert_path_outside_game(WORK, game_folder, "work dir")
    assert_path_outside_game(PATCH_UNITY_GOLDEN, game_folder, "baseline dir")

    translation_csv = EXTRACT_GOLDEN / "translation.csv"
    manifest_src = EXTRACT_GOLDEN / "manifest.json"
    if not translation_csv.is_file() or not manifest_src.is_file():
        raise SystemExit("Missing golden extract translation.csv / manifest.json")

    unity_rels = collect_unity_rel_paths(translation_csv)
    support_rels = extra_support_rel_paths(unity_rels)
    copy_rels = list(dict.fromkeys(unity_rels + support_rels))
    if not unity_rels:
        raise SystemExit("No Unity files listed in golden translation.csv")

    print("HASH originals before copy", flush=True)
    original_before = hash_game_files(game_folder, copy_rels)

    report_path = PATCH_OUT / "import_report.txt"
    patched_root = PATCH_OUT / "COPY_TO_GAME_ROOT"
    can_reuse = reuse_output and report_path.is_file() and patched_root.is_dir()
    if can_reuse:
        print(f"REUSE existing patch output {PATCH_OUT}", flush=True)
        if not GAME_COPY.is_dir():
            GAME_COPY.mkdir(parents=True, exist_ok=True)
            copy_game_files(game_folder, GAME_COPY, copy_rels)
        copied = copy_rels
    else:
        if PATCH_OUT.exists():
            PATCH_OUT.rename(WORK / ("previous_patch_out_" + stamp))
        GAME_COPY.mkdir(parents=True, exist_ok=True)
        PATCH_OUT.mkdir(parents=True, exist_ok=True)
        print(f"COPY {len(copy_rels)} files into {GAME_COPY}", flush=True)
        copied = copy_game_files(game_folder, GAME_COPY, copy_rels)

    PATCH_UNITY_GOLDEN.mkdir(parents=True, exist_ok=True)
    filled_csv = PATCH_UNITY_GOLDEN / "translation.unity_filled.csv"
    filled = fill_unity_translations(translation_csv, filled_csv)
    print(f"FILL {filled} Unity translation rows", flush=True)

    if not can_reuse:
        from vntext_studio import apply_translation_package

        print(f"PATCH game_root={GAME_COPY} output={PATCH_OUT}", flush=True)
        apply_translation_package(
            str(filled_csv),
            str(manifest_src),
            str(GAME_COPY),
            str(PATCH_OUT),
            _progress,
        )

    print("HASH originals after patch", flush=True)
    original_after = hash_game_files(game_folder, copy_rels)
    if original_after != original_before:
        raise SystemExit("FAIL: original golden game files changed during patch capture")

    copy_after = hash_game_files(GAME_COPY, copy_rels)
    if not report_path.is_file():
        raise SystemExit("FAIL: import_report.txt was not created")
    report_text = report_path.read_text(encoding="utf-8")
    shutil.copy2(report_path, PATCH_UNITY_GOLDEN / "import_report.txt")

    output_rels = list_output_files(patched_root)
    inspections = {}
    for rel in output_rels:
        path = patched_root / rel
        print(f"OPEN {rel}", flush=True)
        inspections[rel.replace("\\", "/")] = inspect_patched_file(path)

    unity_inspections = {rel: info for rel, info in inspections.items() if info.get("kind") == "unity"}
    if not unity_inspections:
        raise SystemExit("FAIL: patch output has no Unity files")
    header_bad = [
        rel for rel, info in unity_inspections.items() if not info.get("unityfs_header_ok")
    ]
    if header_bad:
        raise SystemExit(f"FAIL: patched Unity files missing UnityFS header: {header_bad}")
    enumerable = [rel for rel, info in unity_inspections.items() if info.get("objects_enumerable")]
    if not enumerable:
        raise SystemExit("FAIL: no patched Unity file reloaded with objects")

    counts = parse_import_counts(report_text)
    snapshot = {
        "captured_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "game_folder": str(game_folder),
        "game_root_used": str(GAME_COPY),
        "output_dir": str(PATCH_OUT),
        "filled_unity_rows": filled,
        "copied_files": copied,
        "original_files_unchanged": True,
        "copy_source_hashes_unchanged": copy_after == original_before,
        "patched_lines": counts.get("patched_lines", ""),
        "skipped_lines": counts.get("skipped_lines", ""),
        "duplicate_locations_patched_or_attempted": counts.get(
            "duplicate_locations_patched_or_attempted", ""
        ),
        "output_files": output_rels,
        "unity_files_with_objects": enumerable,
        "original_hashes": original_before,
        "copy_hashes_after_patch": copy_after,
        "patched_inspections": inspections,
    }
    expected_snapshot = json.loads(
        (EXPECTED_PATCH_UNITY_GOLDEN / "stats_snapshot.json").read_text(
            encoding="utf-8"
        )
    )
    expected_hashes = expected_snapshot.get("original_hashes") or {}
    hash_keys = origin_asset_hash_keys(expected_hashes)
    original_hashes_match = all(
        original_before.get(key) == expected_hashes.get(key) for key in hash_keys
    )
    snapshot["baseline_provenance"] = baseline_provenance(
        expected_snapshot, snapshot, original_hashes_match=original_hashes_match
    )
    (PATCH_UNITY_GOLDEN / "stats_snapshot.json").write_text(
        json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (PATCH_UNITY_GOLDEN / "original_hashes.json").write_text(
        json.dumps(original_before, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    object_notes = []
    for rel, info in sorted(unity_inspections.items()):
        object_notes.append(
            f"  {rel}: objects={info.get('object_count')} "
            f"sample_readable={info.get('sample_readable')} size={info.get('size')}"
        )
    (PATCH_UNITY_GOLDEN / "README.txt").write_text(
        "\n".join(
            [
                "Unity patch-on-copy safety baseline",
                "===================================",
                "",
                "This baseline runs apply_translation_package against COPIES of golden",
                "Unity/game files. The original game folder is never used as output.",
                "",
                "Filled methods: Unity TextAsset / UI / TypeTree / Naninovel script rows",
                f"with prefix {FILL_PREFIX!r}. Plain-text rows stay empty so this mốc is",
                "independent from tests/golden/patch/ (plain_text only).",
                "",
                "Working copies live in TEST_RUN/unity_patch/ (gitignored).",
                "Recorded mốc files in this folder are the freeze point before moving patch.",
                "",
                "Current UnityPy reload notes (do not 'fix' during the refactor):",
                *object_notes,
                "",
                f"CAPTURED=yes",
                f"ORIGINAL_GAME_UNCHANGED=yes",
                f"UNITYFS_HEADER_OK=yes",
                f"UNITY_FILES_WITH_OBJECTS={', '.join(enumerable)}",
                f"FILLED_UNITY_ROWS={filled}",
                f"PATCHED_LINES={counts.get('patched_lines', '')}",
                f"SKIPPED_LINES={counts.get('skipped_lines', '')}",
                f"OUTPUT_FILES={', '.join(output_rels)}",
                "",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    print("CAPTURE DONE", flush=True)
    print(
        json.dumps(
            {
                "filled_unity_rows": filled,
                "patched_lines": counts.get("patched_lines", ""),
                "skipped_lines": counts.get("skipped_lines", ""),
                "original_files_unchanged": True,
                "unity_files_with_objects": enumerable,
            },
            ensure_ascii=False,
        ),
        flush=True,
    )
    return PATCH_UNITY_GOLDEN


if __name__ == "__main__":
    reuse = "--reuse-output" in sys.argv
    main(reuse_output=reuse)
