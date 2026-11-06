"""The one-use 0.1.17 grant must not permit unrelated tasks or versions."""
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tests/tools'))
import cleanup_work_artifacts as cleanup


class Epoch017AuthorityTests(unittest.TestCase):
    def test_cross_task_permission_requires_the_exact_grant_and_direction(self):
        old, new, grant = cleanup.RELEASE_TASK_0116_BUDGET_ID, cleanup.RELEASE_TASK_0117_BUDGET_ID, cleanup.RELEASE_TASK_0117_REBASELINE_ID
        self.assertTrue(cleanup._rebaseline_prior_task_allowed(old, new, grant))
        self.assertFalse(cleanup._rebaseline_prior_task_allowed(old, new, 'unapproved'))
        self.assertFalse(cleanup._rebaseline_prior_task_allowed(new, old, grant))
        self.assertFalse(cleanup._rebaseline_prior_task_allowed(cleanup.RELEASE_TASK_015_BUDGET_ID, new, grant))

    def test_version_transition_is_bound_to_the_prepared_source_lineage(self):
        grant = cleanup.RELEASE_TASK_0117_REBASELINE_ID
        with patch.object(cleanup, '_git_version_at', side_effect=lambda sha: {'old': '0.1.16', 'new': '0.1.17'}[sha]), patch.object(cleanup, '_git_is_ancestor', return_value=True):
            self.assertTrue(cleanup._rebaseline_versions_match('old', 'new', '0.1.17', grant))
            self.assertFalse(cleanup._rebaseline_versions_match('old', 'new', '0.1.16', grant))
            self.assertFalse(cleanup._rebaseline_versions_match('new', 'old', '0.1.17', grant))
            self.assertFalse(cleanup._rebaseline_versions_match('old', 'new', '0.1.17', 'unapproved'))
        with patch.object(cleanup, '_git_version_at', side_effect=lambda sha: {'old': '0.1.16', 'new': '0.1.17'}[sha]), patch.object(cleanup, '_git_is_ancestor', return_value=False):
            self.assertFalse(cleanup._rebaseline_versions_match('old', 'new', '0.1.17', grant))


class Epoch017SecondGrantTests(unittest.TestCase):
    """owner-20261106-b895c68-017: same task 0.1.17 -> 0.1.17, bound to descendants of the prepared source, never reusable for another task or version."""

    def test_second_grant_is_registered_for_the_same_task_only(self):
        grant = cleanup.RELEASE_TASK_0117_REBASELINE_ID_2
        task, version, approval = cleanup.EPOCH_REBASELINE_AUTHORIZATIONS[grant]
        self.assertEqual((cleanup.RELEASE_TASK_0117_BUDGET_ID, '0.1.17'), (task, version))
        self.assertIn(cleanup.RELEASE_TASK_0117_REBASELINE_PREPARED_SHA, approval)
        self.assertNotEqual(grant, cleanup.RELEASE_TASK_0117_REBASELINE_ID)
        self.assertTrue(cleanup._rebaseline_prior_task_allowed(task, task, grant))
        self.assertFalse(cleanup._rebaseline_prior_task_allowed(cleanup.RELEASE_TASK_0116_BUDGET_ID, task, grant))

    def test_second_grant_requires_same_version_and_the_prepared_lineage(self):
        grant = cleanup.RELEASE_TASK_0117_REBASELINE_ID_2
        versions = {'old': '0.1.17', 'new': '0.1.17', 'older': '0.1.16', 'other': '0.1.18'}
        with patch.object(cleanup, '_git_version_at', side_effect=lambda sha: versions[sha]), patch.object(cleanup, '_git_is_ancestor', return_value=True) as ancestor:
            self.assertTrue(cleanup._rebaseline_versions_match('old', 'new', '0.1.17', grant))
            self.assertEqual((cleanup.RELEASE_TASK_0117_REBASELINE_PREPARED_SHA, 'new'), ancestor.call_args.args)
            self.assertFalse(cleanup._rebaseline_versions_match('older', 'new', '0.1.17', grant))
            self.assertFalse(cleanup._rebaseline_versions_match('old', 'other', '0.1.17', grant))
            self.assertFalse(cleanup._rebaseline_versions_match('old', 'new', '0.1.16', grant))
        with patch.object(cleanup, '_git_version_at', side_effect=lambda sha: versions[sha]), patch.object(cleanup, '_git_is_ancestor', return_value=False):
            self.assertFalse(cleanup._rebaseline_versions_match('old', 'new', '0.1.17', grant))


if __name__ == '__main__':
    unittest.main()
