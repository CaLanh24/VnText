# -*- coding: utf-8 -*-

"""Focused Player.log fail-closed tests for the optional runtime harness."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


def _tests_lib_on_path() -> None:
    cur = Path(__file__).resolve().parent
    while cur.name != "tests" and cur.parent != cur:
        cur = cur.parent
    lib = cur / "lib"
    value = str(lib)
    if value not in sys.path:
        sys.path.insert(0, value)


_tests_lib_on_path()
from bootstrap import bootstrap

TESTS, ROOT, LIB = bootstrap(__file__)
sys.path.insert(0, str(TESTS / "harness" / "vh_parity"))

from player_log_scan import scan_player_log  # noqa: E402


class PlayerLogScanTests(unittest.TestCase):
    def test_external_data_permission_is_not_testable_even_with_screenshot(self):
        text = (
            "Initialize engine version: 2021.3\n"
            "Screenshot captured: 02_after_newgame.png\n"
            "UnobservedTaskException:System.UnauthorizedAccessException: "
            'Access to the path "C:\\GameData" is denied.\n'
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "Player.log"
            path.write_text(text, encoding="utf-8")
            result = scan_player_log(path)

        self.assertEqual(result["status"], "NOT_TESTABLE")
        self.assertTrue(
            any("UnauthorizedAccessException" in reason for reason in result["reasons"])
        )
        self.assertTrue(any("external game-data" in reason for reason in result["reasons"]))
        self.assertTrue(result["markers"]["unobserved_task_exception"])
        self.assertTrue(result["markers"]["exception"])

    def test_clean_player_log_is_pass_without_runtime_markers(self):
        text = (
            "Initialize engine version: 2021.3.29f1\n"
            "[Physics::Module] Initialized MultithreadedJobDispatcher.\n"
            "The referenced script on this Behaviour is missing!\n"
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "Player.log"
            path.write_text(text, encoding="utf-8")
            result = scan_player_log(path)

        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["reasons"], [])
        self.assertFalse(any(result["markers"].values()))

    def test_runtime_error_markers_fail_closed(self):
        text = (
            "Exception: route failed\n"
            "Fatal error: Crash!!!\n"
            "resources.assets is corrupt; index out of bounds\n"
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "Player.log"
            path.write_text(text, encoding="utf-8")
            result = scan_player_log(path)

        self.assertEqual(result["status"], "FAIL")
        for reason in ("Exception", "Fatal", "Crash!!!", "corruption", "out-of-bounds"):
            self.assertIn(reason, result["reasons"])


if __name__ == "__main__":
    unittest.main()
