import unittest

from vntext.renpy_font_support import (
    SCALE_BEGIN, generated_font_scale, normalize_font_scale, render_font_scale, render_font_support, split_generated_head,
)

FONT = "tl/vietnamese/vntext_font_0123456789abcdef.ttf"


class FontScaleTests(unittest.TestCase):
    def test_normalize_accepts_range_and_treats_default_as_none(self):
        self.assertIsNone(normalize_font_scale(None))
        self.assertIsNone(normalize_font_scale(""))
        self.assertIsNone(normalize_font_scale("1"))
        self.assertEqual(normalize_font_scale("0.9"), 0.9)
        self.assertEqual(normalize_font_scale(1.2349), 1.23)
        for bad in ("0.5", 2, "abc", "nan", "-1"):
            with self.assertRaises(ValueError, msg=str(bad)):
                normalize_font_scale(bad)

    def test_block_scales_only_the_generated_font(self):
        block = render_font_scale(FONT, 0.9)
        self.assertEqual(block, f'{SCALE_BEGIN}\ntranslate vietnamese python:\n    config.ftfont_scale["{FONT}"] = 0.9\n# VNText font scale end\n')
        self.assertEqual(render_font_scale(FONT, 1.0), "")
        with self.assertRaises(ValueError):
            render_font_scale("DejaVuSans.ttf", 0.9)   # an engine/game font name would also rescale other languages

    def test_head_round_trips_and_keeps_user_translations(self):
        head = render_font_support(["gui_text"], FONT, [], None, 1.15)
        tail = 'translate vietnamese strings:\n    old "Hi"\n    new "Chào"\n'
        split = split_generated_head(head + tail)
        self.assertIsNotNone(split)
        self.assertEqual(split[1], tail)
        self.assertEqual(generated_font_scale(split[0]), 1.15)
        # without a scale the head is the previous release's exact form
        plain = render_font_support(["gui_text"], FONT, [], None, None)
        self.assertNotIn("ftfont_scale", plain)
        self.assertEqual(split_generated_head(plain + tail)[1], tail)

    def test_edited_scale_block_is_refused(self):
        head = render_font_support(["gui_text"], FONT, [], None, 0.9)
        self.assertIsNone(split_generated_head(head.replace("= 0.9", "= 9.9")))
        self.assertIsNone(split_generated_head(head.replace(FONT + '"] =', 'other.ttf"] =')))


class PatchBuilderTests(unittest.TestCase):
    def test_out_of_range_scale_builds_nothing(self):
        import tempfile
        from pathlib import Path
        from tests.unit import test_renpy_patch
        from vntext.patch_renpy import RenPyPatchError, apply_renpy_translation_package

        with tempfile.TemporaryDirectory() as temp:
            game, csv, manifest = test_renpy_patch.RenPyPatchTests._package(None, Path(temp))
            out = Path(temp) / "out"
            with self.assertRaises(RenPyPatchError):
                apply_renpy_translation_package(str(csv), str(manifest), str(game), str(out), font_scale="9")
            self.assertFalse((out / "COPY_TO_GAME_ROOT").exists())


if __name__ == "__main__":
    unittest.main()
