"""One-step patch upgrade, end to end: the installer harness (every crash point), and a real Ren'Py build -> install A -> build B from the
installed game -> install B over A -> uninstall -> clean original, byte for byte."""
import csv
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from tests.lib.dev_environment import dotnet_executable, nuget_cache
from tests.lib.work_paths import work_temp_dir

ROOT = Path(__file__).resolve().parents[2]
WORK = work_temp_dir("patch-upgrade")
SDK = ROOT / ".dev-env" / "tools" / "renpy-8.5.3"


def _build(project: Path, name: str) -> Path:
    artifacts = Path(WORK) / ("build-" + name)
    env = dict(os.environ, DOTNET_ADD_GLOBAL_TOOLS_TO_PATH="0", DOTNET_CLI_TELEMETRY_OPTOUT="1", DOTNET_NOLOGO="1",
               DOTNET_CLI_HOME=str(Path(WORK) / "dotnet-home"), NUGET_PACKAGES=str(nuget_cache()))
    done = subprocess.run([str(dotnet_executable()), "build", str(project), "-c", "Release", "--artifacts-path", str(artifacts), "-p:NuGetAudit=false"],
                          cwd=ROOT, env=env, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=600)
    if done.returncode:
        raise AssertionError(done.stdout[-3000:] + done.stderr[-2000:])
    return next(artifacts.rglob(name + ".exe"))


def _tree(root: Path, skip_receipt: bool = False) -> dict[str, str]:
    return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(root.rglob("*"))
            if p.is_file() and not (skip_receipt and p.relative_to(root).parts[0] == ".vntext")}


class PatchUpgradeTests(unittest.TestCase):
    def test_installer_harness_including_a_crash_at_every_step(self):
        exe = _build(ROOT / "tests" / "installer_ownership" / "InstallerOwnership.Harness.csproj", "InstallerOwnership.Harness")
        done = subprocess.run([str(exe)], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=600)
        report = json.loads(done.stdout)
        failed = [c for c in report["checks"] if not c["pass"]]
        self.assertEqual([], failed)
        self.assertEqual(0, done.returncode, done.stderr[-2000:])
        self.assertGreaterEqual(len(report["checks"]), 100)

    @unittest.skipUnless((SDK / "renpy.exe").is_file(), "needs the local Ren'Py SDK")
    def test_renpy_patch_b_built_from_the_installed_game_upgrades_a_in_one_step(self):
        from vntext.app_tasks import run_extract_task, run_patch_task
        import tests.unit.test_scan_layout_matrix as layouts
        cli = _build(ROOT / "tests" / "installer_cli" / "InstallerCli.csproj", "InstallerCli")

        def run_cli(*args):
            done = subprocess.run([str(cli), *map(str, args)], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300)
            self.assertEqual(0, done.returncode, done.stdout + done.stderr)

        def fill(path: Path, value):
            with open(path, encoding="utf-8-sig", newline="") as stream:
                rows = list(csv.DictReader(stream))
            for row in rows:
                row["translation"] = value(row["source_text"])
            with open(path, "w", encoding="utf-8", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)

        def build(game: Path, out: Path) -> Path:
            done = []
            run_patch_task(out / "translation.csv", out / "manifest.json", str(game), str(out), progress=lambda *_: None, log=lambda *_: None,
                           complete=done.append)
            self.assertTrue(done[-1].get("ok"), done[-1])
            return max(out.rglob("patch_manifest.json"), key=lambda p: p.stat().st_mtime).parent

        with tempfile.TemporaryDirectory(dir=WORK) as temp:
            base = Path(temp)
            game = base / "game copy"
            game.mkdir()
            layouts.LAYOUTS["loose_rpy"][0](game)
            for folder in ("renpy", "lib"):
                (game / folder).mkdir(exist_ok=True)
            (game / "game" / "script.rpy").write_text('define e = Character("Eileen")\nlabel start:\n    e "Hello there."\n    "A second line."\n    return\n',
                                                      encoding="utf-8")
            original = _tree(game)
            out_a = base / "package-a"
            done = []
            run_extract_task(str(game), str(out_a), "deep", "balanced", False, renpy_sdk_path=str(SDK), renpy_sdk_action="existing",
                             progress=lambda *_: None, log=lambda *_: None, complete=done.append)
            self.assertEqual("COMPLETE", done[-1].get("extract_status"), done[-1])
            fill(out_a / "translation.csv", lambda s: "Xin chào." if s.startswith("Hello") else "Dòng thứ hai.")
            patch_a = build(game, out_a)
            run_cli("install", patch_a, game)
            with_a = _tree(game, skip_receipt=True)

            out_b = base / "package-b"
            shutil.copytree(out_a, out_b, ignore=shutil.ignore_patterns("Patch_*", ".patch-build", ".mt"))
            fill(out_b / "translation.csv", lambda s: "Chào bạn." if s.startswith("Hello") else "Dòng hai.")
            patch_b = build(game, out_b)                 # built from the game WITH patch A installed
            run_cli("install", patch_b, game)            # one-step upgrade over A
            overlay = (game / "game" / "tl" / "vietnamese" / "vntext.rpy").read_text(encoding="utf-8")
            self.assertIn("Chào bạn.", overlay)
            self.assertNotIn("Xin chào.", overlay)
            run_cli("uninstall", patch_b, game)          # back to exactly patch A
            self.assertEqual(with_a, _tree(game, skip_receipt=True))
            run_cli("restore-original", patch_b, game)   # and to the original game, from B's package and the receipt alone (A's package is gone in the app)
            self.assertEqual(original, _tree(game))


if __name__ == "__main__":
    unittest.main()
