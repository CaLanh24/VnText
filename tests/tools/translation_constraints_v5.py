"""Research-only distinction between unresolved and unfinished entry states."""
import re
from tests.tools import translation_constraints_v4 as previous
base=previous.base
source_contract=previous.source_contract
select_attempt=previous.select_attempt


def audit_constraints(row,draft):
    result=previous.audit_constraints(row,draft)
    contract=source_contract(row)
    if not contract or contract['kind']!='exclusion' or contract['entry_class']!='unresolved':return result
    if base.opaque_tokens(row['source_en'])!=base.opaque_tokens(draft) or re.search(r'["“”]',draft):return result
    if re.search(r'\b(?:unfinished|incomplete|uncompleted)\b',row['source_en'],re.I):return result
    if re.search(r'\bchưa (?:được )?(?:hoàn thiện|hoàn thành|xong)\b',base.plain(draft)):
        return {**result,'status':'FAIL','reasons':['unresolved state changed to unfinished/incomplete state']}
    return result


def feedback(contract):
    text=previous.feedback(contract)
    if contract and contract['kind']=='exclusion' and contract['entry_class']=='unresolved':
        text+=' Preserve the unresolved state: chưa giải quyết. Do not substitute unfinished or incomplete.'
    return text
