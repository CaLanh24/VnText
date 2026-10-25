"""Typed printf and inline-URL carriers: protected spans, exact restoration, structural gate."""

from __future__ import annotations

import sys
from pathlib import Path


def _tests_lib_on_path() -> None:
    cur = Path(__file__).resolve().parent
    while cur.name != "tests" and cur.parent != cur:
        cur = cur.parent
    lib = cur / "lib"
    if str(lib) not in sys.path:
        sys.path.insert(0, str(lib))


_tests_lib_on_path()
from bootstrap import bootstrap

TESTS, ROOT, LIB = bootstrap(__file__)

import unittest

from vntext import mt_check
from vntext.mt_check import load_whitelist, structural_problems
from vntext.mt_ct2_pipeline import _blocker_record
from vntext.mt_strategies import candidate_quality_issues
from vntext.mt_translation_safety import mask_text, restore_text, translate_protected

PRINTF_SOURCE = "NPC: You have %d new messages and %s unread letters."
URL_SOURCE = "NPC: URL https://example.invalid/page?x=1&y=2 stays as is."


def _row(source: str) -> dict:
    return {
        "key": "k",
        "source_text": source,
        "context": "line:1",
        "file_path": "dialogue.txt",
        "import_method": "plain_text_line",
        "backend": "plain_text",
    }


class TypedCarrierDetectionTests(unittest.TestCase):
    def test_printf_specifiers_are_typed_and_ordered(self):
        self.assertEqual(mt_check.printf_specifiers(PRINTF_SOURCE), ["%d", "%s"])
        self.assertEqual(
            mt_check.printf_specifiers("%1$s %2$d %-5.2f %ld %05d 100%% done"),
            ["%1$s", "%2$d", "%-5.2f", "%ld", "%05d", "%%"],
        )

    def test_literal_percent_in_prose_is_not_a_specifier(self):
        for text in (
            "NPC: Percent 100% sure of it.",
            "The price is $5.00 (tax: 8%) - do you accept?",
            "50% off, 5% s, 20%discount",
            "Success rate 75%.",
        ):
            with self.subTest(text=text):
                self.assertEqual(mt_check.printf_specifiers(text), [])
                self.assertEqual(structural_problems(_row(text), text), [])

    def test_inline_url_excludes_trailing_sentence_punctuation(self):
        self.assertEqual(
            mt_check.inline_urls(URL_SOURCE), ["https://example.invalid/page?x=1&y=2"]
        )
        self.assertEqual(mt_check.inline_urls("See (http://x.y/z), ok."), ["http://x.y/z"])
        self.assertEqual(mt_check.inline_urls("Visit https://x.y/z."), ["https://x.y/z"])
        self.assertEqual(mt_check.inline_urls("no scheme example.invalid/page?x=1"), [])


class TypedCarrierProtectionTests(unittest.TestCase):
    def test_mask_protects_and_restores_carriers_exactly(self):
        for source, carriers in (
            (PRINTF_SOURCE, ["%d", "%s"]),
            (URL_SOURCE, ["https://example.invalid/page?x=1&y=2"]),
            ("Score %d%% at https://a.b/c?d=1&e=2", ["%d", "%%", "https://a.b/c?d=1&e=2"]),
        ):
            with self.subTest(source=source):
                masked, tokens, kinds, _prepared = mask_text(source)
                for carrier in carriers:
                    self.assertIn(carrier, tokens)
                    self.assertNotIn(carrier, masked)
                restored = restore_text(masked, tokens, kinds)
                self.assertEqual(mt_check.printf_specifiers(restored), mt_check.printf_specifiers(source))
                self.assertEqual(mt_check.inline_urls(restored), mt_check.inline_urls(source))

    def test_protected_translation_restores_carriers_even_when_model_mangles_text(self):
        def damaging_translator(text: str) -> str:
            # A model only ever sees the text between protected spans.
            return "Bản dịch " + text.strip().replace("?", " ?").replace("&", "& ")

        for source in (PRINTF_SOURCE, URL_SOURCE):
            with self.subTest(source=source):
                out = translate_protected(source, damaging_translator, always_attempt=True)
                self.assertEqual(mt_check.printf_specifiers(out), mt_check.printf_specifiers(source))
                self.assertEqual(mt_check.inline_urls(out), mt_check.inline_urls(source))
                self.assertEqual(structural_problems(_row(source), out), [])


