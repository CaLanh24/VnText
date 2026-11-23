"""The bug report is built in its own process, so it works while the worker is busy and when the last task failed."""
import json
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

from tests.lib.work_paths import work_temp_dir

WORK = work_temp_dir("bug-report-cli")
ROOT = Path(__file__).resolve().parents[2]


def run_cli(params: dict, base: Path) -> tuple[int, dict]:
    parameter_file = base / "params.json"
    parameter_file.write_text(json.dumps(params), encoding="utf-8")
    done = subprocess.run([sys.executable, "-m", "vntext.bug_report_cli", str(parameter_file)], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", timeout=120)
    return done.returncode, json.loads(done.stdout.strip().splitlines()[-1])


class BugReportCliTests(unittest.TestCase):
    def test_builds_the_report_and_its_preview_without_the_worker(self):
        with tempfile.TemporaryDirectory(dir=WORK) as temp:
            base = Path(temp)
            game = base / "Secret Game Folder"
            (game / "game").mkdir(parents=True)
            (game / "game" / "script.rpy").write_text('label start:\n    "SECRET LINE"\n', encoding="utf-8")
            out = base / "package" / "bug-reports"
            code, result = run_cli({"src": str(game), "out": str(out), "log_lines": [f"Lỗi ở {game}"], "app_version": "test"}, base)
            self.assertEqual(0, code, result)
            self.assertTrue(result["ok"])
            self.assertIn("CHƯA được gửi đi", result["summary"])
            reports = list(out.glob("vntext-bug-report-*.zip"))
            self.assertEqual(1, len(reports))
            with zipfile.ZipFile(reports[0]) as archive:
                blob = "\n".join(archive.read(name).decode("utf-8", "replace") for name in archive.namelist())
            for secret in ("Secret Game Folder", "SECRET LINE", temp):
                self.assertNotIn(secret.casefold(), blob.casefold())

    def test_reports_a_clear_error_instead_of_crashing(self):
        with tempfile.TemporaryDirectory(dir=WORK) as temp:
            code, result = run_cli({"src": str(Path(temp) / "missing"), "out": str(Path(temp) / "out")}, Path(temp))
            self.assertEqual(1, code)
            self.assertFalse(result["ok"])
            self.assertIn("chọn game", result["error"])
            code, result = run_cli({}, Path(temp))
            self.assertFalse(result["ok"])


if __name__ == "__main__":
    unittest.main()
