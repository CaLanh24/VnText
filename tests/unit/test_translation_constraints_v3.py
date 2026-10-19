import unittest
from tests.tools.translation_constraints_v3 import audit_constraints


class ExclusionPolarityTests(unittest.TestCase):
    def test_actual_added_prohibition_is_not_unknown(self):
        row=dict(source_en='Keep unverified records outside the set eligible for release.')
        for neg in ('Đừng lưu trữ','Không được giữ','Chớ để'):
            self.assertEqual(audit_constraints(row,neg+' các bản ghi chưa xác minh bên ngoài danh sách những bản có thể được phát hành.')['status'],'FAIL')
        self.assertEqual(audit_constraints(row,'Giữ các bản ghi chưa xác minh bên ngoài danh sách những bản có thể được phát hành.')['status'],'CONSTRAINTS_MATCH')

    def test_entry_alias_and_relative_eligibility_but_not_scope_corruption(self):
        row=dict(source_en='Keep unchecked entries outside the collection eligible for export.')
        self.assertEqual(audit_constraints(row,'Hãy để những dữ liệu chưa được kiểm tra nằm ngoài danh sách có thể được xuất dữ liệu.')['status'],'CONSTRAINTS_MATCH')
        for bad in ('Giữ mục nhập chưa kiểm tra trong danh sách được phép xuất dữ liệu.',
                    'Giữ mục nhập chưa kiểm tra ngoài danh sách và vẫn có thể xuất dữ liệu.'):
            self.assertEqual(audit_constraints(row,bad)['status'],'FAIL')
        for unknown in ('Giữ mục nhập chưa kiểm tra ngoài danh sách không được phép xuất dữ liệu.',
                        'Giữ mục nhập chưa kiểm tra ngoài danh sách, đủ điều kiện xuất dữ liệu.'):
            self.assertEqual(audit_constraints(row,unknown)['status'],'UNKNOWN')

    def test_legitimate_prohibition_on_deletion_not_stripped_or_rejected(self):
        row=dict(source_en='Do not delete the backup unless the user confirms.')
        draft='Đừng xóa bản sao lưu trừ khi người dùng xác nhận.'
        self.assertEqual(audit_constraints(row,draft)['status'],'CONSTRAINTS_MATCH')
        self.assertEqual(draft,'Đừng xóa bản sao lưu trừ khi người dùng xác nhận.')
        row=dict(source_en='Keep unverified records outside the set eligible for release.')
        self.assertEqual(audit_constraints(row,'"Đừng giữ bản ghi chưa xác minh ngoài danh sách có thể phát hành."')['status'],'UNKNOWN')
