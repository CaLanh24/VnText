from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "opus_semantic_packet",
    ROOT / "tests" / "tools" / "opus_semantic_packet.py",
)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)

sys.path.insert(0, str(ROOT / "tests" / "lib"))
from work_paths import work_temp_dir  # noqa: E402


class OpusSemanticPacketTests(unittest.TestCase):
    def test_review_schema_is_candidate_agnostic_and_packet_has_blank_slots(self):
        row = {
            "anonymized_id": "ROW-001",
            "source": "Hello.",
            "candidate_translation": "Xin chào.",
            "reviewer_context": "NO_CONTEXT_AVAILABLE",
        }
        packet = MODULE._build_packet([row])
        schema = MODULE.review_schema()

        self.assertTrue(schema["candidate_agnostic"])
        self.assertNotIn("OPUS", json_text(schema))
        self.assertEqual(packet["semantic_status"], "NOT_REVIEWED")
        self.assertEqual(packet["rows"][0]["reviewer_a"]["overall"], "")
        self.assertEqual(packet["rows"][0]["reviewer_b"]["reason"], "")
        self.assertNotIn("category", packet["rows"][0])
        self.assertNotIn("key", packet["rows"][0])

    def test_mapping_is_deterministic_and_private(self):
        rows = [
            {"anonymized_id": "ROW-001", "ordinal": 1, "key": "private:key", "category": "normal"},
            {"anonymized_id": "ROW-002", "ordinal": 2, "key": "private:key-2", "category": "difficult"},
        ]
        first = MODULE._build_mapping(rows, "a" * 40)
        second = MODULE._build_mapping(rows, "a" * 40)
        self.assertEqual(first, second)
        self.assertEqual([row["anonymized_id"] for row in first["rows"]], ["ROW-001", "ROW-002"])

    def test_completion_gate_accepts_only_complete_aligned_baseline(self):
        expected, translated, report = valid_gate_rows()
        failures = MODULE._completion_gate(
            status={"complete": True, "pending": 0, "review_only": 0, "blocked": 0},
            expected_rows=expected,
            translated_rows=translated,
            review_rows=[],
            technical_rows=[],
            report_rows=report,
        )
        self.assertEqual(failures, [])

    def test_completion_gate_rejects_incomplete_status(self):
        expected, translated, report = valid_gate_rows()
        cases = [
            {"complete": False, "pending": 0, "review_only": 0, "blocked": 0},
            {"complete": True, "pending": 1, "review_only": 0, "blocked": 0},
            {"complete": True, "pending": 0, "review_only": 1, "blocked": 0},
            {"complete": True, "pending": 0, "review_only": 0, "blocked": 1},
        ]
        for status in cases:
            with self.subTest(status=status):
                failures = MODULE._completion_gate(
                    status=status,
                    expected_rows=expected,
                    translated_rows=translated,
                    review_rows=[],
                    technical_rows=[],
                    report_rows=report,
                )
                self.assertTrue(any(item["check"].startswith("translate_status") for item in failures))

    def test_completion_gate_rejects_csv_alignment_and_blank_translation(self):
        expected, translated, report = valid_gate_rows()
        cases = {
            "missing": translated[:-1],
            "blank": [*translated[:4], {**translated[4], "translation": "   "}, *translated[5:]],
            "duplicate": [*translated[:-1], translated[-2]],
            "extra": [*translated, {"key": "extra", "translation": "Dư"}],
            "key_mismatch": [{**translated[0], "key": "wrong"}, *translated[1:]],
            "order_drift": [translated[1], translated[0], *translated[2:]],
        }
        for name, actual in cases.items():
            with self.subTest(case=name):
                failures = MODULE._completion_gate(
                    status={"complete": True, "pending": 0, "review_only": 0, "blocked": 0},
                    expected_rows=expected,
                    translated_rows=actual,
                    review_rows=[],
                    technical_rows=[],
                    report_rows=report,
                )
                self.assertTrue(any(item["check"].startswith("translation.csv") for item in failures))

    def test_completion_gate_rejects_review_skipped_and_structural_rows(self):
        expected, translated, report = valid_gate_rows()
        for label, review_rows, technical_rows, report_rows in (
            ("review", [{"key": "private-review"}], [], report),
            ("technical", [], [{"key": "private-technical"}], report),
            ("structural_fail", [], [], [{**report[0], "structural_verdict": "FAIL"}, *report[1:]]),
            ("structural_missing", [], [], [{key: value for key, value in report[0].items() if key != "structural_verdict"}, *report[1:]]),
        ):
            with self.subTest(case=label):
                failures = MODULE._completion_gate(
                    status={"complete": True, "pending": 0, "review_only": 0, "blocked": 0},
                    expected_rows=expected,
                    translated_rows=translated,
                    review_rows=review_rows,
                    technical_rows=technical_rows,
                    report_rows=report_rows,
                )
                self.assertTrue(failures)

    def test_completion_gate_rejects_report_alignment(self):
        expected, translated, report = valid_gate_rows()
        for altered in (
            [{**report[0], "candidate_translation": "Khác"}, *report[1:]],
            report[:-1],
            [{**report[0], "key": "wrong"}, *report[1:]],
        ):
            with self.subTest(report_rows=altered):
                failures = MODULE._completion_gate(
                    status={"complete": True, "pending": 0, "review_only": 0, "blocked": 0},
                    expected_rows=expected,
                    translated_rows=translated,
                    review_rows=[],
                    technical_rows=[],
                    report_rows=altered,
                )
                self.assertTrue(any(item["check"].startswith("baseline_report") for item in failures))

    def test_failed_gate_does_not_publish_packet_or_mapping(self):
        output = work_temp_dir("opus-semantic-packet-gate") / "failed-run"
        output.mkdir(parents=True)
        published = MODULE._publish_review_artifacts(
            output,
            [],
            "a" * 40,
            completion_gate_passed=False,
        )
        self.assertEqual(published, {})
        self.assertFalse((output / "blind_review_packet.json").exists())
        self.assertFalse((output / "private_id_mapping.json").exists())

    def test_reused_output_dir_gets_unique_run_dir(self):
        root = work_temp_dir("opus-semantic-packet-stale")
        requested = root / "opus-baseline"
        requested.mkdir(parents=True)
        old_packet = requested / "blind_review_packet.json"
        old_mapping = requested / "private_id_mapping.json"
        old_packet.write_text("old-packet", encoding="utf-8")
        old_mapping.write_text("old-mapping", encoding="utf-8")

        selected = MODULE._select_output_dir(requested, "new-run")

        self.assertNotEqual(selected, requested)
        self.assertFalse((selected / "blind_review_packet.json").exists())
        self.assertEqual(old_packet.read_text(encoding="utf-8"), "old-packet")
        self.assertEqual(old_mapping.read_text(encoding="utf-8"), "old-mapping")


def json_text(value) -> str:
    import json

    return json.dumps(value, ensure_ascii=False)


def valid_gate_rows():
    expected = [{"key": f"key-{index}", "source_text": f"Source {index}"} for index in range(30)]
    translated = [{"key": row["key"], "translation": f"Dịch {index}"} for index, row in enumerate(expected)]
    report = [
        {
            "key": row["key"],
            "candidate_translation": translated[index]["translation"],
            "structural_verdict": "PASS",
        }
        for index, row in enumerate(expected)
    ]
    return expected, translated, report


if __name__ == "__main__":
    unittest.main()
