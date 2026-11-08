"""A single editable CSV retains review translations without forging a writer proof."""
import hashlib
import json
import unittest

from tests.lib.work_paths import work_temp_dir
from vntext.entry import Entry
from vntext.package_io import write_package, read_csv_rows_file
from vntext.csv_editor_api import load_document, save_document, validate_document
from vntext.patch_gate import load_review_only_keys
from vntext.mt_ct2_status import _load_human_review_keys, _count_review_only_rows


class UnifiedDocumentTests(unittest.TestCase):
    def test_review_edit_persists_in_only_csv_and_stays_guarded(self):
        root = work_temp_dir('unified-document')
        entry = Entry('A short label', 'game/ui.rpy', 'screen', import_method='renpy_screen_candidate', review_only=True).finalize()
        write_package(str(root), [], [entry], {}, False, enforce_symmetry=True)
        path = root / 'translation.csv'
        self.assertEqual([p.name for p in root.glob('*.csv')], ['translation.csv'])
        document = load_document(path)
        self.assertEqual(document['review_keys'], [entry.key])
        document['rows'][0]['translation'] = 'Một nhãn ngắn'
        result = save_document(path, document['fields'], document['rows'], expected_sha256=document['source_sha256'])
        self.assertTrue(result['ok'], result)
        self.assertEqual(read_csv_rows_file(path)[1][0]['translation'], 'Một nhãn ngắn')
        self.assertEqual(load_review_only_keys(root), {entry.key})
        self.assertEqual(_load_human_review_keys(root), {entry.key})
        self.assertEqual(_count_review_only_rows(root), 1)
        # the saved translation never gains patch eligibility: validation still blocks it as review-only
        self.assertIn(entry.key, validate_document(path)['issues_by_key'])

class ImageOnlyPackageTests(unittest.TestCase):
    def _run(self, images):
        from unittest.mock import patch
        from vntext_worker import task_runners
        root = work_temp_dir('image-only-package')
        write_package(str(root), [], [], {}, False, enforce_symmetry=True)         # no text rows at all
        completed = []
        with patch('vntext.image_batch.cached_image_report', return_value={'status': 'COMPLETE'}),              patch('vntext.image_batch.translate_cached_images', return_value=images) as images_call,              patch('vntext_worker.task_runners.emit_complete', side_effect=lambda task, **kw: completed.append(kw)),              patch('vntext_worker.task_runners.run_translate_ct2_task', side_effect=AssertionError('the text translator must not run on an image-only package')):
            task_runners.run_translate_worker('t1', {'csv_path': str(root / 'translation.csv')}, lambda: False)
        return completed, images_call

    def test_image_only_package_reaches_the_image_translation(self):
        completed, images_call = self._run({'translated': 3, 'untranslated': 0, 'total': 3, 'output': 'images/translated', 'cancelled': False})
        images_call.assert_called_once()
        self.assertTrue(completed[-1]['ok'], completed)
        self.assertIn('3/3', completed[-1]['summary'])

    def test_image_only_package_reports_untranslated_images_as_not_complete(self):
        completed, _ = self._run({'translated': 1, 'untranslated': 2, 'total': 3, 'output': 'images/translated', 'cancelled': False})
        self.assertFalse(completed[-1]['ok'], completed)
        self.assertFalse(completed[-1].get('complete', True))
