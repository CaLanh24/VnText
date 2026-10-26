"""The one-time User PATH repair and the process-only sanitiser.  These tests never read or write the real registry."""
import json
import ntpath
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import unittest.mock
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "tests" / "lib"), str(ROOT / "tests" / "tools")]
import path_hygiene  # noqa: E402
import user_path_repair as repair  # noqa: E402

REPO = r"C:\v"
LEGIT = r"C:\Users\VNTextDev\.dotnet\tools"
BASE = [r"C:\Users\VNTextDev\AppData\Local\Microsoft\WindowsApps", LEGIT, r"C:\Users\VNTextDev\.local\bin"]
HEX = "e5eb63142c554f8c97d55316fb863ebd"


def family_a(n=0):
    return rf"C:\v\TEST_RUN\wpf_workflow_{n:032x}\runtime\dotnet\.dotnet\tools"


def family_b(n=0, which="baseline"):
    return rf"C:\v\TEST_RUN\wpf_workflow_{n:032x}\update-version-fixtures\{which}\runtime\dotnet\.dotnet\tools"


def family_c(scope="p13a"):
    return rf"C:\v\RELEASE_RUN\candidate-0.1.13\{scope}\_dotnet\cli_home\.dotnet\tools"


def polluted(count=3):
    items = list(BASE)
    for n in range(count):
        items += [family_a(n), family_b(n, "baseline"), family_b(n, "candidate"), family_c(f"p13{chr(97 + n)}")]
    return ";".join(items)


class FakeStore:
    """In-memory User PATH.  ``on_read[n]`` runs just before the n-th read returns (simulates a foreign writer)."""

    def __init__(self, value, kind=2, on_read=None, on_write=None):
        self.value, self.kind, self.on_read, self.on_write = value, kind, on_read or {}, on_write
        self.reads, self.writes = 0, []

    def read(self):
        self.reads += 1
        if self.reads in self.on_read:
            self.on_read[self.reads](self)
        return self.value, self.kind

    def write(self, value, kind):
        self.writes.append((value, kind))
        self.value, self.kind = value, kind
        if self.on_write:
            self.on_write(self)


def missing(_path):
    return False


class FamilyTests(unittest.TestCase):
    def test_exact_families_only(self):
        for entry in (family_a(), family_b(1, "baseline"), family_b(2, "candidate"), family_c("p13j"), family_a() + "\\", family_a().upper().replace("TEST_RUN", "test_run")):
            with self.subTest(entry=entry):
                self.assertTrue(path_hygiene.is_stale_entry(entry, REPO), entry)
        for entry in (
            LEGIT, "", r"C:\v\.dev-env\dotnet-home\.dotnet\tools", r"C:\other\TEST_RUN\wpf_workflow_%s\runtime\dotnet\.dotnet\tools" % HEX,
            r"C:\v\TEST_RUN2\wpf_workflow_%s\runtime\dotnet\.dotnet\tools" % HEX,
            r"C:\v\TEST_RUN\wpf_workflow_%s\runtime\dotnet\.dotnet\tools\extra" % HEX,
            r"C:\v\TEST_RUN\wpf_workflow_%s\runtime\dotnet\.dotnet" % HEX,
            r"C:\v\TEST_RUN\wpf_workflow_short\runtime\dotnet\.dotnet\tools",                 # not a 32-hex id
            r"C:\v\TEST_RUN\somethingelse\runtime\dotnet\.dotnet\tools",                      # arbitrary TEST_RUN dir is NOT a family
            r"C:\v\TEST_RUN\x\.dotnet\tools", r"C:\v\RELEASE_RUN\x\.dotnet\tools",
            r"C:\v\RELEASE_RUN\candidate-0.1.13\p13a\build\.dotnet\tools",                    # not the _dotnet\cli_home layout
            r"C:\v\TEST_RUN\wpf_workflow_%s\update-version-fixtures\other\runtime\dotnet\.dotnet\tools" % HEX,
        ):
            with self.subTest(entry=entry):
                self.assertFalse(path_hygiene.is_stale_entry(entry, REPO), entry)

    def test_process_only_sanitiser_changes_a_copy_and_keeps_everything_else(self):
        env = {"Path": ";".join(BASE + [family_a(), r"C:\Windows", family_c("p13z"), ""]), "OTHER": "1"}
        before = dict(env)
        removed = path_hygiene.sanitize_env_path(env, REPO)
        self.assertEqual([family_a(), family_c("p13z")], removed)
        self.assertEqual(";".join(BASE + [r"C:\Windows", ""]), env["Path"])           # case-insensitive key, order and empty item kept
        self.assertEqual("1", env["OTHER"])
        clean = {"PATH": ";".join(BASE)}
        self.assertEqual([], path_hygiene.sanitize_env_path(clean, REPO))
        self.assertEqual({"PATH": ";".join(BASE)}, clean)
        self.assertEqual([], path_hygiene.sanitize_env_path({}, REPO))                  # no PATH key: nothing to do
        self.assertNotEqual(before, env)


