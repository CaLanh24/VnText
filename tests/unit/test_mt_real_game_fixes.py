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

    def test_visible_achievement_label_is_not_a_technical_prefix(self):
        self.assertEqual(("ui_label_fixed", "Thành tựu:"), classify_row_authoritative(self.row("Achievements: ", self.CTX))[:2])
        self.assertEqual(("ui_label_fixed", "Đã mở khóa"), classify_row_authoritative(self.row("Unlocked ", self.CTX))[:2])


class DateFormatAndNumberedLabelTests(unittest.TestCase):
    FORMAT = "%b %d, %Y @ %I:%M %p{#achievement_timestamp}"

    def test_a_translation_that_loses_any_strftime_directive_or_punctuation_is_rejected_by_the_preflight(self):
        for broken in ("%b %d%Y %p{#achievement_timestamp}", "%b %d, %Y @ %I %p{#achievement_timestamp}", "%b %d, %Y %I:%M %p{#achievement_timestamp}",
                       "%b %d, %Y @ %I:%M{#achievement_timestamp}", "Tháng %d, %Y @ %I:%M %p{#achievement_timestamp}"):
            with self.subTest(broken):
                self.assertTrue(mt_check.typed_carrier_problems(self.FORMAT, broken))
        self.assertEqual([], mt_check.typed_carrier_problems(self.FORMAT, self.FORMAT))
        self.assertEqual([], mt_check.typed_carrier_problems("Hello 100% sure", "Xin chào chắc 100%"))        # prose percent is not a directive

    def test_pure_date_format_strings_are_technical_copy_literal_never_sent_to_the_model(self):
        row = {"key": "k", "source_text": self.FORMAT, "translation": "", "context": "RenPy:game/x.rpy:3:string:y", "file_path": "game/x.rpy", "import_method": "renpy_string"}
        self.assertEqual(("copy_literal", "date/time format string — giữ nguyên"), classify_row_authoritative(row)[:2])
        self.assertFalse(mt_check.is_date_format_string("Saved on %d"))
        self.assertFalse(mt_check.is_date_format_string("You have %d days and %s hours left"))

    def test_numbered_labels_use_an_exact_pattern_in_ui_contexts_only(self):
        from vntext.ui_labels import resolve_ui_label_translation as resolve
        ctx = "RenPy:game/x.rpy:3:string:y"
        self.assertEqual("Thành tựu 3", resolve("Achievement3", ctx))
        self.assertEqual("Thành tựu 12", resolve("achievement 12", ctx))
        self.assertIsNone(resolve("Achievement3 unlocked", ctx))
        self.assertIsNone(resolve("Achievement3", "RenPy:game/x.rpy:3:start_abc"))


class QualityGateFalsePositiveTests(unittest.TestCase):
    def issues(self, source, value):
        from vntext.mt_strategies import candidate_quality_issues
        row = {"key": "k", "source_text": source, "translation": "", "context": "RenPy:x:start_a", "file_path": "x", "import_method": "renpy_dialogue"}
        return candidate_quality_issues(row, value, set())

    def test_vietnamese_reduplication_is_not_a_repeated_token_fault_but_triples_and_ascii_pairs_are(self):
        self.assertNotIn("quality: repeated token: chằm", self.issues("I stared at them from afar.", "Tôi nhìn chằm chằm vào họ từ xa."))
        self.assertIn("quality: repeated token: chằm", self.issues("I stared at them from afar.", "Tôi nhìn chằm chằm chằm vào họ."))
        self.assertIn("quality: repeated token: very", self.issues("It was so very bad today.", "Nó very very tệ."))

    def test_a_loanword_the_model_keeps_even_alone_is_not_a_translation_failure_for_that_run(self):
        src, out = "I could smell the cheap tequila.", "Tôi có thể ngửi thấy mùi tequila rẻ tiền."
        self.assertTrue(any("english-token" in issue for issue in self.issues(src, out)))
        try:
            asked = []
            mt_check.set_runtime_common_words_provider(lambda: {"common": (), "kept_probe": lambda word: asked.append(word) or word == "tequila"})
            mt_check.ensure_runtime_common_words()
            self.assertFalse(any("english-token" in issue for issue in self.issues(src, out)))
            self.assertEqual(["tequila"], asked)                                       # the model is asked once, only about the flagged word
            self.issues(src, out)
            self.assertEqual(["tequila"], asked)
        finally:
            mt_check.set_runtime_common_words(())
        self.assertTrue(any("english-token" in issue for issue in self.issues(src, out)))


