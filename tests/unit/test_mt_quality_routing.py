"""Regression tests for translation quality routing and explicit keeps."""

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

from vntext.mt_check import english_report, load_whitelist, structural_problems
from vntext.mt_strategies import candidate_quality_issues


class MtQualityRoutingTests(unittest.TestCase):
    def test_repeated_model_output_is_rejected_for_player_text(self):
        row = {
            "source_text": "Please check the file.",
            "translation": "bởi bởi bởi bởi bởi bởi bởi bởi",
            "context": "NaninovelScript:fixture:1",
        }
        self.assertTrue(candidate_quality_issues(row, row["translation"], load_whitelist()))

    def test_explicit_vocalisation_keep_is_allowed(self):
        row = {
            "source_text": "*hmm... uh*",
            "translation": "*hmm... uh*",
            "context": "NaninovelScript:fixture:2",
        }
        self.assertEqual(candidate_quality_issues(row, row["translation"], load_whitelist()), [])

    def test_vietnamese_candidate_with_structural_tokens_is_accepted(self):
        row = {
            "source_text": "Take {mName} to <color=yellow>Park</color>.",
            "translation": "Đưa {mName} đến <color=yellow>Công viên</color>.",
            "context": "TextAsset:ui:line",
        }
        self.assertEqual(candidate_quality_issues(row, row["translation"], load_whitelist()), [])

    def test_content_loss_is_rejected_for_player_dialogue(self):
        row = {
            "source_text": "Read the guide, download the update, and restart the app when prompted.",
            "translation": "Đọc hướng dẫn.",
            "context": "NaninovelScript:fixture:3",
        }
        self.assertIn(
            "quality: content loss",
            candidate_quality_issues(row, row["translation"], load_whitelist()),
        )

    def test_residual_english_is_rejected_after_placeholder_preservation(self):
        row = {
            "source_text": "Take {mName} to <color=yellow>the park</color>.",
            "translation": "Đưa {mName} đến <color=yellow>the park</color>.",
            "context": "NaninovelScript:benchmark",
        }
        self.assertTrue(candidate_quality_issues(row, row["translation"], load_whitelist()))

    def test_source_proper_name_is_allowed_but_english_headword_is_not(self):
        row = {
            "source_text": "SampleName felt refreshed walking in the park.",
            "translation": "SampleName cảm thấy thoải mái hơn khi đi dạo trong công viên.",
            "context": "NaninovelScript:fixture-proper-name",
        }
        self.assertEqual(candidate_quality_issues(row, row["translation"], load_whitelist()), [])

        bad = dict(row)
        bad["source_text"] = "The park felt quiet."
        bad["translation"] = "The công viên yên tĩnh."
        self.assertTrue(candidate_quality_issues(bad, bad["translation"], load_whitelist()))

    def test_source_sfx_and_opaque_terms_are_not_residual_english(self):
        source = "*GLRK* *GLRK* [br](SampleName serves sushi at the bar.)"
        translation = "*GLRK* *GLRK* [br](SampleName phục vụ sushi ở quán bar.)"
        self.assertEqual(
            candidate_quality_issues(
                {
                    "source_text": source,
                    "translation": translation,
                    "context": "NaninovelScript:benchmark",
                },
                translation,
                load_whitelist(),
            ),
            [],
        )

    def test_bounded_loanwords_and_source_literals_are_not_residual_english(self):
        source = "SampleName went to the cocktail bar after the karaoke show."
        translation = "SampleName đi đến cocktail bar sau buổi karaoke."
        self.assertEqual(
            candidate_quality_issues(
                {
                    "source_text": source,
                    "translation": translation,
                    "context": "NaninovelScript:benchmark",
                },
                translation,
                load_whitelist(),
            ),
            [],
        )

    def test_phase_c_sample_residual_english_is_rejected(self):
        row = {
            "source_text": "(Carry {itemName} into the {STORAGE}, then place it beside {MARKER}.)",
            "translation": "(Mang {itemName} into the {STORAGE}, rồi đặt nó cạnh {MARKER}.)",
            "context": "NaninovelScript:phase-c-sample",
        }
        issues = candidate_quality_issues(row, row["translation"], load_whitelist())
        self.assertTrue(
            any("quality: english-" in issue for issue in issues),
            issues,
        )

    def test_phase_c_placeholder_suffix_residue_is_structural_error(self):
        row = {
            "source_text": "({itemName} {ACTION}s before the event.)",
            "translation": "({itemName} {ACTION}ing trước sự kiện.)",
            "context": "NaninovelScript:phase-c-sample",
        }
        self.assertIn(
            "english suffix after placeholder: {ACTION}ing",
            structural_problems(row, row["translation"]),
        )

    def test_phase_c_short_ascii_residue_is_rejected(self):
        row = {
            "source_text": "Move {ITEM} to {TARGET}...",
            "translation": "Đưa {ITEM} đến {TARGET}... s",
            "context": "NaninovelScript:phase-c-sample",
        }
        issues = candidate_quality_issues(row, row["translation"], load_whitelist())
        self.assertTrue(
            any("quality: residual short token: s" in issue for issue in issues),
            issues,
        )

    def test_phase_c_spacing_and_repeated_word_artifacts_are_rejected(self):
        row = {
            "source_text": "({mName} {EJACULATE}s inside of me....♡)",
            "translation": "(Tiếng cười){mName} {EJACULATE} bên trong trong tôi...♡)",
            "context": "NaninovelScript:phase-c-sample",
        }
        issues = candidate_quality_issues(row, row["translation"], load_whitelist())
        self.assertTrue(
            any("quality: repeated token: trong" in issue for issue in issues),
            issues,
        )

        spacing_row = {
            "source_text": "({mName} {MOAN}s, and I feel his {CUM}...♡)",
            "translation": "({mName} {MOAN} , và tôi cảm nhận được {CUM}...♡)",
            "context": "NaninovelScript:phase-c-sample",
        }
        spacing_issues = candidate_quality_issues(
            spacing_row,
            spacing_row["translation"],
            load_whitelist(),
        )
        self.assertIn("quality: punctuation spacing", spacing_issues)

    def test_phase_c_glued_vocalisation_and_vietnamese_are_rejected(self):
        row = {
            "source_text": "Ahhh... {SWEARING}... Ngggghhh...♡",
            "translation": "AhhhÔi trời ơi... {SWEARING} Ngggghhh♡",
            "context": "NaninovelScript:phase-c-sample",
        }
        issues = candidate_quality_issues(row, row["translation"], load_whitelist())
        self.assertIn("quality: glued vocalisation", issues)

    def test_player_visible_identity_still_fails_for_ui_label(self):
        row = {
            "source_text": "CG GALLERY",
            "translation": "CG GALLERY",
            "context": "UI:Text",
            "import_method": "unity_ui_text",
        }
        self.assertIn(
            "quality: identity for player-visible row",
            candidate_quality_issues(row, row["translation"], load_whitelist()),
        )

    def test_content_loss_after_ellipsis_is_rejected(self):
        row = {
            "source_text": "He is very good at it. I wonder how many girls he has kissed!",
            "translation": "Anh ta rất giỏi việc đó.",
            "context": "NaninovelScript:benchmark",
        }
        self.assertIn(
            "quality: content loss",
            candidate_quality_issues(row, row["translation"], load_whitelist()),
        )

    def test_vietnamese_bare_word_and_roman_numeral_are_not_english(self):
        score, reasons = english_report(
            "The drunk fell asleep after a while.",
            "Người say ngủ một lúc.",
            load_whitelist(),
        )
        self.assertEqual((score, reasons), (0, []))
        score, reasons = english_report(
            "Invite someone card II.",
            "Mời ai đó thẻ II.",
            load_whitelist(),
        )
        self.assertEqual((score, reasons), (0, []))


if __name__ == "__main__":
    unittest.main()
