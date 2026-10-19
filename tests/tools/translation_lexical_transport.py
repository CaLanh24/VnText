"""Research-only semantic lexicon transport, preserving original opaque validation."""
from dataclasses import dataclass
import re
from tests.tools import translation_quality_guard as guard
from vntext.mt_check import structural_problems

@dataclass(frozen=True)
class Prepared:
    source: str
    working_source: str
    bindings: tuple
    reordered: bool


def prepare(row):
    source=row['source_en']; domain=row.get('domain_context','')
    if '[LEX' in source:raise ValueError('reserved lexical marker collision')
    # Quoted or opaque text is never clause-normalized; lexical matches cannot overlap opaque spans.
    working=source; reordered=False
    m=re.fullmatch(r'I would have (.+?) if I had (.+?)[.!]?',source,re.I)
    closed_past=bool(m and not guard.opaque_tokens(source) and not re.search(r'["“”\n?]',source) and not re.search(r'\b(?:if|unless|provided|although|but|and)\b',m[1]+' '+m[2],re.I))
    terms={}
    if closed_past:terms.update({'I would have':'tôi hẳn đã','if I had':'nếu trước đó tôi đã'})
    if re.search(r'\b(?:database|transactions?)\b',domain,re.I):terms['roll back']='hoàn tác'
    if re.search(r'\b(?:engineering|measurement|control)\b',domain,re.I):
        terms['sensor']='cảm biến'
        terms.update({'pressure sensor':'cảm biến áp suất','temperature sensor':'cảm biến nhiệt độ','humidity sensor':'cảm biến độ ẩm','temperature switch':'công tắc nhiệt độ','safety switch':'công tắc an toàn','power switch':'công tắc nguồn'})
        if re.search(r'\b(?:the|a|temperature|pressure|safety|power) switch\b',source,re.I):terms['switch']='công tắc'
        if re.search(r'\b(?:a|the|each|one) reading\b',source,re.I):terms['reading']='giá trị đo'
    if re.search(r'\b(?:business|invoice|receipt)\b',domain,re.I):
        terms['receipt']='biên lai'
        if re.search(r'\b(?:the|an|this|that|your|my) invoice\b',source,re.I):terms['invoice']='hóa đơn'
    # Abstain on quoted terminology instead of interpreting UI literals or titles.
    if re.search(r'["“”]',source):terms={}
    opaque=guard.spans(working); matches=[]
    for term,target in terms.items():
        for m in re.finditer(r'(?<!\w)'+re.escape(term)+r'(?!\w)',working,re.I):
            if not any(m.start()<end and m.end()>start for start,end,_ in opaque):
                matches.append((m.start(),m.end(),target))
    matches.sort(key=lambda x:(x[0],-(x[1]-x[0])))
    picked=[]; stop=0
    for item in matches:
        if item[0]>=stop:picked.append(item);stop=item[1]
    matches=picked;bindings=[]
    for i,(start,end,target) in enumerate(matches):bindings.append((f'[LEX{i:03}]',target))
    for (start,end,_),(marker,_) in reversed(list(zip(matches,bindings))):working=working[:start]+marker+working[end:]
    return Prepared(source,working,tuple(bindings),reordered)


def restore(prepared,protected,raw):
    # First enforce existing carrier occurrence/order and original structural tokens.
    value=guard.restore(protected,raw)
    for marker,target in prepared.bindings:
        if value.count(marker)!=1:raise ValueError('lexical carrier occurrence changed')
        if not value[:value.index(marker)].strip():target=target[0].upper()+target[1:]
        value=value.replace(marker,target)
    if '[LEX' in value:raise ValueError('unknown lexical carrier')
    if guard.opaque_tokens(value)!=guard.opaque_tokens(prepared.source):raise ValueError('original opaque sequence changed')
    problems=structural_problems({'source_text':prepared.source},value)
    if problems:raise ValueError('original structural gate: '+'; '.join(problems))
    return value
