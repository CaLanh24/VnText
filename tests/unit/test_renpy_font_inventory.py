"""Font mapping/glyph inventory is inert and keeps unsupported mappings explicit."""
import hashlib
from pathlib import Path
import tempfile
import unittest
from tests.lib.work_paths import work_temp_dir
from vntext.renpy_font_inventory import inspect_font_mapping
from vntext.renpy_font_support import text_font_styles


class FontInventoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=work_temp_dir("font-inventory")); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name); (self.root / "game/fonts").mkdir(parents=True)
        self.font = Path(__file__).resolve().parents[2] / "wpf_app/VNText.Studio.App/Assets/Fonts/Inter-Regular.ttf"

    def test_text_icon_variants_tags_and_compiled_unknown_are_reported_without_execution(self):
        script = '''define gui.text_font = "fonts/body.ttf"
define gui.icon_font = "fonts/icons.ttf"
style say_dialogue:
    font gui.text_font
    bold True
    italic False
style icon:
    font gui.icon_font
style unknown:
    font lookup_font()
label start:
    "{font=fonts/body.ttf}Xin chào{/font}"
'''
        (self.root / "game/screens.rpy").write_text(script, encoding="utf-8")
        (self.root / "game/fonts/body.ttf").write_bytes(self.font.read_bytes())
        (self.root / "game/unknown.rpyc").write_bytes(b"opaque compiled mapping; never execute")
        snapshots = {}; result = inspect_font_mapping(self.root, ["Đặng đợi Ấn"], snapshots, {})
        styles = {item["style"]: item for item in result["styles"]}
        self.assertEqual(styles["say_dialogue"]["font_sha256"], hashlib.sha256(self.font.read_bytes()).hexdigest())
        self.assertEqual(styles["say_dialogue"]["bold"], "True")
        self.assertEqual(styles["icon"]["purpose"], "ICON_HINT_PRESERVED")
        self.assertEqual(styles["unknown"]["mapping_status"], "UNRESOLVED")
        self.assertEqual(result["compiled_without_source_count"], 1)
        self.assertEqual(result["font_tags"][0]["mapping_status"], "EXPLICIT_TAG_NOT_REPLACED")
        self.assertNotIn("icon", text_font_styles([script]))
        self.assertIn(self.root / "game/screens.rpy", snapshots)

    def test_archive_font_is_audited_and_container_hash_is_a_precondition(self):
        from tests.unit.test_renpy_archive import write_rpa
        archive = self.root / "game/assets.rpa"
        write_rpa(archive, {"fonts/body.ttf": self.font.read_bytes(), "gui.rpy": b'define gui.text_font = "fonts/body.ttf"\nstyle say_dialogue:\n    font gui.text_font\n'})
        snapshots = {}; result = inspect_font_mapping(self.root, ["Xin chào Đặng"], snapshots, {})
        self.assertEqual(result["fonts"][0]["glyph_status"], "PASS")
        self.assertEqual(result["styles"][0]["font_source"], "assets.rpa::fonts/body.ttf")
        self.assertEqual(snapshots[archive], hashlib.sha256(archive.read_bytes()).hexdigest())
        with self.assertRaisesRegex(ValueError, "source changed"):
            inspect_font_mapping(self.root, ["Xin chào"], {archive: "0" * 64}, {})
