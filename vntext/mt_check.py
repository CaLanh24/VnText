"""Shared validation logic for machine translation apply/QA.

Used by mt_apply (per-batch hard gate) and mt_qa (whole-file audit).
Nothing here mutates translation.csv.
"""
import json
import re
import unicodedata
from pathlib import Path
from functools import lru_cache

from vntext.mt_paths import paths_for_csv

PH = re.compile(r'\$?\{[^{}]*\}')

# A TextMeshPro tag opens with a letter, a closing slash, or '#' (hex colour).
# Requiring that prevents comparison operators from being mistaken for a tag:
# Comparisons such as ``Reputation<=0`` would otherwise
# match <...> as one giant "tag" and make every translation of it fail.
TAG = re.compile(r'</?[A-Za-z#][^<>]*>')
WORD = re.compile(r'[^\W\d_]+', re.UNICODE)
HEART = '\u2661'
BRACKET_TOKEN = re.compile(r'\[[A-Za-z][A-Za-z0-9_:-]*\]')
# Hashtags are protected display labels, not English prose tokens.
HASHTAG = re.compile(r'#[A-Za-z0-9_À-ỹ]+')

# ---------------------------------------------------------------- placeholders

# A "lexical" placeholder is one that the _synonyms table expands into an actual
# word. Those are ALL-CAPS letters, optionally with digits/underscore. Anything
# containing lowercase letters, arithmetic operators, parentheses or '%' is code
# (a variable or an expression) and must never be touched.
LEXICAL_PH = re.compile(r'\{([A-Z][A-Z0-9_]*)\}')
CODE_PH_CHARS = re.compile(r'[a-z+\-*/%().]')

# All-caps placeholders that are still engine variables, not vocabulary.
NON_LEXICAL_UPPER = {'SNSDM', 'MOD', 'BP', 'AP', 'TP', 'STR', 'DEPRESSION'}

ENG_SUFFIX = re.compile(
    r'\{([A-Z][A-Z0-9_]*)\}(ing|ed|es|ly|s|e)(?![^\W\d_])',
    re.UNICODE,
)


def lexical_placeholders(text):
    out = []
    for m in LEXICAL_PH.finditer(text):
        name = m.group(1)
        if name in NON_LEXICAL_UPPER:
            continue
        out.append(name)
    return out


def english_suffix_hits(text):
    """Return [(placeholder, suffix)] for English inflection glued onto a
    lexical placeholder, e.g. '{FUCK}ed', '{EJACULATE}s', '{ROUGH}ly'.

    Deliberately ignores code placeholders and engine variables so that valid
    expressions such as '{iWillpower*5}' or '{SNSDM}' are never flagged.
    """
    hits = []
    for m in ENG_SUFFIX.finditer(text):
        name, suffix = m.group(1), m.group(2)
        if name in NON_LEXICAL_UPPER:
            continue
        hits.append((name, suffix))
    return hits


# ------------------------------------------------------- Vietnamese phonotactics

_ONSETS = [
    'ngh', 'ng', 'nh', 'ch', 'gh', 'gi', 'kh', 'ph', 'qu', 'th', 'tr',
    'b', 'c', 'd', 'g', 'h', 'k', 'l', 'm', 'n', 'p', 'r', 's', 't', 'v', 'x',
    '',
]

# Rhymes reachable without any diacritic (level tone, plain vowels only).
_BARE_RHYMES = set("""
a ac ach ai am an ang anh ao ap at au ay
e ec em en eng eo ep et
i ia ich im in inh ip it iu
o oa oac oach oai oam oan oang oanh oao oap oat oay oc oe oen oeo oi om on
ong ooc oong op ot
u ua uac uan uang uanh uat uay uc ue uech uenh ui um un ung uo up ut uy uya
uych uyn uynh uyp uyt uyu
y ych ynh
""".split())

_ONSETS_SORTED = sorted(_ONSETS, key=len, reverse=True)


def is_plain_ascii_word(tok):
    return all('a' <= c <= 'z' or 'A' <= c <= 'Z' for c in tok)


def is_possible_vietnamese(tok):
    """True if the (diacritic-free) token could be a Vietnamese syllable."""
    t = tok.lower()
    for onset in _ONSETS_SORTED:
        if t.startswith(onset):
            if t[len(onset):] in _BARE_RHYMES:
                return True
    return False


