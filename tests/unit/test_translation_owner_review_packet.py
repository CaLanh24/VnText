"""Review-packet provenance/scope checks do not grant semantic acceptance."""
import copy
import unittest
from tests.tools import translation_owner_review_packet as packet


class OwnerReviewPacketTests(unittest.TestCase):
    def setUp(self):
        self.payload=packet.load(packet.DEST/'proposals.json')
        self.dataset=packet.load(packet.DATASET)

    def test_original_packet_provenance_and_pending_state(self):
        packet.verify()

    def test_review_preparation_cannot_forge_approval_or_gold(self):
        for field in ('approved','human_gold','training_eligible'):
            forged=copy.deepcopy(self.payload)
            forged['translations'][0][field]=True
            with self.subTest(field=field),self.assertRaises(AssertionError):
                packet.validate_payload(forged,self.dataset)

    def test_cross_scene_context_or_broadened_scope_is_rejected(self):
        for field,value in [('intended_scope',{'package':'ALL PROJECTS'}),
                            ('same_scenario_sources',[{'id':'ADDR-014','source':'wrong scene'}]),
                            ('address_context','A man speaks to a woman.')]:
            forged=copy.deepcopy(self.payload)
            forged['translations'][0][field]=value
            with self.subTest(field=field),self.assertRaises(AssertionError):
                packet.validate_payload(forged,self.dataset)

    def test_glossary_wording_does_not_contradict_proposed_full_sentence(self):
        from vntext.glossary_v2 import candidate_term_issues
        glossary={'entries':[dict(source=t['source'],target=t['proposed_target'])
                             for t in self.payload['glossary']]}
        for row in self.payload['translations']:
            self.assertEqual(candidate_term_issues(row['source'],{},row['proposed_translation'],glossary),[],row['id'])
        # Checking wording is not a semantic oracle; proposals remain unapproved.
        self.assertTrue(all(not row['approved'] for row in self.payload['translations']))


if __name__=='__main__':
    unittest.main()
