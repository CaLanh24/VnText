from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from vntext.app_tasks import run_extract_task
from vntext_worker.task_runners import run_extract_worker


class RenPyExtractTaskTests(unittest.TestCase):
    def test_sdk_route_uses_native_units_without_source_parser_promotion(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "gamecopy"; (root / "game").mkdir(parents=True)
            (root / "game" / "script.rpy").write_text(
                'label start:\n    $ code_literal = "Only code"\n    "Native only"\n',
                encoding="utf-8",
            )
            out = Path(temp) / "out"; completed = []

            def generate(_sdk, workspace):
                template = workspace / "game" / "tl" / "vietnamese"
                template.mkdir(parents=True)
                (template / "script.rpy").write_text(
                    "# game/script.rpy:3\n"
                    "translate vietnamese native_only:\n\n"
                    '    # "Native only"\n'
                    '    ""\n',
                    encoding="utf-8",
                )

            with (
                patch("vntext.app_tasks._run_unity_preflight"),
                patch("vntext.renpy_toolchain.validate_sdk", return_value=SimpleNamespace(version="8.5.3")),
                patch("vntext.renpy_toolchain.generate_empty_vietnamese_template", side_effect=generate),
                patch("vntext.renpy_extract.extract_loose_source", side_effect=AssertionError("source parser called")),
            ):
                run_extract_task(
                    str(root),
                    str(out),
                    "safe",
                    "balanced",
                    True,
                    renpy_sdk_path="C:/sdk",
                    renpy_sdk_action="existing",
                    progress=lambda _x: None,
                    log=lambda _x: None,
                    complete=completed.append,
                )

            self.assertTrue(completed[-1]["complete"])
            self.assertEqual(completed[-1]["review_only"], 0)
            manifest = (out / "manifest.json").read_text(encoding="utf-8")
            self.assertIn('"native_id": "native_only"', manifest)
            self.assertNotIn("Only code", manifest)

    def test_no_sdk_extracts_without_guessing_native_ids(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "game"; (root / "game").mkdir(parents=True)
            (root / "game" / "script.rpy").write_text('label start:\n    "Hello"\n', encoding="utf-8")
            out = Path(temp) / "out"; completed = []
            logs = []
            with patch("vntext.app_tasks._run_unity_preflight"), patch("vntext.renpy_toolchain.managed_sdk", return_value=None), patch.dict("os.environ", {}, clear=True):
                run_extract_task(str(root), str(out), "safe", "balanced", True, progress=lambda _x: None, log=logs.append, complete=completed.append)
            self.assertTrue((out / "translation.csv").is_file())
            self.assertEqual(completed[-1]["review_only"], 1)
            self.assertFalse(completed[-1]["complete"])
            self.assertTrue(completed[-1]["renpy_sdk_missing"])
            self.assertIn("thiếu công cụ Ren'Py", completed[-1]["summary"])
            self.assertIn("chưa có công cụ Ren'Py", completed[-1]["error"])
            self.assertTrue(any("Kết quả chưa đầy đủ" in line for line in logs))

    def test_worker_forwards_explicit_sdk_choice(self):
        callbacks = (lambda _x: None, lambda _x: None, lambda _x: None)
        with patch("vntext_worker.task_runners._make_callbacks", return_value=callbacks), patch("vntext_worker.task_runners.run_extract_task") as task:
            run_extract_worker(
                "renpy-sdk",
                {"src": "C:/game", "out": "C:/package", "renpy_sdk_path": "C:/sdk", "renpy_sdk_action": "existing"},
                lambda: False,
            )
        self.assertEqual(task.call_args.kwargs["renpy_sdk_path"], "C:/sdk")
        self.assertEqual(task.call_args.kwargs["renpy_sdk_action"], "existing")
