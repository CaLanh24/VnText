# -*- coding: utf-8 -*-
"""Unit: a SerializedFile v22+ (64-bit byte_start, 48-byte header) can grow object payloads while the type metadata stays byte-identical."""
from __future__ import annotations

import struct
import sys
from pathlib import Path


def _tests_lib_on_path() -> None:
    cur = Path(__file__).resolve().parent
    while cur.name != "tests" and cur.parent != cur:
        cur = cur.parent
    lib = str(cur / "lib")
    if lib not in sys.path:
        sys.path.insert(0, lib)


_tests_lib_on_path()
from bootstrap import bootstrap
TESTS, ROOT, LIB = bootstrap(__file__)

import unittest

from vntext.unity_fs import rewrite_serialized_file_keep_metadata


def build_v22(payloads: list[bytes]) -> bytes:
    """Hand-built v22 file: one no-TypeTree type (TextAsset), one object per payload, little-endian metadata."""
    meta = bytearray()
    meta += b"2022.3.0f1\0"
    meta += struct.pack("<i", 19)                 # target platform
    meta += b"\0"                                 # enable type tree = False
    meta += struct.pack("<i", 1)                  # type count
    meta += struct.pack("<i", 49) + b"\0" + struct.pack("<h", -1) + b"\x11" * 16
    meta += struct.pack("<i", len(payloads))
    rel = 0
    entries = []
    for index, blob in enumerate(payloads):
        rel += (8 - rel % 8) % 8
        entries.append((index + 1, rel, len(blob)))
        rel += len(blob)
    for path_id, start, size in entries:
        meta += b"\0" * ((4 - len(meta) % 4) % 4) if False else b""
        pad = (4 - (48 + len(meta)) % 4) % 4
        meta += b"\0" * pad
        meta += struct.pack("<qQIi", path_id, start, size, 0)
    meta += struct.pack("<i", 0)                  # script count
    meta += struct.pack("<i", 0)                  # externals
    meta += struct.pack("<i", 0)                  # ref types
    meta += b"\0"                                 # user information
    data_offset = 48 + len(meta)
    data_offset += (16 - data_offset % 16) % 16
    data = bytearray()
    for (path_id, start, size), blob in zip(entries, payloads):
        data += b"\0" * (start - len(data))
        data += blob
    header = struct.pack(">IIII", len(meta), 0, 22, 0) + b"\0\0\0\0" + struct.pack(">IQQQ", len(meta), data_offset + len(data), data_offset, 0)
    return header + bytes(meta) + b"\0" * (data_offset - 48 - len(meta)) + bytes(data)


def text_blob(text: str) -> bytes:
    raw = text.encode("utf-8")
    blob = struct.pack("<i", 1) + b"n\0\0\0" if False else struct.pack("<i", 1) + b"n" + b"\0\0\0"
    blob += struct.pack("<i", len(raw)) + raw
    return blob + b"\0" * ((4 - len(raw) % 4) % 4)


class V22GrowTests(unittest.TestCase):
    def test_grown_object_is_rewritten_and_reparsed(self):
        import UnityPy
        original = build_v22([text_blob("Hello"), text_blob("World")])
        env = UnityPy.load(original)
        child = next(iter(env.files.values()))
        self.assertEqual(child.header.version, 22)
        objects = sorted(child.objects.values(), key=lambda o: o.path_id)
        longer = text_blob("Xin chào các bạn, đây là bản dịch dài hơn nhiều")
        objects[0].data = longer
        child.is_changed = True
        rewritten = rewrite_serialized_file_keep_metadata(child)
        self.assertGreater(len(rewritten), len(original))
        self.assertEqual(struct.unpack_from(">Q", rewritten, 24)[0], len(rewritten))
        again = next(iter(UnityPy.load(rewritten).files.values()))
        got = {o.path_id: o.get_raw_data() for o in again.objects.values()}
        self.assertEqual(got[1], longer)
        self.assertEqual(got[2], text_blob("World"))
        # type metadata untouched: everything before the object entries is identical
        self.assertEqual(rewritten[:24], original[:24])
        self.assertEqual(rewritten[48:48 + 40], original[48:48 + 40])


if __name__ == "__main__":
    unittest.main()
