"""Generic copy/isolation regressions for external Unity fixtures."""

from __future__ import annotations

import shutil
import sys
import tempfile
import unittest
from pathlib import Path

LIB = Path(__file__).resolve().parents[1] / "lib"
if str(LIB) not in sys.path:
    sys.path.insert(0, str(LIB))
from unity_patch_baseline import assert_path_outside_game  # noqa: E402


class CoverageCopyIsolationTests(unittest.TestCase):
    def test_destination_must_be_outside_read_only_source(self):
        with tempfile.TemporaryDirectory(prefix="vntext-copy-isolation-") as name:
            root = Path(name)
            source = root / "source"
            destination = root / "work"
            source.mkdir()
            destination.mkdir()
            assert_path_outside_game(destination, source, "isolated work")
            with self.assertRaises(RuntimeError):
                assert_path_outside_game(source / "nested", source, "source child")

    def test_copy_preserves_source_and_writes_only_to_isolated_destination(self):
        with tempfile.TemporaryDirectory(prefix="vntext-copy-isolation-") as name:
            root = Path(name)
            source = root / "source" / "data.assets"
            destination = root / "work" / "data.assets"
            source.parent.mkdir()
            destination.parent.mkdir()
            source.write_bytes(b"synthetic asset")
            before = source.read_bytes()
            shutil.copy2(source, destination)
            self.assertEqual(destination.read_bytes(), before)
            self.assertEqual(source.read_bytes(), before)
            self.assertNotEqual(source.resolve(), destination.resolve())


if __name__ == "__main__":
    unittest.main()
