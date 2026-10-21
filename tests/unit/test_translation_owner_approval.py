import copy
import unittest
from tests.tools import translation_owner_approval as approval


class DelegatedApprovalTests(unittest.TestCase):
    def setUp(self):
        self.decision=approval.original.load(approval.DEST/'decision.json')

    def test_mapping_and_original_packet_remain_distinct(self):
        approval.verify()

    def test_delegation_cannot_become_human_gold_or_training_permission(self):
        for field in ('human_gold','training_authorized','direct_human_linguistic_review','whole_app_accepted'):
            forged=copy.deepcopy(self.decision);forged[field]=True
            with self.subTest(field=field),self.assertRaises(AssertionError):approval.validate(forged)

    def test_no_extra_or_unreviewed_changed_targets(self):
        for mutation in ('target','extra'):
            forged=copy.deepcopy(self.decision)
            if mutation=='target':forged['translations'][0]['translation']='Different unreviewed wording'
            else:forged['translations'].append(copy.deepcopy(forged['translations'][0]))
            with self.subTest(mutation=mutation),self.assertRaises(AssertionError):approval.validate(forged)

    def test_approval_cannot_broaden_scene_or_glossary_occurrences(self):
        forged=copy.deepcopy(self.decision);forged['translations'][0]['approval_scope']['package']='ALL'
        with self.assertRaises(AssertionError):approval.validate(forged)
        forged=copy.deepcopy(self.decision);forged['glossary'][0]['occurrence_ids']=['ALL']
        with self.assertRaises(AssertionError):approval.validate(forged)


if __name__=='__main__':unittest.main()
