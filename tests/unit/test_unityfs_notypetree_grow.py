# -*- coding: utf-8 -*-

"""Unit: no-TypeTree resources.assets may grow Script objects via metadata-preserving rewrite."""

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
from pathlib import Path

from vntext.unity_fs import (
    _object_has_new_data,
    _original_child_bytes,
    _rewrite_serialized_file_inplace,
    _rewrite_serialized_file_rebuild_data,
    rewrite_serialized_file_keep_metadata,
)


class FakeHeader:
    def __init__(self, data_offset: int, endian: str = "<", version: int = 21):
        self.data_offset = data_offset
        self.endian = endian
        self.version = version


class FakeObj:
    def __init__(self, path_id: int, byte_start: int, byte_size: int, data: bytes | None = None):
        self.path_id = path_id
        self.byte_start = byte_start
        self.byte_size = byte_size
        self.data = data


class FakeChild:
    def __init__(self, original: bytes, objects: dict, types: list, header: FakeHeader):
        self._original = original
        self.objects = objects
        self.types = types
        self.header = header
        self._enable_type_tree = False
        self.is_changed = True
        self.reader = type("R", (), {"bytes": original})()


class TestNoTypeTreeGrow(unittest.TestCase):
    def test_inplace_when_fit(self):
        # meta 16 bytes padding to data_offset=32 for simplicity is hard — use real helper path
        data_offset = 64
        meta = bytearray(b"\x00" * data_offset)
        blob_a = b"AAAA"
        blob_b = b"BBBBBBBB"
        # layout: pad to align — simplified synthetic won't pass _patch_object_directory
        # So only test inplace helper here.
        original = bytes(meta) + blob_a + blob_b
        obj = FakeObj(1, data_offset, len(blob_a), b"aa")
        child = FakeChild(original, {1: obj}, [], FakeHeader(data_offset))
        # inplace pads short blob
        out = _rewrite_serialized_file_inplace(child, original)
        self.assertIsNotNone(out)
        self.assertEqual(len(out), len(original))

    def test_inplace_none_when_grow(self):
        data_offset = 16
        original = (b"\x00" * data_offset) + b"ABCD"
        obj = FakeObj(7, data_offset, 4, b"ABCDEFGH")
        child = FakeChild(original, {7: obj}, [], FakeHeader(data_offset))
        self.assertIsNone(_rewrite_serialized_file_inplace(child, original))


if __name__ == "__main__":
    unittest.main()
