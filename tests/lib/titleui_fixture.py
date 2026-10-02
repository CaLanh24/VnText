"""TitleUI SampleGame fixture constants and copy helpers. Test-only; never write the original game.

Gap (001 golden): CREDIT unity_ui_text lives on the Addressables .bundle, not
TitleUI inside data.unity3d. tests/golden/extract/ (2313 keys) is a preservation
baseline — do not rewrite that folder to make extract tests pass.
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
import shutil
from pathlib import Path


from unity_patch_baseline import (
    EXTRACT_GOLDEN,
    assert_path_outside_game,
    hash_game_files,
    read_game_folder,
)
from work_paths import TITLEUI_STAGING, assert_artifact_under_work

WORK = TITLEUI_STAGING
DATA_UNITY3D_REL = "SampleGame_Data/data.unity3d"
BASELINE_KEY_COUNT = 2313

# Fixture path_ids — TEST/GOLDEN ONLY. Production must not contain these literals.
TITLEUI_GO_PATH_ID = 5218
ITITLEUI_GO_PATH_ID = 5217
CREDIT_TEXT_PATH_ID = 15701
CONTENT_TEXT_PATH_ID = 14271
PATREON_TEXT_PATH_ID = 12541
TIPS_TEXT_PATH_ID = 12571
UICONFIG_PATH_ID = 11824
CUSTOMTITLE_GO_PATH_ID = -3747095206826591039
ADDR_CREDIT_TEXT_PATH_ID = -8351419620336031481

FORBIDDEN_PATH_ID_LITERALS = (
    str(TITLEUI_GO_PATH_ID),
    str(ITITLEUI_GO_PATH_ID),
    str(CREDIT_TEXT_PATH_ID),
    str(CONTENT_TEXT_PATH_ID),
    str(PATREON_TEXT_PATH_ID),
    str(TIPS_TEXT_PATH_ID),
    str(UICONFIG_PATH_ID),
    str(CUSTOMTITLE_GO_PATH_ID),
    str(ADDR_CREDIT_TEXT_PATH_ID),
)

TITLEUI_GO_NAME = "TitleUI"
ITITLEUI_GO_NAME = "ITitleUI.TitleMenu"
CREDIT_GO_NAME = "CREDIT"
CONTENT_GO_NAME = "Content Setting"
SUPPORT_GO_NAME = "Support"
TIPS_LABEL_NAME = "TipsLabel"

# Spec-confirmed additive extract identities (hashes filled after Phase 4 verify).
ALLOWED_TITLEUI_ADDITIONS = (
    {
        "go_name": CREDIT_GO_NAME,
        "source_text": "CREDIT",
        "import_method": "unity_ui_text",
        "file_suffix": "data.unity3d",
    },
    {
        "go_name": CONTENT_GO_NAME,
        "source_text": "CONTENT\nOPTION",
        "import_method": "unity_ui_text",
        "file_suffix": "data.unity3d",
    },
    {
        "go_name": SUPPORT_GO_NAME,
        "source_text": "PATREON",
        "import_method": "unity_ui_text",
        "file_suffix": "data.unity3d",
    },
    {
        "go_name": TIPS_LABEL_NAME,
        "source_text": "Game Guide\nWalkthrough",
        "import_method": "unity_ui_text",
        "file_suffix": "data.unity3d",
    },
)


def titleui_work_dir() -> Path:
    game = read_game_folder()
    assert_path_outside_game(WORK, game, "titleui work dir")
    assert_artifact_under_work(WORK, "titleui work dir")
    WORK.mkdir(parents=True, exist_ok=True)
    return WORK


def ensure_data_unity3d_copy() -> Path:
    game = read_game_folder()
    src = game / DATA_UNITY3D_REL
    dest = titleui_work_dir() / Path(DATA_UNITY3D_REL)
    dest.parent.mkdir(parents=True, exist_ok=True)
    assert_path_outside_game(dest, game, "titleui data.unity3d copy")
    if not dest.is_file() or dest.stat().st_size != src.stat().st_size:
        shutil.copy2(src, dest)
    return dest


def load_baseline_extract_rows() -> list[dict]:
    path = EXTRACT_GOLDEN / "translation.csv"
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def load_baseline_keys() -> list[str]:
    path = EXTRACT_GOLDEN / "translation_keys.txt"
    keys = [line for line in path.read_text(encoding="utf-8").splitlines() if line]
    if len(keys) != BASELINE_KEY_COUNT:
        raise AssertionError(
            f"001 extract baseline must stay {BASELINE_KEY_COUNT} keys, got {len(keys)}"
        )
    return keys


PRESERVE_FIELDS = ("key", "source_text", "context", "import_method", "file_path")
FORBIDDEN_TITLEUI_SOURCE_TEXTS = ("NEW GAME", "CONTINUE", "SETTINGS", "EXIT")


def file_path_is_data_unity3d(file_path: str) -> bool:
    normalized = str(file_path or "").replace("\\", "/").rstrip("/")
    return normalized.endswith("data.unity3d") and not normalized.endswith(".bundle")


def baseline_data_unity3d_rows() -> list[dict]:
    return [
        row
        for row in load_baseline_extract_rows()
        if file_path_is_data_unity3d(row.get("file_path", ""))
    ]


def row_matches_allowed_identity(row: dict, identity: dict) -> bool:
    if str(row.get("import_method") or "") != identity["import_method"]:
        return False
    if str(row.get("source_text") or "") != identity["source_text"]:
        return False
    return file_path_is_data_unity3d(row.get("file_path", ""))


def classify_new_extract_row(row: dict) -> str:
    """Return 'allowed', 'forbidden-defaultui', or 'unexpected' for a key not in 001."""
    source = str(row.get("source_text") or "")
    if source in FORBIDDEN_TITLEUI_SOURCE_TEXTS:
        return "forbidden-defaultui"
    for identity in ALLOWED_TITLEUI_ADDITIONS:
        if row_matches_allowed_identity(row, identity):
            return "allowed"
    return "unexpected"


def original_data_unity3d_hash() -> dict:
    game = read_game_folder()
    return hash_game_files(game, [DATA_UNITY3D_REL])
