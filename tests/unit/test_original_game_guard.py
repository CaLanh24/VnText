import json
from pathlib import Path
import shutil
import unittest

from tests.lib.work_paths import work_temp_dir
from tests.tools import original_game_guard as guard

INSTALLER = b"fake exact installer"
PATCH = ["game/tl/vietnamese/vntext.rpy", "game/zzz_vntext_vietnamese.rpy"]


class OriginalGameGuardTests(unittest.TestCase):
    def setUp(self):
        self.tmp = work_temp_dir("original-game-guard") / self._testMethodName
        shutil.rmtree(self.tmp, ignore_errors=True)
        self.tmp.mkdir(parents=True)
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        t = self.tmp
        self.game, self.owner, self.pkg, self.base = t / "game", t / "owner", t / "pkg", t / "baseline"
        (self.game / "game/cache").mkdir(parents=True)
        (self.game / "game/archive.rpa").write_bytes(b"archive")
        (self.game / "game/cache/a.rpyb").write_bytes(b"cache original")
        (self.game / "game/script.rpy").write_bytes(b"script")
        self.owner.mkdir()
        (self.owner / "tokens.txt").write_bytes(b"current owner file")
        self.pkg.mkdir()
        (self.pkg / "VNTextPatchInstaller.exe").write_bytes(INSTALLER)
        (self.pkg / "patch_manifest.json").write_text(json.dumps({"files": [{"path": p} for p in PATCH]}), encoding="utf-8")
        self.rar = t / "game.rar"
        self.rar.write_bytes(b"rar bytes")
        self.installer_sha = guard.sha(self.pkg / "VNTextPatchInstaller.exe")
        guard.snapshot(self.game, self.owner, self.rar, self.base, ["game/cache/a.rpyb"], guard.sha(self.game / "game/archive.rpa"), running=lambda: False)
        self.result = t / "result.json"
        self.evidence = t / "evidence"
        self.uninstalled = []

    def simulate_run(self):
        (self.game / "game/cache/a.rpyb").write_bytes(b"cache rewritten by the game")
        (self.game / "game/saves").mkdir()
        (self.game / "game/saves/1-1.save").write_bytes(b"save")
        (self.game / "game/tl/vietnamese").mkdir(parents=True)
        (self.game / "game/tl/vietnamese/vntext.rpy").write_bytes(b"patch")
        (self.game / "game/zzz_vntext_vietnamese.rpy").write_bytes(b"patch2")
        # real Ren'Py always compiles a matching .rpyc next to every installed .rpy, even with PYTHONDONTWRITEBYTECODE
        (self.game / "game/tl/vietnamese/vntext.rpyc").write_bytes(b"compiled 1")
        (self.game / "game/zzz_vntext_vietnamese.rpyc").write_bytes(b"compiled 2")

    def fake_uninstall(self, installer, game, pkg):
        self.uninstalled.append(guard.sha(installer))
        for rel in PATCH:                                                   # the exact installer removes its .rpy files and leaves empty directories behind
            (game / Path(*rel.split("/"))).unlink()
        return {"exit": 0}

    def call(self, execute=False, installer_sha=None, running=lambda: False, uninstall=None, rar=None):
        return guard.restore(self.base, self.game, self.owner, rar or self.rar, self.pkg, self.installer_sha if installer_sha is None else installer_sha, execute=execute,
                             evidence=self.evidence, result_path=self.result, uninstall=uninstall or self.fake_uninstall, running=running)

    def test_baseline_is_exact_and_verify_is_read_only(self):
        baseline = json.loads((self.base / "before.json").read_text(encoding="utf-8"))
        self.assertTrue(guard.verify(baseline, self.game, self.owner)["exact"])
        self.assertTrue(baseline["archive_rpa_ok"])
        self.assertEqual(["game/cache/a.rpyb"], baseline["backup_game_files"])

    def test_dry_run_plans_but_changes_nothing(self):
        self.simulate_run()
        before = (guard.snap(self.game), guard.snap(self.owner))
        r = self.call(execute=False)
        self.assertEqual("DRY_RUN", r["mode"])
        self.assertEqual(["game/cache/a.rpyb"], r["plan"]["restore_from_backup"])
        self.assertEqual(["game/saves/1-1.save"], r["plan"]["remove_run_owned_saves"])
        self.assertEqual(sorted(PATCH), sorted(r["plan"]["removed_by_exact_uninstall"]))
        self.assertEqual(sorted(p + "c" for p in PATCH), sorted(r["plan"]["remove_compiled_siblings"]))
        self.assertEqual(before, (guard.snap(self.game), guard.snap(self.owner)))
        self.assertEqual([], self.uninstalled)
        self.assertFalse(self.result.exists() or self.evidence.exists())

    def test_execute_restores_exactly_and_never_touches_owner_data(self):
        self.simulate_run()
        owner_before = guard.snap(self.owner)
        r = self.call(execute=True)
        self.assertTrue(r["final"]["game_exact"] and r["final"]["owner_exact"])
        self.assertEqual([self.installer_sha], self.uninstalled)
        self.assertFalse((self.game / "game/tl").exists() or (self.game / "game/saves").exists())      # empty run-created directories are gone, nothing else
        self.assertEqual(owner_before, guard.snap(self.owner))
        self.assertTrue((self.evidence / "1-1.save").is_file())             # run-owned save archived before removal
        self.assertTrue(guard.verify(json.loads((self.base / "before.json").read_text(encoding="utf-8")), self.game, self.owner)["exact"])
        with self.assertRaises(guard.Refused):                               # the result is never overwritten
            self.call(execute=True)

    def test_unexplained_differences_are_refused_without_any_change(self):
        self.simulate_run()
        (self.game / "game/extra.dat").write_bytes(b"unexpected addition")
        (self.game / "game/script.rpy").write_bytes(b"script edited, no backup exists")
        before = guard.snap(self.game)
        for execute in (False, True):
            with self.assertRaises(guard.Refused) as ctx:
                self.call(execute=execute)
            self.assertIn("extra.dat", str(ctx.exception))
            self.assertIn("script.rpy", str(ctx.exception))
        self.assertEqual(before, guard.snap(self.game))
        self.assertEqual([], self.uninstalled)

    def test_backup_hash_mismatch_is_refused(self):
        self.simulate_run()
        (self.base / "game-files/game/cache/a.rpyb").write_bytes(b"tampered backup")
        with self.assertRaises(guard.Refused):
            self.call(execute=True)
        self.assertEqual([], self.uninstalled)

    def test_preconditions_fail_closed(self):
        self.simulate_run()
        with self.assertRaises(guard.Refused):
            self.call(installer_sha="0" * 64)                                # wrong installer
        with self.assertRaises(guard.Refused):
            self.call(installer_sha="")                                      # installer sha is mandatory (no default, no skip)
        with self.assertRaises(guard.Refused):
            self.call(running=lambda: True)                                  # game still running
        self.rar.write_bytes(b"another rar")
        with self.assertRaises(guard.Refused):
            self.call()                                                      # RAR differs from the baseline value
        self.assertEqual([], self.uninstalled)

    def test_leftover_patch_files_after_uninstall_stop_the_restore(self):
        self.simulate_run()
        with self.assertRaises(guard.Refused):
            self.call(execute=True, uninstall=lambda i, g, p: {"exit": 1})
        self.assertEqual("cache rewritten by the game", (self.game / "game/cache/a.rpyb").read_bytes().decode())   # nothing restored after a failed uninstall

    def test_only_compiled_siblings_of_the_exact_patch_files_are_owned(self):
        self.simulate_run()
        for stray in ("game/other.rpyc", "game/tl/vietnamese/unrelated.rpyc", "game/script.rpyc", "game/zzz_vntext_vietnamese.rpycx"):
            p = self.game / Path(*stray.split("/"))
            p.write_bytes(b"x")
            with self.assertRaises(guard.Refused) as ctx:
                self.call(execute=True)
            self.assertIn(stray, str(ctx.exception))
            p.unlink()
        self.assertEqual([], self.uninstalled)                              # refused before the uninstall, no file touched
        bad = self.tmp / "badpkg"
        bad.mkdir()
        (bad / "VNTextPatchInstaller.exe").write_bytes(INSTALLER)
        (bad / "patch_manifest.json").write_text(json.dumps({"files": [{"path": "../outside.rpy"}]}), encoding="utf-8")
        with self.assertRaises(guard.Refused):
            guard.restore(self.base, self.game, self.owner, self.rar, bad, self.installer_sha, running=lambda: False)

    def test_owner_files_and_directories_are_compared_and_never_written(self):
        self.simulate_run()
        baseline = json.loads((self.base / "before.json").read_text(encoding="utf-8"))
        (self.owner / "newdir").mkdir()
        (self.owner / "tokens.txt").write_bytes(b"changed by something else")
        report = guard.verify(baseline, self.game, self.owner)
        self.assertFalse(report["exact"])
        self.assertEqual(["newdir"], report["owner_dirs_diff"])
        self.assertEqual(["tokens.txt"], report["owner"]["changed"])
        before = guard.snap(self.owner)
        with self.assertRaises(guard.Refused) as ctx:
            self.call(execute=True)                                          # the game side is restored, but a differing Owner AppData fails the readback
        self.assertIn("owner_exact=False", str(ctx.exception))
        self.assertEqual(before, guard.snap(self.owner))                    # not one Owner byte was written
        result = json.loads(self.result.read_text(encoding="utf-8"))
        self.assertTrue(result["final"]["game_exact"] and not result["final"]["owner_exact"])

    def test_junctions_and_overlapping_trees_are_refused(self):
        self.simulate_run()
        with self.assertRaises(guard.Refused):
            guard.restore(self.base, self.game, self.owner, self.rar, self.game, self.installer_sha, running=lambda: False)     # package == game
        inner = self.game / "game" / "pkg"
        inner.mkdir()
        (inner / "VNTextPatchInstaller.exe").write_bytes(INSTALLER)
        (inner / "patch_manifest.json").write_text(json.dumps({"files": [{"path": p} for p in PATCH]}), encoding="utf-8")
        with self.assertRaises(guard.Refused):
            guard.restore(self.base, self.game, self.owner, self.rar, inner, self.installer_sha, running=lambda: False)         # package inside the game
        shutil.rmtree(inner)
        outside = self.tmp / "outside"
        outside.mkdir()
        link = self.game / "game" / "junction"
        made = __import__("subprocess").run(["cmd", "/c", "mklink", "/J", str(link), str(outside)], capture_output=True, text=True)
        if made.returncode != 0:
            self.skipTest("junction creation is not available here")
        try:
            with self.assertRaises(guard.Refused):
                guard.snap(self.game)
            with self.assertRaises(guard.Refused):
                self.call()
        finally:
            __import__("os").rmdir(link)

    def test_snapshot_never_overwrites_a_baseline(self):
        with self.assertRaises(guard.Refused):
            guard.snapshot(self.game, self.owner, self.rar, self.base, [], "x", running=lambda: False)


if __name__ == "__main__":
    unittest.main()
