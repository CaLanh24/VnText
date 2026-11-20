"""Re-patching over an overlay written by an earlier VNText release: authentic generated heads are upgraded in place, anything else is rejected."""
import hashlib
import tempfile
import unittest
from pathlib import Path

from tests.lib.work_paths import work_temp_dir
from tests.unit import test_renpy_patch
from tests.unit.test_renpy_font_lacking_vietnamese import LATIN, sfnt
from vntext import renpy_font_support as support
from vntext.patch_renpy import RenPyPatchError, apply_renpy_translation_package

WORK = work_temp_dir("renpy-generated-head-upgrade")
FONT = "tl/vietnamese/vntext_font_0123456789abcdef.ttf"
STRINGS = 'translate vietnamese strings:\n\n    old "Open"\n    new "Mở"\n'
# SHA-256 of the exact heads rendered by the released v0.1.24 / v0.1.25 sources for the arguments below (taken from the tagged renderers).
RELEASED_024 = "76f5228d524adaa5a7e20c6649b7f77acc00a4c5e7fa9ec7b888468008c41500"
RELEASED_025 = "83a7cdb8158640de7e0a3a17773003c8d70533ac43e06c851a0a6a5a138ffd58"
KEYS = ["fonts/gothic.ttf", "gothic.ttf"]
BUNDLED = f"tl/vietnamese/vntext_font_{support.FALLBACK_SHA256[:16]}.ttf"


def head_024(font=FONT):
    return "\n".join(["# VNText language-scoped text font support v1"] + [part for name in ("default", "say_dialogue") for part in (f"translate vietnamese style {name}:", f'    font "{font}"', "")]) + "\n"


def head_025(font=FONT):
    return head_024(font) + support.render_font_replacement(KEYS, font, guard=False)


class ReleasedHeadTests(unittest.TestCase):
    def test_the_reconstructed_released_heads_are_the_released_bytes(self):
        self.assertEqual(hashlib.sha256(head_024().encode()).hexdigest(), RELEASED_024)
        self.assertEqual(hashlib.sha256(head_025().encode()).hexdigest(), RELEASED_025)

    def test_every_known_release_head_splits_and_keeps_the_users_translations(self):
        for label, head in (("0.1.24", head_024()), ("0.1.25", head_025()), ("current", head_024() + support.render_font_replacement(KEYS, FONT))):
            with self.subTest(label):
                self.assertEqual(support.split_generated_head(head + STRINGS), (head, STRINGS))

    def test_foreign_edits_are_never_split(self):
        for label, text in (
            ("edited block", head_025().replace("            pass", "            import os") + STRINGS),
            ("foreign font", head_024().replace("tl/vietnamese/vntext_font_0123456789abcdef.ttf", "evil/x.ttf") + STRINGS),
            ("extra property", head_024().replace('    font "', '    size 99\n    font "', 1) + STRINGS),
            ("renamed style", head_024().replace("say_dialogue", "say dialogue") + STRINGS),
            ("mixed fonts", head_024().replace("vntext_font_0123456789abcdef", "vntext_font_fedcba9876543210", 1) + STRINGS),
            ("no header", STRINGS),
        ):
            with self.subTest(label):
                self.assertIsNone(support.split_generated_head(text))


class RepatchOverReleasedOverlayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._prior = tempfile.tempdir
        tempfile.tempdir = str(WORK)

    @classmethod
    def tearDownClass(cls):
        tempfile.tempdir = cls._prior

    def _repatch(self, existing_head, *, font_choice=None):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            game, csv, manifest = test_renpy_patch.RenPyPatchTests._package(None, base)
            (game / "game/fonts").mkdir()
            (game / "game/fonts/Gothic.ttf").write_bytes(sfnt(LATIN))
            overlay = game / "game/tl/vietnamese/vntext.rpy"
            overlay.parent.mkdir(parents=True)
            overlay.write_text(existing_head + STRINGS, encoding="utf-8")
            kwargs = {"replacement_font": str(font_choice)} if font_choice else {}
            apply_renpy_translation_package(str(csv), str(manifest), str(game), str(base / "out"), **kwargs)
            return (base / "out/COPY_TO_GAME_ROOT/game/tl/vietnamese/vntext.rpy").read_text(encoding="utf-8")

    def test_a_0_1_24_style_only_overlay_is_upgraded_and_translations_survive(self):
        text = self._repatch(head_024(BUNDLED))
        self.assertEqual(text.count(support.REPLACEMENT_BEGIN), 1)
        self.assertIn('old "Open"', text)
        self.assertEqual(text.count("# VNText language-scoped text font support v1"), 1)

    def test_a_released_0_1_25_overlay_is_upgraded_to_the_guarded_block(self):
        text = self._repatch(head_025(BUNDLED))
        self.assertEqual(text.count(support.REPLACEMENT_BEGIN), 1)
        self.assertIn("_vntext_font_guard", text)
        self.assertIn('old "Open"', text)

    def test_a_changed_font_choice_replaces_the_old_generated_head_only(self):
        font = Path(__file__).resolve().parents[2] / "wpf_app/VNText.Studio.App/Assets/Fonts/Inter-Regular.ttf"
        text = self._repatch(head_025(BUNDLED), font_choice=font)
        self.assertNotIn(BUNDLED, text)
        self.assertEqual(text.count(support.REPLACEMENT_BEGIN), 1)
        self.assertIn('old "Open"', text)

    def test_a_foreign_edit_in_the_generated_head_is_still_rejected(self):
        with self.assertRaises(RenPyPatchError):
            self._repatch(head_025(BUNDLED).replace("            pass", "            import os"))


if __name__ == "__main__":
    unittest.main()