class NameInsideSentenceTests(unittest.TestCase):
    ROW = {"key": "k1", "source_text": "Chang did not notice the cold. He asked about the job.", "translation": "", "context": "RenPy:x:start_a", "file_path": "x",
           "import_method": "renpy_dialogue"}

    class Model:
        def __init__(self, mutate_name=False):
            self.seen = []
            self.mutate_name = mutate_name

        def translate_many(self, texts):
            self.seen.append(list(texts))
            return [("T[" + text + "]").replace("Chang", "Chàng" if self.mutate_name else "Chang") for text in texts]

    def test_a_name_stays_inside_its_sentence_instead_of_cutting_the_sentence_into_orphan_fragments(self):
        from vntext.mt_ct2_io import _batch_translate_chunk
        model = self.Model()
        out = _batch_translate_chunk(model, [dict(self.ROW)])
        sent = [text for batch in model.seen for text in batch]
        self.assertIn("Chang did not notice the cold.", sent)                       # whole sentence, name inside
        self.assertNotIn(" did not notice the cold.", sent)                         # no orphan fragment
        self.assertIn("Chang", out["k1"])

    def test_inferred_name_mutation_does_not_trigger_destructive_fragment_retranslation(self):
        from vntext.mt_ct2_io import _batch_translate_chunk
        model = self.Model(mutate_name=True)
        out = _batch_translate_chunk(model, [dict(self.ROW)])
        self.assertIn("Chàng", out["k1"])
        self.assertIn("He asked about the job.", out["k1"])
        self.assertEqual(1, len(model.seen))

    def test_name_retry_never_sends_orphan_fragments_and_keeps_the_second_sentence(self):
        from vntext.mt_ct2_io import _batch_translate_chunk
        model = self.Model(mutate_name=True)
        out = _batch_translate_chunk(model, [dict(self.ROW)])
        self.assertIn("He asked about the job.", out["k1"])
        self.assertFalse(any(text.strip() == "did not notice the cold." for batch in model.seen for text in batch))
        self.assertFalse(any("ZZG" in text for batch in model.seen for text in batch))

    def test_explicit_user_glossary_translation_still_wins_over_inferred_names(self):
        from vntext.mt_ct2_io import _batch_translate_chunk
        class Unused(self.Model):
            def translate_many(self, texts):
                raise AssertionError("an exact user translation must not go to the model")
        approved = "Chang không nhận thấy cái lạnh. Anh hỏi về công việc."
        out = _batch_translate_chunk(Unused(), [dict(self.ROW)], {self.ROW["source_text"]: approved})
        self.assertEqual(approved, out["k1"])


class CompleteSentenceRetryTests(unittest.TestCase):
    def test_shouted_prose_uses_normal_case_model_input_without_touching_acronyms_or_source(self):
        from vntext.mt_strategies import _normalise_mixed_case_for_mt
        source = "A HUNDRED WHOLE DOLLARS!"
        self.assertEqual("A hundred whole dollars!", _normalise_mixed_case_for_mt(source))
        self.assertEqual("A HUNDRED WHOLE DOLLARS!", source)
        self.assertEqual("NASA IS IN SPACE!", _normalise_mixed_case_for_mt("NASA IS IN SPACE!"))
        self.assertIn("NASA", _normalise_mixed_case_for_mt("THE NASA MISSION IS FINISHED!"))
        class Model:
            def translate_many(self, texts):
                return ["Cả trăm đô-la!" if text == "A hundred whole dollars!" else "Một con thỏ đế!" for text in texts]
        self.assertEqual(["Cả trăm đô-la!"], translate_many_by_sentence(Model(), [source]))

    def test_foreign_name_accents_do_not_mark_an_english_paragraph_as_already_vietnamese(self):
        import unicodedata
        for text in ("Thanks to the Anaïs Nin book, I read it twice.", "Renée asked José about the café."):
            self.assertFalse(mt_check.is_vietnamese_text(text))
        for text in ("Có", "Hủy", "Tên người dùng", "Tiếng Việt"):
            self.assertTrue(mt_check.is_vietnamese_text(text))
            self.assertTrue(mt_check.is_vietnamese_text(unicodedata.normalize('NFD', text)))

    def test_retry_of_plain_prose_keeps_every_sentence_in_context(self):
        from vntext.mt_strategies import translate_sentence_segments_ct2
        class Model(Echo):
            def translate_many(self, texts):
                self.calls.append(list(texts))
                return ["Câu đầu." if text.startswith("First") else "Câu sau." for text in texts]
            def translate(self, text):
                raise AssertionError("the retry must use the sentence batch")
        model = Model(drop_second=True)
        result = translate_sentence_segments_ct2("First one. Second one.", model)
        self.assertEqual("Câu đầu. Câu sau.", result)

    def test_short_adapter_batch_response_retries_every_source_sentence(self):
        class Short:
            def translate_many(self, texts): return []
            def translate(self, text): return {"First one.": "Câu đầu.", "Second one.": "Câu sau."}[text]
        self.assertEqual(["Câu đầu. Câu sau."], translate_many_by_sentence(Short(), ["First one. Second one."]))

    def test_compound_name_anchor_retains_a_common_word_without_whitelisting_plain_prose(self):
        try:
            mt_check.set_runtime_common_words({"mockingbird", "house", "owner"})
            self.assertIn("mockingbird", mt_check.source_proper_name_tokens("We met at Aster Mockingbird Hall."))
            self.assertNotIn("house", mt_check.source_proper_name_tokens("The House Owner paid us."))
        finally:
            mt_check.set_runtime_common_words(())


if __name__ == "__main__":
    unittest.main()
