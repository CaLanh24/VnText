"""Focused tests for the frozen synthetic EN-to-VI evaluator."""

from __future__ import annotations

import copy
import contextlib
import io
import json
import unittest

from tests.tools import translation_quality_phase1 as evaluator


class TranslationQualityPhase1DatasetTests(unittest.TestCase):
    def setUp(self) -> None:
        self.dataset, self.dataset_raw, self.dataset_summary = evaluator.load_dataset()

    def test_frozen_dataset_has_fixed_split_counts_and_no_normalized_leakage(self) -> None:
        self.assertEqual(len(self.dataset_raw), len(evaluator.DATASET_PATH.read_bytes()))
        self.assertEqual(self.dataset_summary["row_count"], 100)
        self.assertEqual(self.dataset_summary["split_counts"], {"development": 80, "held_out": 20})
        self.assertEqual(self.dataset_summary["unique_normalized_source_count"], 100)
        self.assertEqual(
            self.dataset_summary["group_split_counts"],
            evaluator.EXPECTED_GROUP_COUNTS,
        )

    def test_validate_dataset_cli_emits_json_report(self) -> None:
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            exit_code = evaluator._command_validate(None)
        self.assertEqual(exit_code, 0)
        cli_report = json.loads(output.getvalue())
        self.assertEqual(cli_report["status"], "PASS")
        self.assertEqual(cli_report["row_count"], 100)
        self.assertEqual(cli_report["split_counts"], {"development": 80, "held_out": 20})

    def test_duplicate_ids_and_normalized_sources_fail_closed(self) -> None:
        duplicate_id = copy.deepcopy(self.dataset)
        duplicate_id["rows"][1]["id"] = duplicate_id["rows"][0]["id"]
        with self.assertRaisesRegex(evaluator.DatasetValidationError, "duplicate row ID"):
            evaluator.validate_dataset(duplicate_id)

        duplicate_source = copy.deepcopy(self.dataset)
        duplicate_source["rows"][1]["source_en"] = duplicate_source["rows"][0]["source_en"].swapcase()
        with self.assertRaisesRegex(evaluator.DatasetValidationError, "duplicate normalized source"):
            evaluator.validate_dataset(duplicate_source)

    def test_scenario_group_cannot_cross_development_and_held_out(self) -> None:
        leaked = copy.deepcopy(self.dataset)
        dev_row = next(row for row in leaked["rows"] if row["split"] == "development")
        held_out_row = next(
            row for row in leaked["rows"]
            if row["split"] == "held_out" and row["group"] == dev_row["group"]
        )
        held_out_row["scenario_boundary"]["group_id"] = dev_row["scenario_boundary"]["group_id"]
        with self.assertRaisesRegex(evaluator.DatasetValidationError, "crosses split or boundary"):
            evaluator.validate_dataset(leaked)

    def test_review_status_and_reference_fields_fail_closed(self) -> None:
        reviewed = copy.deepcopy(self.dataset)
        reviewed["provenance"]["semantic_review_status"] = "reviewed"
        with self.assertRaisesRegex(evaluator.DatasetValidationError, "draft/unreviewed"):
            evaluator.validate_dataset(reviewed)

        gold = copy.deepcopy(self.dataset)
        gold["rows"][0]["reference_vi"] = "đáp án giả"
        with self.assertRaisesRegex(evaluator.DatasetValidationError, "reference/gold"):
            evaluator.validate_dataset(gold)


