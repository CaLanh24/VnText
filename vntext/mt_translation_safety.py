"""Shared translation helpers that preserve technical and structural text."""

from __future__ import annotations

from vntext.mt_translation_constants import (
    BRACKET,
    EW_AW_RX,
    HASHTAG,
    INJECTED_COLOR_TOKEN,
    LATIN_RX,
    generic_term_translation,
    SENTINEL_FMT,
    SENTINEL_LEFTOVER,
    SENTINEL_RX,
    INTERNAL_SENTINEL_RX,
    STAT_IN_COND,
    STAR_SFX,
    mt_check,
    re,
)

BRACKET_MARKER_RX = re.compile(r"\[QZEL\d{4}\]")


def strip_lexical_suffixes(text):
    def repl(match):
        name = match.group(1)
        if name in mt_check.NON_LEXICAL_UPPER:
            return match.group(0)
        return "{" + name + "}"

    return mt_check.ENG_SUFFIX.sub(repl, text)


def rewrite_cond_token(token):
    out = token
    for pattern, replacement in STAT_IN_COND:
        out = pattern.sub(replacement, out)
    return out


def apply_exact_labels(source, text):
    from vntext.mt_translation_constants import EXACT_LABELS

    out = text
    for source_label, translated_label in EXACT_LABELS:
        if source_label in source and source_label in out:
            out = out.replace(source_label, translated_label)
    return out



def collect_spans(text, *, protect_lexical=True):
    spans = []
    # File/path literals in help text are user-facing instructions.  Protect
    # the complete slash/backslash-delimited token before lexical fallbacks so
    # words such as ``Data`` or ``Text`` are not translated inside a path.
    for m in re.finditer(
        r"(?<![A-Za-z0-9_])[A-Za-z0-9_.-]+(?:(?:/|\\(?!n))[A-Za-z0-9_.-]+)+(?![A-Za-z0-9_])",
        text,
    ):
        spans.append((m.start(), m.end(), m.group(0), 'tech'))
    protected_ranges = [
        (m.start(), m.end())
        for rx in (BRACKET, HASHTAG, STAR_SFX, EW_AW_RX, mt_check.PH, mt_check.TAG, mt_check.COND_EXPR, INTERNAL_SENTINEL_RX)
        for m in rx.finditer(text)
    ]
    protected_ranges.extend((m.start(), m.end()) for m in re.finditer(r'\\n', text))
    # Protect title-case source names through the same span mechanism as tags
    # and placeholders. This prevents CT2 from silently mutating SampleName
    # while keeping common mapped words such as Shower translatable.
    source_names = mt_check.source_proper_name_tokens(text)
    source_literals = mt_check.source_literal_tokens(text, strict=True)
    for m in re.finditer(r'[A-Za-z]+', text):
        if m.group(0).casefold() not in source_names | source_literals:
            continue
        if any(start <= m.start() < end for start, end in protected_ranges):
            continue
        spans.append((m.start(), m.end(), m.group(0), 'name'))
    if protect_lexical:
        # Restore a bounded generic lexical fallback before CT2 sees the token.
        # This prevents model spelling drift while keeping the fallback independent
        # of a package, CSV key, or read-only VH oracle.
        for m in re.finditer(r"[A-Za-z]+", text):
            if any(start <= m.start() < end for start, end in protected_ranges):
                continue
            translated = generic_term_translation(m.group(0))
            # Do not split a sentence around high-frequency function words.  The
            # lexical table also contains ``and/the/of/...`` repairs for model
            # output, but protecting those words before CT2 destroys sentence
            # context and produces the very content-loss/repetition failures this
            # retry path is meant to recover.  They remain eligible for the
            # source/output postprocess repair below.
            if translated is not None and m.group(0).casefold() not in (
                mt_check.ENG_STRONG | mt_check.ENG_WEAK
            ):
                spans.append((m.start(), m.end(), translated, 'lexical'))
    for rx in (BRACKET, HASHTAG, STAR_SFX, EW_AW_RX, mt_check.PH, mt_check.TAG):
        for m in rx.finditer(text):
            spans.append((m.start(), m.end(), m.group(0), 'tech'))
    for m in re.finditer(r'\\n', text):
        spans.append((m.start(), m.end(), m.group(0), 'tech'))
    if mt_check.HEART in text:
        i = 0
        while True:
            j = text.find(mt_check.HEART, i)
            if j < 0:
                break
            spans.append((j, j + len(mt_check.HEART), mt_check.HEART, 'tech'))
            i = j + len(mt_check.HEART)
    for m in mt_check.COND_EXPR.finditer(text):
        spans.append((m.start(), m.end(), m.group(0), 'cond'))
    m = mt_check.KEY_PREFIX.match(text)
    if m:
        spans.append((m.start(), m.end(), m.group(0), 'tech'))
    spans.sort(key=lambda x: (x[0], -(x[1] - x[0])))
    picked = []
    occupied = []
    for s, e, orig, kind in spans:
        if any(s < pe and e > ps for ps, pe in occupied):
            continue
        picked.append((s, e, orig, kind))
        occupied.append((s, e))
    picked.sort(key=lambda x: x[0])
    return picked