class PlanTests(unittest.TestCase):
    def plan(self, value, existing=()):
        keep = {ntpath.normcase(e) for e in existing}
        return repair.plan(value, REPO, lambda path: ntpath.normcase(path) in keep)

    def test_removes_only_exact_family_missing_dirs_in_order(self):
        value = polluted(3)
        result = self.plan(value)
        self.assertEqual(12, len(result["removed"]))
        self.assertEqual(";".join(BASE), result["new_value"])
        self.assertEqual(LEGIT, result["kept_dotnet_tools"][0]["entry"])
        removed = {r["entry"] for r in result["removed"]}
        self.assertEqual([i for i in value.split(";") if i not in removed], result["new_value"].split(";"))

    def test_keeps_existing_dirs_non_family_text_and_preserves_empties(self):
        existing = family_a(7)
        items = BASE + [existing, "", r"C:\v\TEST_RUN\other\runtime\dotnet\.dotnet\tools", family_a(8), r"C:\Windows", ""]
        result = self.plan(";".join(items), existing={existing})
        self.assertEqual([family_a(8)], [r["entry"] for r in result["removed"]])
        self.assertEqual([i for i in items if i != family_a(8)], result["new_value"].split(";"))
        self.assertTrue(result["new_value"].endswith(";"))
        reasons = {k["entry"]: k["reason"] for k in result["kept_dotnet_tools"]}
        self.assertEqual("directory still exists", reasons[existing])

    def test_nothing_to_remove_is_a_no_op(self):
        value = ";".join(BASE)
        self.assertEqual([], self.plan(value)["removed"])
        store = FakeStore(value)
        with tempfile.TemporaryDirectory() as temp, self.assertRaisesRegex(RuntimeError, "nothing to remove"):
            repair.apply(store, expected_sha256=repair.sha256_text(value), backup_path=Path(temp) / "b.json", repo_root=REPO, exists=missing)
        self.assertEqual([], store.writes)


