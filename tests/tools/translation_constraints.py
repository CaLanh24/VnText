"""Test-only finite source/target constraint grammar. MATCH is not translation acceptance."""
from dataclasses import dataclass,asdict
import re
from tests.tools.translation_quality_semantic_transport import role_pair
from tests.tools.translation_quality_guard import opaque_tokens


def plain(text):
    return re.sub(r'\s+',' ',re.sub(r'<[^>]*>','',text)).strip().rstrip('.!?').casefold()


@dataclass(frozen=True)
class Formula:
    condition:str
    action:str
    relation:str
    condition_positive:bool=True
    action_positive:bool=True
    object_id:str=''

    def __post_init__(self):
        if self.relation not in ('if','only_if'):raise ValueError('unsupported relation')

    def allowed(self):
        """Truth rows in order (condition, action) = 00,01,10,11."""
        rows=[]
        for p,a in ((False,False),(False,True),(True,False),(True,True)):
            c=p if self.condition_positive else not p
            act=a if self.action_positive else not a
            rows.append((not c or act) if self.relation=='if' else (not act or c))
        return tuple(rows)


def condition(text,language):
    s=plain(text)
    if re.search(r'\b(and|or|unless|if)\b|\bvà\b|\bhoặc\b',s):return None
    if language=='en':
        positive=not bool(re.search(r'\bnot\b',s))
        patterns=(('user_confirmation',r'\buser\b.*\b(confirm|confirms|approve|approves|agree|agrees)\b'),
                  ('operator_confirmation',r'\boperator\b.*\b(confirm|confirms|approve|approves)\b'),
                  ('signature_valid',r'\bsignature\b.*\bvalid\b'),
                  ('checksum_valid',r'\bchecksum\b.*\bvalid\b'),
                  ('signature_verified',r'\bverified signatures?\b|\bsignatures? (?:are |is )?verified\b'))
    else:
        positive=not bool(re.search(r'\b(không|chưa)\b',s))
        patterns=(('user_confirmation',r'người dùng.*(?:xác nhận|phê duyệt|đồng ý|chấp thuận)'),
                  ('operator_confirmation',r'người (?:vận hành|điều khiển).*(?:xác nhận|phê duyệt|đồng ý)'),
                  ('signature_valid',r'chữ ký.*hợp lệ'),('checksum_valid',r'mã kiểm tra.*hợp lệ'),
                  ('signature_verified',r'chữ ký.*(?:xác minh|xác thực)'))
    found=[name for name,rx in patterns if re.search(rx,s)]
    token=re.search(r'(\{[^{}]+\})',s)
    if token and ((language=='en' and re.search(r'\bconfirms?\b',s)) or (language=='vi' and 'xác nhận' in s)):
        found.append('confirmation:'+token[1])
    return (found[0],positive) if len(found)==1 else None


def action(text,language):
    s=plain(text)
    if re.search(r'\b(and|or)\b|\bvà\b|\bhoặc\b|;',s):return None
    if language=='en':
        s=re.sub(r'^(?:please )?','',s)
        positive=not s.startswith('do not ')
        s=re.sub(r'^do not ','',s)
        patterns=(('reject',r'^reject '),('accept',r'^accept '),('overwrite',r'^overwrite '),
                  ('delete',r'^(?:delete|erase|remove) '),('unchanged',r'^(?:keep .+ unchanged|leave .+ untouched)$'),
                  ('release',r'^released$'),('export',r'^exported$'))
    else:
        s=re.sub(r'^(?:hãy |vui lòng )','',s)
        positive=not bool(re.match(r'^(đừng |không được |không )',s))
        s=re.sub(r'^(đừng |không được |không )','',s)
        patterns=(('reject',r'^từ chối '),('accept',r'^chấp nhận '),('overwrite',r'^ghi đè '),
                  ('delete',r'^(xóa|xoá|gỡ bỏ) '),
                  ('unchanged',r'^(giữ nguyên .+|giữ .+ nguyên vẹn|để .+ không bị thay đổi)$'),
                  ('release',r'^phát hành$'),('export',r'^xuất dữ liệu$'))
    found=[name for name,rx in patterns if re.search(rx,s)]
    if len(found)!=1:return None
    # In this finite accept/reject grammar the operations are complements.
    predicate,polarity=('reject',not positive) if found[0]=='accept' else (found[0],positive)
    object_id=object_identity(s,language)
    if predicate in ('release','export'):object_id='implicit_subject'
    return (predicate,polarity,object_id) if object_id else None


