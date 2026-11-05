"""A near-miss spelling of a capitalised source name is restored; unrelated words and correct Vietnamese are left alone.

Evidence (real-game corpus): OPUS-MT returned ``Babib``/``Tavenn``/``Domineing`` for ``Bambi``/``Tavern``/``Domineering``.  The English-token gate then
rejected complete first-pass translations and a fragmenting fallback was chosen.
"""

import unittest

from vntext.mt_translation_safety import POSTPROCESS_VERSION, postprocess, repair_model_artifacts


class GarbledNameRestoreTests(unittest.TestCase):
    def test_close_misspelling_of_source_names_is_restored(self):
        self.assertEqual(
            "Chào mừng đến quán rượu, Bambi.",
            postprocess("Welcome to the Tavern, Bambi.", "Chào mừng đến Tavenn, Babib."),
        )
        self.assertEqual("Tôi yêu độc đoán quán rượu.", postprocess("I love Domineering Tavern.", "Tôi yêu Domineing Taven."))

    def test_name_absent_from_source_is_not_invented(self):
        self.assertEqual("Xin chào Babib.", postprocess("Hello there.", "Xin chào Babib."))

    def test_vietnamese_words_and_exact_names_are_untouched(self):
        self.assertEqual("Bambi nói tavern rất ồn.", repair_model_artifacts("Bambi said the tavern is loud.", "Bambi nói tavern rất ồn."))
        self.assertEqual("Bạn tên là Bambi.", repair_model_artifacts("You are Bambi.", "Bạn tên là Bambi."))

    def test_ambiguous_match_is_left_alone(self):
        self.assertEqual("Tavenn", repair_model_artifacts("Tavern Tavent", "Tavenn"))

    def test_cache_identity_tracks_the_new_repair(self):
        self.assertNotEqual("sentence-retry-context-4", POSTPROCESS_VERSION)


class ModelArtifactRepairTests(unittest.TestCase):
    def test_garbled_ordinary_word_is_restored_to_the_source_word(self):
        self.assertEqual(
            "Nhưng những người đàn ông này 'vô cùng bị tổn thương'.",
            postprocess("But these men were incredibly hurt.", "Nhưng những người đàn ông này 'incridibly bị tổn thương'."),
        )
        self.assertEqual("Mặt mũi mới tìm thấy của Chang đã làm.", postprocess("Chang's newly found countenance cleared", "Mặt mũi mới tìm thấy của Chunga đã làm."))

    def test_word_joiner_underscore_and_space_before_punctuation_are_removed(self):
        self.assertEqual("Ngài dâng tôi cho con cái dưới quyền Ngài, Khác nào kẻ tôi tớ.", postprocess("He offers me up.", "Ngài dâng tôi cho con_cái dưới quyền Ngài , Khác_nào kẻ tôi_tớ ."))

    def test_underscore_in_source_or_structured_rows_is_kept(self):
        self.assertEqual("Dùng a_b ở đây .", postprocess("Use a_b here .", "Dùng a_b ở đây ."))
        self.assertEqual("{player_name} đi_bộ .", postprocess("{player_name} walks .", "{player_name} đi_bộ ."))

    def test_vowel_cry_becomes_the_source_interjection(self):
        self.assertEqual("Anh ta lẩm bẩm: “Woah, cô thật xấu”.", postprocess("He muttered, “woah, you were bad”.", "Anh ta lẩm bẩm: “Aa, cô thật xấu”."))


class ContinuationJoinTests(unittest.TestCase):
    def test_continuation_piece_is_lowercased_but_sentence_starts_and_names_are_kept(self):
        from vntext.mt_strategies import _join_continuations

        self.assertEqual("Tôi nghĩ rằng bạn đúng", _join_continuations([("I think ", "Tôi nghĩ "), ("that you are right", "Rằng bạn đúng")]))
        self.assertEqual("Xin chào. Bạn khỏe không", _join_continuations([("Hello. ", "Xin chào. "), ("How are you", "Bạn khỏe không")]))
        self.assertEqual("Tôi gặp Bambi", _join_continuations([("I met ", "Tôi gặp "), ("Bambi", "Bambi")]))
        self.assertEqual("Tôi gặp NASA", _join_continuations([("I met ", "Tôi gặp "), ("the NASA", "NASA")]))


class StretchedWordTests(unittest.TestCase):
    def test_stretched_known_word_is_collapsed_but_sfx_and_names_keep_their_bytes(self):
        from vntext.mt_strategies import _normalise_mixed_case_for_mt as normalise

        self.assertEqual("I yelled 'stop!' quick", normalise("I yelled 'stoppp!' quick"))
        self.assertEqual("yes, no", normalise("yesss, nooo"))
        self.assertEqual("hmmm zzzz Aaaah Bellla", normalise("hmmm zzzz Aaaah Bellla"))


class ParentheticalExteriorTests(unittest.TestCase):
    def test_plain_exterior_prose_keeps_sentence_context_and_trailing_space(self):
        from vntext.mt_strategies import translate_parenthetical_segments_ct2

        class Stub:
            def __init__(self):
                self.seen = []

            def translate(self, text):
                self.seen.append(text)
                return {"Hmm.": "Hmm.", "I am sorry.": "Tôi xin lỗi.", "Hmm. I am sorry.": "Hmm. Tôi xin lỗi.", "Hmm. I am sorry. ": "Hmm. Tôi xin lỗi.", "Somehow, his cock got even harder.": "Bằng cách nào đó, nó cứng hơn."}.get(text, "Ngay cả khi tôi không muốn đi,")

            def translate_many(self, texts):
                self.seen.extend(texts)
                return [self.translate(t) for t in texts]

        stub = Stub()
        out = translate_parenthetical_segments_ct2("Even if I did not want to go, (Hmm. I am sorry.) Somehow, his cock got even harder.", stub)
        self.assertIn("Somehow, his cock got even harder.", stub.seen)
        self.assertIn("đi, (", out)
        self.assertTrue(out.endswith("Bằng cách nào đó, nó cứng hơn."))


class QuoteSpacingTests(unittest.TestCase):
    def test_space_after_an_opening_quote_is_removed_only_when_the_source_has_none(self):
        self.assertEqual('Tôi hét "dừng lại!" nhanh.', postprocess("I yelled 'stop!' fast.", 'Tôi hét " dừng lại!" nhanh.'))
        self.assertEqual('Tôi hét " dừng lại!" nhanh.', postprocess('I yelled " stop!" fast.', 'Tôi hét " dừng lại!" nhanh.'))


if __name__ == "__main__":
    unittest.main()
