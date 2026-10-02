"""Contract test for the isolated Release regression runner."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RUNNER = ROOT / "release" / "run_regression.ps1"
WORK = ROOT / "tests" / "golden" / "_work"

sys.path.insert(0, str(ROOT / "tests" / "lib"))
sys.path.insert(0, str(ROOT / "tests" / "tools"))
from cleanup_work_artifacts import cleanup_after_test  # noqa: E402
from work_paths import ambient_scope, register_artifact  # noqa: E402


def _nested_runner_env() -> dict[str, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env.pop("VNTEXT_PARENT_STDOUT_LOG", None)
    env.pop("VNTEXT_PARENT_STDERR_LOG", None)
    return env


class ReleaseRegressionRunnerTests(unittest.TestCase):
    def _register_harness(self, harness: Path, *, name: str) -> None:
        ambient = ambient_scope()
        register_artifact(
            artifact_id=f"release-runner-harness:{name}:{harness.name}",
            path=harness,
            kind="test_workspace",
            created_by="test_release_regression_runner.py",
            owner="test_release_regression_runner.py",
            purpose=f"disposable subprocess harness for {name}",
            lifecycle="DISPOSABLE",
            scope_id=ambient["scope_id"],
            run_id=ambient["run_id"],
            scope_root=ambient["scope_root"],
        )

    def test_runner_executes_pattern_and_writes_complete_summary(self):
        self.assertTrue(RUNNER.is_file(), RUNNER)
        powershell = shutil.which("powershell") or shutil.which("pwsh")
        self.assertIsNotNone(powershell, "PowerShell is required by the Release gate")

        WORK.mkdir(parents=True, exist_ok=True)
        harness = Path(tempfile.mkdtemp(prefix="release_runner_contract_", dir=WORK))
        self._register_harness(harness, name="runner-contract")
        runner_path = harness / "release" / "run_regression.ps1"
        runner_path.parent.mkdir(parents=True)
        shutil.copy2(RUNNER, runner_path)
        for relative in (
            "tests/tools/cleanup_work_artifacts.py",
            "tests/lib/work_paths.py",
            "tests/lib/bootstrap.py",
        ):
            target = harness / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / relative, target)
        unit_dir = harness / "tests" / "unit"
        unit_dir.mkdir(parents=True)
        (unit_dir / "test_fast.py").write_text(
            "import unittest\n\n"
            "class FastTests(unittest.TestCase):\n"
            "    def test_runner_executes_pattern(self):\n"
            "        self.assertTrue(True)\n",
            encoding="utf-8",
        )
        scope_root = harness / "tests" / "golden" / "_work"
        log_root = scope_root / "release_runner_contract"
        log_root.mkdir(parents=True)
        outcome = "FAIL"
        try:
            pattern_file = log_root / "patterns.txt"
            pattern_file.write_text("test_fast.py\n", encoding="utf-8")
            command = [
                powershell,
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(runner_path),
                "-PythonPath",
                sys.executable,
                "-WorkingDirectory",
                str(harness),
                "-LogRoot",
                str(log_root),
                "-SourceSha",
                "contract-test",
                "-TimeoutSeconds",
                "60",
                "-CleanupTimeoutSeconds",
                "45",
                "-PatternFile",
                str(pattern_file),
            ]
            result = subprocess.run(
                command,
                cwd=harness,
                capture_output=True,
                text=True,
                timeout=90,
                env=_nested_runner_env(),
            )
            failure_evidence = ""
            if result.returncode != 0:
                failed_summaries = list(log_root.rglob("REGRESSION_COMPLETE.json"))
                for failed_summary in failed_summaries:
                    failure_evidence += "\n" + failed_summary.read_text(encoding="utf-8")
                    summary_payload = json.loads(failed_summary.read_text(encoding="utf-8"))
                    cleanup_path = Path(str(summary_payload.get("cleanup", {}).get("report") or ""))
                    if cleanup_path.is_file():
                        cleanup_payload = json.loads(cleanup_path.read_text(encoding="utf-8"))
                        failure_evidence += "\n" + json.dumps(
                            {
                                "status": cleanup_payload.get("status"),
                                "unknown": cleanup_payload.get("unknown"),
                                "unexpected_missing": cleanup_payload.get("unexpected_missing"),
                                "modified": cleanup_payload.get("modified"),
                                "errors": cleanup_payload.get("errors"),
                                "metadata_issues": cleanup_payload.get("metadata_issues"),
                                "locked": cleanup_payload.get("locked"),
                                "inventory_complete": cleanup_payload.get("inventory_complete"),
                            },
                            indent=2,
                        )
            self.assertEqual(0, result.returncode, result.stdout + result.stderr + failure_evidence)

            summaries = list(log_root.rglob("REGRESSION_COMPLETE.json"))
            self.assertEqual(1, len(summaries), result.stdout + result.stderr)
            summary = json.loads(summaries[0].read_text(encoding="utf-8"))
            self.assertEqual("PASS", summary["status"])
            self.assertEqual(0, summary["exit_code"])
            self.assertEqual(1, len(summary["results"]))
            self.assertEqual("PASS", summary["results"][0]["status"])
            self.assertEqual(0, summary["results"][0]["exit_code"])
            self.assertTrue(Path(summary["results"][0]["log"]).is_file())
            self.assertTrue(summary["scope_id"].startswith("release-regression-"))
            self.assertTrue(summary["run_id"].startswith("release-run-"))
            self.assertEqual(str(scope_root.resolve()), summary["scope_root"])
            self.assertEqual(45, summary["cleanup_timeout_seconds"])
            self.assertEqual("PASS", summary["cleanup"]["status"])
            self.assertEqual(0, summary["cleanup"]["exit_code"])
            self.assertTrue(Path(summary["cleanup"]["report"]).is_file())
            cleanup = json.loads(
                Path(summary["cleanup"]["report"]).read_text(encoding="utf-8")
            )
            self.assertEqual("PASS", cleanup["status"])
            self.assertEqual("PASS", cleanup["terminal_status"])
            self.assertTrue(cleanup["ok"])
            self.assertTrue(cleanup["inventory_complete"])
            self.assertEqual([], cleanup["unknown"])
            self.assertEqual([], cleanup["modified"])
            self.assertEqual(45.0, cleanup["inventory"]["budget"]["timeout_seconds"])
            outcome = "PASS"
        finally:
            cleanup = cleanup_after_test(
                [harness],
                reason="release-runner-contract-finally",
                outcome=outcome,
            )
            self.assertTrue(cleanup["ok"], cleanup)

    def test_cleanup_timeout_writes_terminal_reports_and_kills_process_tree(self):
        powershell = shutil.which("powershell") or shutil.which("pwsh")
        self.assertIsNotNone(powershell, "PowerShell is required by the Release gate")

        harness = Path(tempfile.mkdtemp(prefix="release_cleanup_timeout_", dir=WORK))
        try:
            self._register_harness(harness, name="cleanup-timeout")
            runner_path = harness / "release" / "run_regression.ps1"
            runner_path.parent.mkdir(parents=True)
            shutil.copy2(RUNNER, runner_path)

            cleanup_path = harness / "tests" / "tools" / "cleanup_work_artifacts.py"
            cleanup_path.parent.mkdir(parents=True)
            fake_cleanup = "\n".join(
                [
                    "from pathlib import Path",
                    "import json",
                    "import subprocess",
                    "import sys",
                    "import time",
                    "",
                    "args = sys.argv[1:]",
                    "if '--register-path' in args:",
                    "    raise SystemExit(0)",
                    "",
                    "def value(flag):",
                    "    return args[args.index(flag) + 1]",
                    "",
                    "if '--snapshot' in args:",
                    "    target = Path(value('--output'))",
                    "    target.parent.mkdir(parents=True, exist_ok=True)",
                    "    target.write_text(json.dumps({",
                    "        'root': value('--scope-root'),",
                    "        'items': {},",
                    "        'errors': [],",
                    "        'complete': True,",
                    "        'inventory': {'complete': True, 'status': 'PASS'},",
                    "    }), encoding='utf-8')",
                    "    raise SystemExit(0)",
                    "",
                    "scope_root = Path(value('--scope-root'))",
                    "scope_root.mkdir(parents=True, exist_ok=True)",
                    "child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)'], cwd=scope_root.anchor)",
                    "(scope_root / 'cleanup-child.pid').write_text(str(child.pid), encoding='utf-8')",
                    "time.sleep(30)",
                ]
            ) + "\n"
            cleanup_path.write_text(fake_cleanup, encoding="utf-8")

            unit_path = harness / "tests" / "unit" / "test_fast.py"
            unit_path.parent.mkdir(parents=True)
            unit_path.write_text(
                "import unittest\n\n"
                "class FastTests(unittest.TestCase):\n"
                "    def test_fast(self):\n"
                "        self.assertTrue(True)\n",
                encoding="utf-8",
            )
            scope_root = harness / "tests" / "golden" / "_work"
            log_root = scope_root / "release_gate"
            log_root.mkdir(parents=True)
            pattern_file = log_root / "patterns.txt"
            pattern_file.write_text("test_fast.py\n", encoding="utf-8")

            command = [
                powershell,
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(runner_path),
                "-PythonPath",
                sys.executable,
                "-WorkingDirectory",
                str(harness),
                "-LogRoot",
                str(log_root),
                "-SourceSha",
                "cleanup-timeout-test",
                "-TimeoutSeconds",
                "30",
                "-CleanupTimeoutSeconds",
                "1",
                "-PatternFile",
                str(pattern_file),
            ]
            result = subprocess.run(
                command,
                cwd=harness,
                capture_output=True,
                text=True,
                timeout=30,
                env=_nested_runner_env(),
            )
            self.assertNotEqual(0, result.returncode, result.stdout + result.stderr)

            summaries = list(log_root.rglob("REGRESSION_COMPLETE.json"))
            self.assertEqual(1, len(summaries), result.stdout + result.stderr)
            summary = json.loads(summaries[0].read_text(encoding="utf-8"))
            self.assertEqual("CLEANUP_FAILED", summary["status"])
            self.assertEqual("TIMEOUT", summary["cleanup"]["status"])
            self.assertEqual(124, summary["cleanup"]["exit_code"])
            cleanup_report = Path(summary["cleanup"]["report"])
            self.assertTrue(cleanup_report.is_file())
            cleanup = json.loads(cleanup_report.read_text(encoding="utf-8"))
            self.assertEqual("TIMEOUT", cleanup["terminal_status"])
            self.assertFalse(cleanup["ok"])
            self.assertFalse(cleanup["inventory_complete"])
            self.assertEqual([], cleanup["deleted"])

            pid_file = scope_root / "cleanup-child.pid"
            self.assertTrue(pid_file.is_file())
            child_pid = int(pid_file.read_text(encoding="utf-8"))
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                try:
                    os.kill(child_pid, 0)
                except OSError:
                    break
                time.sleep(0.1)
            else:
                self.fail(f"cleanup descendant process still exists: {child_pid}")
        finally:
            for _ in range(20):
                try:
                    shutil.rmtree(harness)
                    break
                except FileNotFoundError:
                    break
                except OSError:
                    # Windows can release a killed process's cwd handle just
                    # after the process has exited; retry before leaving a
                    # registered disposable artifact behind.
                    time.sleep(0.25)
            cleanup = cleanup_after_test(
                [harness],
                reason="release-runner-timeout-finally",
                outcome="PASS",
            )
            self.assertTrue(cleanup["ok"], cleanup)

    def test_cleanup_start_error_still_writes_terminal_reports(self):
        powershell = shutil.which("powershell") or shutil.which("pwsh")
        self.assertIsNotNone(powershell, "PowerShell is required by the Release gate")

        harness = Path(tempfile.mkdtemp(prefix="release_cleanup_start_error_", dir=WORK))
        try:
            self._register_harness(harness, name="cleanup-start-error")
            runner_path = harness / "release" / "run_regression.ps1"
            runner_path.parent.mkdir(parents=True)
            shutil.copy2(RUNNER, runner_path)
            scope_root = harness / "tests" / "golden" / "_work"
            log_root = scope_root / "release_gate"
            log_root.mkdir(parents=True)
            pattern_file = log_root / "patterns.txt"
            pattern_file.write_text("test_missing.py\n", encoding="utf-8")

            command = [
                powershell,
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(runner_path),
                "-PythonPath",
                sys.executable,
                "-WorkingDirectory",
                str(harness),
                "-LogRoot",
                str(log_root),
                "-SourceSha",
                "cleanup-start-error-test",
                "-TimeoutSeconds",
                "30",
                "-CleanupTimeoutSeconds",
                "1",
                "-PatternFile",
                str(pattern_file),
            ]
            result = subprocess.run(
                command,
                cwd=harness,
                capture_output=True,
                text=True,
                timeout=30,
                env=_nested_runner_env(),
            )
            self.assertNotEqual(0, result.returncode, result.stdout + result.stderr)

            summaries = list(log_root.rglob("REGRESSION_COMPLETE.json"))
            self.assertEqual(1, len(summaries), result.stdout + result.stderr)
            summary = json.loads(summaries[0].read_text(encoding="utf-8"))
            self.assertEqual("START_ERROR", summary["cleanup"]["status"])
            cleanup_report = Path(summary["cleanup"]["report"])
            self.assertTrue(cleanup_report.is_file())
            cleanup = json.loads(cleanup_report.read_text(encoding="utf-8"))
            self.assertEqual("START_ERROR", cleanup["terminal_status"])
            self.assertFalse(cleanup["ok"])
            self.assertEqual([], cleanup["deleted"])
        finally:
            cleanup = cleanup_after_test(
                [harness],
                reason="release-runner-start-error-finally",
                outcome="PASS",
            )
            self.assertTrue(cleanup["ok"], cleanup)


if __name__ == "__main__":
    unittest.main()
