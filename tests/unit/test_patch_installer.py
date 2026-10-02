"""Installer install/uninstall round-trip on an isolated game copy."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import unittest
from pathlib import Path


def _tests_lib_on_path() -> None:
    cur = Path(__file__).resolve()
    while cur.name != "tests" and cur.parent != cur:
        cur = cur.parent
    lib = cur / "lib"
    if str(lib) not in sys.path:
        sys.path.insert(0, str(lib))


_tests_lib_on_path()
from bootstrap import bootstrap  # noqa: E402

TESTS, ROOT, LIB = bootstrap(__file__)
from vntext.patch import write_patch_manifest  # noqa: E402
from work_paths import ARTIFACT_NAMESPACE, WORK_ROOT, ambient_scope, register_artifact  # noqa: E402


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class PatchInstallerTests(unittest.TestCase):
    @staticmethod
    def _installer_candidates() -> list[Path]:
        candidates = [ROOT / "release" / "patch_installer_publish" / "VNTextPatchInstaller.exe"]
        release_root = os.environ.get("VNTEXT_RELEASE_ROOT")
        if release_root:
            candidates.append(Path(release_root) / "worker" / "vntext" / "tools" / "VNTextPatchInstaller.exe")
        return candidates

    def _register_case(self, case: Path, *, name: str) -> None:
        ambient = ambient_scope()
        register_artifact(
            artifact_id=f"patch-installer-container:{ARTIFACT_NAMESPACE}:{name}",
            path=case.parent,
            kind="test_temp_container",
            created_by="test_patch_installer.py",
            owner="test_patch_installer.py",
            purpose=f"retained container for {name} installer fixture",
            lifecycle="RETAINED",
            scope_id=ambient["scope_id"],
            run_id=ambient["run_id"],
            scope_root=ambient["scope_root"],
        )
        register_artifact(
            artifact_id=f"patch-installer-case:{ARTIFACT_NAMESPACE}:{name}",
            path=case,
            kind="test_workspace",
            created_by="test_patch_installer.py",
            owner="test_patch_installer.py",
            purpose=f"disposable {name} installer round-trip fixture",
            lifecycle="DISPOSABLE",
            scope_id=ambient["scope_id"],
            run_id=ambient["run_id"],
            scope_root=ambient["scope_root"],
        )

    def test_install_uninstall_restores_exact_hash(self):
        candidates = self._installer_candidates()
        installer = next((p for p in candidates if p.is_file()), None)
        if installer is None:
            self.skipTest("patch installer chưa được build")

        case = WORK_ROOT / "bulk_glossary_installer" / "installer_roundtrip"
        if case.exists():
            shutil.rmtree(case)
        self._register_case(case, name="bulk-glossary")
        game = case / "game_copy"
        patch = case / "patch_vtest"
        data = game / "SampleVN_Data" / "data.unity3d"
        target = game / "SampleVN_Data" / "translation.txt"
        payload = patch / "COPY_TO_GAME_ROOT" / "SampleVN_Data" / "translation.txt"
        game.mkdir(parents=True)
        data.parent.mkdir(parents=True, exist_ok=True)
        data.write_bytes(b"game-data-fixture")
        (game / "SampleVN.exe").write_bytes(b"exe-fixture")
        target.write_text("ORIGINAL\n", encoding="utf-8")
        payload.parent.mkdir(parents=True)
        payload.write_text("VIET HOA\n", encoding="utf-8")
        patch.mkdir(parents=True, exist_ok=True)
        manifest = write_patch_manifest(patch, game, "test")
        self.assertEqual(manifest["files"][0]["path"], "SampleVN_Data/translation.txt")
        self.assertEqual(manifest["files"][0]["original_sha256"], sha256(target))
        before = sha256(target)

        install = subprocess.run(
            [str(installer), "--install", str(game), str(patch)],
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(install.returncode, 0, install.stderr or install.stdout)
        self.assertEqual(target.read_text(encoding="utf-8"), "VIET HOA\n")
        self.assertTrue((patch / "install_state.json").is_file())

        uninstall = subprocess.run(
            [str(installer), "--uninstall", str(game), str(patch)],
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(uninstall.returncode, 0, uninstall.stderr or uninstall.stdout)
        self.assertEqual(sha256(target), before)
        self.assertEqual(target.read_text(encoding="utf-8"), "ORIGINAL\n")
        self.assertFalse((patch / "install_state.json").exists())
        (case / "result.json").write_text(json.dumps({"install": True, "uninstall": True, "hash_restored": True}, indent=2), encoding="utf-8")

    def test_manifest_and_installer_accept_generic_unity_data_name(self):
        candidates = self._installer_candidates()
        installer = next((p for p in candidates if p.is_file()), None)
        if installer is None:
            self.skipTest("patch installer chưa được build")

        case = WORK_ROOT / "generic_unity_installer" / "installer_roundtrip"
        if case.exists():
            shutil.rmtree(case)
        self._register_case(case, name="generic-unity")
        game = case / "game_copy"
        patch = case / "patch_vtest"
        data = game / "SampleVN_Data" / "data.unity3d"
        target = game / "SampleVN_Data" / "translation.txt"
        payload = patch / "COPY_TO_GAME_ROOT" / "SampleVN_Data" / "translation.txt"
        data.parent.mkdir(parents=True)
        data.write_bytes(b"sample-game-data")
        (game / "SampleVN.exe").write_bytes(b"sample-exe")
        other_data = game / "Other_Data" / "data.unity3d"
        other_data.parent.mkdir(parents=True)
        other_data.write_bytes(b"other-game-data")
        (game / "Other.exe").write_bytes(b"other-exe")
        target.write_text("ORIGINAL\n", encoding="utf-8")
        payload.parent.mkdir(parents=True)
        payload.write_text("VIET HOA\n", encoding="utf-8")
        manifest = write_patch_manifest(patch, game, "generic")
        self.assertEqual(manifest["game_data_path"], "SampleVN_Data/data.unity3d")
        self.assertEqual(manifest["game_executable"], "SampleVN.exe")
        before = sha256(target)

        install = subprocess.run(
            [str(installer), "--install", str(game), str(patch)],
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(install.returncode, 0, install.stderr or install.stdout)
        self.assertEqual(target.read_text(encoding="utf-8"), "VIET HOA\n")

        uninstall = subprocess.run(
            [str(installer), "--uninstall", str(game), str(patch)],
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(uninstall.returncode, 0, uninstall.stderr or uninstall.stdout)
        self.assertEqual(sha256(target), before)


if __name__ == "__main__":
    unittest.main()
