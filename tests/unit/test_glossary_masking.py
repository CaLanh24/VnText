"""Glossary masking is whole-word, non-cascading and collision-free (Root pure in-memory reproductions, plus v2 and the fake-translator round trip)."""
import unicodedata
import unittest
from pathlib import Path

from vntext.glossary_v2 import mask_terms, restore_terms
from vntext.package_glossary import mask_user_glossary_terms, restore_user_glossary_terms

ROOT = Path(__file__).resolve().parents[2]


def roundtrip(src, glossary):
    masked, restore = mask_user_glossary_terms(src, glossary)
    return masked, restore_user_glossary_terms(masked, restore)


def v2(*entries):
    return {"entries": [{"source": s, "target": t, "priority": p, "kind": "fixed_phrase"} for s, t, p in entries]}


class UserGlossaryMaskingTests(unittest.TestCase):
    def test_a_term_never_matches_inside_another_word(self):
        masked, restored = roundtrip("The passage is clear.", {"ass": "mông"})
        self.assertEqual("The passage is clear.", masked)                    # nothing masked, nothing to restore
        self.assertEqual("The passage is clear.", restored)
        self.assertEqual("An and An.", roundtrip("Alice and Alice.", {"alice": "An"})[1])

    def test_generated_tokens_are_not_remasked_by_a_later_term(self):
        masked, restored = roundtrip("Alice is here.", {"Alice": "An", "Z": "Dét"})
        self.assertEqual("An is here.", restored)
        self.assertNotIn("Dét", restored)
        self.assertNotRegex(restored, r"ZZG")

    def test_an_original_literal_sentinel_is_never_restored_as_a_term(self):
        masked, restore = mask_user_glossary_terms("ZZG9000ZZ and Alice.", {"Alice": "An"})
        self.assertEqual("ZZG9000ZZ and An.", restore_user_glossary_terms(masked, restore))
        self.assertNotIn("ZZG9000ZZ", restore)                               # the generated token avoided the literal

    def test_punctuation_multiword_overlap_and_case(self):
        self.assertEqual("Xin chào, Xin chào!", roundtrip("Hello world, hello World!", {"hello world": "Xin chào"})[1])
        self.assertEqual("kem and đá", roundtrip("Ice  cream and ice", {"ice cream": "kem", "ice": "đá"})[1])    # longest wins, blank runs match
        self.assertEqual("Ông Smith", roundtrip("Mr. Smith", {"mr.": "Ông"})[1])                             # punctuation-ended term
        self.assertEqual("An's book", roundtrip("Alice's book", {"alice": "An"})[1])

    def test_unicode_marks_count_as_word_characters_and_nfd_is_preserved(self):
        nfd = unicodedata.normalize("NFD", "café")
        self.assertEqual(nfd, roundtrip(nfd, {"cafe": "X"})[1])              # "cafe" + combining accent is a different word
        self.assertEqual("X ngon", roundtrip(nfd + " ngon", {nfd: "X"})[1])  # the NFD spelling matches itself, rest untouched
        self.assertEqual("X", roundtrip("café", {nfd: "X"})[1])              # NFC text matches an NFD glossary key

    def test_protected_spans_and_newlines_are_preserved(self):
        src = "Say <b>Alice</b> {name} \n Alice[br]ZZG1ZZ\nAlice"
        masked, restore = mask_user_glossary_terms(src, {"alice": "An"})
        self.assertIn("<b>", masked); self.assertIn("{name}", masked); self.assertIn("\n", masked); self.assertIn("[br]", masked); self.assertIn("ZZG1ZZ", masked)
        self.assertIn("\n", masked)
        self.assertEqual("Say <b>An</b> {name} \n An[br]ZZG1ZZ\nAn", restore_user_glossary_terms(masked, restore))

    def test_a_phrase_does_not_swallow_a_line_break(self):
        self.assertEqual("ice\ncream", roundtrip("ice\ncream", {"ice cream": "kem"})[1])


class GlossaryV2MaskingTests(unittest.TestCase):
    row = {"source_text": "", "context": "", "file_path": "", "import_method": "", "backend": ""}

    def test_v2_whole_word_non_cascading_and_collision_free(self):
        g = v2(("ass", "mông", 0))
        masked, restores, _ = mask_terms("The passage is clear.", self.row, g)
        self.assertEqual("The passage is clear.", masked)
        g = v2(("Alice", "An", 0), ("Z", "Dét", 0))
        masked, restores, _ = mask_terms("Alice is here.", self.row, g)
        self.assertEqual("An is here.", restore_terms(masked, restores))
        masked, restores, _ = mask_terms("ZZG900000ZZG and Alice.", self.row, v2(("Alice", "An", 0)))
        self.assertEqual("ZZG900000ZZG and An.", restore_terms(masked, restores))

    def test_v2_priority_overlap_and_combining_marks(self):
        g = v2(("ice", "đá", 0), ("ice cream", "kem", 5))
        masked, restores, _ = mask_terms("ice cream and ice", self.row, g)
        self.assertEqual("kem and đá", restore_terms(masked, restores))
        nfd = unicodedata.normalize("NFD", "café")
        masked, restores, _ = mask_terms(nfd, self.row, v2(("cafe", "X", 0)))
        self.assertEqual(nfd, restore_terms(masked, restores))

    def test_v2_token_ordinal_stays_stable_for_absent_entries(self):
        masked, _restores, _ = mask_terms("Use Beta.", self.row, v2(("Alpha", "A", 1), ("Beta", "B", 0)))
        self.assertEqual("Use ZZG900001ZZG.", masked)


class FakeTranslatorRoundTripTests(unittest.TestCase):
    """The production order: v2 mask -> user mask -> (translator rewrites ordinary words only) -> user restore -> v2 restore."""

    @staticmethod
    def fake_translate(text):
        return text.replace(" is ", " là ").replace("passage", "đoạn văn")

    def run_pipeline(self, src, user, glossary_v2):
        masked_v2, restore_v2, _ = mask_terms(src, GlossaryV2MaskingTests.row, glossary_v2)
        masked, restore = mask_user_glossary_terms(masked_v2, user)
        out = self.fake_translate(masked)
        return restore_terms(restore_user_glossary_terms(out, restore), restore_v2)

    def test_both_layers_together_keep_original_text_and_apply_each_term_once(self):
        out = self.run_pipeline("Alice is in the passage with Bob; ZZG9000ZZ stays.", {"bob": "Bốp"}, v2(("Alice", "An", 0), ("Z", "Dét", 0)))
        self.assertEqual("An là in the đoạn văn with Bốp; ZZG9000ZZ stays.", out)

    def test_user_terms_never_match_inside_v2_masks(self):
        out = self.run_pipeline("Alice is here.", {"z": "Dét", "g": "Gờ", "900000": "N"}, v2(("Alice", "An", 0)))
        self.assertEqual("An là here.", out)


class CacheStrategyTests(unittest.TestCase):
    def test_changed_masking_bumps_the_strategy_fingerprint_without_touching_cached_rows(self):
        text = (ROOT / "vntext/mt_ct2_pipeline.py").read_text(encoding="utf-8")
        self.assertIn('strategy_version += "-glossary-masking-3"', text)
        self.assertIn('if user_glossary or (glossary_v2 or {}).get("entries"):', text)


if __name__ == "__main__":
    unittest.main()
