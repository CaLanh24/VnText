import json
import unittest
from tests.tools import translation_quality_phase15 as t

class ClosurePromptTests(unittest.TestCase):
    def test_source_derived_owner_and_technical_words(self):
        row=dict(source_en='May I send you my corrected table tomorrow morning?',address_context='younger student to older professor; gender unknown')
        prompt,_,_=t.translation_prompt(row,'',[])
        self.assertIn('my = của em',prompt)
        self.assertIn('table = bảng',prompt)
        self.assertTrue(prompt.rstrip().endswith(row['source_en']))
        prompt,_,_=t.translation_prompt(dict(source_en='Aborting the import must leave the saved snapshot intact.'),'',[])
        self.assertIn('snapshot = bản chụp trạng thái',prompt)
        self.assertNotIn('my =',prompt)
    def test_stopping_not_completion_cue(self):
        prompt,_,_=t.translation_prompt(dict(source_en='Do not erase the recovery folder after stopping the upload.'),'',[])
        self.assertIn('stopping = dừng',prompt)
        self.assertIn('not successful completion',prompt)
    def test_corpus_identity(self):
        rows=json.loads(t.DATA.read_text(encoding='utf-8'))['rows']
        self.assertEqual(len(rows),40)
        self.assertEqual(len({r['id']for r in rows}),40)
        new={r['source_en']for r in rows[28:]};self.assertEqual(len(new),12)
        for phase in (1,5,6,7,8,9,10,11,12,13,14):
            old=json.loads((t.ROOT/f'evaluation/translation_quality_phase{phase}/dataset.v1.json').read_text(encoding='utf-8'))['rows']
            self.assertFalse(new&{r['source_en']for r in old})
        self.assertEqual(t.natural.prior.digest(t.DATA),t.DATA_HASH)
        self.assertEqual(t.natural.prior.digest(t.FIXTURES),t.FIXTURES_HASH)
