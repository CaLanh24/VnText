from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from vntext.renpy_extract import (
    RenPyTemplateParseError,
    parse_renpy_translation_templates,
)


class RenPyNativeTemplateTests(unittest.TestCase):
    def _fixture(self, root: Path) -> Path:
        root.mkdir(parents=True, exist_ok=True)
        (root / "script.rpy").write_text(
            """# game/story.rpy:10
translate klingon narrator_001:

    # "Line one\\nLine two [name] {#narrator}"
    ""

# game/story.rpy:15
translate klingon hero_001:

    # hero happy "Hello [name!t] {b}"
    hero happy ""

# game/story.rpy:20
translate klingon repeat_a:

    # hero "Same [name] {#duplicate}"
    hero ""

# game/story.rpy:21
translate klingon repeat_b:

    # hero "Same [name] {#duplicate}"
    hero ""
""",
            encoding="utf-8",
        )
        (root / "strings.rpy").write_text(
            """translate klingon strings:

 # game/ui.rpy:30
    old "Open the door {#menu}"
    new ""

 # game/ui.rpy:31
    old "Ready %(count)d\\nNext [name]"
    new "Sẵn sàng %(count)d\\nNext [name]"
""",
            encoding="utf-8",
        )
        return root

    def test_parses_typed_dialogue_and_string_units_without_deduping(self):
        with tempfile.TemporaryDirectory() as temp:
            units = parse_renpy_translation_templates(self._fixture(Path(temp)))

        self.assertEqual(len(units), 6)
        self.assertEqual([unit.order for unit in units], list(range(6)))
        self.assertEqual([unit.block_order for unit in units], [1, 2, 3, 4, 5, 5])
        self.assertEqual([unit.language for unit in units], ["klingon"] * 6)

        narrator = units[0]
        self.assertEqual(narrator.unit_kind, "dialogue")
        self.assertEqual(narrator.statement_class, "narration")
        self.assertEqual(narrator.native_id, "narrator_001")
        self.assertEqual(narrator.source_text, "Line one\nLine two [name] {#narrator}")
        self.assertEqual(narrator.target_text, "")
        self.assertEqual(narrator.source_file, "game/story.rpy")
        self.assertEqual(narrator.source_line, 10)
        self.assertEqual(narrator.speaker, "")
        self.assertEqual(narrator.native_identity, ("native_id", "narrator_001"))

        named = units[1]
        self.assertEqual(named.statement_class, "dialogue")
        self.assertEqual(named.speaker, "hero")
        self.assertEqual(named.expression, "happy")
        self.assertEqual(named.target_speaker, "hero")
        self.assertEqual(named.target_expression, "happy")

        duplicates = units[2:4]
        self.assertEqual([unit.source_text for unit in duplicates], [duplicates[0].source_text] * 2)
        self.assertEqual([unit.native_id for unit in duplicates], ["repeat_a", "repeat_b"])
        self.assertEqual([unit.native_identity for unit in duplicates], [
            ("native_id", "repeat_a"),
            ("native_id", "repeat_b"),
        ])

        strings = units[4:]
        self.assertEqual([unit.unit_kind for unit in strings], ["string", "string"])
        self.assertEqual([unit.statement_class for unit in strings], ["string", "string"])
        self.assertEqual([unit.native_id for unit in strings], ["", ""])
        self.assertEqual(strings[0].source_text, "Open the door {#menu}")
        self.assertEqual(strings[0].target_text, "")
        self.assertEqual(strings[0].native_identity, ("source", "Open the door {#menu}"))
        self.assertEqual(strings[0].source_file, "game/ui.rpy")
        self.assertEqual(strings[0].source_line, 30)
        self.assertEqual(strings[1].source_text, "Ready %(count)d\nNext [name]")
        self.assertEqual(strings[1].target_text, "Sẵn sàng %(count)d\nNext [name]")
        self.assertEqual(strings[1].source_file, "game/ui.rpy")
        self.assertEqual(strings[1].source_line, 31)

    def test_parse_is_repeatable_and_supports_single_file_and_language_filter(self):
        with tempfile.TemporaryDirectory() as temp:
            root = self._fixture(Path(temp))
            first = parse_renpy_translation_templates(root, language="klingon")
            second = parse_renpy_translation_templates(root, language="klingon")
            single = parse_renpy_translation_templates(root / "script.rpy", language="klingon")
            missing = parse_renpy_translation_templates(root, language="missing")

        self.assertEqual(first, second)
        self.assertEqual([unit.template_file for unit in first[:4]], ["script.rpy"] * 4)
        self.assertEqual([unit.template_file for unit in first[4:]], ["strings.rpy"] * 2)
        self.assertEqual([unit.template_order for unit in first], list(range(6)))
        self.assertEqual(len(single), 4)
        self.assertEqual(missing, [])

    def test_malformed_or_ambiguous_blocks_fail_closed(self):
        cases = {
            "missing provenance": """translate klingon line_a:\n\n    # \"Hello\"\n    \"\"\n""",
            "provenance separated from header": """# game/story.rpy:1\n\ntranslate klingon line_a:\n\n    # \"Hello\"\n    \"\"\n""",
            "missing target": """# game/story.rpy:1\ntranslate klingon line_a:\n\n    # \"Hello\"\n""",
            "missing new": """translate klingon strings:\n\n    # game/story.rpy:1\n    old \"Hello\"\n""",
            "string missing provenance": """translate klingon strings:\n\n    old \"Hello\"\n    new \"\"\n""",
            "string provenance separated from pair": """translate klingon strings:\n\n    # game/story.rpy:1\n\n    old \"Hello\"\n    new \"\"\n""",
            "wrong string order": """translate klingon strings:\n\n    # game/story.rpy:1\n    new \"Hello\"\n    old \"Source\"\n""",
            "ambiguous expression": """# game/story.rpy:1\ntranslate klingon line_a:\n\n    # Character(\"Hero\") \"Hello\"\n    \"\"\n""",
            "multiple target slots": """# game/story.rpy:1\ntranslate klingon line_a:\n\n    # \"Hello\"\n    \"One\"\n    \"Two\"\n""",
        }
        for name, content in cases.items():
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temp:
                path = Path(temp) / "broken.rpy"
                path.write_text(content, encoding="utf-8")
                with self.assertRaises(RenPyTemplateParseError):
                    parse_renpy_translation_templates(path)

    def test_official_multi_statement_shape_is_rejected_without_flattening(self):
        content = """# game/story.rpy:40
translate klingon line_a:

    # hero "First"
    # hero "Second"
    hero ""
    hero ""
"""
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "multi.rpy"
            path.write_text(content, encoding="utf-8")
            with self.assertRaisesRegex(RenPyTemplateParseError, "unsupported multi-statement native dialogue block"):
                parse_renpy_translation_templates(path)


if __name__ == "__main__":
    unittest.main()
