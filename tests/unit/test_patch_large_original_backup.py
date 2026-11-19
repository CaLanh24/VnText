from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tests.lib.work_paths import work_temp_dir
from vntext import patch_safety

WORK = work_temp_dir("patch-large-backup-tests")


class LargeOriginalBackupTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._prior = tempfile.tempdir
        tempfile.tempdir = str(WORK)

    @classmethod
    def tearDownClass(cls):
        tempfile.tempdir = cls._prior

    def test_small_original_is_still_backed_up_byte_for_byte(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            (base / "game").mkdir()
            source = base / "game" / "data.bin"
            source.write_bytes(b"original")
            patch_safety.backup_original_file(source, base / "backup", "Demo_Data/data.bin")
            self.assertEqual((base / "backup/Demo_Data/data.bin").read_bytes(), b"original")

    def test_original_over_the_limit_is_not_duplicated(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            source = base / "data.unity3d"
            source.write_bytes(b"x" * 16)
            with mock.patch.object(patch_safety, "LARGE_ORIGINAL_BACKUP_LIMIT_BYTES", 8):
                patch_safety.backup_original_file(source, base / "backup", "Demo_Data/data.unity3d")
            self.assertFalse((base / "backup").exists())
            self.assertEqual(source.read_bytes(), b"x" * 16)


if __name__ == "__main__":
    unittest.main()
