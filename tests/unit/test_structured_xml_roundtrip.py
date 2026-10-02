"""Proof for field-level XML extraction and symmetric patching."""

from __future__ import annotations

import codecs
import hashlib
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path


def _tests_lib_on_path() -> None:
    cur = Path(__file__).resolve().parent
    while cur.name != "tests" and cur.parent != cur:
        cur = cur.parent
    lib = cur / "lib"
    value = str(lib)
    if value not in sys.path:
        sys.path.insert(0, value)


_tests_lib_on_path()
from bootstrap import bootstrap

TESTS, ROOT, LIB = bootstrap(__file__)

from vntext.extract_pipeline import extract_project
from vntext.package_io import read_csv_rows_file, write_csv_rows_file, write_package
from vntext.patch import apply_translation_package


class StructuredXmlRoundtripTests(unittest.TestCase):
    def test_extract_patch_reopen_and_preserve_original(self):
        with tempfile.TemporaryDirectory(prefix="vntext-structured-xml-") as name:
            root = Path(name)
            source = root / "StreamingAssets" / "Localization" / "dialogue.xml"
            source.parent.mkdir(parents=True)
            rendered = (
                '<?xml version="1.0" encoding="utf-8"?>\r\n'
                '<localization>\r\n'
                '  <entry id="line_1" label="Play" text="Hello from XML">Welcome from XML</entry>\r\n'
                '  <choice id="choice_1" value="Yes">No</choice>\r\n'
                '</localization>\r\n'
            )
            source.write_bytes(codecs.BOM_UTF8 + rendered.encode("utf-8"))
            original_hash = hashlib.sha256(source.read_bytes()).hexdigest()

            main, review, stats = extract_project(str(root), "deep", None, "balanced")
            xml_entries = [entry for entry in main if entry.import_method == "structured_xml_value"]
            self.assertEqual(
                {entry.source_text for entry in xml_entries},
                {"Play", "Hello from XML", "Welcome from XML", "Yes", "No"},
            )
            self.assertTrue(
                all(
                    {"xml_path", "node_kind"}.issubset(entry.locator)
                    and all(entry.patch_proof.values())
                    for entry in xml_entries
                )
            )
            self.assertFalse(any(entry.source_text in {"line_1", "choice_1"} for entry in main + review))

            package = root / "package"
            write_package(str(package), main, review, stats, True, enforce_symmetry=True)
            fields, rows = read_csv_rows_file(package / "translation.csv")
            translations = {
                "Play": "Chơi",
                "Hello from XML": "Xin chào từ XML",
                "Welcome from XML": "Chào mừng từ XML",
                "Yes": "Có",
                "No": "Không",
            }
            for row in rows:
                row["translation"] = translations[row["source_text"]]
            write_csv_rows_file(package / "translation.csv", fields, rows)

            patch_out = root / "patch"
            apply_translation_package(
                str(package / "translation.csv"),
                str(package / "manifest.json"),
                str(root),
                str(patch_out),
            )

            patched = patch_out / "COPY_TO_GAME_ROOT" / "StreamingAssets" / "Localization" / "dialogue.xml"
            self.assertTrue(patched.is_file())
            self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(), original_hash)
            self.assertTrue(patched.read_bytes().startswith(codecs.BOM_UTF8))
            self.assertIn(b"\r\n", patched.read_bytes())
            document = ET.parse(patched).getroot()
            entry = document.find("entry")
            choice = document.find("choice")
            self.assertIsNotNone(entry)
            self.assertIsNotNone(choice)
            self.assertEqual(entry.attrib["label"], "Chơi")
            self.assertEqual(entry.attrib["text"], "Xin chào từ XML")
            self.assertEqual(entry.text, "Chào mừng từ XML")
            self.assertEqual(choice.attrib["value"], "Có")
            self.assertEqual(choice.text, "Không")
            report = (patch_out / "import_report.txt").read_text(encoding="utf-8")
            self.assertIn("XML StreamingAssets\\Localization\\dialogue.xml: 5/5", report)
            self.assertIn("VERIFY translated_bytes_in_patched_files: 5/5", report)


if __name__ == "__main__":
    unittest.main()
