"""Characterization freeze: UnityFS / Addressables files must stay byte-identical."""

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

import hashlib
import unittest
from pathlib import Path


# SHA-256 of frozen files. addressables.py is still the Phase 0 bytes.
# unity_fs.py: current no-TypeTree grow rebuild (VH-compatible directory patch).
FROZEN_SHA256 = {
    "vntext/unity_fs.py": "2ef242485cbc91978e6ebd9bc54a13f3045c8752d06e0f86cf2138106b7dc15c",
    "vntext/addressables.py": "f2a22890da471a27f0980d71b705661855e5d3a1121b7998b701b75c9ea8030a",
}


def _sha256(path: Path) -> str:
    # The freeze is source-content based.  Git may materialize Python sources
    # as CRLF on Windows, while the recorded hash is the canonical LF blob.
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


class FreezeHashTests(unittest.TestCase):
    def test_unity_fs_sha256_matches_phase0(self):
        rel = "vntext/unity_fs.py"
        path = ROOT / rel
        self.assertTrue(path.is_file(), f"missing frozen file: {rel}")
        self.assertEqual(_sha256(path), FROZEN_SHA256[rel])

    def test_addressables_sha256_matches_phase0(self):
        rel = "vntext/addressables.py"
        path = ROOT / rel
        self.assertTrue(path.is_file(), f"missing frozen file: {rel}")
        self.assertEqual(_sha256(path), FROZEN_SHA256[rel])


if __name__ == "__main__":
    unittest.main()
