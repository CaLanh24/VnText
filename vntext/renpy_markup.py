"""Ren'Py markup check for a translated line, before it is written into a game.

Ren'Py parses every displayed string twice: ``[...]`` is an interpolation (renpy.substitutions.parse) and ``{...}`` a text tag.  A line that breaks
the first one raises at display time and the game stops ("String '...' ends with an open format operation").  This module mirrors those two parsers
(state machine of the interpolation parser, tag stack of check_text_tags) on pure Python, so the check works without the Ren'Py SDK.

``markup_problems(source, translation)`` returns plain Vietnamese reasons (empty = safe); ``repair_markup(source, translation)`` tries a safe repair
(drop stray brackets/braces the source does not have, remove an empty tag pair the source does not have, restore the tags of the source) and
returns the repaired text only when the result passes; otherwise None.
"""
from __future__ import annotations

import re

REASON_BRACKET = "renpy_markup_invalid"

# Conversion flags Ren'Py accepts after "!" inside [...]
_FLAGS = set("rstiqulc!")


def interpolation_error(s: str) -> str:
    """Return '' when ``s`` parses as a Ren'Py interpolated string, else a short English cause (mirror of renpy.substitutions.parse)."""
    LITERAL, EXPRESSION, CONVERSION, FORMAT = 0, 1, 2, 3
    pos = -1
    size = len(s) - 1
    brackets = parens = 0
    state = LITERAL
    fmt = None
    conv = None
    while pos < size:
        pos += 1
        c = s[pos]
        if state == LITERAL:
            if c == "[":
                if s[pos + 1:pos + 2] == "[":
                    pos += 1
                else:
                    state = EXPRESSION
        elif state == EXPRESSION:
            if c == "(":
                parens += 1
            elif c == ")":
                if not parens:
                    break
                parens -= 1
            elif c in "\"'":
                chars, found = 1, 0
                if c * 2 == s[pos + 1:pos + 3]:
                    chars += 2
                    pos += 2
                while pos < size:
                    pos += 1
                    n = s[pos]
                    if n == c:
                        found += 1
                        if found == chars:
                            break
                    else:
                        if n == "\\":
                            pos += 1
                        found = 0
            elif parens:
                pass
            elif c == "[":
                brackets += 1
            elif c == "]":
                if brackets:
                    brackets -= 1
                else:
                    state = LITERAL
            elif brackets:
                pass
            elif c == "!":
                if s[pos + 1:pos + 2] == "=":
                    pos += 1
                else:
                    state = CONVERSION
            elif c == ":":
                state = FORMAT
        elif state == CONVERSION:
            if c == "]":
                state = LITERAL
            elif c == ":":
                state = FORMAT
                conv = True
            elif c not in _FLAGS:
                if fmt is None:
                    return "invalid conversion"
                state = FORMAT
        elif state == FORMAT:
            if c == "]":
                state = LITERAL
            elif conv is None and c == "!":
                state = CONVERSION
                fmt = True
    if state != LITERAL:
        return "open interpolation"
    return ""


_TAG_TOKEN = re.compile(r"\{\{|\{([^{}]*)\}|\{")


def _tags(s: str):
    """Yield text-tag bodies ('i', '/i', 'color=#f00') of ``s``; a lone '{' yields None (an unclosed tag).  '{{' is an escaped brace."""
    for m in _TAG_TOKEN.finditer(s):
        if m.group(0) == "{{":
            continue
        yield m.group(1)


def _tag_name(body: str) -> str:
    return body.partition("=")[0].partition(":")[0]


def _source_brackets(s: str) -> list[str]:
    return sorted(re.findall(r"\[[^\[\]]*\]", s.replace("[[", "")))


def _tag_problem(s: str) -> str:
    stack: list[str] = []
    for body in _tags(s):
        if body is None:
            return "unclosed tag"
        if body.startswith("#"):
            continue
        name = _tag_name(body)
        if name.startswith("/"):
            if not stack or stack[-1] != name[1:]:
                return "mismatched closing tag"
            stack.pop()
        elif name in _CLOSABLE:
            stack.append(name)
    return ""


_CLOSABLE = {"b", "i", "u", "s", "plain", "a", "color", "size", "font", "alpha", "outlinecolor", "k", "rt", "rb", "art", "cps", "shader", "image_unused"}
_EMPTY_PAIR = re.compile(r"\{([a-z]+)(?:[=:][^{}]*)?\}\s*\{/\1\}")


