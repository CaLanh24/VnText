"""Post-translation repair must not rewrite correct Vietnamese that merely looks like a dictionary token.

Evidence: the repair turned "lý do" into "lý làm" (12 of 310 real-game rows) and "kiểm soát" into "kiểm vậyát" because the English dictionary
has ``do``/``so`` and the boundary test was ASCII-only.  Brain's repros: ``In trang này`` -> ``trong trang này`` and ``quả me`` -> ``quả em``.
Genuine English leftovers must still be repaired, and user text is never Unicode-normalized.
"""

import unicodedata
import unittest

from vntext.mt_translation_constants import GENERAL_EN_VI_TERMS, VIETNAMESE_HOMOGRAPH_TERMS, is_vietnamese_homograph
from vntext.mt_translation_safety import postprocess

# Every dictionary key of at most three letters, audited one by one: none of these is a diacritic-free Vietnamese word, so their repair stays.
# Adding a short key to the dictionary fails test_short_keys_are_audited until it is reviewed and listed here or in the homograph set.
AUDITED_NOT_HOMOGRAPH = frozenset(
    "act ado ago ahc ahe aim all and ap aps as ass bad bar bit bla boy bug cab chu cor cry cum dev dms dy eek ek end etc ew fan for fun get got "
    "hah has hek her hey hh hi him his if job juh kky kya lie ll log max met new of oh ol old one oop or out pay phh pre psh red req sea see set "
    "sex shh sis sub tag the tps tw tx uhh umm use ver vu we wet wip wp xp yep yo you yuu".split()
)


class VietnameseHomographRepairTests(unittest.TestCase):
    def test_vietnamese_do_is_not_rewritten_as_the_english_verb(self):
        out = postprocess("There were a hundred reasons I should not go.", "Có một trăm lý do tôi không nên đi.")
        self.assertEqual("Có một trăm lý do tôi không nên đi.", out)

    def test_source_token_do_does_not_corrupt_vietnamese_do(self):
        out = postprocess("I do not know the reasons.", "Tôi không biết lý do.")
        self.assertEqual("Tôi không biết lý do.", out)

    def test_ascii_boundary_does_not_split_vietnamese_words(self):
        out = postprocess("So much so, they watched me.", "Đến mức họ kiểm soát tôi.")
        self.assertEqual("Đến mức họ kiểm soát tôi.", out)
        self.assertNotIn("vậyát", out)

    def test_brain_repros_in_and_me_stay_vietnamese(self):
        self.assertEqual("In trang này.", postprocess("Print this page.", "In trang này."))
        self.assertEqual("Mẹ cho tôi quả me.", postprocess("Me and my mother.", "Mẹ cho tôi quả me."))
        self.assertEqual("Men rượu và man rợ.", postprocess("Yeast and savage.", "Men rượu và man rợ."))

    def test_genuine_english_leftovers_are_still_repaired(self):
        self.assertEqual("thư viện", postprocess("Gallery", "Gallery"))
        self.assertEqual("kết thúc của trò chơi", postprocess("Ending of the game", "Ending of trò chơi"))
        self.assertEqual("Chúng tôi ở nhà", postprocess("We are at home", "Chúng tôi ở home"))

    def test_literal_newline_branch_respects_word_boundaries(self):
        # A source word "home" is repaired right after a literal backslash-n separator, but never inside a longer word ("homeless").
        sep = chr(92) + "n"
        self.assertEqual("Xin chào" + sep + "nhà", postprocess("Hello" + sep + "home", "Xin chào" + sep + "home"))
        self.assertEqual("Xin chào" + sep + "homeless", postprocess("Hello" + sep + "home", "Xin chào" + sep + "homeless"))
        self.assertEqual("Họ" + sep + "kiểm soát", postprocess("They" + sep + "so", "Họ" + sep + "kiểm soát"))
        self.assertEqual("Họ" + sep + "soát", postprocess("They" + sep + "so", "Họ" + sep + "soát"))

    def test_decomposed_vietnamese_is_not_split_or_normalized(self):
        marked = "Tôi ở home" + chr(0x0301)  # "home" + COMBINING ACUTE is one Vietnamese-looking word, not the English token
        self.assertEqual(marked, postprocess("At home", marked))
        self.assertEqual(marked, postprocess("Hello", marked))
        word = unicodedata.normalize("NFD", "lý do")  # decomposed Vietnamese comes back byte-for-byte: user text is never normalized
        self.assertEqual(word, postprocess("A reason", word))
        self.assertEqual(word, postprocess("I do not know", word))

    def test_placeholder_echo_removal_never_cuts_into_vietnamese_words(self):
        # A placeholder named {i}/{a} used to blank the "i" of "Đi" and the "a" of "ưa" (ASCII-only word boundary).
        self.assertEqual("Đi lấy vàng: {i}", postprocess("Gold: {i}", "Đi lấy vàng: {i}"))
        self.assertEqual("Giá trị {a}, ưa thích", postprocess("Value {a}", "Giá trị {a}, ưa thích"))
        self.assertEqual("Giá {x} tại đây", postprocess("Cost {x}", "Giá {x} tại đây"))
        # the intended behaviour stays: a bare echo of the placeholder name is removed
        echoed = postprocess("Name {mName}", "Tên mName {mName}")
        self.assertEqual(1, echoed.count("mName"))
        self.assertIn("{mName}", echoed)

    def test_homograph_set_is_exact_and_dictionary_backed(self):
        for token in ("Do", "so", "IN", "Me", "men", "man"):
            self.assertTrue(is_vietnamese_homograph(token), token)
        self.assertFalse(is_vietnamese_homograph("gallery"))
        self.assertTrue(VIETNAMESE_HOMOGRAPH_TERMS <= set(GENERAL_EN_VI_TERMS))

    def test_short_keys_are_audited(self):
        short = {key for key in GENERAL_EN_VI_TERMS if len(key) <= 3}
        self.assertEqual(set(), short - AUDITED_NOT_HOMOGRAPH - VIETNAMESE_HOMOGRAPH_TERMS, "new short dictionary key needs a homograph audit")


class _StubTranslator:
    """Stands in for the CT2 model: returns a fixed, correct Vietnamese sentence so only the pipeline's own code can change it."""

    def __init__(self, answers):
        self.answers = answers

    def translate_many(self, texts):
        return [self.answers.get(text, text) for text in texts]


class ChunkPipelineKeepsCorrectVietnameseTests(unittest.TestCase):
    def test_full_chunk_pipeline_keeps_ly_do_in_and_me(self):
        from vntext import mt_ct2_io

        cases = {
            "There were a thousand and one reasons I should not go back to them.": "Có hàng ngàn lý do tôi không nên quay lại với họ.",
            "Print this page.": "In trang này.",
            "Me and my mother.": "Mẹ cho tôi quả me.",
        }
        rows = [{"key": f"k{i}", "source_text": src, "context": "RenPy:game/script.rpy:1:start", "import_method": "renpy_dialogue"} for i, src in enumerate(cases)]
        out = mt_ct2_io._batch_translate_chunk(_StubTranslator(cases), rows)
        for i, src in enumerate(cases):
            self.assertEqual(cases[src], out[f"k{i}"])


if __name__ == "__main__":
    unittest.main()
