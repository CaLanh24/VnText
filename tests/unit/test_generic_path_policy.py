"""Generic fail-closed tests for repository and external-fixture boundaries."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

cur = Path(__file__).resolve().parent
while cur.name != "tests" and cur.parent != cur:
    cur = cur.parent
sys.path.insert(0, str(cur / "lib"))
from bootstrap import bootstrap

TESTS, ROOT, LIB = bootstrap(__file__)

from work_paths import (
    DEV_ROOT,
    EXTERNAL_GAME_ROOT,
    MANIFEST_PATH,
    WORK_ROOT,
    assert_artifact_under_work,
    assert_write_destination,
    path_under_dev,
    path_under_external_game,
)


class GenericPathPolicyTests(unittest.TestCase):
    def test_external_fixture_and_system_temp_are_not_write_targets(self):
        for path in (
            EXTERNAL_GAME_ROOT / "source" / "asset",
            Path(tempfile.gettempdir()) / "outside" / "artifact",
        ):
            with self.subTest(path=path), self.assertRaises(RuntimeError):
                assert_write_destination(path, "external write")

    def test_registered_artifact_must_be_inside_checkout_work_root(self):
        valid = WORK_ROOT / "generic-policy-probe"
        self.assertTrue(path_under_dev(assert_artifact_under_work(valid, "valid artifact")))
        for path in (DEV_ROOT / "source-output", EXTERNAL_GAME_ROOT / "fixture"):
            with self.subTest(path=path), self.assertRaises(RuntimeError):
                assert_artifact_under_work(path, "outside artifact")

    def test_active_manifest_paths_are_inside_checkout(self):
        if not MANIFEST_PATH.is_file():
            self.skipTest("no local artifact manifest exists before a workspace run")
        document = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        outside = []
        for entry in document.get("artifacts", []):
            if str(entry.get("status") or "").upper() != "ACTIVE":
                continue
            path = Path(str(entry.get("path") or "")).resolve()
            if not path_under_dev(path):
                outside.append(f"{entry.get('id')}:{path}")
        self.assertEqual(outside, [])


if __name__ == "__main__":
    unittest.main()
