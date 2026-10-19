"""Logged subject/recipient span corrections in explicit closed I/you frames only."""
import re
from tests.tools.translation_constraints_v2 import source_contract
from tests.tools.translation_quality_guard import spans,opaque_tokens
from vntext.mt_check import structural_problems


def bind_metadata_roles(row,draft):
    contract=source_contract(row)
    if not contract or contract['kind'] not in ('transfer','use') or re.search(r'["“”]',draft):return draft,[]
    edits=[];protected=spans(draft)
    noun=r'(?:các |những )?(?:giáo sư|ông|bà|thầy|cô|chị|anh|em|mẹ|con)(?!\w| ấy\b)'
    def consider(m,expected,field):
        start,end=m.span('role');old=m['role'];lower=old.casefold()
        if any(a<=start<b for a,b,_ in protected):return
        value=None
        if lower in ('các '+expected,'những '+expected):value=expected
        elif expected=='giáo sư' and lower in ('ông','bà','thầy','cô'):value=expected
        if value is not None:
            if start==0 and old[0].isupper():value=value[0].upper()+value[1:]
            edits.append(dict(start=start,end=end,before=old,after=value,role_field=field,evidence='explicit closed source role graph'))
    subject=re.match(r'^(?P<role>'+noun+r')\b',draft,re.I)
    if subject:consider(subject,contract['agent'],'agent')
    if contract['kind']=='transfer':
        action=contract['action']
        if action in ('lend','show'):
            patterns=[r'\bcho (?P<role>'+noun+r') (?:mượn|xem)\b']
        elif action=='send':
            patterns=[r'\bgửi (?:cho )?(?P<role>'+noun+r')\b',r'\bcho (?P<role>'+noun+r')\b']
        else:patterns=[r'\bcho (?P<role>'+noun+r')\b']
        found={m.span('role'):m for rx in patterns for m in re.finditer(rx,draft,re.I)}
        if len(found)==1:consider(next(iter(found.values())),contract['recipient'],'recipient')
    # Edits are nonoverlapping and replayable against the input after generic binding.
    result=draft
    for edit in sorted(edits,key=lambda e:e['start'],reverse=True):result=result[:edit['start']]+edit['after']+result[edit['end']:]
    if opaque_tokens(result)!=opaque_tokens(draft) or structural_problems({'source_text':row['source_en']},result):
        raise ValueError('explicit role binding violated source structure')
    return result,edits
