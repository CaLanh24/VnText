"""Engine-level Ren'Py font replacement: config.font_replacement_map routes a game's Latin-only text fonts to the Vietnamese font for the language."""
import json
import tempfile
import types
import unittest
from pathlib import Path

from tests.lib.work_paths import work_temp_dir
from tests.unit import test_renpy_patch
from tests.unit.test_renpy_font_lacking_vietnamese import LATIN, VIETNAMESE, sfnt
from vntext import renpy_font_support as support
from vntext.patch_renpy import apply_renpy_translation_package
from vntext.renpy_extract import RenPyTemplateParseError, existing_translation_inventory

WORK = work_temp_dir("renpy-font-replacement-tests")
TARGET = "tl/vietnamese/vntext_font_0123456789abcdef.ttf"


def block_body(keys):
    block = support.render_font_replacement(keys, TARGET)
    return "\n".join(line[4:] for line in block.split("\n") if line.startswith("    "))


def engine_stand_in(language, base=None):
    config = types.SimpleNamespace(font_replacement_map=dict(base or {}))
    engine = types.SimpleNamespace(game=types.SimpleNamespace(preferences=types.SimpleNamespace(language=language)))
    return config, engine, {"config": config, "renpy": engine}


def run_block(keys, *, language="vietnamese", base=None):
    """Execute the generated python block exactly as Ren'Py would, against a minimal engine stand-in."""
    config, engine, namespace = engine_stand_in(language, base)
    exec(block_body(keys), namespace)
    return config, engine, namespace


class ReplacementKeyTests(unittest.TestCase):
    def test_keys_cover_spellings_of_lacking_text_fonts_only(self):
        fonts = {"fonts/Gothic.ttf": sfnt(LATIN), "gui/font/Full.ttf": sfnt(LATIN + VIETNAMESE), "gui/Icons.ttf": sfnt([0xE000]),
                 "gui/FontAwesome.ttf": sfnt([0xE000]), "gui/awesome-text.ttf": sfnt(LATIN), "a/Same.ttf": sfnt(LATIN), "b/Same.ttf": sfnt(LATIN),
                 "Odd Name é.ttf": sfnt(LATIN)}
        keys = support.replacement_keys_for_game_fonts(fonts)
        # an ambiguous basename, icon/awesome names, fonts that already cover Vietnamese and non-ASCII names are not selected
        self.assertEqual(keys, ["a/same.ttf", "b/same.ttf", "fonts/gothic.ttf", "gothic.ttf"])

    def test_generated_block_round_trips_and_any_edit_is_rejected(self):
        text = support.render_font_support(["default"], TARGET, ["fonts/gothic.ttf", "gothic.ttf"])
        found = support.parse_generated_font_replacement(text.split("\n"))
        self.assertEqual(found[2], ["fonts/gothic.ttf", "gothic.ttf"])
        for old, new in (('language == "vietnamese"', 'language != "vietnamese"'), ("            pass", "            import os"), ('# keys: [', '# keys: ["evil", ')):
            with self.subTest(old=old):
                self.assertIsNone(support.parse_generated_font_replacement(text.replace(old, new).split("\n")))

    def test_unsafe_keys_or_target_cannot_be_rendered(self):
        for keys in (['evil"]);import os;#'], ["Upper.ttf"], ["a\nb.ttf"]):
            with self.subTest(keys=keys), self.assertRaises(ValueError):
                support.render_font_replacement(keys, TARGET)
        with self.assertRaises(ValueError):
            support.render_font_replacement(["a.ttf"], "../x.ttf")
        self.assertEqual(support.render_font_replacement([], TARGET), "")


