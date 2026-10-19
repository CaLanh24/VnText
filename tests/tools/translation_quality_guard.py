"""Test-only opaque-token transport. No product routing or validator changes."""
from __future__ import annotations

from dataclasses import dataclass
import re

from vntext import mt_check
from vntext.mt_translation_constants import BRACKET, HASHTAG, STAR_SFX

MARKER = re.compile(r"\[VNT\d{3}\]")
ESCAPE = re.compile(r"\\[nrt]|[\r\n\t]")
FORMAT = re.compile(r"%%|%(?:\d+\$)?[-+#0 ]*(?:\d+|\*)?(?:\.\d+)?[sdiufFeEgGxc]|\d+(?:\.\d+)?%")
HEART = re.compile(re.escape(mt_check.HEART))
PATTERNS = (mt_check.PH, mt_check.TAG, BRACKET, HASHTAG, STAR_SFX, ESCAPE, FORMAT, HEART)


def spans(text):
    matches = [(m.start(), m.end(), m.group()) for rx in PATTERNS for m in rx.finditer(text)]
    matches.sort(key=lambda item: (item[0], -(item[1]-item[0])))
    picked = []
    end = 0
    for start, stop, token in matches:
        if start >= end:
            picked.append((start, stop, token))
            end = stop
    return picked


def opaque_tokens(text):
    return [token for _, _, token in spans(text)]


@dataclass(frozen=True)
class Protected:
    source: str
    masked: str
    tokens: tuple[str, ...]
    markers: tuple[str, ...]


def protect(source):
    if "[VNT" in source:
        raise ValueError("reserved marker collision in source")
    found = spans(source)
    if len(found) > 999:
        raise ValueError("too many protected occurrences")
    markers = tuple(f"[VNT{i:03}]" for i in range(len(found)))
    pieces = []
    position = 0
    for marker, (start, end, _) in zip(markers, found):
        pieces.extend((source[position:start], marker))
        position = end
    pieces.append(source[position:])
    return Protected(source, "".join(pieces), tuple(t for _, _, t in found), markers)


def restore(protected, raw):
    actual = MARKER.findall(raw)
    if actual != list(protected.markers):
        raise ValueError("missing/extra/reordered/duplicated marker")
    remainder = MARKER.sub("", raw)
    if "[VNT" in remainder or opaque_tokens(remainder):
        raise ValueError("unknown/damaged marker or injected raw structural token")
    result = raw
    for marker, original in zip(protected.markers, protected.tokens):
        result = result.replace(marker, original)
    if opaque_tokens(result) != list(protected.tokens):
        raise ValueError("restored token sequence differs from source")
    problems = mt_check.structural_problems({"source_text": protected.source}, result)
    if problems:
        raise ValueError("existing structural gate: " + "; ".join(problems))
    return result


def sanitize_context(text):
    # Reference symbols are not target identities; never expose their spelling.
    result = text
    for start, end, _ in reversed(spans(text)):
        result = result[:start] + " reference " + result[end:]
    return " ".join(result.split())
