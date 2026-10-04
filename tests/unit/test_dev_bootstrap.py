"""Public bootstrap guards: no downloads, truthful blockers, bounded owned output."""
import contextlib
import io
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from release import dev_bootstrap as dev


def receipt(stdout="", exit_code=0):
    return {"stdout": stdout, "stderr": "", "exit_code": exit_code}


class DevBootstrapTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
