"""Windows window capture helpers for E2E harness (tests only)."""
from __future__ import annotations

import ctypes
from ctypes import wintypes
from pathlib import Path

user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32

# Unity's player window needs PW_RENDERFULLCONTENT for an off-screen render.
PW_RENDERFULLCONTENT = 2


class _BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ("biSize", wintypes.DWORD),
        ("biWidth", wintypes.LONG),
        ("biHeight", wintypes.LONG),
        ("biPlanes", wintypes.WORD),
        ("biBitCount", wintypes.WORD),
        ("biCompression", wintypes.DWORD),
        ("biSizeImage", wintypes.DWORD),
        ("biXPelsPerMeter", wintypes.LONG),
        ("biYPelsPerMeter", wintypes.LONG),
        ("biClrUsed", wintypes.DWORD),
        ("biClrImportant", wintypes.DWORD),
    ]


def screenshot_hwnd(hwnd: int, bmp_path: Path) -> bool:
    """Capture client area of hwnd to 24-bit BMP."""
    if not hwnd:
        return False
    rect = wintypes.RECT()
    if not user32.GetClientRect(hwnd, ctypes.byref(rect)):
        return False
    width = rect.right - rect.left
    height = rect.bottom - rect.top
    if width <= 0 or height <= 0:
        return False
    hdc_window = user32.GetDC(hwnd)
    if not hdc_window:
        return False
    hdc_mem = gdi32.CreateCompatibleDC(hdc_window)
    hbmp = gdi32.CreateCompatibleBitmap(hdc_window, width, height)
    gdi32.SelectObject(hdc_mem, hbmp)
    if not user32.PrintWindow(hwnd, hdc_mem, PW_RENDERFULLCONTENT):
        gdi32.BitBlt(hdc_mem, 0, 0, width, height, hdc_window, 0, 0, 0x00CC0020)
    bmi = _BITMAPINFOHEADER()
    bmi.biSize = ctypes.sizeof(_BITMAPINFOHEADER)
    bmi.biWidth = width
    bmi.biHeight = -height
    bmi.biPlanes = 1
    bmi.biBitCount = 24
    bmi.biCompression = 0
    row_size = ((width * 3 + 3) // 4) * 4
    buf = (ctypes.c_ubyte * (row_size * height))()
    gdi32.GetDIBits(hdc_mem, hbmp, 0, height, buf, ctypes.byref(bmi), 0)
    bmp_path.parent.mkdir(parents=True, exist_ok=True)
    file_header_size = 14
    info_header_size = 40
    pixel_data_size = row_size * height
    file_size = file_header_size + info_header_size + pixel_data_size
    with bmp_path.open("wb") as fh:
        fh.write(b"BM")
        fh.write(file_size.to_bytes(4, "little"))
        fh.write((0).to_bytes(2, "little"))
        fh.write((0).to_bytes(2, "little"))
        fh.write((file_header_size + info_header_size).to_bytes(4, "little"))
        fh.write(info_header_size.to_bytes(4, "little"))
        fh.write(width.to_bytes(4, "little", signed=True))
        fh.write((-height).to_bytes(4, "little", signed=True))
        fh.write((1).to_bytes(2, "little"))
        fh.write((24).to_bytes(2, "little"))
        fh.write((0).to_bytes(4, "little"))
        fh.write(pixel_data_size.to_bytes(4, "little"))
        fh.write((0).to_bytes(16, "little"))
        fh.write(bytes(buf))
    gdi32.DeleteObject(hbmp)
    gdi32.DeleteDC(hdc_mem)
    user32.ReleaseDC(hwnd, hdc_window)
    return bmp_path.is_file() and bmp_path.stat().st_size > 0


def screenshot_bmp(hwnd: int, bmp_path: Path) -> bool:
    return screenshot_hwnd(hwnd, bmp_path)


def bmp_to_png(bmp_path: Path, png_path: Path) -> bool:
    try:
        from PIL import Image
    except ImportError:
        return False
    try:
        with Image.open(bmp_path) as im:
            im.save(png_path, format="PNG")
        return png_path.is_file()
    except OSError:
        return False
