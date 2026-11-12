"""Release 0.1.19 is its own task: the standing allocation applies, no 0.1.17/0.1.18 grant or hop policy is inherited."""
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tests/tools'))
import cleanup_work_artifacts as cleanup


class Epoch019AuthorityTests(unittest.TestCase):
    def test_task_is_supported_with_its_own_limit_and_approval(self):
        task, version, approval = cleanup._release_budget_spec('release-0.1.19')
        self.assertEqual(('release-0.1.19', '0.1.19'), (task, version))
        self.assertEqual(5 * 1024 ** 3, cleanup._release_task_budget_limit(task))
        self.assertTrue(cleanup._release_budget_record_is_valid({"limit_bytes": 5 * 1024 ** 3, "owner_approval": approval}, task, approval))
        self.assertFalse(cleanup._release_budget_record_is_valid({"limit_bytes": 4 * 1024 ** 3, "owner_approval": approval}, task, approval))
        self.assertIn('Owner 2026-11-12', approval); self.assertIn('2026-10-24', approval); self.assertIn('inherits no 0.1.17/0.1.18', approval)
        self.assertNotEqual(approval, cleanup._release_budget_spec('release-0.1.18')[2])
        self.assertEqual(cleanup._task_scope_path(ROOT, task, version), (ROOT / 'RELEASE_RUN' / 'candidate-0.1.19').resolve())

    def test_historical_budgets_and_standing_hop_policy_are_untouched(self):
        self.assertEqual(int(4.5 * 1024 ** 3), cleanup._release_task_budget_limit('release-0.1.18'))
        self.assertEqual(6710886400, cleanup._release_task_budget_limit('release-0.1.17'))
        self.assertEqual(('release-0.1.18', '0.1.18', cleanup.RELEASE_TASK_0118_BUDGET_APPROVAL), cleanup._release_budget_spec('release-0.1.18'))
        self.assertNotIn('release-0.1.19', cleanup.STANDING_TRANSITION_POLICY_TASKS)
        self.assertEqual(('release-0.1.17',), cleanup.STANDING_TRANSITION_POLICY_TASKS)

    def test_only_the_forward_018_to_019_handoff_is_compatible(self):
        old, new = 'release-0.1.18', 'release-0.1.19'
        self.assertTrue(cleanup._epoch_transition_tasks_compatible(new, new))
        self.assertTrue(cleanup._epoch_transition_tasks_compatible(old, new))
        self.assertFalse(cleanup._epoch_transition_tasks_compatible(new, old))
        self.assertFalse(cleanup._epoch_transition_tasks_compatible('release-0.1.17', new))
        self.assertFalse(cleanup._epoch_transition_tasks_compatible('release-0.1.9', new))

    def test_handoff_binds_each_endpoint_to_its_version(self):
        with patch.object(cleanup, '_git_version_at', side_effect=lambda sha: {'old': '0.1.18', 'new': '0.1.19', 'same': '0.1.18'}[sha]):
            self.assertTrue(cleanup._epoch_transition_versions_valid('release-0.1.18', 'release-0.1.19', 'old', 'new'))
            self.assertFalse(cleanup._epoch_transition_versions_valid('release-0.1.18', 'release-0.1.19', 'old', 'same'))
            self.assertFalse(cleanup._epoch_transition_versions_valid('release-0.1.19', 'release-0.1.18', 'new', 'old'))


if __name__ == '__main__':
    unittest.main()