def has_vietnamese_diacritic(tok):
    if 'đ' in tok or 'Đ' in tok:
        return True
    for c in unicodedata.normalize('NFD', tok):
        if unicodedata.combining(c):
            return True
    return False


def is_vietnamese_text(text):
    """True if the string carries Vietnamese-specific diacritics.

    Used to recognise rows whose source_text is *already* Vietnamese - the game
    ships a partial Vietnamese UI, so for those rows keeping the same string is
    a correct translation, not a missing one.
    """
    return has_vietnamese_diacritic(strip_technical(text))


# ------------------------------------------------------------- English lexicons

# Words that cannot be Vietnamese syllables are caught by phonotactics, so this
# list only needs the English words that *are* phonotactically legal in
# Vietnamese. Split by confidence: STRONG on its own is enough to flag a line;
# WEAK needs a second signal (the user explicitly warned about 'to').
ENG_STRONG = set("""
hello
the that them then than this these those there their they
him his her hers hers she who whom whose what when where which while
have has had having been being does doesn dont didn wasn weren
about above after again against almost alone along already also although
always among another answer anyone anything around because before behind
below beside between beyond both bring brought
came come coming could couldn
even ever every everyone everything
from front full
give given going gone good great
here how however
into itself
just keep kept know known
least less letting like little look looked looking love
made make making many maybe mean means might more most much must myself
need needs never next nothing
often once only other others ought outside over
people perhaps please pretty
really right
same said saying seem seems since some something soon still such sure
take taken talk tell than thank thing things think thought through time
today together tonight took toward
under until upon used using
very
want wanted watch water week well went were what whatever will with within
without woman women wonder word work world would wouldn
year yes yet you your yours yourself
cock cunt pussy dick balls cum cums cumming fuck fucking fucked shit
ass asshole tits titties boobs nipple nipples clit slut whore bitch
moan moaning suck sucking lick licking thrust thrusting orgasm
""".split())

ENG_WEAK = set("""
a all am an and any are as at be but by can day do for get go had he
her him his i if in is it its let man may me men my no not of on one
or our out say see so ten to too two up us was way we
hot big bad bit cut hit lot new now old set sit top
""".split())

# Tokens that are safe to retain in Latin script across generic projects.
# Proper names and domain terms belong in a package/user glossary, not here.
DEFAULT_WHITELIST = {
    'mod', 'mods', 'email', 'internet', 'online', 'wifi', 'app', 'web', 'link',
    'menu', 'game', 'save', 'load', 'auto', 'skip', 'log', 'tips', 'hints',
    'fps', 'ui', 'id', 'ok', 'debug', 'video', 'audio', 'camera', 'robot',
    'warning', 'data', 'text', 'org', 'url', 'api', 'json', 'csv', 'xml',
    'ah', 'oh', 'aww', 'aw', 'eh', 'eww', 'hmm', 'ugh', 'wow', 'whoa',
    'okay', 'yeah', 'hey', 'heh', 'hehe', 'gasp', 'gulp', 'giggle', 'sob',
    'cough', 'uh', 'huh', 'mmh', 'ngh', 'ng',
}

# Lowercase source words are not opaque by default: unknown English prose must
# remain visible to the quality gate. Keep only a small, explicit set of common
# loanwords that the game may retain in Vietnamese output.
DEFAULT_SOURCE_LITERALS = frozenset({'bar', 'cocktail', 'karaoke', 'sushi'})


def source_proper_name_tokens(src, whitelist=None):
    """Return conservative source name-like tokens safe to retain in MT output.

    Character/location names commonly stay in Latin script inside an otherwise
    translated sentence. They are not a global whitelist: title/camel-case
    tokens and a lowercase location name in an explicit ``in/at ... city``
    context are eligible; ordinary unknown lowercase prose is not.
    """
    known = set(whitelist or ()) | ENG_STRONG | ENG_WEAK
    out = set()
    from vntext.mt_translation_constants import generic_term_translation

    body = strip_technical(str(src or ""))
    matches = list(re.finditer(r"[A-Za-z]+", body))
    for index, match in enumerate(matches):
        token = match.group(0)
        if (
            len(token) >= 2
            and is_plain_ascii_word(token)
            and (
                re.fullmatch(r"[A-Z][a-z]+", token)
                or re.search(r"[a-z][A-Z]", token)
            )
            and token.casefold() not in known
            and generic_term_translation(token) is None
        ):
            out.add(token.casefold())
            continue
        if (
            len(token) >= 3
            and is_plain_ascii_word(token)
            and token.casefold() not in known
            and generic_term_translation(token) is None
            and index > 0
            and index + 1 < len(matches)
            and matches[index - 1].group(0).casefold()
            in {"in", "at", "from", "near", "to"}
            and matches[index + 1].group(0).casefold()
            in {"city", "town", "village", "river", "lake", "mountain", "place"}
        ):
            out.add(token.casefold())
    return out


