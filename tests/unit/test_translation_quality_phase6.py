import json
import unittest
import unicodedata
from tests.tools import translation_quality_phase6 as trial
from tests.tools.translation_quality_guard import restore


class SemanticTrialTests(unittest.TestCase):
    def test_fresh_split_and_hash(self):
        self.assertEqual(trial.prior.digest(trial.DATA),trial.DATA_HASH)
        rows=json.loads(trial.DATA.read_text(encoding='utf-8'))['rows']
        norm=lambda s: ''.join(c for c in unicodedata.normalize('NFKC',s).casefold() if c.isalnum())
        new={norm(r['source_en']) for r in rows}
        self.assertEqual(len(new),40)
        for phase in (1,5):
            old=json.loads((trial.ROOT/f'evaluation/translation_quality_phase{phase}/dataset.v1.json').read_text(encoding='utf-8'))['rows']
            self.assertFalse(new & {norm(r['source_en']) for r in old})
        groups={}
        for r in rows: groups.setdefault(r['scenario_boundary']['group_id'],set()).add(r['split'])
        self.assertTrue(all(len(s)==1 for s in groups.values()))
        self.assertEqual(sum(r['split']=='held_out' for r in rows),16)

    def test_directional_role_and_unknown_gender(self):
        self.assertIn('xưng em',trial.role_policy('younger brother to older sister'))
        self.assertIn('xưng chị',trial.role_policy('older sister to younger brother'))
        self.assertIn('giáo sư',trial.role_policy('younger student to older professor; gender unknown'))
        self.assertEqual(trial.role_policy('two strangers'), '')

    def test_source_last_no_answer_or_context_token_leak(self):
        rows=json.loads(trial.DATA.read_text(encoding='utf-8'))['rows']
        row=next(r for r in rows if r['id']=='Q6-13-2')
        prompt,ids,p=trial.make_prompt(row,rows,'roles')
        self.assertTrue(prompt.endswith(p.masked))
        self.assertEqual(ids,['Q6-13-1'])
        self.assertNotIn('{LINE_ID}',prompt)
        self.assertIn('Platform nine',prompt)
        self.assertEqual(restore(p,p.masked),row['source_en'])

    def test_sense_hints_do_not_override_literal_woods_or_global_platform(self):
        row={'source_en':'We walked out of the woods.','group':'idioms','domain_context':'literal outdoor description'}
        self.assertEqual(trial.meaning_hints(row,''),[])
        row['source_en']='The software platform is ready.'
        self.assertEqual(trial.meaning_hints(row,''),[])
        row['domain_context']='software deployment'
        self.assertIn('nền tảng',trial.meaning_hints(row,'')[0])
        row['domain_context']='railway departure display'
        self.assertIn('sân ga',trial.meaning_hints(row,'')[0])

    def test_semantic_diagnostics_do_not_rewrite_or_claim_quality(self):
        row={'source_en':'Keep unresolved entries outside the eligible set.'}
        self.assertIn('POSSIBLE_ADDED_PROHIBITION',trial.semantic_flags(row,'Đừng giữ bản ghi ở ngoài.'))
        self.assertEqual(trial.semantic_flags(row,'Giữ bản ghi bên ngoài.'),[])
        self.assertEqual(trial.semantic_flags({'source_en':'Do not leave.'},'Đừng đi.'),[])
        self.assertIn('YOUNGER_BROTHER_AGE_REVERSAL',trial.semantic_flags({'source_en':'Little brother, listen.'},'Anh trai nhỏ, nghe này.'))
