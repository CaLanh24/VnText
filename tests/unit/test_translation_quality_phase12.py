import json
import unicodedata
import unittest
from tests.tools import translation_quality_phase12 as t


class TargetedRemediationTests(unittest.TestCase):
    def test_wrong_prohibition_revision_becomes_selected_match(self):
        row=dict(id='X',source_en='Keep unverified records outside the set eligible for release.',group='logic',split='development')
        responses=iter(['Đừng giữ bản ghi chưa xác minh ngoài danh sách có thể được phát hành.',
                        'Giữ bản ghi chưa xác minh ngoài danh sách có thể được phát hành.'])
        r=t.constrained_pipeline(row,lambda *_:next(responses))
        self.assertEqual([h['state'] for h in r['history']],['FAIL','CONSTRAINTS_MATCH'])
        self.assertEqual(r['selected_attempt'],1)
        self.assertFalse(r['draft'].startswith('Đừng'))
        self.assertEqual(r['output'],'')

    def test_operation_and_scope_revision(self):
        for source,first,second,initial in (
            ('Keep unverified entries outside the set eligible for patching.',
             'Giữ hồ sơ chưa xác minh ngoài nhóm đủ điều kiện cập nhật.',
             'Giữ hồ sơ chưa xác minh ngoài nhóm đủ điều kiện vá.','FAIL'),
            ('Keep unchecked records outside the collection allowed for export.',
             'Giữ hồ sơ chưa kiểm tra ngoài bộ sưu tập, không được phép xuất dữ liệu.',
             'Giữ hồ sơ chưa kiểm tra ngoài bộ sưu tập đủ điều kiện xuất dữ liệu.','UNKNOWN')):
            responses=iter([first,second])
            r=t.constrained_pipeline(dict(id='X',source_en=source,group='logic',split='development'),lambda *_:next(responses))
            self.assertEqual([h['state'] for h in r['history']],[initial,'CONSTRAINTS_MATCH'])
            self.assertEqual(r['selected_attempt'],1)
            self.assertEqual(r['status'],'NEEDS_REVIEW')
            self.assertEqual(r['output'],'')

    def test_fresh_sources_and_groups(self):
        self.assertEqual(t.natural.prior.digest(t.DATA),t.DATA_HASH)
        self.assertEqual(t.natural.prior.digest(t.FIXTURES),t.FIXTURES_HASH)
        rows=json.loads(t.DATA.read_text(encoding='utf-8'))['rows']
        norm=lambda s:''.join(c for c in unicodedata.normalize('NFKC',s).casefold() if c.isalnum())
        new={norm(r['source_en']) for r in rows};self.assertEqual(len(new),4)
        for phase in (1,5,6,7,8,9,10,11):
            old=json.loads((t.ROOT/f'evaluation/translation_quality_phase{phase}/dataset.v1.json').read_text(encoding='utf-8'))['rows']
            self.assertFalse(new&{norm(r['source_en']) for r in old})
        groups={}
        for r in rows:groups.setdefault(r['scenario_boundary']['group_id'],set()).add(r['split'])
        self.assertTrue(all(len(v)==1 for v in groups.values()))
