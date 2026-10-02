"""Generic serialized-asset isolation gate; no Unity game is bundled."""

from __future__ import annotations

import hashlib
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

LIB = Path(__file__).resolve().parents[1] / "lib"
if str(LIB) not in sys.path:
    sys.path.insert(0, str(LIB))
from unity_patch_baseline import assert_path_outside_game  # noqa: E402


class DataUnity3dIsolationTests(unittest.TestCase):
    def test_caller_supplied_asset_is_copied_without_mutating_source(self):
        with tempfile.TemporaryDirectory(prefix="vntext-unity-isolation-") as name:
            root = Path(name)
            source_root = root / "source"
            work_root = root / "work"
            source = source_root / "data.unity3d"
            destination = work_root / "data.unity3d"
            source.parent.mkdir()
            work_root.mkdir()
            source.write_bytes(b"UnityFS synthetic asset")
            before = hashlib.sha256(source.read_bytes()).hexdigest()
            assert_path_outside_game(work_root, source_root, "isolated Unity work")
            shutil.copy2(source, destination)
            destination.write_bytes(destination.read_bytes() + b"\npatched-copy")
            self.assertNotEqual(destination.read_bytes(), source.read_bytes())
            self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(), before)


if __name__ == "__main__":
    unittest.main()