def mask_text(text):
    prepared = strip_lexical_suffixes(text)
    spans = collect_spans(prepared)
    tokens = []
    kinds = []
    for s, e, orig, kind in spans:
        tokens.append(orig)
        kinds.append(kind)
    out = prepared
    for i in range(len(spans) - 1, -1, -1):
        s, e, orig, kind = spans[i]
        out = out[:s] + SENTINEL_FMT % i + out[e:]
    return out, tokens, kinds, prepared


def restore_text(masked, tokens, kinds):
    def repl(m):
        i = int(m.group(1))
        if i >= len(tokens):
            return m.group(0)
        tok = tokens[i]
        if i < len(kinds) and kinds[i] == 'cond':
            tok = rewrite_cond_token(tok)
        return tok
    return SENTINEL_RX.sub(repl, masked)


def split_parts(text, *, protect_lexical=True):
    """Separate opaque spans from translatable text without altering either."""
    prepared = strip_lexical_suffixes(text)
    spans = collect_spans(prepared, protect_lexical=protect_lexical)
    parts = []
    position = 0
    for start, end, original, kind in spans:
        if start > position:
            parts.append(("text", prepared[position:start]))
        token = rewrite_cond_token(original) if kind == "cond" else original
        parts.append(("tech", token))
        position = end
    if position < len(prepared):
        parts.append(("text", prepared[position:]))
    return prepared, parts


def translate_fragment(value, translate_fn, *, always_attempt=False):
    lead = value[: len(value) - len(value.lstrip())]
    trail = value[len(value.rstrip()) :]
    core = value.strip()
    if not core:
        return value
    if not always_attempt and not LATIN_RX.search(value):
        return value
    words = mt_check.WORD.findall(core)
    if not words and not any(ord(char) > 127 for char in core):
        return value
    if not always_attempt:
        if len(words) <= 1 and len(core) <= 16:
            return value
        if core.isupper() and len(words) <= 3 and len(core) <= 28:
            return value
        if len(core) <= 24 and len(words) <= 3 and (
            (core.startswith('"') and core.endswith('"'))
            or (core.startswith("'") and core.endswith("'"))
        ):
            return value
    try:
        translated = translate_fn(core)
    except Exception:
        return value
    out = translated.strip() if isinstance(translated, str) else ""
    if not out:
        return value
    from vntext.patch_gate import has_garbage_repetition

    if has_garbage_repetition(out) or len(out) > max(120, len(core) * 4):
        return value
    return lead + out + trail


def translate_protected(source, translate_fn, *, always_attempt=False):
    _prepared, parts = split_parts(source)
    out = []
    for kind, value in parts:
        if kind == "tech":
            piece = value
        else:
            piece = translate_fragment(value, translate_fn, always_attempt=always_attempt)
        if out and piece:
            previous = out[-1]
            if previous[-1] == ">":
                pass
            elif (previous[-1].isalnum() or previous[-1] in "}]") and (
                piece[0].isalnum() or ord(piece[0]) > 127
            ):
                out.append(" ")
        out.append(piece)
    return postprocess(source, "".join(out))


