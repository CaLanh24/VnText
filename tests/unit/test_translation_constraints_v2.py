import unittest
from tests.tools.translation_constraints_v2 import audit_constraints,select_attempt,source_contract


class ConstraintExtensionTests(unittest.TestCase):
    def test_preservation_variants_and_negative_scope(self):
        row=dict(source_en='Aborting the transfer must not delete the backup.')
        for good in ('Việc hủy chuyển không được phép xóa bản sao lưu.',
                     'Việc hủy chuyển phải đảm bảo bản sao lưu vẫn được giữ lại.'):
            self.assertEqual(audit_constraints(row,good)['status'],'CONSTRAINTS_MATCH')
        for bad in ('Không được hủy chuyển khi bản sao lưu được giữ lại.',
                    'Việc hủy chuyển không cần giữ bản sao lưu.',
                    'Việc hủy chuyển không được phép xóa bản chụp.'):
            self.assertEqual(audit_constraints(row,bad)['status'],'FAIL')

    def test_reference_only_resolves_to_unique_source_archive(self):
        row=dict(source_en='Unless the user confirms, leave the archive untouched.')
        result=audit_constraints(row,'Nếu người dùng không xác nhận, hãy để tập tin đó nguyên vẹn không thay đổi.')
        self.assertEqual(result['status'],'CONSTRAINTS_MATCH')
        self.assertIn('object_resolution',result)
        self.assertEqual(audit_constraints(row,'Nếu người dùng không xác nhận, hãy giữ nguyên cơ sở dữ liệu.')['status'],'FAIL')

    def test_eligibility_alias_never_blesses_ambiguous_or_still_eligible(self):
        row=dict(source_en='Keep unchecked records outside the set allowed for release.')
        self.assertEqual(audit_constraints(row,'Giữ bản ghi chưa được kiểm tra bên ngoài phạm vi được cho phép để công bố.')['status'],'CONSTRAINTS_MATCH')
        self.assertEqual(audit_constraints(row,'Giữ bản ghi chưa được kiểm tra bên ngoài phạm vi, được cho phép để công bố.')['status'],'UNKNOWN')
        self.assertEqual(audit_constraints(row,'Giữ bản ghi chưa được kiểm tra ngoài phạm vi và vẫn có thể công bố.')['status'],'FAIL')

    def test_critical_action_and_identifier_case_are_checked_on_original(self):
        row=dict(source_en='Reject {FILE_ID} unless its checksum is valid.')
        self.assertEqual(audit_constraints(row,'Reject {FILE_ID} nếu mã kiểm tra không hợp lệ.')['status'],'FAIL')
        self.assertEqual(audit_constraints(row,'Từ chối {FILE_ID} nếu mã kiểm tra không hợp lệ.')['status'],'CONSTRAINTS_MATCH')
        self.assertEqual(audit_constraints(row,'Từ chối {file_id} nếu mã kiểm tra không hợp lệ.')['status'],'FAIL')

    def test_permission_question_retains_role_direction(self):
        row=dict(source_en='May I send you my plan?',address_context='younger student to older professor; gender unknown')
        self.assertIsNotNone(source_contract(row))
        self.assertEqual(audit_constraints(row,'Em sẽ gửi giáo sư kế hoạch của em.')['status'],'CONSTRAINTS_MATCH')
        self.assertEqual(audit_constraints(row,'Giáo sư sẽ gửi em kế hoạch của em.')['status'],'FAIL')

    def test_equal_unknown_revision_cannot_replace_original(self):
        h=[dict(state='UNKNOWN',draft='Original with a negation.',structural_error=''),
           dict(state='UNKNOWN',draft='Revision without negation.',structural_error='')]
        self.assertEqual(select_attempt(h)[0],0)
        h[1]['state']='FAIL';self.assertEqual(select_attempt(h)[0],0)
        h[1]['state']='CONSTRAINTS_MATCH';self.assertEqual(select_attempt(h)[0],1)
        h[1]['structural_error']='marker missing';self.assertEqual(select_attempt(h)[0],0)

    def test_invalid_original_valid_review_revision_is_kept(self):
        h=[dict(state='FAIL',draft='',structural_error='missing marker'),
           dict(state='UNKNOWN',draft='Valid review draft.',structural_error='')]
        self.assertEqual(select_attempt(h)[0],1)
