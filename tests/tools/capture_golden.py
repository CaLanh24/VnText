"""Capture extract/patch golden files from the current app. Does not change app logic."""

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

import csv
import json
import os
import shutil
from pathlib import Path


from vntext_studio import CSV_FIELDS, apply_translation_package, extract_project, write_package

_GAME_FOLDER_VALUE = os.environ.get("VNTEXT_GAME_FOLDER", "").strip()
GAME_FOLDER = Path(_GAME_FOLDER_VALUE).expanduser().resolve() if _GAME_FOLDER_VALUE else None
WORK = ROOT / "tests" / "golden" / "_work"
CAPTURE_ROOT = WORK / "capture"
PACKAGE = WORK / "Unity_Translation_Package"
PATCH_OUT = WORK / "Patch_Viet_Hoa"
EXTRACT_GOLDEN = CAPTURE_ROOT / "extract"
PATCH_GOLDEN = CAPTURE_ROOT / "patch"
FILL_PREFIX = "VI:"

EXTRACT_COPY_NAMES = (
    "translation.csv",
    "raw_candidates.csv",
    "review_only.csv",
    "raw_unpatchable.csv",
    "raw_candidates_rejected.csv",
    "extract_report.txt",
    "manifest.json",
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


def _copy_existing(src_dir: Path, dest_dir: Path, names):
    dest_dir.mkdir(parents=True, exist_ok=True)
    copied = []
    for name in names:
        src = src_dir / name
        if src.exists():
            shutil.copy2(src, dest_dir / name)
            copied.append(name)
    return copied


def _write_key_index(csv_path: Path, dest: Path):
    with csv_path.open("r", encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))
    keys = sorted(row.get("key", "") for row in rows if row.get("key"))
    dest.write_text("\n".join(keys) + ("\n" if keys else ""), encoding="utf-8")
    methods = {}
    for row in rows:
        method = row.get("import_method", "") or ""
        methods[method] = methods.get(method, 0) + 1
    return len(keys), methods, rows