def source_literal_tokens(src, whitelist=None, *, strict=False):
    """Return opaque source tokens that may legitimately remain byte-for-byte.

    Proper names are handled separately by :func:`source_proper_name_tokens`.
    Unknown lowercase source words stay strict when ``strict`` is requested so
    an untranslated English word cannot hide behind the literal-token
    exemption. The default keeps the protection path backward-compatible for
    names/acronyms/loanwords that must survive CT2 unchanged.
    """
    known = set(whitelist or ()) | ENG_STRONG | ENG_WEAK
    from vntext.mt_translation_constants import generic_term_translation
    sfx_literals = {
        match.group(1).casefold()
        for match in re.finditer(r'\*([A-Za-z][A-Za-z0-9_-]*)\*', str(src or ""))
    }

    return {
        token.casefold()
        for token in WORD.findall(strip_technical(str(src or "")))
        for mapped in (generic_term_translation(token),)
        if (
            is_plain_ascii_word(token)
            and token.casefold() not in known
            and (
                not strict
                or token.casefold() in DEFAULT_SOURCE_LITERALS
                or token.casefold() in sfx_literals
            )
            # A same-spelling generic term is still required for an explicit
            # literal, so mapped-to-Vietnamese words remain strict.
            and (mapped is None or mapped.casefold() == token.casefold())
        )
    }


def _package_dir(package_dir: Path | str | None) -> Path | None:
    if package_dir is None:
        return None
    p = Path(package_dir)
    if p.is_file():
        return p.parent
    return p


def load_whitelist(package_dir: Path | str | None = None):
    wl = set(DEFAULT_WHITELIST)
    root = _package_dir(package_dir)
    if root is None:
        return wl
    path = paths_for_csv(root / "translation.csv").whitelist
    if path.exists():
        with path.open(encoding='utf-8') as f:
            data = json.load(f)
        for t in data.get('tokens', []):
            wl.add(t.lower())
    return wl


def load_cleared(package_dir: Path | str | None = None):
    """Rows already reviewed by hand, as {key: reason}."""
    root = _package_dir(package_dir)
    if root is None:
        return {}
    path = paths_for_csv(root / "translation.csv").whitelist
    if not path.exists():
        return {}
    with path.open(encoding='utf-8') as f:
        data = json.load(f)
    return dict(data.get('cleared', {}))


def load_policy_skipped(package_dir: Path | str | None = None, active_only=True):
    root = _package_dir(package_dir)
    if root is None:
        return {}
    path = paths_for_csv(root / "translation.csv").policy
    if not path.exists():
        return {}
    with path.open(encoding='utf-8') as f:
        data = json.load(f)
    out = {}
    for k, v in data.get('skipped', {}).items():
        if isinstance(v, dict):
            if active_only and v.get('resolved'):
                continue
            out[k] = v.get('reason', '')
        else:
            out[k] = str(v)
    return out


def identical_reason(src, ctx, whitelist=None):
    """Why translation == source_text is acceptable, or 'SUSPICIOUS'."""
    if whitelist is None:
        whitelist = load_whitelist()
    if is_script_identifier(src, ctx):
        return 'naninovel label / actor id'
    stripped = strip_technical(src).strip()
    if not stripped:
        return 'placeholder/tag only'
    if not WORD.findall(stripped):
        return 'punctuation/number only'
    if COND_EXPR.search(src):
        return 'condition expression'
    toks = WORD.findall(stripped)
    if toks and all(is_onomatopoeia(t) or t.lower() in whitelist for t in toks):
        if all(is_onomatopoeia(t) for t in toks):
            return 'moan / sound effect'
        return 'proper noun / kept term'
    if is_vietnamese_text(src):
        return 'source already Vietnamese'
    return 'SUSPICIOUS'


