"""Regression tests for the Unity window capture flags."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


def _tests_lib_on_path() -> None:
    cur = Path(__file__).resolve().parent
    while cur.name != "tests" and cur.parent != cur:
        cur = cur.parent
    lib = str(cur / "lib")
    if lib not in sys.path:
        sys.path.insert(0, lib)


_tests_lib_on_path()
import windows_capture  # noqa: E402


class _FakeUser32:
    def __init__(self) -> None:
        self.print_flags: list[int] = []

    def GetClientRect(self, _hwnd, rect_ptr):
        rect = rect_ptr._obj
        rect.right = 4
        rect.bottom = 3
        return 1

    def GetDC(self, _hwnd):
        return 1

    def PrintWindow(self, _hwnd, _hdc, flags):
        self.print_flags.append(flags)
        return 1

    def ReleaseDC(self, _hwnd, _hdc):
        return 1


class _FakeGdi32:
    def CreateCompatibleDC(self, _hdc):
        return 2

    def CreateCompatibleBitmap(self, _hdc, _width, _height):
        return 3

    def SelectObject(self, _hdc, _bitmap):
        return 4

    def GetDIBits(self, _hdc, _bitmap, _start, height, _buffer, _bmi, _usage):
        return height

    def DeleteObject(self, _bitmap):
        return 1

    def DeleteDC(self, _hdc):
        return 1


class WindowsCaptureTests(unittest.TestCase):
    def test_unity_capture_requests_full_render_content(self):
        user32 = _FakeUser32()
        with tempfile.TemporaryDirectory() as tmp, patch.object(
            windows_capture, "user32", user32
        ), patch.object(windows_capture, "gdi32", _FakeGdi32()):
            output = Path(tmp) / "capture.bmp"
            self.assertTrue(windows_capture.screenshot_hwnd(1, output))
            self.assertEqual(user32.print_flags, [windows_capture.PW_RENDERFULLCONTENT])
            self.assertEqual(windows_capture.PW_RENDERFULLCONTENT, 2)
            self.assertGreater(output.stat().st_size, 54)


if __name__ == "__main__":
    unittest.main()
