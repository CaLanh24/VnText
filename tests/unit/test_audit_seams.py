import unittest
from unittest.mock import patch
from vntext.patch_plan import group_patch_entries
from tests.lib.dev_projection import latest

class Seams(unittest.TestCase):
    def test_plan_preserves_order_filters_and_diagnostics_without_mutating_input(self):
        rows=[{'key':'a','file_path':'game//dialogue.txt'}, {'key':'b','file_path':'game/dialogue.txt'}, {'key':'c','file_path':'other'}]
        translations={k:{'translation':k.upper()} for k in 'abc'}
        before=[dict(x) for x in rows]
        with patch('vntext.patch_plan.patch_skip_reason',side_effect=lambda e,*a,**kw:'bad tag' if e['key']=='c' else None):
            grouped,skipped,report=group_patch_entries(rows,translations,{'b'},set())
        self.assertEqual(list(grouped),['game\\dialogue.txt'])
        self.assertEqual([e['key'] for e,t in next(iter(grouped.values()))],['a'])
        self.assertEqual(skipped,2); self.assertEqual(report,['SKIP key c: bad tag'])
        self.assertEqual(rows,before)
    def test_projection_never_includes_history_or_text_dump(self):
        response={'content':[{'text':'SECRET HISTORY'}],'structuredContent':{'cursor':7,'agent':{'id':'dev','status':'idle','turns':['SECRET']},'latest_result':{'payload':{'result':'done','turn_id':'t'}}}}
        projected=latest(response)
        self.assertEqual(projected['result'],'done');self.assertEqual(projected['cursor'],7)
        self.assertNotIn('SECRET',str(projected))
    def test_missing_structured_result_is_explicit_not_a_text_fallback(self):
        self.assertFalse(latest({'content':[{'text':'history'}]})['structured_available'])

    def test_explicit_glossary_sentinels_never_reach_model(self):
        from vntext.mt_ct2_io import _batch_translate_chunk
        class Model:
            def translate_many(self,texts):
                if any('ZZG' in t for t in texts):raise AssertionError('sentinel leaked to model')
                return ['Chào buổi sáng, ' if 'morning' in t else ' đã trống rỗng.' for t in texts]
        for src,terms,target in [('Good morning, Alice.',{'Alice':'Alice'},'Alice'),('The mana crystal is empty.',{'mana crystal':'tinh thạch mana'},'tinh thạch mana')]:
            result=_batch_translate_chunk(Model(),[{'key':'x','source_text':src}],terms)['x']
            self.assertIn(target,result);self.assertNotIn('ZZG',result)
