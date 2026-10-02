"""Non-shipping synthetic coverage helper for generic Unity capability probes.

This module is retained for harness compatibility. It never supplies a bundled
game, corpus, or reference translation; real-game execution is opt-in through
the external fixture contract in ``tests/lib/work_paths.py``.
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

import csv
import json
import shutil
import unicodedata
from pathlib import Path


from unity_patch_baseline import (
    EXTRACT_GOLDEN,
    PATCH_UNITY_GOLDEN,
    assert_path_outside_game,
    hash_game_files,
    read_game_folder,
)
from work_paths import (
    COVERAGE_EVIDENCE,
    E2E_GAME_COPY,
    FILE_ROUNDTRIP_STAGING,
    EXTERNAL_GAME_ROOT,
    UNTRUSTED_EXTERNAL_NAMES,
    WORK_ROOT,
    assert_artifact_under_work,
    assert_write_destination,
    external_reject_path,
    safe_robocopy,
)

GOLDEN = ROOT / "tests" / "golden" / "coverage"
WORK = COVERAGE_EVIDENCE
FILE_ROUNDTRIP_WORK = FILE_ROUNDTRIP_STAGING

# External paths below are rejection-only sentinels; they are never copied or written.
R1_COPY = external_reject_path("fixture-copy-a")
R2_COPY = external_reject_path("fixture-copy-b")
R3_COPY = external_reject_path("fixture-copy-c")
R4_COPY = EXTERNAL_GAME_ROOT / "fixture-copy-r4"
R5_COPY = EXTERNAL_GAME_ROOT / "fixture-copy-r5"
R6_COPY = EXTERNAL_GAME_ROOT / "fixture-copy-r6"
R7_COPY = EXTERNAL_GAME_ROOT / "fixture-copy-r7"
NANO_COPY = EXTERNAL_GAME_ROOT / "fixture-copy-naninovel"
HUD_COPY = E2E_GAME_COPY
TITLEUI_ASCII_COPY = EXTERNAL_GAME_ROOT / "fixture-copy-ui"
ADDR_COPY = EXTERNAL_GAME_ROOT / "fixture-copy-addressables"

REJECTED_EXTERNAL_COPY_NAMES = frozenset(
    path.name
    for path in (
        R1_COPY,
        R2_COPY,
        R3_COPY,
        R4_COPY,
        R5_COPY,
        R6_COPY,
        R7_COPY,
        NANO_COPY,
        TITLEUI_ASCII_COPY,
        ADDR_COPY,
    )
)

R1_KEY = "0000000000000001"
R2_KEY = "0000000000000002"
R3_KEY = "0000000000000003"
R4_KEY = "0000000000000004"
R5_KEY = "0000000000000005"
R6_KEY = "0000000000000006"
R7_KEY = "0000000000000007"
R7_FORBIDDEN_CREDIT_BUNDLE_KEY = "0000000000000008"

R1_MARKER = unicodedata.normalize("NFC", "Nhãn mẫu")
R2_MARKER = unicodedata.normalize("NFC", "Nội dung mẫu\nTùy chọn mẫu")
R3_MARKER = unicodedata.normalize("NFC", "Nút mẫu")
R4_MARKER = unicodedata.normalize("NFC", "Cài đặt mẫu")
R5_MARKER = unicodedata.normalize("NFC", "Câu mẫu phải không?")
R6_MARKER = unicodedata.normalize("NFC", "Văn bản mẫu | Hệ thống | Bản dịch mẫu.")
R7_MARKER = unicodedata.normalize("NFC", "Chế độ mẫu:")
NANO_MARKER = unicodedata.normalize("NFC", "Bạn đã sẵn sàng chưa?")

R1_SOURCE = "Example label"
R2_SOURCE = "Example\nOption"
R2_GO_NAME = "Example Setting"
R3_SOURCE = "START EXAMPLE"
R4_SOURCE = "EXAMPLE SETTINGS"
R5_SOURCE = "Example sentence, is this a test?"
R6_SOURCE = "Example text | System | Example translated text"
R6_ASSET_NAME = "ExampleTextAsset"
R5_REL = r"ExampleGame_Data\StreamingAssets\text\example.txt"
R7_SOURCE = "Example mode:"
NANO_SOURCE = "Is this an example?"
R7_PATH_ID = 8  # synthetic fixture identity; never a production locator
R7_BUNDLE_REL = r"ExampleGame_Data\StreamingAssets\aa\StandaloneWindows\example.bundle"
EXPECTED_BUNDLE_OBJECT_COUNT = 3

# Fixture path_ids — TEST/GOLDEN ONLY.
R1_CREDIT_PATH_ID = 1
R3_DEFAULTUI_PATH_ID = 2

FORBIDDEN_PROD_PATH_ID_LITERALS = (
    str(R1_CREDIT_PATH_ID),
    str(R3_DEFAULTUI_PATH_ID),
    "5218",
)

FORBIDDEN_SEED_NAMES = REJECTED_EXTERNAL_COPY_NAMES | frozenset(UNTRUSTED_EXTERNAL_NAMES)

WATCH_RELS = [
    r"ExampleGame.exe",
    r"ExampleGame_Data\data.unity3d",
    r"ExampleGame_Data\StreamingAssets\aa\catalog.json",
    r"ExampleGame_Data\StreamingAssets\aa\StandaloneWindows\example.bundle",
    r"ExampleGame_Data\StreamingAssets\text\example.txt",
]

EXPECTED_OBJECT_COUNT = 3
TITLEUI_ADDED_KEYS = (
    "0000000000000001",
    "0000000000000002",
    "0000000000000009",
    "000000000000000a",
)
RAW_EXTRACT_ONLY_METHODS = (
    "naninovel_raw_candidate",
    "naninovel_blob_string",
    "raw_fixed_slot",
)


def has_vietnamese_diacritic(text: str) -> bool:
    normalized = unicodedata.normalize("NFC", text or "")
    if any("\u0300" <= ch <= "\u036f" for ch in unicodedata.normalize("NFD", normalized)):
        return True
    return any(
        ch in "áàảãạăắằẳẵặâấầẩẫậéèẻẽẹêếềểễệíìỉĩịóòỏõọôốồổỗộơớờởỡợúùủũụưứừửữựýỳỷỹỵđ"
        "ÁÀẢÃẠĂẮẰẲẴẶÂẤẦẨẪẬÉÈẺẼẸÊẾỀỂỄỆÍÌỈĨỊÓÒỎÕỌÔỐỒỔỖỘƠỚỜỞỠỢÚÙỦŨỤƯỨỪỬỮỰÝỲỶỸỴĐ"
        for ch in normalized
    )


def assert_marker_vietnamese(marker: str, label: str) -> None:
    marker = unicodedata.normalize("NFC", marker)
    if not has_vietnamese_diacritic(marker):
        raise AssertionError(f"{label} marker must contain Vietnamese diacritics: {marker!r}")
    ascii_forbidden = ("[TUI]", "[ISO]", "VI:")
    if any(token in marker for token in ascii_forbidden):
        raise AssertionError(f"{label} must not use ASCII 003/001 markers: {marker!r}")


def coverage_work_dir() -> Path:
    game = read_game_folder()
    assert_path_outside_game(WORK, game, "coverage work dir")
    assert_artifact_under_work(WORK, "coverage work dir")
    WORK.mkdir(parents=True, exist_ok=True)
    return WORK


def file_roundtrip_case_dir(case_id: str) -> Path:
    dest = FILE_ROUNDTRIP_WORK / case_id
    game = read_game_folder()
    assert_path_outside_game(dest, game, f"file roundtrip {case_id}")
    assert_artifact_under_work(dest, f"file roundtrip {case_id}")
    dest.mkdir(parents=True, exist_ok=True)
    return dest


def original_hashes() -> dict:
    from unity_patch_baseline import load_original_hashes

    return load_original_hashes()


from unity_patch_baseline import origin_asset_hash_keys  # noqa: F401 — re-export


def assert_original_game_untouched() -> None:
    from game_fingerprint import fingerprint_mismatches

    mismatches = fingerprint_mismatches()
    if mismatches:
        keys = ", ".join(m["key"] for m in mismatches[:3])
        raise AssertionError(
            f"original game file changed ({len(mismatches)} assets, e.g. {keys}). "
            "Restore EN game from backup; do not update baseline without verified source."
        )


def _is_forbidden_seed(path: Path) -> bool:
    name = path.resolve().name
    return name in FORBIDDEN_SEED_NAMES


def assert_seed_from_original(source: Path, dest: Path, label: str) -> None:
    game = read_game_folder().resolve()
    source = source.resolve()
    dest = dest.resolve()
    assert_path_outside_game(dest, game, label)
    if dest == game or game in dest.parents:
        raise RuntimeError(f"{label} dest must not be the original game or inside it: {dest}")
    if _is_forbidden_seed(source) or source != game:
        raise RuntimeError(f"{label} must seed from GAME_FOLDER, not {source}")
    if dest.name in REJECTED_EXTERNAL_COPY_NAMES:
        raise RuntimeError(f"{label} must not use external fixture sentinel: {dest}")
    if source.name in REJECTED_EXTERNAL_COPY_NAMES and source.resolve() != game:
        raise RuntimeError(f"{label} must not seed from another external fixture: {source}")
    if dest.name == R3_COPY.name and source.name == R1_COPY.name:
        raise RuntimeError("R3 copy must not inherit R1")
    if dest.name == R5_COPY.name and source.name in {R1_COPY.name, R3_COPY.name}:
        raise RuntimeError("R5 copy must not inherit R1/R3")


def seed_game_copy(dest: Path, *, label: str) -> Path:
    """Copy the original game into dest. Never seed from another E2E copy."""
    orig = read_game_folder()
    assert_seed_from_original(orig, dest, label)
    assert_write_destination(dest, label)
    if dest.resolve() == E2E_GAME_COPY.resolve():
        assert_artifact_under_work(dest, label)
    elif WORK_ROOT.resolve() not in dest.resolve().parents:
        raise RuntimeError(f"{label} dest must be under {WORK_ROOT}: {dest}")
    safe_robocopy(orig, dest, label=label)
    exe = next((path for path in sorted(dest.glob("*.exe")) if path.is_file()), None)
    if exe is None:
        raise RuntimeError(f"{label} missing Unity executable after seed: {dest}")
    return dest


def copy_rel_from_original(dest_root: Path, rel: str, *, label: str) -> Path:
    game = read_game_folder()
    assert_path_outside_game(dest_root, game, label)
    assert_write_destination(dest_root, label)
    src = game / rel
    dest = dest_root / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)
    if rel.replace("\\", "/").lower().endswith("data.unity3d"):
        from unity_asset_guard import assert_data_unity3d_ready

        assert_data_unity3d_ready(dest, label=label)
    return dest


def load_baseline_rows() -> list[dict]:
    path = EXTRACT_GOLDEN / "translation.csv"
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def load_baseline_keys() -> list[str]:
    path = EXTRACT_GOLDEN / "translation_keys.txt"
    return [line for line in path.read_text(encoding="utf-8").splitlines() if line]


def load_raw_rows() -> list[dict]:
    path = EXTRACT_GOLDEN / "raw_unpatchable.csv"
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def row_by_key(rows: list[dict], key: str) -> dict:
    hits = [row for row in rows if (row.get("key") or "") == key]
    if len(hits) != 1:
        raise AssertionError(f"expected 1 golden row for {key}, got {len(hits)}")
    return hits[0]


def r3_golden_row() -> dict:
    row = row_by_key(load_baseline_rows(), R3_KEY)
    if row.get("source_text") != R3_SOURCE:
        raise AssertionError(row)
    if row.get("import_method") != "unity_textasset_line":
        raise AssertionError(row)
    if "DefaultUI" not in (row.get("object_info") or "") and "DefaultUI" not in (row.get("context") or ""):
        raise AssertionError(row)
    return row


def r5_golden_row() -> dict:
    row = row_by_key(load_baseline_rows(), R5_KEY)
    if row.get("source_text") != R5_SOURCE:
        raise AssertionError(row)
    if row.get("import_method") != "plain_text_line":
        raise AssertionError(row)
    rel = (row.get("file_path") or "").replace("/", "\\")
    if rel.lower() != R5_REL.lower():
        raise AssertionError(row)
    return row


def golden_manifest_entry(key: str) -> dict:
    manifest = json.loads((EXTRACT_GOLDEN / "manifest.json").read_text(encoding="utf-8"))
    hits = [entry for entry in manifest.get("entries", []) if entry.get("key") == key]
    if len(hits) != 1:
        raise AssertionError(f"expected 1 manifest entry for {key}, got {len(hits)}")
    return hits[0]


def write_single_package(pkg: Path, csv_row: dict, manifest_entry: dict, translation: str) -> tuple[Path, Path]:
    from vntext.package_io import CSV_FIELDS

    pkg.mkdir(parents=True, exist_ok=True)
    row = dict(csv_row)
    row["translation"] = translation
    csv_path = pkg / "translation.csv"
    with csv_path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=CSV_FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerow(row)
    manifest_path = pkg / "manifest.json"
    manifest_path.write_text(
        json.dumps({"entries": [manifest_entry]}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return csv_path, manifest_path


def apply_single_translation(
    csv_row: dict,
    manifest_entry: dict,
    translation: str,
    game_copy: Path,
    work: Path,
    log=None,
):
    from vntext.patch import apply_translation_package

    pkg = work / "pkg"
    if pkg.exists():
        shutil.rmtree(pkg)
    csv_path, manifest_path = write_single_package(pkg, csv_row, manifest_entry, translation)
    patch_out = work / "patch_out"
    if patch_out.exists():
        shutil.rmtree(patch_out)
    apply_translation_package(
        str(csv_path),
        str(manifest_path),
        str(game_copy),
        str(patch_out),
        log,
    )
    patched_root = patch_out / "COPY_TO_GAME_ROOT"
    output_rels = [
        str(path.relative_to(patched_root)).replace("\\", "/")
        for path in patched_root.rglob("*")
        if path.is_file()
    ]
    for rel in output_rels:
        src = patched_root / rel.replace("/", "\\")
        dest = game_copy / rel.replace("/", "\\")
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
    return output_rels, patched_root


def read_named_textasset_script(unity_path: Path, asset_name: str) -> str:
    import UnityPy

    env = UnityPy.load(str(unity_path))
    for obj in env.objects:
        type_name = str(getattr(getattr(obj, "type", None), "name", "") or "")
        if type_name != "TextAsset":
            continue
        data = obj.read()
        name = str(getattr(data, "name", "") or getattr(data, "m_Name", "") or "")
        if name != asset_name:
            continue
        script = getattr(data, "m_Script", None)
        if script is None:
            script = getattr(data, "script", None)
        if isinstance(script, (bytes, bytearray)):
            return bytes(script).decode("utf-8", errors="replace")
        return str(script)
    raise AssertionError(f"{asset_name} TextAsset not found in {unity_path}")


def read_defaultui_script(unity_path: Path) -> str:
    return read_named_textasset_script(unity_path, "DefaultUI")


def read_bundle_ui_text(bundle_path: Path, path_id: int) -> str:
    import UnityPy

    env = UnityPy.load(str(bundle_path))
    for obj in env.objects:
        if int(obj.path_id) != int(path_id):
            continue
        data = obj.read()
        return str(getattr(data, "m_Text", "") or "")
    return ""


def count_exact_lines(path: Path, text: str) -> int:
    lines = path.read_text(encoding="utf-8-sig").splitlines()
    return sum(1 for line in lines if line == text)


assert_marker_vietnamese(R1_MARKER, "R1")
assert_marker_vietnamese(R2_MARKER, "R2")
assert_marker_vietnamese(R3_MARKER, "R3")
assert_marker_vietnamese(R4_MARKER, "R4")
assert_marker_vietnamese(R6_MARKER, "R6")
assert_marker_vietnamese(R5_MARKER, "R5")
assert_marker_vietnamese(R7_MARKER, "R7")
assert_marker_vietnamese(NANO_MARKER, "NANO")
