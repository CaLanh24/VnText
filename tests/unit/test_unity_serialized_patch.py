"""Generated SerializedFile parsed, patched and reopened by installed UnityPy.

This proves the native parser/writer seam, not Unity Editor/gameplay acceptance.
"""
import hashlib
import json
import struct
import tempfile
import unittest
from pathlib import Path

import UnityPy
from tests.lib.work_paths import work_temp_dir
from vntext.extract_unity import extract_unity_typetree
from vntext.package_io import write_package, read_csv_rows_file, write_csv_rows_file
from vntext.patch_pipeline import apply_translation_package


def text_asset_bytes(script):
    def aligned(value):
        raw = value.encode("utf-8")
        return struct.pack("<i", len(raw)) + raw + b"\0" * (-len(raw) % 4)
    payload = aligned("Dialogue") + aligned(script)
    metadata = b"2019.4.40f1\0" + struct.pack("<i?i", 19, False, 1)
    metadata += struct.pack("<i?h", 49, False, -1) + b"\0" * 16
    metadata += struct.pack("<i", 1)
    metadata += b"\0" * (-(20 + len(metadata)) % 4)
    metadata += struct.pack("<qIII", 7, 0, len(payload), 0)
    metadata += struct.pack("<ii", 0, 0) + b"\0"
    offset = (20 + len(metadata) + 15) // 16 * 16
    return (struct.pack(">IIII", len(metadata), offset + len(payload), 17, offset)
            + b"\0" * 4 + metadata + b"\0" * (offset - 20 - len(metadata)) + payload)


class UnitySerializedPatchTests(unittest.TestCase):
    def test_real_unitypy_textasset_roundtrip_preserves_source(self):
        with tempfile.TemporaryDirectory(dir=work_temp_dir("unity-serialized-patch")) as temp:
            root = Path(temp)
            game = root / "game"
            game.mkdir()
            source = game / "dialogue.assets"
            source.write_bytes(text_asset_bytes("Hello from this generated TextAsset dialogue fixture.\nKeep this line.\n"))
            original = source.read_bytes()
            obj = next(iter(UnityPy.load(original).objects))
            self.assertEqual(obj.path_id, 7)
            self.assertEqual(obj.read().m_Name, "Dialogue")
            entries = list(extract_unity_typetree(source, game))
            entry = next(item for item in entries if item.source_text == "Hello from this generated TextAsset dialogue fixture.")
            package = root / "package"
            write_package(str(package), [entry], [], {"engine": "UNITY"}, True)
            csv = package / "translation.csv"
            fields, rows = read_csv_rows_file(csv)
            rows[0]["translation"] = "Xin chào từ TextAsset."
            write_csv_rows_file(csv, fields, rows)
            output = root / "patch"
            apply_translation_package(str(csv), str(package / "manifest.json"), str(game), str(output))
            patched = output / "COPY_TO_GAME_ROOT" / "dialogue.assets"
            reopened = next(iter(UnityPy.load(patched.read_bytes()).objects))
            self.assertEqual(reopened.path_id, obj.path_id)
            actual = reopened.read().m_Script
            print("reopened_script=" + repr(actual))
            # Direct SerializedFile slots retain padding; readback compares semantic lines.
            expected = "Xin chào từ TextAsset.\nKeep this line.\n"
            self.assertTrue(actual.startswith(expected), repr(actual))
            self.assertEqual(actual[len(expected):].strip(" "), "")
            self.assertEqual(source.read_bytes(), original)
            self.assertEqual((output / "backup_original/dialogue.assets").read_bytes(), original)
            report = json.loads((output / "patch_verification.json").read_text())
            self.assertEqual(report["counts"].get("FAIL", 0), 0)
            self.assertEqual(report["counts"]["PASS"], 1)
            released = source.with_name("released.assets")
            source.rename(released)
            self.assertEqual(released.read_bytes(), original)
            released.rename(source)
            print(json.dumps({"unitypy": UnityPy.__version__, "source_sha256": hashlib.sha256(original).hexdigest(),
                              "patched_sha256": hashlib.sha256(patched.read_bytes()).hexdigest(), "path_id": reopened.path_id}))