def object_identity(text,language):
    tokens=opaque_tokens(text)
    if tokens:return 'tokens:'+','.join(tokens)
    patterns=(('archive',r'\barchive\b'),('database',r'\bdatabase\b'),('backup',r'\bbackup\b'),
              ('snapshot',r'\bsnapshot\b'),('file',r'\bfiles?\b'),('record',r'\b(?:records?|entries)\b')) if language=='en' else (
              ('archive',r'(?:kho|tệp|tập tin) lưu trữ'),('database',r'cơ sở dữ liệu'),
              ('backup',r'bản sao (?:lưu|dự phòng)'),('snapshot',r'bản chụp'),
              ('file',r'\b(?:tệp|tập tin)\b'),('record',r'bản ghi|mục nhập'))
    found=[name for name,rx in patterns if re.search(rx,text)]
    if 'archive' in found and 'file' in found:found.remove('file')
    return found[0] if len(found)==1 else None


def conditional_formula(text,language):
    s=plain(text)
    # Full sentence partition, not a keyword vote; nested clauses abstain.
    patterns=((r'^unless (.+?), (.+)$','unless',False),(r'^(.+?) unless (.+)$','unless',True)) if language=='en' else (
        (r'^(?:nếu|khi|chỉ cần) (.+?), (.+)$','if',False),(r'^chỉ khi (.+?), (.+)$','only_if',False),
        (r'^trừ khi (.+?), (.+)$','unless',False),(r'^(.+?) trừ khi (.+)$','unless',True),
        (r'^(.+?) (?:nếu|khi) (.+)$','if',True))
    for rx,relation,reverse in patterns:
        m=re.fullmatch(rx,s)
        if not m:continue
        c,a=(m[2],m[1]) if reverse else (m[1],m[2])
        cp,ap=condition(c,language),action(a,language)
        if cp and ap:
            return Formula(cp[0],ap[0],'only_if' if relation=='only_if' else 'if',
                           not cp[1] if relation=='unless' else cp[1],ap[1],ap[2])
        return None
    rx=r'^only (.+?) may be (released|exported)$' if language=='en' else r'^chỉ (.+?) mới (?:được |có thể )?(phát hành|xuất dữ liệu)$'
    m=re.fullmatch(rx,s)
    if m:
        cp,ap=condition(m[1],language),action(m[2],language)
        if cp and ap:return Formula(cp[0],ap[0],'only_if',cp[1],ap[1],ap[2])
    return None


def source_contract(row):
    s=plain(row['source_en']);pair=role_pair(row.get('address_context',''))
    if re.search(r'["“”]|\b(?:he|she|they|their)\b',s):return None
    if pair:
        kin=re.search(r'\b(i am your|you are my) (younger brother|older brother|younger sister|older sister|sister|brother)\b',s)
        if kin:
            subject,owner=pair if kin[1]=='i am your' else (pair[1],pair[0])
            age='younger' if 'younger' in kin[2] or subject=='em' else 'older'
            return dict(kind='kinship',subject=subject,owner=owner,age=age,gender='female' if 'sister' in kin[2] else 'male')
        if re.fullmatch(r'i (?:can |will |may )?(lend|send|bring|show) you my .+',s) and not re.search(r'\b(?:if|unless|and|while|but|or|not)\b',s):
            return dict(kind='transfer',agent=pair[0],recipient=pair[1],owner=pair[0],action=re.search(r'\b(lend|send|bring|show)\b',s)[1])
        if re.fullmatch(r'(?:could|would|can) you (lend|show) me your .+',s) and not re.search(r'\b(?:if|unless|and|while|but|or|not)\b',s):
            return dict(kind='transfer',agent=pair[1],recipient=pair[0],owner=pair[1],action=re.search(r'\b(lend|show)\b',s)[1])
        if re.fullmatch(r'you may (borrow|use) my .+',s) and not re.search(r'\b(?:and|while|if)\b',s):
            return dict(kind='use',agent=pair[1],owner=pair[0],action='borrow' if 'borrow' in s else 'use')
    formula=conditional_formula(s,'en')
    if formula:return dict(kind='conditional',formula=asdict(formula),truth= formula.allowed())
    m=re.fullmatch(r'keep (rejected|unverified|unchecked|unresolved) .+ outside .+ (?:eligible|allowed|permitted) for (export|release|patching)',s)
    if m:return dict(kind='exclusion',entry_class=m[1],operation=m[2])
    if re.fullmatch(r'(?:canceling|aborting|stopping) .+ must (?:preserve .+|leave .+ intact|not (?:delete|erase|remove) .+)',s):
        obj=object_identity(s,'en')
        return dict(kind='cancellation_preserves_data',object_id=obj) if obj else None
    return None


