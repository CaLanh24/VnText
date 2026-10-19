"""Finite entry-noun and eligibility clauses, retaining polarity and operation boundaries."""
import re
from tests.tools import translation_constraints_v3 as previous
base=previous.base
source_contract=previous.source_contract
select_attempt=previous.select_attempt


def audit_constraints(row,draft):
    result=previous.audit_constraints(row,draft)
    contract=source_contract(row)
    if not contract or contract['kind']!='exclusion':return result
    if base.opaque_tokens(row['source_en'])!=base.opaque_tokens(draft):return result
    if re.search(r'["“”]',draft):return result
    if result['status']=='FAIL':return result
    d=base.plain(draft)
    if contract['operation']=='patching' and re.search(r'\bcập nhật\b',d):
        return {**result,'status':'FAIL','reasons':['patch eligibility changed to update eligibility']}
    # Require an affirmative complete clause. A comma or negated modifier cannot be silently discarded.
    if re.search(r',|;|\bvà\b|\bnhưng\b|không (?:được|phù hợp|đủ điều kiện)|chưa được phép',d):
        return {**result,'status':'UNKNOWN','reasons':['eligibility scope contains unsupported punctuation/negation/coordination']}
    classes={'unverified':r'chưa (?:được )?xác minh','unchecked':r'chưa (?:được )?kiểm tra',
             'rejected':r'bị từ chối','unresolved':r'chưa (?:được )?giải quyết'}
    operations={'export':r'xuất dữ liệu','release':r'(?:phát hành|công bố)','patching':r'(?:vá|bản vá)'}
    rx=(r'^(?:hãy )?(?:giữ(?: lại)?|để|lưu trữ) (?:những |các )?'
        r'(?:bản ghi(?: chép)?|mục nhập|phần dữ liệu|dữ liệu|hồ sơ|bản dịch) '+classes[contract['entry_class']]+
        r'(?: nằm| ở)? (?:bên )?(ngoài|trong) '
        r'(?:tập hợp|danh sách|bộ sưu tập|phạm vi|bộ dữ liệu|nhóm) '
        r'(?:(?:những |các )?bản )?'
        r'(?:đủ điều kiện|(?:được )?phép|có thể|phù hợp)(?: được| để| với việc)? '+operations[contract['operation']]+r'$')
    match=re.fullmatch(rx,d)
    if match:
        return {**result,'status':'CONSTRAINTS_MATCH' if match[1]=='ngoài' else 'FAIL',
                'reasons':[] if match[1]=='ngoài' else ['entries moved inside eligible set'],
                'target_facts':dict(entry_class=contract['entry_class'],outside=match[1]=='ngoài',operation=contract['operation'])}
    return result


def feedback(contract):
    if contract and contract['kind']=='exclusion':
        operation={'export':'xuất dữ liệu','release':'phát hành','patching':'vá'}[contract['operation']]
        return (previous.feedback(contract)+' Express the collection eligibility with the affirmative fragment '
                'đủ điều kiện '+operation+'. Keep outside as ngoài. Avoid commas and a second negated eligibility clause.')
    return previous.feedback(contract)
