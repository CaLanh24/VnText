from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tests.lib.work_paths import work_temp_dir
from vntext import patch_readback, patch_safety

WORK = work_temp_dir("patch-memory-overlap-tests")


class _FakeProcess:
    returncode = 0
    args = ["fake"]

    def __init__(self, stdout: str, stderr: str):
        self._out, self._err = stdout, stderr

    def poll(self):
        return self.returncode

    def communicate(self, _input=None, timeout=None):
        return self._out, self._err


class PatchMemoryOverlapTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._prior = tempfile.tempdir
        tempfile.tempdir = str(WORK)

    @classmethod
    def tearDownClass(cls):
        tempfile.tempdir = cls._prior

    def test_bundle_targets_are_never_read_whole_into_the_writer_process(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "Demo_Data").mkdir()
            bundle = root / "Demo_Data" / "data.unity3d"
            bundle.write_bytes(b"UnityFS" + b"\0" * 64)
            text = root / "Demo_Data" / "dialogue.txt"
            text.write_bytes("Xin chào".encode("utf-8"))
            items = {"Demo_Data/data.unity3d": [({"import_method": "unity_ui_text", "source_text": "Hi"}, "Xin chào")],
                     "Demo_Data/dialogue.txt": [({"import_method": "unity_textasset_line", "source_text": "Hi"}, "Xin chào")]}
            reads = []
            original = Path.read_bytes

            def tracking(self):
                reads.append(self.name)
                return original(self)

            report: list[str] = []
            with mock.patch.object(Path, "read_bytes", tracking):
                patch_safety.verify_patched_translations(root, items, report)
            self.assertNotIn("data.unity3d", reads)
            self.assertIn("dialogue.txt", reads)                      # ordinary targets are still verified byte-wise
            self.assertIn("VERIFY translated_bytes_in_patched_files: 1/1", report)

    def test_empty_child_report_names_exit_code_stdout_and_stderr(self):
        grouped = {"Demo_Data/data.unity3d": [({"import_method": "unity_ui_text", "source_text": "Hi", "key": "k"}, "Xin chào")]}
        with mock.patch.object(patch_readback.subprocess, "Popen", return_value=_FakeProcess("", "MemoryError in child")):
            report = patch_readback._run_readback_subprocess(Path("p"), Path("g"), grouped, 5.0)
        text = str(report)
        self.assertEqual(report["counts"].get(patch_readback.FAIL), 1)
        self.assertIn("exit code 0", text)
        self.assertIn("stdout bytes 0", text)
        self.assertIn("MemoryError in child", text)


if __name__ == "__main__":
    unittest.main()