class ApplyTests(unittest.TestCase):
    def apply(self, store, value, temp, **overrides):
        kwargs = dict(expected_sha256=repair.sha256_text(value), backup_path=Path(temp) / "backup.json", repo_root=REPO, exists=missing)
        kwargs.update(overrides)
        return repair.apply(store, **kwargs)

    def test_success_writes_once_keeps_kind_and_an_exclusive_backup(self):
        value = polluted(2)
        with tempfile.TemporaryDirectory() as temp:
            store = FakeStore(value, kind=2)
            report = self.apply(store, value, temp)
            self.assertEqual(8, len(report["removed"]))
            self.assertEqual([(";".join(BASE), 2)], store.writes)
            saved = json.loads((Path(temp) / "backup.json").read_text(encoding="utf-8"))
            self.assertEqual((value, 2, repair.sha256_text(value)), (saved["value"], saved["registry_kind"], saved["sha256"]))
            self.assertEqual(report["after"]["sha256"], saved["planned_sha256"])

    def test_stale_dry_run_hash_writes_nothing_and_creates_no_backup(self):
        value = polluted(1)
        with tempfile.TemporaryDirectory() as temp:
            store = FakeStore(value)
            with self.assertRaisesRegex(RuntimeError, "changed since the dry run"):
                self.apply(store, value, temp, expected_sha256="0" * 64)
            self.assertEqual([], store.writes)
            self.assertFalse((Path(temp) / "backup.json").exists())

    def test_foreign_change_between_plan_and_write_aborts_without_writing(self):
        value = polluted(1)
        for label, hook in (
            ("value", lambda s: setattr(s, "value", s.value + ";C:\\foreign")),
            ("kind", lambda s: setattr(s, "kind", 1)),
        ):
            with self.subTest(label), tempfile.TemporaryDirectory() as temp:
                store = FakeStore(value, on_read={2: hook})       # read 1 = plan, read 2 = the immediate pre-write re-read
                with self.assertRaisesRegex(RuntimeError, "changed between planning and the write"):
                    self.apply(store, value, temp)
                self.assertEqual([], store.writes)                  # the foreign value is untouched

    def test_foreign_change_after_the_write_is_reported_and_never_overwritten(self):
        value = polluted(1)
        with tempfile.TemporaryDirectory() as temp:
            store = FakeStore(value, on_write=lambda s: setattr(s, "value", s.value + ";C:\\foreign-after"))
            with self.assertRaisesRegex(RuntimeError, "nothing further written"):
                self.apply(store, value, temp)
            self.assertEqual(1, len(store.writes))                  # exactly one write: no restore write over the foreign value
            self.assertTrue(store.value.endswith(";C:\\foreign-after"))
            self.assertTrue((Path(temp) / "backup.json").exists())  # backup kept for a manual decision

    def test_existing_backup_is_never_overwritten_and_no_write_happens(self):
        value = polluted(1)
        with tempfile.TemporaryDirectory() as temp:
            backup = Path(temp) / "backup.json"
            backup.write_text("precious", encoding="utf-8")
            store = FakeStore(value)
            with self.assertRaisesRegex(RuntimeError, "existing backup"):
                self.apply(store, value, temp)
            self.assertEqual("precious", backup.read_text(encoding="utf-8"))
            self.assertEqual([], store.writes)

    def test_restore_only_while_the_current_value_is_still_the_one_written(self):
        value = polluted(2)
        with tempfile.TemporaryDirectory() as temp:
            store = FakeStore(value, kind=2)
            self.apply(store, value, temp)
            backup = Path(temp) / "backup.json"
            foreign = FakeStore(store.value + ";C:\\someone-added-this", kind=2)
            with self.assertRaisesRegex(RuntimeError, "foreign change"):
                repair.restore(foreign, backup_path=backup)
            self.assertEqual([], foreign.writes)
            result = repair.restore(store, backup_path=backup)
            self.assertEqual(value, store.value)
            self.assertEqual(repair.sha256_text(value), result["restored_sha256"])
            self.assertEqual(2, store.kind)

    def test_restore_requires_both_the_planned_hash_and_the_original_kind(self):
        value = polluted(2)
        with tempfile.TemporaryDirectory() as temp:
            store = FakeStore(value, kind=2)
            self.apply(store, value, temp)
            backup = Path(temp) / "backup.json"
            store.kind = 1                                                   # same value hash, different registry kind
            writes_before = len(store.writes)
            with self.assertRaisesRegex(RuntimeError, "value or kind"):
                repair.restore(store, backup_path=backup)
            self.assertEqual(writes_before, len(store.writes))               # nothing written over the foreign kind
            store.kind = 2
            self.assertEqual(2, repair.restore(store, backup_path=backup)["registry_kind"])

    def test_unsupported_raw_values_and_kinds_are_refused_everywhere(self):
        value = polluted(1)
        for bad_kind in (0, 3, 4, 7, True, None, "2"):
            with self.subTest(kind=bad_kind), tempfile.TemporaryDirectory() as temp:
                store = FakeStore(value, kind=bad_kind)
                with self.assertRaisesRegex(RuntimeError, "unsupported User PATH registry value"):
                    self.apply(store, value, temp)
                self.assertEqual([], store.writes)
                self.assertFalse((Path(temp) / "backup.json").exists())
        for bad_value in (b"bytes", ["list"], None, 12):
            with self.subTest(value=type(bad_value).__name__), tempfile.TemporaryDirectory() as temp:
                store = FakeStore(bad_value, kind=2)
                with self.assertRaisesRegex(RuntimeError, "unsupported User PATH registry value"):
                    repair.apply(store, expected_sha256="0" * 64, backup_path=Path(temp) / "b.json", repo_root=REPO, exists=missing)
                self.assertEqual([], store.writes)
        for good_kind in (1, 2):                                             # REG_SZ and REG_EXPAND_SZ are accepted and preserved
            with self.subTest(kind=good_kind), tempfile.TemporaryDirectory() as temp:
                store = FakeStore(value, kind=good_kind)
                self.apply(store, value, temp)
                self.assertEqual(good_kind, store.writes[0][1])
        # A corrupt backup record cannot smuggle an unsupported kind into a restore.
        with tempfile.TemporaryDirectory() as temp:
            store = FakeStore(value, kind=2)
            self.apply(store, value, temp)
            backup = Path(temp) / "backup.json"
            record = json.loads(backup.read_text(encoding="utf-8"))
            record["registry_kind"] = 3
            backup.write_text(json.dumps(record), encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "unsupported User PATH registry value"):
                repair.restore(store, backup_path=backup)

    def test_the_real_registry_reader_validates_what_winreg_returns(self):
        for returned in ((b"\x00", 3), ("C:\\x", 0), ("C:\\x", 7)):
            with self.subTest(returned=returned), unittest.mock.patch("winreg.OpenKey"), unittest.mock.patch("winreg.QueryValueEx", return_value=returned):
                with self.assertRaisesRegex(RuntimeError, "unsupported User PATH registry value"):
                    repair.UserRegistryPath().read()
        with unittest.mock.patch("winreg.OpenKey"), unittest.mock.patch("winreg.QueryValueEx", return_value=("C:\\x;D:\\y", 2)):
            self.assertEqual(("C:\\x;D:\\y", 2), repair.UserRegistryPath().read())

    def test_module_can_only_write_the_user_scope(self):
        source = Path(repair.__file__).read_text(encoding="utf-8")
        self.assertNotIn("HKEY_LOCAL_MACHINE", source)
        self.assertNotIn("Session Manager", source)
        self.assertIn("HKEY_CURRENT_USER", source)
        self.assertIn("no atomic compare-and-set", source.replace("NO atomic", "no atomic"))   # the limit is documented, not claimed away


