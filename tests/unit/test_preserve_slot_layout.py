# -*- coding: utf-8 -*-

"""Regression: preserve_slot_size must not shift the next length-prefixed field."""

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

import struct
import unittest

from vntext.extract import _unity_string_padding
from vntext.patch import _apply_unity_length_prefixed_replacements


def _aligned_string(text: str) -> bytes:
    raw = text.encode("utf-8")
    pad = _unity_string_padding(len(raw))
    return struct.pack("<i", len(raw)) + raw + (b"\x00" * pad)


def _read_aligned_string(buf: bytes, offset: int) -> tuple[str, int]:
    length = struct.unpack_from("<i", buf, offset)[0]
    start = offset + 4
    end = start + length
    pad = _unity_string_padding(length)
    text = buf[start:end].decode("utf-8")
    return text, end + pad


class PreserveSlotLayoutTests(unittest.TestCase):
    def test_shorter_replacement_keeps_following_field(self) -> None:
        first = "Hello world!!"  # 13 bytes + 3 pad
        second = "NEXT_FIELD_OK"
        blob = _aligned_string(first) + _aligned_string(second) + struct.pack("<i", 42)
        second_off = len(_aligned_string(first))
        items = [
            {
                "text": first,
                "new_text": "Xin chao",  # shorter UTF-8
                "offset": 0,
                "byte_length": len(first.encode("utf-8")),
            }
        ]
        new_blob, changed = _apply_unity_length_prefixed_replacements(
            blob, items, preserve_slot_size=True
        )
        self.assertEqual(changed, 1)
        self.assertEqual(len(new_blob), len(blob))

        # Declared length of first field must stay identical (no early next-field read).
        declared = struct.unpack_from("<i", new_blob, 0)[0]
        self.assertEqual(declared, len(first.encode("utf-8")))

        # Following field must still decode at the original absolute offset.
        second_text, after_second = _read_aligned_string(new_blob, second_off)
        self.assertEqual(second_text, second)
        trailing = struct.unpack_from("<i", new_blob, after_second)[0]
        self.assertEqual(trailing, 42)

        # Payload is space-padded inside the string body.
        payload = new_blob[4 : 4 + declared]
        self.assertTrue(payload.decode("utf-8").startswith("Xin chao"))
        self.assertEqual(len(payload), declared)

    def test_preserve_skips_when_new_text_longer(self) -> None:
        first = "Short"
        second = "TAIL"
        blob = _aligned_string(first) + _aligned_string(second)
        items = [
            {
                "text": first,
                "new_text": "Much longer than before",
                "offset": 0,
                "byte_length": len(first.encode("utf-8")),
            }
        ]
        new_blob, changed = _apply_unity_length_prefixed_replacements(
            blob, items, preserve_slot_size=True
        )
        self.assertEqual(changed, 0)
        self.assertEqual(new_blob, blob)


if __name__ == "__main__":
    unittest.main()
