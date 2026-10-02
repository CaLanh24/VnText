"""YAML discovery stays bounded and review-only until a symmetric writer exists."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from vntext.extract_pipeline import extract_project
from vntext.extract_yaml import extract_yaml_text_candidates
from vntext.package_io import read_csv_rows_file, write_package


class YAMLReviewExtractionTests(unittest.TestCase):
    def _make_yaml(self, root: Path) -> Path:
        path = root / "Demo_Data" / "StreamingAssets" / "localization.yaml"
        path.parent.mkdir(parents=True)
        path.write_text(
            """meta:
  title: \"A title # keeps its hash\"
  version: 1
  description: |
    Welcome to the demo.
    Choose wisely.
enabled: true
choices:
  - \"First choice\"
  - Second choice # trailing comment
""",
            encoding="utf-8",
        )
        return path

    def test_scanner_emits_display_candidates_with_review_locators_only(self):
        with tempfile.TemporaryDirectory(prefix="vntext-yaml-review-") as name:
            root = Path(name) / "game"
            yaml_path = self._make_yaml(root)

            entries = list(extract_yaml_text_candidates(yaml_path, root))

            self.assertEqual(
                {entry.source_text for entry in entries},
                {
                    "A title # keeps its hash",
                    "Welcome to the demo.",
                    "Choose wisely.",
                    "First choice",
                    "Second choice",
                },
            )
            self.assertTrue(all(entry.review_only for entry in entries))
            self.assertTrue(all(entry.import_method == "yaml_text_candidate" for entry in entries))
            self.assertTrue(all(entry.backend == "yaml_inventory" for entry in entries))
            self.assertTrue(all(not entry.patch_proof for entry in entries))
            self.assertTrue(
                all(
                    set(entry.locator)
                    >= {"line", "column", "yaml_path", "scalar_kind"}
                    for entry in entries
                )
            )
            self.assertEqual(entries[1].locator["yaml_path"], "description.block[1]")

    def test_pipeline_routes_yaml_to_review_in_safe_and_deep_modes(self):
        with tempfile.TemporaryDirectory(prefix="vntext-yaml-pipeline-") as name:
            root = Path(name) / "game"
            self._make_yaml(root)

            for mode in ("safe", "deep"):
                main, review, stats = extract_project(str(root), mode)

                self.assertFalse(main)
                self.assertEqual(stats["files_scanned"], 1)
                self.assertEqual(stats["yaml_inventory_files"], 1)
                self.assertEqual(stats["yaml_review_entries"], 5)
                self.assertEqual(len(review), 5)
                self.assertEqual(stats["method_counts"], {"yaml_text_candidate": 5})
                self.assertTrue(all(item["step"] != "plain_text" for item in stats["file_timings"]))
                self.assertTrue(all(item["step"] != "raw_scan" for item in stats["file_timings"]))

    def test_invalid_utf8_is_explicit_and_never_falls_back_to_raw_scan(self):
        with tempfile.TemporaryDirectory(prefix="vntext-yaml-invalid-") as name:
            root = Path(name) / "game"
            yaml_path = root / "Demo_Data" / "StreamingAssets" / "broken.yml"
            yaml_path.parent.mkdir(parents=True)
            yaml_path.write_bytes(b"title: Good text\n\xff\xfe\n")

            main, review, stats = extract_project(str(root), "deep")

            self.assertFalse(main)
            self.assertFalse(review)
            self.assertEqual(stats["files_scanned"], 1)
            self.assertEqual(stats["yaml_inventory_files"], 1)
            self.assertEqual(stats["yaml_review_entries"], 0)
            self.assertTrue(any("yaml_inventory" in error for error in stats["errors"]))
            self.assertTrue(all(item["step"] != "raw_scan" for item in stats["file_timings"]))

    def test_package_keeps_yaml_candidates_in_review_only_csv(self):
        with tempfile.TemporaryDirectory(prefix="vntext-yaml-package-") as name:
            root = Path(name) / "game"
            package = Path(name) / "package"
            self._make_yaml(root)

            main, review, stats = extract_project(str(root), "safe")
            write_package(str(package), main, review, stats, True, enforce_symmetry=True)

            _fields, translation_rows = read_csv_rows_file(package / "translation.csv")
            _review_fields, review_rows = read_csv_rows_file(package / "review_only.csv")
            self.assertEqual(translation_rows, [])
            self.assertEqual(len(review_rows), 5)
            self.assertTrue(all(row["import_method"] == "yaml_text_candidate" for row in review_rows))
            self.assertTrue(all(row["translation"] == "" for row in review_rows))


if __name__ == "__main__":
    unittest.main()
