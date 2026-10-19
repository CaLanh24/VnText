import unittest
from tests.tools.translation_constraints_v4 import audit_constraints


class NamedReviewCases(unittest.TestCase):
    def test_patch_does_not_mean_update(self):
        row=dict(source_en='Keep unverified entries outside the set eligible for patching.')
        self.assertEqual(audit_constraints(row,'Hãy để các bản ghi chưa xác minh nằm ngoài danh sách phù hợp để được cập nhật.')['status'],'FAIL')
        self.assertEqual(audit_constraints(row,'Giữ các mục nhập chưa xác minh ngoài tập hợp đủ điều kiện vá.')['status'],'CONSTRAINTS_MATCH')

    def test_comma_negation_is_not_blessed_as_positive_collection(self):
        row=dict(source_en='Keep unchecked records outside the collection allowed for export.')
        for unknown in ('Hãy giữ các hồ sơ chưa được kiểm tra bên ngoài bộ sưu tập, không được phép xuất dữ liệu.',
                        'Giữ hồ sơ chưa kiểm tra ngoài bộ sưu tập không đủ điều kiện xuất dữ liệu.'):
            self.assertEqual(audit_constraints(row,unknown)['status'],'UNKNOWN')
        self.assertEqual(audit_constraints(row,'Giữ hồ sơ chưa kiểm tra ngoài bộ sưu tập đủ điều kiện xuất dữ liệu.')['status'],'CONSTRAINTS_MATCH')

    def test_unresolved_records_alias_and_corruptions(self):
        row=dict(source_en='Keep unresolved records outside the collection eligible for export.')
        good='Hãy giữ lại các hồ sơ chưa được giải quyết bên ngoài bộ sưu tập phù hợp với việc xuất dữ liệu.'
        self.assertEqual(audit_constraints(row,good)['status'],'CONSTRAINTS_MATCH')
        for bad in (good.replace('bên ngoài','bên trong'),good.replace('Hãy giữ lại','Đừng giữ lại')):
            self.assertEqual(audit_constraints(row,bad)['status'],'FAIL')
        self.assertEqual(audit_constraints(row,good[:-1]+' và vẫn có thể xuất dữ liệu.')['status'],'FAIL')

    def test_quoted_and_source_prohibition_stay_protected(self):
        row=dict(source_en='Keep unresolved records outside the collection eligible for export.')
        self.assertEqual(audit_constraints(row,'"Đừng giữ hồ sơ chưa giải quyết ngoài danh sách có thể xuất dữ liệu."')['status'],'UNKNOWN')
        row=dict(source_en='Do not delete the file unless the user confirms.')
        self.assertEqual(audit_constraints(row,'Đừng xóa tệp trừ khi người dùng xác nhận.')['status'],'CONSTRAINTS_MATCH')
