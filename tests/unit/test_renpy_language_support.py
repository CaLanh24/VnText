import unittest

from vntext.renpy_language_support import fixed_label_functions, fixed_language_dropdowns, render_language_support


SOURCE = '''init 99 python:
    def current_language_name():
        names = {"French": "Français", "German": "Deutsch", "Italian": "Italiano"}
        if _preferences.language == None:
            return "English"
        else:
            return names[_preferences.language]
screen settings():
    text current_language_name():
        size 20
'''


class LanguageSupportTests(unittest.TestCase):
    def test_static_pure_language_item_list_can_offer_vietnamese(self):
        source = '''init 50 python:
    class ChoiceItem:
        def __init__(self, value, name, action=None, selected=False):
            self.value = value
            self.name = name
            self.action = action
            self.selected = selected
    picker = Dropdown([
        ChoiceItem("en", "English", Language(None)),
        ChoiceItem("fr", "Français", Language("French")),
        ChoiceItem("de", "Deutsch", Language("German")),
    ])
'''
        self.assertEqual(fixed_language_dropdowns([source]), [("picker", "ChoiceItem")])
        self.assertIn('picker.dropdown_list.append(ChoiceItem(', render_language_support([SOURCE, source]))
        self.assertEqual(fixed_language_dropdowns([source, source]), [])
        self.assertEqual(fixed_language_dropdowns([source.replace('self.value = value', 'notify_user()\n            self.value = value')]), [])
        self.assertEqual(fixed_language_dropdowns([source.replace('"Français"', '"font.ttf"')]), [])

    def test_static_language_names_used_as_text_are_supported(self):
        self.assertEqual(fixed_label_functions([SOURCE]), ["current_language_name"])
        code = render_language_support([SOURCE])
        self.assertIn('if _preferences.language == "vietnamese":', code)
        self.assertIn('return _vntext_label_original_current_language_name()', code)
        self.assertIn('Tiếng Việt', code)

    def test_other_localized_values_are_not_language_names(self):
        for replacement in ('font.ttf', 'Bonjour', '999'):
            self.assertEqual(fixed_label_functions([SOURCE.replace('Français', replacement)]), [])

    def test_side_effects_calls_parameters_and_decorators_disqualify(self):
        variants = [
            SOURCE.replace('names = {', 'print("side effect")\n        names = {'),
            SOURCE.replace('current_language_name():', 'current_language_name(argument):', 1),
            SOURCE.replace('    def ', '    @decorate\n    def ', 1),
            SOURCE.replace('return names[_preferences.language]', 'return invoke(names)'),
            SOURCE.replace('"Français"', 'compute_label()'),
        ]
        for source in variants:
            with self.subTest(source=source):
                self.assertEqual(fixed_label_functions([source]), [])

    def test_ambiguous_definitions_or_non_text_use_are_rejected(self):
        self.assertEqual(fixed_label_functions([SOURCE, SOURCE]), [])
        self.assertEqual(fixed_label_functions([SOURCE.replace('text current_language_name():', '$ x = current_language_name()')]), [])
        self.assertEqual(fixed_label_functions([SOURCE, 'init 999 python:\n    current_language_name = other\n']), [])

    def test_wrapper_keeps_all_other_languages_on_original_function(self):
        code = render_language_support([SOURCE]).split('init 999 python:\n', 1)[1]
        import textwrap
        class Preferences:
            language = None
        seen = []
        scope = {'_preferences': Preferences(), 'current_language_name': lambda: seen.append(1) or 'Original'}
        # Execute generated fixed wrapper only, never source/game Python.
        exec(compile(textwrap.dedent(code), '<generated language wrapper>', 'exec'), scope)
        exec(compile(textwrap.dedent(code), '<generated language wrapper repeat>', 'exec'), scope)
        self.assertEqual(scope['current_language_name'](), 'Original')
        scope['_preferences'].language = 'vietnamese'
        self.assertIn('Tiếng Việt', scope['current_language_name']())
        scope['_preferences'].language = 'French'
        self.assertEqual(scope['current_language_name'](), 'Original')
        self.assertEqual(len(seen), 2)


if __name__ == '__main__':
    unittest.main()
