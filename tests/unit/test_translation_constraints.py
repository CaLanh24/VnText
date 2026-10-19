import unittest
from tests.tools.translation_constraints import Formula,audit_constraints,source_contract,conditional_formula


class ConstraintTests(unittest.TestCase):
    def test_truth_tables_distinguish_direction_and_scope(self):
        self.assertEqual(Formula('p','a','if',False,True).allowed(),(False,True,True,True))
        self.assertEqual(Formula('p','a','only_if').allowed(),(True,False,True,True))
        self.assertEqual(Formula('p','a','if',False,False).allowed(),Formula('p','a','only_if').allowed())
        self.assertNotEqual(Formula('p','a','if',False,True).allowed(),Formula('p','a','only_if').allowed())
        with self.assertRaises(ValueError):Formula('p','a','maybe')

    def test_unless_equivalent_and_inverted_drafts(self):
        row=dict(source_en='Unless the user confirms, leave the original files untouched.')
        for draft in ('Nếu người dùng không xác nhận, hãy giữ nguyên các tệp gốc.',
                      'Trừ khi người dùng xác nhận, hãy giữ nguyên các tệp gốc.'):
            self.assertEqual(audit_constraints(row,draft)['status'],'CONSTRAINTS_MATCH')
        for draft in ('Chỉ khi người dùng xác nhận, hãy giữ nguyên các tệp gốc.',
                      'Nếu người dùng xác nhận, hãy giữ nguyên các tệp gốc.',
                      'Nếu người vận hành không xác nhận, hãy giữ nguyên các tệp gốc.'):
            self.assertEqual(audit_constraints(row,draft)['status'],'FAIL')

    def test_prohibition_and_object_identity_not_just_negation_count(self):
        row=dict(source_en='Do not overwrite the archive unless the user approves.')
        self.assertEqual(audit_constraints(row,'Đừng ghi đè kho lưu trữ trừ khi người dùng phê duyệt.')['status'],'CONSTRAINTS_MATCH')
        for bad in ('Hãy ghi đè kho lưu trữ trừ khi người dùng phê duyệt.',
                    'Đừng ghi đè cơ sở dữ liệu trừ khi người dùng phê duyệt.'):
            self.assertEqual(audit_constraints(row,bad)['status'],'FAIL')
        self.assertEqual(audit_constraints(row,'Đừng ghi đè nó trừ khi người dùng phê duyệt.')['status'],'UNKNOWN')

    def test_only_verified_permission_not_if_verified(self):
        row=dict(source_en='Only entries with verified signatures may be released.')
        self.assertEqual(audit_constraints(row,'Chỉ bản ghi có chữ ký đã xác minh mới được phát hành.')['status'],'CONSTRAINTS_MATCH')
        self.assertEqual(audit_constraints(row,'Chỉ bản ghi có chữ ký chưa xác minh mới được phát hành.')['status'],'FAIL')
        # Complete unsupported clause stays UNKNOWN, not a partial keyword PASS.
        self.assertEqual(audit_constraints(row,'Chỉ bản ghi có chữ ký đã xác minh mới được phát hành và xóa bản gốc.')['status'],'UNKNOWN')

    def test_all_agent_recipient_owner_swaps(self):
        row=dict(source_en='I will lend you my red scarf.',address_context='older sister to younger brother')
        good='Chị sẽ cho em mượn khăn đỏ của chị.'
        self.assertEqual(audit_constraints(row,good)['status'],'CONSTRAINTS_MATCH')
        for agent in ('chị','em'):
            for recipient in ('chị','em'):
                for owner in ('chị','em'):
                    draft=f'{agent} sẽ cho {recipient} mượn khăn đỏ của {owner}.'
                    expected='CONSTRAINTS_MATCH' if (agent,recipient,owner)==('chị','em','chị') else 'FAIL'
                    self.assertEqual(audit_constraints(row,draft)['status'],expected,(agent,recipient,owner))
        for bad in ('Chị sẽ cho em và chị mượn khăn đỏ của chị.','Chị sẽ cho chị và em mượn khăn đỏ của chị.','Chị sẽ cho các em mượn khăn đỏ của chị.'):
            self.assertEqual(audit_constraints(row,bad)['status'],'FAIL')
        self.assertEqual(audit_constraints(row,'Chị sẽ cho em mượn khăn đỏ.')['status'],'UNKNOWN')

    def test_request_direction_and_reflexive_owner(self):
        row=dict(source_en='Could you lend me your camera?',address_context='younger brother to older sister')
        self.assertEqual(audit_constraints(row,'Chị có thể cho em mượn máy ảnh của chị không?')['status'],'CONSTRAINTS_MATCH')
        self.assertEqual(audit_constraints(row,'Em có thể cho chị mượn máy ảnh của chị không?')['status'],'FAIL')
        row=dict(source_en='You may borrow my charger.',address_context='older brother to younger sister')
        self.assertEqual(audit_constraints(row,'Em có thể mượn bộ sạc của anh.')['status'],'CONSTRAINTS_MATCH')
        self.assertEqual(audit_constraints(row,'Em có thể mượn bộ sạc của mình.')['status'],'FAIL')

    def test_exclusion_cannot_be_still_exportable(self):
        row=dict(source_en='Keep rejected entries outside the collection eligible for export.')
        self.assertEqual(audit_constraints(row,'Giữ các bản ghi bị từ chối ngoài tập hợp đủ điều kiện xuất dữ liệu.')['status'],'CONSTRAINTS_MATCH')
        for bad in ('Giữ các bản ghi bị từ chối trong tập hợp đủ điều kiện xuất dữ liệu.',
                    'Giữ các bản ghi bị từ chối ngoài bộ sưu tập, và vẫn có thể xuất khẩu được.'):
            self.assertEqual(audit_constraints(row,bad)['status'],'FAIL')

    def test_preservation_not_prohibition_on_cancel_or_other_object(self):
        row=dict(source_en='Canceling the transfer must preserve the backup.')
        self.assertEqual(audit_constraints(row,'Việc hủy chuyển phải giữ bản sao lưu nguyên vẹn.')['status'],'CONSTRAINTS_MATCH')
        for bad in ('Không được hủy chuyển nếu chưa xóa bản sao lưu.',
                    'Việc hủy chuyển phải giữ bản chụp nguyên vẹn.'):
            self.assertEqual(audit_constraints(row,bad)['status'],'FAIL')

    def test_unknown_quotes_and_unrecognized_source_are_not_blessed(self):
        row=dict(source_en='I think the world is beautiful.',address_context='unknown')
        self.assertIsNone(source_contract(row))
        self.assertEqual(audit_constraints(row,'Tôi nghĩ thế giới đẹp.')['status'],'UNKNOWN')
        row=dict(source_en='Reject {A} unless its checksum is valid.')
        self.assertEqual(audit_constraints(row,'Từ chối {B} trừ khi mã kiểm tra hợp lệ.')['status'],'FAIL')
        row=dict(source_en='"I will lend you my scarf," she said.',address_context='older sister to younger brother')
        self.assertIsNone(source_contract(row))
        row['source_en']='I will lend you my scarf.'
        self.assertEqual(audit_constraints(row,'"Chị sẽ cho em mượn khăn của chị."')['status'],'UNKNOWN')
        row['source_en']='I will lend you my scarf if you return it tomorrow.'
        self.assertIsNone(source_contract(row))

    def test_kinship_age_and_gender_are_separate_obligations(self):
        row=dict(source_en='You can tell me the truth; I am your sister.',address_context='older sister to younger brother')
        self.assertEqual(audit_constraints(row,'Em có thể nói thật với chị; chị là chị gái của em.')['status'],'CONSTRAINTS_MATCH')
        for bad in ('Chị là em gái của em.','Chị là anh trai của em.','Em là chị gái của chị.'):
            self.assertEqual(audit_constraints(row,bad)['status'],'FAIL')

    def test_postfix_if_and_identifier_confirmation(self):
        row=dict(source_en='<b>Do not delete {SOURCE_ID}</b> unless {USER_ID} confirms.')
        self.assertEqual(audit_constraints(row,'<b>Đừng xóa {SOURCE_ID}</b> trừ khi {USER_ID} xác nhận.')['status'],'CONSTRAINTS_MATCH')
        self.assertEqual(audit_constraints(row,'<b>Hãy xóa {SOURCE_ID}</b> khi {USER_ID} chưa xác nhận.')['status'],'FAIL')
        row=dict(source_en='Reject {ITEM_ID} unless its checksum is valid.')
        self.assertEqual(audit_constraints(row,'Từ chối {ITEM_ID} nếu mã kiểm tra không hợp lệ.')['status'],'CONSTRAINTS_MATCH')
        self.assertEqual(audit_constraints(row,'Chấp nhận {ITEM_ID} nếu mã kiểm tra không hợp lệ.')['status'],'FAIL')
