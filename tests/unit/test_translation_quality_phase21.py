import json
import unittest
from tests.tools import translation_quality_phase21 as t
from tests.tools import translation_quality_phase20 as old

class HarnessTests(unittest.TestCase):
    def test_frozen_corpus_and_unchanged_route(self):
        rows=json.loads(t.DATA.read_text(encoding='utf-8'))['rows']
        self.assertEqual(len(rows),16);self.assertEqual(len({r['id'] for r in rows}),16)
        self.assertEqual(t.natural.prior.digest(t.DATA),t.DATA_HASH)
        self.assertEqual(t.TERMS,old.TERMS);self.assertIs(t.constraints,old.constraints)
    def test_unaffected_prompt_and_draft_status(self):
        r=dict(id='control',source_en='Close the window.',domain_context='desktop interface',address_context='',group='test',split='development')
        self.assertEqual(t.translation_prompt(r,'',[])[0],old.translation_prompt(r,'',[])[0])
        out=t.constrained_pipeline(r,lambda prompt,label:'Đóng cửa sổ.')
        self.assertEqual(out['status'],'NEEDS_REVIEW');self.assertEqual(out['output'],'')
    def test_protected_carrier_pipeline(self):
        r=dict(id='test',source_en='The sensor sends {VALUE}.',domain_context='engineering measurement',address_context='',group='test',split='development')
        prompt,bundle,_=t.translation_prompt(r,'',[])
        p=bundle[1]
        out=t.constrained_pipeline(r,lambda prompt,label:p.masked)
        self.assertEqual(out['status'],'NEEDS_REVIEW');self.assertEqual(out['output'],'')
        self.assertIn('{VALUE}',out['draft']);self.assertIn('cảm biến',out['draft'])
