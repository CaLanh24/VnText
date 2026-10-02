"""Chiến lược dịch đa bước: mask, protected fragments, synonym, moan preserve."""
from __future__ import annotations

import hashlib
import re
import uuid
from typing import Any

from vntext import mt_check
from vntext.mt_translation_safety import (
    heal_structure,
    is_moan_with_tech_line,
    mask_roundtrip_ok,
    mask_text,
    postprocess,
    restore_text,
    split_parts,
    split_randpick_variants,
    translate_bracket_protected,
    translate_protected,
    validate_candidate,
)
from vntext.mt_classify import is_sound_effect_line
from vntext.patch_gate import reason_label_vi, translation_passes_patch_gate

_MOAN_WORDS = frozenset(
    {"ah", "oh", "uh", "mm", "ha", "hn", "un", "nh", "ng", "eh", "hm", "hmm", "aah", "ooh"}
)

_MIXED_CASE_WORD = re.compile(r"(?<![A-Za-z])[A-Za-z]+(?:'[A-Za-z]+)?(?![A-Za-z])")


def _normalise_mixed_case_for_mt(text: str) -> str:
    """Repair stylised lower-leading casing before the MT tokenizer.

    Script authors occasionally use ``cAN'T dO tHIS`` for emphasis.  The CT2
    model treats those fragments as unknown tokens and may return a short,
    unrelated sentence.  Only lower-leading tokens containing an uppercase
    run are normalised; proper names and all-caps SFX stay byte-for-byte intact
    in the source and restored output.
    """
    def repl(match: re.Match[str]) -> str:
        token = match.group(0)
        if token[:1].islower() and any(char.isupper() for char in token[1:]):
            return token.lower()
        return token

    return _MIXED_CASE_WORD.sub(repl, str(text or ""))


def is_moan_fragment(text: str) -> bool:
    """Fragment ngắn là tiếng rên — giữ nguyên, không gửi OPUS-MT."""
    s = str(text or "").strip()
    if not s or len(s) > 40:
        return False
    if is_sound_effect_line(s):
        return True
    letters = re.findall(r"[A-Za-z]+", s)
    if not letters or len(letters) > 4:
        return False
    return all(w.lower() in _MOAN_WORDS or mt_check.is_onomatopoeia(w) for w in letters)


