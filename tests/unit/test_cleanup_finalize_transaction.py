"""Canonical runner finalization shares one bounded integrity transaction."""
from pathlib import Path
import unittest
from unittest.mock import patch

from tests.tools import cleanup_work_artifacts as cleanup


class FinalizeTransactionTests(unittest.TestCase):
    def call(self):
        return cleanup.finalize_scope(scope_id="fixture", run_id="fixture", scope_root=Path("fixture"), before=None)

    def test_direct_finalization_has_memo_and_clears_it_between_calls(self):
        seen = []

        def implementation(**kwargs):
            seen.append((cleanup._TXN_DEPTH, dict(cleanup._INTEGRITY_CACHE)))
            cleanup._INTEGRITY_CACHE["fixture-proof"] = True
            return {"ok": True}

        with patch.object(cleanup, "assert_artifact_under_work", side_effect=lambda path, purpose: path), patch.object(cleanup, "_finalize_scope_impl", side_effect=implementation):
            self.assertTrue(self.call()["ok"])
            self.assertTrue(self.call()["ok"])
        self.assertEqual(seen, [(1, {}), (1, {})])
        self.assertEqual(cleanup._TXN_DEPTH, 0)
        self.assertEqual(cleanup._INTEGRITY_CACHE, {})

    def test_nested_finalization_preserves_outer_memo_until_outer_exit(self):
        def implementation(**kwargs):
            self.assertEqual(cleanup._TXN_DEPTH, 2)
            self.assertEqual(cleanup._INTEGRITY_CACHE.get("outer-proof"), "valid")
            return {"ok": True}

        def outer():
            cleanup._INTEGRITY_CACHE["outer-proof"] = "valid"
            self.call()
            self.assertEqual(cleanup._TXN_DEPTH, 1)
            self.assertEqual(cleanup._INTEGRITY_CACHE.get("outer-proof"), "valid")

        with patch.object(cleanup, "assert_artifact_under_work", side_effect=lambda path, purpose: path), patch.object(cleanup, "_finalize_scope_impl", side_effect=implementation):
            cleanup._transaction(outer)()
        self.assertEqual(cleanup._TXN_DEPTH, 0)
        self.assertEqual(cleanup._INTEGRITY_CACHE, {})

    def test_exception_does_not_leak_transaction_or_memo(self):
        def fail(**kwargs):
            cleanup._INTEGRITY_CACHE["fixture-proof"] = True
            raise RuntimeError("fixture error")
        with patch.object(cleanup, "assert_artifact_under_work", side_effect=lambda path, purpose: path), patch.object(cleanup, "_new_inventory_budget", side_effect=fail):
            with self.assertRaisesRegex(RuntimeError, "fixture error"):
                self.call()
        self.assertEqual(cleanup._TXN_DEPTH, 0)
        self.assertEqual(cleanup._INTEGRITY_CACHE, {})


if __name__ == '__main__':
    unittest.main()
