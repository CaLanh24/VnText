"""Public bootstrap guards: no downloads, truthful blockers, bounded owned output."""
import contextlib
import io
import json
import re
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from release import dev_bootstrap as dev


def receipt(stdout="", exit_code=0):
    return {"stdout": stdout, "stderr": "", "exit_code": exit_code}


class DevBootstrapTests(unittest.TestCase):
    def test_run_overrides_global_tools_guard_without_mutating_the_caller_mapping(self):
        seen = []

        def fake_run(command, **kwargs):
            seen.append(kwargs["env"].get("DOTNET_ADD_GLOBAL_TOOLS_TO_PATH", "<absent>"))
            return SimpleNamespace(returncode=0, stdout="", stderr="")

        # Inherited-environment boundary (preflight SDK probes): forced to 0 on a copy.
        for label, inherited in (("missing", None), ("stale_one", "1"), ("malicious_true", "true")):
            patched = {k: v for k, v in dev.os.environ.items() if k != "DOTNET_ADD_GLOBAL_TOOLS_TO_PATH"}
            if inherited is not None:
                patched["DOTNET_ADD_GLOBAL_TOOLS_TO_PATH"] = inherited
            with self.subTest(case=label), patch.dict(dev.os.environ, patched, clear=True), \
                    patch.object(dev.subprocess, "run", side_effect=fake_run):
                dev.run(["dotnet", "--list-runtimes"])
                self.assertEqual(inherited, dev.os.environ.get("DOTNET_ADD_GLOBAL_TOOLS_TO_PATH"))  # caller env unchanged
        self.assertEqual(["0"] * 3, seen)
        # An explicit caller mapping is passed through untouched; its owner (main) sets the guard.
        caller = {"PATH": "x", "DOTNET_ADD_GLOBAL_TOOLS_TO_PATH": "1"}
        with patch.object(dev.subprocess, "run", side_effect=fake_run):
            dev.run(["dotnet", "build"], env=caller)
        self.assertEqual({"PATH": "x", "DOTNET_ADD_GLOBAL_TOOLS_TO_PATH": "1"}, caller)
        source = (Path(__file__).resolve().parents[2] / "release" / "dev_bootstrap.py").read_text(encoding="utf-8")
        self.assertIn('DOTNET_ADD_GLOBAL_TOOLS_TO_PATH="0"', source)  # the owned SDK build mapping

    def test_publisher_sets_the_global_tools_guard_before_every_sdk_boundary(self):
        text = (Path(__file__).resolve().parents[2] / "release" / "publish.ps1").read_text(encoding="utf-8")
        guard = 'DOTNET_ADD_GLOBAL_TOOLS_TO_PATH = "0"'
        self.assertNotIn("DOTNET_ADD_GLOBAL_TOOLS_TO_PATH = $", text)
        self.assertNotIn("DOTNET_ADD_GLOBAL_TOOLS_TO_PATH = '1'", text)
        # Each place that assigns a fresh CLI home also assigns the guard in the same block.
        positions = [m.start() for m in re.finditer(r"\$env:DOTNET_CLI_HOME\s*=", text)]
        self.assertGreaterEqual(len(positions), 3)
        for position in positions:
            self.assertIn(guard, text[max(0, position - 900): position + 900])
        # And the first guard assignment precedes the first SDK invocation.
        first_guard = text.index(guard)
        first_sdk = min(i for i in (text.find("& $dotnet "), text.find("(& $dotnet ")) if i >= 0)
        self.assertLess(first_guard, first_sdk)

    def test_launcher_carries_runtime_worker_model_and_local_data(self):
        environment = {key: "C:/owner's/" + key for key in (
            "DOTNET_ROOT", "DOTNET_ROOT_X64", "VNTEXT_WORKER_CWD", "VNTEXT_WORKER_PYTHON",
            "VNTEXT_CT2_MODEL", "VNTEXT_CT2_NO_DOWNLOAD", "VNTEXT_DATA_ROOT", "VNTEXT_LOCALAPPDATA")}
        with patch.object(Path, "write_text") as write:
            dev.write_launcher(Path("owned-output"), environment)
        script = write.call_args_list[0].args[0]
        for key in environment:
            self.assertIn(f"$env:{key} = 'C:/owner''s/{key}'", script)
        self.assertIn('@args', script)
        self.assertIn('Start-DEV.ps1', write.call_args_list[1].args[0])

    def test_build_identity_includes_untracked_status_and_assembly(self):
        result = {"source_sha": "source", "receipts": [], "python": {"path": "python"},
                  "model": {"path": "model"}}
        with patch.object(dev, "run", side_effect=[receipt(""), receipt("?? new-test.py\n")]), \
             patch.object(Path, "read_bytes", side_effect=[b"host", b"assembly"]):
            identity = dev.build_identity(Path("DEV_RUN/bootstrap-build"), result, "runtime8")
        self.assertTrue(identity["dirty"])
        self.assertNotEqual(identity["sha256"], identity["assembly_sha256"])
        self.assertEqual(len(result["receipts"]), 2)

    def test_build_identity_git_failure_blocks(self):
        result = {"receipts": []}
        with patch.object(dev, "run", side_effect=[receipt("", 1), receipt("")]):
            with self.assertRaisesRegex(ValueError, "Git build provenance"):
                dev.build_identity(Path("output"), result, "runtime8")

    def test_python_rejects_old_runtime_and_continues_discovery(self):
        results = [receipt(json.dumps({"path": "old", "version": [3, 10, 9]})),
                   receipt(json.dumps({"path": "new", "version": [3, 12, 14]}))]
        with patch.object(dev, "run", side_effect=results), patch.object(dev.shutil, "which", return_value=None):
            identity, checks = dev.discover_python()
        self.assertEqual(identity["path"], "new")
        self.assertEqual(len(checks), 2)

    def test_explicit_python_failure_does_not_silently_fallback(self):
        with patch.object(dev, "run", return_value=receipt("", 1)) as command:
            identity, checks = dev.discover_python("chosen-python")
        self.assertIsNone(identity)
        self.assertEqual(command.call_count, 1)

    def test_malformed_identity_is_not_readiness(self):
        with patch.object(dev, "run", return_value=receipt("not-json")):
            self.assertIsNone(dev.discover_python("python")[0])

    def test_dependency_error_is_not_empty_missing_list(self):
        with patch.object(dev, "run", return_value=receipt("", 1)):
            packages, raw = dev.requirements("python")
        self.assertTrue(packages["missing"])
        self.assertEqual(raw["exit_code"], 1)

    def test_dependency_invalid_output_blocks(self):
        with patch.object(dev, "run", return_value=receipt("broken")):
            self.assertTrue(dev.requirements("python")[0]["missing"])

    def test_missing_model_is_explicit_and_never_downloaded(self):
        with patch.object(Path, "is_dir", return_value=False):
            result = dev.model_inventory("absent-model")
        self.assertEqual(result["missing"], list(dev.MODEL_FILES))
        self.assertEqual(result["hashes"], {})
        self.assertIn("UNKNOWN", result["provenance"])

    def test_output_refuses_unowned_installation_and_escape(self):
        for target in ("DEV_RUN/v01_audit", "DEV_RUN/cache", "DEV_RUN/../data", "outside", "DEV_RUN/bootstrap-build/subdir"):
            with self.subTest(target=target), self.assertRaises(ValueError):
                dev.safe_output(target)

    def test_existing_output_needs_owner_marker(self):
        with patch.object(Path, "is_symlink", return_value=False), patch.object(Path, "exists", return_value=True), \
             patch.object(Path, "stat") as info, patch.object(Path, "is_file", return_value=False):
            info.return_value.st_file_attributes = 0
            with self.assertRaisesRegex(ValueError, "ownership"):
                dev.safe_output("DEV_RUN/bootstrap-build")

    def test_output_refuses_reparse_point(self):
        with patch.object(Path, "is_symlink", return_value=False), patch.object(Path, "exists", return_value=True), \
             patch.object(Path, "stat") as info:
            info.return_value.st_file_attributes = 0x400
            with self.assertRaisesRegex(ValueError, "linked"):
                dev.safe_output("DEV_RUN/bootstrap-build")

    def test_quota_reservation_checks_nonexempt_headroom(self):
        from tests.tools import cleanup_work_artifacts as cleanup
        inventory = {"complete": True, "within_limit": True, "non_exempt_bytes": 90, "limit_bytes": 100}
        with patch.object(cleanup, "_project_size_snapshot", return_value=inventory):
            self.assertTrue(dev.quota(10)[1])
            self.assertFalse(dev.quota(11)[1])

    def test_incomplete_inventory_never_allows_apply(self):
        from tests.tools import cleanup_work_artifacts as cleanup
        with patch.object(cleanup, "_project_size_snapshot", return_value={"complete": False, "within_limit": False}):
            self.assertFalse(dev.quota()[1])

    def test_exempt_overbudget_never_allows_apply(self):
        from tests.tools import cleanup_work_artifacts as cleanup
        with patch.object(cleanup, "_project_size_snapshot", return_value={"complete": True, "within_limit": False}):
            self.assertFalse(dev.quota()[1])

    def test_check_is_readonly_and_reports_missing_exit2(self):
        with patch.object(dev, "preflight", return_value={"missing": ["SDK8"]}), \
             patch.object(Path, "mkdir") as mkdir, contextlib.redirect_stdout(io.StringIO()) as output:
            code = dev.main([])
        self.assertEqual(code, 2)
        self.assertEqual(json.loads(output.getvalue())["exit_code"], 2)
        mkdir.assert_not_called()

    def test_check_repeated_uses_same_arguments_without_creating_resources(self):
        with patch.object(dev, "preflight", return_value={"missing": []}) as check, \
             patch.object(Path, "mkdir") as mkdir, contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(dev.main(["--python", "shared-python"]), 0)
            self.assertEqual(dev.main(["--python", "shared-python"]), 0)
        self.assertEqual(check.call_args_list[0], check.call_args_list[1])
        mkdir.assert_not_called()

    def test_spawn_error_retains_failure_without_fabricated_exit(self):
        with patch.object(dev.subprocess, "run", side_effect=OSError("missing executable")):
            result = dev.run(["absent"])
        self.assertIsNone(result["exit_code"])
        self.assertIn("missing executable", result["stderr"])

    def test_run_default_environment_preserves_python_context(self):
        with patch.dict(dev.os.environ, {"PYTHONPATH": "chosen-site-packages", "PYTHONNOUSERSITE": "1"}, clear=True), \
             patch.object(dev.subprocess, "run", return_value=SimpleNamespace(returncode=0, stdout="", stderr="")) as child:
            result = dev.run(["python", "-B", "-c", "pass"])
        self.assertEqual(result["exit_code"], 0)
        self.assertEqual(child.call_args.kwargs["env"]["PYTHONPATH"], "chosen-site-packages")
        self.assertEqual(child.call_args.kwargs["env"]["PYTHONNOUSERSITE"], "1")

    def test_run_preserves_explicit_child_environment(self):
        supplied = {"PYTHONPATH": "caller-site-packages", "PYTHONNOUSERSITE": "0"}
        with patch.object(dev.subprocess, "run", return_value=SimpleNamespace(returncode=0, stdout="", stderr="")) as child:
            result = dev.run(["python", "-B", "-c", "pass"], env=supplied)
        self.assertEqual(result["exit_code"], 0)
        self.assertIs(child.call_args.kwargs["env"], supplied)

    def test_json_receipt_preserves_unicode_on_ascii_stdout(self):
        with patch.object(dev, "preflight", return_value={"missing": ["Thiếu công cụ"]}), \
             contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(dev.main([]), 2)
        output.getvalue().encode("ascii")
        self.assertEqual(json.loads(output.getvalue())["missing"], ["Thiếu công cụ"])

    def test_incomplete_smoke_report_cannot_pass(self):
        with self.assertRaises(KeyError):
            dev.smoke_success({"exit_code": 0})

    def test_smoke_zero_without_steps_cannot_pass(self):
        self.assertFalse(dev.smoke_success({"schema": 1, "ok": True, "exit_code": 0, "cleanup_error": None, "steps": []}))

    def test_smoke_cleanup_error_cannot_pass(self):
        self.assertFalse(dev.smoke_success({"schema": 1, "ok": True, "exit_code": 0, "cleanup_error": "locked"}))

    def test_missing_runtime_sdk_and_model_are_one_actionable_list(self):
        inventory = {"root": str(dev.ROOT), "complete": True, "within_limit": True}
        with patch.object(dev, "discover_python", return_value=(None, [])), \
             patch.object(dev, "run", return_value=receipt("", 1)), \
             patch.object(dev, "quota", return_value=(inventory, True)), \
             patch.object(Path, "is_file", return_value=False), \
             patch.object(Path, "is_dir", return_value=False):
            result = dev.preflight(model="missing-model", gate="smoke")
        items = result["missing"]
        self.assertTrue(any(item["item"] == "Python 3.11+" for item in items))
        self.assertTrue(any(item["item"] == "SDK 8 + WindowsDesktop targeting pack" for item in items))
        self.assertTrue(any(item["item"] == "WPF runtime 8" for item in items))
        self.assertTrue(any(item["gate"] == "smoke" and item["item"] == list(dev.MODEL_FILES) for item in items))
        self.assertTrue(all(item["permission"] for item in items))

    def test_missing_packages_block_before_apply_without_pip_install(self):
        inventory = {"root": str(dev.ROOT), "complete": True, "within_limit": True}
        identity = {"path": "selected-python", "version": [3, 12, 14]}
        with patch.object(dev, "discover_python", return_value=(identity, [])), \
             patch.object(dev, "requirements", return_value=({"missing": ["ctranslate2==4.8.1"], "resolved": {}}, receipt())), \
             patch.object(dev, "run", return_value=receipt("", 1)) as command, \
             patch.object(dev, "quota", return_value=(inventory, True)), \
             patch.object(Path, "is_file", return_value=False), \
             patch.object(Path, "is_dir", return_value=False):
            result = dev.preflight()
        self.assertTrue(any(item["item"] == ["ctranslate2==4.8.1"] for item in result["missing"]))
        calls = [call.args[0] for call in command.call_args_list]
        self.assertIn(["selected-python", "-B", "-m", "pip", "check"], calls)
        self.assertFalse(any("install" in args for args in calls))


if __name__ == "__main__":
    unittest.main()
