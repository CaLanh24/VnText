"""Systemic translation fixes found by the real-game run (Ren'Py game, 2026-11-02): sentence-level MT, model-proven common words, catalog before the name guard."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

cur = Path(__file__).resolve().parent
while cur.name != "tests" and cur.parent != cur:
    cur = cur.parent
sys.path.insert(0, str(cur / "lib"))
from bootstrap import bootstrap

TESTS, ROOT, LIB = bootstrap(__file__)

from vntext import mt_check
from vntext.mt_classify import classify_row_authoritative
from vntext.mt_ct2_io import split_sentences, translate_many_by_sentence
from vntext.mt_ct2_pipeline import _discover_common_words


class Echo:
    """Fake model: records calls, answers 'T(<text>)'; a truncating model would drop the second sentence of a whole fragment."""
    def __init__(self, drop_second=False):
        self.calls = []
        self.drop_second = drop_second

    def translate_many(self, texts):
        self.calls.append(list(texts))
        out = []
        for text in texts:
            parts = split_sentences(text)
            out.append(f"T({parts[0]})" if self.drop_second and len(parts) > 1 else f"T({text})")
        return out


class SentenceLevelTranslationTests(unittest.TestCase):
    def test_split_keeps_abbreviations_quotes_and_lowercase_continuations(self):
        self.assertEqual(["Mr. Tia went home.", "Then he slept!"], split_sentences("Mr. Tia went home. Then he slept!"))
        self.assertEqual(["Hello there"], split_sentences("Hello there"))
        self.assertEqual(['"Stop."', "He said no."], split_sentences('"Stop." He said no.'))
        self.assertEqual(["It was dark… and cold."], split_sentences("It was dark… and cold."))     # lower-case continuation: one sentence
        self.assertEqual(["I came…", "Then I left."], split_sentences("I came… Then I left."))

    def test_a_truncating_model_cannot_drop_a_sentence_of_a_multi_sentence_fragment(self):
        model = Echo(drop_second=True)
        out = translate_many_by_sentence(model, ["First one. Second one.", "Single sentence"])
        self.assertEqual(["T(First one.) T(Second one.)", "T(Single sentence)"], out)
        self.assertEqual(1, len(model.calls))                                    # still one batched model call

    def test_empty_model_answer_keeps_the_source_sentence_instead_of_losing_it(self):
        class Silent(Echo):
            def translate_many(self, texts):
                return ["" if "Second" in text else f"T({text})" for text in texts]
        self.assertEqual(["T(First one.) Second one."], translate_many_by_sentence(Silent(), ["First one. Second one."]))


class CommonWordDiscoveryTests(unittest.TestCase):
    def test_model_proven_common_words_are_not_names_but_real_names_stay_protected(self):
        class Vocabulary:
            table = {"Clearly": "Rõ ràng", "clearly": "rõ ràng", "Americans": "Người Mỹ", "americans": "người Mỹ", "Chang": "Chang", "chang": "Chang",
                     "Jacob": "Jacob", "jacob": "Nhật Bản", "Bambi": "Bbib", "bambi": "babib"}
            def translate_many(self, texts):
                return [self.table.get(text, text) for text in texts]
        rows = [{"source_text": "Clearly, Chang saw Jacob and the Americans with Bambi."}]
        common = _discover_common_words(Vocabulary(), rows, {})
        self.assertEqual({"clearly", "americans"}, common)
        self.assertEqual(set(), _discover_common_words(Vocabulary(), rows, {"Clearly": "Rõ ràng"}) & {"clearly"})   # user glossary terms are never touched
        try:
            mt_check.set_runtime_common_words(common)
            names = mt_check.source_proper_name_tokens("Clearly, Chang saw the Americans.")
            self.assertEqual({"chang"}, names)
        finally:
            mt_check.set_runtime_common_words(())
        self.assertIn("clearly", mt_check.source_proper_name_tokens("Clearly, Chang saw the Americans."))     # default behaviour restored


class CatalogBeforeNameGuardTests(unittest.TestCase):
    CTX = "RenPy:game/screens.rpy:1074:string:screens.rpy:231"

    def row(self, source, context):
        return {"key": "k", "source_text": source, "translation": "", "context": context, "file_path": "game/screens.rpy", "import_method": "renpy_string"}

    def test_ren_py_string_table_labels_use_the_catalog_instead_of_being_kept_as_names(self):
        self.assertEqual(("ui_label_fixed", "Quay lại"), classify_row_authoritative(self.row("Back", self.CTX))[:2])
        self.assertEqual(("ui_label_fixed", "Bàn phím"), classify_row_authoritative(self.row("Keyboard", self.CTX))[:2])

    def test_names_and_story_contexts_are_unchanged(self):
        self.assertEqual("copy_literal", classify_row_authoritative(self.row("Chang", self.CTX))[0])
        self.assertEqual("copy_literal", classify_row_authoritative(self.row("Back", "RenPy:game/script.rpy:21:start_a4a14dc7"))[0])


if __name__ == "__main__":
    unittest.main()
