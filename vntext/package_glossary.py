"""Package-owned glossary helpers.

VNText deliberately ships no game-specific translation memory.  A user or
package can opt in to a small exact glossary under ``.mt/glossary.json``;
these helpers preserve placeholders and markup while applying that data.
"""

from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path


# Tags, placeholders, literal \n/[br] and the ZZG sentinels of an earlier masking layer are never glossary text.
_GLOSSARY_PROTECTED = re.compile(r"<[^>]*>|\$?\{[^{}]*\}|\\n|\[br\]|ZZG\d+ZZG?", re.IGNORECASE)


def _normalise(value: object) -> str:
    return " ".join(str(value or "").strip().lower().split())


def load_user_glossary(package_dir: str | Path | None = None) -> dict[str, str]:
    """Load a package-owned flat glossary without any bundled fallback data."""

    if not package_dir:
        return {}
    path = Path(package_dir) / ".mt" / "glossary.json"
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(data, dict):
        return {}
    return {
        key: str(value).strip()
        for raw_key, value in data.items()
        if (key := _normalise(raw_key)) and str(value).strip()
    }


def load_package_glossary(package_dir: str | Path | None = None) -> dict[str, str]:
    """Compatibility alias for the package-owned flat glossary."""

    return load_user_glossary(package_dir)


def _structure_tokens(text: str) -> list[str]:
    return _GLOSSARY_PROTECTED.findall(str(text or ""))


def lookup_user_phrase(src: str, glossary: dict[str, str] | None = None) -> str | None:
    """Return an exact user glossary translation only when structure matches."""

    table = glossary or {}
    value = table.get(_normalise(src))
    if value is None:
        value = next(
            (
                candidate
                for candidate_key, candidate in table.items()
                if _normalise(candidate_key) == _normalise(src)
            ),
            None,
        )
    if value is None or _structure_tokens(src) != _structure_tokens(str(value)):
        return None
    return str(value)


def is_word_char(char: str) -> bool:
    """A letter, digit, underscore or combining mark (so an NFD base letter never ends a word before its accent)."""

    return char.isalnum() or char == "_" or unicodedata.category(char).startswith("M")


def find_term_spans(text: str, term: str, *, ignore_case: bool = True) -> list[tuple[int, int]]:
    """Whole-word/phrase occurrences of ``term`` in ``text`` (original text, never rewritten).

    Boundaries use Unicode letters/digits/marks, but only where the term itself begins/ends with a word character, so a punctuation-bounded term
    ("Mr.") still matches before a space.  NFC and NFD spellings of the term both match; whitespace inside a multiword term matches any run of
    blanks/tabs (never a line break).
    """

    term = str(term or "")
    if not term:
        return []
    variants = []
    for form in ("NFC", "NFD"):
        value = unicodedata.normalize(form, term)
        if value not in variants:
            variants.append(value)
    pieces = []
    for value in sorted(variants, key=len, reverse=True):
        pieces.append(r"[^\S\r\n]+".join(re.escape(word) for word in value.split()))
    pattern = re.compile("|".join(piece for piece in pieces if piece), re.IGNORECASE if ignore_case else 0)
    starts_word = is_word_char(term[0])
    ends_word = is_word_char(term[-1])
    spans: list[tuple[int, int]] = []
    for match in pattern.finditer(text):
        start, end = match.span()
        if start == end:
            continue
        if starts_word and start > 0 and is_word_char(text[start - 1]):
            continue
        if ends_word and end < len(text) and is_word_char(text[end]):
            continue
        spans.append((start, end))
    return spans


def fresh_token(prefix: str, counter: int, suffix: str, *taken_texts: str) -> tuple[str, int]:
    """The next ``prefix+counter+suffix`` token that occurs in NONE of ``taken_texts`` (the original source, so a literal can never be mistaken for a mask)."""

    while True:
        token = f"{prefix}{counter}{suffix}"
        counter += 1
        if not any(token in text for text in taken_texts):
            return token, counter


def restore_tokens(text: str, restore: dict[str, str]) -> str:
    """Replace every generated token in ONE pass, so a restored value is never itself rewritten by a later token."""

    result = str(text or "")
    if not restore:
        return result
    pattern = re.compile("|".join(re.escape(token) for token in sorted(restore, key=len, reverse=True)))
    return pattern.sub(lambda match: str(restore[match.group(0)]), result)


def mask_user_glossary_terms(
    src: str, glossary: dict[str, str] | None = None
) -> tuple[str, dict[str, str]]:
    """Mask package-owned terms without matching inside protected tokens."""

    table = glossary or {}
    if not src or not table:
        return src, {}
    terms = [(key, value) for key, value in table.items()
             if key and value and not _structure_tokens(key) and not _structure_tokens(str(value))]
    terms.sort(key=lambda item: len(item[0]), reverse=True)
    if not terms:
        return src, {}
    restore: dict[str, str] = {}
    counter = 9000

    def mask_plain(plain: str) -> str:
        # Every term is matched on the ORIGINAL plain segment (never on a mask a previous term produced); the longest match wins and
        # equal-length overlaps keep the glossary's own order, so priority is explicit and nothing cascades.
        nonlocal counter
        candidates: list[tuple[int, int, int, int]] = []          # (start, end, term index, -length order key)
        for index, (key, _value) in enumerate(terms):
            for start, end in find_term_spans(plain, key):
                candidates.append((start, end, index, end - start))
        candidates.sort(key=lambda item: (-item[3], item[2], item[0]))
        taken: list[tuple[int, int, int]] = []
        for start, end, index, _length in candidates:
            if any(start < other_end and other_start < end for other_start, other_end, _ in taken):
                continue
            taken.append((start, end, index))
        taken.sort()
        pieces: list[str] = []
        last = 0
        for start, end, index in taken:
            token, counter = fresh_token("ZZG", counter, "ZZ", src)
            restore[token] = str(terms[index][1])
            pieces.append(plain[last:start])
            pieces.append(token)
            last = end
        pieces.append(plain[last:])
        return "".join(pieces)

    parts: list[str] = []
    last = 0
    for match in _GLOSSARY_PROTECTED.finditer(src):
        parts.append(mask_plain(src[last : match.start()]))
        parts.append(match.group(0))
        last = match.end()
    parts.append(mask_plain(src[last:]))
    return "".join(parts), restore


def restore_user_glossary_terms(text: str, restore: dict[str, str]) -> str:
    return restore_tokens(text, restore)


def lookup_short_phrase(src: str, *, glossary: dict[str, str] | None = None) -> str | None:
    """Compatibility helper; only caller-supplied/package glossary data applies."""

    return lookup_user_phrase(src, glossary)
