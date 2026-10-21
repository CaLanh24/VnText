"""Explicit editor review must use saved disk rows, never caller targets."""
import tempfile
from pathlib import Path
import unittest
from tests.lib.work_paths import work_temp_dir
from vntext.package_io import write_csv_rows_file
from vntext import csv_editor_api as api


class ReviewedMemoryEditorTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(dir=work_temp_dir('reviewed-memory-editor'))
        self.package=Path(self.temp.name);self.csv=self.package/'translation.csv'
        self.fields=['key','source_text','translation','file_path','context','import_method']
        self.rows=[dict(key='a',source_text='Open the door.',translation='Mở cửa.',file_path='scene.txt',context='scene:1',import_method='plain_text_line'),
                   dict(key='b',source_text='Please wait.',translation='Vui lòng chờ.',file_path='scene.txt',context='scene:2',import_method='plain_text_line')]
        write_csv_rows_file(self.csv,self.fields,self.rows)
        (self.package/'manifest.json').write_text('{}',encoding='utf-8')

    def tearDown(self):self.temp.cleanup()

    def snapshot(self):return {str(p.relative_to(self.package)):p.read_bytes() for p in self.package.rglob('*') if p.is_file()}

    def test_preview_selected_saved_rows_only_and_no_writes(self):
        before=self.snapshot()
        result=api.preview_reviewed_memory(self.csv,['b'])
        self.assertTrue(result['ok'],result)
        self.assertEqual([r['key'] for r in result['rows']],['b'])
        self.assertEqual(result['rows'][0]['translation'],'Vui lòng chờ.')
        self.assertEqual(before,self.snapshot())

    def test_preview_rejects_duplicate_unknown_empty_selection(self):
        for keys in ([],['a','a'],['missing']):
            with self.subTest(keys=keys):self.assertFalse(api.preview_reviewed_memory(self.csv,keys)['ok'])

    def test_preview_rejects_missing_scope_or_invalid_structure(self):
        for change in ({'context':''},{'file_path':''},{'translation':'Mở {EXTRA} cửa.'}):
            write_csv_rows_file(self.csv,self.fields,[{**self.rows[0],**change},self.rows[1]])
            with self.subTest(change=change):self.assertFalse(api.preview_reviewed_memory(self.csv,['a'])['ok'])

    def test_preview_token_changes_when_csv_or_policy_changes(self):
        first=api.preview_reviewed_memory(self.csv,['a'])
        write_csv_rows_file(self.csv,self.fields,[{**self.rows[0],'translation':'Mở cánh cửa.'},self.rows[1]])
        second=api.preview_reviewed_memory(self.csv,['a'])
        self.assertNotEqual(first['preview_token'],second['preview_token'])
        (self.package/'.mt').mkdir();(self.package/'.mt/translation_memory_scope.json').write_text('broken',encoding='utf-8')
        self.assertFalse(api.preview_reviewed_memory(self.csv,['a'])['ok'])

    def test_validation_inputs_change_token_and_ambiguous_unselected_scope_refuses(self):
        before=api.preview_reviewed_memory(self.csv,['a'])
        (self.package/'.mt').mkdir()
        (self.package/'.mt/whitelist.json').write_text('{"tokens":[]}',encoding='utf-8')
        after=api.preview_reviewed_memory(self.csv,['a'])
        self.assertNotEqual(before['preview_token'],after['preview_token'])
        write_csv_rows_file(self.csv,self.fields,[*self.rows,{**self.rows[0],'key':'duplicate-scope'}])
        self.assertFalse(api.preview_reviewed_memory(self.csv,['a'])['ok'])

    def test_confirm_selected_only_and_extend_without_learning_other_rows(self):
        from vntext.mt_memory import load_translation_memory,lookup_translation_memory,build_translation_memory
        preview=api.preview_reviewed_memory(self.csv,['a'])
        result=api.confirm_reviewed_memory(self.csv,['a'],preview['preview_token'])
        self.assertTrue(result['ok'],result)
        loaded=load_translation_memory(self.package)
        self.assertEqual(lookup_translation_memory(self.rows[0],loaded),'Mở cửa.')
        self.assertIsNone(lookup_translation_memory(self.rows[1],loaded))
        self.assertEqual(len(build_translation_memory(self.rows,self.package)['entries']),1)
        preview=api.preview_reviewed_memory(self.csv,['b'])
        self.assertTrue(api.confirm_reviewed_memory(self.csv,['b'],preview['preview_token'])['ok'])
        self.assertEqual(len(load_translation_memory(self.package)['entries']),2)

    def test_stale_confirm_refuses_without_writes(self):
        preview=api.preview_reviewed_memory(self.csv,['a'])
        write_csv_rows_file(self.csv,self.fields,[{**self.rows[0],'translation':'Mở cánh cửa.'},self.rows[1]])
        before=self.snapshot()
        self.assertFalse(api.confirm_reviewed_memory(self.csv,['a'],preview['preview_token'])['ok'])
        self.assertEqual(before,self.snapshot())

    def test_confirm_lock_refuses_second_writer(self):
        preview=api.preview_reviewed_memory(self.csv,['a'])
        (self.package/'.mt').mkdir();lock=self.package/'.mt/translation_memory_approval.lock';lock.write_text('other',encoding='utf-8')
        self.assertFalse(api.confirm_reviewed_memory(self.csv,['a'],preview['preview_token'])['ok'])
        self.assertEqual(lock.read_text(encoding='utf-8'),'other')

    def test_legacy_conversion_preserves_backup_but_does_not_approve_unselected(self):
        from vntext.mt_memory import build_translation_memory,load_translation_memory
        build_translation_memory(self.rows,self.package)
        old=(self.package/'.mt/translation_memory.json').read_bytes()
        preview=api.preview_reviewed_memory(self.csv,['a']);self.assertTrue(preview['converts_legacy'])
        result=api.confirm_reviewed_memory(self.csv,['a'],preview['preview_token'])
        self.assertTrue(result['ok'],result)
        self.assertEqual(len(load_translation_memory(self.package)['entries']),1)
        self.assertTrue(any(p.read_bytes()==old for p in (self.package/'.mt/approval_history').rglob('*.backup')))

    def test_failure_after_guard_restores_owned_bytes(self):
        from unittest.mock import patch
        from vntext import mt_memory
        preview=api.preview_reviewed_memory(self.csv,['a'])
        original=mt_memory._approval_replace
        def fault(path,data):
            if path.name=='translation_memory.json':raise OSError('injected store failure')
            return original(path,data)
        with patch('vntext.mt_memory._approval_replace',side_effect=fault):
            result=api.confirm_reviewed_memory(self.csv,['a'],preview['preview_token'])
        self.assertFalse(result['ok']);self.assertTrue(result['rolled_back'],result)
        self.assertFalse((self.package/'.mt/translation_memory_scope.json').exists())
        self.assertFalse((self.package/'.mt/translation_memory_decisions.json').exists())

    def test_foreign_guard_mutation_is_preserved_and_reuse_fails_closed(self):
        from unittest.mock import patch
        from vntext import mt_memory
        preview=api.preview_reviewed_memory(self.csv,['a']);original=mt_memory._approval_replace
        def mutate(path,data):
            original(path,data)
            if path.name=='translation_memory_scope.json':path.write_bytes(b'foreign-change')
        with patch('vntext.mt_memory._approval_replace',side_effect=mutate):
            result=api.confirm_reviewed_memory(self.csv,['a'],preview['preview_token'])
        self.assertFalse(result['ok']);self.assertFalse(result['rolled_back'])
        self.assertEqual((self.package/'.mt/translation_memory_scope.json').read_bytes(),b'foreign-change')
        self.assertTrue(mt_memory.load_translation_memory(self.package).get('scope_error'))

    def test_decision_corruption_invalidates_user_confirmed_store(self):
        from vntext.mt_memory import load_translation_memory,lookup_translation_memory
        preview=api.preview_reviewed_memory(self.csv,['a'])
        self.assertTrue(api.confirm_reviewed_memory(self.csv,['a'],preview['preview_token'])['ok'])
        (self.package/'.mt/translation_memory_decisions.json').write_text('{}',encoding='utf-8')
        self.assertIsNone(lookup_translation_memory(self.rows[0],load_translation_memory(self.package)))

    def test_csv_change_after_revalidated_preview_is_not_accepted(self):
        from unittest.mock import patch
        from vntext import mt_memory
        preview=api.preview_reviewed_memory(self.csv,['a']);original=mt_memory.activate_reviewed_memory
        def race(package,rows,snapshot,read):
            write_csv_rows_file(self.csv,self.fields,[{**self.rows[0],'translation':'Mở cánh cửa.'},self.rows[1]])
            return original(package,rows,snapshot,read)
        with patch('vntext.mt_memory.activate_reviewed_memory',side_effect=race):
            result=api.confirm_reviewed_memory(self.csv,['a'],preview['preview_token'])
        self.assertFalse(result['ok'])
        self.assertFalse((self.package/'.mt/translation_memory_scope.json').exists())

    def test_malformed_legacy_cannot_be_silently_converted(self):
        (self.package/'.mt').mkdir()
        path=self.package/'.mt/translation_memory.json'
        for data in ('not json','{"version":"unknown","entries":[]}', '{"version":"1.0.0","entries":[{}]}'):
            path.write_text(data,encoding='utf-8');before=self.snapshot()
            with self.subTest(data=data):self.assertFalse(api.preview_reviewed_memory(self.csv,['a'])['ok'])
            self.assertEqual(before,self.snapshot())

    def test_mixed_store_keeps_old_delegated_reviewer_per_entry(self):
        import json
        from vntext.mt_memory import _digest_entries,load_translation_memory
        first=api.preview_reviewed_memory(self.csv,['a'])
        self.assertTrue(api.confirm_reviewed_memory(self.csv,['a'],first['preview_token'])['ok'])
        store=self.package/'.mt/translation_memory.json';guard_path=self.package/'.mt/translation_memory_scope.json'
        old=json.loads(store.read_text(encoding='utf-8'));guard=json.loads(guard_path.read_text(encoding='utf-8'))
        # Controlled preexisting delegated fixture; no user approval fabricated.
        old['review_kind']='owner-delegated-agent';old['entries'][0]['reviewer_kind']='owner-delegated-agent'
        guard['entries_sha256']=_digest_entries(old['entries'])
        guard['approval_records'][old['entries'][0]['approval_id']]['reviewer_kind']='owner-delegated-agent'
        store.write_text(json.dumps(old),encoding='utf-8');guard_path.write_text(json.dumps(guard),encoding='utf-8')
        second=api.preview_reviewed_memory(self.csv,['b'])
        self.assertTrue(api.confirm_reviewed_memory(self.csv,['b'],second['preview_token'])['ok'])
        loaded=load_translation_memory(self.package)
        self.assertFalse(loaded.get('scope_error'),loaded)
        self.assertEqual(loaded['review_kind'],'mixed-explicit')
        self.assertEqual([e['reviewer_kind']for e in loaded['entries']],['owner-delegated-agent','user-confirmed'])


if __name__=='__main__':unittest.main()
