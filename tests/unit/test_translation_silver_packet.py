"""Offline provenance and positive-reuse safety; no models or network."""
import shutil
import unittest
from tests.lib.work_paths import work_temp_dir
from tests.tools import translation_silver_packet as p


class SilverPacketTests(unittest.TestCase):
    def test_public_packet_verifies_without_ignored_originals(self):
        report=p.verify(p.PACKET)
        self.assertEqual(report['counts'],dict(sources=60,audited_rows=12,terms=48,candidate_terms=3,memory=9))
        self.assertFalse(report['human_gold'])

    def test_payload_tamper_rejected(self):
        root=work_temp_dir('silver-packet-hash-tamper')/'packet'
        shutil.copytree(p.PACKET,root)
        with (root/'memory-candidate.json').open('a',encoding='utf-8') as handle:
            handle.write(' ')
        with self.assertRaisesRegex(AssertionError,'content hash mismatch'):
            p.verify(root)

    def test_rehashed_unsafe_memory_still_rejected(self):
        root=work_temp_dir('silver-packet-policy-tamper')/'packet'
        shutil.copytree(p.PACKET,root)
        file=root/'memory-candidate.json'; memory=p.read(file)
        memory['records'][0]['approved']=True
        p.write(file,memory)
        manifest=p.read(root/'manifest.json')
        manifest['files']['memory-candidate.json']=p.sha(file)
        p.write(root/'manifest.json',manifest)
        with self.assertRaisesRegex(AssertionError,'policy mismatch'):
            p.verify(root)

    def test_original_grades_and_adjustments_remain_separate(self):
        rows={r['id']:r for r in p.read(p.PACKET/'curation.json')['rows']}
        item=rows['Q19-ui-08']
        self.assertEqual(item['original_blind_review']['A']['verdict'],'minor')
        self.assertEqual(item['audited_verdicts']['opus_glossary'],'major')
        self.assertEqual(item['original_blind_review']['winner'],'A')
        self.assertFalse(item['memory_eligible'])
        self.assertFalse(rows['Q19-ui-04']['memory_eligible'])
        self.assertTrue(rows['Q19-ui-04']['current_conservative_exclusion'])
        self.assertFalse(rows['Q19-dialogue-06']['memory_eligible'])
        self.assertEqual(set(rows['Q19-dialogue-06']['audited_verdicts'].values()),{'acceptable'})
        self.assertEqual(rows['Q19-dialogue-06']['source'].get('address_context',''),'')
        self.assertNotIn('Q19-dialogue-06',[r['id'] for r in p.read(p.PACKET/'memory-candidate.json')['records']])
        self.assertEqual(rows['Q19-protected_tokens-02']['outputs']['opus_glossary']['output'],'')
