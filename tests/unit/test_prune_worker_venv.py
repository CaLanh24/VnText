"""Focused package-pruning checks for the portable CT2 worker environment."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch


def _bootstrap_tests():
    cur = Path(__file__).resolve().parent
    while cur.name != "tests" and cur.parent != cur:
        cur = cur.parent
    sys.path.insert(0, str(cur / "lib"))
    from bootstrap import bootstrap

    return bootstrap(__file__)


TESTS, ROOT, _LIB = _bootstrap_tests()
sys.path.insert(0, str(ROOT / "release"))
import prune_worker_venv
from work_paths import work_temp_dir


class PruneWorkerVenvTests(unittest.TestCase):
    def test_prunes_only_fmod_vendor_subtree_and_preserves_helper_license(self):
        root = work_temp_dir("prune-fmod-vendor") / ".venv"
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
        root = work_temp_dir("prune-fmod-error") / ".venv"
        vendor = root / "Lib" / "site-packages" / "fmod_toolkit" / "libfmod"
        vendor.mkdir(parents=True)
        with patch.object(prune_worker_venv.shutil, "rmtree", side_effect=PermissionError("locked vendor")):
            with self.assertRaisesRegex(PermissionError, "locked vendor"):
                prune_worker_venv.prune_venv(root)
        self.assertTrue(vendor.exists())

    def test_rejects_fmod_binary_outside_expected_vendor_subtree(self):
        root = work_temp_dir("prune-fmod-leftover") / ".venv"
        site = root / "Lib" / "site-packages"
        site.mkdir(parents=True)
        for name in ("fmod.dll", "FMODSTUDIO.DLL", "libfmod.so.13", "libfmod.dylib"):
            binary = site / name
            binary.write_bytes(b"unexpected vendor fixture")
            with self.assertRaisesRegex(RuntimeError, "vendor FMOD binary"):
                prune_worker_venv.prune_venv(root)
            binary.unlink()

    def test_drops_non_worker_packages_but_keeps_worker_runtime_packages(self):
        site = work_temp_dir("prune-worker-venv") / ".venv" / "Lib" / "site-packages"
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
