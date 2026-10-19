import json
import unittest
from tests.tools import translation_quality_phase18 as t
from tests.tools import translation_quality_phase17 as old

class ContractDomainTests(unittest.TestCase):
    def test_only_house_contract_changes_old_prompts(self):
        rows=json.loads(old.DATA.read_text(encoding='utf-8'))['rows']
        changed=[]
        for r in rows:
            before=old.translation_prompt(r,'',[])[0];after=t.translation_prompt(r,'',[])[0]
            if before!=after:changed.append(r['id'])
        self.assertEqual(changed,['Q17-04-1'])
        source='The contract is valid.'
        for domain in ('programming function contract','international treaty negotiations','conversation',''):
            r=dict(source_en=source,domain_context=domain)
            self.assertEqual(old.translation_prompt(r,'',[])[0],t.translation_prompt(r,'',[])[0])
    def test_corpus_identity_and_unique_sources(self):
        rows=json.loads(t.DATA.read_text(encoding='utf-8'))['rows'];self.assertEqual(len(rows),17)
        self.assertEqual(len({r['id']for r in rows}),17)
        new={r['source_en']for r in rows[-4:]};self.assertEqual(len(new),4)
        for phase in (1,5,6,7,8,9,10,11,12,13,14,15,16,17):
            oldrows=json.loads((t.ROOT/f'evaluation/translation_quality_phase{phase}/dataset.v1.json').read_text(encoding='utf-8'))['rows']
            self.assertFalse(new&{r['source_en']for r in oldrows})
        self.assertEqual(t.natural.prior.digest(t.DATA),t.DATA_HASH)
