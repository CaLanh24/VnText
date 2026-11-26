"""0.1.38: every machine-translation check code shown to a person has a Vietnamese label (a screenshot of the build confirmation showed 'question mark lost')."""
import re
import unittest
from pathlib import Path

from vntext.patch_gate import REASON_LABELS_VI, reason_label_vi

ROOT = Path(__file__).resolve().parents[2]


def _has_vietnamese(text):
    return any(ord(ch) > 127 for ch in text)


class ReasonLabelTests(unittest.TestCase):
    def test_every_structural_problem_code_has_a_vietnamese_label(self):
        source = (ROOT / "vntext" / "mt_check.py").read_text(encoding="utf-8")
        codes = set(re.findall(r"out\.append\('([a-z][a-z /]+?)(?: %d| ->|:|')", source))
        codes |= {"question mark lost", "question split into separate sentences", "money/percent mismatch", "url mismatch"}
        self.assertGreater(len(codes), 10)
        missing = [f"{code} -> {reason_label_vi(code)}" for code in sorted(codes) if not _has_vietnamese(reason_label_vi(code))]
        self.assertEqual([], missing)

    def test_no_label_leaks_a_developer_word(self):
        for code, label in REASON_LABELS_VI.items():
            for banned in ("review_only", "mt_blocked", "human_review", "locator", "bucket", "profile legacy", "extract lại", "placeholder", "Synonym"):
                self.assertNotIn(banned, label, code)


if __name__ == "__main__":
    unittest.main()
