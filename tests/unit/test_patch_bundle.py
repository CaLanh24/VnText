"""One self-contained patch EXE: bundle format safety, and a real launch/install/uninstall on an inert fixture."""
from __future__ import annotations

import os
import struct
import subprocess
import sys
import tempfile
import unittest
import unittest.mock
from pathlib import Path


def _tests_lib_on_path() -> None:
    cur = Path(__file__).resolve()
    while cur.name != "tests" and cur.parent != cur:
        cur = cur.parent
    if str(cur / "lib") not in sys.path:
        sys.path.insert(0, str(cur / "lib"))


_tests_lib_on_path()
from bootstrap import bootstrap  # noqa: E402

TESTS, ROOT, LIB = bootstrap(__file__)
from vntext import patch_bundle  # noqa: E402
from tests.lib.work_paths import work_temp_dir  # noqa: E402


def _inert_patch(root: Path) -> tuple[Path, Path]:
    """A declared fixture: a fake Ren'Py game and a patch that only adds/replaces files inside it."""
    from vntext.patch_output import write_renpy_patch_manifest
    game, patch = root / "game", root / "patch"
    for name in ("game", "renpy", "lib"):
        (game / name).mkdir(parents=True, exist_ok=True)
    (game / "Game.exe").write_bytes(b"fixture executable")
    (game / "game/script.rpy").write_bytes(b'label start:\n    "Hello"\n')
    payload = patch / "COPY_TO_GAME_ROOT/game/tl/vietnamese/vntext.rpy"
    payload.parent.mkdir(parents=True)
    payload.write_bytes(b'translate vietnamese strings:\n    old "Hello"\n    new "Xin chao"\n')
    (patch / "COPY_TO_GAME_ROOT/game/zzz_vntext_vietnamese.rpy").write_bytes(b'init 999 python:\n    config.language = "vietnamese"\n')
    write_renpy_patch_manifest(patch, game, "test", {"entries": [{"file_path": "game/script.rpy"}]})
    return game, patch


class PatchBundleFormatTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=work_temp_dir("patch-bundle"))
        self.root = Path(self.temp.name)
        self.addCleanup(self.temp.cleanup)
        self.stub = self.root / "stub.exe"
        self.stub.write_bytes(b"MZ" + b"\0" * 1000)
        _, self.patch = _inert_patch(self.root)

    def test_footer_is_aligned_with_the_installer_reader(self):
        # The installer reads the LAST 57 bytes: sha256(32) + length(8) + 17-byte magic.  A one-byte misalignment makes every bundle unreadable.
        self.assertEqual(57, patch_bundle.FOOTER_SIZE)
        out = patch_bundle.bundle_patch(self.stub, self.patch, self.root / "out" / "VNText-VietHoa.exe")
        data = out.read_bytes()
        self.assertEqual(patch_bundle.MAGIC, data[-17:])
        info = patch_bundle.verify_bundle(out)
        self.assertEqual(info["payload_bytes"], struct.unpack("<Q", data[-25:-17])[0])
        self.assertIn("patch_manifest.json", info["files"])
        self.assertTrue(all(n == "patch_manifest.json" or n.startswith("COPY_TO_GAME_ROOT/") or n.startswith("patch_") for n in info["files"]))
        self.assertEqual(self.stub.read_bytes(), data[: len(self.stub.read_bytes())])
        self.assertEqual([], [p for p in (self.root / "out").iterdir() if p.name != "VNText-VietHoa.exe"])   # no stray staging

    def test_tampered_payload_or_footer_is_rejected(self):
        out = patch_bundle.bundle_patch(self.stub, self.patch, self.root / "out" / "x.exe")
        data = bytearray(out.read_bytes())
        data[len(self.stub.read_bytes()) + 30] ^= 0xFF
        bad = self.root / "bad.exe"; bad.write_bytes(bytes(data))
        with self.assertRaises(ValueError):
            patch_bundle.verify_bundle(bad)
        short = self.root / "short.exe"; short.write_bytes(out.read_bytes()[:-20])
        with self.assertRaises(ValueError):
            patch_bundle.verify_bundle(short)

    def test_limits_and_links_are_refused(self):
        with unittest.mock.patch.object(patch_bundle, "MAX_ENTRIES", 1):
            with self.assertRaises(ValueError):
                patch_bundle.bundle_patch(self.stub, self.patch, self.root / "out" / "many.exe")
        with unittest.mock.patch.object(patch_bundle, "MAX_TOTAL_BYTES", 10):
            with self.assertRaises(ValueError):
                patch_bundle.bundle_patch(self.stub, self.patch, self.root / "out" / "big.exe")
        self.assertFalse((self.root / "out" / "many.exe").exists() or (self.root / "out" / "big.exe").exists())
        (self.patch / "patch_manifest.json").unlink()
        with self.assertRaises(ValueError):
            patch_bundle.bundle_patch(self.stub, self.patch, self.root / "out" / "nomanifest.exe")


