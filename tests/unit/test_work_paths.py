"""Canonical work paths and explicit external-fixture boundaries."""

from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

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

import unittest
import work_paths as paths
from work_paths import (
    E2E_GAME_COPY,
    MANIFEST_PATH,
    WORK_ROOT,
    assert_artifact_under_work,
    assert_e2e_copy_separate_from_source,
    resolve_game_folder,
)

from work_paths import DEV_ROOT, EXTERNAL_GAME_ROOT, assert_write_destination, path_under_external_game
from work_paths import UNTRUSTED_EXTERNAL_NAMES, external_reject_path
from work_paths import dispose_e2e_game_copy, prepare_e2e_game_copy


class WorkPathContractTests(unittest.TestCase):
    def test_registry_writer_refuses_malformed_manifest_without_rewriting_it(self):
        with tempfile.TemporaryDirectory(prefix="vntext-work-paths-") as name:
            root = Path(name)
            work = root / "tests" / "golden" / "_work"
            work.mkdir(parents=True)
            manifest = work / "artifacts_manifest.json"
            for invalid_content in (b"{broken", b"[]", b'{"artifacts": null}'):
                with self.subTest(invalid_content=invalid_content):
                    manifest.write_bytes(invalid_content)
                    with patch.object(paths, "ROOT", root), patch.object(paths, "TESTS", root / "tests"), patch.object(
                        paths, "GOLDEN", root / "tests" / "golden"
                    ), patch.object(paths, "DEV_ROOT", root), patch.object(paths, "EXTERNAL_GAME_ROOT", root / "readonly"), patch.object(
                        paths, "WORK_ROOT", work
                    ), patch.object(paths, "E2E_GAME_COPY", work / "game_copy"), patch.object(
                        paths, "MANIFEST_PATH", manifest
                    ), patch.object(paths, "PROTECTED_PATH_PREFIXES", ()):
                        with self.assertRaises(ValueError):
                            paths.register_artifact(
                                artifact_id="test:preserve-malformed-registry",
                                path=work / "output.bin",
                                kind="test_output",
                                created_by="test_work_paths.py",
                                owner="test_work_paths.py",
                                purpose="proves malformed registry cannot be overwritten",
                                lifecycle="DISPOSABLE",
                            )
                    self.assertEqual(invalid_content, manifest.read_bytes())

    def test_canonical_e2e_copy_is_under_work(self):
        self.assertEqual(E2E_GAME_COPY, WORK_ROOT / "game-copy")
        self.assertEqual(WORK_ROOT, ROOT / "TEST_RUN")
        assert_artifact_under_work(E2E_GAME_COPY, "e2e")

    def test_external_fixture_and_checkout_source_are_not_artifact_workspaces(self):
        self.assertTrue(path_under_external_game(EXTERNAL_GAME_ROOT / "fixture"))
        for path in (EXTERNAL_GAME_ROOT / "fixture", DEV_ROOT / "source-output"):
            with self.subTest(path=path), self.assertRaises(RuntimeError):
                assert_artifact_under_work(path, "outside workspace")
        with self.assertRaises(RuntimeError):
            assert_write_destination(EXTERNAL_GAME_ROOT / "fixture", "external source")

    def test_no_vntext_work_directory_contract(self):
        self.assertFalse((ROOT / ".vntext_work").exists())
        self.assertEqual(MANIFEST_PATH.parent, WORK_ROOT)

    def test_external_fixture_is_not_the_e2e_copy(self):
        try:
            game = resolve_game_folder()
        except RuntimeError:
            self.skipTest("external Unity game fixture is not configured; set VNTEXT_GAME_FOLDER")
        self.assertNotEqual(game.resolve(), E2E_GAME_COPY.resolve())

    def test_prepare_dispose_preserves_source_and_blocks_active_process(self):
        live_manifest_before = MANIFEST_PATH.read_bytes() if MANIFEST_PATH.is_file() else None
        try:
            with tempfile.TemporaryDirectory(prefix="vntext-e2e-lifecycle-") as tmp:
                isolated_root = Path(tmp)
                work = isolated_root / "tests" / "golden" / "_work"
                game_copy = work / "game_copy"
                manifest = work / "artifacts_manifest.json"
                source = isolated_root / "source"
                data = source / "SampleGame_Data"
                data.mkdir(parents=True)
                work.mkdir(parents=True)
                manifest.write_text(
                    json.dumps(
                        {
                            "version": 2,
                            "schema_version": 2,
                            "updated_at": "2026-01-01T00:00:00Z",
                            "artifacts": [],
                            "archive": [],
                        }
                    ),
                    encoding="utf-8",
                )
                (source / "SampleGame.exe").write_bytes(b"source executable")
                (data / "data.unity3d").write_bytes(b"source data")

                def hashes(root: Path) -> dict[str, str]:
                    return {
                        str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
                        for path in sorted(root.rglob("*"))
                        if path.is_file()
                    }

                source_before = hashes(source)
                game = None
                with patch.object(paths, "GAME_FOLDER_PRIMARY", source), patch.object(
                    paths, "WORK_ROOT", work
                ), patch.object(paths, "E2E_GAME_COPY", game_copy), patch.object(
                    paths, "MANIFEST_PATH", manifest
                ), patch.object(paths, "DEV_ROOT", isolated_root), patch.object(
                    paths, "EXTERNAL_GAME_ROOT", isolated_root / "external"
                ), patch.dict(
                    os.environ,
                    {"VNTEXT_GAME_PROCESS_NAME": "__vntext_no_such_process__.exe"},
                ):
                    try:
                        game_copy.mkdir(parents=True)
                        unregistered_marker = game_copy / "unregistered.txt"
                        unregistered_marker.write_text("preserve unknown copy", encoding="utf-8")
                        with self.assertRaisesRegex(RuntimeError, "unregistered game copy"):
                            dispose_e2e_game_copy(reason="unregistered-copy guard regression")
                        self.assertTrue(unregistered_marker.is_file())
                        unregistered_marker.unlink()
                        game_copy.rmdir()

                        game = prepare_e2e_game_copy(label="work_paths lifecycle regression", mode="fresh")
                        self.assertEqual(source_before, hashes(game))
                        stale_file = game / "old-run-marker.txt"
                        stale_file.write_text("must disappear on next run", encoding="utf-8")
                        game = prepare_e2e_game_copy(label="fresh game copy regression", mode="reset")
                        self.assertEqual(source_before, hashes(game))
                        self.assertFalse(stale_file.exists())

                        active = [{"pid": 424242, "exe": str(game / "SampleGame.exe")}]
                        with patch.object(paths, "configured_game_processes", return_value=active), patch.object(
                            paths.subprocess, "call"
                        ) as process_call:
                            self.assertEqual(active, paths.processes_using(game))
                            paths.configured_game_processes.assert_called_with("SampleGame.exe")
                            with self.assertRaisesRegex(RuntimeError, "still in use"):
                                paths.kill_processes_using(game)
                            with self.assertRaises(RuntimeError):
                                dispose_e2e_game_copy(reason="blocked lifecycle regression")
                            process_call.assert_not_called()
                        self.assertTrue(game.exists())
                        paths.register_artifact(
                            artifact_id="game-copy-descendant",
                            path=game / "SampleGame_Data" / "data.unity3d",
                            kind="game_file",
                            created_by="work_paths lifecycle regression",
                            owner="work_paths lifecycle regression",
                            purpose="registered test-copy descendant",
                            lifecycle="PROTECTED",
                        )
                    finally:
                        with patch.object(paths, "configured_game_processes", return_value=[]):
                            if game is not None and game.exists():
                                self.assertTrue(
                                    dispose_e2e_game_copy(reason="work_paths lifecycle regression cleanup")
                                )

                self.assertEqual(source_before, hashes(source))
                self.assertFalse(game_copy.exists())
                final_entries = json.loads(manifest.read_text(encoding="utf-8"))["artifacts"]
                copy_entries = [
                    entry for entry in final_entries if entry["path"].startswith(str(game_copy))
                ]
                self.assertGreaterEqual(len(copy_entries), 2)
                self.assertTrue(
                    all(entry["lifecycle"] == "MISSING" for entry in copy_entries)
                )
        finally:
            live_manifest_after = MANIFEST_PATH.read_bytes() if MANIFEST_PATH.is_file() else None
            self.assertEqual(live_manifest_before, live_manifest_after)


if __name__ == "__main__":
    unittest.main()
