"""Generic Addressables catalog discovery without a game-specific path."""

from __future__ import annotations

import base64
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


def _tests_lib_on_path() -> None:
    cur = Path(__file__).resolve().parent
    while cur.name != "tests" and cur.parent != cur:
        cur = cur.parent
    lib = cur / "lib"
    if str(lib) not in sys.path:
        sys.path.insert(0, str(lib))


_tests_lib_on_path()
from bootstrap import bootstrap

TESTS, ROOT, LIB = bootstrap(__file__)

from vntext.addressables import encode_addressables_extra_data, parse_addressables_extra_data
from vntext.addressables_discovery import (
    is_addressables_bundle_candidate,
    patch_catalogs_for_bundles_generic,
    resolve_addressables_catalog_rel,
)
from vntext.extract_unity import extract_unity_typetree
from vntext.package_io import read_csv_rows_file, write_csv_rows_file, write_package
from vntext.patch import apply_translation_package

from test_unity_capability_microfixtures import (
    _FakeUnityPy,
    _save_fake_environment,
    _write_game,
)


class GenericAddressablesDiscoveryTests(unittest.TestCase):
    def test_custom_catalog_directory_is_discovered_and_rewritten(self):
        with tempfile.TemporaryDirectory(prefix="vntext-addressables-generic-") as name:
            root = Path(name) / "game"
            catalog_dir = root / "Sample_Data" / "StreamingAssets" / "remote_content"
            bundle_rel = (
                "Sample_Data/StreamingAssets/remote_content/StandaloneWindows/"
                "locale_0123456789abcdef0123456789abcdef.bundle"
            )
            source_catalog = catalog_dir / "catalog.json"
            source_catalog.parent.mkdir(parents=True)
            source_catalog.write_text(
                json.dumps(
                    {
                        "m_ExtraDataString": base64.b64encode(
                            encode_addressables_extra_data(
                                [
                                    {
                                        "marker": 1,
                                        "assembly_name": "Unity.ResourceManager",
                                        "class_name": "ContentCatalogData",
                                        "value": {
                                            "m_Hash": "0123456789abcdef0123456789abcdef",
                                            "m_Crc": 123,
                                            "m_BundleSize": 10,
                                            "m_UseCrcForCachedBundles": True,
                                        },
                                    }
                                ]
                            )
                        ).decode("ascii")
                    }
                ),
                encoding="utf-8",
            )
            patch_root = Path(name) / "patch" / "COPY_TO_GAME_ROOT"
            target_bundle = patch_root / bundle_rel
            target_bundle.parent.mkdir(parents=True)
            target_bundle.write_bytes(b"patched bundle payload")

            self.assertEqual(
                resolve_addressables_catalog_rel(root, bundle_rel).as_posix(),
                "Sample_Data/StreamingAssets/remote_content/catalog.json",
            )
            self.assertTrue(is_addressables_bundle_candidate(root, bundle_rel))
            report: list[str] = []
            patch_catalogs_for_bundles_generic(
                root,
                patch_root,
                [(bundle_rel, target_bundle)],
                report,
            )

            patched_catalog = patch_root / "Sample_Data/StreamingAssets/remote_content/catalog.json"
            document = json.loads(patched_catalog.read_text(encoding="utf-8"))
            records = parse_addressables_extra_data(
                base64.b64decode(document["m_ExtraDataString"])
            )
            value = records[0]["value"]
            self.assertEqual(value["m_Crc"], 0)
            self.assertEqual(value["m_BundleSize"], target_bundle.stat().st_size)
            self.assertFalse(value["m_UseCrcForCachedBundles"])
            self.assertTrue(any("updated 1 bundle CRC/size" in line for line in report), report)

    def test_patch_pipeline_updates_custom_catalog_layout(self):
        with tempfile.TemporaryDirectory(prefix="vntext-addressables-pipeline-") as name:
            root = Path(name) / "game"
            package = Path(name) / "package"
            patch_out = Path(name) / "patch"
            bundle_rel = (
                "Sample_Data/StreamingAssets/remote_content/StandaloneWindows/"
                "locale_0123456789abcdef0123456789abcdef.bundle"
            )
            source = _write_game(
                root,
                [
                    {
                        "path_id": 7,
                        "type": "TextAsset",
                        "name": "Locale",
                        "script": "Hello from custom Addressables.\n",
                        "type_tree_enabled": False,
                    }
                ],
                relative=bundle_rel,
            )
            catalog_dir = root / "Sample_Data" / "StreamingAssets" / "remote_content"
            catalog_dir.mkdir(parents=True, exist_ok=True)
            catalog_dir.joinpath("catalog.json").write_text(
                json.dumps(
                    {
                        "m_ExtraDataString": base64.b64encode(
                            encode_addressables_extra_data(
                                [
                                    {
                                        "marker": 1,
                                        "assembly_name": "Unity.ResourceManager",
                                        "class_name": "ContentCatalogData",
                                        "value": {
                                            "m_Hash": "0123456789abcdef0123456789abcdef",
                                            "m_Crc": 123,
                                            "m_BundleSize": 10,
                                            "m_UseCrcForCachedBundles": True,
                                        },
                                    }
                                ]
                            )
                        ).decode("ascii")
                    }
                ),
                encoding="utf-8",
            )
            original_hash = hashlib.sha256(source.read_bytes()).hexdigest()
            fake_unitypy = type("FakeUnityPy", (), {"load": staticmethod(_FakeUnityPy.load)})
            with patch.dict(sys.modules, {"UnityPy": fake_unitypy}):
                extracted = list(extract_unity_typetree(source, root))
                entry = next(item for item in extracted if item.source_text == "Hello from custom Addressables.")
                write_package(
                    str(package),
                    [entry],
                    [],
                    {"fixture": "generic-addressables"},
                    True,
                    enforce_symmetry=True,
                )
                fields, rows = read_csv_rows_file(package / "translation.csv")
                rows[0]["translation"] = "Xin chao Addressables."
                write_csv_rows_file(package / "translation.csv", fields, rows)
                with patch("vntext.patch_output.save_unity_env", side_effect=_save_fake_environment):
                    report = apply_translation_package(
                        str(package / "translation.csv"),
                        str(package / "manifest.json"),
                        str(root),
                        str(patch_out),
                    )

            self.assertTrue(
                any("ADDRESSABLES catalog" in line and "updated 1 bundle CRC/size" in line for line in report),
                report,
            )
            patched_catalog = patch_out / "COPY_TO_GAME_ROOT" / "Sample_Data" / "StreamingAssets" / "remote_content" / "catalog.json"
            records = parse_addressables_extra_data(
                base64.b64decode(json.loads(patched_catalog.read_text(encoding="utf-8"))["m_ExtraDataString"])
            )
            self.assertEqual(records[0]["value"]["m_Crc"], 0)
            self.assertEqual(
                records[0]["value"]["m_BundleSize"],
                (patch_out / "COPY_TO_GAME_ROOT" / bundle_rel).stat().st_size,
            )
            self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(), original_hash)

    def test_unrelated_bundle_is_not_promoted_without_catalog(self):
        with tempfile.TemporaryDirectory(prefix="vntext-addressables-unrelated-") as name:
            root = Path(name)
            rel = "Sample_Data/StreamingAssets/custom/locale.bundle"
            self.assertIsNone(resolve_addressables_catalog_rel(root, rel))
            self.assertFalse(is_addressables_bundle_candidate(root, rel))

    def test_extensionless_resource_stays_out_of_frozen_catalog_writer_route(self):
        with tempfile.TemporaryDirectory(prefix="vntext-addressables-extensionless-") as name:
            root = Path(name)
            catalog_dir = root / "Sample_Data" / "StreamingAssets" / "remote"
            catalog_dir.mkdir(parents=True)
            (catalog_dir / "catalog.json").write_text("{}", encoding="utf-8")
            rel = "Sample_Data/StreamingAssets/remote/StandaloneWindows/locale_resource"
            self.assertIsNotNone(resolve_addressables_catalog_rel(root, rel))
            self.assertFalse(is_addressables_bundle_candidate(root, rel))

    def test_path_traversal_is_not_used_for_catalog_discovery(self):
        with tempfile.TemporaryDirectory(prefix="vntext-addressables-traversal-") as name:
            root = Path(name) / "game"
            root.mkdir()
            (Path(name) / "catalog.json").write_text("{}", encoding="utf-8")
            rel = "Sample_Data/StreamingAssets/aa/../escape.bundle"
            self.assertIsNone(resolve_addressables_catalog_rel(root, rel))
            self.assertFalse(is_addressables_bundle_candidate(root, rel))


if __name__ == "__main__":
    unittest.main()
