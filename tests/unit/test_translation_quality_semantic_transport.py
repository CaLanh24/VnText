import unittest
from tests.tools.translation_quality_semantic_transport import mask_roles,restore_roles,paraphrase_logic,relationship_contradictions


class SemanticTransportTests(unittest.TestCase):
    def test_explicit_relation_contradiction_not_incidental_kinship(self):
        self.assertTrue(relationship_contradictions('older sister to younger brother','Chị là em gái của em.'))
        self.assertFalse(relationship_contradictions('older sister to younger brother','Chị sẽ gặp em gái của cô ấy.'))
        self.assertFalse(relationship_contradictions('strangers','Chị là em gái của em.'))

    def test_directional_roles_and_exact_occurrences(self):
        r=mask_roles('I will lend you my ruler.','older sister to younger brother')
        self.assertEqual([v for _,v in r.replacements],['chị','em','chị'])
        text=f'{r.replacements[0][0]} sẽ cho {r.replacements[1][0]} mượn thước của {r.replacements[2][0]}.'
        self.assertEqual(restore_roles(r,text),'chị sẽ cho em mượn thước của chị.')
        for bad in (text.replace(r.replacements[1][0],''),text+' '+r.replacements[0][0],text.replace('sẽ','tôi sẽ'),text.replace('ROLEVNT001X','ROLEVNT 001X')):
            with self.assertRaises(ValueError):restore_roles(r,bad)

    def test_no_guess_or_embedded_word_masking(self):
        for source,metadata in [('Yourself and young people.','strangers'),('Yourself and young people.','mother to daughter'),('"I am you," she said.','mother to daughter'),("You're ready.",'mother to daughter')]:
            self.assertEqual(mask_roles(source,metadata).text,source)
        r=mask_roles('I ask you.','younger student to older professor; gender unknown')
        self.assertEqual([v for _,v in r.replacements],['em','giáo sư'])
        r=mask_roles('I ask you.','younger brother to older sister')
        self.assertEqual([v for _,v in r.replacements],['em','chị'])
        with self.assertRaises(ValueError):mask_roles('ROLEVNT000X','unknown')

    def test_unless_truth_table_and_negative_controls(self):
        self.assertEqual(paraphrase_logic('Unless its signature is valid, reject it.'),('If its signature is not valid, reject it.','unless_copula'))
        self.assertEqual(paraphrase_logic('Unless the user confirms, keep the file.'),('If the user does not confirm, keep the file.','unless_confirmation'))
        for text in ('Unless it is not valid, accept it.','Do not delete unless I agree.','Only valid files may pass.','Unless the user never confirms, stop.'):
            self.assertEqual(paraphrase_logic(text),(text,None))
