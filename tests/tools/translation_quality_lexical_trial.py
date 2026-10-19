"""One test-only lexical-protection ablation; never changes the product route."""
from __future__ import annotations

import json
from pathlib import Path
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tests.tools import translation_quality_phase1 as evaluator
from vntext import mt_translation_safety as safety

REPORT_PATH = evaluator.EVIDENCE_ROOT / "lexical-trial-a.v1.json"


def run_trial() -> dict:
    original_split = safety.split_parts
    original_protocol = evaluator.baseline_protocol
    original_make_report = evaluator.make_report
    trial_sha = evaluator.sha256_file(Path(__file__))

    def split_without_lexical(text, *, protect_lexical=True):
        return original_split(text, protect_lexical=False)

    def trial_protocol(dataset):
        return {
            **original_protocol(dataset),
            "test_only_intervention": "split_parts lexical=False; opaque/name policy unchanged",
            "trial_script_sha256": trial_sha,
            "product_promotion": "NOT_AUTHORIZED_BY_TRIAL",
        }

    def trial_report(*args, **kwargs):
        report = original_make_report(*args, **kwargs)
        report["experiment"] = {
            "id": "lexical-trial-a-v1",
            "script_sha256": trial_sha,
            "intervention": "lexical=False",
            "product_route_changed": False,
            "baseline_report": "opus-baseline.v1.json",
        }
        return report

    with patch.object(safety, "split_parts", split_without_lexical), patch.object(
        evaluator, "baseline_protocol", trial_protocol
    ), patch.object(evaluator, "make_report", trial_report), patch.object(
        evaluator, "DEFAULT_REPORT_PATH", REPORT_PATH
    ):
        return evaluator.run_baseline(REPORT_PATH)


if __name__ == "__main__":
    result = run_trial()
    print(json.dumps({"run_status": result["run_status"], "summary": result["summary"]}))
    raise SystemExit(0 if result["run_status"] == "COMPLETED" else 2)
