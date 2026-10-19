import json
import unittest
from tests.tools import translation_quality_phase16 as t

class ResidualPrecisionTests(unittest.TestCase):
    def test_domain_transfer_boundary(self):
        source='Canceling this transfer must preserve the backup.'
        prompt,_,_=t.translation_prompt(dict(source_en=source,domain_context='software integrity'),'',[])
        self.assertIn('transfer means transmission of data',prompt)
        for domain in ('legal ownership of a house','banking and financial payments','conversation',''):
            prompt,_,_=t.translation_prompt(dict(source_en=source,domain_context=domain),'',[])
            self.assertNotIn('transfer means transmission of data',prompt)
    def test_rollback_and_contiguous_eligibility(self):
        prompt,_,_=t.translation_prompt(dict(source_en='Cancel the migration without removing its rollback data.'),'',[])
        self.assertIn('not data generated during rollback',prompt)
        self.assertIn('rollback data = dữ liệu hoàn tác',prompt)
        source='Keep unresolved records outside the collection permitted for patching.'
        prompt,_,_=t.translation_prompt(dict(source_en=source),'',[])
        self.assertIn('Do not separate it by a comma',prompt)
        self.assertTrue(prompt.rstrip().endswith(source))
    def test_corpus_identity(self):
        rows=json.loads(t.DATA.read_text(encoding='utf-8'))['rows'];self.assertEqual(len(rows),48)
        self.assertEqual(len({r['id']for r in rows}),48)
        new={r['source_en']for r in rows[40:]};self.assertEqual(len(new),8)
        for phase in (1,5,6,7,8,9,10,11,12,13,14,15):
            old=json.loads((t.ROOT/f'evaluation/translation_quality_phase{phase}/dataset.v1.json').read_text(encoding='utf-8'))['rows']
            self.assertFalse(new&{r['source_en']for r in old})
        self.assertEqual(t.natural.prior.digest(t.DATA),t.DATA_HASH)