ROLE_WORD=r'(?:giáo sư|chị|anh|em|mẹ|con|tôi|bạn|ông|bà)'


def target_roles(text,kind):
    s=plain(text)
    if re.search(r'\bvà\b|\bhoặc\b|;',s):return None
    subject=re.match(r'^('+ROLE_WORD+r')\b',s)
    if not subject:return None
    agent=subject[1]
    if re.search(r'\b(các|những|chúng|bọn)\b',s):return dict(error='plural_or_added_participants')
    owner=re.search(r'\bcủa ('+ROLE_WORD+r'|mình)\b',s)
    owner_value=(agent if owner[1]=='mình' else owner[1]) if owner else None
    recipient=None;verb=None
    lend=re.search(r'\bcho (.+?) mượn\b',s)
    if lend:
        verb='lend';recipient=lend[1]
    elif re.search(r'\bgửi\b',s):
        verb='send'
        m=re.search(r'\bgửi (?:cho )?('+ROLE_WORD+r')\b',s)
        if m:recipient=m[1]
    elif re.search(r'\bmang\b',s):
        verb='bring';m=re.search(r'\bcho ('+ROLE_WORD+r')\b',s)
        if m:recipient=m[1]
    elif re.search(r'\bxem\b',s) and re.search(r'\bcho ('+ROLE_WORD+r')\b',s):
        verb='show';recipient=re.search(r'\bcho ('+ROLE_WORD+r')\b',s)[1]
    elif re.search(r'\bmượn\b',s):verb='borrow'
    elif re.search(r'\bsử dụng\b|\bdùng\b',s):verb='use'
    if recipient and re.fullmatch(ROLE_WORD,recipient) is None:return None
    facts=dict(agent=agent,owner=owner_value,action=verb)
    if kind=='transfer':facts['recipient']=recipient
    return facts


