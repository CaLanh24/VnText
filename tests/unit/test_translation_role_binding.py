import unittest
from tests.tools.translation_role_binding import bind_metadata_roles
from tests.tools.translation_constraints_v2 import audit_constraints


class MetadataBindingTests(unittest.TestCase):
    def test_plural_listener_is_single_only_in_closed_source_frame(self):
        row=dict(source_en='I will bring you my gloves after breakfast.',address_context='older sister to younger brother')
        before='Sau bữa sáng, chị sẽ mang cho các em găng tay của mình.'
        result,edits=bind_metadata_roles(row,before)
        self.assertEqual(result,'Sau bữa sáng, chị sẽ mang cho em găng tay của mình.')
        self.assertEqual(edits[0]['before'],'các em')
        self.assertEqual(audit_constraints(row,result)['status'],'CONSTRAINTS_MATCH')
        row['source_en']='I will bring you and your friends my gloves.'
        self.assertEqual(bind_metadata_roles(row,before),(before,[]))

    def test_only_professor_recipient_span_not_honorific_object(self):
        row=dict(source_en='I will show you my grandfather.',address_context='younger student to older professor; gender unknown')
        before='Em sẽ cho ông xem ảnh của ông nội.'
        result,edits=bind_metadata_roles(row,before)
        self.assertEqual(result,'Em sẽ cho giáo sư xem ảnh của ông nội.')
        self.assertEqual(len(edits),1)
        row['source_en']='She will show you her grandfather.'
        self.assertEqual(bind_metadata_roles(row,before),(before,[]))

    def test_professor_agent_and_quoted_unknown_scope(self):
        row=dict(source_en='Could you lend me your reference book?',address_context='younger student to older professor; gender unknown')
        before='Ông có thể cho em mượn sách của mình không?'
        result,edits=bind_metadata_roles(row,before)
        self.assertTrue(result.startswith('Giáo sư'))
        self.assertEqual(edits[0]['role_field'],'agent')
        self.assertEqual(audit_constraints(row,result)['status'],'CONSTRAINTS_MATCH')
        self.assertEqual(bind_metadata_roles(row,'"'+before+'"'),('"'+before+'"',[]))

    def test_missing_ownership_is_unknown_after_honorific_repair(self):
        row=dict(source_en='May I send you my chart?',address_context='younger student to older professor; gender unknown')
        result,_=bind_metadata_roles(row,'Em có thể gửi biểu đồ cho ông không?')
        self.assertEqual(audit_constraints(row,result)['status'],'UNKNOWN')
        self.assertEqual(audit_constraints(row,'Em có thể gửi biểu đồ của em cho giáo sư không?')['status'],'CONSTRAINTS_MATCH')
