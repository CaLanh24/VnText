from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from vntext.renpy_extract import extract_loose_source
from vntext.renpy_toolchain import RenPyToolchainError, install_managed_sdk, validate_sdk


class RenPyExtractTests(unittest.TestCase):
    def test_dialogue_identity_comes_only_from_template_and_duplicates_remain_distinct(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); game = root / "game"; game.mkdir()
            (game / "script.rpy").write_text('label start:\n    "Come here."\n    e "Come here."\n    menu:\n        "Open the door":\n            pass\n    $ status = _("Ready: %(count)d")\n', encoding="utf-8")
            template = game / "tl" / "vietnamese"; template.mkdir(parents=True)
            (template / "script.rpy").write_text('translate vietnamese start_a:\n    # "Come here."\n    ""\ntranslate vietnamese start_b:\n    # e "Come here."\n    e ""\n', encoding="utf-8")
            main, review, _stats = extract_loose_source(root, template_root=template)
            dialogue = [row for row in main if row.import_method == "renpy_dialogue"]
            self.assertEqual([row.locator["native_id"] for row in dialogue], ["start_a", "start_b"])
            self.assertNotEqual(dialogue[0].key, dialogue[1].key)
            self.assertEqual([row.source_text for row in main if row.import_method == "renpy_string"], ["Open the door", "Ready: %(count)d"])
            self.assertEqual(review, [])

    def test_missing_template_never_guesses_dialogue_id(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); game = root / "game"; game.mkdir()
            (game / "script.rpy").write_text('label start:\n    "Hello"\n', encoding="utf-8")
            main, review, _stats = extract_loose_source(root)
            self.assertEqual(main, [])
            self.assertEqual(len(review), 1)
            self.assertEqual(review[0].locator["native_id"], "")

    def test_sdk_validation_is_pinned_and_rejects_wrong_version(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); (root / "lib" / "py3-windows-x86_64").mkdir(parents=True)
            (root / "renpy.py").write_text("# placeholder", encoding="utf-8")
            (root / "lib" / "py3-windows-x86_64" / "python.exe").write_bytes(b"")
            with patch("vntext.renpy_toolchain.subprocess.run") as run:
                run.return_value.returncode = 0; run.return_value.stdout = "Ren'Py 8.5.3"; run.return_value.stderr = ""
                self.assertEqual(validate_sdk(root).version, "8.5.3")
                run.return_value.stdout = "Ren'Py 8.6.0"
                with self.assertRaises(RenPyToolchainError):
                    validate_sdk(root)

    def test_managed_install_rejects_unverified_archive_before_extract(self):
        with tempfile.TemporaryDirectory() as temp:
            archive = Path(temp) / "sdk.zip"; archive.write_bytes(b"not an sdk")
            with self.assertRaises(RenPyToolchainError):
                install_managed_sdk(archive)
