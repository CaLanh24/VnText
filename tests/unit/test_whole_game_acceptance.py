import unittest

from tests.tools.whole_game_acceptance import esc, row_invariants


class WholeGameAcceptanceTests(unittest.TestCase):
    def test_row_invariants_detect_each_contract_break(self):
        self.assertEqual([], row_invariants("Hi [name]! {b}x{/b}\nok", "Chào [name]! {b}x{/b}\nđược"))
        self.assertEqual(["placeholder"], row_invariants("Hi [name]", "Chào"))
        self.assertEqual(["tags"], row_invariants("{b}x{/b}", "x"))
        self.assertEqual(["newline"], row_invariants("a\nb", "a b"))
        self.assertIn("encoding", row_invariants("dung", "du" + chr(0x300) + "ng"))  # decomposed (non-NFC) diacritic found in the real 311-row CSV
        self.assertIn("encoding", row_invariants("x", "x" + chr(0xFFFD)))

    def test_overlay_escape_matches_renpy_string_form(self):
        bs = chr(92)
        self.assertEqual("a " + bs + '"b' + bs + '"' + bs + "nc" + bs + bs, esc('a "b"' + chr(10) + "c" + bs))


if __name__ == "__main__":
    unittest.main()
