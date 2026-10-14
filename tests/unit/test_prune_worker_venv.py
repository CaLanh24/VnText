"""Focused package-pruning checks for the portable CT2 worker environment."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch
import uuid


def _bootstrap_tests():
    cur = Path(__file__).resolve().parent
    while cur.name != "tests" and cur.parent != cur:
        cur = cur.parent
    sys.path.insert(0, str(cur / "lib"))
    from bootstrap import bootstrap

    return bootstrap(__file__)


TESTS, ROOT, _LIB = _bootstrap_tests()
sys.path.insert(0, str(ROOT / "tests" / "tools"))
sys.path.insert(0, str(ROOT / "release"))
import prune_worker_venv
from work_paths import WORK_ROOT, artifact_scope


class PruneWorkerVenvTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        WORK_ROOT.mkdir(parents=True, exist_ok=True)
        cls._fixture_root = WORK_ROOT / f"prune-worker-venv-tests-{uuid.uuid4().hex}"
        cls._fixture_scope = artifact_scope(
            cls._fixture_root,
            artifact_id=f"prune-worker-venv-tests:{uuid.uuid4().hex}",
            kind="test_fixture_scope",
            owner="test_prune_worker_venv",
            purpose="bounded fixtures for worker venv pruning tests",
        )
        cls._fixture_scope.__enter__()
        cls._fixture_root.mkdir()

    @classmethod
    def tearDownClass(cls):
        cls._fixture_scope.__exit__(None, None, None)

    def fixture(self, name):
        root = self._fixture_root / name
        root.mkdir(parents=True)
        return root

    def test_filtered_copy_omits_pruned_payload_before_staging_and_preserves_source(self):
        root = self.fixture("prune-worker-copy")
        source = root / "source.venv"
        destination = root / "stage.venv"
        keep = source / "Lib/site-packages/ctranslate2/core.py"
        drop = source / "Lib/site-packages/torch/lib/large.bin"
        dist = source / "Lib/site-packages/torch-2.0.dist-info/METADATA"
        script = source / "Scripts/python.exe"
        cache = source / "Lib/site-packages/ctranslate2/__pycache__/core.pyc"
        package_tests = source / "Lib/site-packages/ctranslate2/tests/test_core.py"
        for path, payload in ((keep, b"keep"), (drop, b"drop"), (dist, b"metadata"),
                              (script, b"python"), (cache, b"bytecode"),
                              (package_tests, b"test fixture")):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(payload)

        report = prune_worker_venv.copy_pruned_source(source, destination)

        self.assertEqual(b"keep", (destination / keep.relative_to(source)).read_bytes())
        self.assertEqual(b"python", (destination / script.relative_to(source)).read_bytes())
        self.assertFalse((destination / drop.relative_to(source)).exists())
        self.assertFalse((destination / dist.relative_to(source)).exists())
        self.assertFalse((destination / cache.relative_to(source)).exists())
        self.assertFalse((destination / package_tests.relative_to(source)).exists())
        self.assertEqual(b"drop", drop.read_bytes())
        self.assertEqual(b"metadata", dist.read_bytes())
        self.assertEqual(10, report["bytes"])

    def test_filtered_copy_refuses_existing_destination_and_source_links(self):
        root = self.fixture("prune-worker-copy-guards")
        source = root / "source.venv"
        destination = root / "stage.venv"
        (source / "Scripts").mkdir(parents=True)
        (source / "Scripts/python.exe").write_bytes(b"python")
        destination.mkdir()
        with self.assertRaises(FileExistsError):
            prune_worker_venv.copy_pruned_source(source, destination)
        destination.rmdir()
        link = source / "Scripts/pythonw.exe"
        link.write_bytes(b"link fixture")
        real_is_symlink = Path.is_symlink
        with patch.object(Path, "is_symlink", lambda item: item == link or real_is_symlink(item)):
            with self.assertRaisesRegex(RuntimeError, "contains a link"):
                prune_worker_venv.copy_pruned_source(source, destination)
        self.assertFalse(destination.exists())

    def test_filtered_copy_handles_windows_long_paths(self):
        root = self.fixture("prune-worker-long-path")
        source = root / "source.venv"
        destination = root / "stage.venv"
        python = source / "Scripts" / "python.exe"
        python.parent.mkdir(parents=True)
        python.write_bytes(b"python")
        deep = source / "Lib" / "site-packages" / "ctranslate2"
        for index in range(24):
            deep = deep / f"segment-{index:02d}"
        long_file = deep / "runtime-module.py"
        long_file.parent.mkdir(parents=True)
        long_file.write_text("runtime", encoding="utf-8")
        self.assertGreater(len(str(long_file)), 260)

        prune_worker_venv.copy_pruned_source(source, destination)

        copied = destination / long_file.relative_to(source)
        self.assertEqual("runtime", copied.read_text(encoding="utf-8"))

    def test_prunes_only_fmod_vendor_subtree_and_preserves_helper_license(self):
        root = self.fixture("prune-fmod-vendor") / ".venv"
        site = root / "Lib" / "site-packages"
        vendor = site / "fmod_toolkit" / "libfmod"
        for relative in ("Windows/x64/fmod.dll", "Linux/libfmod.so.13", "Mac/libfmod.dylib"):
            binary = vendor / relative
            binary.parent.mkdir(parents=True, exist_ok=True)
            binary.write_bytes(b"vendor fixture")
        helper = site / "fmod_toolkit" / "__init__.py"
        helper.write_text("# helper fixture", encoding="utf-8")
        notice = site / "fmod_toolkit-0.1.3.dist-info" / "LICENSE"
        notice.parent.mkdir()
        notice.write_text("MIT fixture", encoding="utf-8")
        report = prune_worker_venv.prune_venv(root)
        self.assertIn("fmod_toolkit/libfmod", report["removed"])
        self.assertFalse(vendor.exists())
        self.assertEqual("# helper fixture", helper.read_text(encoding="utf-8"))
        self.assertEqual("MIT fixture", notice.read_text(encoding="utf-8"))

    def test_vendor_deletion_error_is_not_hidden(self):
        root = self.fixture("prune-fmod-error") / ".venv"
        vendor = root / "Lib" / "site-packages" / "fmod_toolkit" / "libfmod"
        vendor.mkdir(parents=True)
        with patch.object(prune_worker_venv.shutil, "rmtree", side_effect=PermissionError("locked vendor")):
            with self.assertRaisesRegex(PermissionError, "locked vendor"):
                prune_worker_venv.prune_venv(root)
        self.assertTrue(vendor.exists())

    def test_rejects_fmod_binary_outside_expected_vendor_subtree(self):
        root = self.fixture("prune-fmod-leftover") / ".venv"
        site = root / "Lib" / "site-packages"
        site.mkdir(parents=True)
        for name in ("fmod.dll", "FMODSTUDIO.DLL", "libfmod.so.13", "libfmod.dylib"):
            binary = site / name
            binary.write_bytes(b"unexpected vendor fixture")
            with self.assertRaisesRegex(RuntimeError, "vendor FMOD binary"):
                prune_worker_venv.prune_venv(root)
            binary.unlink()

    def test_drops_non_worker_packages_but_keeps_worker_runtime_packages(self):
        site = self.fixture("prune-worker-venv") / ".venv" / "Lib" / "site-packages"
        scripts = site.parent.parent / "Scripts"
        site.mkdir(parents=True)
        scripts.mkdir()

        for package, version in (
            ("minisbd", "0.9.5"),
            ("argostranslate", "1.11.0"),
            ("PySide6_Addons", "6.8.3"),
            ("PySide6_Essentials", "6.8.3"),
            ("pyinstaller_hooks_contrib", "2026.6"),
            ("setuptools", "84.0.0"),
            ("UnityPy", "1.25.3"),
            ("ctranslate2", "4.8.1"),
            ("transformers", "5.17.0"),
            ("sentencepiece", "0.2.2"),
        ):
            (site / package).mkdir()
            (site / package / "__init__.py").write_text("", encoding="utf-8")
            dist_info = site / f"{package}-{version}.dist-info"
            dist_info.mkdir()
            (dist_info / "METADATA").write_text(
                f"Name: {package}\nVersion: {version}\n", encoding="utf-8"
            )

        report = prune_worker_venv.prune_venv(site.parent.parent)

        for dropped in (
            "minisbd",
            "argostranslate",
            "PySide6_Addons",
            "PySide6_Essentials",
            "pyinstaller_hooks_contrib",
            "setuptools",
        ):
            self.assertIn(dropped, prune_worker_venv.DROP_PACKAGES)
            self.assertIn(dropped, report["removed"])
            self.assertFalse((site / dropped).exists())
            self.assertEqual([], list(site.glob(f"{dropped}-*.dist-info")))
        for retained in ("UnityPy", "ctranslate2", "transformers", "sentencepiece"):
            self.assertTrue((site / retained).is_dir(), retained)
            self.assertEqual(1, len(list(site.glob(f"{retained}-*.dist-info"))), retained)


if __name__ == "__main__":
    unittest.main()
