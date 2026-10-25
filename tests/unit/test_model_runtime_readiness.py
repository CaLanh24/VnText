"""Readiness checks must include the runtime used to translate a package."""

from __future__ import annotations

import builtins
import tempfile
from types import SimpleNamespace
import unittest
from pathlib import Path
from unittest.mock import patch

from vntext.mt_ct2_model import model_status


class ModelRuntimeReadinessTests(unittest.TestCase):
    def test_model_file_does_not_claim_ready_when_ctranslate2_import_fails(self):
        with tempfile.TemporaryDirectory(prefix="vntext-model-runtime-") as name:
            model_dir = Path(name)
            (model_dir / "model.bin").write_bytes(b"model marker")
            real_import = builtins.__import__

            def import_without_ct2(module, *args, **kwargs):
                if module == "ctranslate2":
                    raise ModuleNotFoundError("No module named 'ctranslate2'")
                return real_import(module, *args, **kwargs)

            with patch("builtins.__import__", side_effect=import_without_ct2):
                status = model_status(model_dir)

        self.assertFalse(status["ready"], status)
        self.assertFalse(status["runtime_ready"], status)
        self.assertIn("ctranslate2", status["message"].lower())
        self.assertIn("khóa", status["message"].lower())

    def test_status_reports_each_bounded_readiness_boundary(self):
        with tempfile.TemporaryDirectory(prefix="vntext-model-runtime-") as name:
            model_dir = Path(name)
            (model_dir / "model.bin").write_bytes(b"model marker")
            real_import = builtins.__import__
            events: list[str] = []

            def import_with_fake_ct2(module, *args, **kwargs):
                if module == "ctranslate2":
                    return SimpleNamespace(__version__="test")
                return real_import(module, *args, **kwargs)

            with patch("builtins.__import__", side_effect=import_with_fake_ct2):
                status = model_status(model_dir, progress_callback=events.append)

        self.assertTrue(status["ready"], status)
        self.assertEqual(6, len(events))
        self.assertIn("resolve_model_dir: start", events[0])
        self.assertIn("resolve_model_dir: done", events[1])
        self.assertIn("model.bin check: start", events[2])
        self.assertIn("model.bin check: done", events[3])
        self.assertIn("import ctranslate2: start", events[4])
        self.assertIn("import ctranslate2: done", events[5])


if __name__ == "__main__":
    unittest.main()