class PatchBundleRuntimeTests(unittest.TestCase):
    """Launches the REAL self-contained installer with a payload appended, on an inert game fixture and an isolated payload cache."""

    @staticmethod
    def _stub() -> Path | None:
        for candidate in (os.environ.get("VNTEXT_PATCH_INSTALLER"), str(ROOT / "release" / "patch_installer_publish" / "VNTextPatchInstaller.exe")):
            if candidate and Path(candidate).is_file():
                return Path(candidate)
        return None

    def test_bundled_exe_installs_refuses_tampered_cache_and_uninstalls(self):
        stub = self._stub()
        if stub is None:
            self.skipTest("self-contained patch installer not built (set VNTEXT_PATCH_INSTALLER)")
        with tempfile.TemporaryDirectory(dir=work_temp_dir("patch-bundle-runtime")) as temp:
            root = Path(temp)
            game, patch = _inert_patch(root)
            exe = patch_bundle.bundle_patch(stub, patch, root / "out" / "VNText-VietHoa.exe")
            storage = root / "storage"
            env = {**os.environ, "VNTEXT_PATCH_STORAGE": str(storage)}

            def run(*args, exe_path=exe):
                return subprocess.run([str(exe_path), *args], capture_output=True, text=True, encoding="utf8", errors="backslashreplace", timeout=120, env=env, stdin=subprocess.DEVNULL)

            first = run("--install", str(game))
            self.assertEqual(0, first.returncode, first.stdout + first.stderr)
            target = game / "game/tl/vietnamese/vntext.rpy"
            self.assertEqual((patch / "COPY_TO_GAME_ROOT/game/tl/vietnamese/vntext.rpy").read_bytes(), target.read_bytes())
            self.assertEqual(b'label start:\n    "Hello"\n', (game / "game/script.rpy").read_bytes())
            cache = next((storage / "VNText" / "Patches").iterdir())
            self.assertTrue((cache / "install_state.json").is_file())                           # state/backups live in the managed cache, not beside the EXE
            self.assertEqual(["VNText-VietHoa.exe"], [p.name for p in exe.parent.iterdir()])    # the distributable is ONE file

            # a tampered installed file blocks uninstall (existing refusal guard)
            target.write_bytes(b"external mod")
            self.assertNotEqual(0, run("--uninstall", str(game)).returncode)
            self.assertEqual(b"external mod", target.read_bytes())
            target.write_bytes((patch / "COPY_TO_GAME_ROOT/game/tl/vietnamese/vntext.rpy").read_bytes())
            # a tampered CACHED payload/manifest is restored from the verified archive on the next launch, extra planted files are removed
            (cache / "COPY_TO_GAME_ROOT/game/zzz_vntext_vietnamese.rpy").write_bytes(b"evil")
            planted = cache / "COPY_TO_GAME_ROOT/game/planted.rpy"; planted.write_bytes(b"planted")
            manifest_before = (patch / "patch_manifest.json").read_bytes()
            (cache / "patch_manifest.json").write_bytes(b'{"tampered": true}')
            second = run("--uninstall", str(game))
            self.assertEqual(0, second.returncode, second.stdout + second.stderr)
            self.assertFalse(planted.exists())
            self.assertEqual(manifest_before, (cache / "patch_manifest.json").read_bytes())
            self.assertFalse((game / "game/zzz_vntext_vietnamese.rpy").exists())
            self.assertFalse((cache / "install_state.json").exists())

            # a corrupted EXE (payload bit flip) refuses to open
            data = bytearray(exe.read_bytes()); data[-200] ^= 0xFF
            broken = root / "broken.exe"; broken.write_bytes(bytes(data))
            self.assertNotEqual(0, run("--install", str(game), exe_path=broken).returncode)
            self.assertFalse(target.exists())


class PatchInstallerUiSourceTests(unittest.TestCase):
    """Native review found the description clipped at the default size and a plain square/blue-flat look; these guard the layout rules in source."""

    def test_description_wraps_to_its_own_height_and_the_brand_mark_is_the_app_artwork(self):
        form = (ROOT / "wpf_app" / "VNText.PatchInstaller" / "InstallerForm.cs").read_text(encoding="utf-8")
        project = (ROOT / "wpf_app" / "VNText.PatchInstaller" / "VNText.PatchInstaller.csproj").read_text(encoding="utf-8")
        self.assertIn("_description = new() { AutoSize = true", form)                  # content-sized, never a fixed height
        self.assertNotRegex(form, r"_description[^;]*Height\s*=")
        self.assertIn("_description.MaximumSize = new Size(inner, 0)", form)           # wraps at the card width on every resize
        self.assertIn("SizeType.AutoSize", form)
        self.assertIn("class RoundedButton", form); self.assertIn("class RoundedPanel", form)
        self.assertIn("VNText.Logo.png", form)
        self.assertIn("brand_144.png", project)
        self.assertTrue((ROOT / "wpf_app" / "VNText.PatchInstaller" / "Assets" / "brand_144.png").is_file())


if __name__ == "__main__":
    import unittest.mock  # noqa: F401
    unittest.main()
