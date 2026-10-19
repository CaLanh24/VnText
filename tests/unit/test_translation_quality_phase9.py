import json
import unittest
import unicodedata
from tests.tools import translation_quality_phase9 as t


class ConstraintPipelineTests(unittest.TestCase):
    def test_counterexample_retries_once_without_semantic_auto_acceptance(self):
        row=dict(id='X',source_en='I will lend you my scarf.',address_context='older sister to younger brother',group='address',split='development')
        calls=[];responses=iter(['Chị sẽ cho em và chị mượn khăn của chị.','Chị sẽ cho em mượn khăn của chị.'])
        def infer(prompt,label):calls.append(prompt);return next(responses)
        r=t.constrained_pipeline(row,infer)
        self.assertEqual([h['state'] for h in r['history']],['FAIL','CONSTRAINTS_MATCH'])
        self.assertEqual(len(calls),2)
        self.assertIn('recipient: em',calls[1])
        self.assertEqual(r['output'],'')
        self.assertEqual(r['status'],'NEEDS_REVIEW')

    def test_persistent_error_and_unsupported_stop_safely(self):
        row=dict(id='X',source_en='Unless the user confirms, leave the files untouched.',group='logic',split='development')
        r=t.constrained_pipeline(row,lambda *_:'Chỉ khi người dùng xác nhận, hãy giữ nguyên các tệp.')
        self.assertEqual(len(r['history']),2)
        self.assertEqual(r['constraint_status'],'FAIL')
        row['source_en']='The mountains look blue.'
        r=t.constrained_pipeline(row,lambda *_:'Những ngọn núi trông xanh.')
        self.assertEqual(len(r['history']),1)
        self.assertEqual(r['constraint_status'],'UNKNOWN')

    def test_corrupted_identifiers_do_not_leak_into_retry_feedback(self):
        row=dict(id='X',source_en='Reject {FILE_ID} unless its checksum is valid.',group='protected_tokens',split='development')
        prompts=[]
        def infer(prompt,label):prompts.append(prompt);return 'Từ chối {WRONG}.'
        r=t.constrained_pipeline(row,infer)
        self.assertTrue(all(h['structural_error'] for h in r['history']))
        self.assertNotIn('{FILE_ID}',prompts[1])
        self.assertNotIn('{WRONG}',prompts[1])

    def test_frozen_sources_unique_and_scene_split(self):
        self.assertEqual(t.natural.prior.digest(t.DATA),t.DATA_HASH)
        self.assertEqual(t.natural.prior.digest(t.FIXTURES),t.FIXTURES_HASH)
        rows=json.loads(t.DATA.read_text(encoding='utf-8'))['rows']
        norm=lambda s:''.join(c for c in unicodedata.normalize('NFKC',s).casefold() if c.isalnum())
        new={norm(r['source_en']) for r in rows};self.assertEqual(len(new),16)
        for phase in (1,5,6,7,8):
            old=json.loads((t.ROOT/f'evaluation/translation_quality_phase{phase}/dataset.v1.json').read_text(encoding='utf-8'))['rows']
            self.assertFalse(new&{norm(r['source_en']) for r in old})
        groups={}
        for r in rows:groups.setdefault(r['scenario_boundary']['group_id'],set()).add(r['split'])
        self.assertTrue(all(len(v)==1 for v in groups.values()))
