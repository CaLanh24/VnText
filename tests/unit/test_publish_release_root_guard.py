"""The publisher must refuse unknown ReleaseRoot entries before publishing."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys
import shutil
import unittest
from uuid import uuid4


def _bootstrap_tests():
    cur = Path(__file__).resolve().parent
    while cur.name != "tests" and cur.parent != cur:
        cur = cur.parent
    sys.path.insert(0, str(cur / "lib"))
    from bootstrap import bootstrap
    return bootstrap(__file__)


TESTS, ROOT, _LIB = _bootstrap_tests()
from work_paths import WORK_ROOT, RELEASE_ROOT, ambient_scope, new_scope_id, register_artifact
sys.path.insert(0, str(TESTS / "tools"))
from cleanup_work_artifacts import cleanup_after_test


def _tree_snapshot(root: Path) -> dict[str, dict[str, object]]:
    snapshot = {}
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root).as_posix()
        if path.is_dir():
            snapshot[relative] = {"kind": "directory"}
        else:
            snapshot[relative] = {
                "kind": "file",
                "bytes": path.stat().st_size,
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest().upper(),
            }
    return snapshot


class PublishReleaseRootGuardTests(unittest.TestCase):
    def test_dev_smoke_build_is_registered_and_isolated_from_live_dev_exe(self):
        script = (ROOT / "release" / "publish.ps1").read_text(encoding="utf-8")
        self.assertIn('$devSmokeRoot = Join-Path $publishArtifactRoot "dev-smoke"', script)
        self.assertIn('Register-WorkPath $publishScope $devSmokeRoot', script)
        self.assertIn('$devAppExe = Join-Path $devSmokeOut "VNText.Studio.App.exe"', script)
        self.assertIn("-o $devSmokeOut", script)
        self.assertNotIn("-o $devRunRoot", script)
        self.assertIn("cleanup_after_test([Path(sys.argv[4])],reason='release/publish.ps1 WPF DEV smoke'", script)

    def test_unexpected_top_level_item_is_reported_without_writing_release_root(self):
        scope = ambient_scope()
        scope_id = scope["scope_id"] if scope["scope_id"] != "legacy" else new_scope_id("publish-root-guard")
        run_id = scope["run_id"] if scope["run_id"] != "legacy" else scope_id
        work = WORK_ROOT / f"publish-root-guard-{uuid4().hex}"
        release_root = RELEASE_ROOT / f"publish-root-guard-{uuid4().hex}" / "ReleaseRoot"
        register_artifact(
            artifact_id=f"publish-root-guard:{work.name}",
            path=work,
            kind="test_workspace",
            created_by="test_publish_release_root_guard.py",
            owner="test_publish_release_root_guard.py",
            purpose="isolated ReleaseRoot refusal fixture",
            lifecycle="DISPOSABLE",
            scope_id=scope_id,
            run_id=run_id,
            scope_root=scope["scope_root"],
        )
        outcome = "FAIL"
        try:
            updates = release_root / "Updates"
            updates.mkdir(parents=True)
            (release_root / "Setup.exe").write_bytes(b"existing Setup sentinel\x00\x01")
            (updates / "wpf-update-current.json").write_bytes(b'{"package":"retained.zip"}\n')
            (updates / "retained.zip").write_bytes(b"existing package sentinel\x02\x03")
            unexpected_name = "owner-content.bin"
            (release_root / unexpected_name).write_bytes(b"must remain untouched\x04\x05")
            before = _tree_snapshot(release_root)
            worker_venv_root = Path(sys.executable).resolve().parent.parent
            self.assertTrue((worker_venv_root / "Scripts" / "python.exe").is_file(), worker_venv_root)

            command = [
                "pwsh", "-NoLogo", "-NoProfile", "-NonInteractive",
                "-ExecutionPolicy", "Bypass", "-File",
                str(ROOT / "release" / "publish.ps1"),
                "-ReleaseRoot", str(release_root),
                "-WorkerVenvRoot", str(worker_venv_root),
                "-WpfUpdateVersion", "1.44.11-dev",
                "-SkipTests",
            ]
            result = subprocess.run(
                command,
                cwd=ROOT,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=30,
            )
            after = _tree_snapshot(release_root)
            print("PUBLISH_ROOT_GUARD_EVIDENCE " + json.dumps({
                "command": command,
                "exit_code": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "before": before,
                "after": after,
            }, ensure_ascii=False, sort_keys=True))

            combined_output = result.stdout + result.stderr
            self.assertEqual(1, result.returncode, combined_output)
            self.assertIn(unexpected_name, combined_output)
            self.assertEqual(before, after, "Publisher modified or removed a ReleaseRoot item before refusing.")
            self.assertEqual(
                {"Setup.exe", "Updates", unexpected_name},
                {path.name for path in release_root.iterdir()},
            )
            outcome = "PASS"
        finally:
            if release_root.parent.exists():
                shutil.rmtree(release_root.parent, ignore_errors=True)
            cleanup = cleanup_after_test(
                [work],
                reason="test_publish_release_root_guard.py",
                outcome=outcome,
                scope_id=scope_id,
                run_id=run_id,
            )
        if outcome == "PASS":
            if not cleanup.get("ok"):
                self.assertEqual("REVIEW_REQUIRED", cleanup.get("cleanup_status"), cleanup)
                self.assertGreater(cleanup["project_size"]["before"]["non_exempt_bytes"], cleanup["project_size"]["before"]["limit_bytes"])


if __name__ == "__main__":
    unittest.main()
