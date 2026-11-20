from __future__ import annotations

import unittest

from vntext.extract_naninovel import is_naninovel_localization_document, plausible_text
from vntext.extract_text import iter_textasset_lines

DOC = (
    "; Russian <ru> to English <en> localization document for `1CHAPTER` naninovel script\n\n"
    "# 9\n; <color=#FF4026>Время проснуться</color>\n<color=#FF4026>Time to wake up</color>\n\n"
    "# a\n; Кому там не терпится пообщаться со мной?\nWho can't wait to talk to me?\n\n"
    "# b\n; Материал и ресурсы.\nThe material and resources were transformed.\n"
)


class NaninovelLocalizationDocumentTests(unittest.TestCase):
    def test_header_accepts_a_story_document_the_whole_text_noise_filter_rejects(self):
        self.assertFalse(plausible_text(DOC), "fixture must trip the engine-word heuristic (material/transform/resources)")
        self.assertTrue(is_naninovel_localization_document(DOC))
        lines = [parsed["text"] for _index, parsed in iter_textasset_lines(DOC)]
        self.assertIn("Who can't wait to talk to me?", lines)

    def test_only_the_exact_header_shape_is_accepted(self):
        for text in ("", "plain text with material", "; Russian <ru> localization document\n", "x\n; Russian <ru> to English <en> localization document for `A` naninovel script",
                     "; Russian to English localization document for `A` naninovel script\n"):
            with self.subTest(text=text[:40]):
                self.assertFalse(is_naninovel_localization_document(text))
        self.assertTrue(is_naninovel_localization_document("; Russian <ru> to Chinese <zh-CN> localization document for `2CHAPTER` naninovel script\n"))


if __name__ == "__main__":
    unittest.main()
