"""Cold MISSING history and rebuilt-path MISSING claims must not block deleting an explicitly DISPOSABLE target."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tests/tools'))
import cleanup_work_artifacts as cleanup


class ColdMissingDisposeTests(unittest.TestCase):
    def test_cold_missing_review_is_not_a_deletion_blocker_but_other_issues_are(self):
        cold = {"path": "registry", "reason": cleanup.COLD_MISSING_REVIEW_REASON, "count": 5}
        bad = {"path": "registry", "reason": "registry_entry_duplicate_id"}
        self.assertEqual([], cleanup._epoch_blocking_metadata_issues({"metadata_issues": [cold]}))
        self.assertEqual([bad], cleanup._epoch_blocking_metadata_issues({"metadata_issues": [cold, bad]}))

    def test_global_cleanup_uses_the_same_cold_missing_rule_as_scoped_cleanup(self):
        text = (ROOT / 'tests/tools/cleanup_work_artifacts.py').read_text(encoding='utf-8')
        self.assertIn('deletion_blocking_issues = _epoch_blocking_metadata_issues(reconciled) + list(reconciled.get("inventory_errors") or [])', text)
        self.assertIn('and not deletion_blocking_issues', text)
        # every issue, cold MISSING included, is still reported as blocked/REVIEW_REQUIRED
        self.assertIn('"reason": "registry_metadata_invalid"', text)

    def test_missing_claim_on_a_rebuilt_path_blocks_unless_a_disposable_record_registers_that_path(self):
        target = ROOT / "tests" / "unit"           # exists
        missing = {"id": "old", "path": str(target), "lifecycle": "MISSING"}
        self.assertEqual("STALE", cleanup._registered_keep_blocker(target, [missing])["lifecycle"])
        disposable = {"id": "new", "path": str(target), "lifecycle": "DISPOSABLE"}
        self.assertIsNone(cleanup._registered_keep_blocker(target, [missing, disposable]))
        retained = {"id": "keep", "path": str(target), "lifecycle": "RETAINED"}
        self.assertEqual("RETAINED", cleanup._registered_keep_blocker(target, [missing, disposable, retained])["lifecycle"])


if __name__ == '__main__':
    unittest.main()
