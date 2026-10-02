"""Runtime path helpers for DEV vs RELEASE."""

from __future__ import annotations

import sys
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

import unittest

from vntext.runtime_paths import (
    app_data_root,
    default_output_dir,
    is_frozen,
)


class RuntimePathsTests(unittest.TestCase):
    def test_not_frozen_in_tests(self):
        self.assertFalse(is_frozen())

    def test_app_data_under_localappdata(self):
        root = app_data_root()
        self.assertIn("VNTextStudio", str(root))

    def test_default_output_in_documents(self):
        out = default_output_dir()
        self.assertIn("VNText_Output", str(out))

    def test_release_data_and_default_output_stay_under_install_root(self):
        import os
        from unittest.mock import patch

        from uuid import uuid4
        from work_paths import new_scope_id, register_artifact

        sys.path.insert(0, str(TESTS / "tools"))
        from cleanup_work_artifacts import cleanup_after_test

        root = TESTS / "golden" / "_work" / f"runtime-path-boundary-{uuid4().hex}"
        scope = new_scope_id("runtime-path-boundary")
        register_artifact(artifact_id=f"runtime-path:{root.name}", path=root, kind="test_workspace", created_by="test_runtime_paths.py", owner="test_runtime_paths.py", purpose="Release data path boundary test", lifecycle="DISPOSABLE", scope_id=scope, run_id=scope)
        data = root / "data"
        tempfile = __import__("tempfile")
        prior_tempdir = tempfile.tempdir
        outcome = "FAIL"
        try:
            with patch.dict(os.environ, {"VNTEXT_DATA_ROOT": str(data), "VNTEXT_RENPY_TOOL_ROOT": str(root / "outside"), "TEMP": str(data / "temp"), "TMP": str(data / "temp"), "TMPDIR": str(data / "temp")}):
                from vntext.runtime_paths import configure_runtime, app_data_root, default_output_dir

                configure_runtime()
                self.assertEqual(data.resolve(), app_data_root())
                self.assertEqual((data / "output").resolve(), default_output_dir())
                self.assertEqual((data / "temp").resolve(), Path(__import__("tempfile").gettempdir()))
                from vntext.renpy_toolchain import managed_sdk_root
                self.assertEqual((data / "tools" / "renpy-8.5.3").resolve(), managed_sdk_root())
            outcome = "PASS"
        finally:
            tempfile.tempdir = prior_tempdir
            report = cleanup_after_test([root], reason="test_runtime_paths.py", outcome=outcome, scope_id=scope, run_id=scope)
        if outcome == "PASS":
            self.assertTrue(report.get("ok"), report)


    def test_version_compare(self):
        from vntext.app_update import parse_version, version_newer

        self.assertTrue(version_newer("1.40.0", "1.39.0"))
        self.assertFalse(version_newer("1.39.0", "1.40.0"))
        self.assertEqual(parse_version("1.44.9-dev"), (1, 44, 9))
        self.assertTrue(version_newer("1.44.10-dev", "1.44.9-dev"))

    def test_default_update_url_from_config(self):
        from vntext.app_config import default_update_manifest_url

        url = default_update_manifest_url()
        self.assertEqual("", url)

    def test_manifest_sources_do_not_use_an_unconfigured_remote_default(self):
        import os
        from unittest.mock import patch

        from vntext.app_update import resolve_manifest_sources

        with patch.dict(os.environ, {"VNTEXT_UPDATE_URL": ""}), patch(
            "vntext.app_update.sibling_release_manifest", return_value=None
        ):
            self.assertEqual([], resolve_manifest_sources())

    def test_manifest_sources_keep_an_explicit_remote_override(self):
        import os
        from unittest.mock import patch

        from vntext.app_update import resolve_manifest_sources

        url = "https://updates.example.invalid/RELEASE.json"
        with patch.dict(os.environ, {"VNTEXT_UPDATE_URL": url}), patch(
            "vntext.app_update.sibling_release_manifest", return_value=None
        ):
            self.assertEqual([url], resolve_manifest_sources())

    def test_check_for_update_uses_newer_sibling_manifest(self):
        import json
        import os
        import tempfile
        from pathlib import Path
        from unittest.mock import patch

        from vntext.app_update import check_for_update

        with tempfile.TemporaryDirectory() as tmp:
            sibling = Path(tmp) / "RELEASE.json"
            target = Path(tmp) / "VNText Studio.new.exe"
            target.write_bytes(b"fake")
            sibling.write_text(
                json.dumps(
                    {
                        "version": "9.9.9",
                        "url": str(target),
                        "sha256": "",
                        "notes": "test",
                    }
                ),
                encoding="utf-8",
            )
            with patch("vntext.app_update.manifest_url_override", return_value=None), patch(
                "vntext.app_update.default_update_manifest_url",
                return_value="",
            ), patch("vntext.app_update.sibling_release_manifest", return_value=sibling):
                info = check_for_update("1.0.0")
        self.assertIsNotNone(info)
        self.assertEqual(info["version"], "9.9.9")


if __name__ == "__main__":
    unittest.main()
