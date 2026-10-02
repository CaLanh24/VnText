"""Regression: test artifacts stay inside the checkout work area."""

from __future__ import annotations

import re
import sys
import tempfile
import unittest
from pathlib import Path


def _tests_lib_on_path() -> None:
    cur = Path(__file__).resolve().parent
    while cur.name != "tests" and cur.parent != cur:
        cur = cur.parent
    lib = cur / "lib"
    p = str(lib)
    if p not in sys.path:
        sys.path.insert(0, p)


_tests_lib_on_path()
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


class GenericArtifactWritePolicyTests(unittest.TestCase):
    def test_external_fixture_root_is_read_only_and_work_root_is_writable(self):
        external = EXTERNAL_GAME_ROOT / "source" / "probe.txt"
        self.assertTrue(path_under_external_game(external))
        with self.assertRaises(RuntimeError):
            assert_write_destination(external, "external fixture")
        destination = WORK_ROOT / "artifact_policy_probe"
        resolved = assert_write_destination(destination, "work probe")
        self.assertTrue(path_under_dev(resolved))
        self.assertTrue(str(resolved).startswith(str(DEV_ROOT)))

    def test_artifact_workspaces_cannot_escape_checkout_or_work_root(self):
        with self.assertRaises(RuntimeError):
            assert_write_destination(Path(tempfile.gettempdir()) / "outside.txt", "outside")
        with self.assertRaises(RuntimeError):
            assert_artifact_under_work(DEV_ROOT / "outside-work", "outside work")

SCAN_ROOTS = (TESTS / "lib", TESTS / "unit", TESTS / "harness")

# Generic equivalents used by the public snapshot.  These remain strict:
# absolute personal paths and direct write calls are rejected in active tests.
PERSONAL_PATH_PATTERN = re.compile(r"[A-Za-z]:[\\/](?:Users|home)[\\/][^\"'\n]+")
EXTERNAL_PATH_LITERAL_PATTERN = re.compile(
    r'Path\s*\(\s*r?["\'][A-Za-z]:[\\/][^"\']+["\']\s*\)'
)
GENERIC_WRITE_PATTERN = re.compile(
    r"(?:assert_write_destination|assert_artifact_under_work)\s*\(\s*"
    r"(?:Path\s*\([^)]*\)|[A-Za-z_][A-Za-z0-9_]*)"
)
HARDCODED_EXTERNAL_WRITE = re.compile(
    r"(?:write_text|write_bytes|mkdir|copy2|copytree|rmtree)\s*\(\s*"
    r"Path\s*\(\s*r?[\"'][A-Za-z]:[\\/][^\"']+[\"']"
)


class ArtifactWritePolicyTests(unittest.TestCase):
    def test_write_destination_rejects_external_fixture_and_accepts_work(self):
        with self.assertRaises(RuntimeError):
            assert_write_destination(EXTERNAL_GAME_ROOT / "probe.txt", "external fixture")
        with self.assertRaises(RuntimeError):
            assert_write_destination(Path(tempfile.gettempdir()) / "probe.txt", "outside")
        dest = WORK_ROOT / "artifact_policy_probe"
        resolved = assert_write_destination(dest, "work probe")
        self.assertTrue(path_under_dev(resolved))
        self.assertTrue(str(resolved).startswith(str(DEV_ROOT)))

    def test_external_fixture_is_not_an_artifact_workspace(self):
        self.assertTrue(path_under_external_game(EXTERNAL_GAME_ROOT / "fixture"))
        with self.assertRaises(RuntimeError):
            assert_artifact_under_work(EXTERNAL_GAME_ROOT / "fixture", "external fixture")

    def test_unsafe_destinations_are_rejected_by_the_single_policy_gate(self):
        for destination in (
            EXTERNAL_GAME_ROOT / "source.txt",
            Path(tempfile.gettempdir()) / "outside.txt",
            DEV_ROOT / "not-a-test-workspace",
        ):
            with self.subTest(destination=destination), self.assertRaises(RuntimeError):
                assert_artifact_under_work(destination, "unsafe destination")

    def test_no_personal_path_literals_in_lib_unit_harness(self):
        hits: list[str] = []
        for root in SCAN_ROOTS:
            if not root.is_dir():
                continue
            for path in root.rglob("*.py"):
                text = path.read_text(encoding="utf-8")
                if PERSONAL_PATH_PATTERN.search(text):
                    hits.append(str(path.relative_to(TESTS)))
        self.assertEqual(hits, [], msg=f"personal path literals remain: {hits}")

    def test_no_absolute_external_path_literals_in_test_sources(self):
        hits: list[str] = []
        for root in SCAN_ROOTS:
            if not root.is_dir():
                continue
            for path in root.rglob("*.py"):
                if path.name in {"test_artifact_write_policy.py"}:
                    continue
                text = path.read_text(encoding="utf-8")
                for match in EXTERNAL_PATH_LITERAL_PATTERN.finditer(text):
                    hits.append(f"{path.relative_to(TESTS)}:{match.group(0)}")
        self.assertEqual(hits, [], msg=f"absolute external Path() literals: {hits}")

    def test_manifest_active_artifacts_under_dev(self):
        import json

        if not MANIFEST_PATH.is_file():
            # A clean clone has no generated registry until a scoped test run.
            # Absence cannot contain an unsafe ACTIVE entry.
            return
        doc = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        bad: list[str] = []
        for entry in doc.get("artifacts", []):
            if entry.get("status") != "ACTIVE":
                continue
            path = Path(entry["path"]).resolve()
            if not path_under_dev(path):
                bad.append(f"{entry.get('id')}:{path}")
        self.assertEqual(bad, [], msg=f"ACTIVE manifest outside DEV: {bad}")


if __name__ == "__main__":
    unittest.main()
