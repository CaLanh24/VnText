"""Mask a piece of script text down to its SHAPE: syntax, nesting and token kinds survive, every name and every string is replaced.

A bug report from a game nobody here owns needs the structure of the place that failed (which keywords, how deep, how long) but never the words.
Keywords of the Ren'Py language stay; identifiers, strings, numbers and comments' words become class + length (+ a short hash so equal tokens can be
told apart).  ``rebuild_text`` turns a shape back into text of the same structure so the failing parser path can be replayed.
"""
from __future__ import annotations

import hashlib
import re

SHAPE_SCHEMA = 1
MAX_LINES = 80
MAX_TOKENS_PER_LINE = 120
HASH_MIN_LENGTH = 8          # shorter tokens would be easy to guess from their hash, so they carry none

KEYWORDS = frozenset("""
translate strings python style init define default label screen text old new return if elif else for while pass jump call scene show hide with menu
play stop queue voice nvl window say image transform layeredimage camera on onlayer as at behind zorder expression transform animation
class def import from in not and or is none true false lambda try except finally raise global nonlocal del assert yield print
hbox vbox frame fixed grid vpgrid viewport side button imagebutton textbutton bar vbar input key timer use add action hovered unhovered
""".split())
KNOWN_TAGS = frozenset("""
b i u s plain font size color outlinecolor alpha k cps w p nw fast done clear a rb rt art space vspace image noalt
""".split())

_TOKEN = re.compile(
    r"""(?P<str>"(?:\\.|[^"\\])*"?|'(?:\\.|[^'\\])*'?)|(?P<num>\d+(?:\.\d+)?)|(?P<word>[^\W\d]\w*)|(?P<space>\s+)|(?P<other>.)""",
    re.UNICODE | re.DOTALL,
)
_MARKER = re.compile(r"\{(/?)([A-Za-z_]*)(?:=[^}]*)?\}|\[[^\]\[]*\]|%\([^)]*\)[a-z]|%[sd]")


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", "replace")).hexdigest()[:8]


def _char_class(text: str) -> str:
    counts = {"lower": 0, "upper": 0, "digit": 0, "space": 0, "punct": 0, "non_ascii": 0}
    for ch in text:
        if ord(ch) > 127:
            counts["non_ascii"] += 1
        elif ch.islower():
            counts["lower"] += 1
        elif ch.isupper():
            counts["upper"] += 1
        elif ch.isdigit():
            counts["digit"] += 1
        elif ch.isspace():
            counts["space"] += 1
        else:
            counts["punct"] += 1
    return " ".join(f"{name}={count}" for name, count in counts.items() if count)


def _string_shape(raw: str) -> dict:
    quote = raw[0]
    closed = len(raw) > 1 and raw.endswith(quote) and not raw.endswith("\\" + quote)
    body = raw[1:-1] if closed else raw[1:]
    markers = []
    for match in _MARKER.finditer(body):
        text = match.group(0)
        if text.startswith("{"):
            tag = match.group(2).lower()
            markers.append("{" + match.group(1) + (tag if tag in KNOWN_TAGS else "?") + "}")
        elif text.startswith("["):
            markers.append("[id]")
        else:
            markers.append("%")
        if len(markers) >= 16:
            break
    shape = {"k": "str", "q": quote, "len": len(body), "cls": _char_class(body), "closed": closed}
    if markers:
        shape["markers"] = markers
    if len(body) >= HASH_MIN_LENGTH:
        shape["h"] = _hash(body)
    return shape


def _word_shape(word: str) -> dict | str:
    if word.lower() in KEYWORDS and word == word.lower():
        return word
    shape = {"k": "id", "len": len(word), "cls": _char_class(word)}
    if len(word) >= HASH_MIN_LENGTH:
        shape["h"] = _hash(word)
    return shape


def mask_line(raw: str) -> dict:
    expanded = raw.expandtabs(4)
    stripped = expanded.lstrip(" ")
    tokens: list = []
    gaps: list[str] = []
    gap = "0"
    comment = stripped.startswith("#")
    body = stripped[1:].lstrip(" ") if comment else stripped
    for match in _TOKEN.finditer(body):
        kind = match.lastgroup
        value = match.group(0)
        if kind == "space":
            gap = "1"
            continue
        gaps.append(gap)
        gap = "0"
        if kind == "str":
            tokens.append(_string_shape(value))
        elif kind == "num":
            tokens.append({"k": "num", "len": len(value)})
        elif kind == "word":
            tokens.append(_word_shape(value))
        else:
            tokens.append(value)
        if len(tokens) >= MAX_TOKENS_PER_LINE:
            tokens.append("…")
            gaps.append("0")
            break
    return {"indent": len(expanded) - len(stripped), "comment": comment, "tokens": tokens, "gaps": "".join(gaps)}


def mask_block(text: str) -> list[dict]:
    """Shape of every line of ``text`` (blank lines kept as empty shapes so line numbers and spacing survive)."""
    lines = text.splitlines()
    shaped = [mask_line(line) if line.strip() else {"blank": True} for line in lines[:MAX_LINES]]
    if len(lines) > MAX_LINES:
        shaped.append({"truncated_lines": len(lines) - MAX_LINES})
    return shaped


def _rebuild_string(token: dict) -> str:
    body = "".join(m.replace("?", "x") if m.startswith("{") else ("[v]" if m == "[id]" else "%s") for m in token.get("markers", []))
    return token["q"] + body + "x" * max(0, int(token["len"]) - len(body)) + (token["q"] if token.get("closed", True) else "")


def rebuild_text(shape: list[dict]) -> str:
    out = []
    for line in shape:
        if line.get("blank"):
            out.append("")
            continue
        if "tokens" not in line:
            continue
        gaps = line.get("gaps") or ""
        text = ""
        for index, token in enumerate(line["tokens"]):
            if isinstance(token, str):
                piece = token
            elif token["k"] == "str":
                piece = _rebuild_string(token)
            elif token["k"] == "num":
                piece = "1" * max(1, int(token["len"]))
            else:
                piece = "v" + "x" * max(0, int(token["len"]) - 1)
            text += (" " if index < len(gaps) and gaps[index] == "1" and text else "") + piece
        out.append(" " * int(line.get("indent", 0)) + ("# " if line.get("comment") else "") + text)
    return "\n".join(out) + "\n"
