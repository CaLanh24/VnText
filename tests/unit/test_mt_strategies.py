"""Tests for mt_strategies."""

from __future__ import annotations

import sys
from pathlib import Path

def _tests_lib_on_path() -> None:
    cur = Path(__file__).resolve().parent
    while cur.name != "tests" and cur.parent != cur:
        cur = cur.parent
    lib = cur / "lib"
    p = str(lib)
    if p not in sys.path:
        sys.path.insert(0, p)

_tests_lib_on_path()
from bootstrap import bootstrap
TESTS, ROOT, LIB = bootstrap(__file__)

import unittest
from pathlib import Path
from unittest.mock import MagicMock


from vntext.mt_translation_safety import (
    collapse_token_repetition,
    collect_spans,
    postprocess,
    split_parts,
    translate_bracket_protected,
)
from vntext.mt_check import COND_EXPR
from vntext.mt_strategies import (
    is_moan_fragment,
    retry_row_strategies,
    translate_glrk_br_ct2,
    translate_inline_placeholders_ct2,
    translate_clause_segments_ct2,
    translate_sentence_segments_ct2,
    translate_protected_ct2,
    translate_synonym_row,
)
from vntext.patch_gate import has_garbage_repetition, translation_passes_patch_gate


class MtStrategiesTests(unittest.TestCase):
    def test_cond_expr_captures_multi_digit(self):
        src = "when Submissive>=90 & Corruption<50 & DEPRESSION>=1 Marriage"
        self.assertEqual(
            [m.group(0) for m in COND_EXPR.finditer(src)],
            ["Submissive>=90", "Corruption<50", "DEPRESSION>=1"],
        )
        _prep, parts = split_parts(src)
        tech = [v for k, v in parts if k == "tech"]
        self.assertIn("Phục tùng>=90", tech)
        self.assertIn("Tha hóa<50", tech)
        self.assertIn("Trầm cảm>=1", tech)
        # Không để sót chữ số (bug cũ: >=9 + text \"0 &\").
        text_bits = "".join(v for k, v in parts if k == "text")
        self.assertNotRegex(text_bits, r"^\s*0\b|\s0\s*&")

    def test_moan_fragment(self):
        self.assertTrue(is_moan_fragment("ah, ah"))
        self.assertFalse(is_moan_fragment("Hello world"))

    def test_retry_trace_contains_attempt_identity_and_output_hashes(self):
        row = {
            "source_text": "Hello there",
            "context": "TextAsset:dialogue:1",
            "file_path": "dialogue.txt",
            "import_method": "plain_text_line",
        }
        trace: list[dict] = []
        candidate, _strategy, reasons = retry_row_strategies(
            row,
            MagicMock(),
            set(),
            batch_raw="Xin chào",
            fast=True,
            full_raw="Xin chào",
            trace=trace,
        )
        self.assertEqual(candidate, "Xin chào")
        self.assertEqual(reasons, [])
        self.assertTrue(trace)
        attempt = trace[0]
        self.assertRegex(attempt["attempt_id"], r"^[0-9a-f-]{36}$")
        self.assertTrue(attempt["raw_output_hash"])
        self.assertTrue(attempt["candidate_hash"])

    def test_translate_synonym_row(self):
        row = {
            "source_text": "{HARD}=hard",
            "context": "TextAsset:_synonyms:1",
            "file_path": "x/_synonyms.txt",
        }
        tr = MagicMock()
        tr.translate.return_value = "cứng"
        out = translate_synonym_row(row, tr)
        self.assertEqual("{HARD}=cứng", out)

    def test_synonym_short_stems_and_phrase_fallbacks_are_translated(self):
        row = {
            "source_text": "{SWEARING}=Holy shit,ass,Oh my gods",
            "context": "TextAsset:_synonyms:1",
            "file_path": "x/_synonyms.txt",
        }
        out = translate_synonym_row(row, MagicMock())
        self.assertEqual("{SWEARING}=chết tiệt,mông,ôi các vị thần", out)

    def test_postprocess_repairs_observed_ui_labels(self):
        self.assertEqual(postprocess("NEW GAME", "NEW GAME"), "mới trò chơi")
        self.assertEqual(postprocess("INFO", "INFO"), "thông tin")
        self.assertEqual(postprocess("SUPPORT", "SUPPORT"), "hỗ trợ")

    def test_generic_fallback_repairs_variant_pool_and_tagged_ui(self):
        class IdentityTranslator:
            def translate(self, text):
                return text

        translator = IdentityTranslator()
        variants = translate_protected_ct2(
            "willing,welcoming,receptive,gracious,excited,enthusiastic,accepting",
            translator,
        )
        self.assertEqual(
            variants,
            "sẵn sàng,chào đón,tiếp nhận,tốt bụng,phấn khích,nhiệt tình,chấp nhận",
        )
        ui = translate_protected_ct2(
            "<color=yellow>CONTENT OPTIONS</color>", translator
        )
        self.assertEqual(ui, "<color=yellow>nội dung tùy chọn</color>")

    def test_retry_repairs_contractions_around_placeholders(self):
        class IdentityTranslator:
            def translate(self, text):
                return text

        row = {
            "source_text": (
                "You aren't just going to {ITEM} and leave like I'm some {FILE}?"
            ),
            "context": "TextAsset:dialogue:1",
            "file_path": "dialogue.txt",
            "import_method": "unity_textasset_line",
        }
        candidate, strategy, reasons = retry_row_strategies(
            row,
            IdentityTranslator(),
            set(),
            batch_raw=row["source_text"],
            full_raw=row["source_text"],
        )
        self.assertTrue(candidate, (strategy, reasons))
        self.assertNotIn("aren't", candidate)
        self.assertNotIn("I'm", candidate)
        self.assertIn("{ITEM}", candidate)
        self.assertIn("{FILE}", candidate)

    def test_protected_translation_keeps_source_proper_names_exact(self):
        source = "SampleName met ExampleTown in the city."

        class Translator:
            def translate(self, text):
                if text == "met":
                    return "gặp"
                if text == "in the city.":
                    return "trong thành phố."
                return text.replace("ExampleTown", "ExampleTwon")

        out = translate_protected_ct2(source, Translator())
        self.assertIn("SampleName", out)
        self.assertIn("ExampleTown", out)
        self.assertNotIn("ExampleTwon", out)
        self.assertIn("gặp", out)

    def test_protected_translation_keeps_lowercase_and_camelcase_literals_exact(self):
        source = "DemoName met QuestLead in sampleplace city."

        class Translator:
            def translate(self, text):
                return (
                    text.replace("DemoName", "DemoNime")
                    .replace("QuestLead", "QuestLeed")
                    .replace("sampleplace", "sampleplce")
                )

        out = translate_protected_ct2(source, Translator())
        self.assertIn("DemoName", out)
        self.assertIn("QuestLead", out)
        self.assertIn("sampleplace", out)
        self.assertNotIn("DemoNime", out)
        self.assertNotRegex(out, r"\bQuestLeed\b")
        self.assertNotIn("sampleplce", out)

    def test_unknown_lowercase_prose_is_not_masked_as_a_literal(self):
        source = "I feel a rush filling me up and find it."
        masked_names = {
            span[2].casefold()
            for span in collect_spans(source)
            if span[3] == "name"
        }
        self.assertNotIn("feel", masked_names)
        self.assertNotIn("rush", masked_names)
        self.assertNotIn("filling", masked_names)
        self.assertNotIn("find", masked_names)

    def test_bracket_route_restores_placeholders_and_tags_after_one_translation(self):
        source = "I feel {mName} under <color=yellow>the lamp</color>."

        class Translator:
            def __init__(self):
                self.calls = []

            def translate(self, text):
                self.calls.append(text)
                return (
                    text.replace("I feel", "Tôi cảm thấy")
                    .replace("under", "dưới")
                    .replace("the lamp", "chiếc đèn")
                )

        translator = Translator()
        out = translate_bracket_protected(source, translator.translate)
        self.assertEqual(len(translator.calls), 1)
        self.assertIn("[QZEL0000]", translator.calls[0])
        self.assertNotIn("{mName}", translator.calls[0])
        self.assertNotIn("<color=yellow>", translator.calls[0])
        self.assertIn("{mName}", out)
        self.assertIn("<color=yellow>chiếc đèn</color>", out)

    def test_bracket_route_keeps_mapped_prose_visible_to_translator(self):
        source = "Everyone look! I'm going to be pregnant {mName}."

        class Translator:
            def __init__(self):
                self.calls = []

            def translate(self, text):
                self.calls.append(text)
                return (
                    text.replace("Everyone look!", "Mọi người nhìn kìa!")
                    .replace("I'm going to be", "Em sắp")
                    .replace("pregnant", "mang thai")
                )

        translator = Translator()
        out = translate_bracket_protected(source, translator.translate)

        self.assertEqual(len(translator.calls), 1)
        self.assertIn("pregnant", translator.calls[0])
        self.assertIn("[QZEL0000]", translator.calls[0])
        self.assertNotIn("[QZEL0001]", translator.calls[0])
        self.assertIn("mang thai", out)
        self.assertIn("{mName}", out)

    def test_bracket_route_rejects_marker_mutation(self):
        source = "Take {mName} now."

        def mutate_marker(text):
            return text.replace("[QZEL0000]", "[QZEL9999]")

        self.assertIsNone(translate_bracket_protected(source, mutate_marker))

    def test_ct2_placeholder_route_precedes_raw_sentence_translation(self):
        source = "I feel {mName} under the lamp."

        class Translator:
            def __init__(self):
                self.calls = []

            def translate(self, text):
                self.calls.append(text)
                self.assert_not_raw(text)
                return text.replace("I feel", "Tôi cảm thấy").replace("under", "dưới")

            def assert_not_raw(self, text):
                if "{mName}" in text:
                    raise AssertionError("raw placeholder sentence was attempted")

        translator = Translator()
        out = translate_protected_ct2(source, translator)
        self.assertIn("Tôi cảm thấy", out)
        self.assertIn("{mName}", out)
        self.assertIn("[QZEL", translator.calls[0])

    def test_retry_prefers_safe_placeholder_candidate_over_raw_sentence(self):
        source = "I feel {mName} now."

        class Translator:
            def translate(self, text):
                return text.replace("I feel", "Tôi cảm thấy").replace("now", "bây giờ")

        row = {
            "source_text": source,
            "context": "NaninovelScript:phase-c-sample",
            "file_path": "dialogue.txt",
            "import_method": "naninovel_script_string",
        }
        candidate, strategy, reasons = retry_row_strategies(
            row,
            Translator(),
            set(),
            full_raw="Đã dịch {mName} câu.",
        )
        self.assertEqual(strategy, "placeholder_safe_first", (candidate, reasons))
        self.assertIn("Tôi cảm thấy", candidate)

    def test_retry_accepts_direct_sentence_only_after_placeholder_validation(self):
        class IdentityTranslator:
            def translate(self, text):
                return text

        row = {
            "source_text": "Hello {mName}.",
            "context": "NaninovelScript:phase-c-sample",
            "file_path": "dialogue.txt",
            "import_method": "naninovel_script_string",
        }
        candidate, strategy, reasons = retry_row_strategies(
            row,
            IdentityTranslator(),
            set(),
            full_raw="Xin chào {mName}.",
        )
        self.assertEqual((candidate, strategy, reasons), ("Xin chào {mName}.", "direct_source", []))

    def test_collapse_underscore_garbage(self):
        raw = "Không có {EJACULATE} sâu bên trong em...♡________"
        cleaned = collapse_token_repetition(raw)
        self.assertNotIn("___", cleaned)
        self.assertFalse(has_garbage_repetition(cleaned))

    def test_postprocess_heals_underscore_run(self):
        src = "(He {EJACULATE}s deep inside me...♡)"
        raw = "Không có {EJACULATE} sâu bên trong em...♡________________"
        pp = postprocess(src, raw)
        row = {
            "source_text": src,
            "context": "TextAsset:x",
            "file_path": "f",
            "import_method": "unity_textasset_line",
        }
        ok, _ = translation_passes_patch_gate(row, pp, set())
        self.assertTrue(ok)

    def test_translate_inline_placeholders_restores_tech(self):
        src = "(My eyes water as I lick precum from this {JERK}'s {COCK}, and it tastes so good)"
        tr = MagicMock()
        tr.translate.return_value = (
            "Mắt tôi ngấn nước khi liếm dâm dịch từ gã tồi tệ này, và nó ngon"
        )
        out = translate_inline_placeholders_ct2(src, tr)
        self.assertIn("{JERK}", out)
        self.assertIn("{COCK}", out)
        self.assertRegex(out, r"[\u00c0-\u1ef9]")

    def test_translate_glrk_br_keeps_prefix(self):
        src = "*GLRK* *GLRK* *GLRK*[br](Hello {mName} world)"
        tr = MagicMock()
        tr.translate.return_value = "Xin chào thế giới"
        out = translate_glrk_br_ct2(src, tr)
        self.assertTrue(out.startswith("*GLRK* *GLRK* *GLRK*[br]"))
        self.assertIn("{mName}", out)
        self.assertIn("Xin chào", out)

    def test_split_parts_restores_generic_terms_before_ct2(self):
        _prepared, parts = split_parts("Stalker gains Corruption+ and Pheromones+.")
        tech = [v for k, v in parts if k == "tech"]
        self.assertIn("kẻ theo dõi", tech)
        self.assertIn("tha hóa", tech)
        self.assertIn("pheromone", tech)

    def test_generic_terms_never_rewrite_placeholder_names(self):
        _prepared, parts = split_parts("As I {MOAN} in exhaustion, {PAIN} rises")
        tech = [v for k, v in parts if k == "tech"]
        self.assertIn("{MOAN}", tech)
        self.assertIn("{PAIN}", tech)

    def test_sentence_segments_preserve_tail_after_ellipsis(self):
        tr = MagicMock()
        tr.translate.side_effect = ["Anh ta rất giỏi việc đó...", "Tôi tự hỏi anh ta đã hôn bao nhiêu cô gái!"]
        out = translate_sentence_segments_ct2(
            "He's very good at it... I wonder how many girls he's kissed!", tr
        )
        self.assertIn("Anh ta rất giỏi", out)
        self.assertIn("bao nhiêu cô gái", out)

    def test_clause_segments_preserve_comma_question_tail(self):
        tr = MagicMock()
        tr.translate.side_effect = [
            "Bao nhiêu người đã có anh",
            "anh đã lấy bao nhiêu hàng",
        ]
        out = translate_clause_segments_ct2(
            "How many guys have had you, how many loads have you taken?", tr
        )
        self.assertIn("Bao nhiêu người đã có anh", out)
        self.assertIn("anh đã lấy bao nhiêu hàng", out)

    def test_postprocess_removes_model_hash_and_name_artifacts(self):
        src = "(The final act, {mName} pumps my {ASSHOLE} full of {CUM})"
        out = postprocess(
            src,
            "(Hành động cuối, {mName} Name {ASSHOLE} # đầy {CUM})",
        )
        self.assertNotIn("#", out)
        self.assertNotRegex(out, r"\}\s+Name\b")

    def test_postprocess_repairs_generic_residual_and_keeps_path_literal(self):
        src = "Cheering and groping in Folder/Sample_Data/StreamingAssets/Text"
        out = postprocess(src, "*Cheering* and groping in Folder/Sample_Data/StreamingAssets/Text")
        self.assertIn("*reo hò*", out)
        self.assertIn("sờ soạng", out)
        self.assertIn("Sample_Data/StreamingAssets/Text", out)

    def test_postprocess_repairs_hallucinated_generic_output_token(self):
        src = "A suspicious club has unique culture"
        out = postprocess(src, "Một câu lạc bộ khả nghi có Comment độc đáo")
        self.assertNotRegex(out, r"\bComment\b")
        self.assertIn("ghi chú", out)

    def test_postprocess_removes_bare_placeholder_echo(self):
        src = "*GLRRRK*!!![br]({TASTY})"
        out = postprocess(src, "*GLRRRK*!!![br](TASTY ... {TASTY})")
        self.assertNotRegex(out, r"(?<![A-Za-z{])TASTY(?![A-Za-z}])")
        self.assertIn("{TASTY}", out)


if __name__ == "__main__":
    unittest.main()
