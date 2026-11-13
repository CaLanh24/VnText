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


class Epoch019RebaselineGrantTests(unittest.TestCase):
    """owner-20261113-cba2a80-019: ONE single-use grant for release-0.1.19 0.1.19 -> 0.1.19, bound to descendants of the prepared source."""

    def test_grant_is_registered_for_this_task_only_and_quotes_the_owner(self):
        grant = cleanup.RELEASE_TASK_0119_REBASELINE_ID
        task, version, approval = cleanup.EPOCH_REBASELINE_AUTHORIZATIONS[grant]
        self.assertEqual(('release-0.1.19', '0.1.19'), (task, version))
        self.assertIn(cleanup.RELEASE_TASK_0119_REBASELINE_PREPARED_SHA, approval)
        self.assertIn('cho phep', approval); self.assertIn('5 GiB', approval); self.assertIn('11 GiB', approval); self.assertIn('48 MiB', approval)
        self.assertIn('eight-hop', approval); self.assertIn('No user-data deletion', approval)
        self.assertEqual([grant], [k for k, v in cleanup.EPOCH_REBASELINE_AUTHORIZATIONS.items() if v[0] == 'release-0.1.19'])
        self.assertTrue(cleanup._rebaseline_prior_task_allowed(task, task, grant))
        self.assertFalse(cleanup._rebaseline_prior_task_allowed('release-0.1.18', task, grant))
        self.assertEqual(5 * 1024 ** 3, cleanup._release_task_budget_limit(task))                # the budget is NOT changed by the grant

    def test_grant_requires_same_version_and_the_prepared_lineage(self):
        grant = cleanup.RELEASE_TASK_0119_REBASELINE_ID
        versions = {'old': '0.1.19', 'new': '0.1.19', 'older': '0.1.18', 'other': '0.1.20'}
        with patch.object(cleanup, '_git_version_at', side_effect=lambda sha: versions[sha]), patch.object(cleanup, '_git_is_ancestor', return_value=True) as ancestor:
            self.assertTrue(cleanup._rebaseline_versions_match('old', 'new', '0.1.19', grant))
            self.assertEqual((cleanup.RELEASE_TASK_0119_REBASELINE_PREPARED_SHA, 'new'), ancestor.call_args.args)
            self.assertFalse(cleanup._rebaseline_versions_match('older', 'new', '0.1.19', grant))
            self.assertFalse(cleanup._rebaseline_versions_match('old', 'other', '0.1.19', grant))
            self.assertFalse(cleanup._rebaseline_versions_match('old', 'new', '0.1.18', grant))
            self.assertNotIn('unapproved', cleanup.EPOCH_REBASELINE_AUTHORIZATIONS)             # an unknown id is rejected by the registry lookup, not by version matching
        with patch.object(cleanup, '_git_version_at', side_effect=lambda sha: versions[sha]), patch.object(cleanup, '_git_is_ancestor', return_value=False):
            self.assertFalse(cleanup._rebaseline_versions_match('old', 'new', '0.1.19', grant))

    def test_earlier_grants_and_the_eight_hop_policy_are_untouched(self):
        self.assertNotIn('release-0.1.19', cleanup.STANDING_TRANSITION_POLICY_TASKS)
        self.assertEqual(('release-0.1.17',), cleanup.STANDING_TRANSITION_POLICY_TASKS)
        self.assertIn(cleanup.RELEASE_TASK_0117_REBASELINE_ID_2, cleanup.EPOCH_REBASELINE_AUTHORIZATIONS)
        self.assertNotEqual(cleanup.RELEASE_TASK_0119_REBASELINE_ID, cleanup.RELEASE_TASK_0117_REBASELINE_ID_2)


if __name__ == '__main__':
    unittest.main()
