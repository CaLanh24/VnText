"""Synthetic disk fixtures only; no live registry or user files are mutated."""
import contextlib
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'tests/lib'),str(ROOT/'tests/tools')]
from registry_storage import pack_exact, snapshot_bytes, snapshot_json, archive_missing, cold_records
from compact_registry_history import plan, apply


class StorageTests(unittest.TestCase):
    def setUp(self):
        base=ROOT/'TEST_RUN/tmp';base.mkdir(parents=True,exist_ok=True)
        self.temp=tempfile.TemporaryDirectory(prefix='audit-storage-',dir=base)
        self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)

    def test_snapshot_exact_bytes_and_idempotence(self):
        p=self.root/'history.json';raw=b'{"a":"'+b'x'*1500000+b'"}\r\n';p.write_bytes(raw)
        result=pack_exact(p)
        self.assertLess(result['after_bytes'],len(raw));self.assertEqual(snapshot_bytes(p),raw)
        self.assertFalse(pack_exact(p)['changed'])
        p.write_bytes(p.read_bytes()[:-8])
        with self.assertRaises((OSError,EOFError,ValueError)):snapshot_bytes(p)

    def test_failed_replace_preserves_snapshot_and_removes_staging(self):
        p=self.root/'history.json';p.write_bytes(b'original')
        with patch('registry_storage.os.replace',side_effect=OSError('denied')):
            with self.assertRaises(OSError):pack_exact(p)
        self.assertEqual(p.read_bytes(),b'original');self.assertEqual(list(self.root.glob('*.pack')),[])

    def fixture(self):
        tr=self.root/'TEST_RUN';hist=tr/'artifact-registry-epochs/e1';hist.mkdir(parents=True)
        records=[dict(id='missing',path=str(tr/'absent'),lifecycle='MISSING',status='MISSING',proof='unchanged'),
                 dict(id='unknown',path=str(tr/'unknown'),lifecycle='UNKNOWN'),
                 dict(id='artifact-registry-epoch:e1',path=str(hist),lifecycle='RETAINED')]
        d=dict(version=2,schema_version=2,artifacts=records,prospective_epoch={'source_sha':'a'*40,'owner_approval':'original'})
        p=tr/'artifacts_manifest.json';p.write_text(json.dumps(d),encoding='utf8')
        (hist/'rollback_manifest.json').write_text(json.dumps(dict(d,padding='x'*1100000)),encoding='utf8')
        return p,d

    def test_cas_refuses_changed_live_registry_before_mutation(self):
        p,d=self.fixture();reviewed=plan(self.root);p.write_bytes(p.read_bytes()+b' ')
        with self.assertRaisesRegex(ValueError,'changed'):apply(self.root,reviewed)
        self.assertFalse((p.parent/'registry-history').exists())

    def test_migration_preserves_all_records_authority_and_snapshot_hashes(self):
        p,d=self.fixture();snap=p.parent/'artifact-registry-epochs/e1/rollback_manifest.json';before=snap.read_bytes()
        result=apply(self.root,plan(self.root));after=json.loads(p.read_text())
        self.assertTrue(result['ok']);self.assertEqual(snapshot_bytes(snap),before)
        self.assertEqual(after['prospective_epoch'],d['prospective_epoch'])
        all_records=after['artifacts']+list(cold_records(after,p))
        self.assertCountEqual(all_records,d['artifacts'])
        self.assertEqual(after['cold_records'][0]['unresolved_missing'],1)
        blob=p.parent/after['cold_records'][0]['path'];blob.write_bytes(blob.read_bytes()+b'tamper')
        with self.assertRaisesRegex(ValueError,'hash mismatch'):list(cold_records(after,p))


if __name__=='__main__':unittest.main()
