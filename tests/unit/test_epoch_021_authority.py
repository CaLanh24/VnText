"""The authorized next release has its own scope/budget, not a reused old grant."""
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tests/tools'))
import cleanup_work_artifacts as cleanup


class Epoch021AuthorityTests(unittest.TestCase):
    def test_single_rebaseline_is_owner_bound_and_keeps_version_lineage_guards(self):
        authority = cleanup.EPOCH_REBASELINE_AUTHORIZATIONS[cleanup.RELEASE_TASK_0121_REBASELINE_ID]
        self.assertEqual(authority[:2], ("release-0.1.21", "0.1.21"))
        self.assertIn("Cho phép rebaseline batch 0.1.21", authority[2])
        self.assertNotIn("release-0.1.21", cleanup.STANDING_TRANSITION_POLICY_TASKS)
        with patch.object(cleanup, "_git_version_at", return_value="0.1.21"), patch.object(cleanup, "_git_is_ancestor", return_value=True):
            self.assertTrue(cleanup._rebaseline_versions_match("old", "new", "0.1.21", cleanup.RELEASE_TASK_0121_REBASELINE_ID))
        with patch.object(cleanup, "_git_version_at", return_value="0.1.21"), patch.object(cleanup, "_git_is_ancestor", return_value=False):
            self.assertFalse(cleanup._rebaseline_versions_match("old", "new", "0.1.21", cleanup.RELEASE_TASK_0121_REBASELINE_ID))
        with patch.object(cleanup, "_git_version_at", return_value="0.1.20"), patch.object(cleanup, "_git_is_ancestor", return_value=True):
            self.assertFalse(cleanup._rebaseline_versions_match("old", "new", "0.1.21", cleanup.RELEASE_TASK_0121_REBASELINE_ID))
    def test_exact_scope_and_budget(self):
        task, version, approval = cleanup._release_budget_spec('release-0.1.21')
        self.assertEqual(('release-0.1.21', '0.1.21'), (task, version))
        self.assertEqual(6 * 1024**3, cleanup._release_task_budget_limit(task))
        self.assertEqual((ROOT/'RELEASE_RUN/candidate-0.1.21').resolve(), cleanup._task_scope_path(ROOT, task, version))
        self.assertIn('Owner 2026-11-18', approval)
        self.assertIn('2026-10-24', approval)
        self.assertNotEqual(approval, cleanup._release_budget_spec('release-0.1.20')[2])
        self.assertFalse(cleanup._release_budget_record_is_valid({'limit_bytes': 5*1024**3, 'owner_approval': cleanup._release_budget_spec('release-0.1.20')[2]}, task, approval))

    def test_forward_handoff_only_and_no_new_hop_policy(self):
        self.assertTrue(cleanup._epoch_transition_tasks_compatible('release-0.1.20', 'release-0.1.21'))
        self.assertFalse(cleanup._epoch_transition_tasks_compatible('release-0.1.21', 'release-0.1.20'))
        self.assertFalse(cleanup._epoch_transition_tasks_compatible('release-0.1.18', 'release-0.1.21'))
        self.assertNotIn('release-0.1.21', cleanup.STANDING_TRANSITION_POLICY_TASKS)
        with patch.object(cleanup, '_git_version_at', side_effect=lambda sha: {'old':'0.1.20','new':'0.1.21','wrong':'0.1.20'}[sha]):
            self.assertTrue(cleanup._epoch_transition_versions_valid('release-0.1.20','release-0.1.21','old','new'))
            self.assertFalse(cleanup._epoch_transition_versions_valid('release-0.1.20','release-0.1.21','old','wrong'))


if __name__ == '__main__':
    unittest.main()
