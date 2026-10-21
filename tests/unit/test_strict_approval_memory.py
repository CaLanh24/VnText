"""Strict approval boundary regressions; fixture uses only delegated synthetic data."""
import copy
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from vntext.mt_memory import build_translation_memory,load_translation_memory,lookup_translation_memory,normalize_memory_text
from tests.tools import translation_owner_approval as approval


def hashed(value):return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode('utf-8')).hexdigest()
def binding(path):return hashlib.sha256(str(Path(path).resolve()).casefold().encode('utf-8')).hexdigest()


class StrictApprovalMemoryTests(unittest.TestCase):
    def setUp(self):
        from tests.lib.work_paths import work_temp_dir
        self.temp=tempfile.TemporaryDirectory(prefix='strict-approval-',dir=work_temp_dir('strict-approval-memory'))
        self.package=Path(self.temp.name)/'package';(self.package/'.mt').mkdir(parents=True)
        decision=approval.original.load(approval.DEST/'decision.json');row=decision['translations'][0]
        self.row=dict(key=row['id'],source_text=row['source'],translation='',file_path=row['scenario_boundary']['file_id'],
                      context=row['scenario_boundary']['group_id']+':'+row['id'],import_method='plain_text_line')
        self.target=row['translation']
        entry=dict(source=normalize_memory_text(row['source']),context_family=self.row['context'].split(':')[0],
                   source_text_exact=row['source'],context_exact=self.row['context'],file_path_exact=self.row['file_path'],
                   import_method='plain_text_line',translation=self.target,approved=True,human_gold=False,training_eligible=False)
        draft=next(r for r in approval.original.load(approval.original.DEST/'proposals.json')['translations'] if r['id']==row['id'])
        entry.update(approval_id=row['id'],proposal_sha256=hashed(draft))
        self.memory=dict(version='1.0.0',scope_policy='strict-approval-v1',package_binding=binding(self.package),
                         approval_sha256=approval.sha(approval.DEST/'decision.json'),review_kind='owner-delegated-agent',entries=[entry])
        self.memory['proposal_file_sha256']=decision['proposal_file_sha256']
        self.guard=dict(version=1,scope_policy='strict-approval-v1',package_binding=self.memory['package_binding'],
                        approval_sha256=self.memory['approval_sha256'],entries_sha256=hashed(self.memory['entries']))
        self.guard.update(proposal_file_sha256=self.memory['proposal_file_sha256'],approval_records={row['id']:dict(
            proposal_sha256=entry['proposal_sha256'],scope_sha256=hashed({k:entry[k] for k in
            ('source_text_exact','file_path_exact','context_exact','import_method','translation')}))})
        self.store=self.package/'.mt/translation_memory.json';self.marker=self.package/'.mt/translation_memory_scope.json'
        self.write()

    def write(self):
        self.store.write_text(json.dumps(self.memory,ensure_ascii=False),encoding='utf-8')
        self.marker.write_text(json.dumps(self.guard),encoding='utf-8')

    def tearDown(self):self.temp.cleanup()

    def test_matching_scope_reuses_reviewed_target(self):
        self.assertEqual(lookup_translation_memory(self.row,load_translation_memory(self.package)),self.target)

    def test_wrong_file_full_context_raw_case_whitespace_or_method_miss(self):
        for field,value in [('file_path','other.txt'),('context','other:1'),('source_text',self.row['source_text'].upper()),
                            ('source_text',' '+self.row['source_text']),('import_method','other')]:
            with self.subTest(field=field,value=value):
                self.assertIsNone(lookup_translation_memory({**self.row,field:value},load_translation_memory(self.package)))

    def test_copied_package_binding_misses(self):
        other=Path(self.temp.name)/'copy';shutil.copytree(self.package,other)
        self.assertIsNone(lookup_translation_memory(self.row,load_translation_memory(other)))

    def test_missing_or_corrupt_store_never_rebuilds_as_legacy(self):
        rows=[{**self.row,'translation':self.target}]
        for payload in (None,'broken JSON'):
            self.write()
            if payload is None:self.store.unlink()
            else:self.store.write_text(payload,encoding='utf-8')
            loaded=build_translation_memory(rows,self.package)
            self.assertTrue(loaded.get('scope_error'))
            self.assertIsNone(lookup_translation_memory(self.row,loaded))
            if payload is None:self.assertFalse(self.store.exists())
            else:self.assertEqual(self.store.read_text(encoding='utf-8'),payload)

    def test_missing_guard_or_unknown_policy_does_not_downgrade(self):
        self.marker.unlink()
        self.assertIsNone(lookup_translation_memory(self.row,build_translation_memory([],self.package)))
        self.guard['scope_policy']='unknown';self.write()
        self.assertIsNone(lookup_translation_memory(self.row,load_translation_memory(self.package)))

    def test_rebuild_preserves_policy_bytes_without_learning_csv(self):
        before=self.store.read_bytes()
        loaded=build_translation_memory([{**self.row,'translation':'Unapproved changed wording'}],self.package)
        self.assertEqual(self.store.read_bytes(),before)
        self.assertEqual(lookup_translation_memory(self.row,loaded),self.target)

    def test_duplicate_entries_fail_closed_even_with_same_wording(self):
        self.memory['entries'].append(copy.deepcopy(self.memory['entries'][0]))
        self.guard['entries_sha256']=hashed(self.memory['entries']);self.write()
        self.assertIsNone(lookup_translation_memory(self.row,load_translation_memory(self.package)))

    def test_guard_removed_after_load_blocks_lookup_and_cache_write(self):
        from unittest.mock import MagicMock
        from vntext.mt_ct2_pipeline import _cache_validated_candidate
        loaded=load_translation_memory(self.package)
        self.marker.unlink()
        self.assertIsNone(lookup_translation_memory(self.row,loaded))
        cache=MagicMock()
        _cache_validated_candidate(cache,self.row,self.target,{'approval_memory':loaded})
        cache.put.assert_not_called()

    def test_strict_cache_scope_includes_file_without_changing_legacy_key(self):
        from vntext.translation_cache import compute_cache_fingerprint
        args=dict(model_metadata={'model_id':'test'},memory_scope='approval-set-hash')
        other={**self.row,'file_path':'other.txt'}
        self.assertEqual(compute_cache_fingerprint(self.row,**args)['cache_key'],
                         compute_cache_fingerprint(other,**args)['cache_key'])
        args['memory_scope_policy']='strict-approval-v1'
        self.assertNotEqual(compute_cache_fingerprint(self.row,**args)['cache_key'],
                            compute_cache_fingerprint(other,**args)['cache_key'])

    def test_missing_wrong_or_duplicate_approval_identity_fails_closed(self):
        original=copy.deepcopy(self.memory)
        for field,value in [('approval_id',None),('approval_id','UNREVIEWED'),('proposal_sha256','0'*64)]:
            self.memory=copy.deepcopy(original)
            if value is None:self.memory['entries'][0].pop(field)
            else:self.memory['entries'][0][field]=value
            self.guard['entries_sha256']=hashed(self.memory['entries']);self.write()
            with self.subTest(field=field,value=value):
                self.assertIsNone(lookup_translation_memory(self.row,load_translation_memory(self.package)))

    def test_changed_entry_cannot_be_resealed_without_reviewed_scope_record(self):
        self.memory['entries'][0]['translation']='Unreviewed replacement'
        self.guard['entries_sha256']=hashed(self.memory['entries']);self.write()
        self.assertIsNone(lookup_translation_memory(self.row,load_translation_memory(self.package)))

    def test_real_pipeline_cache_hit_then_wrong_file_miss_with_same_key(self):
        from unittest.mock import patch
        from vntext.mt_ct2_pipeline import run_ct2_translate_keys
        from vntext.package_io import read_csv_rows_file,write_csv_rows_file
        class Delegate:
            config={'batch_size':8,'inter_threads':1,'flush_every':8}
            calls=0
            def translate_many(inst,texts):
                inst.calls+=1;return ['Mara suýt tiết lộ chuyện bất ngờ.' for _ in texts]
            def translate(inst,text):
                inst.calls+=1;return 'Mara suýt tiết lộ chuyện bất ngờ.'
        delegate=Delegate()
        csv_path=self.package/'translation.csv';fields=list(self.row)
        write_csv_rows_file(csv_path,fields,[self.row])
        before=self.store.read_bytes()
        with patch('vntext.mt_ct2_model.get_translator',return_value=delegate):
            first=run_ct2_translate_keys(csv_path,[self.row['key']],backup=False)
            second=run_ct2_translate_keys(csv_path,[self.row['key']],backup=False)
            self.assertEqual(delegate.calls,0)
            self.assertEqual(first['cache']['writes'],1)
            self.assertEqual(second['cache']['hits'],1)
            write_csv_rows_file(csv_path,fields,[{**self.row,'source_text':self.row['source_text'].upper()}])
            changed_case=run_ct2_translate_keys(csv_path,[self.row['key']],backup=False)
            self.assertEqual(changed_case['cache']['hits'],0)
            self.assertGreater(delegate.calls,0)
            write_csv_rows_file(csv_path,fields,[{**self.row,'file_path':'other.txt'}])
            wrong=run_ct2_translate_keys(csv_path,[self.row['key']],backup=False)
        self.assertEqual(wrong['cache']['hits'],0)
        self.assertGreater(delegate.calls,0)
        self.assertNotEqual(read_csv_rows_file(csv_path)[1][0]['translation'],self.target)
        self.assertEqual(self.store.read_bytes(),before)

    def test_stale_approval_snapshot_cannot_authorize_cache_reads(self):
        from unittest.mock import MagicMock
        from vntext.mt_ct2_pipeline import _cached_batch_translate_chunk,_translation_cache_context
        from vntext.mt_model_adapter import Ct2ModelAdapter
        loaded=load_translation_memory(self.package)
        delegate=MagicMock();delegate.config={'batch_size':8}
        delegate.translate_many.return_value=['Mara suýt tiết lộ chuyện bất ngờ.']
        context=_translation_cache_context(self.package,Ct2ModelAdapter(delegate),{},loaded,allow_overwrite=True)
        self.marker.unlink()
        cache=MagicMock();cache.lookup.return_value=self.target
        _out,_hits,authority=_cached_batch_translate_chunk(cache,delegate,[self.row],{},loaded,context)
        cache.lookup.assert_not_called()
        self.assertFalse(authority)
        delegate.translate_many.assert_called()

    def test_approval_flags_do_not_bypass_structure_gate(self):
        from vntext.mt_ct2_status import _safe_candidate
        candidate,reasons=_safe_candidate(self.row,self.target+' {EXTRA}',set(),quality=True,preserve_candidate=True)
        self.assertIsNone(candidate)
        self.assertTrue(reasons)


if __name__=='__main__':unittest.main()
