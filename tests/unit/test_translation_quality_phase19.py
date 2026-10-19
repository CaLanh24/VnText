import json
import collections
import unicodedata
import unittest
from tests.tools import translation_quality_phase19 as t

class BroadBlindEvaluationTests(unittest.TestCase):
    def test_dataset_and_frozen_pipeline(self):
        rows=json.loads(t.DATA.read_text(encoding='utf-8'))['rows']
        self.assertEqual(len(rows),60);self.assertEqual(len({r['id']for r in rows}),60)
        self.assertEqual(set(collections.Counter(r['group']for r in rows).values()),{10})
        self.assertEqual(collections.Counter(r['split']for r in rows),{'development':42,'heldout':18})
        norm=lambda s:''.join(c for c in unicodedata.normalize('NFKC',s).casefold()if c.isalnum())
        new={norm(r['source_en'])for r in rows};self.assertEqual(len(new),60)
        for phase in (1,5,6,7,8,9,10,11,12,13,14,15,16,17,18):
            old=json.loads((t.ROOT/f'evaluation/translation_quality_phase{phase}/dataset.v1.json').read_text(encoding='utf-8'))['rows']
            self.assertFalse(new&{norm(r['source_en'])for r in old})
        self.assertIs(t.constrained_pipeline,t.frozen.constrained_pipeline)
        self.assertIs(t.translation_prompt,t.frozen.translation_prompt)
        self.assertIs(t.TERMS,t.frozen.TERMS)
        self.assertEqual(t.natural.prior.digest(t.DATA),t.DATA_HASH)
    def test_blinding_exactness_and_reproducibility(self):
        rows=json.loads(t.DATA.read_text(encoding='utf-8'))['rows'][:5]
        c=dict(rows=[dict(id=r['id'],draft='candidate-'+r['id'])for r in rows])
        b=dict(rows=[dict(id=r['id'],output='opus-'+r['id'])for r in rows])
        pack,mapping=t.blind_pack(c,b);self.assertEqual((pack,mapping),t.blind_pack(c,b))
        for r in pack:
            self.assertEqual(set(r),{'id','source_en','domain_context','address_context','A','B'})
            for label in ('A','B'):
                prefix='candidate-'if mapping[r['id']][label]=='candidate'else'opus-'
                self.assertEqual(r[label],prefix+r['id'])
