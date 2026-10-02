"""Fail closed before any game copy or Patch operation."""
import csv
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "tests/tools"), str(ROOT / "tests/lib"), str(ROOT)]
from verify_completed_package import authenticate, authenticate_source, digest
from work_paths import work_temp_dir


class CompletedPackageAuthenticationTests(unittest.TestCase):
    def test_source_provenance_rejects_missing_or_changed_game(self):
        authenticate_source({"game\\data": "hash"}, {"game/data": {"sha256": "hash"}})
        for recorded, current in (({}, {}), ({"game/data": "hash"}, {}),
                                  ({"game/data": "hash"}, {"game/data": {"sha256": "other"}})):
            with self.assertRaises(ValueError):
                authenticate_source(recorded, current)

    def test_checksum_completion_and_count_are_required(self):
        with tempfile.TemporaryDirectory(dir=work_temp_dir("auth")) as directory:
            package = Path(directory)
            path = package / "translation.csv"
            path.write_text("key,source_text,translation\nk,Hello,Xin chào\n", encoding="utf-8-sig")
            completion = dict(ok=True, complete=True, pending=0, review_only=0, blocked=0, translated=1)
            self.assertEqual(len(authenticate(package, completion, digest(path))), 1)
            for invalid in (dict(complete=False), dict(pending=1), dict(review_only=1), dict(blocked=1), dict(translated=2)):
                with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                    authenticate(package, {**completion, **invalid}, digest(path))
            with self.assertRaises(ValueError):
                authenticate(package, completion, "0" * 64)
            path.write_text("key,source_text,translation\nk,Hello,\n", encoding="utf-8-sig")
            with self.assertRaises(ValueError):
                authenticate(package, completion, digest(path))
