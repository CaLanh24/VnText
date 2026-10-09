from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from vntext.renpy_adapter import detect_engine


class RenPyEngineDetectionTests(unittest.TestCase):
    def _folder(self) -> tempfile.TemporaryDirectory:
        return tempfile.TemporaryDirectory()

    def test_loose_source_is_supported(self):
        with self._folder() as temp:
            root = Path(temp)
            (root / "game").mkdir()
            (root / "game" / "script.rpy").write_text("label start:\n", encoding="utf-8")
            result = detect_engine(root)
            self.assertEqual((result.engine, result.status), ("RENPY_LOOSE_SOURCE", "SUPPORTED"))

    def test_compiled_only_is_not_patchable(self):
        with self._folder() as temp:
            root = Path(temp)
            (root / "game").mkdir()
            (root / "game" / "script.rpyc").write_bytes(b"x")
            result = detect_engine(root)
            self.assertEqual((result.engine, result.status), ("RENPY_COMPILED_ONLY", "EXTRACT_ONLY"))
            from vntext.extract_pipeline import extract_project
            with self.assertRaisesRegex(ValueError,"Ren'Py"):
                extract_project(str(root))

    def test_mixed_evidence_requires_review(self):
        with self._folder() as temp:
            root = Path(temp)
            (root / "game").mkdir()
            (root / "game" / "script.rpy").write_text("label start:\n", encoding="utf-8")
            (root / "Example_Data").mkdir()
            result = detect_engine(root)
            self.assertEqual((result.engine, result.status), ("MIXED", "REVIEW_REQUIRED"))
            from vntext.extract_pipeline import extract_project
            with self.assertRaisesRegex(ValueError,"Ren'Py"):
                extract_project(str(root))

    def test_unknown_is_not_guessed(self):
        with self._folder() as temp:
            result = detect_engine(Path(temp))
            self.assertEqual((result.engine, result.status), ("UNKNOWN", "REVIEW_REQUIRED"))
