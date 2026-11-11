"""Release 0.1.18 is its own task: the standing allocation applies, no 0.1.17 grant or hop policy is inherited."""
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tests/tools'))
import cleanup_work_artifacts as cleanup


class Epoch018AuthorityTests(unittest.TestCase):
    def test_task_is_supported_with_its_own_limit_and_approval(self):
        task, version, approval = cleanup._release_budget_spec('release-0.1.18')
        self.assertEqual(('release-0.1.18', '0.1.18'), (task, version))
        self.assertEqual(3 * 1024 ** 3, cleanup._release_task_budget_limit(task))
        self.assertIn('Owner 2026-11-12', approval); self.assertIn('2026-10-24', approval); self.assertIn('inherits no 0.1.17', approval)
        self.assertNotEqual(approval, cleanup._release_budget_spec('release-0.1.17')[2])
        self.assertEqual(cleanup._task_scope_path(ROOT, task, version), (ROOT / 'RELEASE_RUN' / 'candidate-0.1.18').resolve())

    def test_historical_budgets_and_standing_hop_policy_are_untouched(self):
        self.assertEqual(6710886400, cleanup._release_task_budget_limit('release-0.1.17'))
        self.assertEqual(('release-0.1.17', '0.1.17', cleanup.RELEASE_TASK_0117_BUDGET_APPROVAL), cleanup._release_budget_spec('release-0.1.17'))
        self.assertNotIn('release-0.1.18', cleanup.STANDING_TRANSITION_POLICY_TASKS)            # 0.1.18 never rides the 0.1.17 standing-hop policy
        self.assertEqual(('release-0.1.17',), cleanup.STANDING_TRANSITION_POLICY_TASKS)

    def test_only_the_forward_017_to_018_handoff_is_compatible(self):
        old, new = 'release-0.1.17', 'release-0.1.18'
        self.assertTrue(cleanup._epoch_transition_tasks_compatible(new, new))
        self.assertTrue(cleanup._epoch_transition_tasks_compatible(old, new))
        self.assertFalse(cleanup._epoch_transition_tasks_compatible(new, old))
        self.assertFalse(cleanup._epoch_transition_tasks_compatible('release-0.1.16', new))
        self.assertFalse(cleanup._epoch_transition_tasks_compatible('release-0.1.8', new))

    def test_handoff_binds_each_endpoint_to_its_version(self):
        with patch.object(cleanup, '_git_version_at', side_effect=lambda sha: {'old': '0.1.17', 'new': '0.1.18', 'same': '0.1.17'}[sha]):
            self.assertTrue(cleanup._epoch_transition_versions_valid('release-0.1.17', 'release-0.1.18', 'old', 'new'))
            self.assertFalse(cleanup._epoch_transition_versions_valid('release-0.1.17', 'release-0.1.18', 'old', 'same'))   # target still 0.1.17
            self.assertFalse(cleanup._epoch_transition_versions_valid('release-0.1.18', 'release-0.1.17', 'new', 'old'))


if __name__ == '__main__':
    unittest.main()


class ColdRegistryEpochTests(unittest.TestCase):
    def test_cold_missing_review_does_not_block_an_epoch_step_but_every_other_issue_does(self):
        cold = {"path": "registry", "reason": cleanup.COLD_MISSING_REVIEW_REASON, "count": 28917}
        self.assertEqual([], cleanup._epoch_blocking_metadata_issues({"metadata_issues": [cold]}))
        self.assertEqual([], cleanup._epoch_blocking_metadata_issues({}))
        bad = {"path": "registry", "reason": "registry_entry_missing_id"}
        self.assertEqual([bad], cleanup._epoch_blocking_metadata_issues({"metadata_issues": [cold, bad]}))
        # An invalid cold archive is a registry error, reported under its own reason, and still blocks.
        broken = {"path": "registry", "reason": "cold archive logical hash mismatch"}
        self.assertEqual([broken], cleanup._epoch_blocking_metadata_issues({"metadata_issues": [broken]}))

    def test_the_cleanup_report_still_surfaces_the_cold_review_reason(self):
        text = (ROOT / 'tests/tools/cleanup_work_artifacts.py').read_text(encoding='utf-8')
        self.assertIn('metadata_issues.append({"path": str(MANIFEST_PATH), "reason": COLD_MISSING_REVIEW_REASON', text)