class TypedCarrierStructuralTests(unittest.TestCase):
    def test_correct_printf_draft_passes_structure_and_quality(self):
        draft = "NPC: Bạn có %d tin nhắn mới và %s thư chưa đọc."
        row = _row(PRINTF_SOURCE)
        self.assertEqual(structural_problems(row, draft), [])
        self.assertEqual(candidate_quality_issues(row, draft, load_whitelist()), [])

    def test_correct_url_draft_passes_structure_and_quality(self):
        draft = "NPC: Địa chỉ https://example.invalid/page?x=1&y=2 giữ nguyên như vậy."
        row = _row(URL_SOURCE)
        self.assertEqual(structural_problems(row, draft), [])
        self.assertEqual(candidate_quality_issues(row, draft, load_whitelist()), [])

    def test_printf_lost_damaged_extra_or_reordered_is_rejected(self):
        row = _row(PRINTF_SOURCE)
        for label, draft in (
            ("lost", "NPC: Bạn có %d tin nhắn mới và thư chưa đọc."),
            ("damaged", "NPC: Bạn có % d tin nhắn mới và %s thư chưa đọc."),
            ("extra", "NPC: Bạn có %d tin nhắn mới và %s thư chưa đọc %d."),
            ("reordered", "NPC: Bạn có %s tin nhắn mới và %d thư chưa đọc."),
            ("type-changed", "NPC: Bạn có %d tin nhắn mới và %d thư chưa đọc."),
        ):
            with self.subTest(case=label):
                self.assertIn("printf specifier mismatch", structural_problems(row, draft))

    def test_printf_escape_percent_must_survive(self):
        row = _row("Loading %d%% complete")
        self.assertEqual(structural_problems(row, "Đang tải %d%% hoàn tất"), [])
        self.assertIn("printf specifier mismatch", structural_problems(row, "Đang tải %d% hoàn tất"))

    def test_numbered_specifiers_may_move_but_not_vanish(self):
        row = _row("Hello %1$s, you have %2$d items")
        self.assertEqual(structural_problems(row, "Bạn có %2$d vật phẩm, chào %1$s"), [])
        self.assertIn(
            "printf specifier mismatch", structural_problems(row, "Chào %1$s, bạn có vật phẩm")
        )

    def test_url_lost_damaged_extra_or_changed_is_rejected(self):
        row = _row(URL_SOURCE)
        for label, draft in (
            ("lost", "NPC: Địa chỉ trang giữ nguyên như vậy."),
            ("scheme-damaged", "NPC: Địa chỉ https example.invalid/page?x=1&y=2 giữ nguyên."),
            ("query-spaced", "NPC: Địa chỉ https://example.invalid/page ?x=1& y=2 giữ nguyên."),
            ("query-changed", "NPC: Địa chỉ https://example.invalid/page?x=1 giữ nguyên."),
            ("extra", "NPC: Địa chỉ https://example.invalid/page?x=1&y=2 và https://other.invalid/ giữ."),
        ):
            with self.subTest(case=label):
                self.assertIn("url mismatch", structural_problems(row, draft))

    def test_existing_placeholder_and_tag_protections_stay_strict(self):
        row = _row("Hello {player_name}, <b>stay</b> close.")
        self.assertIn("placeholder mismatch", structural_problems(row, "Chào {player}, <b>ở</b> gần."))
        self.assertIn("tag mismatch", structural_problems(row, "Chào {player_name}, ở gần."))

    def test_lone_short_residue_still_rejected_outside_carriers(self):
        row = _row("Take it to the market now.")
        issues = candidate_quality_issues(row, "Mang nó đến chợ ngay s", load_whitelist())
        self.assertTrue(any("residual short token: s" in issue for issue in issues), issues)


class NumericCarrierTests(unittest.TestCase):
    PRICE = "NPC: The price is $5.00 (tax: 8%) - do you accept?"

    def test_money_and_percent_are_detected_without_touching_prose_percent(self):
        self.assertEqual(mt_check.numeric_carriers(self.PRICE), ["$5.00", "8%"])
        self.assertEqual(mt_check.numeric_carriers("Kostet 5,00 € oder 1.000,50 €"), ["5,00 €", "1.000,50 €"])
        self.assertEqual(mt_check.numeric_carriers("100% sure, 7.5%."), ["100%", "7.5%"])
        # printf conversion and escape are not percentages
        self.assertEqual(mt_check.numeric_carriers("Loading 50%d and 50%% done"), [])
        self.assertEqual(mt_check.numeric_carriers("Buy 3 potions for 120 gold"), [])

    def test_native_bad_price_translation_is_rejected(self):
        row = _row(self.PRICE)
        bad = "NPC: Giá là 5 đô.00 đô-la."
        problems = structural_problems(row, bad)
        self.assertIn("money/percent mismatch", problems)
        self.assertIn("question mark lost", problems)

    def test_price_with_exact_carriers_and_question_passes(self):
        row = _row(self.PRICE)
        good = "NPC: Giá là $5.00 (thuế: 8%) - bạn có chấp nhận không?"
        self.assertEqual(structural_problems(row, good), [])

    def test_money_percent_lost_changed_or_extra_is_rejected(self):
        row = _row(self.PRICE)
        for label, draft in (
            ("percent lost", "NPC: Giá là $5.00 - bạn chấp nhận không?"),
            ("money changed", "NPC: Giá là $5.50 (thuế: 8%) - chấp nhận không?"),
            ("percent changed", "NPC: Giá là $5.00 (thuế: 80%) - chấp nhận không?"),
            ("extra", "NPC: Giá là $5.00 (thuế: 8% 9%) - chấp nhận không?"),
        ):
            with self.subTest(case=label):
                self.assertIn("money/percent mismatch", structural_problems(row, draft))

    def test_question_mark_only_required_when_source_asks(self):
        self.assertEqual(structural_problems(_row("NPC: It is fine."), "NPC: Không sao."), [])
        self.assertIn("question mark lost", structural_problems(_row('NPC: "Are you ready?"'), 'NPC: "Bạn sẵn sàng chưa."'))
        self.assertEqual(structural_problems(_row('NPC: "Are you ready?"'), 'NPC: "Bạn sẵn sàng chưa?"'), [])

    def test_dropped_closing_parenthesis_is_rejected_only_for_balanced_sources(self):
        row = _row(self.PRICE)
        damaged = "NPC: Giá là $5.00 (thuế: 8%- bạn chấp nhận không?"
        self.assertIn("parenthesis clause damaged", structural_problems(row, damaged))
        # An unbalanced source (emoticon) is not held to balance.
        self.assertEqual(structural_problems(_row("NPC: Thanks :)"), "NPC: Cảm ơn"), [])

    def test_masking_protects_money_and_percent(self):
        masked, tokens, kinds, _ = mask_text(self.PRICE)
        self.assertIn("$5.00", tokens)
        self.assertIn("8%", tokens)
        self.assertNotIn("$5.00", masked)
        self.assertNotIn("8%", masked)


