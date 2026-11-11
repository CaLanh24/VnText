import hashlib
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[2]
from vntext import csv_editor_api as api


class Transactions(unittest.TestCase):
    def setUp(self):
        base=ROOT/'TEST_RUN/tmp';base.mkdir(parents=True,exist_ok=True)
        self.temp=tempfile.TemporaryDirectory(prefix='audit-csv-',dir=base);self.addCleanup(self.temp.cleanup)
        self.csv=Path(self.temp.name)/'translation.csv';self.original=b'key,source_text,translation\r\nk,Hello,Xin chao\r\n'
        self.csv.write_bytes(self.original);self.doc=api.load_document(self.csv)

    def replace(self):
        return api.replace_translation(self.csv,self.doc['fields'],self.doc['rows'],'chao','chào',expected_sha256=self.doc['source_sha256'])

    def test_bulk_undo_restores_exact_csv_bytes_and_caller_draft(self):
        before=[dict(x) for x in self.doc['rows']];result=self.replace();self.assertTrue(result['ok'],result)
        self.assertEqual(self.doc['rows'],before)
        self.assertTrue(api.restore_backup(self.csv,result['backup_path'])['ok'])
        self.assertEqual(self.csv.read_bytes(),self.original)

    def test_external_change_before_replace_preserved(self):
        self.csv.write_bytes(self.original+b'foreign')
        result=self.replace();self.assertFalse(result['ok']);self.assertEqual(self.csv.read_bytes(),self.original+b'foreign')

    def test_reconcile_failure_rolls_back_exact_bytes(self):
        with patch.object(api,'_reconcile_saved_review_rows',side_effect=OSError('ledger denied')):
            result=self.replace()
        self.assertFalse(result['ok']);self.assertTrue(result['rolled_back']);self.assertEqual(self.csv.read_bytes(),self.original)

    def test_foreign_write_after_commit_is_never_rolled_back(self):
        def foreign(*a,**kw):self.csv.write_bytes(b'foreign');raise OSError('ledger denied')
        with patch.object(api,'_reconcile_saved_review_rows',side_effect=foreign):result=self.replace()
        self.assertFalse(result['ok']);self.assertFalse(result['rolled_back']);self.assertTrue(result['foreign_change_preserved']);self.assertEqual(self.csv.read_bytes(),b'foreign')

    def test_undo_refuses_new_external_csv_revision(self):
        result=self.replace();self.csv.write_bytes(b'foreign')
        self.assertFalse(api.restore_backup(self.csv,result['backup_path'])['ok']);self.assertEqual(self.csv.read_bytes(),b'foreign')

    def test_legacy_undo_needs_explicit_current_hash(self):
        backup=self.csv.with_suffix('.bak');backup.write_bytes(self.original)
        self.assertFalse(api.restore_backup(self.csv,backup)['ok'])
        digest=hashlib.sha256(self.csv.read_bytes()).hexdigest()
        self.assertTrue(api.restore_backup(self.csv,backup,digest)['ok'])


if __name__=='__main__':unittest.main()
