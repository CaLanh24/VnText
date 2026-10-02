"""Tests for mt_classify row actions."""

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


from vntext.mt_classify import (
    CLASSIFIER_DO_NOT_TRANSLATE,
    CLASSIFIER_REVIEW,
    CLASSIFIER_TRANSLATE,
    CLASSIFIER_UNSUPPORTED,
    CLASSIFIER_POLICY_HASH,
    CLASSIFIER_POLICY_VERSION,
    classify_row,
    classify_row_authoritative,
    classify_row_v2,
    evaluate_classifier_v2,
    is_sound_effect_line,
    is_star_sfx_line,
)
from vntext.mt_ct2_pipeline import _select_ct2_targets


class MtClassifyTests(unittest.TestCase):
    def test_authoritative_route_exposes_v2_and_preserves_legacy_action(self):
        action, reason, decision = classify_row_authoritative({
            "key": "visible-authoritative",
            "source_text": "Hello, how are you?",
            "context": "NaninovelScript:Main:print",
        })
        self.assertEqual(action, "translate")
        self.assertTrue(reason)
        self.assertEqual(decision.decision, CLASSIFIER_TRANSLATE)
        self.assertEqual(decision.legacy_action, "translate")

    def test_authoritative_route_is_fail_closed_for_raw_and_review_rows(self):
        raw_action, _raw_reason, raw_decision = classify_row_authoritative({
            "source_text": "A visible sentence",
            "import_method": "naninovel_raw_candidate",
        })
        review_action, _review_reason, review_decision = classify_row_authoritative({
            "source_text": "A visible sentence",
            "review_only": True,
        })
        self.assertEqual((raw_action, raw_decision.decision), ("unsupported", CLASSIFIER_UNSUPPORTED))
        self.assertEqual((review_action, review_decision.decision), ("review_only", CLASSIFIER_REVIEW))

    def test_ct2_target_selection_consumes_authoritative_boundary(self):
        rows = [
            {"key": "visible", "source_text": "Hello world", "translation": ""},
            {"key": "raw", "source_text": "Visible raw", "translation": "", "import_method": "naninovel_raw_candidate"},
            {"key": "review", "source_text": "Visible review", "translation": "", "review_only": True},
        ]
        targets, refresh_count = _select_ct2_targets(
            rows, {}, allow_overwrite=False, glossary_v2={"entries": []}
        )
        self.assertEqual([row["key"] for row in targets], ["visible"])
        self.assertEqual(refresh_count, 0)

    def test_v2_player_visible_decision_has_policy_and_metadata_evidence(self):
        result = classify_row_v2({
            "key": "visible-1",
            "source_text": "Hello, how are you?",
            "context": "NaninovelScript:Main:print",
            "file_path": "StreamingAssets/Scripts/Main.nani",
            "import_method": "naninovel_script_string",
            "backend": "naninovel",
            "locator": {"path_id": 7, "field_path": "m_Text"},
            "patch_proof": {"reader": True, "writer": True},
        })
        self.assertEqual(result.decision, CLASSIFIER_TRANSLATE)
        self.assertEqual(result.ledger, "translation")
        self.assertEqual(result.reason_code, "PLAYER_VISIBLE_COPY")
        self.assertEqual(result.policy_version, CLASSIFIER_POLICY_VERSION)
        self.assertEqual(result.policy_hash, CLASSIFIER_POLICY_HASH)
        self.assertEqual(result.evidence["engine_family"], "naninovel")
        self.assertTrue(result.evidence["patch_proof_present"])
        self.assertTrue(result.evidence["patch_proof_complete"])
        self.assertEqual(result.evidence["locator_fields"], ["field_path", "path_id"])

    def test_v2_hard_boundaries_never_route_raw_or_review_to_translation(self):
        raw = classify_row_v2({
            "key": "raw-1",
            "source_text": "A visible sentence",
            "import_method": "naninovel_raw_candidate",
            "review_only": False,
        })
        review = classify_row_v2({
            "key": "review-1",
            "source_text": "Another visible sentence",
            "import_method": "unity_typetree_field",
            "review_only": True,
        })
        self.assertEqual(raw.decision, CLASSIFIER_UNSUPPORTED)
        self.assertEqual(raw.ledger, "review_only")
        self.assertEqual(raw.reason_code, "UNSUPPORTED_RAW_ROUTE")
        self.assertEqual(review.decision, CLASSIFIER_REVIEW)
        self.assertEqual(review.ledger, "review_only")
        self.assertEqual(review.reason_code, "EXTRACT_REVIEW_ONLY")

    def test_v2_technical_and_literal_routes_have_separate_ledgers(self):
        technical = classify_row_v2({
            "key": "tech-1",
            "source_text": "Assets/Scenes/Main.unity",
            "file_path": "StreamingAssets/config.json",
        })
        literal = classify_row_v2({
            "key": "literal-1",
            "source_text": "*GLRRRK*!!!",
            "context": "TextAsset:Main",
        })
        self.assertEqual(technical.decision, CLASSIFIER_DO_NOT_TRANSLATE)
        self.assertEqual(technical.ledger, "technical_skipped")
        self.assertEqual(literal.decision, CLASSIFIER_DO_NOT_TRANSLATE)
        self.assertEqual(literal.ledger, "intentional_keep")

    def test_v2_evaluation_reports_coverage_and_labeled_errors(self):
        rows = [
            {"key": "a", "source_text": "Hello world", "label": "player_visible"},
            {"key": "b", "source_text": "Assets/Main.unity", "label": "technical"},
            {"key": "c", "source_text": "*SFX*", "label": "intentional_keep"},
            {"key": "d", "source_text": "Unknown text", "review_only": True, "label": "review"},
        ]
        report = evaluate_classifier_v2(rows)
        self.assertTrue(report["no_drop"])
        self.assertEqual(report["rows"], 4)
        self.assertEqual(report["decision_counts"][CLASSIFIER_TRANSLATE], 1)
        self.assertEqual(report["decision_counts"][CLASSIFIER_REVIEW], 1)
        self.assertEqual(report["technical_false_positive"], 0)
        self.assertEqual(report["player_visible_false_negative"], 0)
        self.assertEqual(report["technical_leakage"], 0.0)
    def test_naninovel_label_skipped(self):
        row = {
            "source_text": "Start",
            "translation": "",
            "context": "NaninovelScript:Main",
        }
        self.assertEqual(classify_row(row)[0], "skip_technical")

    def test_naninovel_choice_label_translates(self):
        row = {
            "source_text": "Shower",
            "translation": "",
            "context": "NaninovelScript:fixture:choice",
            "import_method": "naninovel_choice",
        }
        self.assertEqual(classify_row(row)[0], "translate")

    def test_standalone_source_proper_name_is_kept(self):
        row = {
            "source_text": "SampleName",
            "translation": "",
            "context": "UI:Text",
            "import_method": "unity_ui_text",
        }
        self.assertEqual(classify_row(row)[0], "copy_literal")

        english = dict(row)
        english["source_text"] = "The"
        self.assertEqual(classify_row(english)[0], "translate")

        mapped = dict(row)
        mapped["source_text"] = "Shower"
        self.assertEqual(classify_row(mapped)[0], "translate")

    def test_color_wrapped_ui_label_remains_translation_candidate(self):
        row = {
            "source_text": "<color=yellow>PASS</color>",
            "translation": "",
            "context": "NaninovelScript:1:choice",
            "import_method": "naninovel_choice",
        }
        action, fixed = classify_row(row)
        self.assertEqual(action, "translate")
        self.assertEqual(fixed, "player-visible text")

    def test_hesitation_keep(self):
        row = {
            "source_text": "(Eh.. Player...?)",
            "translation": "",
            "context": "NaninovelScript:9",
        }
        self.assertEqual(classify_row(row)[0], "copy_literal")

    def test_star_sfx_keep(self):
        row = {
            "source_text": "*GLRRRK*!!!",
            "translation": "",
            "context": "TextAsset:foo:line:1",
        }
        self.assertEqual(classify_row(row)[0], "copy_literal")

    def test_allcaps_ui_translates(self):
        row = {
            "source_text": "EXTERNAL SCRIPTS",
            "translation": "",
            "context": "TextAsset:DefaultUI:line:16",
        }
        action = classify_row(row)[0]
        self.assertIn(action, {"translate", "ui_label_fixed"})
        self.assertNotEqual(action, "copy_literal")
        self.assertNotEqual(action, "skip_technical")

    def test_dialogue_with_placeholders_translates(self):
        row = {
            "source_text": "Move {ITEM} to the {TARGET} before continuing.",
            "translation": "",
            "context": "TextAsset:example:line",
        }
        self.assertEqual(classify_row(row)[0], "translate")

    def test_short_lexical_utterances_are_not_misclassified_as_sfx(self):
        for source in (
            "Ugh.. it hurts!",
            "Please... be gentle.",
            "Oh, sorry...!",
            "STOP IT!!!!!!!",
        ):
            self.assertEqual(
                classify_row({"source_text": source, "context": "NaninovelScript:fixture"})[0],
                "translate",
                source,
            )

    def test_repeated_bla_with_punctuation_is_technical(self):
        for source in ("bla bla bla...", "BLA BLA BLA...."):
            self.assertEqual(classify_row({"source_text": source})[0], "skip_technical")

    def test_repeated_player_prose_is_not_literal_keep(self):
        # Repetition in a dialogue line is content, not a reason to leave the
        # whole row in English.  Only the bounded BLA debug token above is
        # technical; these rows must reach the normal CT2 route.
        for source in (
            "This is not embarrassing. This is not embarrassing. This is not embarrassing...",
            "*HA HA HA* The train is late. The train is late.",
        ):
            self.assertEqual(
                classify_row({"source_text": source, "context": "NaninovelScript:fixture"})[0],
                "translate",
                source,
            )

    def test_script_allcaps_dialogue_is_translated(self):
        for source in ("OPEN MENU", "PAUSE GAME", "CHECK STATUS"):
            self.assertEqual(
                classify_row({"source_text": source, "context": "NaninovelScript:fixture"})[0],
                "translate",
                source,
            )

    def test_vietnamese_ui_copied(self):
        row = {
            "source_text": "Nội dung",
            "translation": "",
            "context": "UI:Text",
        }
        self.assertEqual(classify_row(row)[0], "copy_source")

    def test_no_latin_dialogue_copy_literal(self):
        row = {
            "source_text": "♡♡♡",
            "translation": "",
            "context": "TextAsset:line",
        }
        self.assertEqual(classify_row(row)[0], "copy_literal")

    def test_malformed_repeated_star_sfx_keep(self):
        source = "*GYUK* GYUK* *GYUK*"
        self.assertTrue(is_star_sfx_line(source))
        self.assertEqual(classify_row({"source_text": source})[0], "copy_literal")

    def test_laughter_asset_and_scene_tokens_are_not_sent_to_mt(self):
        for source in (
            "A ha ha...",
            "DEMO Series 1",
            "demo series 1",
            "<color=yellow>SampleRoute_{mName}</color>",
            "<color=yellow>QuestScene{tUniform}</color>",
            "yyyy-MM-dd HH:mm:ss",
            "!StringContain(sampleType,tempValue)",
            "StringContains(tempName,\"SceneAlpha,SceneBeta\")",
            "Character.{itemType}_Happy",
            "EV.room_2_1_{mName}",
            ".Work_{temp}",
            "StringContain(contactList,\"sample customer\")",
            "randE%3!=1",
        ):
            row = {
                "source_text": source,
                "translation": "",
                "context": "NaninovelScript:fixture",
            }
            self.assertIn(classify_row(row)[0], {"copy_literal", "skip_technical"}, source)

    def test_generic_unity_data_path_is_technical_without_title_literal(self):
        for source in ("SampleVN_Data/StreamingAssets/dialogue.txt", "OtherVN_Data/data.unity3d"):
            self.assertEqual(classify_row({"source_text": source})[0], "skip_technical", source)

    def test_short_moan_with_heart_is_kept_literal(self):
        for source in ("Ahanng....♡", "Ahngh...♡"):
            action, _reason = classify_row({"source_text": source})
            self.assertEqual(action, "copy_literal", source)

    def test_naninovel_runtime_token_pool_is_skipped_without_filtering_prose(self):
        for source in (
            "NpcAlpha,NpcBeta,QuestFlag,QuestFlag2,SceneLabel,SceneLabel2",
            "actionA,actionB,actionB,actionB",
            "RouteAlpha,AreaWest,AreaWest2,PlaceModel,PlacePublic",
            "begin,end,check,collect,remove,*ok,update,save,load,open,close",
        ):
            action, reason = classify_row({
                "source_text": source,
                "context": "NaninovelScript:fixture",
            })
            self.assertEqual(action, "skip_technical", source)
            self.assertIn("token pool", reason)

        self.assertEqual(
            classify_row({
                "source_text": "Hello, how are you?",
                "context": "NaninovelScript:fixture",
            })[0],
            "translate",
        )

    def test_prefixed_repeated_onomatopoeia_is_kept_literal(self):
        source = "Speaker: GUK GUK GUK GUK..."
        self.assertTrue(is_sound_effect_line(source))
        self.assertEqual(classify_row({"source_text": source})[0], "copy_literal")

    def test_sfx_prefix_with_dialogue_tail_is_translated(self):
        source = "*GLRK* *GLRK* *GLRK*[br](It's hard to breathe..!)"
        self.assertEqual(classify_row({"source_text": source})[0], "translate")

    def test_editor_notes_and_gibberish_are_technical(self):
        for source in (
            "bla bla bla",
            "anal (Use same scene as vaginal)",
            "Never edit the above lines -- this is an auto-save point",
        ):
            self.assertEqual(classify_row({"source_text": source})[0], "skip_technical")


if __name__ == "__main__":
    unittest.main()