def strip_technical(text):
    """Remove placeholders, tags and escape sequences before language checks."""
    t = PH.sub(' ', text)
    t = TAG.sub(' ', t)
    t = BRACKET_TOKEN.sub(' ', t)
    t = HASHTAG.sub(' ', t)
    t = t.replace('\\n', ' ')
    return t


KEY_PREFIX = re.compile(r'^[A-Za-z][A-Za-z0-9_]*(\.[A-Za-z][A-Za-z0-9_]*)*:\s')
# Stat/HUD conditions: Submissive>=90, Corruption<50, Attractiveness+Pheromones>=400
COND_EXPR = re.compile(
    r'[A-Za-z_][A-Za-z0-9_]*(?:\+[A-Za-z_][A-Za-z0-9_]*)*'
    r'\s*(<=|>=|<|>|==|!=|=)\s*-?\d+(?:\.\d+)?'
)

SCRIPT_IDENT = re.compile(r'^[A-Za-z][A-Za-z0-9_.\-]*$')
HEX_COLOR = re.compile(r'^#[0-9A-Fa-f]{3,8}$')
TRIPLED_LETTER = re.compile(r'(.)\1\1', re.I)
LAUGH = re.compile(r'^[aeiou]*(?:h[aeiou]+){2,}h*$', re.I)
BREATH = re.compile(r'^(?=[haeiou]*(.)\1)[haeiou]{3,}$', re.I)
ROMAN_NUMERAL = re.compile(r'^(?:M{0,3})(?:CM|CD|D?C{0,3})(?:XC|XL|L?X{0,3})(?:IX|IV|V?I{0,3})$', re.I)


@lru_cache(maxsize=4096)
def is_onomatopoeia(tok):
    """`Haaah`, `Nggggh`, `Hahaha`, `Ahehe` — a sound, not a word.

    Two shapes are recognised. Three of the same letter in a row means a
    stretched sound: English words practically never do it, moans in this game do
    it constantly. Alternating h and vowels at least twice means laughter, and the
    two-h minimum keeps the English pronoun `he` out of it.

    Short sounds that fit neither shape (`Kyaa`, `Woah`) stay in whitelist.json.
    """
    return bool(TRIPLED_LETTER.search(tok)
                or (len(tok) >= 4 and LAUGH.match(tok))
                or BREATH.match(tok))


def is_roman_numeral(tok: str) -> bool:
    """Roman numerals are labels/numbers, never residual English."""
    value = str(tok or "").strip()
    return bool(value and ROMAN_NUMERAL.fullmatch(value))


def is_script_identifier(src, ctx):
    """True for a bare token inside a Naninovel script.

    These are `# label` targets, actor ids and resource ids, all resolved by exact
    string match: `@goto .Start`, `@char Girl`, `@back Park.Wide`. The importer
    rewrites only strings that equal source_text within the same script object, so
    translating one of these renames the declaration but not every reference, and
    the jump or the character silently stops resolving. They stay in English on
    purpose. Anything holding a space or sentence punctuation is display text and
    is excluded here.

    Player-facing @choice / @print display strings are tagged by extract as
    NaninovelScript:<id>:choice|print and must not be treated as identifiers.
    """
    s = src.strip()
    if HEX_COLOR.match(s):
        return True
    ctx_s = str(ctx or "")
    if not ctx_s.startswith("NaninovelScript:"):
        return False
    # Tagged display roles from extract (Unity/Naninovel general).
    if ctx_s.endswith(":choice") or ctx_s.endswith(":print") or ":choice:" in ctx_s:
        return False
    return bool(SCRIPT_IDENT.match(s))