def markup_problems(source: str, translation: str) -> list[str]:
    """Plain Vietnamese reasons the translated line would break or mangle the game's markup.  Empty list = safe."""
    out: list[str] = []
    src = str(source or "")
    new = str(translation or "")
    err = interpolation_error(new)
    if err:
        out.append("Dấu [ ] không đóng hoặc sai (game sẽ báo lỗi và dừng)")
    elif _source_brackets(src) != _source_brackets(new):
        out.append("Mất hoặc đổi mục [tên] như câu gốc")
    tag_err = _tag_problem(new)
    if tag_err and not _tag_problem(src):
        out.append("Thẻ { } bị hỏng hoặc không đóng đúng")
    elif tag_err == "unclosed tag" and _tag_problem(src) == "unclosed tag" and new.count("{") != src.count("{"):
        out.append("Thẻ { } bị hỏng hoặc không đóng đúng")
    if len(_EMPTY_PAIR.findall(new)) > len(_EMPTY_PAIR.findall(src)):
        out.append("Có cặp thẻ rỗng thừa")
    return out


def has_markup_problem(source: str, translation: str) -> bool:
    return bool(markup_problems(source, translation))


_VALID_TOKEN = re.compile(r"\[\[|\{\{|\[[^\[\]{}]*\]|\{[^{}\[\]]*\}")


def _strip_stray(src: str, text: str) -> str:
    """Remove every '[' ']' '{' '}' that is not part of a well-formed token (escape, [name], {tag}); drop empty tag pairs the source lacks."""
    pieces = []
    last = 0
    for m in _VALID_TOKEN.finditer(text):
        pieces.append(re.sub(r"[\[\]{}]", "", text[last:m.start()]))
        pieces.append(m.group(0))
        last = m.end()
    pieces.append(re.sub(r"[\[\]{}]", "", text[last:]))
    out = "".join(pieces)
    if len(_EMPTY_PAIR.findall(out)) > len(_EMPTY_PAIR.findall(src)):
        out = _EMPTY_PAIR.sub(lambda m: "" if len(_EMPTY_PAIR.findall(src)) == 0 else m.group(0), out)
    return re.sub(r"[ \t]{2,}", " ", out).strip() if out != text else text


def repair_markup(source: str, translation: str) -> str | None:
    """A safe repaired translation, or None when no safe repair exists (the caller then blocks the line)."""
    src = str(source or "")
    new = str(translation or "")
    if not markup_problems(src, new):
        return new
    mended = re.sub(r"\[(/?[A-Za-z]+(?:[=:][^\[\]{}]*)?)\}", r"{}", new)      # "[i}" -> "{i}"
    mended = re.sub(r"\{(/?[A-Za-z]+(?:[=:][^\[\]{}]*)?)\]", r"{}", mended)   # "{/i]" -> "{/i}"
    candidates = [_strip_stray(src, mended)]
    try:
        from vntext.mt_translation_safety import heal_structure
        candidates.append(heal_structure(src, candidates[0]))
    except Exception:
        pass
    prose = re.sub(r"[\[\]{}]", "", re.sub(r"\[[^\[\]]*[\]}]|\{[^{}]*[}\]]", " ", new))
    prose = re.sub(r"\s{2,}", " ", prose).strip()
    try:
        from vntext.mt_translation_safety import heal_structure as _heal
        candidates.append(_heal(src, prose))
    except Exception:
        pass
    for cand in candidates:
        if cand and cand != new and not markup_problems(src, cand):
            from vntext.mt_check import PH, TAG
            if sorted(PH.findall(src)) == sorted(PH.findall(cand)) and sorted(TAG.findall(src)) == sorted(TAG.findall(cand)):
                return cand
    return None


_QUOTED = re.compile(r'"(?:\\.|[^"\\])*"')


def overlay_problems(payload: str) -> list[tuple[int, str]]:
    """(line number, plain reason) for every line of a generated ``game/tl/<language>`` file that Ren'Py could not display.

    Checks the shown strings only: ``new "…"`` and the indented Say line of a ``translate <lang> <id>:`` block (comments and ``old`` lines are the original text)."""
    import json

    found: list[tuple[int, str]] = []
    for number, line in enumerate(str(payload or "").splitlines(), 1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or stripped.startswith("old ") or stripped.startswith("translate "):
            continue
        if not line.startswith("    "):
            continue
        m = _QUOTED.search(stripped[4:] if stripped.startswith("new ") else stripped)
        if not m:
            continue
        try:
            text = json.loads(m.group(0))
        except ValueError:
            found.append((number, "Chuỗi trong tệp bản dịch bị hỏng dấu nháy"))
            continue
        if interpolation_error(text):
            found.append((number, "Dấu [ ] không đóng hoặc sai (game sẽ báo lỗi và dừng)"))
        elif _tag_problem(text) == "unclosed tag":
            found.append((number, "Thẻ { } không đóng đúng"))
    return found


def describe_overlay_problems(problems: list[tuple[int, str]], *, limit: int = 8) -> str:
    shown = "; ".join(f"dòng {n}: {why}" for n, why in problems[:limit])
    more = f" (và {len(problems) - limit} dòng khác)" if len(problems) > limit else ""
    return shown + more
