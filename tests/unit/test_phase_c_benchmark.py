from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "phase_c_ct2_sample",
    ROOT / "tests" / "tools" / "phase_c_ct2_sample.py",
)
assert SPEC and SPEC.loader
PHASE_C = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PHASE_C)


class PhaseCBenchmarkTests(unittest.TestCase):
    def test_transport_ok_does_not_override_quality_gated_incomplete(self):
        self.assertFalse(
            PHASE_C._worker_success(
                {"ok": True, "complete": False, "pending": 2, "review_only": 2, "blocked": 2}
            )
        )

    def test_success_requires_zero_pending_review_and_blocked(self):
        self.assertTrue(
            PHASE_C._worker_success(
                {"ok": True, "complete": True, "pending": 0, "review_only": 0, "blocked": 0}
            )
        )


if __name__ == "__main__":
    unittest.main()
