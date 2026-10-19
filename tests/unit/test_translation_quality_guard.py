"""Adversarial transport gates, independent of a translation model."""
import json
from pathlib import Path
import random
import unittest
import unicodedata

from tests.tools.translation_quality_guard import protect, restore, opaque_tokens, sanitize_context
from tests.tools.translation_quality_phase5 import make_prompt


class GuardTests(unittest.TestCase):
    def test_occurrences_distinct_exact_restore_and_visible_tag_body(self):
        source = '{NAME} sees <b><i>amber light</i></b>; {NAME} keeps ♡.\\n%s %02d'
        p = protect(source)
        self.assertEqual(len(set(p.markers)), len(p.markers))
        self.assertIn('amber light', p.masked)
        self.assertNotIn('{NAME}', p.masked)
        translated = p.masked.replace(' sees ', ' thấy ').replace('amber light', 'ánh sáng hổ phách').replace(' keeps ', ' giữ ')
        output = restore(p, translated)
        self.assertIn('<b><i>ánh sáng hổ phách</i></b>', output)
        self.assertEqual(opaque_tokens(output), opaque_tokens(source))

    def test_foreign_missing_duplicate_reordered_and_deformed_markers_reject(self):
        p = protect('{A} near {B}.')
        for candidate in ('[VNT000] gần [VNT999].', '[VNT000] gần.',
                          '[VNT000] [VNT000] [VNT001]', '[VNT001] gần [VNT000]',
                          '[VNT 000] gần [VNT001]', '[VNT000] gần [VNT001] [VNTX]'):
            with self.subTest(candidate=candidate), self.assertRaises(ValueError):
                restore(p, candidate)

    def test_raw_context_placeholder_or_escape_injection_rejects(self):
        p = protect('{ALLY_NAME} wins.')
        for candidate in ('[VNT000] thắng {PLAYER}.', '[VNT000] thắng.\\n',
                          '[VNT000] thắng.\nThêm', '[VNT000] thắng <b>nữa</b>.'):
            with self.subTest(candidate=candidate), self.assertRaises(ValueError):
                restore(p, candidate)

    def test_context_redaction_removes_target_like_tokens_but_keeps_prose(self):
        text = '{PLAYER} chose <b>amber door</b>.\\nThen [accept] beside ♡.'
        redacted = sanitize_context(text)
        self.assertEqual(opaque_tokens(redacted), [])
        self.assertIn('amber door', redacted)
        self.assertNotIn('PLAYER', redacted)

    def test_source_collision_fails_closed(self):
        with self.assertRaises(ValueError):
            protect('A literal [VNT000] already exists.')

    def test_leading_controls_and_percentage_are_not_trimmed(self):
        source = '\n{SPEAKER}: Ready\\tNow\r\n75% complete.'
        p = protect(source)
        result = restore(p, p.masked.replace('Ready', 'Sẵn sàng').replace('Now', 'Bây giờ'))
        self.assertTrue(result.startswith('\n{SPEAKER}'))
        self.assertEqual(opaque_tokens(source), opaque_tokens(result))

    def test_randomized_mixed_tokens_no_mutation_or_collision(self):
        rng = random.Random(1705)
        tokens = ['{A}', '${b}', '<b>', '</b>', '[pause=0.7]', '#Route7', '*SIGH*', '♡', '\\n', '\t', '%1$s', '50%']
        for _ in range(100):
            source = 'word '.join(rng.choices(tokens, k=12))
            p = protect(source)
            self.assertEqual(restore(p, p.masked), source)

    def test_new_dataset_unique_against_seen_set_and_group_splits(self):
        root = Path(__file__).resolve().parents[2]
        new = json.loads((root/'evaluation/translation_quality_phase5/dataset.v1.json').read_text(encoding='utf-8'))['rows']
        old = json.loads((root/'evaluation/translation_quality_phase1/dataset.v1.json').read_text(encoding='utf-8'))['rows']
        norm = lambda s: ''.join(c for c in unicodedata.normalize('NFKC', s).casefold() if c.isalnum())
        self.assertEqual(len(new), 60)
        self.assertEqual(sum(r['split']=='development' for r in new), 40)
        self.assertEqual(len({norm(r['source_en']) for r in new}), 60)
        self.assertFalse({norm(r['source_en']) for r in new} & {norm(r['source_en']) for r in old})
        groups = {}
        for row in new:
            groups.setdefault(row['scenario_boundary']['group_id'], set()).add(row['split'])
        self.assertTrue(all(len(splits)==1 for splits in groups.values()))

    def test_actual_prompt_hides_both_source_and_context_identities(self):
        root = Path(__file__).resolve().parents[2]
        rows = json.loads((root/'evaluation/translation_quality_phase1/dataset.v1.json').read_text(encoding='utf-8'))['rows']
        row = next(r for r in rows if r['id']=='TOK-008')
        prompt, ids, protected = make_prompt(row, rows, 'semantic')
        self.assertEqual(ids, ['TOK-007'])
        self.assertNotIn('PLAYER', prompt)
        self.assertNotIn('ALLY_NAME', prompt)
        self.assertTrue(prompt.endswith(protected.masked))
        self.assertEqual(protected.tokens, ('♡', '{ALLY_NAME}'))

    def test_technical_glossary_does_not_mask_visible_words_or_match_substrings(self):
        row = {'id':'test', 'group':'terminology', 'split':'development', 'source_en':'The journal contains a cachet.',
               'scenario_boundary':{'file_id':'test','group_id':'test','engine':'synthetic','kind':'standalone_line','turn':1}}
        prompt, _, protected = make_prompt(row, [row], 'semantic')
        self.assertIn('journal translates to nhật ký', prompt)
        self.assertNotIn('cache translates to', prompt)
        self.assertEqual(protected.masked, row['source_en'])


if __name__ == '__main__':
    unittest.main()
