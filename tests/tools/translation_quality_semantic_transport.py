"""Research-only explicit-role carriers and conservative English logic paraphrases."""
from dataclasses import dataclass
import re

ROLE = re.compile(r'ROLEVNT\d{3}X')


def role_pair(metadata):
    c=metadata.casefold()
    if 'younger brother to older sister' in c:return 'em','chị'
    if 'older sister' in c and 'younger brother' in c:return 'chị','em'
    if 'older brother to younger sister' in c:return 'anh','em'
    if 'mother' in c and 'daughter' in c:return 'mẹ','con'
    if 'student' in c and 'professor' in c:return 'em','giáo sư'
    return None


@dataclass(frozen=True)
class Roles:
    text:str
    replacements:tuple


def mask_roles(text,metadata):
    if 'ROLEVNT' in text:raise ValueError('reserved role carrier collision')
    pair=role_pair(metadata)
    if not pair:return Roles(text,())
    replacements=[]
    # These are grammatical I/you tokens only; never mask quoted text, contractions,
    # third-person subjects, kinship nouns, or arbitrary English possessives.
    if re.search(r'["“”]|\b(?:I|you)[’\']',text,re.I):return Roles(text,())
    def replace(m):
        marker=f'ROLEVNT{len(replacements):03}X'
        value=pair[0] if m.group().casefold() in ('i','me','my','mine') else pair[1]
        replacements.append((marker,value))
        return marker
    masked=re.sub(r'(?<![\w])(?:I|me|my|mine|you|your|yours)(?![\w])',replace,text,flags=re.I)
    return Roles(masked,tuple(replacements))


def restore_roles(roles,raw):
    expected=[m for m,_ in roles.replacements]
    if ROLE.findall(raw)!=expected:raise ValueError('role carriers missing/extra/reordered/duplicated')
    remainder=ROLE.sub('',raw)
    if 'ROLEVNT' in remainder:raise ValueError('damaged role carrier')
    # A generated generic pronoun would bypass the explicit role contract.
    if expected and re.search(r'(?<!\w)(tôi|bạn|ông|bà)(?!\w)',remainder,re.I):
        raise ValueError('unbound generated role pronoun')
    for marker,value in roles.replacements:raw=raw.replace(marker,value)
    return raw


def paraphrase_logic(source):
    """Only affirmative unless-copula and explicit confirmation patterns are supported."""
    m=re.fullmatch(r'Unless (.+?) (is|are) ([^,]+), (.+)',source,re.I)
    if m and not re.search(r'\b(?:not|never|no|only|unless|if)\b',m[1]+' '+m[3],re.I):
        return f'If {m[1]} {m[2]} not {m[3]}, {m[4]}','unless_copula'
    m=re.fullmatch(r'Unless (the (?:user|operator)) (confirms|approves|consents), (.+)',source,re.I)
    if m:
        infinitive={'confirms':'confirm','approves':'approve','consents':'consent'}[m[2].casefold()]
        return f'If {m[1]} does not {infinitive}, {m[3]}','unless_confirmation'
    return source,None


def relationship_contradictions(metadata,output):
    """Reject explicit self-kinship contradictions only, not arbitrary kinship mentions."""
    pair=role_pair(metadata)
    if not pair:return []
    wrong={('chị','em'):r'chị (?:là|chính là) (?:người )?em gái',
           ('anh','em'):r'anh (?:là|chính là) (?:người )?em trai',
           ('em','chị'):r'em (?:là|chính là) (?:người )?anh trai'}
    pattern=wrong.get(pair)
    return ['explicit_sibling_age_contradiction'] if pattern and re.search(pattern,output,re.I) else []
