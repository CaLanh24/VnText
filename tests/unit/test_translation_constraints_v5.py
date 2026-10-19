import unittest
from tests.tools.translation_constraints_v5 import audit_constraints


class ResolutionStateTests(unittest.TestCase):
    def test_unresolved_is_not_unfinished(self):
        row=dict(source_en='Keep unresolved translations outside the set permitted for release.')
        good='Giữ bản dịch chưa giải quyết ngoài tập hợp đủ điều kiện phát hành.'
        self.assertEqual(audit_constraints(row,good)['status'],'CONSTRAINTS_MATCH')
        for phrase in ('chưa hoàn thiện','chưa hoàn thành','chưa xong','chưa được hoàn thiện'):
            self.assertEqual(audit_constraints(row,good.replace('chưa giải quyết',phrase))['status'],'FAIL')

    def test_unfinished_source_and_quoted_text_not_rewritten(self):
        draft='Giữ bản dịch chưa hoàn thiện ngoài tập hợp đủ điều kiện phát hành.'
        self.assertEqual(audit_constraints(dict(source_en='Keep unfinished translations outside the set permitted for release.'),draft)['status'],'UNKNOWN')
        self.assertEqual(audit_constraints(dict(source_en='Keep unresolved translations outside the set permitted for release.'),'"'+draft+'"')['status'],'UNKNOWN')

    def test_inside_and_added_prohibition_still_fail(self):
        row=dict(source_en='Keep unresolved translations outside the set permitted for release.')
        for bad in ('Giữ bản dịch chưa giải quyết trong tập hợp đủ điều kiện phát hành.',
                    'Đừng giữ bản dịch chưa giải quyết ngoài tập hợp đủ điều kiện phát hành.'):
            self.assertEqual(audit_constraints(row,bad)['status'],'FAIL')
