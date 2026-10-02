"""Resolve tests/ root and put lib + project root on sys.path."""
from __future__ import annotations

import sys
from pathlib import Path


def tests_root(from_file: str | Path | None = None) -> Path:
    if from_file is not None:
        cur = Path(from_file).resolve().parent
        while cur.name != "tests" and cur.parent != cur:
            cur = cur.parent
        if cur.name == "tests":
            return cur
    # lib/bootstrap.py → tests/
    here = Path(__file__).resolve().parent
    return here.parent


def bootstrap(from_file: str | Path) -> tuple[Path, Path, Path]:
    """Return (tests_dir, project_root, lib_dir) and extend sys.path."""
    tests = tests_root(from_file)
    root = tests.parent
    lib = tests / "lib"
    for p in (str(root), str(lib)):
        if p not in sys.path:
            sys.path.insert(0, p)
    return tests, root, lib


def harness_dir(name: str, from_file: str | Path) -> Path:
  tests = tests_root(from_file)
  return tests / "harness" / name
