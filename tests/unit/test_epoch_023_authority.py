"""Release 0.1.23 has its own scope/budget and an ordinary forward hand-off from 0.1.22 only."""
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tests/tools'))
import cleanup_work_artifacts as cleanup


class Epoch023AuthorityTests(unittest.TestCase):
    def test_exact_scope_budget_and_guards(self):
        task, version, approval = cleanup._release_budget_spec('release-0.1.23')
        self.assertEqual(('release-0.1.23', '0.1.23'), (task, version))
        self.assertEqual(5500 * 1024**2, cleanup._release_task_budget_limit(task))
        self.assertEqual((ROOT / 'RELEASE_RUN/candidate-0.1.23').resolve(), cleanup._task_scope_path(ROOT, task, version))
        self.assertIn('Owner 2026-11-19', approval)
        self.assertIn('48 MiB reserve', approval)
        self.assertIn('11 GiB shared cap', approval)
        self.assertNotEqual(approval, cleanup._release_budget_spec('release-0.1.22')[2])
        self.assertFalse(cleanup._release_budget_record_is_valid({'limit_bytes': 5500 * 1024**2, 'owner_approval': cleanup._release_budget_spec('release-0.1.22')[2]}, task, approval))

    def test_forward_handoff_from_022_only(self):
        self.assertTrue(cleanup._epoch_transition_tasks_compatible('release-0.1.22', 'release-0.1.23'))
        self.assertTrue(cleanup._epoch_transition_tasks_compatible('release-0.1.23', 'release-0.1.23'))
        self.assertFalse(cleanup._epoch_transition_tasks_compatible('release-0.1.23', 'release-0.1.22'))
        self.assertFalse(cleanup._epoch_transition_tasks_compatible('release-0.1.21', 'release-0.1.23'))
        self.assertNotIn('release-0.1.23', cleanup.STANDING_TRANSITION_POLICY_TASKS)
        with patch.object(cleanup, '_git_version_at', side_effect=lambda sha: {'old': '0.1.22', 'new': '0.1.23', 'wrong': '0.1.22'}[sha]):
            self.assertTrue(cleanup._epoch_transition_versions_valid('release-0.1.22', 'release-0.1.23', 'old', 'new'))
            self.assertFalse(cleanup._epoch_transition_versions_valid('release-0.1.22', 'release-0.1.23', 'old', 'wrong'))


if __name__ == '__main__':
    unittest.main()
