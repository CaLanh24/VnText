"""Generic unit checks for Addressables child inspection and discovery."""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "tests" / "lib") not in sys.path:
    sys.path.insert(0, str(ROOT / "tests" / "lib"))

from addressables_bundle import find_original_addressables_bundle, inspect_child


class AddressablesBundleStructureTests(unittest.TestCase):
    def test_discovery_accepts_explicit_generic_bundle(self):
        with tempfile.TemporaryDirectory(prefix="vntext-addressables-discovery-") as temp:
            root = Path(temp)
            bundle = root / "Sample_Data" / "StreamingAssets" / "remote" / "content.bundle"
            bundle.parent.mkdir(parents=True)
            bundle.write_bytes(b"UnityFS synthetic bundle")
            self.assertEqual(find_original_addressables_bundle(root), bundle.resolve())

    def test_discovery_can_use_explicit_environment_path(self):
        with tempfile.TemporaryDirectory(prefix="vntext-addressables-env-") as temp:
            bundle = Path(temp) / "external.bundle"
            bundle.write_bytes(b"synthetic")
            old = os.environ.get("VNTEXT_ADDRESSABLES_BUNDLE")
            try:
                os.environ["VNTEXT_ADDRESSABLES_BUNDLE"] = str(bundle)
                self.assertEqual(find_original_addressables_bundle(Path(temp) / "empty"), bundle.resolve())
            finally:
                if old is None:
                    os.environ.pop("VNTEXT_ADDRESSABLES_BUNDLE", None)
                else:
                    os.environ["VNTEXT_ADDRESSABLES_BUNDLE"] = old

    def test_inspect_child_reports_raw_shape_without_loading_unity(self):
        child = SimpleNamespace(reader=SimpleNamespace(view=b"raw payload"))
        result = inspect_child("content.bundle", child)
        self.assertEqual(result["kind"], "raw")
        self.assertEqual(result["size"], len(b"raw payload"))
        self.assertEqual(result["header_hex"], b"raw payload".hex(" "))

    def test_inspect_child_reports_serialized_child_metadata(self):
        child = SimpleNamespace(
            objects={1: object(), 2: object()},
            header=SimpleNamespace(file_size=42),
            types=[],
            _enable_type_tree=True,
            reader=SimpleNamespace(view=b"serialized"),
        )
        result = inspect_child("CAB-001", child)
        self.assertEqual(result["kind"], "serialized_file")
        self.assertEqual(result["object_count"], 2)
        self.assertTrue(result["enable_type_tree"])


if __name__ == "__main__":
    unittest.main()
