"""Scan-time and patch-time per-font / per-image outcomes shown by the app (no JSON reading needed)."""
import json
import tempfile
import unittest
from pathlib import Path

from tests.lib.work_paths import work_temp_dir
from tests.unit import test_renpy_patch
from tests.unit.test_renpy_font_lacking_vietnamese import LATIN, VIETNAMESE, sfnt
from vntext.patch_renpy import apply_renpy_translation_package
from vntext.renpy_asset_scan import font_outcomes, outcome_counts, scan_renpy_assets

WORK = work_temp_dir("renpy-asset-scan-tests")
COMBINING = list(range(0x300, 0x370))


class AssetScanTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._prior = tempfile.tempdir
        tempfile.tempdir = str(WORK)

    @classmethod
    def tearDownClass(cls):
        tempfile.tempdir = cls._prior

    def _game(self, base):
        game = base / "game"
        (game / "fonts").mkdir(parents=True)
        (game / "fonts/Gothic.ttf").write_bytes(sfnt(LATIN))                                   # Latin-only text font
        (game / "fonts/Full.ttf").write_bytes(sfnt(LATIN + VIETNAMESE + COMBINING))             # already Vietnamese
        (game / "fonts/FontAwesome.ttf").write_bytes(sfnt([0xE000]))                           # icon font
        (game / "fonts/pack.ttc").write_bytes(b"ttcf")
        (game / "fonts/web.woff2").write_bytes(b"wOF2")
        (game / "gui").mkdir()
        (game / "gui/menu.png").write_bytes(b"")
        (game / "screens.rpy").write_text("screen menu():\n    imagebutton:\n        idle \"gui/menu.png\"\n", encoding="utf-8")
        return base

    def test_a_non_renpy_folder_is_not_scanned(self):
        with tempfile.TemporaryDirectory() as temp:
            self.assertIsNone(scan_renpy_assets(temp))

    def test_scan_reports_every_font_with_an_outcome_and_a_reason(self):
        with tempfile.TemporaryDirectory() as temp:
            result = scan_renpy_assets(self._game(Path(temp)))
        rows = {row["source"]: row for row in result["fonts"]["assets"]}
        self.assertEqual(rows["fonts/Gothic.ttf"]["outcome"], "WILL_REPLACE")
        self.assertEqual(rows["fonts/Full.ttf"]["outcome"], "OK")
        self.assertEqual(rows["fonts/FontAwesome.ttf"]["outcome"], "PRESERVED")
        for name in ("fonts/pack.ttc", "fonts/web.woff2"):
            self.assertEqual(rows[name]["outcome"], "UNRESOLVED")
            self.assertTrue(rows[name]["why"])
        self.assertEqual(result["fonts"]["outcomes"], outcome_counts(result["fonts"]["assets"]))
        self.assertIn("Not proof", result["fonts"]["coverage_scope"])
        self.assertIn("discovered", result["images"]["coverage_scope"])
        self.assertEqual(result["images"]["candidates"][0]["asset"], "gui/menu.png")
        json.dumps(result)                                                                      # the report must serialise as-is

    def test_built_patch_marks_routed_fonts_replaced_and_unrouted_ones_unresolved(self):
        assets = [{"source": "fonts/Gothic.ttf", "status": "NEEDS_VIETNAMESE_FONT", "why": "x", "static_use_count": 1},
                  {"source": "a/Same.ttf", "status": "NEEDS_VIETNAMESE_FONT", "why": "x", "static_use_count": 0}]
        rows = {row["source"]: row for row in font_outcomes(assets, ["fonts/gothic.ttf", "gothic.ttf"], built=True)}
        self.assertEqual(rows["fonts/Gothic.ttf"]["outcome"], "REPLACED")
        self.assertEqual(rows["a/Same.ttf"]["outcome"], "UNRESOLVED")
        self.assertIn("no safe replacement key", rows["a/Same.ttf"]["why"])

    def test_the_real_patch_records_outcomes_the_dialog_can_show(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            game, csv, manifest = test_renpy_patch.RenPyPatchTests._package(None, base)
            (game / "game/fonts").mkdir()
            (game / "game/fonts/Gothic.ttf").write_bytes(sfnt(LATIN))
            (game / "game/fonts/web.woff2").write_bytes(b"wOF2")
            apply_renpy_translation_package(str(csv), str(manifest), str(game), str(base / "out"))
            evidence = json.loads((base / "out/font_preflight.json").read_text(encoding="utf-8"))
        rows = {row["source"]: row for row in evidence["font_outcomes"]}
        self.assertEqual(rows["fonts/Gothic.ttf"]["outcome"], "REPLACED")
        self.assertEqual(rows["fonts/web.woff2"]["outcome"], "UNRESOLVED")
        self.assertEqual(evidence["font_outcome_counts"]["REPLACED"], 1)


if __name__ == "__main__":
    unittest.main()
