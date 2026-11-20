"""A preferred font that lacks only symbols (e.g. U+266B) keeps its place; the bundled verified font supplies just those glyphs, text untouched."""
import json
import tempfile
import unittest
from pathlib import Path

from tests.lib.work_paths import work_temp_dir
from tests.unit import test_renpy_patch
from tests.unit.test_renpy_font_lacking_vietnamese import LATIN, VIETNAMESE, sfnt
from vntext import renpy_font_support as support
from vntext.app_tasks import _validate_renpy_overlay_output
from vntext.patch_renpy import RenPyPatchError, apply_renpy_translation_package

WORK = work_temp_dir("renpy-glyph-fallback-tests")
NOTE = 0x266B
COMBINING = list(range(0x300, 0x370))
BUNDLED_NAME = support._FALLBACK_NAME


class RangeTests(unittest.TestCase):
    def test_symbols_collapse_into_ranges_and_letters_or_fragments_are_refused(self):
        self.assertEqual(support.glyph_fallback_ranges([NOTE, NOTE + 1, 0x2605]), [(0x2605, 0x2605), (NOTE, NOTE + 1)])
        self.assertIsNone(support.glyph_fallback_ranges([NOTE, ord("ư")]), "a Latin letter is never mixed in glyph by glyph")
        self.assertIsNone(support.glyph_fallback_ranges([]))
        self.assertIsNone(support.glyph_fallback_ranges([0x2000 + 3 * index for index in range(support.MAX_FALLBACK_RANGES + 1)]))

    def test_group_head_round_trips_and_every_edit_is_rejected(self):
        font = "tl/vietnamese/vntext_font_0123456789abcdef.ttf"
        head = support.render_font_support(["default", "say_dialogue"], font, ["gothic.ttf"], (BUNDLED_NAME, [(NOTE, NOTE)]))
        self.assertIn(f'font FontGroup().add("{BUNDLED_NAME}", 0x266B, 0x266B).add("{font}", None, None)', head)
        text = head + "translate vietnamese strings:\n"
        self.assertEqual(support.split_generated_head(text), (head, "translate vietnamese strings:\n"))
        widened = text.replace("0x266B, 0x266B", "0x266B, 0x26FF")           # ranges are generated data, like style names: still a structurally authentic head
        self.assertIsNotNone(support.split_generated_head(widened))
        extra = f'.add("{BUNDLED_NAME}", 0x30, 0x30)'
        self.assertIsNone(support.split_generated_head(text.replace("0x266B, 0x266B)", "0x266B, 0x266B)" + extra * 40)))      # over the bounded range count
        for label, bad in (("foreign fallback", text.replace(BUNDLED_NAME, "tl/vietnamese/vntext_font_ffffffffffffffff.ttf")),
                           ("extra call", text.replace(', None, None)', ', None, None).evil()', 1)), ("one style differs", text.replace("0x266B, 0x266B", "0x266C, 0x266C", 1))):
            with self.subTest(label):
                self.assertIsNone(support.split_generated_head(bad))

    def test_unsafe_fallback_cannot_be_rendered(self):
        for fallback in (("evil.ttf", [(1, 2)]), (BUNDLED_NAME, []), (BUNDLED_NAME, [(0x30, 0x30)] * 40)):
            with self.subTest(fallback=fallback), self.assertRaises(ValueError):
                support.render_font_support(["default"], "tl/vietnamese/vntext_font_0123456789abcdef.ttf", (), fallback)


class PatchWithSymbolTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._prior = tempfile.tempdir
        tempfile.tempdir = str(WORK)

    @classmethod
    def tearDownClass(cls):
        tempfile.tempdir = cls._prior

    def _package(self, base, covered):
        game, csv, manifest = test_renpy_patch.RenPyPatchTests._package(None, base)
        raw = csv.read_bytes()
        self.assertIn("Mở".encode(), raw)
        csv.write_bytes(raw.replace("Mở".encode(), "Mở ♫".encode()))
        preferred = base / "Preferred.ttf"
        preferred.write_bytes(sfnt(LATIN + VIETNAMESE + COMBINING + covered))
        return game, csv, manifest, preferred

    def test_preferred_font_is_kept_and_only_the_missing_symbol_comes_from_the_verified_fallback(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            game, csv, manifest, preferred = self._package(base, [])
            apply_renpy_translation_package(str(csv), str(manifest), str(game), str(base / "out"), replacement_font=str(preferred))
            evidence = json.loads((base / "out/font_preflight.json").read_text(encoding="utf-8"))
            self.assertEqual(evidence["glyph_status"], "PASS_WITH_FALLBACK")
            self.assertEqual(evidence["missing"], [])
            self.assertEqual([item.split()[0] for item in evidence["primary_missing"]], ["U+266B"])
            self.assertEqual(evidence["glyph_fallback"]["sha256"], support.FALLBACK_SHA256)
            payload = base / "out/COPY_TO_GAME_ROOT"
            overlay = (payload / "game/tl/vietnamese/vntext.rpy").read_text(encoding="utf-8")
            self.assertIn("Mở ♫", overlay)                                       # the translation is untouched
            self.assertIn(f'.add("{BUNDLED_NAME}", 0x266B, 0x266B).add("tl/vietnamese/vntext_font_', overlay)
            self.assertTrue((payload / "game" / BUNDLED_NAME).is_file())
            self.assertTrue((payload / "game" / BUNDLED_NAME).with_suffix(".license.txt").is_file())
            self.assertIn(evidence["payload_font"], {path.relative_to(payload).as_posix() for path in payload.rglob("*") if path.is_file()})
            _validate_renpy_overlay_output(base / "out")                         # the product's own layout validator accepts exactly this payload
            manifest_data = json.loads((base / "out/patch_manifest.json").read_text(encoding="utf-8")) if (base / "out/patch_manifest.json").is_file() else None
            if manifest_data:
                self.assertIn(evidence["glyph_fallback"]["payload_font"], {item["path"] for item in manifest_data["files"]})

    def test_a_second_patch_over_the_fallback_overlay_keeps_it(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            game, csv, manifest, preferred = self._package(base, [])
            apply_renpy_translation_package(str(csv), str(manifest), str(game), str(base / "out1"), replacement_font=str(preferred))
            for path in (base / "out1/COPY_TO_GAME_ROOT").rglob("*"):
                if path.is_file():
                    destination = game / path.relative_to(base / "out1/COPY_TO_GAME_ROOT")
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    destination.write_bytes(path.read_bytes())
            apply_renpy_translation_package(str(csv), str(manifest), str(game), str(base / "out2"), replacement_font=str(preferred))
            again = (base / "out2/COPY_TO_GAME_ROOT/game/tl/vietnamese/vntext.rpy").read_text(encoding="utf-8")
            self.assertEqual(again.count("# VNText language-scoped text font support v1"), 1)
            self.assertIn(".add(\"" + BUNDLED_NAME, again)
            self.assertIn("Mở ♫", again)

    def test_a_font_that_already_has_the_symbol_needs_no_fallback(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            game, csv, manifest, preferred = self._package(base, [NOTE])
            apply_renpy_translation_package(str(csv), str(manifest), str(game), str(base / "out"), replacement_font=str(preferred))
            evidence = json.loads((base / "out/font_preflight.json").read_text(encoding="utf-8"))
            self.assertNotIn("glyph_fallback", evidence)
            self.assertEqual(evidence["glyph_status"], "PASS")

    def test_missing_letters_are_still_rejected_not_mixed(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            game, csv, manifest, preferred = self._package(base, [NOTE])
            preferred.write_bytes(sfnt(LATIN + COMBINING + [NOTE]))                            # lacks the Vietnamese letters, not just a symbol
            apply_renpy_translation_package(str(csv), str(manifest), str(game), str(base / "out1"))   # an overlay already exists after this
            for path in (base / "out1/COPY_TO_GAME_ROOT").rglob("*"):
                if path.is_file():
                    destination = game / path.relative_to(base / "out1/COPY_TO_GAME_ROOT")
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    destination.write_bytes(path.read_bytes())
            with self.assertRaisesRegex(RenPyPatchError, "lacks translated glyphs"):
                apply_renpy_translation_package(str(csv), str(manifest), str(game), str(base / "out2"), replacement_font=str(preferred))


if __name__ == "__main__":
    unittest.main()