class ReplacementSemanticsTests(unittest.TestCase):
    KEYS = ["fonts/gothic.ttf", "gothic.ttf"]

    def test_every_spelling_and_bold_italic_variant_is_routed_and_flags_are_kept(self):
        config, _engine, _ns = run_block(self.KEYS)
        lookup = config.font_replacement_map.get
        for spelling in ("fonts/Gothic.ttf", "Gothic.ttf", "GOTHIC.TTF", "./fonts/gothic.ttf", "0@Gothic.ttf", "fonts\\Gothic.TTF"):
            for bold in (False, True):
                for italic in (False, True):
                    with self.subTest(spelling=spelling, bold=bold, italic=italic):
                        self.assertEqual(lookup((spelling, bold, italic), (spelling, bold, italic)), (TARGET, bold, italic))
        self.assertEqual(lookup(("fonts/Other.ttf", False, False), "DEFAULT"), "DEFAULT")        # unrelated fonts keep Ren'Py's own default
        self.assertEqual(lookup(("fonts/Other.ttf", True, False), ("fonts/Other.ttf", True, False)), ("fonts/Other.ttf", True, False))

    def test_games_own_replacement_map_is_preserved_and_chained(self):
        base = {("fonts/gothic.ttf", True, False): ("fonts/gothic-bold.ttf", False, False), (TARGET, True, False): ("tl/vietnamese/bold.ttf", False, False),
                ("Other.ttf", True, False): ("Other-Bold.ttf", False, False)}
        config, _engine, _ns = run_block(self.KEYS, base=base)
        lookup = config.font_replacement_map.get
        self.assertEqual(lookup(("Other.ttf", True, False), None), ("Other-Bold.ttf", False, False))
        # the game's bold gothic face is also Latin-only: it is replaced, then the Vietnamese font's own bold entry is chained
        self.assertEqual(lookup(("gothic.ttf", True, False), None)[0], "tl/vietnamese/bold.ttf")
        config.font_replacement_map[("later.ttf", False, False)] = ("later2.ttf", False, False)    # the game can still add entries afterwards
        self.assertEqual(lookup(("later.ttf", False, False), None), ("later2.ttf", False, False))

    def test_replacement_is_scoped_to_the_vietnamese_language(self):
        config, engine, _ns = run_block(self.KEYS)
        lookup = config.font_replacement_map.get
        self.assertEqual(lookup(("Gothic.ttf", False, False), None), (TARGET, False, False))
        for language in (None, "spanish"):
            engine.game.preferences.language = language
            self.assertEqual(lookup(("Gothic.ttf", False, False), "D"), "D")

    def test_malformed_requests_never_raise_and_rerun_is_idempotent(self):
        config, _engine, namespace = run_block(self.KEYS)
        for key in (None, 5, ("x",), (None, False, False)):
            config.font_replacement_map.get(key, "D")
        wrapped = config.font_replacement_map
        exec(block_body(self.KEYS), namespace)                           # a second language change re-wraps without losing entries
        self.assertIsNot(config.font_replacement_map, wrapped)
        self.assertEqual(config.font_replacement_map.get(("Gothic.ttf", False, False), None), (TARGET, False, False))


class ReplacementOverlayRoundTripTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._prior = tempfile.tempdir
        tempfile.tempdir = str(WORK)

    @classmethod
    def tearDownClass(cls):
        tempfile.tempdir = cls._prior

    def test_generated_overlay_is_accepted_by_the_existing_translation_inventory_and_foreign_python_is_not(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            target = root / "game/tl/vietnamese/vntext.rpy"
            target.parent.mkdir(parents=True)
            generated = support.render_font_support(["default"], TARGET, ["gothic.ttf"])
            strings = 'translate vietnamese strings:\n\n    old "Open"\n    new "Mở"\n'
            target.write_text(generated + strings, encoding="utf-8")
            self.assertEqual(existing_translation_inventory(root)["strings"]["Open"]["translation"], "Mở")
            target.write_text(generated.replace("            pass", "            import os") + strings, encoding="utf-8")
            with self.assertRaises(RenPyTemplateParseError):
                existing_translation_inventory(root)
            target.write_text("translate vietnamese python:\n    config.x = 1\n", encoding="utf-8")
            with self.assertRaises(RenPyTemplateParseError):
                existing_translation_inventory(root)

    def test_patch_emits_the_block_and_a_second_patch_replaces_only_that_generated_block(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            game, csv, manifest = test_renpy_patch.RenPyPatchTests._package(None, base)
            (game / "game/fonts").mkdir()
            (game / "game/fonts/Gothic.ttf").write_bytes(sfnt(LATIN))
            apply_renpy_translation_package(str(csv), str(manifest), str(game), str(base / "out1"))
            overlay = (base / "out1/COPY_TO_GAME_ROOT/game/tl/vietnamese/vntext.rpy").read_text(encoding="utf-8")
            self.assertEqual(overlay.count(support.REPLACEMENT_BEGIN), 1)
            evidence = json.loads((base / "out1/font_preflight.json").read_text(encoding="utf-8"))
            self.assertEqual(evidence["font_replacement"]["keys"], ["fonts/gothic.ttf", "gothic.ttf"])
            self.assertIn("styles, screen text properties", evidence["font_replacement"]["covers"])
            for path in (base / "out1/COPY_TO_GAME_ROOT").rglob("*"):         # install the overlay, then add another Latin-only font and patch again
                if path.is_file():
                    destination = game / path.relative_to(base / "out1/COPY_TO_GAME_ROOT")
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    destination.write_bytes(path.read_bytes())
            (game / "game/fonts/Second.ttf").write_bytes(sfnt(LATIN))
            apply_renpy_translation_package(str(csv), str(manifest), str(game), str(base / "out2"))
            again = (base / "out2/COPY_TO_GAME_ROOT/game/tl/vietnamese/vntext.rpy").read_text(encoding="utf-8")
            self.assertEqual(again.count(support.REPLACEMENT_BEGIN), 1)
            self.assertEqual(support.parse_generated_font_replacement(again.split("\n"))[2], ["fonts/gothic.ttf", "fonts/second.ttf", "gothic.ttf", "second.ttf"])
            self.assertIn("translate vietnamese start_a:", again)


if __name__ == "__main__":
    unittest.main()
