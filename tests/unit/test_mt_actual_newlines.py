"""Real CSV line breaks must survive MT masking and every shared write gate."""
import re
import unittest

from vntext.mt_check import structural_problems
from vntext.mt_translation_safety import collect_spans, mask_text, restore_text, validate_candidate
from vntext.patch_gate import patch_skip_reason


class ActualNewlineTests(unittest.TestCase):
    def test_real_line_breaks_are_protected_without_splitting_crlf(self):
        source = "First\r\nSecond\nThird\rFourth\\nLast"
        spans = collect_spans(source, protect_lexical=False, key_prefix=False)
        breaks = [text for _, _, text, kind in spans if kind == "tech"]
        self.assertEqual(breaks, ["\r\n", "\n", "\r", "\\n"])

    def test_flattened_or_reencoded_warning_is_blocked(self):
        row = {"source_text": "Load this game?\nUnsaved progress will be lost."}
        for candidate in (
            "Tải trò chơi? Tiến trình chưa lưu sẽ bị mất.",
            "Tải trò chơi?\\nTiến trình chưa lưu sẽ bị mất.",
            "Tải trò chơi?\r\nTiến trình chưa lưu sẽ bị mất.",
        ):
            with self.subTest(candidate=candidate):
                self.assertIn("actual newline mismatch", structural_problems(row, candidate))
                self.assertIn("actual newline mismatch", validate_candidate(row, candidate, set()))

    def test_preserved_breaks_are_allowed_and_invented_breaks_blocked(self):
        row = {"source_text": "First\r\nSecond\nThird"}
        self.assertNotIn("actual newline mismatch", structural_problems(row, "Một\r\nHai\nBa"))
        self.assertIn("actual newline mismatch", structural_problems({"source_text": "First"}, "Một\n"))

    def test_literal_newline_guard_remains_independent(self):
        reasons = structural_problems({"source_text": "First\\nSecond"}, "Một\nHai")
        self.assertIn("actual newline mismatch", reasons)
        self.assertTrue(any(reason.startswith("literal newline count") for reason in reasons))

    def test_mask_restore_roundtrip_preserves_exact_csv_breaks(self):
        source = "Load this game?\r\nUnsaved progress will be lost.\n{name}\\nEnd"
        masked, tokens, kinds, prepared = mask_text(source)
        self.assertNotIn("\r", masked)
        self.assertNotIn("\n", masked)
        restored = restore_text(masked, tokens, kinds)
        self.assertEqual(re.findall(r"\\n|\r\n|\r|\n", restored), ["\r\n", "\n", "\\n"])
        self.assertIn("{name}", restored)
        self.assertEqual(prepared, source)

    def test_patch_gate_refuses_flattened_translation(self):
        entry = {"source_text": "Load this game?\nUnsaved progress will be lost.", "key": "warning"}
        reason = patch_skip_reason(entry, "Tải trò chơi? Tiến trình chưa lưu sẽ bị mất.", set())
        self.assertIn("actual newline mismatch", reason)


if __name__ == "__main__":
    unittest.main()
