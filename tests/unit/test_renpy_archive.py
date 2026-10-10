from __future__ import annotations

import pickle
import os
import tempfile
import unittest
import zlib
from pathlib import Path
from unittest.mock import patch

from tests.lib.work_paths import work_temp_dir
from vntext.renpy_archive import RenPyArchive, RenPyArchiveError, _safe_index

WORK = work_temp_dir("renpy-archive")
KEY = 0x42424242


def write_rpa(path: Path, members: dict[str, bytes]) -> None:
    header_size = len(b"RPA-3.0 0000000000000000 00000000\n")
    data = bytearray(b"\0" * header_size)
    index = {}
    for name, content in members.items():
        offset = len(data)
        data.extend(content)
        index[name] = [(offset ^ KEY, len(content) ^ KEY, b"")]
    index_offset = len(data)
    data.extend(zlib.compress(pickle.dumps(index, protocol=5)))
    data[:header_size] = f"RPA-3.0 {index_offset:016x} {KEY:08x}\n".encode("ascii")
    path.write_bytes(data)


def write_rpa2(path: Path, members: dict[str, bytes]) -> None:
    header_size = len(b"RPA-2.0 0000000000000000\n")
    data = bytearray(b"\0" * header_size); index = {}
    for name, content in members.items():
        offset = len(data); data.extend(content); index[name] = [(offset, len(content))]
    index_offset = len(data); data.extend(zlib.compress(pickle.dumps(index, protocol=2)))
    data[:header_size] = f"RPA-2.0 {index_offset:016x}\n".encode("ascii")
    path.write_bytes(data)


class RenPyArchiveTests(unittest.TestCase):
    def test_reads_rpa3_member_without_unpickling_and_keeps_hash_identity(self):
        with tempfile.TemporaryDirectory(dir=WORK) as temp:
            path = Path(temp) / "game.rpa"
            content = b'label start:\n    e "Hello"\n'
            write_rpa(path, {"game/script.rpy": content})
            archive = RenPyArchive(path)
            result = archive.read_member("game/script.rpy")
            self.assertEqual(result["content"], content)
            self.assertEqual(result["member_sha256"], __import__("hashlib").sha256(content).hexdigest())
            self.assertEqual(result["container_sha256"], archive.container_sha256)

    def test_reads_rpa2_primitive_index(self):
        with tempfile.TemporaryDirectory(dir=WORK) as temp:
            path=Path(temp)/"legacy.rpa";content=b"image bytes"
            write_rpa2(path,{"game/gui/image.png":content})
            archive=RenPyArchive(path)
            self.assertEqual(archive.version,"2.0")
            self.assertEqual(archive.read_member("game/gui/image.png")["content"],content)

    def test_rejects_traversal_and_overlapping_members(self):
        with tempfile.TemporaryDirectory(dir=WORK) as temp:
            root = Path(temp)
            traversal = root / "traversal.rpa"
            write_rpa(traversal, {"../outside.rpy": b"x"})
            with self.assertRaisesRegex(RenPyArchiveError, "path"):
                RenPyArchive(traversal)
            overlap = root / "overlap.rpa"
            header_size = len(b"RPA-3.0 0000000000000000 00000000\n")
            raw = b"x" * 4
            index = {"game/a.rpy": [(header_size ^ KEY, 4 ^ KEY, b"")],
                     "game/b.rpy": [(header_size ^ KEY, 4 ^ KEY, b"")]}
            packed = zlib.compress(pickle.dumps(index, protocol=5))
            offset = header_size + len(raw)
            overlap.write_bytes(f"RPA-3.0 {offset:016x} {KEY:08x}\n".encode() + raw + packed)
            with self.assertRaisesRegex(RenPyArchiveError, "overlap"):
                RenPyArchive(overlap)

    def test_rejects_windows_unsafe_names_and_case_collisions(self):
        with tempfile.TemporaryDirectory(dir=WORK) as temp:
            root = Path(temp)
            for name in ("game/../x.png", "game/./x.png", "game/a//x.png", "game/CON.png", "game/a:stream.png"):
                path = root / "unsafe.rpa"; write_rpa(path, {name: b"x"})
                with self.subTest(name=name), self.assertRaises(RenPyArchiveError): RenPyArchive(path)
            path = root / "case.rpa"; write_rpa(path, {"game/A.png": b"a", "game/a.png": b"b"})
            with self.assertRaisesRegex(RenPyArchiveError, "case-insensitively"): RenPyArchive(path)

    def test_pickle_global_opcode_is_rejected_without_execution(self):
        with self.assertRaisesRegex(RenPyArchiveError, "unsupported RPA index opcode"):
            _safe_index(pickle.dumps(os.system, protocol=5))

    def test_chunk_budget_is_checked_before_member_reads(self):
        import vntext.renpy_archive as archive_module
        with tempfile.TemporaryDirectory(dir=WORK) as temp:
            path = Path(temp) / "chunks.rpa"
            header_size = len(b"RPA-3.0 0000000000000000 00000000\n")
            data = b"abcdef"; index_offset = header_size + len(data)
            index = {"game/two.png": [(header_size ^ KEY, 3 ^ KEY, b""), ((header_size + 3) ^ KEY, 3 ^ KEY, b"")]}
            packed = zlib.compress(pickle.dumps(index, protocol=5))
            path.write_bytes(f"RPA-3.0 {index_offset:016x} {KEY:08x}\n".encode() + data + packed)
            with patch.object(archive_module, "MAX_MEMBER_BYTES", 5):
                archive = RenPyArchive(path)
                with self.assertRaisesRegex(RenPyArchiveError, "exceeds 64 MiB"):
                    archive.read_member("game/two.png")


if __name__ == "__main__":
    unittest.main()
