"""The Ren'Py font-size slider must reach the patch builder: the worker used to drop `font_scale` (found by running a real game)."""
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import vntext_worker.task_runners as runners


class WorkerFontScaleTests(unittest.TestCase):
    def run_worker(self, params):
        seen = {}
        with tempfile.TemporaryDirectory() as tmp:
            package = Path(tmp) / "package"
            package.mkdir()
            csv, manifest = package / "translation.csv", package / "manifest.json"
            csv.write_text("x", encoding="utf-8")
            manifest.write_text("{}", encoding="utf-8")
            base = {"src": tmp, "out": str(package), "csv_path": str(csv), "manifest_path": str(manifest)}
            with mock.patch.object(runners, "has_translations", return_value=True), \
                 mock.patch("vntext.patch_gate.audit_patch_package", return_value={"eligible": 1, "blocked": 0}), \
                 mock.patch("vntext.patch_gate.format_preflight_log", return_value="ok"), \
                 mock.patch("vntext_worker.task_runners.run_patch_task", side_effect=lambda *a, **k: seen.update(k), create=True), \
                 mock.patch("vntext.app_tasks.run_patch_task", side_effect=lambda *a, **k: seen.update(k)):
                runners.run_patch_worker("t", {**base, **params}, lambda: False)
        return seen

    def test_font_scale_is_forwarded(self):
        self.assertEqual("0.70", self.run_worker({"font_scale": "0.70"}).get("font_scale"))

    def test_missing_font_scale_means_unchanged(self):
        self.assertEqual("", self.run_worker({}).get("font_scale"))


if __name__ == "__main__":
    unittest.main()
