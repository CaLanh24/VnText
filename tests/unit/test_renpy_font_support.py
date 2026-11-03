"""Static font selection is language-scoped; icon and dynamic styles survive."""
import unittest

from vntext.renpy_font_support import render_font_support, text_font_styles


class FontSupportTests(unittest.TestCase):
    def test_only_explicit_gui_text_font_styles_are_selected(self):
        script = '''style dialogue:
    font gui.text_font
style heading is text:
    font gui.interface_text_font
style glyph:
    font "icons.ttf"
style dynamic:
    font lookup_font()
screen ignored():
    text "hello":
        font gui.text_font
'''
        self.assertEqual(text_font_styles([script]), ["default", "dialogue", "heading"])

    def test_gui_text_properties_and_comments_are_supported(self):
        script = '''style say_dialogue:
    properties gui.text_properties("dialogue")
style say_label is default: # speaker
    font gui.name_text_font # static reference
'''
        self.assertEqual(text_font_styles([script]), ["default", "say_dialogue", "say_label"])

    def test_nested_python_or_translation_styles_are_not_promoted(self):
        script = '''init python:
    style fake:
        font gui.text_font
translate other style unrelated:
    font gui.text_font
'''
        self.assertEqual(text_font_styles([script]), ["default"])

    def test_output_only_changes_vietnamese_styles_not_gui_or_config(self):
        rendered = render_font_support(["say_dialogue", "default", "say_dialogue"])
        self.assertEqual(rendered.count("translate vietnamese style say_dialogue:"), 1)
        self.assertNotIn("gui.", rendered)
        self.assertNotIn("config.", rendered)
        self.assertNotIn("init ", rendered)
        self.assertNotIn("translate None", rendered)
        self.assertIn('    font "DejaVuSans.ttf"', rendered)

    def test_untrusted_identifier_cannot_inject_script(self):
        with self.assertRaises(ValueError):
            render_font_support(["x:\n    python: dangerous()"])


if __name__ == "__main__":
    unittest.main()