def _fill_plain_text_translations(src_csv: Path, dest_csv: Path) -> int:
    with src_csv.open("r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        fieldnames = list(reader.fieldnames or CSV_FIELDS)
        rows = list(reader)
    filled = 0
    for row in rows:
        if row.get("import_method") == "plain_text_line" and row.get("source_text"):
            row["translation"] = FILL_PREFIX + row["source_text"]
            filled += 1
    dest_csv.parent.mkdir(parents=True, exist_ok=True)
    with dest_csv.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    return filled


def _parse_import_counts(report_text: str) -> dict:
    counts = {}
    for line in report_text.splitlines():
        if line.startswith("patched_lines:") or line.startswith("skipped_lines:"):
            key, _, value = line.partition(":")
            counts[key.strip()] = value.strip()
    return counts


def _parse_extract_report(text: str) -> dict:
    stats: dict = {"backend_counts": {}, "method_counts": {}}
    section = None
    for raw in text.splitlines():
        line = raw.rstrip()
        if line == "backend_counts:":
            section = "backend_counts"
            continue
        if line == "method_counts:":
            section = "method_counts"
            continue
        if section and line.startswith("  "):
            name, _, value = line.strip().partition(":")
            try:
                stats[section][name.strip()] = int(value.strip())
            except ValueError:
                stats[section][name.strip()] = value.strip()
            continue
        section = None
        if ":" in line and not line.startswith("note:"):
            key, _, value = line.partition(":")
            key = key.strip()
            value = value.strip()
            if key in {
                "mode",
                "extract_level",
                "files_scanned",
                "main_entries",
                "review_entries",
                "skipped_deep_files",
                "skipped_raw_files",
                "naninovel_scanned_files",
            }:
                stats[key] = int(value) if value.isdigit() else value
    return stats


def main(from_package: Path | None = None):
    if GAME_FOLDER is None or not GAME_FOLDER.is_dir():
        raise SystemExit(f"Game folder not found: {GAME_FOLDER}")
    EXTRACT_GOLDEN.mkdir(parents=True, exist_ok=True)
    PATCH_GOLDEN.mkdir(parents=True, exist_ok=True)
    PACKAGE.mkdir(parents=True, exist_ok=True)
    for child in list(PACKAGE.iterdir()):
        if child.is_file():
            child.unlink()
        elif child.is_dir():
            shutil.rmtree(child)
    if PATCH_OUT.exists():
        shutil.rmtree(PATCH_OUT)

    if from_package is not None:
        src = Path(from_package)
        if not (src / "translation.csv").is_file() or not (src / "manifest.json").is_file():
            raise SystemExit(f"Package missing translation.csv/manifest.json: {src}")
        print(f"COPY PACKAGE {src}", flush=True)
        for name in EXTRACT_COPY_NAMES:
            item = src / name
            if item.exists():
                shutil.copy2(item, PACKAGE / name)
        copied = _copy_existing(PACKAGE, EXTRACT_GOLDEN, EXTRACT_COPY_NAMES)
        stats = _parse_extract_report((EXTRACT_GOLDEN / "extract_report.txt").read_text(encoding="utf-8"))
    else:
        print(f"EXTRACT {GAME_FOLDER}", flush=True)
        main_entries, review_entries, stats = extract_project(
            str(GAME_FOLDER),
            "deep",
            _progress,
            "balanced",
        )
        write_package(str(PACKAGE), main_entries, review_entries, stats, separate_review=True)
        copied = _copy_existing(PACKAGE, EXTRACT_GOLDEN, EXTRACT_COPY_NAMES)
    key_count, methods, _rows = _write_key_index(
        EXTRACT_GOLDEN / "translation.csv",
        EXTRACT_GOLDEN / "translation_keys.txt",
    )
    comparable = {
        "mode": stats.get("mode"),
        "extract_level": stats.get("extract_level"),
        "files_scanned": stats.get("files_scanned"),
        "main_entries": stats.get("main_entries"),
        "review_entries": stats.get("review_entries"),
        "backend_counts": stats.get("backend_counts"),
        "method_counts": stats.get("method_counts"),
        "translation_csv_keys": key_count,
        "translation_csv_methods": methods,
        "skipped_deep_files": stats.get("skipped_deep_files"),
        "skipped_raw_files": stats.get("skipped_raw_files"),
        "naninovel_scanned_files": stats.get("naninovel_scanned_files"),
    }
    (EXTRACT_GOLDEN / "stats_snapshot.json").write_text(
        json.dumps(comparable, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    filled_csv = PATCH_GOLDEN / "translation.filled.csv"
    filled = _fill_plain_text_translations(EXTRACT_GOLDEN / "translation.csv", filled_csv)
    print(f"PATCH filling {filled} plain_text_line rows", flush=True)
    apply_translation_package(
        str(filled_csv),
        str(PACKAGE / "manifest.json"),
        str(GAME_FOLDER),
        str(PATCH_OUT),
        _progress,
    )
    shutil.copy2(PATCH_OUT / "import_report.txt", PATCH_GOLDEN / "import_report.txt")
    report = (PATCH_GOLDEN / "import_report.txt").read_text(encoding="utf-8")
    patch_counts = _parse_import_counts(report)
    (PATCH_GOLDEN / "stats_snapshot.json").write_text(
        json.dumps({"filled_plain_text_rows": filled, **patch_counts}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    capture_report = CAPTURE_ROOT / "capture_summary.json"
    capture_report.write_text(
        json.dumps(
            {
                "captured": True,
                "fixture": "external VNTEXT_GAME_FOLDER",
                "package_source": str(PACKAGE),
                "extract_files": copied,
                "translation_csv_keys": key_count,
                "filled_plain_text_rows": filled,
                **patch_counts,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print("CAPTURE DONE", flush=True)
    print(json.dumps({**comparable, **patch_counts, "filled_plain_text_rows": filled}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    from_package = None
    if len(sys.argv) >= 3 and sys.argv[1] == "--from-package":
        from_package = Path(sys.argv[2])
    elif len(sys.argv) == 2:
        raise SystemExit("Usage: capture_golden.py [--from-package DIR]")
    main(from_package)
