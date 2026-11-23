"""Unity bundles, serialized files and ZIP archives: the report carries their structure, a stand-in rebuilt from it shows the same structure, and no name survives."""
import json
import struct
import tempfile
import unittest
import zipfile
from pathlib import Path

from tests.lib.work_paths import work_temp_dir
from tests.tools.synth_from_report import synthesize
from vntext.bug_report import fingerprint
from vntext.structure_shapes import serialized_shape, shape_for, unityfs_shape, zip_shape

WORK = work_temp_dir("bug-report-containers")
SECRETS = ("SecretLevelName", "ZorbaCab", "hero_portrait", "TopSecretZip")


def make_unityfs(path: Path, *, truncate=None, magic=b"UnityFS\0") -> None:
    blocks = [(40000, 40000), (700, 700)]
    info = b"\0" * 16 + struct.pack(">I", len(blocks)) + b"".join(struct.pack(">IIH", r, c, 0) for r, c in blocks)
    nodes = [("CAB-ZorbaCab-0", 40000), ("SecretLevelName.resS", 700)]
    info += struct.pack(">I", len(nodes)) + b"".join(struct.pack(">QQI", 0, size, 4) + name.encode() + b"\0" for name, size in nodes)
    prefix = magic + struct.pack(">I", 6) + b"5.x.x\0" + b"2019.4.1f1\0"
    tail = struct.pack(">III", len(info), len(info), 0)
    body = b"\0" * sum(r for r, _ in blocks)
    total = len(prefix) + 8 + len(tail) + len(info) + len(body)
    data = prefix + struct.pack(">Q", total) + tail + info + body
    path.write_bytes(data[:truncate] if truncate else data)


def make_zip(path: Path) -> None:
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("TopSecretZip/hero_portrait.png", b"x" * 3000, compress_type=zipfile.ZIP_DEFLATED)
        archive.writestr("TopSecretZip/data.json", b"y" * 200, compress_type=zipfile.ZIP_STORED)
        archive.writestr("readme.txt", b"z" * 90000, compress_type=zipfile.ZIP_DEFLATED)


class ContainerShapeTests(unittest.TestCase):
    def _game(self, base: Path) -> Path:
        root = base / "Game Folder"
        (root / "Game_Data" / "StreamingAssets").mkdir(parents=True)
        make_unityfs(root / "Game_Data" / "StreamingAssets" / "SecretLevelName.bundle")
        make_unityfs(root / "Game_Data" / "StreamingAssets" / "broken.bundle", truncate=70)
        make_unityfs(root / "Game_Data" / "StreamingAssets" / "wrong.bundle", magic=b"UnityXX\0")
        make_zip(root / "TopSecretZip.zip")
        (root / "bad.zip").write_bytes(b"PK\3\4 not really a zip")
        return root

    def test_unityfs_shape_reads_header_blocks_and_nodes_without_names(self):
        with tempfile.TemporaryDirectory(dir=WORK) as temp:
            path = Path(temp) / "a.bundle"
            make_unityfs(path)
            shape = unityfs_shape(path)
            self.assertEqual(6, shape["format_version"])
            self.assertEqual(2, shape["blocks"])
            self.assertEqual({"lt1k": 1, "lt64k": 1}, shape["block_uncompressed_classes"])
            self.assertEqual({"none": 2}, shape["block_compression"])
            self.assertEqual(2, shape["nodes"])
            self.assertNotIn("error", shape)
            self.assertNotIn("ZorbaCab", json.dumps(shape))

    def test_failures_are_located_not_described_by_content(self):
        with tempfile.TemporaryDirectory(dir=WORK) as temp:
            truncated, wrong = Path(temp) / "t.bundle", Path(temp) / "w.bundle"
            make_unityfs(truncated, truncate=70)
            make_unityfs(wrong, magic=b"UnityXX\0")
            self.assertEqual("bad_magic", unityfs_shape(wrong)["error"]["kind"])
            self.assertIn("kind", unityfs_shape(truncated)["error"])
            bad = Path(temp) / "b.zip"
            bad.write_bytes(b"PK\3\4 junk")
            self.assertEqual("BadZipFile", zip_shape(bad)["error"]["kind"])

    def test_report_to_stand_in_keeps_the_structure_and_leaks_no_name(self):
        with tempfile.TemporaryDirectory(dir=WORK) as temp:
            root = self._game(Path(temp))
            report = fingerprint(root)
            blob = json.dumps(report, ensure_ascii=False)
            for secret in SECRETS + (temp,):
                self.assertNotIn(secret.casefold(), blob.casefold(), secret)
            containers = [f["container"] for f in report["files"] if "container" in f]
            self.assertEqual({"unityfs", "zip"}, {c["kind"] for c in containers})
            stand_in = synthesize(report, Path(temp) / "stand-in")
            replay = fingerprint(stand_in)

            stable = ("kind", "format_version", "blocks", "nodes", "entries", "block_compression", "compression_methods", "extensions")

            def keyed(rep):
                # Names are hashed again for the stand-in, so compare by structure, not by path.
                rows = [{**{k: v.get(k) for k in stable}, "error": (v.get("error") or {}).get("kind")} for v in (f["container"] for f in rep["files"] if "container" in f)]
                return sorted(json.dumps(r, sort_keys=True) for r in rows)
            self.assertEqual(keyed(report), keyed(replay))

    def test_serialized_header_v22_is_read_and_replayed(self):
        from tests.unit import test_unityfs_v22_grow as grow
        builder = next((getattr(grow, n) for n in dir(grow) if n.startswith(("build", "make", "_build", "_make"))), None)
        with tempfile.TemporaryDirectory(dir=WORK) as temp:
            path = Path(temp) / "level0.assets"
            head = bytearray(64)
            struct.pack_into(">I", head, 8, 22)
            head[16] = 0
            struct.pack_into(">I", head, 20, 120)
            struct.pack_into(">QQ", head, 24, 4096, 192)
            path.write_bytes(bytes(head) + b"\0" * 4032)
            shape = serialized_shape(path)
            self.assertEqual((22, "little", 120, 4096, 192), (shape["version"], shape["endianness"], shape["metadata_size"], shape["declared_size"], shape["data_offset"]))
            self.assertIsNone(shape_for(Path(temp) / "x.txt", b"hello world 12345"))
            self.assertIsNotNone(builder)


if __name__ == "__main__":
    unittest.main()