class TranslationQualityPhase1ReportTests(unittest.TestCase):
    def setUp(self) -> None:
        self.dataset, _, _ = evaluator.load_dataset()

    def test_source_fallback_and_raw_model_output_remain_visible(self) -> None:
        source = next(row for row in self.dataset["rows"] if row["id"] == "TOK-001")
        raw_output = "Cánh cửa phía đông vẫn khóa."
        call = {"input": "sentinelized input", "raw_output": raw_output, "disposition": "RETURNED", "error": None}
        result = evaluator.completed_row_result(source, source["source_en"], [call], 0.25)
        self.assertEqual(result["route_output"], source["source_en"])
        self.assertEqual(result["disposition"], "ROUTE_RETURNED")
        self.assertTrue(result["output_matches_source"])
        self.assertEqual(result["model_calls"][0]["raw_output"], raw_output)
        self.assertEqual(result["structural_verdict"], "PASS")
        self.assertEqual(result["semantic_review_verdict"], "UNKNOWN")
        summary = evaluator.summarize_rows([result])
        self.assertEqual(summary["route_returned_rows"], 1)
        self.assertEqual(summary["output_identity_rows"], 1)

    def test_structural_failure_is_kept_separate_from_semantic_unknown(self) -> None:
        source = next(row for row in self.dataset["rows"] if row["id"] == "TOK-001")
        result = evaluator.completed_row_result(source, "Cánh cửa phía đông vẫn khóa.", [], 0.1)
        self.assertEqual(result["structural_verdict"], "FAIL")
        self.assertIn("placeholder mismatch", result["structural_reasons"])
        self.assertEqual(result["semantic_review_verdict"], "UNKNOWN")

    def test_markup_and_literal_newline_errors_remain_visible(self) -> None:
        tag_source = next(row for row in self.dataset["rows"] if row["id"] == "TOK-003")
        tag_result = evaluator.completed_row_result(
            tag_source,
            tag_source["source_en"].replace("</color>", ""),
            [],
            0.1,
        )
        self.assertIn("tag mismatch", tag_result["structural_reasons"])

        newline_source = next(row for row in self.dataset["rows"] if row["id"] == "TOK-006")
        newline_result = evaluator.completed_row_result(
            newline_source,
            newline_source["source_en"].replace("\\n", " "),
            [],
            0.1,
        )
        self.assertTrue(any("literal newline count" in reason for reason in newline_result["structural_reasons"]))
        self.assertEqual(tag_result["semantic_review_verdict"], "UNKNOWN")
        self.assertEqual(newline_result["semantic_review_verdict"], "UNKNOWN")

    def test_report_serialization_is_deterministic_and_semantics_cannot_pass(self) -> None:
        report = evaluator.make_report(
            self.dataset,
            dataset_sha256="d" * 64,
            protocol_sha256="p" * 64,
            tool_sha256="t" * 64,
            git_head="0" * 40,
            started_at_utc="2026-10-19T00:00:00.000Z",
        )
        for row in report["rows"]:
            row["disposition"] = "NOT_RUN_TEST"
            row["error"] = "test fixture: no baseline execution"
        report["summary"] = evaluator.summarize_rows(report["rows"])
        self.assertEqual(evaluator.validate_report(report, self.dataset)["total_rows"], 100)
        self.assertEqual(evaluator.serialize_report(report), evaluator.serialize_report(copy.deepcopy(report)))

        invalid = copy.deepcopy(report)
        invalid["semantic_quality_verdict"] = "PASS"
        with self.assertRaisesRegex(ValueError, "cannot be inferred"):
            evaluator.validate_report(invalid, self.dataset)

        missing_reason = copy.deepcopy(report)
        missing_reason["rows"][0]["error"] = None
        missing_reason["summary"] = evaluator.summarize_rows(missing_reason["rows"])
        with self.assertRaisesRegex(ValueError, "reason-coded final disposition"):
            evaluator.validate_report(missing_reason, self.dataset)

    def test_source_identity_is_counted_separately_and_validated(self) -> None:
        report = evaluator.make_report(
            self.dataset,
            dataset_sha256="d" * 64,
            protocol_sha256="p" * 64,
            tool_sha256="t" * 64,
            git_head="0" * 40,
            started_at_utc="2026-10-19T00:00:00.000Z",
        )
        for row in report["rows"]:
            row["disposition"] = "NOT_RUN_TEST"
            row["error"] = "test fixture: no baseline execution"
        source = self.dataset["rows"][0]
        report["rows"][0] = evaluator.completed_row_result(source, source["source_en"], [], 0.0)
        report["summary"] = evaluator.summarize_rows(report["rows"])
        self.assertEqual(report["summary"]["route_returned_rows"], 1)
        self.assertEqual(report["summary"]["output_identity_rows"], 1)
        self.assertEqual(evaluator.validate_report(report, self.dataset)["output_identity_rows"], 1)

        report["rows"][0]["output_matches_source"] = False
        report["summary"] = evaluator.summarize_rows(report["rows"])
        with self.assertRaisesRegex(ValueError, "source identity flag"):
            evaluator.validate_report(report, self.dataset)


if __name__ == "__main__":
    unittest.main()