def split_randpick_variants(text):
    """Split a RandPick pool on tight commas, not thousands separators."""
    if mt_check.tight_commas(text) < 2:
        return None
    parts = []
    start = 0
    for match in mt_check.TIGHT_COMMA.finditer(text):
        parts.append(text[start:match.start()])
        start = match.end()
    parts.append(text[start:])
    return parts if len(parts) >= 3 else None


def translate_bracket_protected(text, translate_fn):
    """Translate one placeholder-bearing sentence with stable bracket markers.

    CT2 can deform the legacy ``ZZG`` sentinels.  Bracket markers are checked
    byte-for-byte and in source order; any mutation rejects this route instead
    of restoring a corrupted placeholder/tag.
    """
    if not mt_check.PH.search(str(text or "")):
        return None
    # Keep ordinary mapped prose visible to the model.  Bracket protection is
    # for structural/opaque tokens; masking lexical words here removes the
    # sentence context needed to translate them naturally.
    spans = [span for span in collect_spans(text) if span[3] != 'lexical']
    if not spans or BRACKET_MARKER_RX.search(text):
        return None
    markers = [f"[QZEL{i:04d}]" for i in range(len(spans))]
    masked = text
    for marker, (start, end, _original, _kind) in reversed(list(zip(markers, spans))):
        masked = masked[:start] + marker + masked[end:]
    try:
        translated = translate_fn(masked)
    except Exception:
        return None
    if not isinstance(translated, str) or not translated.strip():
        return None
    if BRACKET_MARKER_RX.findall(translated) != markers:
        return None
    restored = translated
    for marker, (_start, _end, original, _kind) in zip(markers, spans):
        restored = restored.replace(marker, original, 1)
    if BRACKET_MARKER_RX.search(restored):
        return None
    return postprocess(text, restored)


def mask_roundtrip_ok(src):
    masked, tokens, kinds, prepared = mask_text(src)
    restored = restore_text(masked, tokens, kinds)
    # Condition tokens may be rewritten; compare with that rewrite applied.
    expected = prepared
    spans = collect_spans(prepared)
    for s, e, orig, kind in reversed(spans):
        if kind == 'cond':
            expected = expected[:s] + rewrite_cond_token(orig) + expected[e:]
    return restored == expected, prepared, masked, restored


def is_moan_with_tech_line(src: str) -> bool:
    """Thoại chỉ gồm tiếng rên + placeholder/tag/♡ — giữ nguyên, không MT."""
    s = str(src or "").strip()
    if not s:
        return False
    # Classify from the original lexical tokens. ``split_parts`` may replace a
    # generic fallback token with Vietnamese before CT2, which must not turn
    # an ordinary UI label or player-visible utterance into a literal keep.
    original_letters = re.findall(r"[A-Za-z]+", s)
    if original_letters and not all(
        (len(w) <= 5 and w.lower() in {"ah", "oh", "uh", "mm", "ha", "hn", "un", "nh", "ng", "eh", "hm", "hmm", "aah", "ooh"})
        or mt_check.is_onomatopoeia(w)
        for w in original_letters
    ):
        return False
    _prep, parts = split_parts(s)
    texts = [v.strip() for kind, v in parts if kind == "text" and v.strip()]
    if not texts:
        return bool(mt_check.PH.search(s) or mt_check.HEART in s)
    for t in texts:
        letters = re.findall(r"[A-Za-z]+", t)
        if letters and all(
            (len(w) <= 5 and w.lower() in {"ah", "oh", "uh", "mm", "ha", "hn", "un", "nh", "ng", "eh", "hm", "hmm", "aah", "ooh"})
            or mt_check.is_onomatopoeia(w)
            for w in letters
        ):
            continue
        if re.fullmatch(r"[!?.…,~♡♥\s]+", t):
            continue
        if len(t) <= 2 and not re.search(r"[A-Za-z]", t):
            continue
        return False
    return True


