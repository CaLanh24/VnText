"""QA disposition is independent of permissive legacy keep routing."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / 'tests/tools'), str(ROOT)]
from audit_saved_identities import disposition


class IdentityDispositionTests(unittest.TestCase):
    def test_sound_does_not_excuse_lexical_prose(self):
        for source in ('Thirsty... *gulp*', '*rough breathing*', '(LOCKED)', 'Ek... Hey!'):
            with self.subTest(source=source):
                verdict, _ = disposition({'source_text': source, 'context': 'Script:dialogue'})
                self.assertNotEqual(verdict, 'VALID_KEEP')

    def test_nonlexical_vocalization_and_brand_keep(self):
        for source in ('Ah...! Nnh...', 'Subscribestar', '*chup*'):
            with self.subTest(source=source):
                self.assertEqual(disposition({'source_text': source, 'context': 'Script:dialogue'})[0], 'VALID_KEEP')

        # Lexical stage directions use the generic protected-span fallback even
        # when CT2 echoes the source; tags and star delimiters remain intact.
        from vntext.mt_translation_safety import postprocess
        self.assertEqual(postprocess('*humming*', '*humming*'), '*ngân nga*')
        self.assertEqual(
            postprocess('<color=orange>*Gasp breathing*</color>', '<color=orange>*Gasp breathing*</color>'),
            '<color=orange>*thở gấp thở*</color>',
        )
