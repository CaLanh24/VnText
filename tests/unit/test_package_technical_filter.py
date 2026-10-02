"""Technical extract rows are audited separately from player-visible CSV."""
from __future__ import annotations

import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path

cur = Path(__file__).resolve().parent
while cur.name != "tests" and cur.parent != cur:
    cur = cur.parent
sys.path.insert(0, str(cur / "lib"))
from bootstrap import bootstrap

TESTS, ROOT, LIB = bootstrap(__file__)

from vntext.entry import Entry
from vntext.package_io import write_package
from vntext.patchability import STRUCTURED_XML_PATCH_PROOF


class TechnicalPackageFilterTests(unittest.TestCase):
    def test_skip_technical_is_not_written_to_translation_csv(self):
        visible = Entry(
            source_text="Hello player",
            file_path="game/dialogue.txt",
            context="dialogue",
            import_method="plain_text_line",
            safety="safe",
        ).finalize()
        technical = Entry(
            source_text="Sample.Scene_{mName}",
            file_path="game/dialogue.txt",
            context="runtime",
            import_method="plain_text_line",
            safety="safe",
        ).finalize()
        out = Path(tempfile.mkdtemp(prefix="vntext_technical_filter_"))
        write_package(str(out), [visible, technical], [], {"mode": "deep"}, False)

        with (out / "translation.csv").open(encoding="utf-8-sig", newline="") as fh:
            rows = list(csv.DictReader(fh))
        self.assertEqual([r["key"] for r in rows], [visible.key])

        with (out / "technical_skipped.csv").open(encoding="utf-8-sig", newline="") as fh:
            skipped = list(csv.DictReader(fh))
        self.assertEqual([r["key"] for r in skipped], [technical.key])
        self.assertIn("skip_technical", skipped[0]["patch_note"])

        manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["stats"]["technical_skipped_entries"], 1)
        self.assertEqual(manifest["technical_skipped"][0]["source_text"], technical.source_text)
        self.assertEqual(manifest["technical_skipped"][0]["reason"], "path/id/hash token — không phải thoại")

    def test_naninovel_runtime_pool_is_written_to_technical_ledger(self):
        visible = Entry(
            source_text="Hello, how are you?",
            file_path="game/dialogue.txt",
            context="NaninovelScript:1",
            import_method="naninovel_script_string",
            safety="safe",
        ).finalize()
        technical = Entry(
            source_text="actionA,actionB,actionB,actionB",
            file_path="game/dialogue.txt",
            context="NaninovelScript:fixture:1",
            import_method="naninovel_script_string",
            safety="safe",
        ).finalize()
        out = Path(tempfile.mkdtemp(prefix="vntext_technical_pool_"))
        write_package(str(out), [visible, technical], [], {"mode": "deep"}, False)

        with (out / "translation.csv").open(encoding="utf-8-sig", newline="") as fh:
            rows = list(csv.DictReader(fh))
        self.assertEqual([r["key"] for r in rows], [visible.key])
        with (out / "technical_skipped.csv").open(encoding="utf-8-sig", newline="") as fh:
            skipped = list(csv.DictReader(fh))
        self.assertEqual([r["key"] for r in skipped], [technical.key])
        self.assertIn("token pool", skipped[0]["patch_note"])

    def test_mono_runtime_xml_is_written_to_technical_ledger(self):
        technical = Entry(
            source_text="Adds entries to your Web.config file which are required by any .NET 3.5 AJAX.NET application.",
            file_path="MonoBleedingEdge/etc/mono/mconfig/config.xml",
            context="element_path=/1/0",
            import_method="structured_xml_value",
            safety="safe",
            locator={"xml_path": [0, 0], "node_kind": "text"},
            backend="structured_xml",
            patch_proof=dict(STRUCTURED_XML_PATCH_PROOF),
        ).finalize()
        out = Path(tempfile.mkdtemp(prefix="vntext_mono_runtime_filter_"))
        write_package(str(out), [technical], [], {"mode": "deep"}, True, enforce_symmetry=True)

        with (out / "translation.csv").open(encoding="utf-8-sig", newline="") as fh:
            rows = list(csv.DictReader(fh))
        self.assertEqual(rows, [])

        with (out / "technical_skipped.csv").open(encoding="utf-8-sig", newline="") as fh:
            skipped = list(csv.DictReader(fh))
        self.assertEqual([row["key"] for row in skipped], [technical.key])
        self.assertIn("technical runtime/config path", skipped[0]["patch_note"])

        manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["stats"]["technical_skipped_entries"], 1)
        self.assertEqual(manifest["technical_skipped"][0]["file_path"], technical.file_path)
        self.assertEqual(manifest["technical_skipped"][0]["reason"], "technical runtime/config path — không phải thoại")


if __name__ == "__main__":
    unittest.main()
