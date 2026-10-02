"""Phase 5 proof for signature-based extensionless discovery and patching."""

from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


from vntext.entry import Entry
from vntext.extract_pipeline import extract_project
from vntext.extract_naninovel import should_naninovel_scan
from vntext.package_io import read_csv_rows_file, write_csv_rows_file, write_package
from vntext.unity_analyzer import detect_resource_kind
from vntext.patch import apply_translation_package


class ExtensionlessResourceTests(unittest.TestCase):
    def test_signature_detector_routes_extensionless_text_and_unity_header(self):
        with tempfile.TemporaryDirectory(prefix="vntext-extensionless-detect-") as name:
            root = Path(name)
            text_path = root / "dialogue"
            unity_path = root / "asset_blob"
            binary_path = root / "opaque"
            text_path.write_text("Hello from an extensionless resource\n", encoding="utf-8")
            unity_path.write_bytes(b"UnityFS\x00synthetic fixture")
            binary_path.write_bytes(b"\x00\x01\x02\xffopaque")

            text_kind = detect_resource_kind(text_path)
            unity_kind = detect_resource_kind(unity_path)
            binary_kind = detect_resource_kind(binary_path)

            self.assertTrue(text_kind["is_extensionless_text"])
            self.assertFalse(text_kind["is_unity_extractable"])
            self.assertTrue(unity_kind["is_unity_extractable"])
            self.assertEqual(unity_kind["signature"], "unityfs")
            self.assertFalse(binary_kind["is_extensionless_text"])
            self.assertFalse(binary_kind["is_unity_extractable"])

    def test_extract_pipeline_dispatches_extensionless_unity_header(self):
        with tempfile.TemporaryDirectory(prefix="vntext-extensionless-unity-") as name:
            root = Path(name) / "game"
            asset = root / "Demo_Data" / "asset_blob"
            asset.parent.mkdir(parents=True)
            asset.write_bytes(b"UnityFS\x00synthetic fixture")
            extracted = Entry(
                source_text="Hello from Unity",
                file_path="Demo_Data/asset_blob",
                context="path_id:7;field:m_Text",
                import_method="unity_typetree_field",
                safety="safe",
                locator={"path_id": 7, "field_path": "m_Text"},
                backend="unity_typetree",
            ).finalize()

            with patch("vntext.extract_unity.extract_unity_typetree", return_value=[extracted]) as reader:
                main, review, stats = extract_project(str(root), "safe")

            self.assertEqual(reader.call_count, 1)
            self.assertEqual(stats["files_scanned"], 1)
            self.assertEqual(stats["extensionless_unity_files"], 1)
            self.assertEqual(stats["extensionless_text_files"], 0)
            # Discovery is still proven (the reader was dispatched), but the
            # synthetic row has no roundtrip proof and must not enter MAIN.
            self.assertFalse(main)
            self.assertEqual([entry.file_path for entry in review], ["Demo_Data/asset_blob"])
            self.assertTrue(review[0].review_only)
            self.assertEqual(stats["symmetry_gate"]["demoted_to_review_entries"], 1)

    def test_compressed_unityfs_skips_file_level_naninovel_scan(self):
        with tempfile.TemporaryDirectory(prefix="vntext-unityfs-raw-policy-") as name:
            root = Path(name)
            unityfs = root / "asset.unity3d"
            webdata = root / "asset.bundle"
            unityraw = root / "asset_raw.unity3d"
            unityfs.write_bytes(b"UnityFS\x00compressed blocks")
            webdata.write_bytes(b"UnityWebData1.0\x00wrapped bundle")
            unityraw.write_bytes(b"UnityRaw\x00serialized data")

            self.assertFalse(should_naninovel_scan(unityfs, ".unity3d", is_unity_resource=True))
            self.assertFalse(should_naninovel_scan(webdata, ".bundle", is_unity_resource=True))
            self.assertTrue(should_naninovel_scan(unityraw, ".unity3d", is_unity_resource=True))

    def test_deep_extract_does_not_run_raw_scan_on_unityfs(self):
        with tempfile.TemporaryDirectory(prefix="vntext-unityfs-pipeline-") as name:
            root = Path(name) / "game"
            asset = root / "Demo_Data" / "asset.unity3d"
            asset.parent.mkdir(parents=True)
            asset.write_bytes(b"UnityFS\x00compressed blocks")

            with patch(
                "vntext.unity_analyzer.detect_resource_kind",
                return_value={
                    "signature": "unityfs",
                    "is_unity_extractable": True,
                    "is_extensionless_text": False,
                },
            ), patch("vntext.extract_unity.extract_unity_typetree", return_value=[]), patch(
                "vntext.extract_unity.scan_unity_ui_blob", return_value=[]
            ), patch("vntext.extract_naninovel.scan_naninovel_blob") as raw_scan:
                main, review, stats = extract_project(str(root), "deep")

            self.assertFalse(main)
            self.assertFalse(review)
            self.assertFalse(raw_scan.called)
            self.assertNotIn("naninovel_scan", [item["step"] for item in stats["file_timings"]])

    def test_extract_package_patch_reopen_and_original_fingerprint_for_extensionless_text(self):
        with tempfile.TemporaryDirectory(prefix="vntext-extensionless-roundtrip-") as name:
            root = Path(name) / "game"
            package = Path(name) / "package"
            output = Path(name) / "patch"
            (root / "Demo_Data").mkdir(parents=True)
            source = root / "Demo_Data" / "dialogue"
            source.write_text("Hello from an extensionless resource\nKeep this line\n", encoding="utf-8")

            main, review, stats = extract_project(str(root), "safe")

            self.assertEqual(stats["files_scanned"], 1)
            self.assertEqual(stats["extensionless_text_files"], 1)
            self.assertEqual(stats["extensionless_unity_files"], 0)
            self.assertTrue(main)
            self.assertFalse(review)
            self.assertTrue(all(entry.patch_proof for entry in main))
            self.assertTrue(stats["symmetry_gate"]["main_flow_safe"])

            write_package(str(package), main, review, stats, True, enforce_symmetry=True)
            manifest = json.loads((package / "manifest.json").read_text(encoding="utf-8"))
            self.assertTrue(manifest["entries"][0]["patch_proof"]["semantic_verify"])

            fields, rows = read_csv_rows_file(package / "translation.csv")
            self.assertEqual(len(rows), 2)
            selected = [row for row in rows if row["source_text"] == "Hello from an extensionless resource"]
            self.assertEqual(len(selected), 1)
            selected[0]["translation"] = "Xin chào từ tài nguyên không có phần mở rộng"
            write_csv_rows_file(package / "translation.csv", fields, rows)

            original_hash = hashlib.sha256(source.read_bytes()).hexdigest()
            report = apply_translation_package(
                str(package / "translation.csv"),
                str(package / "manifest.json"),
                str(root),
                str(output),
            )

            patched = output / "COPY_TO_GAME_ROOT" / "Demo_Data" / "dialogue"
            self.assertTrue(any("TEXT Demo_Data\\dialogue: 1/1" in line for line in report), report)
            self.assertEqual(
                patched.read_text(encoding="utf-8"),
                "Xin chào từ tài nguyên không có phần mở rộng\nKeep this line\n",
            )
            self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(), original_hash)
            self.assertTrue((output / "backup_original" / "Demo_Data" / "dialogue").is_file())


if __name__ == "__main__":
    unittest.main()
