"""Focused lifecycle tests for the canonical TEST_RUN cleanup."""

from __future__ import annotations

import contextlib
import io
import json
import shutil
import os
import stat
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch


def _tests_lib_on_path() -> None:
    cur = Path(__file__).resolve().parent
    while cur.name != "tests" and cur.parent != cur:
        cur = cur.parent
    lib = cur / "lib"
    tools = cur / "tools"
    if str(lib) not in sys.path:
        sys.path.insert(0, str(lib))
    if str(tools) not in sys.path:
        sys.path.insert(0, str(tools))


_tests_lib_on_path()
from bootstrap import bootstrap

TESTS, ROOT, LIB = bootstrap(__file__)

import cleanup_work_artifacts as cleanup  # noqa: E402
import work_paths as paths  # noqa: E402
import run_with_cleanup as runner  # noqa: E402
PROJECT_INVENTORY_ROOT = cleanup._project_inventory_root

RUNNER = ROOT / "tests" / "tools" / "run_with_cleanup.py"


class CleanupLifecycleTests(unittest.TestCase):
    @contextlib.contextmanager
    def isolated_owner_pending(self):
        """Keep retained production evidence from changing synthetic lifecycle fixtures."""
        marker = "VNTEXT_OWNER_TEST_PENDING"
        previous = os.environ.pop(marker, None)
        try:
            yield
        finally:
            if previous is not None:
                os.environ[marker] = previous

    @contextlib.contextmanager
    def isolated_workspace(self):
        with self.isolated_owner_pending(), tempfile.TemporaryDirectory(prefix="vntext-cleanup-") as name:
            root = Path(name)
            tests_root = root / "tests"
            golden = tests_root / "golden"
            work = root / "TEST_RUN"
            work.mkdir(parents=True)
            game_copy = work / "game-copy"
            game_copy.mkdir()
            manifest = work / "artifacts_manifest.json"

            with contextlib.ExitStack() as stack:
                wp_values = {
                    "ROOT": root,
                    "TESTS": tests_root,
                    "GOLDEN": golden,
                    "WORK_ROOT": work,
                    "E2E_GAME_COPY": game_copy,
                    "MANIFEST_PATH": manifest,
                    "DEV_ROOT": root.resolve(),
                    "EXTERNAL_GAME_ROOT": root / "readonly",
                    "PROTECTED_PATH_PREFIXES": (),
                }
                cleanup_values = {
                    "ROOT": root,
                    "TESTS": tests_root,
                    "WORK_ROOT": work,
                    "MANIFEST_PATH": manifest,
                    "E2E_GAME_COPY": game_copy,
                    "EVIDENCE": work / "evidence",
                    "CLEANUP_MANIFEST": work / "cleanup_manifest.json",
                    "SIZE_REPORT": work / "size_report.json",
                    "KEEP_PATHS": {"artifacts_manifest.json", "game-copy"},
                    "DELETE_DIR_NAMES": set(),
                    "EXTRA_DELETE_PATHS": set(),
                    "EXTRA_DELETE_GLOBS": set(),
                }
                for module, values in ((paths, wp_values), (cleanup, cleanup_values)):
                    for key, value in values.items():
                        stack.enter_context(patch.object(module, key, value))
                # A unit fixture owns its synthetic checkout, even when TEMP
                # is redirected inside the real DEV checkout by the wrapper.
                stack.enter_context(patch.object(cleanup, "_project_inventory_root", return_value=root))
                yield root, work, game_copy, manifest

    def _register(self, artifact: Path, *, lifecycle: str = "DISPOSABLE") -> None:
        paths.register_artifact(
            artifact_id=f"test:{artifact.name}",
            path=artifact,
            kind="test_fixture",
            created_by="test_cleanup_work_artifacts",
            owner="test_cleanup_work_artifacts",
            purpose="focused lifecycle test",
            lifecycle=lifecycle,
        )

    @contextlib.contextmanager
    def canonical_runner_harness(self):
        """Run the subprocess wrapper against a clean copied project surface."""
        with self.isolated_owner_pending():
            paths.WORK_ROOT.mkdir(parents=True, exist_ok=True)
            harness = Path(tempfile.mkdtemp(prefix="vntext-canonical-runner-", dir=paths.WORK_ROOT))
            for relative in (
                Path("tests/lib/bootstrap.py"),
                Path("tests/lib/work_paths.py"),
                Path("tests/tools/cleanup_work_artifacts.py"),
                Path("tests/tools/run_with_cleanup.py"),
            ):
                destination = harness / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(ROOT / relative, destination)
            work = harness / "TEST_RUN"
            work.mkdir(parents=True)
            self.assertNotEqual(
                (work / "artifacts_manifest.json").resolve(),
                paths.MANIFEST_PATH.resolve(),
            )
            self.assertNotEqual(
                (harness / "tests" / "tools" / "run_with_cleanup.py").resolve(),
                RUNNER.resolve(),
            )
            canonical_before = (
                paths.MANIFEST_PATH.read_bytes() if paths.MANIFEST_PATH.exists() else None
            )
            try:
                yield harness, harness / "tests" / "tools" / "run_with_cleanup.py", work
            finally:
                canonical_after = (
                    paths.MANIFEST_PATH.read_bytes() if paths.MANIFEST_PATH.exists() else None
                )
                self.assertEqual(canonical_before, canonical_after)
                shutil.rmtree(harness, ignore_errors=True)

    def test_protected_game_copy_is_not_deleted(self):
        with self.isolated_workspace() as (_root, _work, game, _manifest):
            (game / "marker.txt").write_text("keep", encoding="utf-8")
            report = cleanup.cleanup_after_test([game], reason="protected-test", outcome="PASS")
            self.assertFalse(report["ok"])
            self.assertTrue(game.is_dir())
            self.assertTrue((game / "marker.txt").is_file())
            self.assertEqual("protected_game_copy", report["errors"][0]["reason"])

    def test_cleanup_target_rejects_external_user_or_game_path(self):
        with self.isolated_workspace() as (root, _work, _game, _manifest):
            outside = root / "outside-user-data"
            outside.mkdir()
            with self.assertRaises(RuntimeError):
                paths.cleanup_target(outside, "outside")
            report = cleanup.cleanup_after_test([outside], reason="outside-test", outcome="PASS")
            self.assertFalse(report["ok"])
            self.assertTrue(outside.is_dir())

    def test_dry_run_is_read_only_and_plans_registered_disposable(self):
        with self.isolated_workspace() as (_root, work, _game, manifest):
            artifact = work / "run-output"
            artifact.mkdir()
            (artifact / "payload.bin").write_bytes(b"x" * 16)
            self._register(artifact)
            before_manifest = manifest.read_bytes()
            before_paths = sorted(str(p.relative_to(work)) for p in work.rglob("*"))

            report = cleanup.cleanup_work(dry_run=True, registered_only=True, outcome="PASS")

            self.assertTrue(report["ok"], report)
            self.assertTrue(any(item["path"].endswith("run-output") for item in report["would_delete"]))
            self.assertTrue(artifact.is_dir())
            self.assertEqual(before_manifest, manifest.read_bytes())
            self.assertEqual(before_paths, sorted(str(p.relative_to(work)) for p in work.rglob("*")))
            self.assertFalse((work / "cleanup_dry_run.json").exists())

    def test_cleanup_blocks_disposable_root_with_retained_claim(self):
        with self.isolated_workspace() as (_root, work, _game, manifest):
            target = work / "overlapping-claims"
            target.mkdir()
            payload = target / "keep.bin"
            payload.write_bytes(b"retained payload")
            paths.register_artifact(
                artifact_id="retained-claim",
                path=target,
                kind="retained_output",
                created_by="test_cleanup_work_artifacts",
                purpose="same root is retained by an earlier run",
                lifecycle="RETAINED",
            )
            paths.register_artifact(
                artifact_id="disposable-claim",
                path=target,
                kind="temporary_output",
                created_by="test_cleanup_work_artifacts",
                purpose="duplicate disposable registration must not override retention",
                lifecycle="DISPOSABLE",
            )
            before_manifest = manifest.read_bytes()

            dry_run = cleanup.cleanup_work(dry_run=True, registered_only=True, outcome="PASS")

            self.assertEqual(before_manifest, manifest.read_bytes())
            self.assertFalse(any(item["path"] == str(target) for item in dry_run["would_delete"]))
            self.assertTrue(any(
                item["path"] == str(target)
                and item["blocking_id"] == "retained-claim"
                for item in dry_run["blocked"]
            ))
            self.assertTrue(payload.is_file())

    def test_registered_keep_blocker_respects_lifecycle_and_malformed_claims(self):
        with self.isolated_workspace() as (_root, work, _game, _manifest):
            target = work / "candidate"
            descendant = target / "payload.bin"
            target.mkdir()
            descendant.write_bytes(b"keep")
            claim = {"id": "DISPOSABLE", "path": str(descendant), "lifecycle": "DISPOSABLE"}
            self.assertIsNone(cleanup._registered_keep_blocker(target, [claim]))
            missing_claim = {"id": "missing", "path": str(descendant), "lifecycle": "MISSING"}
            blocker = cleanup._registered_keep_blocker(target, [missing_claim])
            self.assertEqual("STALE", blocker["lifecycle"])
            self.assertEqual("missing_claim_path_still_exists", blocker["reason"])
            for lifecycle in ("PROTECTED", "RETAINED", "UNKNOWN", "STALE"):
                with self.subTest(lifecycle=lifecycle):
                    claim = {"id": lifecycle, "path": str(descendant), "lifecycle": lifecycle}
                    self.assertEqual(lifecycle, cleanup._registered_keep_blocker(target, [claim])["lifecycle"])
            malformed = {"id": "bad-path", "lifecycle": "DISPOSABLE"}
            self.assertEqual("UNKNOWN", cleanup._registered_keep_blocker(target, [malformed])["lifecycle"])
            self.assertEqual("UNKNOWN", cleanup._registered_keep_blocker(target, [None])["lifecycle"])
            malformed_lifecycle = {"id": "bad-life", "path": str(descendant), "lifecycle": "BOGUS", "status": "MISSING"}
            self.assertEqual("UNKNOWN", cleanup._registered_keep_blocker(target, [malformed_lifecycle])["lifecycle"])
            descendant.unlink()
            self.assertIsNone(cleanup._registered_keep_blocker(target, [missing_claim]))

    def test_malformed_registry_claim_blocks_cleanup_without_rewriting_registry(self):
        with self.isolated_workspace() as (_root, work, _game, manifest):
            target = work / "disposable-output"
            target.mkdir()
            payload = target / "payload.bin"
            payload.write_bytes(b"keep until ownership is valid")
            self._register(target, lifecycle="DISPOSABLE")
            document = json.loads(manifest.read_text(encoding="utf-8"))
            valid_document = json.loads(json.dumps(document))
            document["artifacts"].append(None)
            malformed = (json.dumps(document, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
            manifest.write_bytes(malformed)

            result = cleanup.cleanup_work(dry_run=False, registered_only=True, outcome="PASS")

            self.assertEqual("REVIEW_REQUIRED", result["cleanup_status"], result)
            self.assertTrue(payload.is_file())
            self.assertEqual(malformed, manifest.read_bytes())
            self.assertTrue(result["blocked"])

            before = cleanup.snapshot_tree(work, include_hashes=True, skip_retained=True)
            finalized = cleanup.finalize_scope(
                scope_id="legacy",
                run_id="legacy",
                scope_root=work,
                before=before,
                outcome="PASS",
            )
            self.assertEqual("REVIEW_REQUIRED", finalized["cleanup_status"], finalized)
            self.assertTrue(payload.is_file())
            self.assertEqual(malformed, manifest.read_bytes())

            malformed_claims = []
            missing_id_claim = dict(valid_document["artifacts"][0])
            missing_id_claim.pop("id")
            malformed_claims.append(missing_id_claim)
            invalid_lifecycle_claim = dict(valid_document["artifacts"][0])
            invalid_lifecycle_claim.update({"lifecycle": "BROKEN", "status": "DISPOSABLE"})
            malformed_claims.append(invalid_lifecycle_claim)
            duplicate_id_claim = dict(valid_document["artifacts"][0])
            malformed_claims.append(duplicate_id_claim)
            for claim in malformed_claims:
                with self.subTest(claim=claim):
                    candidate = json.loads(json.dumps(valid_document))
                    candidate["artifacts"].append(claim)
                    malformed_claim = (json.dumps(candidate, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
                    manifest.write_bytes(malformed_claim)
                    result = cleanup.cleanup_work(dry_run=False, registered_only=True, outcome="PASS")
                    self.assertEqual("REVIEW_REQUIRED", result["cleanup_status"], result)
                    self.assertTrue(payload.is_file())
                    self.assertEqual(malformed_claim, manifest.read_bytes())
                    self.assertTrue(result["blocked"])

    def test_project_size_measures_fixed_exemptions_and_fails_closed_on_links_and_special_nodes(self):
        with self.isolated_workspace() as (root, _work, _game, _manifest):
            venv = root / ".venv"
            sdk = root / "DEV_RUN" / "dotnet-sdk-10"
            venv.mkdir()
            sdk.mkdir(parents=True)
            (venv / "python.bin").write_bytes(b"12345")
            (sdk / "dotnet.bin").write_bytes(b"1234567")
            (root / "source.txt").write_bytes(b"123")
            with patch.object(cleanup, "PROJECT_SIZE_EXEMPTIONS", {
                ".venv": "test Python environment",
                "DEV_RUN/dotnet-sdk-10": "test SDK",
            }):
                measured = cleanup._project_size_snapshot()
            self.assertTrue(measured["complete"], measured)
            self.assertEqual(3, measured["non_exempt_bytes"])
            self.assertEqual(
                {".venv": (5, "test Python environment"), "DEV_RUN/dotnet-sdk-10": (7, "test SDK")},
                {item["path"]: (item["bytes"], item["reason"]) for item in measured["exemptions"]},
            )
            class Entry:
                def __init__(self, path, mode):
                    self.path = str(path)
                    self.mode = mode

                def stat(self, *, follow_symlinks=False):
                    return type("Info", (), {"st_mode": self.mode, "st_size": 0, "st_file_attributes": 0})()

            class Scan:
                def __init__(self, entries):
                    self.entries = entries

                def __enter__(self):
                    return iter(self.entries)

                def __exit__(self, *_args):
                    return False

            real_scandir = os.scandir
            def injected_scandir(directory):
                if Path(directory) == root:
                    return Scan([Entry(root / "source-link", stat.S_IFLNK | 0o777)])
                return real_scandir(directory)

            with patch.object(cleanup.os, "scandir", side_effect=injected_scandir):
                linked = cleanup._project_size_snapshot()
            self.assertFalse(linked["complete"])
            self.assertTrue(any(item["error"] == "link_or_reparse_point" for item in linked["errors"]))

            def injected_special_scandir(directory):
                if Path(directory) == root:
                    return Scan([Entry(root / "special.pipe", stat.S_IFIFO | 0o600)])
                return real_scandir(directory)

            with patch.object(cleanup.os, "scandir", side_effect=injected_special_scandir):
                special = cleanup._project_size_snapshot()
            self.assertFalse(special["complete"])
            self.assertTrue(any(item["error"] == "unsupported_special_file" for item in special["errors"]))

    def test_cleanup_never_deletes_through_registered_link(self):
        with self.isolated_workspace() as (_root, work, _game, _manifest):
            target = work / "link-target.bin"
            target.write_bytes(b"target")
            link = work / "registered-link"
            deleted = []
            real_lstat = Path.lstat

            def injected_lstat(candidate):
                if candidate == link:
                    return type("LinkInfo", (), {"st_mode": stat.S_IFLNK | 0o777, "st_file_attributes": 0})()
                return real_lstat(candidate)

            with patch.object(Path, "lstat", new=injected_lstat):
                removed = cleanup.safe_rmtree(link, deleted, reason="focused link guard", allow_registered_disposable=True)
            self.assertFalse(removed)
            self.assertFalse(link.exists())
            self.assertTrue(target.is_file())
            self.assertEqual("link_or_reparse_point", deleted[0]["reason"])

    def test_combined_exempt_cap_and_exact_baseline_roots(self):
        with self.isolated_workspace() as (root, _work, _game, _manifest):
            for relative, payload in [(".dev-env", b"123"), ("DEV_RUN/cache", b"456"),
                                      ("DEV_RUN/baselines/fullapp-013", b"7"),
                                      ("DEV_RUN/baselines/stable-012", b"a"),
                                      ("DEV_RUN/baselines/unapproved", b"89")]:
                folder = root / relative
                folder.mkdir(parents=True, exist_ok=True)
                (folder / "payload").write_bytes(payload)
            with patch.object(cleanup, "PROJECT_EXEMPT_SIZE_LIMIT_BYTES", 6), patch.object(cleanup, "PROJECT_SIZE_LIMIT_BYTES", 6):
                result = cleanup._project_size_snapshot()
            self.assertTrue(result["complete"], result)
            self.assertEqual(3, result["exempt_bytes"])
            self.assertEqual(7, result["non_exempt_bytes"])
            self.assertFalse(result["within_limit"], result)

    def test_snapshot_inventory_counts_main_root_and_nested_duplicate_environment(self):
        with self.isolated_workspace() as (root, _work, _game, _manifest):
            for relative in ["tests/tools/cleanup_work_artifacts.py", "tests/lib/work_paths.py"]:
                marker = root / relative
                marker.parent.mkdir(parents=True, exist_ok=True)
                marker.write_bytes(b"")
            snapshot = root / ".scratch/snapshot"
            (snapshot / ".venv").mkdir(parents=True)
            (snapshot / ".venv/payload").write_bytes(b"123")
            (root / "outside-snapshot").write_bytes(b"4567")
            actual_is_file = Path.is_file
            def fixture_marker(path):
                if path.name in {"cleanup_work_artifacts.py", "work_paths.py"}:
                    return path in {root / "tests/tools/cleanup_work_artifacts.py", root / "tests/lib/work_paths.py"}
                return actual_is_file(path)
            with patch.object(cleanup, "ROOT", snapshot), patch.object(cleanup, "PROJECT_SIZE_LIMIT_BYTES", 6), \
                 patch.object(cleanup, "_project_inventory_root", PROJECT_INVENTORY_ROOT), \
                 patch.object(Path, "is_file", fixture_marker):
                result = cleanup._project_size_snapshot()
            self.assertEqual(str(root.resolve()), result["root"])
            self.assertEqual(7, result["non_exempt_bytes"])
            self.assertEqual(0, result["exempt_bytes"])
            self.assertFalse(result["within_limit"])

    def test_runner_quota_preflight_blocks_child_and_new_retained_output(self):
        with self.isolated_workspace() as (root, work, _game, _manifest):
            snapshot = root / ".scratch/snapshot"
            snapshot.mkdir(parents=True)
            blocked = {"root": str(root), "complete": True, "within_limit": False,
                       "non_exempt_bytes": cleanup.PROJECT_SIZE_LIMIT_BYTES + 1,
                       "exempt_bytes": 0, "errors": []}
            report = work / "blocked.json"
            output = work / "must-not-be-created"
            with patch.object(runner, "ROOT", snapshot), patch.object(runner, "WORK_ROOT", work), \
                 patch.object(cleanup, "_project_size_snapshot", return_value=blocked), \
                 patch.object(runner, "_source_sha", return_value="fixture-source"), \
                 patch.object(runner.subprocess, "Popen") as launch:
                code = runner.run([sys.executable, "-c", "pass"], timeout=10,
                                          report_path=report, retained_roots=[output])
            self.assertEqual(1, code)
            launch.assert_not_called()
            self.assertFalse(output.exists())
            result = json.loads(report.read_text(encoding="utf-8"))
            self.assertEqual("PROVEN_BLOCKED", result["outcome"])
            self.assertEqual("NOT_STARTED", result["child_process_state"])
            self.assertIsNone(result["child_exit_code"])
            self.assertEqual(str(root), result["cleanup"]["project_size"]["before"]["root"])

    def test_project_size_incomplete_or_over_limit_never_yields_cleanup_pass(self):
        for operation in ("scope", "whole", "post_test"):
            with self.subTest(operation=operation), self.isolated_workspace() as (_root, work, _game, _manifest):
                artifact = work / f"size-gate-{operation}"
                artifact.mkdir()
                (artifact / "payload").write_text("temporary", encoding="utf-8")
                if operation != "scope":
                    self._register(artifact)
                before = {"complete": True, "within_limit": True, "non_exempt_bytes": 1, "limit_bytes": cleanup.PROJECT_SIZE_LIMIT_BYTES, "exemptions": []}
                too_large = {"complete": True, "within_limit": False, "non_exempt_bytes": cleanup.PROJECT_SIZE_LIMIT_BYTES + 1, "limit_bytes": cleanup.PROJECT_SIZE_LIMIT_BYTES, "exemptions": []}
                incomplete = {"complete": False, "within_limit": False, "non_exempt_bytes": None, "limit_bytes": cleanup.PROJECT_SIZE_LIMIT_BYTES, "exemptions": [], "errors": [{"error": "injected"}]}
                snapshots = [before, too_large] if operation != "post_test" else [incomplete, before]
                with patch.object(cleanup, "_project_size_snapshot", side_effect=snapshots):
                    if operation == "scope":
                        scope_id = paths.new_scope_id("size-gate")
                        paths.register_artifact(
                            artifact_id=f"size-gate-{operation}", path=artifact, kind="test_output",
                            created_by="focused-test", owner="focused-test", purpose="size gate",
                            lifecycle="DISPOSABLE", scope_id=scope_id, run_id=scope_id,
                        )
                        result = cleanup.finalize_scope(
                            scope_id=scope_id, run_id=scope_id, scope_root=work,
                            before=cleanup.snapshot_tree(work), outcome="PASS",
                        )
                    elif operation == "whole":
                        result = cleanup.cleanup_work(dry_run=False, registered_only=True, outcome="PASS")
                    else:
                        result = cleanup.cleanup_after_test([artifact], reason="size-gate", outcome="PASS")
                self.assertEqual("REVIEW_REQUIRED", result.get("cleanup_status", result.get("status")), result)

    def test_retained_tree_registration_is_batched_and_idempotent_by_path(self):
        with self.isolated_workspace() as (_root, work, _game, manifest):
            retained = work / "retained-output"
            nested = retained / "nested"
            nested.mkdir(parents=True)
            (retained / "root.bin").write_bytes(b"root")
            (nested / "child.bin").write_bytes(b"child-data")

            with patch.object(runner, "WORK_ROOT", work):
                with patch.object(paths, "_save_manifest", wraps=paths._save_manifest) as save_manifest:
                    runner._register_retained_tree(retained, scope_id="scope-one", run_id="run-one")
                    self.assertEqual(1, save_manifest.call_count)
                    first = json.loads(manifest.read_text(encoding="utf-8"))["artifacts"]
                    first_paths = {
                        item["path"]: item["id"]
                        for item in first
                        if item.get("id", "").startswith("runner-retained-path:")
                    }

                    runner._register_retained_tree(retained, scope_id="scope-two", run_id="run-two")
                    self.assertEqual(2, save_manifest.call_count)

            second = json.loads(manifest.read_text(encoding="utf-8"))["artifacts"]
            records = [item for item in second if item.get("id", "").startswith("runner-retained-path:")]
            self.assertEqual(3, len(records))
            self.assertEqual(first_paths, {item["path"]: item["id"] for item in records})
            self.assertTrue(all(item["scope_id"] == "scope-two" and item["run_id"] == "run-two" for item in records))
            nested_record = next(item for item in records if item["path"] == str(nested.resolve()))
            self.assertEqual(len(b"child-data"), nested_record["bytes"])

    def test_artifact_batch_rejects_duplicate_id(self):
        with self.isolated_workspace() as (_root, work, _game, manifest):
            first = work / "first.bin"
            second = work / "second.bin"
            first.write_bytes(b"first")
            second.write_bytes(b"second")
            record = {
                "artifact_id": "same-id",
                "kind": "output",
                "created_by": "test",
                "purpose": "batch collision test",
                "lifecycle": "RETAINED",
                "scope_id": "scope",
                "run_id": "run",
                "scope_root": work,
            }
            with self.assertRaisesRegex(ValueError, "duplicate artifact id in batch"):
                paths.register_artifacts([
                    {**record, "path": first},
                    {**record, "path": second},
                ])
            self.assertFalse(manifest.exists())

    def test_report_inventory_keeps_digest_and_omits_repeated_path_rows(self):
        items = {
            "b.txt": {"path": "b.txt", "bytes": 2},
            "a.txt": {"path": "a.txt", "bytes": 1},
        }
        report = cleanup._report_inventory_snapshot(
            {"root": "work", "items": items, "errors": [], "complete": True}
        )
        reordered = cleanup._report_inventory_snapshot(
            {"root": "work", "items": dict(reversed(list(items.items()))), "errors": [], "complete": True}
        )
        self.assertNotIn("items", report)
        self.assertTrue(report["items_omitted"])
        self.assertEqual(2, report["items_count"])
        self.assertEqual(64, len(report["items_sha256"]))
        self.assertEqual(report["items_sha256"], reordered["items_sha256"])
        self.assertTrue(report["complete"])

        large_report = {"unknown": [{"id": str(index)} for index in range(101)]}
        cleanup._compact_report_records(large_report, ("unknown",))
        self.assertEqual(100, len(large_report["unknown"]))
        self.assertEqual(101, large_report["unknown_summary"]["count"])
        self.assertTrue(large_report["unknown_summary"]["omitted"])

    def test_registered_disposable_under_retained_evidence_is_owner_cleanable(self):
        with self.isolated_workspace() as (_root, work, _game, _manifest):
            artifact = work / "evidence" / "runtime_data"
            artifact.mkdir(parents=True)
            (artifact / "player.log").write_text("runtime", encoding="utf-8")
            paths.register_artifact(
                artifact_id="test:evidence-root",
                path=work / "evidence",
                kind="test_evidence",
                created_by="test_cleanup_work_artifacts",
                owner="test_cleanup_work_artifacts",
                purpose="retained evidence parent",
                lifecycle="RETAINED",
            )
            self._register(artifact)
            paths.register_artifact(
                artifact_id="test:duplicate-runtime-data",
                path=artifact,
                kind="test_fixture",
                created_by="test_cleanup_work_artifacts",
                owner="test_cleanup_work_artifacts",
                purpose="duplicate runtime cleanup registration",
                lifecycle="DISPOSABLE",
            )
            with patch.object(cleanup, "KEEP_PATHS", {"artifacts_manifest.json", "game-copy", "evidence"}):
                report = cleanup.cleanup_work(
                    dry_run=False,
                    registered_only=True,
                    outcome="PASS",
                )

            self.assertTrue(report["ok"], report)
            self.assertFalse(artifact.exists())
            self.assertTrue(any(item.get("path") == str(artifact) and item.get("deleted") for item in report["deleted"]))
            manifest = json.loads((work / "artifacts_manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(
                {"MISSING"},
                {
                    item["lifecycle"]
                    for item in manifest["artifacts"]
                    if item["id"] in {"test:runtime_data", "test:duplicate-runtime-data"}
                },
            )

    def test_dry_run_inventory_timeout_is_terminal_read_only(self):
        with self.isolated_workspace() as (_root, work, _game, manifest):
            unknown = work / "unclassified-large-tree"
            unknown.mkdir()
            (unknown / "payload.bin").write_bytes(b"keep")
            before_manifest = manifest.read_bytes() if manifest.exists() else None
            before_paths = sorted(str(path.relative_to(work)) for path in work.rglob("*"))

            report = cleanup.cleanup_work(
                dry_run=True,
                registered_only=True,
                outcome="PASS",
                timeout_seconds=0,
            )

            self.assertEqual("REVIEW_REQUIRED", report["status"])
            self.assertFalse(report["ok"])
            self.assertFalse(report["inventory_complete"])
            self.assertEqual("TIMEOUT", report["inventory"]["budget"]["status"])
            self.assertEqual([], report["deleted"])
            self.assertTrue(unknown.is_dir())
            self.assertEqual(before_manifest, manifest.read_bytes() if manifest.exists() else None)
            self.assertEqual(before_paths, sorted(str(path.relative_to(work)) for path in work.rglob("*")))
            self.assertFalse((work / "cleanup_manifest.json").exists())

    def test_inventory_item_limit_is_fail_closed_without_delete(self):
        with self.isolated_workspace() as (_root, work, _game, _manifest):
            artifact = work / "registered-output"
            artifact.mkdir()
            (artifact / "payload.bin").write_bytes(b"must remain")
            self._register(artifact)

            report = cleanup.cleanup_work(
                dry_run=False,
                registered_only=True,
                outcome="PASS",
                timeout_seconds=30,
                max_items=1,
            )

            self.assertEqual("REVIEW_REQUIRED", report["status"])
            self.assertFalse(report["ok"])
            self.assertFalse(report["inventory_complete"])
            self.assertEqual("LIMIT", report["inventory"]["budget"]["status"])
            self.assertEqual([], report["deleted"])
            self.assertTrue(artifact.is_dir())

    def test_cli_dry_run_timeout_emits_terminal_json_without_work_write(self):
        before_manifest = paths.MANIFEST_PATH.read_bytes() if paths.MANIFEST_PATH.exists() else None
        before_work = paths.WORK_ROOT.exists()
        stdout = io.StringIO()
        with patch.object(
            sys,
            "argv",
            [
                "cleanup_work_artifacts.py",
                "--dry-run",
                "--registered-only",
                "--outcome",
                "PASS",
                "--inventory-timeout-seconds",
                "0",
            ],
        ), contextlib.redirect_stdout(stdout):
            exit_code = cleanup.main()

        payload = json.loads(stdout.getvalue())
        self.assertEqual(1, exit_code)
        self.assertEqual("REVIEW_REQUIRED", payload["status"])
        self.assertFalse(payload["ok"])
        self.assertFalse(payload["inventory_complete"])
        self.assertEqual("TIMEOUT", payload["inventory_status"])
        self.assertEqual(before_manifest, paths.MANIFEST_PATH.read_bytes() if paths.MANIFEST_PATH.exists() else None)
        self.assertEqual(before_work, paths.WORK_ROOT.exists())

    def test_cli_cleanup_exception_emits_terminal_fail_closed_report(self):
        with self.isolated_workspace() as (root, _work, _game, _manifest):
            report_path = root / "cleanup-exception-report.json"
            stdout = io.StringIO()
            with patch.object(cleanup, "cleanup_work", side_effect=RuntimeError("synthetic cleanup failure")):
                with patch.object(
                    sys,
                    "argv",
                    [
                        "cleanup_work_artifacts.py",
                        "--registered-only",
                        "--outcome",
                        "PASS",
                        "--output",
                        str(report_path),
                    ],
                ), contextlib.redirect_stdout(stdout):
                    exit_code = cleanup.main()

            self.assertEqual(1, exit_code)
            payload = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertEqual("FAIL", payload["terminal_status"])
            self.assertEqual("REVIEW_REQUIRED", payload["status"])
            self.assertFalse(payload["ok"])
            self.assertFalse(payload["inventory_complete"])
            self.assertEqual([], payload["deleted"])

    def test_canonical_runner_cleanup_timeout_is_terminal_and_fail_closed(self):
        with self.isolated_workspace() as (_root, work, _game, manifest):
            stdout = io.StringIO()
            with patch.object(runner, "ROOT", _root), patch.object(runner, "WORK_ROOT", work), contextlib.redirect_stdout(stdout):
                exit_code = runner.run(
                    [sys.executable, "-c", "pass"],
                    timeout=10,
                    report_path=None,
                    cleanup_timeout=0,
                )

            payload = json.loads(stdout.getvalue())
            self.assertEqual(1, exit_code)
            self.assertEqual("REVIEW_REQUIRED", payload["status"])
            self.assertEqual("PASS", payload["outcome"])
            self.assertFalse(payload["cleanup"]["ok"])
            self.assertFalse(payload["cleanup"]["inventory_complete"])
            self.assertEqual("TIMEOUT", payload["cleanup"]["inventory"]["budget"]["status"])
            self.assertEqual([], payload["cleanup"]["deleted"])
            # The runner registers its compact report and disposable logs
            # before the finalization inventory. Incomplete inventory blocks
            # their deletion, and the report/registry stay available.
            if manifest.exists():
                entries = json.loads(manifest.read_text(encoding="utf-8"))["artifacts"]
                registered_paths = {item["path"]: item["lifecycle"] for item in entries}
                self.assertEqual("DISPOSABLE", registered_paths[payload["markdown_report"]])
                self.assertEqual("DISPOSABLE", registered_paths[payload["primary_output"]["stdout"]["path"]])
                self.assertEqual("DISPOSABLE", registered_paths[payload["primary_output"]["stderr"]["path"]])

    def test_finalization_timeout_is_terminal_and_does_not_delete(self):
        with self.isolated_workspace() as (_root, work, _game, _manifest):
            scope_id = paths.new_scope_id("finalization-timeout")
            artifact = work / "finalization-timeout-output"
            artifact.mkdir()
            (artifact / "payload.bin").write_bytes(b"must remain")
            paths.register_artifact(
                artifact_id="finalization-timeout-output",
                path=artifact,
                kind="test_output",
                created_by="test_cleanup_work_artifacts",
                owner="test_cleanup_work_artifacts",
                purpose="timeout regression output",
                lifecycle="DISPOSABLE",
                scope_id=scope_id,
                run_id=scope_id,
            )
            before = cleanup.snapshot_tree(work, include_hashes=False)

            report = cleanup.finalize_scope(
                scope_id=scope_id,
                run_id=scope_id,
                scope_root=work,
                before=before,
                outcome="PASS",
                timeout_seconds=0,
            )

            self.assertEqual("TIMEOUT", report["terminal_status"])
            self.assertEqual("REVIEW_REQUIRED", report["status"])
            self.assertFalse(report["ok"])
            self.assertFalse(report["inventory_complete"])
            self.assertEqual([], report["deleted"])
            self.assertTrue(artifact.is_dir())

    def test_lifecycle_metrics_scales_without_inventory_registry_cross_product(self):
        with self.isolated_workspace() as (_root, work, _game, _manifest):
            count = 8000
            entries = [
                {
                    "id": f"retained-{index}",
                    "path": str(work / f"registered-{index}"),
                    "lifecycle": "RETAINED",
                    "status": "ACTIVE",
                    "bytes": index,
                }
                for index in range(count)
            ]
            items = {
                f"candidate-{index}.txt": {
                    "path": str(work / f"candidate-{index}.txt"),
                    "relative_path": f"candidate-{index}.txt",
                    "kind": "file",
                    "bytes": 1,
                }
                for index in range(count)
            }
            budget = cleanup.InventoryBudget(timeout_seconds=5, max_items=1)
            started = time.perf_counter()
            metrics = cleanup._snapshot_lifecycle_metrics(
                {"items": items, "complete": True},
                {"entries": entries, "unknown": []},
                budget=budget,
            )
            elapsed = time.perf_counter() - started

            self.assertIsNone(budget.failure, budget.report())
            self.assertEqual(count, metrics["file_count"])
            self.assertEqual(count, metrics["registry_counts"]["RETAINED"])
            self.assertLess(elapsed, 5.0, f"lifecycle metrics exceeded deadline: {elapsed:.3f}s")

    def test_missing_active_entry_is_reconciled_without_silent_drop(self):
        with self.isolated_workspace() as (_root, work, _game, manifest):
            artifact = work / "will-disappear"
            artifact.mkdir()
            self._register(artifact, lifecycle="RETAINED")
            artifact.rmdir()

            result = cleanup.reconcile_registry(persist=False)

            entry = next(item for item in result["entries"] if item["id"] == "test:will-disappear")
            self.assertEqual("MISSING", entry["lifecycle"])
            self.assertEqual("ACTIVE", json.loads(manifest.read_text(encoding="utf-8"))["artifacts"][0]["status"])

    def test_registry_migration_dry_run_is_read_only_and_archives_terminal_metadata(self):
        with self.isolated_workspace() as (_root, work, _game, manifest):
            artifact = work / "historical-output"
            artifact.write_text("historical", encoding="utf-8")
            self._register(artifact, lifecycle="MISSING")
            history = work / "cleanup_post_test.jsonl"
            history.write_text(
                json.dumps(
                    {
                        "schema_version": 2,
                        "utc": "2026-01-02T03:04:05Z",
                        "reason": "historical cleanup",
                        "outcome": "PASS",
                        "ok": True,
                        "deleted": [
                            {
                                "path": str(artifact),
                                "deleted": True,
                                "deleted_at": "2026-01-02T03:04:05Z",
                                "reason": "historical cleanup",
                                "bytes": len("historical"),
                            }
                        ],
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            artifact.unlink()
            before = manifest.read_bytes()

            provenance = cleanup.backfill_missing_deletion_provenance(dry_run=True)
            report = cleanup.migrate_registry(dry_run=True, source_sha="test-sha")

            self.assertEqual(1, provenance["planned_count"])
            self.assertEqual(0, provenance["unresolved_count"])
            self.assertEqual(1, report["planned_archive_count"])
            self.assertEqual("PASS", report["status"])
            self.assertEqual(before, manifest.read_bytes())
            applied = cleanup.backfill_missing_deletion_provenance(dry_run=False)
            self.assertTrue(applied["ok"])
            entries = json.loads(manifest.read_text(encoding="utf-8"))["artifacts"]
            entry = next(item for item in entries if item["id"] == f"test:{artifact.name}")
            self.assertEqual("cleanup_post_test.jsonl", entry["deletion_provenance"]["evidence_source"])
            self.assertEqual("2026-01-02T03:04:05Z", entry["deletion_provenance"]["deleted_at"])
            self.assertFalse(artifact.exists())

    def test_registry_migration_apply_preserves_physical_unknown_and_is_idempotent(self):
        with self.isolated_workspace() as (_root, work, _game, manifest):
            artifact = work / "duplicate-output"
            artifact.mkdir()
            (artifact / "payload.txt").write_text("keep", encoding="utf-8")
            paths.register_artifact(
                artifact_id="unknown-default",
                path=artifact,
                kind="legacy",
                created_by="test",
                owner="unknown",
                purpose="unclassified artifact; manual review required",
                lifecycle="UNKNOWN",
            )
            paths.register_artifact(
                artifact_id="unknown-owned",
                path=artifact,
                kind="run-output",
                created_by="test",
                owner="phase-c",
                purpose="retained runtime evidence",
                lifecycle="UNKNOWN",
            )

            first = cleanup.migrate_registry(dry_run=False, source_sha="test-sha")
            doc = json.loads(manifest.read_text(encoding="utf-8"))
            self.assertEqual("REVIEW_REQUIRED", first["status"])
            self.assertEqual(1, first["live_unresolved"]["UNKNOWN"])
            self.assertEqual({"unknown-owned"}, {item["id"] for item in doc["artifacts"]})
            self.assertEqual({"unknown-default"}, {item["id"] for item in doc["archive"]})
            archived = doc["archive"][0]
            self.assertEqual("UNKNOWN", archived["lifecycle_before_archive"])
            self.assertEqual("ACTIVE", archived["status_before_archive"])
            self.assertEqual("test-sha", archived["migration_source_sha"])
            self.assertTrue((artifact / "payload.txt").is_file())

            second = cleanup.migrate_registry(dry_run=False, source_sha="test-sha")
            doc_again = json.loads(manifest.read_text(encoding="utf-8"))
            self.assertEqual(0, second["planned_archive_count"])
            self.assertEqual(1, len(doc_again["archive"]))
            self.assertEqual(doc["artifacts"], doc_again["artifacts"])

    def _epoch_guards(self):
        return patch.object(
            cleanup,
            "_git_repository_state",
            return_value={"head": "test-sha", "dirty": False, "error": ""},
        ), patch.object(
            cleanup,
            "_incident_identity",
            return_value={"scope_id": cleanup.INCIDENT_SCOPE_ID, "status": "PASS", "sha256": cleanup.INCIDENT_REGISTRY_SHA256, "artifact_count": 6},
        )

    def test_prospective_epoch_plan_is_read_only(self):
        with self.isolated_workspace() as (_root, work, _game, manifest):
            artifact = work / "known"
            artifact.mkdir()
            self._register(artifact, lifecycle="RETAINED")
            before = manifest.read_bytes()
            git_guard, incident_guard = self._epoch_guards()
            with git_guard, incident_guard:
                result = cleanup.activate_prospective_epoch(dry_run=True, epoch_id="epoch-plan", source_sha="test-sha")
            self.assertTrue(result["ok"])
            self.assertEqual("PASS", result["status"])
            self.assertEqual(before, manifest.read_bytes())
            self.assertFalse((work / "artifact-registry-epochs").exists())

    def test_empty_registry_reset_requires_explicit_owner_authorization(self):
        with self.isolated_workspace() as (_root, work, _game, manifest):
            before_paths = {str(path.relative_to(work)) for path in work.rglob("*")}
            git_guard = patch.object(
                cleanup,
                "_git_repository_state",
                return_value={"head": "test-sha", "dirty": False, "error": ""},
            )
            missing_incident = patch.object(
                cleanup,
                "_incident_identity",
                return_value={"scope_id": cleanup.INCIDENT_SCOPE_ID, "path": str(cleanup._prospective_epoch_incident_path()), "status": "MISSING"},
            )
            with git_guard, missing_incident:
                result = cleanup.activate_prospective_epoch(
                    dry_run=True, epoch_id="epoch-reset-no-auth", source_sha="test-sha"
                )
                invalid = cleanup.activate_prospective_epoch(
                    dry_run=True, epoch_id="epoch-reset-blank-auth", source_sha="test-sha",
                    owner_reset_authorization="   ",
                )
            self.assertFalse(result["ok"])
            self.assertIn("owner_reset_authorization_required", result["reasons"])
            self.assertFalse(invalid["ok"])
            self.assertIn("owner_reset_authorization_required", invalid["reasons"])
            self.assertFalse(manifest.exists())
            self.assertFalse((work / "artifact-registry-epochs").exists())
            self.assertEqual(before_paths, {str(path.relative_to(work)) for path in work.rglob("*")})

    def test_explicit_owner_reset_records_unverifiable_history_and_verifies_in_isolation(self):
        with self.isolated_workspace() as (_root, work, _game, manifest):
            git_guard = patch.object(
                cleanup,
                "_git_repository_state",
                return_value={"head": "test-sha", "dirty": False, "error": ""},
            )
            missing_incident = patch.object(
                cleanup,
                "_incident_identity",
                return_value={"scope_id": cleanup.INCIDENT_SCOPE_ID, "path": str(cleanup._prospective_epoch_incident_path()), "status": "MISSING"},
            )
            authorization = "Owner authorized a prospective registry reset after deleting the previous _work scope."
            with git_guard, missing_incident:
                applied = cleanup.activate_prospective_epoch(
                    dry_run=False, epoch_id="epoch-owner-reset", source_sha="test-sha",
                    owner_reset_authorization=authorization,
                )
                verified = cleanup.verify_prospective_epoch()
            self.assertTrue(applied["ok"], applied)
            self.assertTrue(verified["ok"], verified)
            epoch = json.loads(manifest.read_text(encoding="utf-8"))["prospective_epoch"]
            self.assertEqual("OWNER_AUTHORIZED_RESET", epoch["reset_provenance"]["status"])
            self.assertEqual(authorization, epoch["reset_provenance"]["authorization"])
            self.assertEqual("ABSENT", epoch["reset_provenance"]["manifest_before"])
            self.assertEqual("MISSING", epoch["reset_provenance"]["incident_before"]["status"])
            self.assertEqual("NOT_RECOVERABLE/UNVERIFIABLE", epoch["historical_hygiene"])
            self.assertEqual("NOT_RECOVERABLE/UNVERIFIABLE", epoch["historical_registry_identity"]["status"])
            self.assertEqual(0, epoch["rollback"]["bytes"])
            self.assertTrue(epoch["rollback"]["manifest_absent"])
            self.assertTrue(Path(epoch["rollback"]["path"]).is_file())

            invalid_document = json.loads(manifest.read_text(encoding="utf-8"))
            invalid_document["prospective_epoch"]["reset_provenance"]["authorization"] = ""
            cleanup._atomic_write_bytes(
                manifest,
                (json.dumps(invalid_document, ensure_ascii=False, indent=2) + "\n").encode("utf-8"),
            )
            with missing_incident:
                invalid = cleanup.verify_prospective_epoch()
            self.assertFalse(invalid["ok"])
            self.assertIn("owner_reset_record_invalid", invalid["reasons"])
            self.assertIn("rollback_metadata_reset_record_mismatch", invalid["reasons"])

    def test_explicit_owner_reset_captures_present_post_reset_manifest_as_exact_rollback(self):
        with self.isolated_workspace() as (_root, work, _game, manifest):
            artifact = work / "new-run-report.md"
            artifact.write_text("current task evidence", encoding="utf-8")
            self._register(artifact, lifecycle="RETAINED")
            before = manifest.read_bytes()
            before_sha = cleanup.hashlib.sha256(before).hexdigest().upper()
            git_guard = patch.object(
                cleanup,
                "_git_repository_state",
                return_value={"head": "test-sha", "dirty": False, "error": ""},
            )
            missing_incident = patch.object(
                cleanup,
                "_incident_identity",
                return_value={"scope_id": cleanup.INCIDENT_SCOPE_ID, "path": str(cleanup._prospective_epoch_incident_path()), "status": "MISSING"},
            )
            authorization = "Owner authorizes a new epoch after the prior registry and incident were removed."
            with git_guard, missing_incident:
                applied = cleanup.activate_prospective_epoch(
                    dry_run=False, epoch_id="epoch-present-manifest-reset", source_sha="test-sha",
                    owner_reset_authorization=authorization,
                )
                verified = cleanup.verify_prospective_epoch()
            self.assertTrue(applied["ok"], applied)
            self.assertTrue(verified["ok"], verified)
            epoch = json.loads(manifest.read_text(encoding="utf-8"))["prospective_epoch"]
            reset = epoch["reset_provenance"]
            rollback = epoch["rollback"]
            self.assertEqual("ABSENT", reset["owner_reported_reset"]["manifest"])
            self.assertEqual("PRESENT", reset["manifest_before"])
            self.assertEqual(before_sha, reset["manifest_before_sha256"])
            self.assertEqual(len(before), reset["manifest_before_bytes"])
            self.assertFalse(rollback["manifest_absent"])
            self.assertEqual(before_sha, rollback["sha256"])
            self.assertEqual(before, Path(rollback["path"]).read_bytes())
            self.assertEqual("NOT_RECOVERABLE/UNVERIFIABLE", epoch["historical_registry_identity"]["status"])

            Path(rollback["path"]).write_bytes(before + b"tampered")
            with missing_incident:
                invalid = cleanup.verify_prospective_epoch()
            self.assertFalse(invalid["ok"])
            self.assertIn("rollback_snapshot_hash_mismatch", invalid["reasons"])

    def test_malformed_manifest_blocks_authorized_epoch_reset_without_mutation(self):
        with self.isolated_workspace() as (_root, work, _game, manifest):
            manifest.write_text("{not-json", encoding="utf-8")
            before = manifest.read_bytes()
            git_guard = patch.object(
                cleanup,
                "_git_repository_state",
                return_value={"head": "test-sha", "dirty": False, "error": ""},
            )
            missing_incident = patch.object(
                cleanup,
                "_incident_identity",
                return_value={"scope_id": cleanup.INCIDENT_SCOPE_ID, "path": str(cleanup._prospective_epoch_incident_path()), "status": "MISSING"},
            )
            with git_guard, missing_incident:
                result = cleanup.activate_prospective_epoch(
                    dry_run=False, epoch_id="epoch-malformed-manifest", source_sha="test-sha",
                    owner_reset_authorization="Owner authorizes only a valid current manifest snapshot.",
                )
            self.assertFalse(result["ok"])
            self.assertIn("registry_manifest_invalid", result["reasons"])
            self.assertEqual(before, manifest.read_bytes())
            self.assertFalse((work / "artifact-registry-epochs").exists())

    def test_manifest_directory_blocks_authorized_epoch_reset(self):
        with self.isolated_workspace() as (_root, work, _game, manifest):
            manifest.mkdir()
            git_guard = patch.object(
                cleanup,
                "_git_repository_state",
                return_value={"head": "test-sha", "dirty": False, "error": ""},
            )
            missing_incident = patch.object(
                cleanup,
                "_incident_identity",
                return_value={"scope_id": cleanup.INCIDENT_SCOPE_ID, "path": str(cleanup._prospective_epoch_incident_path()), "status": "MISSING"},
            )
            with git_guard, missing_incident:
                result = cleanup.activate_prospective_epoch(
                    dry_run=False, epoch_id="epoch-directory-manifest", source_sha="test-sha",
                    owner_reset_authorization="Owner authorizes no reset over malformed state.",
                )
            self.assertFalse(result["ok"])
            self.assertIn("registry_manifest_not_regular_file", result["reasons"])
            self.assertTrue(manifest.is_dir())
            self.assertFalse((work / "artifact-registry-epochs").exists())

    def test_epoch_preflight_preserves_writer_lock_and_rejects_registry_change(self):
        with self.isolated_workspace() as (_root, work, _game, manifest):
            artifact = work / "current-report.md"
            artifact.write_text("registered", encoding="utf-8")
            self._register(artifact, lifecycle="RETAINED")
            writer_lock = work / ".artifact-registry-epoch.writer.lock"
            git_guard, incident_guard = self._epoch_guards()
            original_snapshot_tree = cleanup.snapshot_tree

            def add_competing_writer_lock(*args, **kwargs):
                if not writer_lock.exists():
                    writer_lock.write_text("another active writer", encoding="utf-8")
                return original_snapshot_tree(*args, **kwargs)

            with git_guard, incident_guard, patch.object(
                cleanup, "snapshot_tree", side_effect=add_competing_writer_lock
            ):
                locked = cleanup.activate_prospective_epoch(
                    dry_run=False, epoch_id="epoch-concurrent-writer", source_sha="test-sha"
                )
            self.assertFalse(locked["ok"])
            self.assertIn("registry_writer_active", locked["reasons"])
            self.assertEqual("another active writer", writer_lock.read_text(encoding="utf-8"))

        with self.isolated_workspace() as (_root, work, _game, manifest):
            artifact = work / "current-report.md"
            artifact.write_text("registered", encoding="utf-8")
            self._register(artifact, lifecycle="RETAINED")
            before = manifest.read_bytes()
            original_snapshot_tree = cleanup.snapshot_tree
            calls = 0

            def change_manifest_after_preflight(*args, **kwargs):
                nonlocal calls
                calls += 1
                result = original_snapshot_tree(*args, **kwargs)
                if calls == 1:
                    manifest.write_bytes(before + b"\n")
                return result

            git_guard, incident_guard = self._epoch_guards()
            with git_guard, incident_guard, patch.object(
                cleanup, "snapshot_tree", side_effect=change_manifest_after_preflight
            ):
                changed = cleanup.activate_prospective_epoch(
                    dry_run=False, epoch_id="epoch-changed-registry", source_sha="test-sha"
                )
            self.assertFalse(changed["ok"])
            self.assertIn("registry_state_changed_during_preflight", changed["reasons"])
            self.assertEqual(before + b"\n", manifest.read_bytes())
            self.assertFalse((work / ".artifact-registry-epoch.writer.lock").exists())

    def test_incident_directory_is_invalid_not_missing(self):
        with self.isolated_workspace() as (_root, work, _game, _manifest):
            incident_path = work / "incident-registry"
            incident_path.mkdir()
            with patch.object(cleanup, "_prospective_epoch_incident_path", return_value=incident_path):
                identity = cleanup._incident_identity()
            self.assertEqual("INVALID", identity["status"])
            self.assertEqual("incident_not_regular_file", identity["error"])

    def test_explicit_owner_reset_rolls_back_to_absent_manifest_on_verification_failure(self):
        with self.isolated_workspace() as (_root, work, _game, manifest):
            git_guard = patch.object(
                cleanup,
                "_git_repository_state",
                return_value={"head": "test-sha", "dirty": False, "error": ""},
            )
            missing_incident = patch.object(
                cleanup,
                "_incident_identity",
                return_value={"scope_id": cleanup.INCIDENT_SCOPE_ID, "path": str(cleanup._prospective_epoch_incident_path()), "status": "MISSING"},
            )
            failure = {"status": "PROVEN_BLOCKED", "ok": False, "reasons": ["injected_reset_verification_failure"]}
            with git_guard, missing_incident, patch.object(cleanup, "verify_prospective_epoch", return_value=failure):
                result = cleanup.activate_prospective_epoch(
                    dry_run=False, epoch_id="epoch-reset-rollback", source_sha="test-sha",
                    owner_reset_authorization="Owner authorized isolated reset rollback test.",
                )
            self.assertFalse(result["ok"])
            self.assertIn("injected_reset_verification_failure", result["reasons"])
            self.assertFalse(manifest.exists())
            self.assertFalse((work / "artifact-registry-epochs" / "epoch-reset-rollback").exists())

    def test_prospective_epoch_apply_is_no_delete_unknown_preserving_and_idempotent(self):
        with self.isolated_workspace() as (_root, work, _game, manifest):
            artifact = work / "known"
            artifact.mkdir()
            self._register(artifact, lifecycle="RETAINED")
            unknown = work / "unproven"
            unknown.write_text("keep", encoding="utf-8")
            before_paths = {str(path) for path in work.rglob("*")}
            git_guard, incident_guard = self._epoch_guards()
            with git_guard, incident_guard:
                result = cleanup.activate_prospective_epoch(dry_run=False, epoch_id="epoch-apply", source_sha="test-sha")
            self.assertTrue(result["ok"])
            self.assertEqual("PASS", result["status"])
            self.assertEqual([], result["deletions"])
            self.assertTrue(unknown.is_file())
            self.assertTrue(before_paths.issubset({str(path) for path in work.rglob("*")}))
            document = json.loads(manifest.read_text(encoding="utf-8"))
            epoch = document["prospective_epoch"]
            self.assertEqual("epoch-apply", epoch["epoch_id"])
            self.assertEqual("NOT_RECOVERABLE/UNVERIFIABLE", epoch["historical_hygiene"])
            self.assertGreater(result["counts"].get("UNKNOWN", 0), 0)
            rollback = Path(epoch["rollback"]["path"])
            self.assertEqual(result["rollback"]["sha256"], cleanup._sha256_file(rollback))
            with git_guard, incident_guard:
                second = cleanup.activate_prospective_epoch(dry_run=False, epoch_id="epoch-apply", source_sha="test-sha")
            self.assertTrue(second["ok"])
            self.assertTrue(second["idempotent"])

    def test_prospective_epoch_refuses_dirty_writer_incomplete_and_conflicting_state(self):
        with self.isolated_workspace() as (_root, work, _game, manifest):
            artifact = work / "known"
            artifact.mkdir()
            self._register(artifact, lifecycle="RETAINED")
            incident_guard = patch.object(
                cleanup,
                "_incident_identity",
                return_value={"scope_id": cleanup.INCIDENT_SCOPE_ID, "status": "PASS", "sha256": cleanup.INCIDENT_REGISTRY_SHA256, "artifact_count": 6},
            )
            with incident_guard, patch.object(cleanup, "_git_repository_state", return_value={"head": "other", "dirty": True, "error": ""}):
                blocked = cleanup.activate_prospective_epoch(dry_run=True, epoch_id="epoch-blocked", source_sha="test-sha")
            self.assertFalse(blocked["ok"])
            self.assertIn("working_tree_dirty", blocked["reasons"])
            with incident_guard, patch.object(cleanup, "_git_repository_state", return_value={"head": "test-sha", "dirty": False, "error": ""}):
                limited = cleanup.activate_prospective_epoch(dry_run=True, epoch_id="epoch-limited", source_sha="test-sha", max_items=1)
            self.assertFalse(limited["ok"])
            self.assertIn("current_inventory_incomplete_or_budget_limited", limited["reasons"])
            (work / ".artifact-registry-epoch.writer.lock").write_text("active", encoding="utf-8")
            try:
                with incident_guard, patch.object(cleanup, "_git_repository_state", return_value={"head": "test-sha", "dirty": False, "error": ""}):
                    writer = cleanup.activate_prospective_epoch(dry_run=True, epoch_id="epoch-writer", source_sha="test-sha")
                self.assertFalse(writer["ok"])
                self.assertIn("registry_writer_active", writer["reasons"])
            finally:
                (work / ".artifact-registry-epoch.writer.lock").unlink()

    def test_prospective_epoch_verify_refuses_rollback_hash_mismatch_and_conflict(self):
        with self.isolated_workspace() as (_root, work, _game, manifest):
            artifact = work / "known"
            artifact.mkdir()
            self._register(artifact, lifecycle="RETAINED")
            git_guard, incident_guard = self._epoch_guards()
            with git_guard, incident_guard:
                applied = cleanup.activate_prospective_epoch(dry_run=False, epoch_id="epoch-hash", source_sha="test-sha")
            self.assertTrue(applied["ok"])
            rollback = Path(applied["rollback"]["path"])
            rollback.write_text("tampered", encoding="utf-8")
            with incident_guard:
                verified = cleanup.verify_prospective_epoch()
            self.assertFalse(verified["ok"])
            self.assertIn("rollback_snapshot_hash_mismatch", verified["reasons"])
            with git_guard, incident_guard:
                conflict = cleanup.activate_prospective_epoch(dry_run=True, epoch_id="epoch-other", source_sha="test-sha")
            self.assertFalse(conflict["ok"])
            self.assertIn("conflicting_active_epoch", conflict["reasons"])

    def test_prospective_epoch_rolls_back_after_verification_failure(self):
        with self.isolated_workspace() as (_root, work, _game, manifest):
            artifact = work / "known"
            artifact.mkdir()
            (artifact / "payload.txt").write_text("keep", encoding="utf-8")
            self._register(artifact, lifecycle="RETAINED")
            before_manifest = manifest.read_bytes()
            before_paths = {
                str(path.relative_to(work)): path.read_bytes()
                for path in work.rglob("*")
                if path.is_file()
            }
            git_guard, incident_guard = self._epoch_guards()
            failed_verification = {"status": "PROVEN_BLOCKED", "ok": False, "reasons": ["injected_verification_failure"]}
            with git_guard, incident_guard, patch.object(
                cleanup, "verify_prospective_epoch", return_value=failed_verification
            ):
                result = cleanup.activate_prospective_epoch(
                    dry_run=False, epoch_id="epoch-rollback", source_sha="test-sha"
                )
            self.assertFalse(result["ok"])
            self.assertIn("injected_verification_failure", result["reasons"])
            self.assertEqual(before_manifest, manifest.read_bytes())
            self.assertEqual(
                before_paths,
                {
                    str(path.relative_to(work)): path.read_bytes()
                    for path in work.rglob("*")
                    if path.is_file()
                },
            )
            self.assertFalse((work / "artifact-registry-epochs" / "epoch-rollback").exists())
            self.assertNotIn("prospective_epoch", json.loads(manifest.read_text(encoding="utf-8")))

    def test_prospective_epoch_blocks_interrupted_pending_scope(self):
        with self.isolated_workspace() as (_root, work, _game, _manifest):
            scope = work / "artifact-registry-epochs" / "epoch-pending"
            scope.mkdir(parents=True)
            (scope / ".pending.json").write_text('{"state":"PENDING"}', encoding="utf-8")
            git_guard, incident_guard = self._epoch_guards()
            with git_guard, incident_guard:
                result = cleanup.activate_prospective_epoch(
                    dry_run=True, epoch_id="epoch-next", source_sha="test-sha"
                )
            self.assertFalse(result["ok"])
            self.assertIn("unregistered_epoch_scope:epoch-pending", result["reasons"])

    def test_unregistered_root_is_unknown_and_not_deleted(self):
        with self.isolated_workspace() as (_root, work, game, _manifest):
            unknown = work / "unregistered-root"
            unknown.mkdir()
            (unknown / "data.bin").write_bytes(b"unknown")

            result = cleanup.reconcile_registry(persist=False)

            item = next(item for item in result["unknown"] if item["relative_path"] == "unregistered-root")
            self.assertEqual("UNKNOWN", item["lifecycle"])
            self.assertTrue(game.is_dir())
            self.assertTrue(unknown.is_dir())

    def test_registration_requires_owner_purpose_and_lifecycle(self):
        with self.isolated_workspace() as (_root, work, _game, manifest):
            artifact = work / "registered"
            artifact.mkdir()
            self._register(artifact, lifecycle="RETAINED")
            entry = json.loads(manifest.read_text(encoding="utf-8"))["artifacts"][0]
            self.assertEqual("test_cleanup_work_artifacts", entry["owner"])
            self.assertEqual("focused lifecycle test", entry["purpose"])
            self.assertEqual("RETAINED", entry["lifecycle"])
            self.assertTrue(entry["scope_id"])
            self.assertTrue(entry["run_id"])
            self.assertTrue(entry["provenance"]["registered_by"])

    def test_registration_rejects_missing_metadata_and_id_path_reuse(self):
        with self.isolated_workspace() as (_root, work, _game, _manifest):
            first = work / "first"
            second = work / "second"
            first.mkdir()
            second.mkdir()
            with self.assertRaises(ValueError):
                paths.register_artifact(
                    artifact_id="bad-metadata",
                    path=first,
                    kind="fixture",
                    created_by="test",
                    owner="",
                    purpose="",
                    lifecycle="RETAINED",
                )
            self._register(first, lifecycle="RETAINED")
            with self.assertRaises(ValueError):
                paths.register_artifact(
                    artifact_id=f"test:{first.name}",
                    path=second,
                    kind="fixture",
                    created_by="test",
                    owner="test",
                    purpose="duplicate path guard",
                    lifecycle="RETAINED",
                )

    def test_pass_cleanup_deletes_disposable_and_marks_missing(self):
        with self.isolated_workspace() as (_root, work, _game, manifest):
            artifact = work / "pass-output"
            artifact.mkdir()
            (artifact / "file.txt").write_text("temporary", encoding="utf-8")

            report = cleanup.cleanup_after_test([artifact], reason="pass-test", outcome="PASS")

            self.assertTrue(report["ok"])
            self.assertFalse(artifact.exists())
            entry = next(item for item in json.loads(manifest.read_text(encoding="utf-8"))["artifacts"] if item["id"].endswith("pass-output"))
            self.assertEqual("MISSING", entry["lifecycle"])
            self.assertEqual("pass-test", entry["deletion_provenance"]["reason"])
            self.assertEqual(str(artifact), entry["deletion_provenance"]["path"])

    def test_pass_cleanup_marks_registered_descendants_missing(self):
        with self.isolated_workspace() as (_root, work, _game, manifest):
            artifact = work / "nested-pass-output"
            child = artifact / "child"
            child.mkdir(parents=True)
            self._register(artifact)
            self._register(child)

            report = cleanup.cleanup_after_test([artifact], reason="nested-pass-test", outcome="PASS")

            self.assertTrue(report["ok"])
            self.assertFalse(artifact.exists())
            records = json.loads(manifest.read_text(encoding="utf-8"))["artifacts"]
            descendants = [item for item in records if str(item["path"]).startswith(str(artifact))]
            self.assertEqual({"MISSING"}, {item["lifecycle"] for item in descendants})
            self.assertTrue(all(item.get("deletion_provenance") for item in descendants))

    def test_fail_cleanup_deletes_registered_payload_but_preserves_test_outcome(self):
        with self.isolated_workspace() as (_root, work, _game, manifest):
            artifact = work / "failed-output"
            artifact.mkdir()
            (artifact / "failure.log").write_text("evidence", encoding="utf-8")

            report = cleanup.cleanup_after_test([artifact], reason="fail-test", outcome="FAIL")

            self.assertTrue(report["ok"])
            self.assertFalse(artifact.exists())
            self.assertEqual("FAIL", report["terminal_status"])
            self.assertEqual("PASS", report["cleanup_status"])
            entry = next(item for item in json.loads(manifest.read_text(encoding="utf-8"))["artifacts"] if item["id"].endswith("failed-output"))
            self.assertEqual("MISSING", entry["lifecycle"])

    def test_cleanup_after_test_attempts_disposal_for_every_known_terminal_outcome(self):
        for outcome in ("PASS", "FAIL", "TIMEOUT", "START_ERROR", "CANCELLED"):
            with self.subTest(outcome=outcome), self.isolated_workspace() as (_root, work, _game, manifest):
                artifact = work / f"terminal-{outcome.lower()}"
                artifact.mkdir()
                (artifact / "payload.bin").write_bytes(b"payload")
                report = cleanup.cleanup_after_test([artifact], reason=f"test-{outcome}", outcome=outcome)
                self.assertEqual(outcome, report["outcome"])
                self.assertEqual(outcome, report["terminal_status"])
                self.assertTrue(report["ok"], report)
                self.assertFalse(artifact.exists())
                self.assertTrue(any(item.get("path") == str(artifact) for item in report["deleted"]))
                entry = next(
                    item for item in json.loads(manifest.read_text(encoding="utf-8"))["artifacts"]
                    if item.get("path") == str(artifact)
                )
                self.assertEqual("MISSING", entry["lifecycle"])

    def test_post_test_cleanup_does_not_claim_missing_race_as_its_deletion(self):
        with self.isolated_workspace() as (_root, work, _game, manifest):
            artifact = work / "race-output"
            artifact.mkdir()
            def another_actor_removes(path, _deleted, **_kwargs):
                shutil.rmtree(path)
                return False

            with patch.object(cleanup, "safe_rmtree", side_effect=another_actor_removes):
                report = cleanup.cleanup_after_test([artifact], reason="race-test", outcome="FAIL")
            self.assertFalse(report["ok"])
            self.assertFalse(artifact.exists())
            self.assertTrue(any(item["reason"] == "disposable_deletion_not_proven" for item in report["errors"]))
            entry = next(item for item in json.loads(manifest.read_text(encoding="utf-8"))["artifacts"] if item.get("path") == str(artifact))
            self.assertEqual("DISPOSABLE", entry["lifecycle"])
            self.assertNotIn("deletion_provenance", entry)

    def test_blocked_game_test_disposes_registered_copy_without_claiming_pass(self):
        with self.isolated_workspace() as (_root, work, _game, manifest):
            game = work / "blocked-game-copy"
            game.mkdir()
            (game / "game.exe").write_bytes(b"test game")
            paths.register_artifact(
                artifact_id="blocked-game-copy-owner",
                path=game,
                kind="test_game_copy",
                created_by="test_cleanup_work_artifacts",
                owner="test_cleanup_work_artifacts",
                purpose="temporary game copy for a blocked test",
                lifecycle="DISPOSABLE",
            )

            report = cleanup.cleanup_after_test(
                [game],
                reason="blocked-game-copy-disposal",
                outcome="PROVEN_BLOCKED",
                disposable_paths=[game],
            )

            self.assertEqual("PROVEN_BLOCKED", report["outcome"])
            self.assertTrue(report["ok"])
            self.assertFalse(game.exists())
            entries = [
                item for item in json.loads(manifest.read_text(encoding="utf-8"))["artifacts"]
                if str(item["path"]).startswith(str(game))
            ]
            self.assertTrue(entries)
            self.assertEqual({"MISSING"}, {item["lifecycle"] for item in entries})

    def test_unregistered_or_non_game_path_cannot_use_always_dispose(self):
        with self.isolated_workspace() as (_root, work, _game, _manifest):
            artifact = work / "not-a-game-copy"
            artifact.mkdir()
            self._register(artifact)

            report = cleanup.cleanup_after_test(
                [artifact],
                reason="reject-forced-disposal",
                outcome="FAIL",
                disposable_paths=[artifact],
            )

            self.assertFalse(report["ok"])
            self.assertTrue(artifact.is_dir())
            self.assertIn("game_copy_not_registered_disposable", {item["reason"] for item in report["errors"]})

    def test_default_cleanup_outcome_is_unknown_and_never_deletes(self):
        with self.isolated_workspace() as (_root, work, _game, manifest):
            artifact = work / "unknown-output"
            artifact.mkdir()
            report = cleanup.cleanup_after_test([artifact], reason="unknown-test")
            self.assertEqual("UNKNOWN", report["outcome"])
            self.assertTrue(artifact.is_dir())
            entry = next(item for item in json.loads(manifest.read_text(encoding="utf-8"))["artifacts"] if item["id"].endswith("unknown-output"))
            self.assertEqual("UNKNOWN", entry["lifecycle"])

    def test_scoped_pass_deletes_registered_disposable_nested_output(self):
        with self.isolated_workspace() as (_root, work, _game, _manifest):
            scope_id = paths.new_scope_id("nested-pass")
            output = work / "nested-pass-output"
            paths.register_artifact(
                artifact_id="nested-pass-output",
                path=output,
                kind="test_output",
                created_by="test_cleanup_work_artifacts",
                owner="test_cleanup_work_artifacts",
                purpose="registered disposable nested output",
                lifecycle="DISPOSABLE",
                scope_id=scope_id,
                run_id=scope_id,
            )
            before = cleanup.snapshot_tree(work)
            output.mkdir()
            (output / "child.txt").write_text("child", encoding="utf-8")
            report = cleanup.finalize_scope(
                scope_id=scope_id,
                run_id=scope_id,
                scope_root=work,
                before=before,
                outcome="PASS",
            )
            self.assertTrue(report["ok"], report)
            self.assertFalse(output.exists())
            self.assertTrue(any(item["relative_path"] == "nested-pass-output/child.txt" for item in report["created"]))

    def test_scoped_inventory_limit_applies_to_each_complete_snapshot(self):
        with self.isolated_workspace() as (_root, work, _game, _manifest):
            baseline = work / "baseline"
            baseline.mkdir()
            for index in range(80):
                (baseline / f"{index:03d}.txt").write_text("baseline", encoding="utf-8")

            scope_id = paths.new_scope_id("separate-snapshot-budgets")
            report = cleanup.finalize_scope(
                scope_id=scope_id,
                run_id=scope_id,
                scope_root=work,
                before=cleanup.snapshot_tree(work, include_hashes=False),
                outcome="PASS",
                max_items=100,
            )

            self.assertTrue(report["ok"], report)
            self.assertTrue(report["run_inventory"]["complete"])
            self.assertTrue(report["after_inventory"]["complete"])
            self.assertLess(report["run_inventory"]["inventory"]["items_seen"], 100)
            self.assertLess(report["after_inventory"]["inventory"]["items_seen"], 100)
            self.assertTrue(report["run_inventory"]["items_omitted"])
            self.assertNotIn("items", report["run_inventory"])
            self.assertEqual(
                report["run_inventory"]["items_count"],
                report["inventory"]["reconcile"]["items_count"],
            )

    def test_scoped_cleanup_preserves_retained_descendant_after_reconciliation(self):
        with self.isolated_workspace() as (_root, work, _game, _manifest):
            scope_id = paths.new_scope_id("retained-descendant")
            parent = work / "nuget_packages"
            child = parent / "package.bin"
            parent.mkdir()
            child.write_bytes(b"retained package")
            for artifact_id, path, lifecycle in (
                ("disposable-cache-parent", parent, "DISPOSABLE"),
                ("retained-cache-child", child, "RETAINED"),
            ):
                paths.register_artifact(
                    artifact_id=artifact_id,
                    path=path,
                    kind="test_output",
                    created_by="test_cleanup_work_artifacts",
                    owner="test_cleanup_work_artifacts",
                    purpose="parent and retained descendant lifecycle regression",
                    lifecycle=lifecycle,
                    scope_id=scope_id,
                    run_id=scope_id,
                )
            report = cleanup.finalize_scope(
                scope_id=scope_id,
                run_id=scope_id,
                scope_root=work,
                before=cleanup.snapshot_tree(work),
                outcome="PASS",
            )
            after = cleanup.reconcile_registry()
            self.assertTrue(child.is_file())
            self.assertFalse(report["ok"])
            self.assertEqual("REVIEW_REQUIRED", report["cleanup_status"])
            self.assertFalse(any(item["path"] == str(parent) and item.get("deleted") for item in report["deleted"]))
            self.assertTrue(any(item.get("reason") == "registered_non_disposable_descendant" for item in report["deleted"]))
            self.assertEqual([], [item for item in after["entries"] if item["scope_id"] == scope_id and item["lifecycle"] == "MISSING"])

    def test_scoped_pass_rejects_unregistered_child_under_retained_parent(self):
        with self.isolated_workspace() as (_root, work, _game, _manifest):
            scope_id = paths.new_scope_id("nested-unknown")
            parent = work / "retained-parent"
            parent.mkdir()
            paths.register_artifact(
                artifact_id="retained-parent",
                path=parent,
                kind="retained_fixture",
                created_by="test_cleanup_work_artifacts",
                owner="test_cleanup_work_artifacts",
                purpose="retained parent must not absorb new children",
                lifecycle="RETAINED",
                scope_id=scope_id,
                run_id=scope_id,
            )
            before = cleanup.snapshot_tree(work)
            child = parent / "unregistered.txt"
            child.write_text("unknown", encoding="utf-8")
            report = cleanup.finalize_scope(
                scope_id=scope_id,
                run_id=scope_id,
                scope_root=work,
                before=before,
                outcome="PASS",
            )
            self.assertFalse(report["ok"])
            self.assertTrue(any(item["path"].endswith("retained-parent\\unregistered.txt") for item in report["unknown"]))
            self.assertTrue(child.is_file())

    def test_snapshot_delta_ignores_one_sided_optional_hash(self):
        metadata = {"kind": "file", "bytes": 6, "mtime_ns": 123}
        before = {"items": {"existing.txt": {**metadata, "sha256": "before"}}}
        after = {"items": {"existing.txt": metadata}}
        self.assertEqual(([], [], []), cleanup._snapshot_delta(before, after))
        changed = {"items": {"existing.txt": {**metadata, "sha256": "after"}}}
        self.assertEqual(1, len(cleanup._snapshot_delta(before, changed)[1]))

    def test_scoped_modified_existing_artifact_is_reported(self):
        with self.isolated_workspace() as (_root, work, _game, _manifest):
            scope_id = paths.new_scope_id("modified")
            artifact = work / "existing-retained"
            artifact.mkdir()
            file_path = artifact / "stable.txt"
            file_path.write_text("before", encoding="utf-8")
            before = cleanup.snapshot_tree(work)
            file_path.write_text("modified", encoding="utf-8")
            report = cleanup.finalize_scope(
                scope_id=scope_id,
                run_id=scope_id,
                scope_root=work,
                before=before,
                outcome="PASS",
            )
            self.assertFalse(report["ok"])
            self.assertTrue(any(item["path"].endswith("existing-retained\\stable.txt") for item in report["modified"]))

    def test_terminal_nonpass_outcomes_delete_registered_output_after_scope_finalization(self):
        for outcome in ("FAIL", "TIMEOUT", "START_ERROR", "CANCELLED"):
            with self.subTest(outcome=outcome), self.isolated_workspace() as (_root, work, _game, _manifest):
                scope_id = paths.new_scope_id(outcome.lower())
                artifact = work / f"{outcome.lower()}-output"
                artifact.mkdir()
                paths.register_artifact(
                    artifact_id=f"{outcome.lower()}-output",
                    path=artifact,
                    kind="test_output",
                    created_by="test_cleanup_work_artifacts",
                    owner="test_cleanup_work_artifacts",
                    purpose=f"dispose payload after {outcome}",
                    lifecycle="DISPOSABLE",
                    scope_id=scope_id,
                    run_id=scope_id,
                )
                report = cleanup.finalize_scope(
                    scope_id=scope_id,
                    run_id=scope_id,
                    scope_root=work,
                    before=cleanup.snapshot_tree(work),
                    outcome=outcome,
                )
                self.assertEqual(outcome, report["outcome"])
                self.assertEqual(outcome, report["terminal_status"])
                self.assertTrue(report["ok"], report)
                self.assertFalse(artifact.exists())
                self.assertTrue(any(item.get("path") == str(artifact.resolve()) for item in report["deleted"]))

    def test_registered_runner_failure_deletes_disposable_artifact(self):
        with self.isolated_workspace() as (_root, work, _game, manifest):
            artifact = work / "runner-failure-output"
            artifact.mkdir()
            (artifact / "failure.log").write_text("debug", encoding="utf-8")
            self._register(artifact)

            report = cleanup.cleanup_work(dry_run=False, registered_only=True, outcome="FAIL")

            self.assertTrue(report["ok"], report)
            self.assertFalse(artifact.exists())
            entry = next(item for item in json.loads(manifest.read_text(encoding="utf-8"))["artifacts"] if item["id"] == "test:runner-failure-output")
            self.assertEqual("MISSING", entry["lifecycle"])
            self.assertEqual("FAIL", report["terminal_status"])

    def test_locked_disposable_fails_closed_without_killing_process(self):
        with self.isolated_workspace() as (_root, work, _game, _manifest):
            artifact = work / "locked-output"
            artifact.mkdir()
            with patch.object(cleanup, "processes_using", return_value=[{"pid": 123}]):
                report = cleanup.cleanup_after_test([artifact], reason="locked-test", outcome="PASS")

            self.assertFalse(report["ok"])
            self.assertTrue(artifact.is_dir())
            self.assertEqual("locked_by_process", report["deleted"][0]["reason"])
            self.assertEqual([report["deleted"][0]], report["locked"])
            entry = next(item for item in json.loads(_manifest.read_text(encoding="utf-8"))["artifacts"] if item["path"] == str(artifact.resolve()))
            self.assertEqual("DISPOSABLE", entry["lifecycle"])

    def test_cleanup_report_has_before_after_deleted_retained_unknown(self):
        with self.isolated_workspace() as (_root, work, _game, _manifest):
            artifact = work / "report-output"
            artifact.mkdir()
            (artifact / "payload").write_bytes(b"temporary")
            self._register(artifact)
            report = cleanup.cleanup_work(dry_run=False, registered_only=False, outcome="PASS")

            self.assertTrue(report["ok"], report)
            self.assertIn("work_total_gb", report["before"])
            self.assertIn("work_total_gb", report["after"])
            self.assertTrue(any(item.get("deleted") for item in report["deleted"]))
            self.assertIn("retained", report)
            self.assertIn("unknown", report)
            self.assertIn("protected", report)
            self.assertTrue(cleanup.CLEANUP_MANIFEST.is_file())

    def test_cleanup_report_proves_disposable_and_duplicate_bytes_do_not_grow(self):
        with self.isolated_workspace() as (_root, work, game, _manifest):
            disposable = work / "metrics-disposable"
            retained = work / "metrics-retained"
            disposable.mkdir()
            retained.mkdir()
            payload = b"same exact payload\n"
            (disposable / "copy-a.bin").write_bytes(payload)
            (disposable / "copy-b.bin").write_bytes(payload)
            (retained / "baseline.bin").write_bytes(payload)
            (game / "protected.marker").write_text("must remain", encoding="utf-8")
            self._register(disposable, lifecycle="DISPOSABLE")
            self._register(retained, lifecycle="RETAINED")

            report = cleanup.cleanup_work(
                dry_run=False,
                registered_only=True,
                outcome="PASS",
            )

            self.assertTrue(report["ok"], report)
            before = report["before_metrics"]
            after = report["after_metrics"]
            self.assertGreater(before["disposable_bytes"], 0)
            self.assertEqual(0, after["disposable_bytes"])
            self.assertLessEqual(after["disposable_bytes"], before["disposable_bytes"])
            self.assertGreater(before["duplicate_measurement"]["duplicate_bytes"], 0)
            self.assertLessEqual(
                after["duplicate_measurement"]["duplicate_bytes"],
                before["duplicate_measurement"]["duplicate_bytes"],
            )
            self.assertGreaterEqual(after["registry_counts"]["MISSING"], 1)
            self.assertTrue((game / "protected.marker").is_file())
            self.assertIn("lifecycle_metrics", report)
            json.dumps(report)

    def test_artifact_scope_creates_then_cleans_disposable_run(self):
        with self.isolated_workspace() as (_root, work, _game, manifest):
            artifact = work / "scoped-output"
            with paths.artifact_scope(
                artifact,
                artifact_id="scope-test",
                kind="integration_output",
                owner="test_cleanup_work_artifacts",
                purpose="disposable integration lifecycle",
            ) as scoped:
                scoped.mkdir()
                (scoped / "generated.txt").write_text("generated", encoding="utf-8")

            self.assertFalse(artifact.exists())
            ids = {item["id"] for item in json.loads(manifest.read_text(encoding="utf-8"))["artifacts"]}
            self.assertIn("scope-test", ids)

    def test_artifact_scope_cleans_fail_timeout_and_cancelled_bodies(self):
        cases = (
            ("FAIL", RuntimeError("planned failure")),
            ("TIMEOUT", subprocess.TimeoutExpired(["probe"], timeout=1)),
            ("CANCELLED", KeyboardInterrupt()),
        )
        with self.isolated_workspace() as (_root, work, _game, manifest):
            for outcome, error in cases:
                with self.subTest(outcome=outcome):
                    artifact = work / f"scope-{outcome.lower()}"
                    artifact_id = f"scope-{outcome.lower()}"
                    with self.assertRaises(type(error)) as raised:
                        with paths.artifact_scope(
                            artifact,
                            artifact_id=artifact_id,
                            kind="integration_output",
                            owner="test_cleanup_work_artifacts",
                            purpose="exception cleanup lifecycle",
                        ) as scoped:
                            scoped.mkdir()
                            (scoped / "payload.bin").write_bytes(b"temporary payload")
                            raise error

                    self.assertIs(raised.exception, error)
                    self.assertFalse(artifact.exists())
                    entry = next(
                        item for item in json.loads(manifest.read_text(encoding="utf-8"))["artifacts"]
                        if item["id"] == artifact_id
                    )
                    self.assertEqual("MISSING", entry["lifecycle"])
                    history = [
                        json.loads(line)
                        for line in (work / "cleanup_post_test.jsonl").read_text(encoding="utf-8").splitlines()
                    ]
                    self.assertEqual(outcome, history[-1]["outcome"])
                    self.assertTrue(history[-1]["ok"], history[-1])

    def test_artifact_scope_raises_when_exception_cleanup_is_not_proven(self):
        with self.isolated_workspace() as (_root, work, _game, _manifest):
            artifact = work / "scope-cleanup-failure"
            with patch.object(
                cleanup,
                "cleanup_after_test",
                return_value={"ok": False, "cleanup_status": "REVIEW_REQUIRED"},
            ) as cleanup_after:
                with self.assertRaisesRegex(RuntimeError, "artifact cleanup failed") as raised:
                    with paths.artifact_scope(
                        artifact,
                        artifact_id="scope-cleanup-failure",
                        kind="integration_output",
                        owner="test_cleanup_work_artifacts",
                        purpose="cleanup failure must surface",
                    ) as scoped:
                        scoped.mkdir()
                        raise RuntimeError("original test failure")

            self.assertIsInstance(raised.exception.__cause__, RuntimeError)
            self.assertEqual("FAIL", cleanup_after.call_args.kwargs["outcome"])
            self.assertTrue(artifact.exists())

    def test_canonical_wrapper_cleans_registered_disposable_integration_output(self):
        with self.canonical_runner_harness() as (harness, runner_path, work):
            artifact = work / f"run_with_cleanup_probe_{__import__('os').getpid()}"
            retained_root = work / "retained-build"
            report_path = work / "evidence" / "runner_report.json"
            stdout_log = work / "evidence" / "child.stdout.log"
            stderr_log = work / "evidence" / "child.stderr.log"
            child_code = (
                "import sys; from pathlib import Path; "
                "sys.path.insert(0, 'tests/lib'); "
                "from work_paths import register_artifact; "
                f"p=Path({str(artifact)!r}); p.mkdir(parents=True, exist_ok=True); "
                "(p / 'generated.txt').write_text('generated', encoding='utf-8'); "
                f"r=Path({str(retained_root)!r}) / 'nested'; r.mkdir(parents=True, exist_ok=True); "
                "(r / 'payload.bin').write_bytes(b'payload'); "
                "print('stdout-primary-evidence'); print('stderr-primary-evidence', file=sys.stderr); "
                f"register_artifact(artifact_id='canonical-wrapper-probe-{__import__('os').getpid()}', path=p, kind='integration_output', "
                "created_by='test_canonical_wrapper', owner='test_canonical_wrapper', "
                "purpose='wrapper integration', lifecycle='DISPOSABLE')"
            )
            result = subprocess.run(
                [
                    sys.executable,
                    str(runner_path),
                    "--report",
                    str(report_path),
                    "--stdout-log",
                    str(stdout_log),
                    "--stderr-log",
                    str(stderr_log),
                    "--retained-root",
                    str(retained_root),
                    "--",
                    sys.executable,
                    "-c",
                    child_code,
                ],
                cwd=harness,
                capture_output=True,
                text=True,
                timeout=60,
            )
            payload = json.loads(result.stdout)
            cleanup_report = payload.get("cleanup") or {}
            self.assertEqual(
                0,
                result.returncode,
                json.dumps({
                    "outcome": payload.get("outcome"),
                    "child_exit_code": payload.get("child_exit_code"),
                    "cleanup_status": cleanup_report.get("cleanup_status"),
                    "blocked": cleanup_report.get("blocked"),
                    "unknown": cleanup_report.get("unknown"),
                    "locked": cleanup_report.get("locked"),
                    "errors": cleanup_report.get("errors"),
                    "skipped": [item for item in cleanup_report.get("deleted", []) if item.get("skipped")],
                    "project_size": cleanup_report.get("project_size"),
                }, ensure_ascii=False, sort_keys=True),
            )
            self.assertFalse(artifact.exists())
            self.assertFalse(stdout_log.exists())
            self.assertFalse(stderr_log.exists())
            self.assertEqual(b"payload", (retained_root / "nested" / "payload.bin").read_bytes())
            self.assertTrue(report_path.is_file())
            self.assertEqual(payload, json.loads(report_path.read_text(encoding="utf-8")))
            self.assertEqual("PASS", payload["status"])
            self.assertEqual("NOT_UNITTEST", payload["test_summary"]["status"])
            self.assertEqual("PASS", payload["cleanup"]["cleanup_status"])
            self.assertIn("stdout-primary-evidence", payload["stdout_excerpt"])
            self.assertIn("stderr-primary-evidence", payload["stderr_excerpt"])
            markdown = payload["markdown_excerpt"]
            self.assertIn("stdout-primary-evidence", markdown)
            self.assertIn("stderr-primary-evidence", markdown)
            self.assertIn("Test summary", markdown)
            self.assertEqual([], payload["cleanup"]["unknown"])
            self.assertEqual([], payload["cleanup"]["unexpected_missing"])
            self.assertGreaterEqual(len(payload["cleanup"]["expected_missing"]), 1)
            before = payload["cleanup"]["before_metrics"]
            after = payload["cleanup"]["after_metrics"]
            self.assertEqual(0, after["unexpected_missing_count"])
            self.assertEqual(
                {"UNKNOWN": 0, "MISSING": 0, "STALE": 0},
                after["unresolved_registry_counts"],
            )
            self.assertLessEqual(after["disposable_bytes"], before["disposable_bytes"])

    def test_runner_terminal_reports_cover_outcomes_and_keep_cleanup_separate(self):
        class SimulatedProcess:
            next_outcome = "PASS"
            next_pid = 41000

            def __init__(self, _command, **kwargs):
                self.pid = type(self).next_pid
                type(self).next_pid += 1
                self.returncode = None
                self.stdout = kwargs.get("stdout")
                self.stderr = kwargs.get("stderr")
                if self.stdout is not None:
                    if self.next_outcome == "PASS":
                        payload = b"Ran 1 tests in 0.001s\n\nOK\nstdout-evidence\n"
                    elif self.next_outcome == "FAIL":
                        payload = b"Ran 1 tests in 0.001s\n\nFAILED (failures=1)\nstdout-evidence\n"
                    else:
                        payload = b"stdout-evidence\n"
                    self.stdout.write(payload)
                if self.stderr is not None:
                    self.stderr.write(b"stderr-evidence\n")

            def wait(self, timeout=None):
                if self.next_outcome == "TIMEOUT":
                    raise subprocess.TimeoutExpired("simulated", timeout)
                if self.next_outcome == "CANCELLED":
                    raise KeyboardInterrupt
                self.returncode = 1 if self.next_outcome == "FAIL" else 0
                return self.returncode

            def poll(self):
                return self.returncode

        cases = {
            "PASS": (0, "PASS"),
            "FAIL": (1, "FAIL"),
            "TIMEOUT": (0, "NOT_UNITTEST"),
            "START_ERROR": (None, "NOT_UNITTEST"),
            "CANCELLED": (0, "NOT_UNITTEST"),
        }
        for outcome, (child_exit, expected_summary) in cases.items():
            with self.subTest(outcome=outcome), self.isolated_workspace() as (_root, work, _game, _manifest):
                shutil.rmtree(_game, ignore_errors=False)
                _manifest.unlink(missing_ok=True)
                with patch.object(runner, "WORK_ROOT", work), patch.object(runner, "_source_sha", return_value="focused-test-sha"):
                    if outcome == "START_ERROR":
                        process_patch = patch.object(runner.subprocess, "Popen", side_effect=OSError("fixture start error"))
                    else:
                        SimulatedProcess.next_outcome = outcome
                        process_patch = patch.object(runner.subprocess, "Popen", side_effect=SimulatedProcess)
                    stop_patch = patch.object(
                        runner, "_request_stop",
                        side_effect=lambda proc: (setattr(proc, "returncode", 0) or True),
                    )
                    with process_patch, stop_patch, contextlib.redirect_stdout(io.StringIO()) as captured:
                        return_code = runner.run(
                            ["python", "-c", "simulated"],
                            timeout=0.01,
                            report_path=work / f"{outcome.lower()}.json",
                            cleanup_timeout=5,
                        )
                    payload = json.loads(captured.getvalue())
                    self.assertEqual(outcome, payload["outcome"])
                    self.assertEqual(child_exit, payload["child_exit_code"])
                    self.assertEqual(expected_summary, payload["test_summary"]["status"])
                    self.assertEqual("PASS", payload["cleanup"]["cleanup_status"])
                    self.assertEqual(0 if outcome == "PASS" else 1, return_code)
                    markdown = payload["markdown_excerpt"]
                    for evidence in ("Command:", "Child exit code:", "Test summary", outcome):
                        self.assertIn(evidence, markdown)
                    self.assertIn("fixture start error", markdown) if outcome == "START_ERROR" else None
                    if outcome != "START_ERROR":
                        self.assertIn("stdout-evidence", payload["stdout_excerpt"])
                        self.assertIn("stderr-evidence", payload["stderr_excerpt"])
                        self.assertIn("stdout-evidence", markdown)
                        self.assertIn("stderr-evidence", markdown)
                    self.assertFalse(Path(payload["primary_output"]["stdout"]["path"]).exists())
                    self.assertFalse(Path(payload["primary_output"]["stderr"]["path"]).exists())
                    self.assertFalse(work.exists(), f"terminal TEST_RUN was not disposed for {outcome}")

    def test_runner_does_not_claim_cleanup_pass_while_child_remains_alive(self):
        class StillRunning:
            pid = 41999
            returncode = None

            def __init__(self, _command, **kwargs):
                self.stdout = kwargs.get("stdout")
                self.stderr = kwargs.get("stderr")
                if self.stdout is not None:
                    self.stdout.write(b"still-running-output\n")

            def wait(self, timeout=None):
                raise subprocess.TimeoutExpired("simulated", timeout)

            def poll(self):
                return None

        with self.isolated_workspace() as (_root, work, _game, _manifest):
            with patch.object(runner, "WORK_ROOT", work), patch.object(runner, "_source_sha", return_value="focused-test-sha"), patch.object(
                runner.subprocess, "Popen", side_effect=StillRunning
            ), patch.object(runner, "_request_stop", return_value=False), contextlib.redirect_stdout(io.StringIO()) as captured:
                result_code = runner.run(
                    ["python", "-c", "long running"],
                    timeout=0.01,
                    report_path=work / "still-running.json",
                    cleanup_timeout=5,
                )
            payload = json.loads(captured.getvalue())
            self.assertEqual(1, result_code)
            self.assertEqual("RUNNING", payload["child_process_state"])
            self.assertIsNone(payload["child_exit_code"])
            self.assertEqual("REVIEW_REQUIRED", payload["cleanup"]["cleanup_status"])
            self.assertEqual("REVIEW_REQUIRED", payload["cleanup"]["status"])
            self.assertIn("child_process_still_running", {item["reason"] for item in payload["cleanup"]["errors"]})
            self.assertIn("still-running-output", Path(payload["markdown_report"]).read_text(encoding="utf-8"))
            self.assertIn("child_process_still_running", Path(payload["markdown_report"]).read_text(encoding="utf-8"))
            self.assertTrue(Path(payload["primary_output"]["stdout"]["path"]).exists())
            summary_stdout = work / "summary.stdout.txt"
            summary_stderr = work / "summary.stderr.txt"
            summary_stderr.write_text(
                "test_a (suite.Case.test_a) ... skipped 'requires fixture A'\n"
                "test_b (suite.Case.test_b) ... skipped 'requires fixture B'\n"
                "sample.py:1: ResourceWarning: stream not closed\n"
                "Ran 742 tests in 1.234s\n\nOK (skipped=7)\n",
                encoding="utf-8",
            )
            summary = runner._parse_unittest_summary(summary_stdout, summary_stderr)
            self.assertEqual(
                {"status": "PASS", "tests": 742, "failures": 0, "errors": 0, "skips": 7, "warnings": 1},
                {key: summary[key] for key in ("status", "tests", "failures", "errors", "skips", "warnings")},
            )
            self.assertEqual(
                ["requires fixture A", "requires fixture B"],
                [item["reason"] for item in summary["skip_reasons"]],
            )

    def test_runner_summary_records_bounded_failure_details(self):
        with self.isolated_workspace() as (_root, work, _game, _manifest):
            stdout = work / "failure.stdout.txt"
            stderr = work / "failure.stderr.txt"
            stderr.write_text(
                "======================================================================\n"
                "ERROR: fixture.Case.test_broken (fixture.Case.test_broken)\n"
                "----------------------------------------------------------------------\n"
                "Traceback (most recent call last):\n  ValueError: fixture detail\n"
                "======================================================================\n"
                "Ran 1 test in 0.001s\n\nFAILED (errors=1)\n",
                encoding="utf-8",
            )
            summary = runner._parse_unittest_summary(stdout, stderr)
            self.assertEqual("FAIL", summary["status"])
            self.assertEqual(1, len(summary["failure_records"]))
            self.assertEqual("ERROR", summary["failure_records"][0]["kind"])
            self.assertIn("ValueError: fixture detail", summary["failure_records"][0]["details"])
            self.assertLessEqual(len(summary["failure_records"][0]["details"]), 500)

    def test_canonical_wrapper_recleans_reused_artifact_id(self):
        with self.canonical_runner_harness() as (harness, runner_path, work):
            artifact = work / f"run_with_cleanup_reuse_{__import__('os').getpid()}"
            artifact_id = f"canonical-wrapper-reuse-{__import__('os').getpid()}"
            child_code = (
                "import sys; from pathlib import Path; "
                "sys.path.insert(0, 'tests/lib'); "
                "from work_paths import register_artifact; "
                f"p=Path({str(artifact)!r}); p.mkdir(parents=True, exist_ok=True); "
                "(p / 'generated.txt').write_text('generated', encoding='utf-8'); "
                f"register_artifact(artifact_id={artifact_id!r}, path=p, kind='integration_output', "
                "created_by='test_canonical_wrapper', owner='test_canonical_wrapper', "
                "purpose='reused wrapper integration', lifecycle='DISPOSABLE')"
            )
            for _ in range(2):
                result = subprocess.run(
                    [sys.executable, str(runner_path), "--", sys.executable, "-c", child_code],
                    cwd=harness,
                    capture_output=True,
                    text=True,
                    timeout=60,
                )
                self.assertEqual(0, result.returncode, result.stdout + result.stderr)
                self.assertFalse(artifact.exists())
                self.assertEqual("PASS", json.loads(result.stdout)["status"])

    def test_canonical_wrapper_disposes_game_copy_after_each_terminal_outcome(self):
        with self.canonical_runner_harness() as (harness, runner_path, work):
            game_copy = work / "game-copy"
            ready = harness / "fixture.ready"
            ready_runner = harness / "ready_runner.py"
            ready_runner.write_text(
                "import sys, time\n"
                "from pathlib import Path\n"
                "sys.path.insert(0, 'tests/tools')\n"
                "import run_with_cleanup as runner\n"
                "original = runner.subprocess.Popen\n"
                "def start_ready_child(command, **kwargs):\n"
                "    proc = original(command, **kwargs)\n"
                "    if len(command) > 2 and command[1] == '-c':\n"
                "        deadline = time.monotonic() + 10\n"
                "        while not Path('fixture.ready').is_file():\n"
                "            if proc.poll() is not None:\n"
                "                raise RuntimeError('fixture child exited before readiness')\n"
                "            if time.monotonic() >= deadline:\n"
                "                runner._request_stop(proc)\n"
                "                raise RuntimeError('fixture readiness deadline exceeded')\n"
                "            time.sleep(0.01)\n"
                "    return proc\n"
                "runner.subprocess.Popen = start_ready_child\n"
                "sys.exit(runner.main())\n",
                encoding="utf-8",
            )
            cases = (
                ("PASS", [], "raise SystemExit(0)", 0),
                ("FAIL", [], "raise SystemExit(7)", 1),
                ("TIMEOUT", ["--timeout-seconds", "0.1"], "import time; time.sleep(5)", 1),
            )
            for outcome, runner_args, child_end, wrapper_exit in cases:
                report_path = work / f"game_copy_{outcome.lower()}.json"
                # The TIMEOUT child deliberately sets up slower than its run
                # budget. The fixture-only launcher waits for registration before
                # returning Popen, so the real runner's timed wait starts ready.
                child_code = (
                    ("import time; time.sleep(0.2); " if outcome == "TIMEOUT" else "") +
                    "import sys; from pathlib import Path; sys.path.insert(0, 'tests/lib'); "
                    "from work_paths import E2E_GAME_COPY, register_artifact; "
                    "E2E_GAME_COPY.mkdir(parents=True, exist_ok=True); "
                    "(E2E_GAME_COPY / 'game.exe').write_bytes(b'test game'); "
                    f"register_artifact(artifact_id='e2e_game_copy', path=E2E_GAME_COPY, kind='e2e_game_copy', "
                    "created_by='canonical wrapper test', owner='work_paths', "
                    "purpose='temporary game copy', lifecycle='PROTECTED'); "
                    f"Path({str(ready)!r}).write_text('FIXTURE_READY', encoding='utf-8'); "
                    f"{child_end}"
                )
                result = subprocess.run(
                    [
                        sys.executable,
                        str(ready_runner if outcome == "TIMEOUT" else runner_path),
                        *runner_args,
                        "--report",
                        str(report_path),
                        "--",
                        sys.executable,
                        "-c",
                        child_code,
                    ],
                    cwd=harness,
                    capture_output=True,
                    text=True,
                    timeout=60,
                )
                payload = json.loads(result.stdout)
                self.assertEqual(outcome, payload["outcome"], result.stdout + result.stderr)
                self.assertEqual(wrapper_exit, result.returncode)
                self.assertEqual("EXITED", payload["child_process_state"])
                self.assertIsNotNone(payload["child_exit_code"])
                self.assertEqual("FIXTURE_READY", ready.read_text(encoding="utf-8"))
                ready.unlink()
                self.assertFalse(report_path.exists())
                self.assertFalse(game_copy.exists())
                self.assertIn("game_copy_disposal", payload["cleanup"], f"{outcome}: {payload}")
                self.assertEqual(
                    {"path": str(game_copy), "removed": True, "ok": True},
                    payload["cleanup"]["game_copy_disposal"],
                )

    def test_canonical_wrapper_timeout_reports_outcome_and_disposes_only_after_exit(self):
        with self.canonical_runner_harness() as (harness, runner_path, work):
            report_path = work / f"timeout_runner_{__import__('os').getpid()}.json"
            result = subprocess.run(
                [
                    sys.executable,
                    str(runner_path),
                    "--timeout-seconds",
                    "0.1",
                    "--report",
                    str(report_path),
                    "--",
                    sys.executable,
                    "-c",
                    "import time; time.sleep(2)",
                ],
                cwd=harness,
                capture_output=True,
                text=True,
                timeout=30,
            )
            payload = json.loads(result.stdout)
            self.assertEqual(1, result.returncode)
            self.assertEqual("TIMEOUT", payload["outcome"])
            self.assertEqual("TIMEOUT", payload["cleanup"]["outcome"])
            if payload["child_process_state"] == "RUNNING":
                self.assertTrue(report_path.is_file())
            else:
                self.assertFalse(report_path.exists())
                self.assertFalse(work.exists())
            stdout_path = Path(payload["primary_output"]["stdout"]["path"])
            stderr_path = Path(payload["primary_output"]["stderr"]["path"])
            if payload["child_process_state"] == "EXITED":
                self.assertIsInstance(payload["child_exit_code"], int)
                self.assertNotEqual(124, payload["child_exit_code"])
                self.assertEqual("PASS", payload["cleanup"]["cleanup_status"])
                self.assertFalse(stdout_path.exists())
                self.assertFalse(stderr_path.exists())
            else:
                self.assertIsNone(payload["child_exit_code"])
                self.assertEqual("REVIEW_REQUIRED", payload["cleanup"]["cleanup_status"])
                self.assertIn("child_process_still_running", {item["reason"] for item in payload["cleanup"]["errors"]})

    def test_canonical_wrapper_start_error_is_terminal_and_reported(self):
        with self.canonical_runner_harness() as (harness, runner_path, work):
            report_path = work / f"start_error_runner_{__import__('os').getpid()}.json"
            result = subprocess.run(
                [
                    sys.executable,
                    str(runner_path),
                    "--report",
                    str(report_path),
                    "--",
                    str(work / "missing-command-for-runner-test.exe"),
                ],
                cwd=harness,
                capture_output=True,
                text=True,
                timeout=30,
            )
            payload = json.loads(result.stdout)
            self.assertEqual(1, result.returncode)
            self.assertEqual("START_ERROR", payload["outcome"])
            self.assertEqual("START_ERROR", payload["cleanup"]["outcome"])
            self.assertFalse(report_path.exists())
            self.assertFalse(work.exists())

    def test_redirected_runtime_roots_register_shared_path_once(self):
        with self.isolated_workspace() as (root, work, _game, manifest):
            shared = work / "temp"
            appdata = work / "appdata"
            outside = root / "outside"
            env = {
                "TEMP": str(shared),
                "TMP": str(shared),
                "HF_HUB_CACHE": str(shared),
                "APPDATA": str(appdata),
                "LOCALAPPDATA": str(outside),
            }
            with patch.object(runner, "WORK_ROOT", work):
                runner._register_runner_owned_roots(
                    env=env,
                    scope_id="shared-root-scope",
                    run_id="shared-root-run",
                    include_release_verify=True,
                )
            entries = json.loads(manifest.read_text(encoding="utf-8"))["artifacts"]
            self.assertEqual(4, len(entries))
            self.assertEqual(1, sum(item["path"] == str(shared.resolve()) for item in entries))
            self.assertTrue(all(item["lifecycle"] == "DISPOSABLE" for item in entries))
            self.assertTrue(shared.is_dir() and appdata.is_dir())
            self.assertFalse(outside.exists())
            self.assertTrue(Path(env["VNTEXT_RELEASE_VERIFY_RUN_ROOT"]).is_dir())

    def test_post_test_cleanup_uses_ambient_runner_scope(self):
        with self.isolated_workspace() as (_root, work, _game, manifest):
            artifact = work / "ambient-output"
            artifact.mkdir()
            with patch.dict(
                __import__("os").environ,
                {
                    "VNTEXT_ARTIFACT_SCOPE_ID": "ambient-scope",
                    "VNTEXT_ARTIFACT_RUN_ID": "ambient-run",
                    "VNTEXT_ARTIFACT_SCOPE_ROOT": str(work),
                },
                clear=False,
            ):
                report = cleanup.cleanup_after_test(
                    [artifact], reason="ambient-test", outcome="FAIL"
                )
            self.assertTrue(report["ok"])
            entry = next(
                item
                for item in json.loads(manifest.read_text(encoding="utf-8"))["artifacts"]
                if item["path"] == str(artifact.resolve())
            )
            self.assertEqual("ambient-scope", entry["scope_id"])
            self.assertEqual("ambient-run", entry["run_id"])

    def test_post_test_history_namespaces_physical_path_and_preserves_legacy_entry(self):
        with self.isolated_workspace() as (root, work, _game, manifest):
            artifact = work / "legacy-collision-output"
            artifact.mkdir()
            legacy_path = root.parent / "other-worktree" / "tests" / "golden" / "_work" / "cleanup_post_test.jsonl"
            legacy_entry = {
                "id": "cleanup_post_test_history",
                "path": str(legacy_path),
                "status": "ACTIVE",
            }
            manifest.write_text(
                json.dumps({"version": 2, "schema_version": 2, "artifacts": [legacy_entry]}) + "\n",
                encoding="utf-8",
            )

            report = cleanup.cleanup_after_test([artifact], reason="legacy-history-test", outcome="FAIL")

            self.assertTrue(report["ok"])
            entries = json.loads(manifest.read_text(encoding="utf-8"))["artifacts"]
            history = [item for item in entries if item.get("kind") == "cleanup_history"]
            self.assertEqual(1, len(history))
            self.assertNotEqual("cleanup_post_test_history", history[0]["id"])
            self.assertIn(":pathns:", history[0]["id"])
            self.assertEqual(str((work / "cleanup_post_test.jsonl").resolve()), history[0]["path"])
            self.assertNotEqual(
                history[0]["id"],
                cleanup._stable_path_artifact_id("cleanup_post_test_history", legacy_path),
            )
            self.assertIn(legacy_entry, entries)

    def test_post_test_history_id_is_stable_for_same_physical_path(self):
        with self.isolated_workspace() as (_root, work, _game, manifest):
            cleanup.cleanup_after_test([], reason="stable-history-first", outcome="FAIL")
            first_entries = json.loads(manifest.read_text(encoding="utf-8"))["artifacts"]
            first = next(item for item in first_entries if item.get("kind") == "cleanup_history")

            cleanup.cleanup_after_test([], reason="stable-history-second", outcome="FAIL")
            second_entries = json.loads(manifest.read_text(encoding="utf-8"))["artifacts"]
            history = [item for item in second_entries if item.get("kind") == "cleanup_history"]

            self.assertEqual(1, len(history))
            self.assertEqual(first["id"], history[0]["id"])
            self.assertEqual(first["path"], history[0]["path"])
            self.assertEqual(2, len((work / "cleanup_post_test.jsonl").read_text(encoding="utf-8").splitlines()))


if __name__ == "__main__":
    unittest.main()
