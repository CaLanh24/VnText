import json
import unicodedata
import unittest
from tests.tools import translation_quality_phase13 as t


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

    def test_unfinished_revision_and_failed_retry_retention(self):
        row=dict(id='X',source_en='Keep unresolved translations outside the set permitted for release.',group='logic',split='development')
        bad='Giữ bản dịch chưa hoàn thiện ngoài tập hợp đủ điều kiện phát hành.'
        good='Giữ bản dịch chưa giải quyết ngoài tập hợp đủ điều kiện phát hành.'
        responses=iter([bad,good])
        r=t.constrained_pipeline(row,lambda *_:next(responses))
        self.assertEqual([h['state'] for h in r['history']],['FAIL','CONSTRAINTS_MATCH'])
        self.assertEqual(r['selected_attempt'],1)
        self.assertEqual(r['draft'],good)
        r=t.constrained_pipeline(row,lambda *_:bad)
        self.assertEqual(r['selected_attempt'],0)
        self.assertEqual(r['constraint_status'],'FAIL')
        self.assertEqual(r['output'],'')
        self.assertEqual(r['status'],'NEEDS_REVIEW')
        prompt,_,_=t.translation_prompt(row,'',[])
        self.assertIn('unresolved = chưa giải quyết',prompt)
        self.assertTrue(prompt.rstrip().endswith(row['source_en']))

    def test_fresh_sources_and_groups(self):
        self.assertEqual(t.natural.prior.digest(t.DATA),t.DATA_HASH)
        self.assertEqual(t.natural.prior.digest(t.FIXTURES),t.FIXTURES_HASH)
        rows=json.loads(t.DATA.read_text(encoding='utf-8'))['rows']
        norm=lambda s:''.join(c for c in unicodedata.normalize('NFKC',s).casefold() if c.isalnum())
        new={norm(r['source_en']) for r in rows};self.assertEqual(len(new),4)
        for phase in (1,5,6,7,8,9,10,11,12):
            old=json.loads((t.ROOT/f'evaluation/translation_quality_phase{phase}/dataset.v1.json').read_text(encoding='utf-8'))['rows']
            self.assertFalse(new&{norm(r['source_en']) for r in old})
        groups={}
        for r in rows:groups.setdefault(r['scenario_boundary']['group_id'],set()).add(r['split'])
        self.assertTrue(all(len(v)==1 for v in groups.values()))