def candidate_quality_issues(
    row: dict,
    candidate: str,
    whitelist: set[str],
) -> list[str]:
    """Reject model output that is structurally safe but visibly low quality.

    Patch safety alone cannot catch malformed repeated-name output or a
    mostly untranslated sentence. Explicit literal-keep rows are exempt;
    player-visible MT rows are not.
    """
    value = str(candidate or "").strip()
    source = str(row.get("source_text") or "").strip()
    if not value:
        return ["quality: empty candidate"]

    from vntext.patch_gate import has_garbage_repetition, has_html_garbage, is_ct2_junk_translation

    from vntext.mt_classify import classify_row_authoritative

    action, _reason, _decision = classify_row_authoritative({**row, "translation": ""})
    if value in {"*", "..."} and action in {
        "translate", "translate_synonym", "ui_label_fixed"
    }:
        issues = ["quality: symbol-only candidate"]
    else:
        issues = []
    if value == source and allow_identity_translation(row, "quality"):
        return []
    intentional_echo = False
    if has_garbage_repetition(value):
        from vntext.patch_gate import has_intentional_echo

        intentional_echo = (
            mt_check.tight_commas(source) < 2
            and has_intentional_echo(source)
            and has_intentional_echo(value)
        )
    if (has_garbage_repetition(value) and not intentional_echo) or is_ct2_junk_translation(source, value):
        issues.append("quality: repeated/model garbage")
    if has_html_garbage(value) and value != source:
        issues.append("quality: malformed markup")
    if value == source and action in {"translate", "translate_synonym", "ui_label_fixed"}:
        issues.append("quality: identity for player-visible row")

    source_visible = mt_check.strip_technical(source).strip()
    candidate_visible = mt_check.strip_technical(value).strip()
    source_words = mt_check.WORD.findall(source_visible)
    candidate_words = mt_check.WORD.findall(candidate_visible)
    if len(source_words) >= 6:
        # Vietnamese can be shorter than English, but a visible dialogue that
        # loses roughly half its words is a truncation, not a valid concise
        # translation. This specifically catches CT2 stopping at an ellipsis.
        minimum_words = max(3, (len(source_words) * 3 + 4) // 5)
        if len(candidate_words) < minimum_words:
            issues.append("quality: content loss")
    if len(source_visible) >= 28 and len(candidate_visible) < max(7, len(source_visible) // 4):
        if "quality: content loss" not in issues:
            issues.append("quality: content loss")

    if action in {"translate", "translate_synonym", "ui_label_fixed"}:
        # ponytail: bounded residue checks catch CT2 artifacts without owning a
        # second grammar checker; expand only when a reviewed fixture proves it.
        for token in mt_check.WORD.findall(candidate_visible):
            if token.casefold() in {"a", "m", "s"}:
                issues.append(f"quality: residual short token: {token}")
        repeated_tokens = {
            match.group(1).casefold()
            for match in re.finditer(r"\b([^\W\d_]{3,})\s+\1\b", candidate_visible, re.IGNORECASE)
        }
        issues.extend(f"quality: repeated token: {token}" for token in sorted(repeated_tokens))
        if (
            re.search(r"\s+[,.!?…]", value)
            and not re.search(r"\s+[,.!?…]", source)
        ):
            issues.append("quality: punctuation spacing")
        if any(
            mt_check.is_onomatopoeia(token) and mt_check.has_vietnamese_diacritic(token)
            for token in mt_check.WORD.findall(candidate_visible)
        ):
            issues.append("quality: glued vocalisation")
        _score, reasons = mt_check.english_report(source, value, whitelist)
        for reason in reasons:
            if reason.startswith(("english-token", "english-weak", "ascii-ratio", "overlap")):
                issues.append("quality: " + reason)
    return issues


def evaluate_candidate(
    row: dict,
    raw: str,
    whitelist: set[str],
    *,
    quality: bool = False,
) -> tuple[str | None, list[str]]:
    """Giống _safe_candidate trong mt_ct2 — tránh import vòng."""
    candidate = postprocess(row["source_text"], raw)
    reasons = validate_candidate(row, candidate, whitelist)
    if not reasons:
        gate_ok, gate_reason = translation_passes_patch_gate(row, candidate, whitelist)
        if gate_ok:
            if quality:
                quality_reasons = candidate_quality_issues(row, candidate, whitelist)
                if quality_reasons:
                    return None, quality_reasons
            return candidate, []
        return None, [f"Patch Gate: {reason_label_vi(gate_reason)}"]
    fixed = postprocess(row["source_text"], candidate)
    reasons2 = validate_candidate(row, fixed, whitelist)
    if not reasons2:
        gate_ok, gate_reason = translation_passes_patch_gate(row, fixed, whitelist)
        if gate_ok:
            if quality:
                quality_reasons = candidate_quality_issues(row, fixed, whitelist)
                if quality_reasons:
                    return None, quality_reasons
            return fixed, reasons
        return None, [f"Patch Gate: {reason_label_vi(gate_reason)}"]
    return None, reasons2


def translate_synonym_row(row: dict, translator: Any) -> str:
    """Dịch phần sau `{KEY}=`, giữ prefix và số variant."""
    src = str(row.get("source_text") or "")
    m = re.match(r"(\{[A-Za-z0-9_]+\}=)(.*)", src, re.DOTALL)
    if not m:
        return ""
    prefix, rest = m.group(1), m.group(2)
    phrase_fallbacks = {
        "back door": "cửa sau",
        "cock slave": "nô lệ tình dục",
        "cum bucket": "xô tinh dịch",
        "cum dump": "bãi tinh dịch",
        "dear gods": "các vị thần",
        "dwemer penis": "dương vật Dwemer",
        "holy fuck": "chết tiệt",
        "holy shit": "chết tiệt",
        "oh damn": "ôi chết tiệt",
        "oh fuck": "ôi chết tiệt",
        "oh gods": "ôi các vị thần",
        "oh my gods": "ôi các vị thần",
        "oh shit": "ôi chết tiệt",
        "sex toy": "đồ chơi tình dục",
        "worm ridden": "nhiễm giun",
    }

    def _part_ok(src_part: str, out_part: str) -> bool:
        if not out_part:
            return False
        if out_part.count(",") != 0:
            return False
        from vntext.patch_gate import has_garbage_repetition

        if has_garbage_repetition(out_part):
            return False
        if len(out_part) > max(48, len(src_part) * 5):
            return False
        # Lặp token dính (unitunitunit / bánbán)
        if re.search(r"([A-Za-zÀ-ỹ]{2,8})\1{3,}", out_part, flags=re.IGNORECASE):
            return False
        return True

    def _should_mt_part(part: str) -> bool:
        # Stem rất ngắn (us, rap) — giữ EN. Từ ≥4 ký tự vẫn thử dịch.
        if re.fullmatch(r"[a-z]{1,3}", part or ""):
            return False
        return bool(mt_check.WORD.findall(part))

    if "," in rest:
        parts = [p.strip() for p in rest.split(",")]
        out_parts: list[str] = []
        for part in parts:
            if not part:
                out_parts.append(part)
                continue
            if not _should_mt_part(part):
                # Short stems skip CT2, but still receive the bounded lexical
                # repair (for example ``ass`` in a synonym pool).
                out_parts.append(postprocess(part, part))
                continue
            cleaned = phrase_fallbacks.get(part.casefold())
            if cleaned is None:
                raw = translator.translate(part)
                cleaned = re.sub(r"\s*,\s*", " ", str(raw or "")).strip()
                cleaned = postprocess(part, cleaned)
            out_parts.append(cleaned if _part_ok(part, cleaned) else part)
        return prefix + ",".join(out_parts)
    body = rest.strip()
    if not body:
        return prefix
    if not _should_mt_part(body):
        return prefix + postprocess(body, body)
    cleaned = phrase_fallbacks.get(body.casefold())
    if cleaned is None:
        raw = translator.translate(body)
        cleaned = re.sub(r"\s*,\s*", " ", str(raw or "")).strip()
        cleaned = postprocess(body, cleaned)
    return prefix + (cleaned if _part_ok(body, cleaned) else body)


def _ct2_fn(translator: Any, *, preserve_moan: bool = True):
    def fn(core: str) -> str:
        if preserve_moan and is_moan_fragment(core):
            return core
        return translator.translate(_normalise_mixed_case_for_mt(core))

    return fn


def translate_protected_ct2(src: str, translator: Any) -> str:
    if mt_check.PH.search(src):
        safe = translate_bracket_protected(src, _ct2_fn(translator))
        if safe is not None:
            return safe
    return translate_protected(src, _ct2_fn(translator), always_attempt=True)


def translate_masked_ct2(src: str, translator: Any) -> str | None:
    if mt_check.PH.search(src):
        return translate_bracket_protected(src, translator.translate)
    ok, prepared, masked, _restored = mask_roundtrip_ok(src)
    if not ok or not masked.strip():
        return None
    _masked2, tokens, kinds, _ = mask_text(prepared)
    # Chỉ dùng mask khi cả chuỗi (hoặc từng phần sau split an toàn) vừa budget token.
    token_len = getattr(translator, "_token_len", None)
    max_tok = getattr(translator, "_max_src_tokens", 480)
    if callable(token_len):
        from vntext.mt_ct2 import _split_text_under_token_limit

        parts = _split_text_under_token_limit(masked, token_len, max_tokens=max_tok)
        if any(token_len(p) > max_tok for p in parts):
            return None
    try:
        translated = translator.translate(masked)
    except RuntimeError:
        return None
    restored = restore_text(translated, tokens, kinds)
    # Nếu model phá sentinel → bỏ strategy này.
    # CT2 may mutate a sentinel into ``ZZG 1000 ZZZ`` or another near-match;
    # any residual ZZ/G marker means the mask round-trip is unsafe.  Require
    # every protected token to have been restored before accepting this path.
    if re.search(r"Z{2,}\s*G|ZZZ", restored, flags=re.I):
        return None
    if len(re.findall(r"ZZ\s*G\s*\d+\s*ZZ", str(translated), flags=re.I)):
        return None
    from vntext.patch_gate import emptied_color_content, has_html_garbage

    if has_html_garbage(restored) or emptied_color_content(src, restored):
        return None
    return postprocess(src, restored)


def translate_literal_newlines_ct2(src: str, translator: Any) -> str:
    """Giữ số lượng `\\n` literal — dịch từng đoạn rồi ghép lại.

    Nếu một đoạn CT2 ra rác/HTML garbage thì giữ nguyên đoạn EN (không phá cả tip).
    """
    if "\\n" not in src:
        return translate_protected_ct2(src, translator)
    from vntext.patch_gate import has_garbage_repetition, has_html_garbage, is_ct2_junk_translation

    parts = src.split("\\n")
    fn = _ct2_fn(translator)
    out: list[str] = []
    for part in parts:
        if not part.strip():
            out.append(part)
            continue
        if not (mt_check.WORD.findall(part) or any(ord(c) > 127 for c in part)):
            out.append(part)
            continue
        translated = (
            translate_protected_ct2(part, translator)
            if mt_check.PH.search(part)
            else translate_protected(part, fn, always_attempt=True)
        )
        if (
            not translated.strip()
            or has_garbage_repetition(translated)
            or has_html_garbage(translated)
            or is_ct2_junk_translation(part, translated)
            or (part.count("#") == 0 and translated.count("#") > 0)
        ):
            out.append(part)
        else:
            out.append(translated)
    return postprocess(src, "\\n".join(out))


def translate_row_ct2(row: dict, translator: Any) -> str:
    """Dịch một dòng: RandPick → protected; không batch."""
    src = row["source_text"]
    variants = split_randpick_variants(src)
    fn = _ct2_fn(translator)
    if variants:
        parts = [
            translate_protected_ct2(v, translator)
            if mt_check.PH.search(v)
            else translate_protected(v, fn, always_attempt=True)
            for v in variants
        ]
        return postprocess(src, ",".join(parts))
    if "\\n" in src and src.count("\\n") >= 2:
        return translate_literal_newlines_ct2(src, translator)
    return translate_protected_ct2(src, translator)


def translate_sentence_segments_ct2(src: str, translator: Any) -> str:
    """Translate punctuation-delimited clauses independently without dropping one.

    Some local MT models stop after ``...`` in a parenthetical aside. Splitting
    only at source punctuation keeps every source fragment in the retry path;
    structural tokens are still handled by ``translate_protected`` per chunk.
    """
    parts = re.split(r"(?<=[.!?…])(?=\s+)", src)
    if len(parts) < 2:
        return translate_protected_ct2(src, translator)
    return postprocess(src, "".join(
        translate_protected(part, _ct2_fn(translator), always_attempt=True)
        for part in parts
    ))


def translate_parenthetical_segments_ct2(src: str, translator: Any) -> str:
    """Translate balanced parenthetical asides independently.

    OPUS-MT frequently drops a leading ``(aside)`` when the following clause
    is short (for example ``(So gross!) Just leave me alone!``).  Translate
    the inner prose separately while restoring the delimiters byte-for-byte;
    this is a segmentation/retry repair, not a quality-gate exemption.
    """
    if not re.search(r"\([^()]*\)", src):
        return translate_protected_ct2(src, translator)
    fn = _ct2_fn(translator)
    pieces: list[str] = []
    cursor = 0
    for match in re.finditer(r"\([^()]*\)", src):
        if match.start() > cursor:
            pieces.append(
                translate_protected(src[cursor : match.start()], fn, always_attempt=True)
            )
        original = match.group(0)
        inner = original[1:-1]
        translated_inner = translate_protected(inner, fn, always_attempt=True)
        # Keep the source aside when CT2 returns empty/garbage; the caller's
        # normal structural and quality validation will still decide whether
        # the complete row can be accepted.
        if not translated_inner.strip():
            translated_inner = inner
        pieces.append("(" + translated_inner + ")")
        cursor = match.end()
    if cursor < len(src):
        pieces.append(translate_protected(src[cursor:], fn, always_attempt=True))
    return postprocess(src, "".join(pieces))


def translate_word_chunks_ct2(src: str, translator: Any, *, chunk_words: int = 4) -> str:
    """Recover omitted tails by translating bounded natural-language chunks.

    This fallback is intentionally limited to rows without tags/placeholders
    (those use the protected segmentation paths above).  A short CT2 output
    with a short leading name can otherwise fail the content-loss gate;
    four-word chunks retain the complete source coverage while each request
    remains within the local model's reliable context.
    """
    if mt_check.PH.search(src) or mt_check.TAG.search(src) or "[br]" in src.lower():
        return translate_protected_ct2(src, translator)
    matches = list(re.finditer(r"\S+(?:\s+|$)", src))
    if len(matches) < max(6, chunk_words + 1):
        return translate_protected_ct2(src, translator)
    chunks = [
        src[matches[i].start() : matches[min(i + chunk_words, len(matches)) - 1].end()]
        for i in range(0, len(matches), chunk_words)
    ]
    fn = _ct2_fn(translator)
    translated: list[str] = []
    for chunk in chunks:
        translated.append(translate_protected(chunk, fn, always_attempt=True))
    return postprocess(src, "".join(translated))


def translate_clause_segments_ct2(src: str, translator: Any) -> str:
    """Translate comma/semicolon clauses independently when CT2 truncates a tail.

    A short question with two coordinated clauses can make OPUS-MT return only
    the first clause.  Splitting on punctuation followed by whitespace keeps
    every clause and is deliberately disabled for tight-comma RandPick pools.
    """
    if mt_check.tight_commas(src) >= 2:
        return translate_protected_ct2(src, translator)
    parts = re.split(r"(?<=[,;:])(?=\s+)", src)
    if len(parts) < 2:
        return translate_protected_ct2(src, translator)
    return postprocess(src, "".join(
        translate_protected(part, _ct2_fn(translator), always_attempt=True)
        for part in parts
    ))


def translate_pipe_segments_ct2(src: str, translator: Any) -> str:
    """Dịch từng đoạn cách bởi | (tip/HUD), giữ khoảng trắng quanh |.

    Đoạn CT2 rác → giữ EN đoạn đó (bảo toàn tip/ending card).
    """
    if "|" not in src:
        return translate_protected_ct2(src, translator)
    from vntext.patch_gate import has_garbage_repetition, has_html_garbage, is_ct2_junk_translation

    chunks = src.split("|")
    out_chunks: list[str] = []
    fn = _ct2_fn(translator)
    for chunk in chunks:
        core = chunk.strip()
        if not core:
            out_chunks.append(chunk)
            continue
        lead_len = len(chunk) - len(chunk.lstrip(" "))
        trail_len = len(chunk) - len(chunk.rstrip(" "))
        lead = chunk[:lead_len]
        trail = chunk[len(chunk) - trail_len :] if trail_len else ""
        translated = translate_protected(core, fn, always_attempt=True)
        if (
            not translated.strip()
            or has_garbage_repetition(translated)
            or has_html_garbage(translated)
            or is_ct2_junk_translation(core, translated)
            or (core.count("#") == 0 and translated.count("#") > 0)
        ):
            out_chunks.append(chunk)
        else:
            out_chunks.append(lead + translated + trail)
    return postprocess(src, "|".join(out_chunks))


_COLOR_BLOCK = re.compile(r"(<color\s*=\s*[^>]+>)(.*?)(</color>)", re.I | re.DOTALL)
_LABEL_BEFORE_FORMULA = re.compile(
    r"^([A-Za-z][A-Za-z0-9 +/'’.-]{1,40}?)\s+(\{.*)$",
    re.DOTALL,
)


def translate_color_wrapped_ct2(src: str, translator: Any) -> str:
    """Dịch nội dung trong <color=…>…</color> (glossary trước, rồi CT2); giữ thẻ.

    Pattern skill phổ biến: ``oral skills {expr} [expr]`` — chỉ dịch nhãn trước ``{``.
    """
    from vntext.ui_labels import resolve_ui_label_translation
    from vntext.patch_gate import has_garbage_repetition, has_html_garbage, is_ct2_junk_translation

    if not src or "<color" not in src.lower():
        return translate_protected_ct2(src, translator)

    gloss = resolve_ui_label_translation(src)
    if gloss and gloss.strip() and gloss.strip() != src.strip():
        return gloss

    fn = _ct2_fn(translator)

    def _translate_inner(core: str) -> str:
        if not core.strip():
            return core
        hit = resolve_ui_label_translation(core)
        if hit is not None:
            return hit
        fm = _LABEL_BEFORE_FORMULA.match(core.strip())
        if fm and "{" in core:
            label, rest = fm.group(1).strip(), fm.group(2)
            label_hit = resolve_ui_label_translation(label)
            if label_hit is None:
                label_hit = translate_protected(label, fn, always_attempt=True)
                if (
                    not label_hit.strip()
                    or has_garbage_repetition(label_hit)
                    or is_ct2_junk_translation(label, label_hit)
                ):
                    label_hit = label
            return f"{label_hit} {rest}" if not rest.startswith(" ") else f"{label_hit}{rest}"
        translated = translate_protected(core, fn, always_attempt=True)
        if (
            not translated.strip()
            or has_garbage_repetition(translated)
            or has_html_garbage(translated)
            or is_ct2_junk_translation(core, translated)
        ):
            return core
        return translated

    def _repl(m: re.Match[str]) -> str:
        open_t, inner, close_t = m.group(1), m.group(2), m.group(3)
        lead_len = len(inner) - len(inner.lstrip(" "))
        trail_len = len(inner) - len(inner.rstrip(" "))
        lead = inner[:lead_len]
        trail = inner[len(inner) - trail_len :] if trail_len else ""
        core = inner.strip()
        return f"{open_t}{lead}{_translate_inner(core)}{trail}{close_t}"

    rebuilt = _COLOR_BLOCK.sub(_repl, src)
    if "[br]" in rebuilt.lower():
        return translate_br_segments_ct2(rebuilt, translator)
    return postprocess(src, rebuilt)


def _restore_placeholders_from_parts(source: str, translated: str, parts) -> str:
    """Graft {TECH} tokens CT2 dropped, anchored by last word before each token in source."""
    out = translated
    for kind, tok in parts:
        if kind != "tech" or tok in out:
            continue
        pos = source.find(tok)
        if pos < 0:
            out = out + tok
            continue
        before = source[:pos]
        anchor_words = re.findall(r"[\wÀ-ỹ']{2,}", before)
        if not anchor_words:
            out = (tok + out) if pos == 0 else (out + tok)
            continue
        needle = anchor_words[-1]
        idx = out.lower().find(needle.lower())
        if idx < 0 and len(anchor_words) >= 2:
            needle = anchor_words[-2]
            idx = out.lower().find(needle.lower())
        if idx >= 0:
            insert_at = idx + len(needle)
            out = out[:insert_at] + tok + out[insert_at:]
        else:
            out = out + tok
    return out


def translate_inline_placeholders_ct2(src: str, translator: Any) -> str:
    """Translate prose around placeholders while keeping every tech token exact.

    The previous implementation sent the *unmasked* string (including
    ``{skill_x+...}``) to CT2 and only grafted a placeholder back when the
    model dropped it.  CT2 often kept a mutated expression such as
    ``{skill_x+ }``; because the token was still present, the graft never ran
    and the structural gate correctly rejected the row.  Reuse the normal
    protected-span path instead: each prose fragment is translated
    independently and all placeholders/tags/conditions are restored byte for
    byte before validation.
    """
    from vntext.patch_gate import has_garbage_repetition, has_html_garbage, is_ct2_junk_translation

    _prepared, parts = split_parts(src)
    if not any(kind == "tech" for kind, _value in parts):
        return translate_protected_ct2(src, translator)
    out = translate_protected_ct2(src, translator)
    if (
        not out.strip()
        or has_garbage_repetition(out)
        or has_html_garbage(out)
        or is_ct2_junk_translation(src, out)
    ):
        return src
    return out


def translate_glrk_br_ct2(src: str, translator: Any) -> str:
    """*GLRK*/*GLRRRK*…[br](dialogue {PLACEHOLDERS}) — giữ sfx, dịch phần thoại."""
    from vntext.patch_gate import has_garbage_repetition, has_html_garbage, is_ct2_junk_translation

    lower = src.lower()
    if "[br]" not in lower:
        return translate_br_segments_ct2(src, translator)
    # Match *SFX* variants: GLRK, GLRRRK, SQUISH, etc. at line start.
    if not re.match(r"(?is)^\*[A-Za-z]{2,16}\*[!?.…]*\[br\]", src.strip()):
        return translate_br_segments_ct2(src, translator)
    i = lower.find("[br]")
    prefix = src[: i + 4]
    tail = src[i + 4 :]
    if not tail.strip():
        return src
    translated_tail = translate_inline_placeholders_ct2(tail, translator)
    if (
        not translated_tail.strip()
        or translated_tail.strip() == tail.strip()
        or has_garbage_repetition(translated_tail)
        or has_html_garbage(translated_tail)
        or is_ct2_junk_translation(tail, translated_tail)
    ):
        # Trả source → strategy sau (glossary / br_segments) xử lý; không đẩy rác CT2.
        return src
    return postprocess(src, prefix + translated_tail)


def translate_br_segments_ct2(src: str, translator: Any) -> str:
    """Dịch từng đoạn `[br]` — giữ nguyên thẻ ngắt dòng Naninovel/TMP."""
    if "[br]" not in src.lower():
        return translate_protected_ct2(src, translator)
    from vntext.patch_gate import has_garbage_repetition, has_html_garbage, is_ct2_junk_translation

    # Giữ đúng casing của token [br] gốc bằng split casefold index.
    parts: list[str] = []
    buf = src
    lower = buf.lower()
    while True:
        i = lower.find("[br]")
        if i < 0:
            parts.append(buf)
            break
        parts.append(buf[:i])
        parts.append(buf[i : i + 4])
        buf = buf[i + 4 :]
        lower = buf.lower()
    fn = _ct2_fn(translator)
    out: list[str] = []
    for part in parts:
        if part.lower() == "[br]" or not part.strip():
            out.append(part)
            continue
        if not (mt_check.WORD.findall(part) or any(ord(c) > 127 for c in part)):
            out.append(part)
            continue
        if "{" in part:
            translated = translate_inline_placeholders_ct2(part, translator)
        else:
            translated = (
                translate_protected_ct2(part, translator)
                if mt_check.PH.search(part)
                else translate_protected(part, fn, always_attempt=True)
            )
        if (
            not translated.strip()
            or has_garbage_repetition(translated)
            or has_html_garbage(translated)
            or is_ct2_junk_translation(part, translated)
            or (part.count("#") == 0 and translated.count("#") > 0)
        ):
            out.append(part)
        else:
            out.append(translated)
    return postprocess(src, "".join(out))


def has_intentional_source_repetition(src: str) -> bool:
    from vntext.patch_gate import has_garbage_repetition, has_intentional_echo

    return bool(src and (has_garbage_repetition(src) or has_intentional_echo(src)))


def allow_identity_translation(row: dict, strategy_name: str) -> bool:
    """True when writing source==translation is an intentional keep, not a silent miss."""
    src = str(row.get("source_text") or "")
    if strategy_name.startswith("copy_source_repetition"):
        return True
    # The explicit keep ledger is the source of truth for bounded SFX, status
    # labels and non-English editor markers.  Consult it before the broader
    # classifier heuristics so a quality check cannot reject a documented keep.
    from vntext.intentional_keep import intentional_keep_reason

    if intentional_keep_reason(row):
        return True
    if is_sound_effect_line(src) or is_moan_with_tech_line(src):
        return True
    from vntext.mt_classify import classify_row_authoritative

    action, _reason, _decision = classify_row_authoritative({**row, "translation": ""})
    return action in {
        "copy_literal",
        "copy_source",
        "skip_technical",
        "skip_ui_label",
        "done",
    }


def retry_row_strategies(
    row: dict,
    translator: Any,
    whitelist: set[str],
    batch_raw: str = "",
    *,
    fast: bool = False,
    user_glossary: dict[str, str] | None = None,
    full_raw: str = "",
    trace: list[dict[str, Any]] | None = None,
) -> tuple[str | None, str, list[str]]:
    """Thử lần lượt chiến lược; trả (candidate, strategy_name, reasons).

    fast=True: bỏ mask/pipe (đắt) — dùng cho full pass đầu; vòng sau có thể full strategies.
    """
    strategies: list[tuple[str, str]] = []
    src = row["source_text"]
    if mt_check.PH.search(src):
        strategies.append(("placeholder_safe_first", translate_protected_ct2(src, translator)))
    if batch_raw.strip():
        strategies.append(("batch_default", batch_raw))
        strategies.append(("batch_healed", postprocess(src, batch_raw)))

    last_reasons: list[str] = []
    valid_candidates: list[tuple[int, int, str, str]] = []
    unsafe_raw_placeholder_strategies = {
        "batch_default",
        "batch_healed",
        "full_sentence",
        "full_sentence_fast",
    }

    def _try(name: str, raw: str) -> tuple[str | None, list[str]]:
        """Evaluate one retry candidate and optionally retain full evidence."""
        raw_text = str(raw or "")
        if mt_check.PH.search(src) and name in unsafe_raw_placeholder_strategies:
            candidate, reasons = None, ["placeholder-safe route required"]
        else:
            candidate, reasons = evaluate_candidate(row, raw_text, whitelist, quality=True)
        if (
            candidate
            and candidate.strip() == src.strip()
            and not allow_identity_translation(row, name)
        ):
            reasons = ["identity keep bị từ chối — cần bản dịch thật"]
            candidate = None
        if trace is not None:
            trace.append(
                {
                    "attempt_id": str(uuid.uuid4()),
                    "strategy": name,
                    "raw_output": raw_text,
                    "raw_output_hash": hashlib.sha256(
                        raw_text.encode("utf-8", "surrogatepass")
                    ).hexdigest()
                    if raw_text
                    else "",
                    "candidate": str(candidate or ""),
                    "candidate_hash": hashlib.sha256(
                        str(candidate).encode("utf-8", "surrogatepass")
                    ).hexdigest()
                    if candidate
                    else "",
                    "validation_reasons": list(reasons or []),
                    "passed": bool(candidate),
                }
            )
        return candidate, list(reasons or [])

    for name, raw in strategies:
        candidate, reasons = _try(name, raw)
        if candidate:
            valid_candidates.append((0, len(candidate), name, candidate))
        last_reasons = reasons or last_reasons

    strategies2: list[tuple[str, str]] = []
    # Package glossary has precedence over the built-in UI glossary. Exact
    # entries are returned before CT2 so a user correction cannot be undone by
    # the model. Structural tokens must match exactly (tags/placeholders/newlines).
    from vntext.package_glossary import lookup_user_phrase

    user_hit = lookup_user_phrase(src, user_glossary)
    if user_hit and user_hit.strip() != src.strip():
        strategies2.append(("user_glossary", user_hit))

    if has_intentional_source_repetition(src):
        strategies2.append(("copy_source_repetition", src))

    # Glossary trước CT2 — nhãn ngắn/choice hay bị OPUS-MT sinh rác lặp.
    from vntext.ui_labels import resolve_ui_label_translation

    gloss = resolve_ui_label_translation(src, str(row.get("context") or ""))
    if gloss and gloss.strip() and gloss.strip() != src.strip():
        strategies2.append(("ui_glossary", gloss))

    if fast:
        # Pass đầu: full_sentence; chỉ copy EN khi keep hợp lệ (sfx/moan/classify).
        if not full_raw.strip():
            try:
                full_raw = translator.translate(src)
            except Exception:
                full_raw = ""
        if full_raw.strip():
            if mt_check.PH.search(src):
                # A full-sentence response may preserve every token exactly.
                # Admit it only through the normal structural, quality, and
                # Patch Gate checks below; the legacy raw route remains unsafe.
                strategies2.append(("direct_source", full_raw))
            strategies2.append(("full_sentence_fast", postprocess(src, full_raw)))
        if allow_identity_translation(row, "copy_literal"):
            strategies2.append(("copy_literal", src))
    else:
        # Tip/ending card nhiều \\n: dịch theo đoạn trước full_sentence (tránh mất \\n/tag).
        if "\\n" in src and src.count("\\n") >= 5:
            strategies2.append(
                ("literal_newlines_first", translate_literal_newlines_ct2(src, translator))
            )
        if "<color" in src.lower():
            strategies2.append(
                ("color_wrapped_first", translate_color_wrapped_ct2(src, translator))
            )
        if "[br]" in src.lower():
            if re.search(r"(?is)^\*[A-Za-z]{2,16}\*", src.strip()):
                strategies2.append(("glrk_br_first", translate_glrk_br_ct2(src, translator)))
            strategies2.append(("br_segments_first", translate_br_segments_ct2(src, translator)))
        if "|" in src and src.count("|") >= 2:
            strategies2.append(
                ("pipe_segments_first", translate_pipe_segments_ct2(src, translator))
            )
        # Dịch cả câu (không tách tên) — tránh rác khi fragment quá ngắn quanh KEEP_NAMES.
        if not full_raw.strip():
            try:
                full_raw = translator.translate(src)
            except Exception:
                full_raw = ""
        if full_raw.strip():
            if mt_check.PH.search(src):
                strategies2.append(("direct_source", full_raw))
            strategies2.append(("full_sentence", postprocess(src, full_raw)))
        if re.search(r"[.!?…]\s+", src):
            strategies2.append(("sentence_segments", translate_sentence_segments_ct2(src, translator)))
        if re.search(r"\([^()]*\)", src):
            strategies2.append(
                ("parenthetical_segments", translate_parenthetical_segments_ct2(src, translator))
            )
        if len(mt_check.WORD.findall(mt_check.strip_technical(src))) >= 6:
            strategies2.append(("word_chunks", translate_word_chunks_ct2(src, translator)))
        if mt_check.WORD.findall(src) and re.search(r"[,;:]\s+", src):
            strategies2.append(("clause_segments", translate_clause_segments_ct2(src, translator)))
        strategies2.append(("protected_moan", translate_protected_ct2(src, translator)))
        strategies2.append(("row_protected", translate_row_ct2(row, translator)))
        if "\\n" in src and src.count("\\n") >= 2:
            strategies2.append(
                ("literal_newlines", translate_literal_newlines_ct2(src, translator))
            )
        if "<color" in src.lower():
            strategies2.append(("color_wrapped", translate_color_wrapped_ct2(src, translator)))
        if "[br]" in src.lower():
            strategies2.append(("br_segments", translate_br_segments_ct2(src, translator)))
        if "|" in src or "<color" in src.lower() or "<b>" in src.lower():
            strategies2.append(("pipe_segments", translate_pipe_segments_ct2(src, translator)))
        masked = translate_masked_ct2(src, translator)
        if masked is not None:
            strategies2.append(("mask_roundtrip", masked))
        if allow_identity_translation(row, "copy_literal"):
            strategies2.append(("copy_literal", src))
        # Cụm ngắn / structure: chỉ giữ EN khi classify cho phép identity.
        if allow_identity_translation(row, "copy_literal_fallback"):
            if mt_check.tight_commas(src) >= 2 or (len(src) <= 40 and " " in src):
                strategies2.append(("copy_literal_fallback", src))
            if src.count("\\n") >= 5 or src.count("[br]") >= 2:
                strategies2.append(("copy_literal_structure", src))

    for name, raw in strategies2:
        candidate, reasons = _try(name, raw)
        if candidate:
            valid_candidates.append((0, len(candidate), name, candidate))
        last_reasons = reasons or last_reasons
    if valid_candidates:
        # All candidates here passed structural, Patch Gate, and quality
        # checks. Prefer a complete full-sentence/segmented candidate over a
        # shorter masked fragment: shortening was the reason CT2 silently lost
        # the tail after an ellipsis. User/package glossaries remain strongest.
        preference = {
            "user_glossary": -2,
            "ui_glossary": -1,
            "placeholder_safe_first": -1,
            "direct_source": 0,
            "full_sentence": 0,
            "full_sentence_fast": 0,
            "sentence_segments": 1,
        }
        _score, _length, name, candidate = min(
            valid_candidates,
            key=lambda item: (preference.get(item[2], 2), item[0], item[1]),
        )
        return candidate, name, []
    return None, (strategies2[-1][0] if strategies2 else "none"), last_reasons


def moan_preserve_indices(cores: list[str]) -> set[int]:
    return {i for i, c in enumerate(cores) if is_moan_fragment(c)}
