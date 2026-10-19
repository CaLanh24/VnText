import json
import unittest
from tests.tools import translation_quality_phase17 as t

class CompoundPrecisionTests(unittest.TestCase):
    def test_file_specificity_and_verification(self):
        source='The file transfer must wait until the backup is verified.'
        prompt,_,_=t.translation_prompt(dict(source_en=source,domain_context='software integrity'),'',[])
        self.assertIn('file transfer = truyền tệp',prompt)
        self.assertIn('Preserve the file noun',prompt)
        self.assertNotIn('Here transfer means transmission of data',prompt)
        self.assertIn('not merely confirmed',prompt)
        self.assertTrue(prompt.rstrip().endswith(source))
        prompt,_,_=t.translation_prompt(dict(source_en='Confirm the transfer.',domain_context='banking and financial payments'),'',[])
        self.assertNotIn('Preserve the file noun',prompt)
        self.assertNotIn('Verified means',prompt)
        self.assertNotIn('Here transfer means transmission of data',prompt)
    def test_corpus_identity(self):
        rows=json.loads(t.DATA.read_text(encoding='utf-8'))['rows'];self.assertEqual(len(rows),52)
        self.assertEqual(len({r['id']for r in rows}),52)
        new={r['source_en']for r in rows[48:]};self.assertEqual(len(new),4)
        for phase in (1,5,6,7,8,9,10,11,12,13,14,15,16):
            old=json.loads((t.ROOT/f'evaluation/translation_quality_phase{phase}/dataset.v1.json').read_text(encoding='utf-8'))['rows']
            self.assertFalse(new&{r['source_en']for r in old})
        self.assertEqual(t.natural.prior.digest(t.DATA),t.DATA_HASH)