SAMPLES = [
    (family_a(), True), (family_b(1, "baseline"), True), (family_b(2, "candidate"), True), (family_c("p13j"), True),
    (family_a() + "\\", True),
    (LEGIT, False), (r"C:\v\.dev-env\dotnet-home\.dotnet\tools", False),
    (r"C:\v\TEST_RUN\x\.dotnet\tools", False), (r"C:\v\TEST_RUN2\wpf_workflow_%s\runtime\dotnet\.dotnet\tools" % HEX, False),
    (r"C:\other\TEST_RUN\wpf_workflow_%s\runtime\dotnet\.dotnet\tools" % HEX, False),
    (r"C:\v\TEST_RUN\wpf_workflow_%s\runtime\dotnet\.dotnet\tools\extra" % HEX, False),
    (r"C:\v\RELEASE_RUN\candidate-0.1.13\p13a\build\.dotnet\tools", False),
]


class OwnedBoundaryTests(unittest.TestCase):
    """Stale homes retained in the persistent User PATH must not reach children of the owned boundaries (process-only)."""

    def polluted_env(self):
        return {"PATH": ";".join(BASE + [family_a(3), family_c("p13k"), r"C:\Windows"]), "DOTNET_ADD_GLOBAL_TOOLS_TO_PATH": "1"}

    def test_publisher_pattern_agrees_with_the_python_families(self):
        pwsh = shutil.which("pwsh")
        if pwsh is None:
            self.skipTest("pwsh is not installed")
        text = (ROOT / "release" / "publish.ps1").read_text(encoding="utf-8")
        line = next(l for l in text.splitlines() if l.startswith("$stalePathPattern = "))
        self.assertIn("-split ';'", text)
        self.assertIn("$canonicalRepoRoot.TrimEnd", line)                                 # the validated root, not the snapshot's $DevRoot
        self.assertLess(text.index("$canonicalRepoRoot = Split-Path"), text.index("$stalePathPattern ="))
        self.assertLess(text.index("DevRunRoot must be the canonical project's DEV_RUN"), text.index("$stalePathPattern ="))
        script = "\n".join([
            r"$canonicalRepoRoot = 'C:\v'", line,
            "$samples = @(" + ",".join("'" + e.replace("'", "''") + "'" for e, _ in SAMPLES) + ")",
            "($samples | ForEach-Object { [bool]($_ -match $stalePathPattern) }) | ConvertTo-Json -Compress",
        ])
        out = subprocess.run([pwsh, "-NoProfile", "-NonInteractive", "-Command", script], capture_output=True, text=True, timeout=60)
        self.assertEqual(0, out.returncode, out.stderr)
        self.assertEqual([want for _, want in SAMPLES], json.loads(out.stdout))
        self.assertEqual([want for _, want in SAMPLES], [path_hygiene.is_stale_entry(e, REPO) for e, _ in SAMPLES])
        # ... and it runs before the first SDK call of the publisher.
        self.assertLess(text.index("$stalePathPattern ="), text.index("DOTNET_CLI_HOME = $dotnetCliHome"))

    def test_bootstrap_inherited_environment_is_sanitised_but_an_explicit_mapping_is_not(self):
        from release import dev_bootstrap

        seen = []

        def fake_run(command, **kwargs):
            seen.append(kwargs["env"])
            return unittest.mock.Mock(returncode=0, stdout="", stderr="")

        stale = [family_a(3), family_c("p13k")]
        with unittest.mock.patch.dict(os.environ, {"PATH": ";".join(BASE + stale + [r"C:\Windows"])}), unittest.mock.patch.object(dev_bootstrap.subprocess, "run", fake_run):
            dev_bootstrap.run(["dotnet", "--list-runtimes"])
            self.assertEqual(";".join(BASE + stale + [r"C:\Windows"]), os.environ["PATH"])   # the caller's own environment is unchanged
        child_path = seen[0]["PATH"].split(";")
        # Entries are recognised relative to the repository the module lives in, so use real family paths under it.
        repo_family = str(ROOT / "TEST_RUN" / ("wpf_workflow_" + HEX) / "runtime" / "dotnet" / ".dotnet" / "tools")
        with unittest.mock.patch.dict(os.environ, {"PATH": ";".join(BASE + [repo_family, r"C:\Windows"])}), unittest.mock.patch.object(dev_bootstrap.subprocess, "run", fake_run):
            dev_bootstrap.run(["dotnet", "--list-runtimes"])
            caller = {"PATH": ";".join(BASE + [repo_family]), "DOTNET_ADD_GLOBAL_TOOLS_TO_PATH": "1"}
            dev_bootstrap.run(["dotnet", "build"], env=caller)
        self.assertNotIn(repo_family, seen[1]["PATH"].split(";"))
        self.assertIn(r"C:\Windows", seen[1]["PATH"].split(";"))
        self.assertIs(caller, seen[2])                                                    # explicit mapping passed through untouched
        self.assertIn(repo_family, seen[2]["PATH"].split(";"))
        self.assertEqual("0", seen[0]["DOTNET_ADD_GLOBAL_TOOLS_TO_PATH"])
        self.assertTrue(child_path)

    def test_bootstrap_owned_explicit_build_mapping_is_sanitised(self):
        from release import dev_bootstrap

        repo_family = str(ROOT / "TEST_RUN" / ("wpf_workflow_" + HEX) / "runtime" / "dotnet" / ".dotnet" / "tools")
        result = {"python": {"path": r"C:\py\python.exe"}, "model": {"path": ""}}
        with tempfile.TemporaryDirectory() as temp:
            cache, output = Path(temp) / "cache", Path(temp) / "out"
            with unittest.mock.patch.dict(os.environ, {"PATH": ";".join(BASE + [repo_family, r"C:\Windows"]), "DOTNET_ADD_GLOBAL_TOOLS_TO_PATH": "1"}):
                env = dev_bootstrap.owned_build_env(result, output, cache, r"C:\dotnet")
                self.assertIn(repo_family, os.environ["PATH"].split(";"))               # the caller's own environment is unchanged
            self.assertNotIn(repo_family.lower(), [e.lower() for e in env["PATH"].split(";")])
            self.assertIn(r"C:\Windows", env["PATH"].split(";"))
            self.assertEqual("0", env["DOTNET_ADD_GLOBAL_TOOLS_TO_PATH"])                   # guard still forced
            self.assertEqual(str(cache / "dotnet-home"), env["DOTNET_CLI_HOME"])
        source = (ROOT / "release" / "dev_bootstrap.py").read_text(encoding="utf-8")
        self.assertIn("env = owned_build_env(result, output, cache, runtime_root)", source)    # main() uses it for the build and the smoke
        self.assertNotIn("env = os.environ.copy()\n            runtime_root", source)        # no un-sanitised owned mapping left in main()

    def test_wpf_harness_environment_drops_stale_homes_in_a_real_child_process(self):
        sys.path[:0] = [str(ROOT)]
        from tests.unit.test_wpf_workflow import _harness_env

        repo_family = str(ROOT / "TEST_RUN" / ("wpf_workflow_" + HEX) / "update-version-fixtures" / "baseline" / "runtime" / "dotnet" / ".dotnet" / "tools")
        with tempfile.TemporaryDirectory() as temp, unittest.mock.patch.dict(os.environ, {"PATH": os.environ.get("PATH", "") + ";" + repo_family}):
            env = _harness_env(Path(temp))
            self.assertEqual("0", env["DOTNET_ADD_GLOBAL_TOOLS_TO_PATH"])
            self.assertNotIn(repo_family.lower(), [e.lower() for e in env.get("PATH", env.get("Path", "")).split(";")])
            child = subprocess.run([sys.executable, "-I", "-c", "import os;print(os.environ.get('PATH',''))"], env=env, capture_output=True, text=True, timeout=60)
            self.assertEqual(0, child.returncode, child.stderr)
            self.assertNotIn(repo_family.lower(), [e.lower() for e in child.stdout.strip().split(";")])
            self.assertGreater(len(child.stdout.strip().split(";")), 3)                    # the rest of PATH is intact

    def test_canonical_runner_sanitises_its_child_environment(self):
        source = (ROOT / "tests" / "tools" / "run_with_cleanup.py").read_text(encoding="utf-8")
        guard = source.index('env["DOTNET_ADD_GLOBAL_TOOLS_TO_PATH"] = "0"')
        self.assertIn("path_hygiene.sanitize_env_path(env, ROOT)", source[guard:guard + 600])
        self.assertLess(guard, source.index("proc = subprocess.Popen("))


if __name__ == "__main__":
    unittest.main()
