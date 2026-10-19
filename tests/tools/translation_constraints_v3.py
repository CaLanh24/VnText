"""Explicit exclusion polarity; v2 contracts remain unchanged for other phenomena."""
import re
from tests.tools import translation_constraints_v2 as previous
base=previous.base
source_contract=previous.source_contract
select_attempt=previous.select_attempt


def audit_constraints(row,draft):
    result=previous.audit_constraints(row,draft)
    contract=source_contract(row)
    if not contract or contract['kind']!='exclusion':return result
    if base.opaque_tokens(row['source_en'])!=base.opaque_tokens(draft):return result
    d=base.plain(draft)
    if re.search(r'["“”]',draft):return result
    # Source is affirmative Keep ... outside. Do not confuse this with Do not include.
    if re.match(r'^(?:đừng|không được|chớ)\s+(?:giữ|lưu|để)',d):
        return {**result,'status':'FAIL','reasons':['added prohibition reverses affirmative keep-outside instruction']}
    if result['status']=='FAIL':return result
    classes={'unverified':r'chưa (?:được )?xác minh','unchecked':r'chưa (?:được )?kiểm tra',
             'rejected':r'bị từ chối','unresolved':r'chưa (?:được )?giải quyết'}
    operations={'export':r'xuất dữ liệu','release':r'(?:phát hành|công bố)','patching':r'(?:vá|bản vá)'}
    # Full clause, no comma/coordination/extra sentence may hide an eligibility reversal.
    rx=(r'^(?:hãy )?(?:giữ(?: lại)?|để|lưu trữ) (?:những |các )?'
        r'(?:bản ghi(?: chép)?|mục nhập|phần dữ liệu|dữ liệu) '+classes[contract['entry_class']]+
        r'(?: nằm| ở)? (?:bên )?(ngoài|trong) '
        r'(?:tập hợp|danh sách|bộ sưu tập|phạm vi|bộ dữ liệu) '
        r'(?:(?:những |các )?bản )?'
        r'(?:đủ điều kiện|(?:được )?phép|có thể)(?: được| để)? '+operations[contract['operation']]+r'$')
    m=re.fullmatch(rx,d)
    if m:
        return {**result,'status':'CONSTRAINTS_MATCH' if m[1]=='ngoài' else 'FAIL',
                'target_facts':dict(outside=m[1]=='ngoài',eligible_operation=contract['operation'],entry_class=contract['entry_class']),
                'reasons':[] if m[1]=='ngoài' else ['excluded entries moved inside eligible set']}
    # Do not let the earlier substring parser bless a negated eligibility modifier.
    if re.search(r'không (?:đủ điều kiện|được phép|thể)|chưa được phép',d):
        return {**result,'status':'UNKNOWN','reasons':['negative eligibility scope not supported']}
    return result


def feedback(contract):
    if contract and contract['kind']=='exclusion':
        return ('The source commands KEEP, not DO NOT KEEP. Keep these entries OUTSIDE the eligible collection. '
                'Do not add a prohibition on keeping them outside. The eligible operation is '+contract['operation']+'.')
    return previous.feedback(contract)
