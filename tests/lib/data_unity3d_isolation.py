"""Generic isolated binary-asset helpers; no bundled game fixture is assumed."""

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

import shutil
from pathlib import Path

from work_paths import UNITY_STAGING, assert_artifact_under_work, assert_write_destination

WORK = UNITY_STAGING
DATA_UNITY3D_REL = "data.unity3d"


def isolation_work_dir() -> Path:
    assert_artifact_under_work(WORK, "addr_isolation work dir")
    WORK.mkdir(parents=True, exist_ok=True)
    return WORK


def copy_asset_to_isolation(source: Path, relative: str = DATA_UNITY3D_REL) -> Path:
    """Copy one caller-supplied asset below the registered isolated work root."""
    source = Path(source).expanduser().resolve()
    if not source.is_file():
        raise FileNotFoundError(source)
    destination = assert_write_destination(isolation_work_dir() / relative, "isolated asset")
    if destination == source:
        raise RuntimeError("isolated asset destination must differ from source")
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    return destination


if __name__ == "__main__":
    unittest.main()
