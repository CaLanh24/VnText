import json
import unittest
from tests.tools import translation_quality_phase14 as t


class MixedReplayTests(unittest.TestCase):
    def test_replay_exact_sources_and_frozen_pipeline(self):
        rows=json.loads(t.DATA.read_text(encoding='utf-8'))['rows']
        prior=[]
        for phase in (8,13):prior+=json.loads((t.ROOT/f'evaluation/translation_quality_phase{phase}/dataset.v1.json').read_text(encoding='utf-8'))['rows']
        self.assertEqual(rows,prior)
        self.assertEqual(len(rows),28)
        self.assertEqual(len({r['id'] for r in rows}),28)
        self.assertIs(t.constrained_pipeline,t.frozen.constrained_pipeline)
        self.assertEqual(t.TERMS,t.frozen.TERMS)
        self.assertEqual(t.natural.prior.digest(t.DATA),t.DATA_HASH)
        self.assertEqual(t.natural.prior.digest(t.FIXTURES),t.FIXTURES_HASH)