def audit_constraints(row,draft):
    source=source_contract(row)
    result=dict(status='UNKNOWN',source_contract=source,target_facts=None,reasons=[])
    if opaque_tokens(row['source_en'])!=opaque_tokens(draft):
        return {**result,'status':'FAIL','reasons':['protected syntax differs']}
    if source is None:return {**result,'reasons':['source grammar unsupported']}
    if re.search(r'["“”]',draft):return {**result,'reasons':['quoted target scope unsupported']}
    kind=source['kind'];d=plain(draft)
    if kind=='kinship':
        if re.search(r'nhưng|không đúng|không phải',d):return {**result,'reasons':['kinship negation/contrast scope unsupported']}
        facts=list(re.finditer(r'('+ROLE_WORD+r') (?:là|chính là) (em trai|anh trai|chị gái|em gái) của ('+ROLE_WORD+r')',d))
        if len(facts)==1:
            m=facts[0];term=m[2]
            target=dict(subject=m[1],owner=m[3],age='younger' if term.startswith('em ') else 'older',gender='male' if term.endswith('trai') else 'female')
            result['target_facts']=target
            result['reasons']=[key+' differs from source' for key in target if target[key]!=source[key]]
            result['status']='FAIL' if result['reasons'] else 'CONSTRAINTS_MATCH'
        else:result['reasons']=['kinship proposition missing/ambiguous']
    elif kind in ('transfer','use'):
        # Additional/plural counterpart is an explicit contradiction for one-person metadata.
        pair=role_pair(row.get('address_context',''))
        if pair and any(re.search(r'\b(?:các|những) '+re.escape(p)+r'\b',d) for p in pair):
            return {**result,'status':'FAIL','reasons':['plural listener/speaker contradicts explicit single participant']}
        if pair and (re.search(re.escape(pair[1])+r' và '+re.escape(pair[0]),d) or re.search(re.escape(pair[0])+r' và '+re.escape(pair[1]),d)):
            return {**result,'status':'FAIL','reasons':['added participant in recipient/owner relation']}
        facts=target_roles(d,kind);result['target_facts']=facts
        if not facts:return {**result,'reasons':['target role grammar unsupported']}
        for key in ('agent','recipient','owner','action'):
            if key not in source:continue
            if facts.get(key) is not None and facts[key]!=source[key]:result['reasons'].append(key+' differs from source')
        if result['reasons']:result['status']='FAIL'
        elif all(facts.get(k) is not None for k in source if k!='kind'):result['status']='CONSTRAINTS_MATCH'
        else:result['reasons']=['incomplete target role evidence']
    elif kind=='conditional':
        target=conditional_formula(d,'vi')
        result['target_facts']=asdict(target) if target else None
        if target:
            expected=Formula(**source['formula'])
            if (target.condition,target.action,target.object_id)!=(expected.condition,expected.action,expected.object_id):
                result.update(status='FAIL',reasons=['condition/action/object identity differs'])
            elif target.allowed()!=expected.allowed():
                result.update(status='FAIL',reasons=['condition/polarity truth table differs'])
            else:result['status']='CONSTRAINTS_MATCH'
        else:result['reasons']=['target condition grammar unsupported']
    elif kind=='exclusion':
        operation={'export':r'xuất (?:dữ liệu|bản)','release':r'phát hành','patching':r'(?:vá|bản vá)'}[source['operation']]
        cls={'rejected':r'bị từ chối','unverified':r'chưa (?:được )?xác minh','unchecked':r'chưa (?:được )?kiểm tra','unresolved':r'chưa (?:được )?giải quyết'}[source['entry_class']]
        negative_operation=operation+(r'|xuất khẩu|export' if source['operation']=='export' else '')
        if re.search(negative_operation,d) and re.search(r'vẫn (?:có thể|được phép|được)',d):
            result.update(status='FAIL',reasons=['excluded entries still eligible in target'])
        elif re.search(cls,d) and re.search(r'\btrong\b.+(?:đủ điều kiện|được phép)',d):
            result.update(status='FAIL',reasons=['outside eligibility changed to inside'])
        elif re.search(cls,d) and re.search(r'\bngoài\b.+(?:đủ điều kiện|được phép)',d) and re.search(operation,d) and not re.search(r'\bvà\b|;',d):
            result['status']='CONSTRAINTS_MATCH'
        else:result['reasons']=['target exclusion grammar unsupported']
    else:
        if re.match(r'^(?:đừng|không được) hủy',d):
            result.update(status='FAIL',reasons=['prohibits cancellation instead of deleting data'])
        elif re.search(r'(?:hủy|dừng)',d) and (re.search(r'(?:giữ|bảo toàn).+(?:nguyên vẹn|bản sao|dữ liệu)',d) or re.search(r'không (?:được )?(?:xóa|xoá|làm mất|gỡ bỏ)',d)) and not re.search(r'\bvà\b|\bnếu\b|;',d):
            obj=object_identity(d,'vi')
            if obj==source['object_id']:result['status']='CONSTRAINTS_MATCH'
            elif obj:result.update(status='FAIL',reasons=['preserved object differs'])
            else:result['reasons']=['preserved object unknown']
        else:result['reasons']=['target preservation grammar unsupported']
    return result


def feedback(contract):
    if contract is None:return 'Preserve the original meaning; do not invent relationships.'
    kind=contract['kind']
    if kind in ('transfer','use'):
        return '; '.join(f'{k}: {v}' for k,v in contract.items() if k!='kind')+'. One participant per role; do not add a recipient.'
    if kind=='conditional':
        return 'Preserve this implication: '+'; '.join(f'{k}={v}' for k,v in contract['formula'].items())
    if kind=='exclusion':return 'These entries are NOT eligible for '+contract['operation']+'. Keep them OUTSIDE that eligible set.'
    return 'Cancellation must preserve the data. Do not turn this into a prohibition on cancellation.'
