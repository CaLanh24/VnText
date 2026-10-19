import unittest
from tests.tools import translation_quality_phase20 as t
from tests.tools import translation_quality_phase18 as old

class SemanticHintTests(unittest.TestCase):
    def test_six_classes_and_controls(self):
        pairs=[('I would have waited if I had seen him.','conversation'),('Bring the coat I gave you.','conversation'),('Continue without discarding the draft.','desktop interface'),('A transaction can roll back.','database transactions'),('Read the invoice.','business'),('Read the sensor.','engineering')]
        for source,domain in pairs:
            self.assertTrue(t.semantic_hints(dict(source_en=source,domain_context=domain)))
        for source,domain in [('I will wait if I see him.','conversation'),('Bring the coat you gave me.','conversation'),('Continue without skipping the draft.','desktop interface'),('Roll back the carpet.','house'),('Read the receipt.','business'),('Read the switch.','engineering')]:
            self.assertFalse(t.semantic_hints(dict(source_en=source,domain_context=domain)))
    def test_unaffected_prompt_and_checker_identity(self):
        row=dict(id='control',source_en='Close the window.',domain_context='desktop interface',address_context='')
        self.assertEqual(t.translation_prompt(row,'',[]),old.translation_prompt(row,'',[]))
        self.assertIs(t.constraints,old.constraints)
        self.assertEqual(t.TERMS,old.TERMS)

    def test_frozen_fresh_corpus(self):
        import json
        rows=json.loads(t.DATA.read_text(encoding='utf-8'))['rows']
        self.assertEqual(len(rows),12)
        self.assertEqual(len({r['id'] for r in rows}),12)
        self.assertEqual(t.natural.prior.digest(t.DATA),t.DATA_HASH)
        oldrows=json.loads((t.ROOT/'evaluation/translation_quality_phase19/dataset.v1.json').read_text(encoding='utf-8'))['rows']
        self.assertFalse({r['source_en'] for r in rows}&{r['source_en'] for r in oldrows})
