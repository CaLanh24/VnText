"""Add harness subdirs to sys.path (post-reorg layout)."""
from __future__ import annotations

import sys
from pathlib import Path

from bootstrap import tests_root


def ensure_harness(*names: str, from_file: str | Path) -> Path:
    tests = tests_root(from_file)
    for name in names:
        p = str(tests / "harness" / name)
        if p not in sys.path:
            sys.path.insert(0, p)
    return tests
