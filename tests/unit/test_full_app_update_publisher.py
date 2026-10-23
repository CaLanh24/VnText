"""Focused coverage for full-app update package contents."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
import unittest
import zipfile


def _bootstrap_tests():
    current = Path(__file__).resolve().parent
    while current.name != "tests" and current.parent != current:
        current = current.parent
    sys.path.insert(0, str(current / "lib"))
    from bootstrap import bootstrap
    return bootstrap(__file__)


TESTS, ROOT, _LIB = _bootstrap_tests()
sys.path.insert(0, str(ROOT / "release"))
import publish_full_app_update
from work_paths import ambient_scope, new_scope_id, register_artifact, work_temp_dir
sys.path.insert(0, str(TESTS / "tools"))
from cleanup_work_artifacts import cleanup_after_test


class FullAppUpdatePublisherTests(unittest.TestCase):
    def test_inventory_reads_deep_windows_paths(self):
        if sys.platform != "win32":
            self.skipTest("Windows path prefix behavior is platform-specific")
        ambient = ambient_scope()
        scope = ambient["scope_id"]
        run_id = ambient["run_id"]
        if scope == "legacy":
            scope = run_id = new_scope_id("full-app-long-path")
        work = work_temp_dir("full-app-long-path", scope_id=scope, run_id=run_id)
        register_artifact(
            artifact_id=f"full-app-long-path:{scope}", path=work,
            kind="test_workspace", created_by="test_full_app_update_publisher.py",
            owner="test_full_app_update_publisher.py",
            purpose="full-app publisher Windows long path test",
            lifecycle="DISPOSABLE", scope_id=scope, run_id=run_id,
        )
        outcome = "FAIL"
        try:
            root = work / "candidate"
            app = root / "app"
            for index in range(5):
                app /= f"segment-{index}-" + ("x" * 42)
            publish_full_app_update._long_path(app).mkdir(parents=True)
            exe = publish_full_app_update._long_path(root / "VNText Studio.exe")
            exe.write_bytes(b"app")
            publish_full_app_update._long_path(root / "app" / "VERSION.txt").write_text("0.1.1\n", encoding="utf-8")
            publish_full_app_update._long_path(root / "app" / "RELEASE.json").write_text("{}\n", encoding="utf-8")
            payload = publish_full_app_update._long_path(app / "deep-worker.bin")
            payload.write_bytes(b"deep payload")
            self.assertGreater(len(str(payload)), 260)
            inventory = publish_full_app_update._inventory(root)
            relative = "app/" + payload.relative_to(publish_full_app_update._long_path(root / "app")).as_posix()
            self.assertIn(relative, inventory)
            self.assertEqual(len(b"deep payload"), inventory[relative]["size"])
            outcome = "PASS"
        finally:
            report = cleanup_after_test(
                [work], reason="test_full_app_update_publisher.py long path",
                outcome=outcome, scope_id=scope, run_id=run_id,
            )
        if outcome == "PASS":
            self.assertTrue(report["ok"], report)
            self.assertFalse(work.exists(), report)

    def test_changed_worker_file_is_in_package_with_candidate_bytes(self):
        ambient = ambient_scope()
        scope = ambient["scope_id"]
        run_id = ambient["run_id"]
        if scope == "legacy":
            scope = run_id = new_scope_id("full-app-publisher")
        work = work_temp_dir("full-app-publisher", scope_id=scope, run_id=run_id)
        register_artifact(
            artifact_id=f"full-app-publisher:{scope}", path=work,
            kind="test_workspace", created_by="test_full_app_update_publisher.py",
            owner="test_full_app_update_publisher.py",
            purpose="full-app publisher changed worker package test",
            lifecycle="DISPOSABLE", scope_id=scope, run_id=run_id,
        )
        outcome = "FAIL"
        try:
            baseline = work / "baseline"
            candidate = work / "candidate"
            updates = work / "Updates"
            for root in (baseline, candidate):
                (root / "app" / "worker").mkdir(parents=True)
                (root / "app" / "worker" / "models").mkdir()

            baseline_exe = b"baseline app"
            (baseline / "VNText Studio.exe").write_bytes(baseline_exe)
            (baseline / "app" / "VERSION.txt").write_text("0.1.0\n", encoding="utf-8")
            (baseline / "app" / "RELEASE.json").write_text(json.dumps({
                "version": "0.1.0",
                "sha256": hashlib.sha256(baseline_exe).hexdigest(),
            }), encoding="utf-8")
            (baseline / "app" / "worker" / "worker.py").write_bytes(b"old worker")
            (baseline / "app" / "worker" / "models" / "pinned.bin").write_bytes(b"pinned model")

            candidate_exe = b"candidate app"
            worker_bytes = b"candidate worker payload"
            (candidate / "VNText Studio.exe").write_bytes(candidate_exe)
            (candidate / "app" / "VERSION.txt").write_text("0.1.1\n", encoding="utf-8")
            (candidate / "app" / "RELEASE.json").write_text(json.dumps({
                "version": "0.1.1",
                "sha256": hashlib.sha256(candidate_exe).hexdigest(),
                "source_sha": "1" * 40,
                "source_tree_sha256": "2" * 64,
            }), encoding="utf-8")
            (candidate / "app" / "worker" / "worker.py").write_bytes(worker_bytes)
            (candidate / "app" / "worker" / "models" / "pinned.bin").write_bytes(b"pinned model")

            result = publish_full_app_update.publish(
                baseline, candidate, updates, "0.1.1", "1" * 40, "2" * 64,
            )
            package_path = Path(result["package_path"])
            with zipfile.ZipFile(package_path) as package:
                names = set(package.namelist())
                self.assertIn("app/worker/worker.py", names)
                self.assertEqual(worker_bytes, package.read("app/worker/worker.py"))
                self.assertNotIn("app/worker/models/pinned.bin", names)
                manifest = json.loads(package.read(publish_full_app_update.MANIFEST_NAME))
                self.assertIn("app/worker/worker.py", manifest["replace_files"])

            # A named route coexists with the legacy asset/feed for public0.1.7 clients.
            legacy_feed = (updates / publish_full_app_update.FEED_NAME).read_bytes()
            route = publish_full_app_update.publish(baseline, candidate, updates, "0.1.1", "1" * 40, "2" * 64, baseline_named=True)
            named = Path(route["package_path"])
            self.assertRegex(named.name, r"^full-app-update-from-0\.1\.0-to-0\.1\.1-[0-9a-f]{16}\.zip$")
            self.assertEqual(legacy_feed, (updates / publish_full_app_update.FEED_NAME).read_bytes())
            self.assertTrue(package_path.exists())
            self.assertEqual(hashlib.sha256(named.read_bytes()).hexdigest(), route["package_sha256"])
            self.assertEqual(2, route["retained_package_count"])
            with zipfile.ZipFile(named) as archive:
                self.assertEqual(worker_bytes, archive.read("app/worker/worker.py"))

            (candidate / "app" / "worker" / "models" / "pinned.bin").write_bytes(b"changed model")
            (candidate / "app" / "VERSION.txt").write_text("0.1.2\n", encoding="utf-8")
            (candidate / "app" / "RELEASE.json").write_text(json.dumps({
                "version": "0.1.2",
                "sha256": hashlib.sha256(candidate_exe).hexdigest(),
                "source_sha": "1" * 40,
                "source_tree_sha256": "2" * 64,
            }), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "cannot add, replace, or delete model files"):
                publish_full_app_update.publish(
                    baseline, candidate, updates, "0.1.2", "1" * 40, "2" * 64,
                )

            with self.assertRaisesRegex(ValueError, "protected application data"):
                publish_full_app_update._safe_name("app/Data/private.bin")
            with self.assertRaisesRegex(ValueError, "cannot add, replace, or delete model files"):
                publish_full_app_update._validate_protected_model(
                    {"app/worker/models/pinned.bin": {"sha256": "a" * 64, "size": 1}},
                    {"app/worker/Models/pinned.bin": {"sha256": "b" * 64, "size": 1}},
                )

            outcome = "PASS"
        finally:
            report = cleanup_after_test(
                [work], reason="test_full_app_update_publisher.py",
                outcome=outcome, scope_id=scope, run_id=run_id,
            )
        if outcome == "PASS":
            self.assertTrue(report["ok"], report)
            self.assertFalse(work.exists(), report)
            self.assertFalse(report.get("errors"), report)


if __name__ == "__main__":
    unittest.main()
