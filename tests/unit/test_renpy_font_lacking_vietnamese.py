"""A game's own Latin-only text font (e.g. a gothic face) must reach the Vietnamese style overlay even when the style name is unconventional."""
import hashlib
import struct
import tempfile
import unittest
from pathlib import Path

from tests.lib.work_paths import work_temp_dir
from tests.unit.test_renpy_font_cmap_audit import font
from vntext import renpy_font_support as support

WORK = work_temp_dir("renpy-font-lacking-tests")


def sfnt(codepoints):
    groups = b"".join(struct.pack(">LLL", cp, cp, 3 + index) for index, cp in enumerate(sorted(set(codepoints))))
    sub = struct.pack(">HHLLL", 12, 0, 16 + len(groups), 0, len(set(codepoints))) + groups
    return font(sub, encoding=10, glyphs=1200)


LATIN = [ord(c) for c in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"]
VIETNAMESE = [ord(c) for c in support._VIETNAMESE_PROBE]


class LackingFontTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._prior = tempfile.tempdir
        tempfile.tempdir = str(WORK)

    @classmethod
    def tearDownClass(cls):
        tempfile.tempdir = cls._prior

    def test_only_latin_text_fonts_without_vietnamese_are_selected(self):
        fonts = {"fonts/Gothic.ttf": sfnt(LATIN), "gui/font/Full.ttf": sfnt(LATIN + VIETNAMESE), "gui/icons.ttf": sfnt([0xE000, 0xE001]),
                 "fonts/broken.ttf": b"not a font", "Mixed/Case.OTF": sfnt(LATIN)}
        self.assertEqual(support.text_fonts_lacking_vietnamese(fonts), {"fonts/gothic.ttf", "mixed/case.otf"})

    def test_literal_font_of_any_style_name_is_selected_only_for_a_lacking_font(self):
        script = '''style menu_title:
    font "fonts/Gothic.ttf"
style narrator_box:
    font 'Fonts/Gothic.TTF'  # same file, other spelling
style fancy:
    font "gui/font/Full.ttf"
style glyph_title:
    font "fonts/Gothic.ttf"
style plain:
    font "fonts/other.ttf"
screen s():
    text "x" font "fonts/Gothic.ttf"
'''
        self.assertEqual(support.text_font_styles([script]), ["default"])                                           # nothing is guessed without font evidence
        chosen = support.text_font_styles([script], {"fonts/gothic.ttf"})
        self.assertEqual(chosen, ["default", "menu_title", "narrator_box"])                                        # glyph/icon names and other fonts stay untouched

    def test_prepare_font_support_reads_game_fonts_loose_and_adds_the_style_with_bounded_evidence(self):
        bundled = Path(__file__).resolve().parents[2] / "vntext/fonts/DejaVuSans.ttf"
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "game/fonts").mkdir(parents=True)
            (root / "game/script.rpy").write_text('style menu_title:\n    font "fonts/Gothic.ttf"\nlabel start:\n    "x"\n', encoding="utf-8")
            gothic = sfnt(LATIN)
            (root / "game/fonts/Gothic.ttf").write_bytes(gothic)
            snapshots = {}
            rendered = support.prepare_font_support(root, snapshots, {}, bundled)
            self.assertIn("translate vietnamese style menu_title:", rendered)
            self.assertIn("translate vietnamese style default:", rendered)
            self.assertEqual(snapshots[root / "game/fonts/Gothic.ttf"], hashlib.sha256(gothic).hexdigest())     # the font is bound to the source CAS
            # a font that already has Vietnamese leaves the style alone
            (root / "game/fonts/Gothic.ttf").write_bytes(sfnt(LATIN + VIETNAMESE))
            self.assertNotIn("translate vietnamese style menu_title:", support.prepare_font_support(root, {}, {}, bundled))


if __name__ == "__main__":
    unittest.main()
