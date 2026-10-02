"""Regression tests for trace diagnostics reaching completion consumers."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


def _bootstrap() -> Path:
    tests = Path(__file__).resolve().parents[1]
    if str(tests / "lib") not in sys.path:
        sys.path.insert(0, str(tests / "lib"))
    from bootstrap import bootstrap

    _tests, root, _lib = bootstrap(__file__)
    return root


ROOT = _bootstrap()

from vntext.app_tasks import _diagnostic_completion_fields  # noqa: E402
from vntext_worker import task_runners  # noqa: E402


class DiagnosticCompletionTests(unittest.TestCase):
    def test_trace_summary_becomes_actionable_completion_fields(self):
        with tempfile.TemporaryDirectory(prefix="vntext-diagnostic-") as name:
            package = Path(name)
            meta = package / ".mt"
            meta.mkdir()
            summary = meta / "diagnostic_summary.json"
            summary.write_text(
                json.dumps(
                    {
                        "run_id": "run-1",
                        "classification_counts": {"MAIN": 10},
                        "root_cause_counts": {"TRANSLATION_MISSED": 3},
                        "translation": {"translation_missed": 3},
                        "actionable_next_step": "Review missing candidates and retry.",
                    }
                ),
                encoding="utf-8",
            )

            fields = _diagnostic_completion_fields(package)

            self.assertEqual("TRANSLATE", fields["diagnostic_stage"])
            self.assertEqual("TRANSLATION_MISSED", fields["diagnostic_root_cause"])
            self.assertEqual(3, fields["diagnostic_affected_count"])
            self.assertEqual("Review missing candidates and retry.", fields["diagnostic_action"])
            self.assertEqual(str(summary.resolve()), fields["diagnostic_path"])

    def test_review_summary_is_not_silently_reported_as_clean(self):
        with tempfile.TemporaryDirectory(prefix="vntext-diagnostic-") as name:
            package = Path(name)
            meta = package / ".mt"
            meta.mkdir()
            (meta / "diagnostic_summary.json").write_text(
                json.dumps({"classification_counts": {"REVIEW": 4, "UNSUPPORTED": 2}}),
                encoding="utf-8",
            )

            fields = _diagnostic_completion_fields(package)

            self.assertEqual("CLASSIFY", fields["diagnostic_stage"])
            self.assertEqual("UNKNOWN", fields["diagnostic_root_cause"])
            self.assertEqual(6, fields["diagnostic_affected_count"])

    def test_misclassified_summary_routes_to_classifier_diagnostics(self):
        with tempfile.TemporaryDirectory(prefix="vntext-diagnostic-") as name:
            package = Path(name)
            meta = package / ".mt"
            meta.mkdir()
            summary = meta / "diagnostic_summary.json"
            summary.write_text(
                json.dumps(
                    {
                        "classification_counts": {"MAIN": 1},
                        "root_cause_counts": {"MISCLASSIFIED": 1},
                        "actionable_next_step": "Review the authoritative classifier route against the package split.",
                    }
                ),
                encoding="utf-8",
            )

            fields = _diagnostic_completion_fields(package)

            self.assertEqual("CLASSIFY", fields["diagnostic_stage"])
            self.assertEqual("MISCLASSIFIED", fields["diagnostic_root_cause"])
            self.assertEqual(1, fields["diagnostic_affected_count"])

    def test_clean_summary_does_not_spam_success_completion(self):
        with tempfile.TemporaryDirectory(prefix="vntext-diagnostic-") as name:
            package = Path(name)
            meta = package / ".mt"
            meta.mkdir()
            (meta / "diagnostic_summary.json").write_text(
                json.dumps(
                    {
                        "classification_counts": {"MAIN": 4},
                        "root_cause_counts": {},
                        "run_status_counts": {"COMPLETED": 1},
                    }
                ),
                encoding="utf-8",
            )

            self.assertEqual({}, _diagnostic_completion_fields(package))

    def test_worker_callback_forwards_diagnostic_fields(self):
        with patch.object(task_runners, "emit_complete") as emit:
            _progress, _log, complete = task_runners._make_callbacks("task-1", lambda: False)
            complete(
                {
                    "ok": False,
                    "summary": "failed",
                    "error": "blocked",
                    "complete": False,
                    "pending": 1,
                    "review_only": 0,
                    "blocked": 1,
                    "translated": 2,
                    "diagnostic_stage": "PATCH",
                    "diagnostic_root_cause": "PATCH_VERIFY_FAILED",
                    "diagnostic_affected_count": 1,
                    "diagnostic_action": "Inspect read-back evidence.",
                    "diagnostic_path": "package/.mt/diagnostic_summary.json",
                    "diagnostic_status": "FAILED",
                }
            )

        kwargs = emit.call_args.kwargs
        self.assertEqual("PATCH", kwargs["diagnostic_stage"])
        self.assertEqual("PATCH_VERIFY_FAILED", kwargs["diagnostic_root_cause"])
        self.assertEqual(1, kwargs["diagnostic_affected_count"])
        self.assertEqual("package/.mt/diagnostic_summary.json", kwargs["diagnostic_path"])


if __name__ == "__main__":
    unittest.main()
