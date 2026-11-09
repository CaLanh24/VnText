"""Owner regressions: automatic OCR must prove text; controls are not prose."""
import unittest
from unittest.mock import patch
from PIL import Image
from vntext.image_text import _corroborated_line
from vntext.mt_classify import classify_row_authoritative


class OwnerQualityBatchTests(unittest.TestCase):
    def test_runtime_controls_are_skipped_even_in_review_or_already_translated(self):
        for source in ('Achievement2', '%b %d, %Y @ %I:%M %p{#achievement_timestamp}',
                       '[a.stat_progress]/[a.stat_max]', '[config.name!t]', '<', '>',
                       '{#quick_page}Q', '{#auto_page}A', '[page]'):
            for translated in ('', 'Old automatic translation'):
                with self.subTest(source=source, translated=translated):
                    action, _, decision = classify_row_authoritative(dict(
                        source_text=source, translation=translated,
                        import_method='renpy_screen_candidate', review_only=True))
                    self.assertEqual(action, 'skip_technical')
                    self.assertEqual(decision.ledger, 'technical_skipped')

    def test_human_labels_and_sentences_are_not_discarded(self):
        for source in ('Mute All', 'Achievement unlocked', 'Achievement 2',
                       'Hello [name]!', 'Page [page]', '{#menu}Save game'):
            action, _, _ = classify_row_authoritative(dict(source_text=source, import_method='renpy_string'))
            self.assertNotEqual(action, 'skip_technical', source)

    def test_photo_fragment_without_crop_consensus_is_not_text(self):
        image = Image.new('RGB', (200, 100))
        line = dict(text='•ell', words=[dict(text='•ell', x=10, y=10, width=100, height=40)])
        with patch('vntext.image_text._windows_ocr', return_value={'lines': []}):
            self.assertFalse(_corroborated_line(image, line))
        # A substring in another line is not sufficient confirmation.
        with patch('vntext.image_text._windows_ocr', return_value={'lines': [{'text': 'hello'}]}):
            self.assertFalse(_corroborated_line(image, line))

    def test_short_labels_names_and_unknown_words_survive_consensus(self):
        image = Image.new('RGB', (200, 100))
        for text in ('OK', 'Save', 'Xylophoria', 'OPTIONS', 'New game'):
            line = dict(text=text, words=[dict(text=text, x=10, y=10, width=150, height=35)])
            with patch('vntext.image_text._windows_ocr', return_value={'lines': [{'text': text}]}):
                self.assertTrue(_corroborated_line(image, line), text)


if __name__ == '__main__':
    unittest.main()
