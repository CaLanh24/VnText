"""Persist Owner-delegated Brain decisions separately from the sealed draft."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
from tests.tools import translation_owner_review_packet as original

ROOT=original.ROOT
DEST=ROOT/'evaluation/translation_owner_approval_v1'
TRANSLATION_IDS={'IDI-001','IDI-004','IDI-005','IDI-006','IDI-007','IDI-010','IDI-012','IDI-015','IDI-016','IDI-017','ADDR-008','ADDR-014','ADDR-015','ADDR-016','TERM-001','TERM-004','TERM-014'}
TERM_IDS={'G01','G02','G03','G04','G05','G06'}


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def validate(decision):
    packet=original.load(original.DEST/'proposals.json')
    assert decision['status']=='APPROVED_BY_OWNER_DELEGATED_AGENT'
    assert decision['reviewer']=='Brain read-only'
    assert decision['authority']['owner_quote']=='m duyệt đi'
    assert decision['authority']['thread_id']=='01a0ffa3-6f97-7882-898b-33c11559d267'
    assert decision['authority']['turn_id']=='01a158d1-2185-7bc3-951f-1c82dc6c06af'
    assert decision['packet_manifest_sha256']==sha(original.DEST/'manifest.json')
    assert decision['proposal_file_sha256']==sha(original.DEST/'proposals.json')
    assert decision['direct_human_linguistic_review'] is False
    assert decision['human_gold'] is False and decision['training_authorized'] is False
    assert decision['product_imported'] is False and decision['whole_app_accepted'] is False
    assert len(decision['translations'])==17 and {r['id'] for r in decision['translations']}==TRANSLATION_IDS
    assert len(decision['glossary'])==6 and {r['id'] for r in decision['glossary']}==TERM_IDS
    for kind,key in [('translations','proposed_translation'),('glossary','proposed_target')]:
        sources={r['id']:r for r in packet[kind]}
        for row in decision[kind]:
            source=sources[row['id']]
            assert row['approved'] is True and row['source']==source['source']
            assert row['translation']==source[key]
            assert row['human_gold'] is False and row['training_eligible'] is False
            if kind=='translations':
                assert row['approval_scope']==source['intended_scope']
                assert row['scenario_boundary']==source['scenario_boundary']
                assert row['address_context']==source['address_context']
            else:
                assert row['occurrence_ids']==source['occurrence_ids']
                assert row['domain_note']==source['domain_note'] and row['exclusions']==source['exclusions']
    # A later decision must never turn the old pending packet into approval.
    assert packet['approved'] is False and packet['product_imported'] is False
    assert all(not r['approved'] for r in packet['translations'])
    return True


def build():
    original.verify()
    if DEST.exists():raise FileExistsError(DEST)
    packet=original.load(original.DEST/'proposals.json')
    decision=dict(schema_version=1,status='APPROVED_BY_OWNER_DELEGATED_AGENT',reviewer='Brain read-only',
        authority=dict(owner_quote='m duyệt đi',thread_id='01a0ffa3-6f97-7882-898b-33c11559d267',
                       turn_id='01a158d1-2185-7bc3-951f-1c82dc6c06af',
                       grant='Review the named 17 translations and six glossary proposals in their recorded contexts'),
        packet_manifest_sha256=sha(original.DEST/'manifest.json'),proposal_file_sha256=sha(original.DEST/'proposals.json'),
        direct_human_linguistic_review=False,human_gold=False,training_authorized=False,
        product_imported=False,whole_app_accepted=False,translations=[],glossary=[],
        integration_status='NOT_APPLIED_SCOPE_PREREQUISITE_UNRESOLVED',
        caveats=['Existing memory may fall back across context families within package.',
                 'Memory rebuild currently drops any proposed strict approval boundary.',
                 'Approval is not a global bank, training grant or proof of unseen translation quality.'])
    for row in packet['translations']:
        assert row['id'] in TRANSLATION_IDS
        decision['translations'].append(dict(id=row['id'],source=row['source'],translation=row['proposed_translation'],
            approval_scope=copy.deepcopy(row['intended_scope']),scenario_boundary=copy.deepcopy(row['scenario_boundary']),
            address_context=row['address_context'],approved=True,human_gold=False,training_eligible=False))
    for row in packet['glossary']:
        assert row['id'] in TERM_IDS
        decision['glossary'].append(dict(id=row['id'],source=row['source'],translation=row['proposed_target'],
            occurrence_ids=row['occurrence_ids'],domain_note=row['domain_note'],exclusions=row['exclusions'],
            approved=True,human_gold=False,training_eligible=False))
    validate(decision)
    DEST.mkdir()
    (DEST/'decision.json').write_text(json.dumps(decision,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    text='''# Quyết định duyệt do Owner ủy quyền

Owner đã nói **“m duyệt đi”** tại chat Brain read-only, turn
`01a158d1-2185-7bc3-951f-1c82dc6c06af`. Brain chấp thuận cả17câu và6thuật ngữ
đúng đề xuất, nguồn, occurrence, ngữ cảnh và exclusions của gói gốc.
`decision.json` lưu đủ mapping cùng hash gói gốc, không sửa bất kỳ bản nháp,
manifest hay phiếu trống gốc nào.

Đây là **duyệt của agent được Owner ủy quyền**, không phải human linguistic gold,
không phải quyền training hoặc nghiệm thu chất lượng toàn app. TERM-014 được
chấp thuận cách chuyển câu bị động trong ngữ cảnh xuất dữ liệu; G05 chỉ được
dùng trong ngữ cảnh cache lookup/result, không phải mọi nghĩa của hit.

Chưa áp dụng vào app/package/memory. Bộ nhớ hiện tại có fallback theo
context-family và rebuild từ CSV có thể làm mất ranh giới scope: cần khép seam
này trước bước tích hợp. Không được biến các câu đã thấy thành bank mặc định.

Kiểm tra offline: `python -B -m tests.tools.translation_owner_approval verify`.
Verifier xác minh mapping/phạm vi/attribution của artifact, không tự tạo quyền,
duyệt ngôn ngữ lại hoặc xác nhận model đã cải thiện.
'''
    (DEST/'README.md').write_text(text,encoding='utf-8')
    print('Recorded delegated approval:17 translations/6 terms; not applied.')


def verify():
    original.verify()
    validate(original.load(DEST/'decision.json'))
    print('PASS: delegated approval mapping and boundaries; original packet still pending and unchanged.')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['build','verify'])
    {'build':build,'verify':verify}[p.parse_args().action]()
