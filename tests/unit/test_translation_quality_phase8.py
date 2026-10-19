import json
import unittest
import unicodedata
from tests.tools import translation_quality_phase8 as t


class AuditedTranslationTests(unittest.TestCase):
    def test_post_edit_only_binds_explicit_generic_pronouns_outside_syntax(self):
        row=dict(source_en='I can lend you my coat. {tôi}',address_context='older sister to younger brother')
        before='Tôi có thể cho bạn mượn áo của tôi. {tôi}'
        after,edits=t.bind_generic_roles(row,before)
        self.assertEqual(after,'Chị có thể cho em mượn áo của chị. {tôi}')
        self.assertEqual(len(edits),3)
        self.assertEqual(t.opaque_tokens(before),t.opaque_tokens(after))
        # Reconstruct original exactly from logged edits, including Unicode lengths.
        rebuilt=before
        for e in reversed(edits):rebuilt=rebuilt[:e['start']]+e['after']+rebuilt[e['end']:]
        self.assertEqual(rebuilt,after)

    def test_post_edit_abstains_on_ambiguous_roles_quotes_and_plural(self):
        for source in ('She told me about you.','We will lend you our coat.','"I am ready," she said.',"I've brought your bag.",'My friends like you.','My ego is strong.'):
            row=dict(source_en=source,address_context='older sister to younger brother')
            self.assertEqual(t.bind_generic_roles(row,'Tôi nói với bạn.'),('Tôi nói với bạn.',[]))
        self.assertEqual(t.bind_generic_roles(dict(source_en='I ask you.',address_context='unknown'),'Tôi hỏi bạn.'),('Tôi hỏi bạn.',[]))

    def test_affirmative_action_conflicts_have_negative_controls(self):
        row=dict(source_en='<b>Do not delete {A}</b> unless {B} confirms.')
        self.assertIn('affirmative deletion contradicts source prohibition',t.rule_audit(row,'<b>Hãy xóa {A}</b> khi {B} chưa xác nhận.'))
        self.assertEqual(t.rule_audit(row,'<b>Đừng xóa {A}</b> trừ khi {B} xác nhận.'),[])
        self.assertIn('accept contradicts source rejection',t.rule_audit(dict(source_en='Reject the file unless valid.'),'Chấp nhận tệp nếu không hợp lệ.'))

    def test_audit_parse_is_strict_and_unknown_cannot_pass(self):
        self.assertEqual(t.parse_audit('PASS'),('PASS',''))
        self.assertEqual(t.parse_audit('FAIL: added recipient')[0],'FAIL')
        for raw in ('probably PASS','PASS\nFAIL','The translation is correct','{"verdict":"PASS"}',''):
            self.assertEqual(t.parse_audit(raw)[0],'UNKNOWN')
        self.assertEqual(t.decision([],'PASS',False),'UNKNOWN')
        self.assertEqual(t.decision(['wrong role'],'PASS',True),'FAIL')
        self.assertEqual(t.decision([],'UNKNOWN',True),'UNKNOWN')

    def test_retry_is_bounded_and_never_fakes_acceptance(self):
        row=dict(id='X',source_en='I can lend you my coat.',group='address',split='development',address_context='older sister to younger brother')
        responses=iter(['Tôi cho bạn mượn áo.','FAIL: wrong roles','Chị cho em mượn áo của chị.','FAIL: still wrong'])
        calls=[]
        def infer(prompt,label):calls.append(label);return next(responses)
        result=t.natural_pipeline(row,infer,'label',True)
        self.assertEqual(len(result['history']),2)
        self.assertEqual(len(calls),4)
        self.assertEqual(result['output'],'')
        self.assertEqual(result['status'],'NEEDS_REVIEW')
        self.assertEqual(result['draft'],'Chị cho em mượn áo của chị.')

    def test_revision_success_and_unknown_preserves_review(self):
        row=dict(id='X',source_en='I can lend you my coat.',group='address',split='development',address_context='older sister to younger brother')
        responses=iter(['Tôi cho bạn mượn áo.','FAIL','Chị cho em mượn áo của chị.','PASS'])
        result=t.natural_pipeline(row,lambda *_:next(responses),'label',True)
        self.assertEqual(result['status'],'AUTO_CANDIDATE')
        result=t.natural_pipeline(row,lambda *_:'Chị cho em mượn áo của chị.',None,False)
        self.assertEqual(len(result['history']),1)
        self.assertEqual(result['status'],'NEEDS_REVIEW')

    def test_rules_detect_added_recipient_without_rewriting(self):
        row=dict(source_en='I will send you my paper.',address_context='younger student to older professor; gender unknown')
        self.assertIn('added speaker as recipient',t.rule_audit(row,'Em sẽ gửi giáo sư và em bài viết.'))
        self.assertEqual(t.rule_audit(row,'Em sẽ gửi giáo sư bài viết của em.'),[])
        self.assertIn('unknown professor gender guessed',t.rule_audit(row,'Em sẽ gửi cô bài viết của em.'))

    def test_source_boundary_and_frozen_new_strings(self):
        self.assertEqual(t.prior.digest(t.DATA),t.DATA_HASH)
        self.assertEqual(t.prior.digest(t.FIXTURES),t.FIXTURES_HASH)
        rows=json.loads(t.DATA.read_text(encoding='utf-8'))['rows']
        norm=lambda s:''.join(c for c in unicodedata.normalize('NFKC',s).casefold() if c.isalnum())
        new={norm(r['source_en']) for r in rows}
        self.assertEqual(len(new),24)
        for phase in (1,5,6,7):
            old=json.loads((t.ROOT/f'evaluation/translation_quality_phase{phase}/dataset.v1.json').read_text(encoding='utf-8'))['rows']
            self.assertFalse(new&{norm(r['source_en']) for r in old})
        groups={}
        for r in rows:groups.setdefault(r['scenario_boundary']['group_id'],set()).add(r['split'])
        self.assertTrue(all(len(v)==1 for v in groups.values()))
        prompt,p,_=t.translation_prompt(rows[1])
        self.assertTrue(prompt.endswith(p.masked))
        self.assertNotIn(rows[0]['source_en'],prompt)
        self.assertNotIn('ROLEVNT',prompt)

    def test_structural_corruption_cannot_be_accepted_by_judge(self):
        row=dict(id='X',source_en='{A} waits.',group='protected_tokens',split='development')
        # Invalid drafts never reach semantic judge, even if a judge would say PASS.
        result=t.natural_pipeline(row,lambda *_:'{B} chờ.','label',True)
        self.assertEqual(result['status'],'NEEDS_REVIEW')
        self.assertEqual(result['output'],'')
        self.assertTrue(all(x['structural_error'] for x in result['history']))
