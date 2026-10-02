"""Generic safety helpers for isolated Unity resource tests."""

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
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

UNITY_SUFFIXES = {".assets", ".bundle", ".unity3d", ".sharedassets"}
UNITY_FILL_METHODS = {
    "unity_textasset_line",
    "unity_textasset_table_cell",
    "unity_textasset_script",
    "unity_ui_text",
    "unity_typetree_field",
    "naninovel_script_string",
}


def read_game_folder() -> Path:
    from work_paths import resolve_game_folder

    return resolve_game_folder()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def source_revision() -> str:
    """Return the checkout revision used for an actual capture."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise RuntimeError(f"cannot resolve source revision: {exc}") from exc
    return result.stdout.strip()


def assert_path_outside_game(path: Path, game_folder: Path, label: str) -> None:
    resolved = path.resolve()
    game = game_folder.resolve()
    if resolved == game or game in resolved.parents:
        raise RuntimeError(f"{label} must not be inside the source folder: {resolved}")


def collect_unity_rel_paths(translation_csv: Path) -> list[str]:
    found: dict[str, None] = {}
    with translation_csv.open("r", encoding="utf-8-sig", newline="") as fh:
        for row in csv.DictReader(fh):
            rel = (row.get("file_path") or "").strip()
            if not rel:
                continue
            suffix = Path(rel).suffix.lower()
            if suffix in UNITY_SUFFIXES:
                found[rel] = None
    return list(found)


def extra_support_rel_paths(unity_rels: list[str]) -> list[str]:
    from vntext.addressables import addressables_catalog_rel

    extras: dict[str, None] = {}
    for rel in unity_rels:
        catalog = addressables_catalog_rel(rel)
        if catalog is not None:
            extras[str(catalog)] = None
    return list(extras)


def hash_game_files(game_folder: Path, rels: list[str]) -> dict[str, dict]:
    """Hash explicit files from an immutable source root."""
    out = {}
    for rel in rels:
        src = game_folder / rel
        info = {"exists": src.is_file(), "size": src.stat().st_size if src.is_file() else 0}
        if src.is_file():
            info["sha256"] = sha256_file(src)
        out[rel.replace("\\", "/")] = info
    return out


def origin_asset_hash_keys(recorded: dict) -> list[str]:
    """Filter catalog metadata from recorded source content hashes."""
    keys: list[str] = []
    for key in recorded:
        normalized = str(key).replace("\\", "/")
        if normalized.endswith("aa/catalog.json"):
            continue
        keys.append(key)
    return keys


def copy_game_files(game_folder: Path, dest_root: Path, rels: list[str]) -> list[str]:
    from work_paths import assert_write_destination

    assert_write_destination(dest_root, "copy_game_files")
    copied = []
    for rel in rels:
        src = game_folder / rel
        if not src.is_file():
            raise FileNotFoundError(f"Golden game file missing: {src}")
        dest = dest_root / rel
        assert_write_destination(dest, f"copy_game_files {rel}")
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
        copied.append(rel)
    return copied


def fill_unity_translations(src_csv: Path, dest_csv: Path) -> int:
    from work_paths import assert_write_destination

    assert_write_destination(dest_csv, "fill_unity_translations")
    with src_csv.open("r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        fieldnames = list(reader.fieldnames or [])
        rows = list(reader)
    filled = 0
    for row in rows:
        method = row.get("import_method") or ""
        source = row.get("source_text") or ""
        if method in UNITY_FILL_METHODS and source:
            row["translation"] = "VI:" + source
            filled += 1
    dest_csv.parent.mkdir(parents=True, exist_ok=True)
    with dest_csv.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    return filled


def parse_import_counts(report_text: str) -> dict[str, str]:
    counts = {}
    for line in report_text.splitlines():
        if line.startswith("patched_lines:") or line.startswith("skipped_lines:"):
            key, _, value = line.partition(":")
            counts[key.strip()] = value.strip()
        if line.startswith("duplicate_locations_patched_or_attempted:"):
            key, _, value = line.partition(":")
            counts[key.strip()] = value.strip()
    return counts


def list_output_files(patched_root: Path) -> list[str]:
    if not patched_root.is_dir():
        return []
    rels = []
    for path in sorted(patched_root.rglob("*")):
        if path.is_file():
            rels.append(str(path.relative_to(patched_root)).replace("/", "\\"))
    return rels


def inspect_patched_file(path: Path) -> dict:
    info: dict = {
        "size": path.stat().st_size,
        "sha256": sha256_file(path),
        "openable": False,
        "objects_enumerable": False,
        "kind": "other",
    }
    suffix = path.suffix.lower()
    if suffix == ".json":
        info["kind"] = "json"
        json.loads(path.read_text(encoding="utf-8-sig"))
        info["openable"] = True
        return info
    if suffix in UNITY_SUFFIXES:
        info["kind"] = "unity"
        header = path.read_bytes()[:8]
        info["magic"] = header[:7].decode("ascii", "replace")
        info["unityfs_header_ok"] = info["magic"] == "UnityFS"
        import UnityPy
        import gc

        env = UnityPy.load(str(path))
        try:
            objects = list(env.objects)
            info["object_count"] = len(objects)
            readable = 0
            errors = []
            for obj in objects[:32]:
                try:
                    obj.read()
                    readable += 1
                except Exception as exc:
                    errors.append(f"{getattr(getattr(obj, 'type', None), 'name', '')}:{getattr(obj, 'path_id', '')}:{exc}")
            info["sample_readable"] = readable
            info["sample_errors"] = errors[:5]
            info["objects_enumerable"] = info["object_count"] > 0
            info["openable"] = bool(info["unityfs_header_ok"])
            return info
        finally:
            env = None
            objects = None
            gc.collect()
    info["kind"] = "bytes"
    info["openable"] = info["size"] > 0
    return info
