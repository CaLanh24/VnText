import json
import unicodedata
import unittest
from tests.tools import translation_quality_phase11 as t


class TargetedRemediationTests(unittest.TestCase):
    def test_wrong_prohibition_revision_becomes_selected_match(self):
        row=dict(id='X',source_en='Keep unverified records outside the set eligible for release.',group='logic',split='development')
        responses=iter(['Đừng giữ bản ghi chưa xác minh ngoài danh sách có thể được phát hành.',
                        'Giữ bản ghi chưa xác minh ngoài danh sách có thể được phát hành.'])
        r=t.constrained_pipeline(row,lambda *_:next(responses))
        self.assertEqual([h['state'] for h in r['history']],['FAIL','CONSTRAINTS_MATCH'])
        self.assertEqual(r['selected_attempt'],1)
        self.assertFalse(r['draft'].startswith('Đừng'))
        self.assertEqual(r['output'],'')

    def test_owner_cue_cannot_turn_omitted_ownership_into_match(self):
        row=dict(id='X',source_en='May I send you my revised summary this evening?',address_context='younger student to older professor; gender unknown',group='address',split='development')
        prompt,_,_=t.translation_prompt(row,'',[])
        self.assertIn('của em',prompt)
        result=t.constrained_pipeline(row,lambda *_:'Em có thể gửi giáo sư bản tóm tắt tối nay không?')
        self.assertEqual(result['constraint_status'],'UNKNOWN')
        result=t.constrained_pipeline(row,lambda *_:'Em có thể gửi giáo sư bản tóm tắt của mình tối nay không?')
        self.assertEqual(result['constraint_status'],'CONSTRAINTS_MATCH')

    def test_fresh_sources_and_groups(self):
        self.assertEqual(t.natural.prior.digest(t.DATA),t.DATA_HASH)
        self.assertEqual(t.natural.prior.digest(t.FIXTURES),t.FIXTURES_HASH)
        rows=json.loads(t.DATA.read_text(encoding='utf-8'))['rows']
        norm=lambda s:''.join(c for c in unicodedata.normalize('NFKC',s).casefold() if c.isalnum())
        new={norm(r['source_en']) for r in rows};self.assertEqual(len(new),8)
        for phase in (1,5,6,7,8,9,10):
            old=json.loads((t.ROOT/f'evaluation/translation_quality_phase{phase}/dataset.v1.json').read_text(encoding='utf-8'))['rows']
            self.assertFalse(new&{norm(r['source_en']) for r in old})
        groups={}
        for r in rows:groups.setdefault(r['scenario_boundary']['group_id'],set()).add(r['split'])
        self.assertTrue(all(len(v)==1 for v in groups.values()))
