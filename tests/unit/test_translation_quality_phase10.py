import json
import unittest
import unicodedata
from tests.tools import translation_quality_phase10 as t


class StableRevisionTests(unittest.TestCase):
    def test_retry_never_replaces_unknown_with_unproven_changed_negation(self):
        row=dict(id='X',source_en='Keep unverified records outside the set eligible for export.',group='logic',split='development')
        original='Giữ bản ghi chưa xác minh ở ngoài nhóm, không phù hợp để xuất khẩu.'
        responses=iter([original,'Giữ bản ghi chưa xác minh ở ngoài nhóm, phù hợp để xuất khẩu.'])
        r=t.constrained_pipeline(row,lambda *_:next(responses))
        self.assertEqual(len(r['history']),2)
        self.assertEqual(r['selected_attempt'],0)
        self.assertEqual(r['draft'],original)
        self.assertEqual(r['output'],'')

    def test_proven_constraint_revision_selected_and_wordbank_not_substring(self):
        row=dict(id='X',source_en='Reject the file unless its signature is valid.',group='logic',split='development')
        responses=iter(['Reject tệp nếu chữ ký không hợp lệ.','Từ chối tệp nếu chữ ký không hợp lệ.'])
        prompts=[]
        def infer(prompt,label):prompts.append(prompt);return next(responses)
        r=t.constrained_pipeline(row,infer)
        self.assertEqual(r['selected_attempt'],1)
        self.assertEqual(r['constraint_status'],'CONSTRAINTS_MATCH')
        self.assertIn('reject = từ chối',prompts[0])
        self.assertNotIn('reject =',t.translation_prompt({**row,'source_en':'The rejection is final.'},'',[])[0])

    def test_data_rights_and_disjoint_group_splits(self):
        self.assertEqual(t.natural.prior.digest(t.DATA),t.DATA_HASH)
        self.assertEqual(t.natural.prior.digest(t.FIXTURES),t.FIXTURES_HASH)
        rows=json.loads(t.DATA.read_text(encoding='utf-8'))['rows']
        norm=lambda s:''.join(c for c in unicodedata.normalize('NFKC',s).casefold() if c.isalnum())
        new={norm(r['source_en']) for r in rows};self.assertEqual(len(new),12)
        for phase in (1,5,6,7,8,9):
            old=json.loads((t.ROOT/f'evaluation/translation_quality_phase{phase}/dataset.v1.json').read_text(encoding='utf-8'))['rows']
            self.assertFalse(new&{norm(r['source_en']) for r in old})
        groups={}
        for r in rows:groups.setdefault(r['scenario_boundary']['group_id'],set()).add(r['split'])
        self.assertTrue(all(len(v)==1 for v in groups.values()))
        self.assertEqual(sum(r['split']=='held_out' for r in rows),4)