def english_report(src, trans, whitelist):
    """Multi-signal residual-English detection for one row.

    Returns (score, [reasons]). score >= 1 means the row needs a human look.
    """
    from vntext.mt_translation_constants import generic_term_translation

    reasons = []
    if not trans.strip():
        return 0, reasons

    body = strip_technical(trans)
    body = KEY_PREFIX.sub(' ', body)
    body = COND_EXPR.sub(' ', body)

    toks = [t for t in WORD.findall(body)]
    if not toks:
        return 0, reasons

    source_names = source_proper_name_tokens(src, whitelist)
    source_literals = source_literal_tokens(src, whitelist, strict=True)
    strong = 0
    weak = 0
    bare = 0
    bad = []
    for tok in toks:
        low = tok.lower()
        mapped = generic_term_translation(tok)
        if (
            low in whitelist
            or low in source_names
            or low in source_literals
            or (mapped is not None and mapped.casefold() == low)
            or is_onomatopoeia(tok)
            or is_roman_numeral(tok)
        ):
            continue
        if has_vietnamese_diacritic(tok):
            continue
        if not is_plain_ascii_word(tok):
            continue
        bare += 1
        if low in ENG_STRONG:
            strong += 1
            bad.append(tok)
        elif len(low) >= 2 and not is_possible_vietnamese(low):
            strong += 1
            bad.append(tok)
        elif low in ENG_WEAK and not is_possible_vietnamese(low):
            weak += 1
            bad.append(tok)

    if strong:
        reasons.append('english-token: ' + ' '.join(sorted(set(bad))[:8]))
    elif weak >= 2:
        reasons.append('english-weak: ' + ' '.join(sorted(set(bad))[:8]))

    has_diacritic = any(has_vietnamese_diacritic(t) for t in toks)
    if len(toks) >= 3 and not has_diacritic and bare / len(toks) >= 0.7:
        reasons.append('ascii-ratio %d/%d' % (bare, len(toks)))

    if trans.strip() == src.strip():
        reasons.append('identical-to-source')
    elif not is_vietnamese_text(src):
        # Overlap only means "not translated" when the source really is English.
        # Comparing two Vietnamese strings would flag every polished rewrite of
        # the game's own built-in Vietnamese UI.
        st = {t.lower() for t in WORD.findall(strip_technical(src))
              if t.lower() not in whitelist and t.lower() not in source_names
              and t.lower() not in source_literals
              and not is_onomatopoeia(t) and not is_roman_numeral(t)}
        tt = {t.lower() for t in toks
              if t.lower() not in whitelist and t.lower() not in source_names
              and t.lower() not in source_literals
              and not is_onomatopoeia(t) and not is_roman_numeral(t)}
        shared = st & tt
        if len(shared) >= 4 and st and len(shared) / len(st) >= 0.5:
            reasons.append('overlap %d/%d' % (len(shared), len(st)))

    return len(reasons), reasons


# --------------------------------------------------------------- structural gate

def is_synonym_row(row):
    return (row.get('context', '').startswith('TextAsset:_synonyms')
            or str(row.get('file_path') or '').endswith('_synonyms.txt'))


TIGHT_COMMA = re.compile(r'(?<!\d),(?=\S)(?!\d)')


def tight_commas(text):
    """Count commas with no space after them.

    Naninovel `RandPick("a,b,c")` pools are written without spaces around the
    separator, while ordinary prose always puts a space after a comma. Two or more
    tight commas therefore means the row is a pool, and the variant count must
    survive translation or the game loses randomisation — or worse, splits one
    Vietnamese sentence into two nonsense options.
    """
    return len(TIGHT_COMMA.findall(text))


def structural_problems(row, new):
    """Hard blockers. Empty list means the row is safe to write."""
    src = row['source_text']
    out = []

    if is_synonym_row(row):
        m = re.match(r'(\{[A-Za-z0-9_]+\}=)', src)
        if m and not new.startswith(m.group(1)):
            out.append('synonym prefix mismatch')
        if new.count(',') != src.count(','):
            out.append('synonym variant count %d -> %d'
                       % (src.count(',') + 1, new.count(',') + 1))
        return out

    if sorted(PH.findall(src)) != sorted(PH.findall(new)):
        out.append('placeholder mismatch')
    if sorted(TAG.findall(src)) != sorted(TAG.findall(new)):
        out.append('tag mismatch')
    if src.count('\\n') != new.count('\\n'):
        out.append('literal newline count %d -> %d'
                   % (src.count('\\n'), new.count('\\n')))
    if src.count(HEART) != new.count(HEART):
        out.append('heart glyph count %d -> %d'
                   % (src.count(HEART), new.count(HEART)))

    n_src, n_new = tight_commas(src), tight_commas(new)
    if n_src >= 2 and n_new != n_src:
        out.append('RandPick variant count %d -> %d' % (n_src + 1, n_new + 1))

    hits_new = english_suffix_hits(new)
    hits_src = set(english_suffix_hits(src))
    # Source game đôi khi có {STEM}es cố ý — chỉ chặn khi bản dịch *thêm* suffix.
    extra = [h for h in hits_new if h not in hits_src]
    if extra:
        out.append('english suffix after placeholder: '
                   + ' '.join('{%s}%s' % h for h in extra))

    return out
