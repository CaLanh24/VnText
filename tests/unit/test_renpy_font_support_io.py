"""File/hash/shadowing guards around the static font support planner."""
import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tests.lib.work_paths import work_temp_dir
from vntext import renpy_font_support as support


class FontSupportIoTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=work_temp_dir("font-support-io"))
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.font = self.root / "renpy/common/DejaVuSans.ttf"
        self.font.parent.mkdir(parents=True)
        self.font.write_bytes(b"fixture-font")
        self.script = self.root / "game/screens.rpy"
        self.script.parent.mkdir()
        self.script.write_text('style say_dialogue:\n    font gui.text_font\n', encoding='utf-8')
        self.font_hash = hashlib.sha256(self.font.read_bytes()).hexdigest()

    def plan(self, snapshots=None):
        with patch.object(support, "FALLBACK_SHA256", self.font_hash):
            return support.prepare_font_support(self.root, snapshots if snapshots is not None else {}, {})

    def test_verified_font_and_all_consumed_sources_join_writer_cas(self):
        snapshots = {}
        rendered = self.plan(snapshots)
        self.assertIn('translate vietnamese style say_dialogue:', rendered)
        self.assertEqual(snapshots[self.font], self.font_hash)
        self.assertEqual(snapshots[self.script], hashlib.sha256(self.script.read_bytes()).hexdigest())

    def test_unknown_or_missing_font_does_not_inject_support(self):
        self.assertEqual(support.prepare_font_support(self.root, {}, {}), '')
        self.font.unlink()
        self.assertEqual(self.plan(), '')

    def test_game_asset_shadowing_engine_font_opts_out(self):
        (self.root / 'game/DejaVuSans.ttf').write_bytes(b'foreign-game-font')
        self.assertEqual(self.plan(), '')

    def test_source_change_after_text_preflight_is_not_overwritten_in_cas(self):
        snapshots = {self.script: '0' * 64}
        with self.assertRaisesRegex(ValueError, 'changed after text preflight'):
            self.plan(snapshots)
        self.assertEqual(snapshots[self.script], '0' * 64)

    def test_script_bounds_are_enforced(self):
        with patch.object(support, 'MAX_SCRIPT_BYTES', 1):
            with self.assertRaisesRegex(ValueError, 'exceeds bounds'):
                self.plan()

    def test_translation_and_icon_fonts_are_not_rewritten(self):
        target = self.root / 'game/tl/other/foreign.rpy'
        target.parent.mkdir(parents=True)
        target.write_text('style foreign:\n    font gui.text_font\n', encoding='utf-8')
        self.script.write_text('style glyph:\n    font "icons.ttf"\n', encoding='utf-8')
        rendered = self.plan()
        self.assertNotIn('style foreign:', rendered)
        self.assertNotIn('style glyph:', rendered)
        self.assertEqual(target.read_text(encoding='utf-8'), 'style foreign:\n    font gui.text_font\n')


if __name__ == '__main__':
    unittest.main()
