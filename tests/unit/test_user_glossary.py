"""Package glossary tests, including structural token preservation."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

cur = Path(__file__).resolve().parent
while cur.name != "tests" and cur.parent != cur:
    cur = cur.parent
sys.path.insert(0, str(cur / "lib"))
from bootstrap import bootstrap

TESTS, ROOT, LIB = bootstrap(__file__)

from vntext.mt_ct2 import _batch_translate_chunk
from vntext.mt_ct2_pipeline import _select_ct2_targets
from vntext.package_glossary import (
    load_package_glossary,
    load_user_glossary,
    lookup_user_phrase,
    mask_user_glossary_terms,
    restore_user_glossary_terms,
)
from vntext.mt_memory import (
    build_translation_memory,
    load_translation_memory,
    lookup_translation_memory,
)


class FakeTranslator:
    def __init__(self):
        self.calls: list[str] = []

    def translate_many(self, texts):
        self.calls.extend(texts)
        return [f"dịch {text}" for text in texts]


class UserGlossaryTests(unittest.TestCase):
    def test_existing_rows_refresh_only_when_overwrite_is_explicit(self):
        rows = [
            {"key": "old", "source_text": "Use pheromones", "translation": "Dùng nội tiết"},
            {"key": "other", "source_text": "Open the door", "translation": "Mở cửa"},
            {"key": "blank", "source_text": "Use pheromones again", "translation": ""},
        ]
        glossary = {"pheromones": "mị lực"}

        frozen, refresh_frozen = _select_ct2_targets(rows, glossary, allow_overwrite=False)
        self.assertEqual([row["key"] for row in frozen], ["blank"])
        self.assertEqual(refresh_frozen, 0)

        refreshed, refresh_count = _select_ct2_targets(rows, glossary, allow_overwrite=True)
        self.assertEqual([row["key"] for row in refreshed], ["blank", "old"])
        self.assertEqual(refresh_count, 1)

    def test_user_glossary_overrides_builtin_and_exact_preserves_structure(self):
        package = Path(tempfile.mkdtemp(prefix="vntext_glossary_"))
        (package / ".mt").mkdir()
        (package / ".mt" / "glossary.json").write_text(
            json.dumps({"pheromones": "mị lực", "<color=red>pass</color>": "<color=red>đạt</color>"}, ensure_ascii=False),
            encoding="utf-8",
        )
        user = load_user_glossary(package)
        merged = load_package_glossary(package)
        self.assertEqual(user["pheromones"], "mị lực")
        self.assertEqual(merged["pheromones"], "mị lực")
        self.assertEqual(lookup_user_phrase("<color=red>PASS</color>", user), "<color=red>đạt</color>")

    def test_terms_are_masked_outside_tags_and_restored(self):
        masked, restore = mask_user_glossary_terms(
            "Use Pheromones {mName}<color=red>Pheromones</color>\\n", {"pheromones": "mị lực"}
        )
        self.assertEqual(masked.count("Pheromones"), 0)
        self.assertIn("<color=red>ZZG9001ZZ</color>", masked)
        self.assertIn("{mName}", masked)
        self.assertEqual(restore_user_glossary_terms(masked, restore), "Use mị lực {mName}<color=red>mị lực</color>\\n")

    def test_batch_uses_exact_glossary_without_ct2_and_keeps_tags(self):
        translator = FakeTranslator()
        row = {
            "key": "k1",
            "source_text": "<color=red>Pheromones {mName}</color>\\n",
        }
        result = _batch_translate_chunk(
            translator,
            [row],
            {"<color=red>pheromones {mName}</color>\\n": "<color=red>mị lực {mName}</color>\\n"},
        )
        self.assertEqual(result["k1"], "<color=red>mị lực {mName}</color>\\n")
        self.assertEqual(translator.calls, [])

    def test_batch_masks_term_before_ct2_and_restores_user_translation(self):
        translator = FakeTranslator()
        result = _batch_translate_chunk(
            translator,
            [{"key": "k1", "source_text": "Use pheromones {mName}"}],
            {"pheromones": "mị lực"},
        )
        self.assertIn("mị lực", result["k1"])
        self.assertIn("{mName}", result["k1"])
        self.assertTrue(any("ZZG9000ZZ" in call for call in translator.calls))

    def test_batch_keeps_generic_terms_in_ct2_sentence_context(self):
        translator = FakeTranslator()
        source = "Stalker gains Corruption+ and Pheromones+."
        _batch_translate_chunk(translator, [{"key": "k1", "source_text": source}])
        self.assertEqual(translator.calls, [source])

    def test_translation_memory_requires_unique_wording_and_uses_context_family(self):
        package = Path(tempfile.mkdtemp(prefix="vntext_memory_"))
        rows = [
            {
                "key": "k1",
                "source_text": "Start game",
                "translation": "Bắt đầu game",
                "context": "NaninovelScript:1",
                "import_method": "naninovel_script_string",
            },
            {
                "key": "k2",
                "source_text": "Start game",
                "translation": "Bắt đầu game",
                "context": "NaninovelScript:2",
                "import_method": "naninovel_script_string",
            },
            {
                "key": "k3",
                "source_text": "Open",
                "translation": "Mở",
                "context": "TextAsset:menu",
                "import_method": "unity_textasset_line",
            },
            {
                "key": "k4",
                "source_text": "Open",
                "translation": "Mở cửa",
                "context": "TextAsset:dialogue",
                "import_method": "unity_textasset_line",
            },
        ]
        memory = build_translation_memory(rows, package)
        self.assertEqual(memory["unique_entries"], 1)
        loaded = load_translation_memory(package)
        self.assertEqual(
            lookup_translation_memory(
                {"source_text": "START  game", "context": "NaninovelScript:9", "import_method": "naninovel_script_string"},
                loaded,
            ),
            "Bắt đầu game",
        )
        self.assertIsNone(
            lookup_translation_memory(
                {"source_text": "Open", "context": "TextAsset:other", "import_method": "unity_textasset_line"},
                loaded,
            )
        )

    def test_batch_uses_translation_memory_before_ct2(self):
        translator = FakeTranslator()
        result = _batch_translate_chunk(
            translator,
            [{
                "key": "k1",
                "source_text": "Start game",
                "context": "NaninovelScript:9",
                "import_method": "naninovel_script_string",
            }],
            {},
            {"version": "1.0.0", "entries": [{
                "source": "start game",
                "translation": "Bắt đầu game",
                "context_family": "naninovelscript",
                "import_method": "naninovel_script_string",
            }]},
        )
        self.assertEqual(result["k1"], "Bắt đầu game")
        self.assertEqual(translator.calls, [])


if __name__ == "__main__":
    unittest.main()
