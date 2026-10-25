"""Plain-text extraction must account for every dialogue line it keeps or drops."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path


def _tests_lib_on_path() -> None:
    cur = Path(__file__).resolve().parent
    while cur.name != "tests" and cur.parent != cur:
        cur = cur.parent
    lib = cur / "lib"
    if str(lib) not in sys.path:
        sys.path.insert(0, str(lib))


_tests_lib_on_path()
from bootstrap import bootstrap

TESTS, ROOT, LIB = bootstrap(__file__)

import unittest

from vntext.extract_quality import raw_text_quality
from vntext.extract_text import extract_plain_text

# English dialogue whose only "_" lives inside a brace placeholder.
PLACEHOLDER_DIALOGUE = (
    "NPC: Hello {player_name}, welcome back to the village!",
    "Guard: Pass, {title} {last_name}. The gate is open.",
    "NPC: HP: {hp}/{max_hp}  MP: {mp}/{max_mp}",
    "NPC: Goodbye, {player_name}. See you tomorrow!",
    "Aldeano: ¡Hola, {player_name}! Tienes %d mensajes nuevos.",
)
# Code-like text outside placeholders must stay rejected.
CODE_LIKE = (
    "snake_case_name",
    "some_var = 1",
    "NPC: call do_thing now.",
    "{player_name}",
    "NPC: set flag_one to 1",
)
# Non-Latin scripts are excluded by the existing edge policy, not by this change.
NON_LATIN = (
    "村人: こんにちは、{player_name}さん！今日はいい天気ですね。",
    "Стражник: Стой! Кто идёт в такой час, {player_name}?",
)


class PlainTextExtractAccountingTests(unittest.TestCase):
    def test_placeholder_names_do_not_make_dialogue_look_like_code(self):
        for line in PLACEHOLDER_DIALOGUE:
            with self.subTest(line=line):
                self.assertTrue(raw_text_quality(line, for_main=True))

    def test_code_identifiers_outside_placeholders_stay_rejected(self):
        for line in CODE_LIKE:
            with self.subTest(line=line):
                self.assertFalse(raw_text_quality(line, for_main=True))

    def test_every_line_is_extracted_or_has_a_named_exclusion(self):
        lines = (
            ("NPC: Plain line one.", "extract"),
            *((line, "extract") for line in PLACEHOLDER_DIALOGUE),
            ("NPC: Same line repeated.", "extract"),
            ("NPC: Same line repeated.", "extract"),
            *((line, "non-latin edge policy") for line in NON_LATIN),
            *((line, "code-like text") for line in CODE_LIKE),
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / "dialogue.txt"
            path.write_text("\n".join(text for text, _ in lines) + "\n", encoding="utf-8", newline="")
            entries = list(extract_plain_text(path, root))
        by_line = {entry.locator["line"]: entry for entry in entries}
        for number, (text, expected) in enumerate(lines, start=1):
            with self.subTest(line=number, text=text, expected=expected):
                if expected == "extract":
                    self.assertIn(number, by_line)
                    self.assertEqual(by_line[number].source_text, text)
                else:
                    self.assertNotIn(number, by_line)
        # No line is unaccounted: kept + named exclusions equal the input.
        kept = sum(1 for _, expected in lines if expected == "extract")
        self.assertEqual(len(entries), kept)
        self.assertEqual(len(lines), kept + sum(1 for _, e in lines if e != "extract"))


if __name__ == "__main__":
    unittest.main()
