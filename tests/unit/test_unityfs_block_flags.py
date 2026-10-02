"""UnityFS per-block flags must be compression only, never archive 0x40."""

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
from pathlib import Path


ARCHIVE_BLOCKS_AND_DIRECTORY_INFO_COMBINED = 0x40
COMPRESSION_NONE = 0
COMPRESSION_LZ4 = 2
COMPRESSION_LZ4HC = 3


class _DummyChild:
    def __init__(self, data: bytes, name: str = "CAB-dummy"):
        self.name = name
        self.bytes = data
        self.Length = len(data)
        self.flags = 0
        self.reader = self
        self.view = memoryview(data)


class _DummyRoot:
    def __init__(self, payload: bytes):
        self.signature = "UnityFS"
        self.version = 7
        self.version_player = "2019.4.35f1"
        self.version_engine = "2019.4.35f1"
        self.dataflags = ARCHIVE_BLOCKS_AND_DIRECTORY_INFO_COMBINED
        self._block_info_flags = ARCHIVE_BLOCKS_AND_DIRECTORY_INFO_COMBINED
        self._uses_block_alignment = True
        self.files = {"CAB-dummy": _DummyChild(payload)}


def _read_cstring(buf: bytes, pos: int) -> tuple[str, int]:
    end = buf.index(b"\x00", pos)
    return buf[pos:end].decode("ascii", "replace"), end + 1


def parse_unityfs_block_flags(path: Path) -> dict:
    data = path.read_bytes()
    pos = 0
    magic, pos = _read_cstring(data, pos)
    if magic != "UnityFS":
        raise ValueError(f"not UnityFS: {magic!r}")
    version = struct.unpack_from(">I", data, pos)[0]
    pos += 4
    _player, pos = _read_cstring(data, pos)
    _engine, pos = _read_cstring(data, pos)
    _file_size, compressed_info, uncompressed_info, data_flag = struct.unpack_from(">qIII", data, pos)
    pos += 8 + 4 + 4 + 4
    if version >= 7:
        pos += (16 - (pos % 16)) % 16
    info_bytes = data[pos:pos + compressed_info]
    compression = data_flag & 0x3F
    if compression in (COMPRESSION_LZ4, COMPRESSION_LZ4HC):
        import lz4.block

        info_raw = lz4.block.decompress(info_bytes, uncompressed_size=uncompressed_info)
    elif compression == COMPRESSION_NONE:
        info_raw = info_bytes
        if len(info_raw) != uncompressed_info:
            info_raw = info_bytes[:uncompressed_info]
    else:
        raise ValueError(f"unsupported directory compression {compression}")
    # 16-byte hash + int32 block count
    count = struct.unpack_from(">i", info_raw, 16)[0]
    off = 20
    blocks = []
    for _ in range(count):
        unpacked, packed, flags = struct.unpack_from(">IIH", info_raw, off)
        blocks.append({"uncompressed": unpacked, "compressed": packed, "flags": int(flags)})
        off += 10
    return {
        "data_flag": int(data_flag),
        "directory_compression": compression,
        "blocks": blocks,
    }


class UnityFsBlockFlagTests(unittest.TestCase):
    def test_lz4_blocks_do_not_carry_archive_combined_flag(self):
        from vntext.unity_fs import write_unityfs_lz4_streaming
        from work_paths import work_temp_dir

        payload = b"VNTEXT-FLAG-PROBE" * (128 * 1024 // 16)
        root = _DummyRoot(payload)
        tmp = work_temp_dir("unityfs_flags")
        dest = tmp / "dummy.bundle"
        try:
            write_unityfs_lz4_streaming(root, dest)
            parsed = parse_unityfs_block_flags(dest)
        finally:
            if dest.exists():
                dest.unlink()
        self.assertTrue(parsed["blocks"], parsed)
        self.assertEqual(
            parsed["data_flag"] & ARCHIVE_BLOCKS_AND_DIRECTORY_INFO_COMBINED,
            ARCHIVE_BLOCKS_AND_DIRECTORY_INFO_COMBINED,
        )
        compressed = 0
        for block in parsed["blocks"]:
            flags = block["flags"]
            self.assertEqual(
                flags & ARCHIVE_BLOCKS_AND_DIRECTORY_INFO_COMBINED,
                0,
                f"archive 0x40 leaked into block flags: {block}",
            )
            compression = flags & 0x3F
            if block["compressed"] < block["uncompressed"]:
                self.assertIn(compression, (COMPRESSION_LZ4, COMPRESSION_LZ4HC), block)
                compressed += 1
            else:
                self.assertEqual(compression, COMPRESSION_NONE, block)
        self.assertGreater(compressed, 0, parsed["blocks"])


if __name__ == "__main__":
    unittest.main()
