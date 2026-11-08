"""A single editable CSV retains review translations without forging a writer proof."""
import hashlib
import json
import unittest

from tests.lib.work_paths import work_temp_dir
from vntext.entry import Entry
from vntext.package_io import write_package, read_csv_rows_file
from vntext.csv_editor_api import load_document, save_document
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
        self.assertIn(entry.key, result['issues_by_key'])

