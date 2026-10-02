"""Regression tests for the scoped Release-package mirror."""

from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


def _tests_lib_on_path() -> None:
    cur = Path(__file__).resolve().parent
    while cur.name != "tests" and cur.parent != cur:
        cur = cur.parent
    lib = cur / "lib"
    if str(lib) not in sys.path:
        sys.path.insert(0, str(lib))


_tests_lib_on_path()
from bootstrap import bootstrap

TESTS, ROOT, LIB = bootstrap(__file__)

import contextlib
from unittest.mock import patch

import work_paths as paths


TOOLS = ROOT / "tests" / "tools"
MIRROR_PATH = TOOLS / "mirror_release_package.py"
_spec = importlib.util.spec_from_file_location("mirror_release_package", MIRROR_PATH)
assert _spec and _spec.loader
mirror_tool = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mirror_tool)


class MirrorReleasePackageTests(unittest.TestCase):
    @contextlib.contextmanager
    def isolated_workspace(self):
        with tempfile.TemporaryDirectory(prefix="vntext-mirror-") as name:
            root = Path(name)
            work = root / "tests" / "golden" / "_work"
            work.mkdir(parents=True)
            manifest = work / "artifacts_manifest.json"
            values = {
                "ROOT": root,
                "TESTS": root / "tests",
                "GOLDEN": root / "tests" / "golden",
                "WORK_ROOT": work,
                "E2E_GAME_COPY": work / "game_copy",
                "MANIFEST_PATH": manifest,
                "DEV_ROOT": root.resolve(),
                "EXTERNAL_GAME_ROOT": root / "readonly",
                "PROTECTED_PATH_PREFIXES": (),
            }
            with contextlib.ExitStack() as stack:
                for key, value in values.items():
                    stack.enter_context(patch.object(paths, key, value))
                yield root, work, manifest

    def test_mirror_registers_disposable_destination_with_provenance(self):
        with self.isolated_workspace() as (root, work, manifest):
            source = root / "release"
            source.mkdir()
            (source / "translation.csv").write_text("key,translation\n1,\n", encoding="utf-8")
            destination = work / "release-mirror"

            copied = mirror_tool.mirror(
                source,
                destination,
                scope_id="mirror-scope",
                run_id="mirror-run",
            )

            self.assertEqual(["translation.csv"], copied)
            self.assertTrue((destination / "translation.csv").is_file())
            entry = json.loads(manifest.read_text(encoding="utf-8"))["artifacts"][0]
            self.assertEqual(str(destination.resolve()), entry["path"])
            self.assertEqual("DISPOSABLE", entry["lifecycle"])
            self.assertEqual("mirror-scope", entry["scope_id"])
            self.assertEqual("mirror-run", entry["run_id"])
            self.assertEqual("mirror_release_package.py", entry["owner"])
            self.assertTrue(entry["provenance"]["registered_by"])

    def test_mirror_rejects_destination_outside_work(self):
        with self.isolated_workspace() as (root, _work, _manifest):
            source = root / "release"
            source.mkdir()
            with self.assertRaises(RuntimeError):
                mirror_tool.mirror(source, root / "outside")


if __name__ == "__main__":
    unittest.main()