class PrintfOrderSemanticsTests(unittest.TestCase):
    def test_mixed_numbered_and_unnumbered_keep_exact_order(self):
        row = _row("%s then %1$s then %d")
        self.assertEqual(structural_problems(row, "%s rồi %1$s rồi %d"), [])
        for draft in ("%1$s rồi %s rồi %d", "%d rồi %1$s rồi %s", "%s rồi %d rồi %1$s"):
            with self.subTest(draft=draft):
                self.assertIn("printf specifier mismatch", structural_problems(row, draft))

    def test_multiple_unnumbered_around_numbered_cannot_swap(self):
        row = _row("%s, %2$s, %d")
        self.assertIn("printf specifier mismatch", structural_problems(row, "%d, %2$s, %s"))

    def test_all_numbered_order_is_free_but_content_is_not(self):
        row = _row("%1$s has %2$d")
        self.assertEqual(structural_problems(row, "%2$d của %1$s"), [])
        self.assertIn("printf specifier mismatch", structural_problems(row, "%1$s có %1$d"))
        self.assertIn("printf specifier mismatch", structural_problems(row, "%1$s có"))

    def test_percent_escape_carries_no_argument_but_must_survive(self):
        row = _row("%1$s is %2$d%% done")
        self.assertEqual(structural_problems(row, "%2$d%% xong cho %1$s"), [])
        self.assertIn("printf specifier mismatch", structural_problems(row, "%2$d xong cho %1$s"))
        self.assertIn("printf specifier mismatch", structural_problems(row, "%2$d%%%% xong cho %1$s"))
        unnumbered = _row("%d%% then %s")
        self.assertEqual(structural_problems(unnumbered, "%d%% rồi %s"), [])
        self.assertIn("printf specifier mismatch", structural_problems(unnumbered, "%s rồi %d%%"))

    def test_supported_grammar_bounds(self):
        supported = ["%d", "%5d", "%-5d", "%05.2f", "%.3s", "%*d", "%.*f", "%ld", "%lld", "%hhd", "%zu", "%x", "%X", "%o",
                     "%e", "%g", "%c", "%p", "%1$s", "%12$05d"]
        for spec in supported:
            with self.subTest(spec=spec):
                self.assertEqual(mt_check.printf_specifiers(f"a {spec} b"), [spec])
        # Outside the grammar: not carriers (no protection, no false rejection).
        for text in ("a %n b", "a %q b", "a % d b", "a %1$*2$d b", "a %", "a %5 b", "50%off", "5%d"):
            with self.subTest(text=text):
                self.assertEqual(mt_check.printf_specifiers(text), [])


class TypedCarrierInventoryTests(unittest.TestCase):
    def test_classifier_and_blocker_inventory_count_the_same_carriers(self):
        row = _row("NPC: %d messages at https://example.invalid/page?x=1&y=2 and {name}")
        record = _blocker_record(
            row, strategy="row_protected", raw_output="", reasons=["quality: x"]
        )
        features = record["source_features"]
        self.assertEqual(features["printf_count"], 1)
        self.assertEqual(features["url_count"], 1)
        self.assertEqual(features["placeholder_count"], 2)
        shape = record["classification"]["classifier_v2"]["evidence"]["source_shape"]
        self.assertTrue(shape["has_placeholder"])

    def test_plain_prose_has_no_carriers(self):
        record = _blocker_record(
            _row("NPC: It is 100% fine."), strategy="row_protected", raw_output="", reasons=[]
        )
        self.assertEqual(record["source_features"]["placeholder_count"], 0)
        self.assertEqual(record["source_features"]["printf_count"], 0)
        shape = record["classification"]["classifier_v2"]["evidence"]["source_shape"]
        self.assertFalse(shape["has_placeholder"])


if __name__ == "__main__":
    unittest.main()
