"""Finite research-only positive transaction alternatives; unsupported scopes abstain."""
import re
from tests.tools import translation_constraints_v5 as previous
base=previous.base
select_attempt=previous.select_attempt

def source_contract(row):
    if re.fullmatch(r'The (?:model|monitor|scheduler) (?:predicts|checks|determines) whether the transaction will (?:finish|complete) or roll back\.',row['source_en'],re.I):
        return {'kind':'positive_alternatives'}
    return previous.source_contract(row)

def audit_constraints(row,draft):
    contract=source_contract(row)
    if not contract or contract['kind']!='positive_alternatives':return previous.audit_constraints(row,draft)
    result=dict(status='UNKNOWN',source_contract=contract,target_facts=None,reasons=['target alternative grammar unsupported'],draft_modified_by_parser=False)
    if base.opaque_tokens(row['source_en'])!=base.opaque_tokens(draft):return {**result,'status':'FAIL','reasons':['protected syntax differs']}
    d=base.plain(draft)
    if re.search(r'giao dịch.+\b(?:không|chưa|chẳng|đừng)\b',d):return {**result,'status':'FAIL','reasons':['positive rollback alternative was negated']}
    if re.search(r'liệu giao dịch (?:sẽ )?(?:hoàn tất|hoàn thành|kết thúc) (?:hay|hoặc) hoàn tác[.]?$',d):return {**result,'status':'CONSTRAINTS_MATCH','reasons':[]}
    return result

def feedback(contract):
    if contract and contract['kind']=='positive_alternatives':return 'Both outcomes are positive alternatives: finish OR roll back. Do not add NOT to either outcome. Preserve whether, transaction and both outcomes.'
    return previous.feedback(contract)