def heal_structure(src: str, text: str) -> str:
    """Khôi phục ♡/\\n thiếu; nếu mất placeholder/tag thì gắn lại đúng vị trí tech từ source."""
    if not src:
        return text or ""
    out = text or ""
    missing_h = src.count(mt_check.HEART) - out.count(mt_check.HEART)
    if missing_h > 0:
        if src.rstrip().endswith(mt_check.HEART):
            out = out.rstrip() + (mt_check.HEART * missing_h)
        else:
            out = out + (mt_check.HEART * missing_h)
    missing_n = src.count("\\n") - out.count("\\n")
    if missing_n > 0:
        out = out + ("\\n" * missing_n)

    src_ph = mt_check.PH.findall(src)
    out_ph = mt_check.PH.findall(out)
    src_tg = mt_check.TAG.findall(src)
    out_tg = mt_check.TAG.findall(out)
    if sorted(src_ph) == sorted(out_ph) and sorted(src_tg) == sorted(out_tg):
        return out

    # Gắn lại toàn bộ tech spans theo thứ tự source; giữ prose đã dịch (đã bỏ tech).
    _prepared, parts = split_parts(src)
    prose = out
    for kind, val in parts:
        if kind == "tech" and val:
            prose = prose.replace(val, " ")
    prose = re.sub(r"\s+", " ", prose).strip()
    pieces: list[str] = []
    text_budget = prose
    for kind, val in parts:
        if kind == "tech":
            pieces.append(val)
            continue
        lead = val[: len(val) - len(val.lstrip())] if val else ""
        trail = val[len(val.rstrip()) :] if val else ""
        core = val.strip() if val else ""
        if not core:
            pieces.append(val)
            continue
        if text_budget:
            pieces.append(lead + text_budget + trail)
            text_budget = ""
        else:
            pieces.append(lead + trail)
    candidate = "".join(pieces)
    if sorted(mt_check.PH.findall(src)) == sorted(mt_check.PH.findall(candidate)):
        missing_h2 = src.count(mt_check.HEART) - candidate.count(mt_check.HEART)
        if missing_h2 > 0 and src.rstrip().endswith(mt_check.HEART):
            candidate = candidate.rstrip() + (mt_check.HEART * missing_h2)
        return candidate
    return out


def collapse_token_repetition(text: str) -> str:
    """Gỡ lặp từ/ký tự kiểu CT2 rác, giữ nội dung khác."""
    if not text:
        return text
    out = re.sub(r"[_\-]{3,}", "", text)  # ________ / --- do model
    out = re.sub(r"(.)\1{4,}", r"\1\1\1", out)  # aaaaa -> aaa
    out = re.sub(r"\b(\w{2,})(?:\s+\1){2,}\b", r"\1", out, flags=re.UNICODE)
    out = re.sub(r"([♪])(?:\s*\1){3,}", r"\1", out)
    out = re.sub(r"\s{2,}", " ", out).strip()
    return out


