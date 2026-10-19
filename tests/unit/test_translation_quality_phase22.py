import unittest
from tests.tools import translation_quality_phase22 as t
from tests.tools import translation_lexical_transport_v2 as lex
from tests.tools import translation_alternative_constraints as c
from tests.tools.translation_quality_guard import protect

class CompositionTests(unittest.TestCase):
    def row(self,s,domain='database transactions'):
        return dict(source_en=s,domain_context=domain)
    def test_alternative_polarity_and_abstention(self):
        r=self.row('The model predicts whether the transaction will finish or roll back.')
        for d in ['Mô hình dự đoán liệu giao dịch có sẽ hoàn thành hay không hoặc hoàn tác.','Mô hình dự đoán liệu giao dịch sẽ hoàn tất hay không hoàn tác.','Mô hình dự đoán liệu giao dịch sẽ hoàn tất hoặc chưa hoàn tác.']:
            self.assertEqual(c.audit_constraints(r,d)['status'],'FAIL')
        self.assertEqual(c.audit_constraints(r,'Mô hình dự đoán liệu giao dịch sẽ hoàn tất hoặc hoàn tác.')['status'],'CONSTRAINTS_MATCH')
        self.assertIsNone(c.source_contract(self.row('The model predicts whether the transaction will finish or not roll back.')))
        self.assertIsNone(c.source_contract(self.row('She said "finish or roll back".')))
    def test_bundle_and_reject_damage(self):
        r=lex.prepare(self.row('The sensor and safety switch share <b>{CIRCUIT}</b>.','engineering control'))
        p=protect(r.working_source)
        self.assertEqual(len(p.markers),3)
        self.assertIn('<b>{CIRCUIT}</b>',lex.restore(r,p,p.masked))
        with self.assertRaises(ValueError):lex.restore(r,p,p.masked.replace('[VNT','[TVNT'))
        with self.assertRaises(ValueError):lex.prepare(self.row('Read [BND000].'))
    def test_normal_text_inside_tags_is_not_bundled(self):
        r=lex.prepare(self.row('<b>ordinary words</b>','conversation'))
        self.assertEqual(r.working_source,'<b>ordinary words</b>')
    def test_physical_roll_and_tense_boundary(self):
        r=lex.prepare(self.row('Roll back the rug.','household furniture'))
        self.assertIn('cuộn lại',str(r.bindings))
        r=lex.prepare(self.row('I would have saved it if I had noticed you.','conversation'));p=protect(r.working_source)
        d=lex.restore(r,p,p.masked.replace('saved','đã lưu'))
        self.assertNotIn('đã đã',d)
        for s in ['I would have a car if I had money.','I would have called if I had your number.']:
            self.assertFalse(lex.prepare(self.row(s,'conversation')).bindings)

    def test_possession_prompt_has_no_past_directive(self):
        r=dict(id='scope',source_en='I would have a car if I had money.',domain_context='conversation',address_context='')
        self.assertNotIn('unreal condition in the past',t.translation_prompt(r,'',[])[0])

    def test_frozen_corpus(self):
        import json
        rows=json.loads(t.DATA.read_text(encoding='utf-8'))['rows']
        self.assertEqual(len(rows),12);self.assertEqual(len({r['id'] for r in rows}),12)
        self.assertEqual(t.natural.prior.digest(t.DATA),t.DATA_HASH)
