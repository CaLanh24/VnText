"""Conservative parser extensions; preserve text, expose every normalization."""
from dataclasses import asdict,replace
import re
from tests.tools import translation_constraints as base


def source_contract(row):
    contract=base.source_contract(row)
    if contract:return contract
    s=base.plain(row['source_en'])
    if re.fullmatch(r'may i (send|bring|lend|show) you my .+',s):
        derived=re.sub(r'^may i ','I may ',row['source_en'],flags=re.I)
        return base.source_contract({**row,'source_en':derived})
    return None


def normalized_target(draft):
    s=base.plain(draft)
    s=s.replace('không được phép ','không được ').replace('được cho phép ','được phép ')
    s=re.sub(r'\bđể ([^,;]+?) nguyên vẹn(?: không thay đổi)?$',r'giữ nguyên \1',s)
    s=re.sub(r'\bđể ([^,;]+?) như cũ$',r'giữ nguyên \1',s)
    return s


def audit_constraints(row,draft):
    source=source_contract(row)
    normalized=normalized_target(draft)
    temporal=(('after breakfast',r'^sau bữa sáng, '),('this afternoon',r'^chiều nay,? '),
              ('tomorrow morning',r'^(?:sáng mai|ngày mai buổi sáng),? '),('tonight',r'^tối nay,? '))
    for source_time,rx in temporal:
        if source_time in base.plain(row['source_en']):normalized=re.sub(rx,'',normalized)
    parser_row={**row,'source_en':base.plain(row['source_en'])}
    result=base.audit_constraints(parser_row,normalized)
    result.update(source_contract=source,normalized_target=normalized,draft_modified_by_parser=False)
    if base.opaque_tokens(row['source_en'])!=base.opaque_tokens(draft):
        return {**result,'status':'FAIL','reasons':['protected syntax differs']}
    if source is None:return {**result,'status':'UNKNOWN','reasons':['source grammar unsupported']}
    # Quoted scopes retain the original abstention boundary.
    if re.search(r'["“”]',draft):return {**result,'status':'UNKNOWN','reasons':['quoted scope unsupported']}
    kind=source['kind']
    if kind=='conditional':
        expected=base.Formula(**source['formula'])
        if expected.action=='reject' and re.match(r'^reject\b',normalized):
            return {**result,'status':'FAIL','reasons':['critical action Reject untranslated']}
        target=base.conditional_formula(normalized,'vi')
        if target:
            if expected.object_id=='archive' and target.object_id=='file' and re.search(r'(?:tệp|tập tin) (?:đó|này)\b',normalized):
                target=replace(target,object_id='archive')
                result['object_resolution']='definite file refers to sole source archive object'
            result['target_facts']=asdict(target)
            if (target.condition,target.action,target.object_id)!=(expected.condition,expected.action,expected.object_id):
                result.update(status='FAIL',reasons=['condition/action/object identity differs'])
            elif target.allowed()!=expected.allowed():
                result.update(status='FAIL',reasons=['condition/polarity truth table differs'])
            else:result.update(status='CONSTRAINTS_MATCH',reasons=[])
    elif kind=='exclusion':
        # Alternative release wording only inside this declared release operation.
        scoped=normalized.replace('công bố','phát hành') if source['operation']=='release' else normalized
        result.update(base.audit_constraints(parser_row,scoped))
        tail=scoped.split('ngoài',1)[-1]
        if result['status']=='CONSTRAINTS_MATCH' and ',' in tail:
            result.update(status='UNKNOWN',reasons=['comma-separated eligibility scope ambiguous'])
    elif kind=='cancellation_preserves_data':
        if result['status']=='FAIL':return result
        if re.search(r'(?:hủy|dừng)',normalized) and re.search(r'không (?:cần|phải|được) (?:giữ|bảo toàn)',normalized):
            return {**result,'status':'FAIL','reasons':['required preservation explicitly negated']}
        if re.search(r'(?:hủy|dừng)',normalized) and re.search(r'(?:vẫn )?được giữ (?:lại|nguyên)',normalized) and not re.search(r'\bnếu\b|\bvà\b|;',normalized):
            obj=base.object_identity(normalized,'vi')
            if obj==source['object_id']:result.update(status='CONSTRAINTS_MATCH',reasons=[])
            elif obj:result.update(status='FAIL',reasons=['preserved object differs'])
    elif kind in ('transfer','use'):
        if result['status']=='FAIL':return result
        facts=base.target_roles(normalized,kind)
        if facts:
            if kind=='transfer' and facts.get('action')=='send' and facts.get('recipient') is None:
                recipients=list(re.finditer(r'\bcho ('+base.ROLE_WORD+r')\b',normalized))
                if len(recipients)==1:facts['recipient']=recipients[0][1]
            result['target_facts']=facts
            reasons=[k+' differs from source' for k in ('agent','recipient','owner','action') if k in source and facts.get(k) is not None and facts[k]!=source[k]]
            if reasons:result.update(status='FAIL',reasons=reasons)
            elif all(facts.get(k) is not None for k in source if k!='kind'):result.update(status='CONSTRAINTS_MATCH',reasons=[])
            else:result.update(status='UNKNOWN',reasons=['incomplete target role evidence'])
    result.update(source_contract=source,normalized_target=normalized,draft_modified_by_parser=False)
    return result


def feedback(contract):
    if contract and contract['kind']=='kinship':
        return 'Preserve the sibling relationship: '+'; '.join(f'{k}={v}' for k,v in contract.items() if k!='kind')
    return base.feedback(contract)


def select_attempt(history):
    """No presumed improvement from equal uncertainty; retain original valid draft."""
    if len(history)>1 and history[1]['state']=='CONSTRAINTS_MATCH' and not history[1]['structural_error']:
        return 1,'revision matches supported constraints'
    if history[0]['draft'] and not history[0]['structural_error']:
        return 0,'revision not proven better; retain original'
    if len(history)>1 and history[1]['draft'] and not history[1]['structural_error']:
        return 1,'original structurally invalid; retain valid review draft'
    return 0,'no valid draft'