def postprocess(src, text):
    # Translator adapters are expected to return strings.  Keep the retry
    # path fail-closed when a backend/mocked adapter returns a non-text value
    # (for example MagicMock): that row must be rejected and sent to review,
    # not crash the whole batch while validating the candidate.
    out = text if isinstance(text, str) else ""
    if INJECTED_COLOR_TOKEN.search(out):
        out = INJECTED_COLOR_TOKEN.sub('', out)
    # Normalize a small set of English contractions before token-level repair.
    # WORD intentionally splits apostrophes, so repairing ``you`` first would
    # otherwise leave malformed ``bạn're``/``không't`` fragments.
    for pattern, replacement in (
        (r"(?<![A-Za-z])you['’]re(?![A-Za-z])", "bạn"),
        (r"(?<![A-Za-z])i['’]m(?![A-Za-z])", "tôi"),
        (r"(?<![A-Za-z])aren['’]t(?![A-Za-z])", "không"),
    ):
        out = re.sub(pattern, replacement, out, flags=re.IGNORECASE)
    # OPUS-MT occasionally emits ``#`` as a placeholder-like separator even
    # when the source has no hash token.  It is a model artifact, not display
    # content; remove only standalone hashes absent from the source so the
    # structural/quality gates still see the real translated prose.
    if '#' not in (src or '') and '#' in out:
        out = re.sub(r'(?<!\w)#(?!\w)', ' ', out)
        out = re.sub(r'\s{2,}', ' ', out).strip()
    # When a {mName}-style technical token is protected, CT2 can hallucinate a
    # second literal ``Name`` immediately after it.  Drop that artifact only
    # when the source itself contains no ordinary word "name".
    source_plain = mt_check.PH.sub(' ', str(src or ''))
    if not re.search(r'\bname\b', source_plain, flags=re.I):
        out = re.sub(r'(?<=\})\s+name\b', ' ', out, flags=re.I)
    # Remove a bare echo of a protected placeholder (``TASTY {TASTY}``,
    # ``Name {mName}``, ...).  The placeholder itself remains untouched; only
    # the model's duplicate display token is removed when the source has no
    # ordinary occurrence outside its braces.
    for placeholder in mt_check.PH.findall(str(src or '')):
        bare = placeholder.strip('{}').lstrip('$')
        # Only a simple ``{mName}`` token can have a duplicated *literal* name
        # in model prose.  Expressions such as ``{10*(1+skill_x)}`` contain
        # operators and nested identifiers; treating the inner identifiers as
        # an echo would erase them from the protected expression itself.
        if (
            not bare
            or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", bare)
            or re.search(rf"\b{re.escape(bare)}\b", source_plain, flags=re.I)
        ):
            continue
        out = re.sub(
            rf"(?<![A-Za-z{{]){re.escape(bare)}(?![A-Za-z}}])",
            " ",
            out,
            flags=re.I,
        )
    # Translate a generic star-wrapped SFX when the lexical table has a safe
    # source-token mapping; the star delimiters remain byte-for-byte intact.
    for m in STAR_SFX.finditer(str(src or '')):
        sm = re.fullmatch(r"\*([A-Za-z]+)\*([!?.…]*)", m.group(0))
        original = m.group(0)
        if sm:
            translated_sfx = generic_term_translation(sm.group(1))
            if translated_sfx is None:
                continue
            replacement = f"*{translated_sfx}*{sm.group(2)}"
        else:
            # Some UI/choice markers wrap more than one source word, e.g.
            # ``*Cencored Violate*``.  Translate only when every lexical word
            # has a bounded generic mapping; otherwise leave the intentional
            # marker untouched for the normal quality gate.
            inner_match = re.fullmatch(r"\*([A-Za-z][A-Za-z ]*[A-Za-z])\*([!?.…]*)", original)
            if not inner_match:
                continue
            inner = inner_match.group(1)
            words = list(re.finditer(r"[A-Za-z]+", inner))
            if not words:
                continue
            rebuilt = inner
            for wm in reversed(words):
                translated_word = generic_term_translation(wm.group(0))
                if translated_word is None:
                    rebuilt = ""
                    break
                rebuilt = rebuilt[: wm.start()] + translated_word + rebuilt[wm.end() :]
            if not rebuilt:
                continue
            replacement = f"*{rebuilt}*{inner_match.group(2)}"
        if original in out:
            out = out.replace(original, replacement)
    # If CT2 copied a generic source token despite the protected-span pass,
    # apply the same bounded dictionary to that exact token in the candidate.
    # This is source-token based (not key/path/VH based) and leaves proper
    # names/unknown English untouched for the quality gate to reject.
    source_scan = str(src or "").replace("\\n", " ")
    source_protected_ranges = [
        (m.start(), m.end())
        for rx in (BRACKET, HASHTAG, STAR_SFX, EW_AW_RX, mt_check.PH, mt_check.TAG, mt_check.COND_EXPR, INTERNAL_SENTINEL_RX)
        for m in rx.finditer(source_scan)
    ]
    source_protected_ranges.extend((m.start(), m.end()) for m in re.finditer(
        r"(?<![A-Za-z0-9_])[A-Za-z0-9_.-]+(?:(?:/|\\(?!n))[A-Za-z0-9_.-]+)+(?![A-Za-z0-9_])",
        source_scan,
    ))

    def _replace_unprotected_token(text: str, token: str, replacement: str) -> str:
        """Replace a source lexical token only in translated prose.

        A global ``re.sub`` here used to rewrite words inside a protected
        placeholder (``{G_Option_Block_Harassment}`` became
        ``{G_Option_khối_Harassment}``), creating a structural blocker after
        the masking path had done its job.  Recompute protected output spans
        for each token and leave tags/placeholders/conditions untouched.
        """
        protected = [
            (m.start(), m.end())
            for rx in (BRACKET, HASHTAG, EW_AW_RX, mt_check.PH, mt_check.TAG, mt_check.COND_EXPR, INTERNAL_SENTINEL_RX)
            for m in rx.finditer(text)
        ]
        protected.extend((m.start(), m.end()) for m in re.finditer(
            r"(?<![A-Za-z0-9_])[A-Za-z0-9_.-]+(?:(?:/|\\(?!n))[A-Za-z0-9_.-]+)+(?![A-Za-z0-9_])",
            text,
        ))
        pattern = re.compile(rf"(?<![A-Za-z{{]){re.escape(token)}(?![A-Za-z}}])", re.I)
        return pattern.sub(
            lambda m: m.group(0)
            if any(start <= m.start() < end for start, end in protected)
            else replacement,
            text,
        )

    for token_match in re.finditer(r"[A-Za-z]+", source_scan):
        source_token = token_match.group(0)
        if any(start <= token_match.start() < end for start, end in source_protected_ranges):
            continue
        # Keep path component words literal; path spans are protected in the
        # translation pass and these terms must not be rewritten afterwards.
        if source_token.casefold() in {"data", "folder"}:
            continue
        translated_token = generic_term_translation(source_token)
        if not translated_token:
            continue
        out = _replace_unprotected_token(out, source_token, translated_token)
        # A literal newline is encoded as the two characters ``\\n``; replace
        # the exact token after that separator as well (the boundary assertion
        # above sees the trailing ``n`` as a letter).
        for variant in {
            source_token,
            source_token.lower(),
            source_token.capitalize(),
            source_token.upper(),
        }:
            out = out.replace("\\n" + variant, "\\n" + translated_token)
    # CT2 may hallucinate one of the same bounded English vocabulary terms
    # even when that word is absent from the source (for example ``Comment``
    # in a long Tips row).  Repair only exact generic dictionary tokens in
    # unprotected prose; paths, tags, placeholders, condition expressions and
    # named spans remain byte-for-byte untouched.
    output_protected_ranges = [
        (m.start(), m.end())
        for rx in (BRACKET, HASHTAG, STAR_SFX, EW_AW_RX, mt_check.PH, mt_check.TAG, mt_check.COND_EXPR, INTERNAL_SENTINEL_RX)
        for m in rx.finditer(out)
    ]
    output_protected_ranges.extend((m.start(), m.end()) for m in re.finditer(
        r"(?<![A-Za-z0-9_])[A-Za-z0-9_.-]+(?:(?:/|\\(?!n))[A-Za-z0-9_.-]+)+(?![A-Za-z0-9_])",
        out,
    ))
    output_repairs: list[tuple[int, int, str]] = []
    for token_match in re.finditer(r"[A-Za-z]+", out):
        if any(start <= token_match.start() < end for start, end in output_protected_ranges):
            continue
        # The ASCII scan intentionally finds source English inside Vietnamese
        # words as well (``so`` in ``soạng``). Never rewrite such a fragment.
        if (
            token_match.start() > 0
            and out[token_match.start() - 1].isalpha()
        ) or (
            token_match.end() < len(out)
            and out[token_match.end()].isalpha()
        ):
            continue
        translated_token = generic_term_translation(token_match.group(0))
        if translated_token and translated_token.casefold() != token_match.group(0).casefold():
            output_repairs.append((token_match.start(), token_match.end(), translated_token))
    for start, end, replacement in reversed(output_repairs):
        out = out[:start] + replacement + out[end:]
    # Correct two recurring inflection/spelling drifts when the source gives a
    # generic anchor for them (for example ``man`` -> ``Name`` or
    # ``MatchMaking`` -> ``MatchMake``).  This remains source-token based.
    if re.search(r"\b(?:man|men)\b", source_scan, flags=re.I):
        out = re.sub(r"(?<![A-Za-z{])name(?![A-Za-z}])", "người đàn ông", out, flags=re.I)
    if re.search(r"\bmatchmaking\b", source_scan, flags=re.I):
        out = re.sub(r"(?<![A-Za-z{])matchmake(?![A-Za-z}])", "mai mối", out, flags=re.I)
    # A leading article before a protected placeholder is commonly copied by
    # CT2 even though the Vietnamese clause already carries the relation.
    if re.match(r"^\s*\(?(?:The)\b", str(src or ''), flags=re.I):
        out = re.sub(r"^(\s*\(?)The\s+", r"\1", out, count=1, flags=re.I)
    if re.search(r"\bGAME\s+OVER\b", str(src or ''), flags=re.I):
        out = re.sub(r"\bGAME\s+over\b", "GAME KẾT THÚC", out, flags=re.I)
    # CT2 hay chèn ♪ khi fail — bỏ nếu source không có.
    if "♪" not in (src or "") and "♪" in (out or ""):
        out = re.sub(r"\s*♪\s*", " ", out)
        out = re.sub(r"\s{2,}", " ", out).strip()
    # Bỏ space thừa ngay sau thẻ mở <color=…> (join bug cũ / CT2).
    out = re.sub(r"(<color\s*=\s*[^>]+>)\s+", r"\1", out, flags=re.I)
    out = apply_exact_labels(src, out)
    if mt_check.tight_commas(src) >= 2:
        if mt_check.tight_commas(out) != mt_check.tight_commas(src):
            cand = re.sub(r',\s+', ',', out)
            if mt_check.tight_commas(cand) == mt_check.tight_commas(src):
                out = cand
    from vntext.patch_gate import has_garbage_repetition

    if has_garbage_repetition(out):
        collapsed = collapse_token_repetition(out)
        tok_in = len(re.findall(r"\S+", out))
        tok_out = len(re.findall(r"\S+", collapsed))
        # Chỉ nhận collapse khi còn đủ token — tránh "bán×20" → "bán" rồi heal gắn placeholder.
        if (
            not has_garbage_repetition(collapsed)
            and tok_out >= max(4, int(tok_in * 0.55))
            and len(collapsed.strip()) >= max(16, int(len(out) * 0.5))
        ):
            out = collapsed
    # Không heal khi vẫn còn rác — tránh biến rác thành "hợp lệ cấu trúc".
    if not has_garbage_repetition(out):
        out = heal_structure(src, out)
    return out


def validate_candidate(row, new, whitelist):
    reasons = []
    if not (new or '').strip():
        reasons.append('empty translation')
        return reasons
    if SENTINEL_LEFTOVER.search(new):
        reasons.append('sentinel leftover')
    reasons.extend(mt_check.structural_problems(row, new))
    # Identity OK khi không lỗi cấu trúc phía trên: giữ EN sau khi CT2 fail
    # còn hơn để trống (dialogue_pending vô hạn).
    return reasons

__all__ = [
    "apply_exact_labels",
    "collect_spans",
    "is_moan_with_tech_line",
    "heal_structure",
    "collapse_token_repetition",
    "mask_roundtrip_ok",
    "mask_text",
    "postprocess",
    "restore_text",
    "split_parts",
    "split_randpick_variants",
    "strip_lexical_suffixes",
    "translate_bracket_protected",
    "translate_fragment",
    "translate_protected",
    "validate_candidate",
    "rewrite_cond_token",
]
