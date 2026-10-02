"""Generic file-family roundtrip gate; no game or frozen corpus is required."""

from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path

from vntext.entry import Entry
from vntext.package_io import read_csv_rows_file, write_csv_rows_file, write_package
from vntext.patch import apply_translation_package


_PROOF = {
    "reader": True,
    "writer": True,
    "preflight": True,
    "reopen": True,
    "semantic_verify": True,
}


class CoverageFileRoundtripTests(unittest.TestCase):
    def test_plain_text_roundtrip_preserves_source_and_utf8_marker(self):
        with tempfile.TemporaryDirectory(prefix="vntext-file-roundtrip-") as name:
            root = Path(name)
            game = root / "game"
            package = root / "package"
            output = root / "patch"
            game.mkdir()
            source = game / "dialogue.txt"
            source.write_text("Hello player\nKeep this line\n", encoding="utf-8")
            source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
            entry = Entry(
                source_text="Hello player",
                file_path="dialogue.txt",
                context="line:0",
                import_method="plain_text_line",
                locator={"line": 0},
                patch_proof=_PROOF,
            ).finalize()
            write_package(str(package), [entry], [], {"mode": "safe"}, True, enforce_symmetry=True)
            fields, rows = read_csv_rows_file(package / "translation.csv")
            rows[0]["translation"] = "Xin chào người chơi"
            write_csv_rows_file(package / "translation.csv", fields, rows)

            apply_translation_package(
                str(package / "translation.csv"),
                str(package / "manifest.json"),
                str(game),
                str(output),
            )

            patched = output / "COPY_TO_GAME_ROOT" / "dialogue.txt"
            self.assertEqual(patched.read_text(encoding="utf-8"), "Xin chào người chơi\nKeep this line\n")
            self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(), source_hash)
            self.assertTrue((output / "patch_verification.json").is_file())


if __name__ == "__main__":
    unittest.main()
