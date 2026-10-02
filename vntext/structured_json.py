"""Safe field-level JSON extraction and patching.

JSON is handled as a structured document, never as line text.  Each extracted
string carries a JSON Pointer and the patcher checks the original value at that
pointer before rewriting the document.
"""

from __future__ import annotations

import codecs
import json
import re
from pathlib import Path
from typing import Any, Iterable

from vntext.entry import Entry
from vntext.extract_constants import UI_SHORT_TEXT
from vntext.extract_text import textasset_line_quality, translatable_field
from vntext.patchability import STRUCTURED_JSON_PATCH_PROOF


def _escape_pointer_part(value: str) -> str:
    return str(value).replace("~", "~0").replace("/", "~1")


def _unescape_pointer_part(value: str) -> str:
    return str(value).replace("~1", "/").replace("~0", "~")


def _iter_string_values(value: Any, pointer: str = "") -> Iterable[tuple[str, str]]:
    if isinstance(value, dict):
        for key, child in value.items():
            child_pointer = f"{pointer}/{_escape_pointer_part(key)}"
            yield from _iter_string_values(child, child_pointer)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from _iter_string_values(child, f"{pointer}/{index}")
    elif isinstance(value, str) and pointer:
        yield pointer, value


def _pointer_field_path(pointer: str) -> str:
    parts = [
        _unescape_pointer_part(part)
        for part in str(pointer).split("/")[1:]
        if part and not part.isdigit()
    ]
    return ".".join(parts) or "value"


def _read_json(path: Path) -> tuple[Any, bool, str, str]:
    raw = path.read_bytes()
    has_bom = raw.startswith(codecs.BOM_UTF8)
    text = raw.decode("utf-8-sig")
    return json.loads(text), has_bom, text, "\r\n" if "\r\n" in text else "\n"


def extract_structured_json(path: Path, root: Path) -> Iterable[Entry]:
    """Yield eligible JSON string leaves with proof-backed JSON Pointer locators."""

    try:
        document, _has_bom, _text, _newline = _read_json(path)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return

    rel = path.relative_to(root).as_posix()
    for pointer, value in _iter_string_values(document):
        if not value or value != value.strip() or not textasset_line_quality(value):
            continue
        field_path = _pointer_field_path(pointer)
        last_field = field_path.rsplit(".", 1)[-1].lower()
        technical_field = last_field in {"name", "key", "id", "guid", "path", "address"}
        if not translatable_field(field_path, value) and (
            technical_field or value.lower() not in UI_SHORT_TEXT
        ):
            continue
        yield Entry(
            source_text=value,
            file_path=rel,
            context=f"json:{pointer}",
            object_info=f"JSON Pointer {pointer}",
            import_method="structured_json_value",
            safety="safe",
            locator={"json_pointer": pointer, "value_type": "string"},
            backend="structured_json",
            patch_proof=dict(STRUCTURED_JSON_PATCH_PROOF),
        ).finalize()


def _get_pointer_value(document: Any, pointer: str) -> Any:
    current = document
    parts = str(pointer).split("/")[1:]
    for raw_part in parts:
        part = _unescape_pointer_part(raw_part)
        if isinstance(current, dict):
            if part not in current:
                return None
            current = current[part]
        elif isinstance(current, list):
            try:
                current = current[int(part)]
            except (ValueError, IndexError):
                return None
        else:
            return None
    return current


def _set_pointer_value(document: Any, pointer: str, value: str) -> bool:
    parts = str(pointer).split("/")[1:]
    if not parts:
        return False
    current = document
    for raw_part in parts[:-1]:
        part = _unescape_pointer_part(raw_part)
        if isinstance(current, dict):
            if part not in current:
                return False
            current = current[part]
        elif isinstance(current, list):
            try:
                current = current[int(part)]
            except (ValueError, IndexError):
                return False
        else:
            return False
    last = _unescape_pointer_part(parts[-1])
    if isinstance(current, dict):
        if last not in current:
            return False
        current[last] = value
        return True
    if isinstance(current, list):
        try:
            index = int(last)
            current[index] = value
            return True
        except (ValueError, IndexError):
            return False
    return False


def _indent_width(text: str) -> int:
    match = re.search(r"\n([ \t]+)[\"}]", text)
    if not match:
        return 2
    whitespace = match.group(1)
    return len(whitespace.expandtabs(4)) or 2


def patch_structured_json(
    source: Path,
    target: Path,
    items: Iterable[tuple[dict, str]],
) -> tuple[int, int]:
    """Patch JSON string values, returning ``(changed, skipped)`` counts."""

    document, has_bom, original_text, newline = _read_json(source)
    changed = 0
    skipped = 0
    for entry, translation in items:
        locator = entry.get("locator") or {}
        pointer = str(locator.get("json_pointer") or "")
        source_text = str(entry.get("source_text") or "")
        current = _get_pointer_value(document, pointer)
        if not pointer or not isinstance(current, str) or current != source_text:
            skipped += 1
            continue
        if _set_pointer_value(document, pointer, str(translation)):
            changed += 1
        else:
            skipped += 1

    pretty = "\n" in original_text or "\r" in original_text
    rendered = json.dumps(
        document,
        ensure_ascii=False,
        indent=_indent_width(original_text) if pretty else None,
        separators=None if pretty else (",", ":"),
    )
    if newline != "\n":
        rendered = rendered.replace("\n", newline)
    if original_text.endswith(("\n", "\r")):
        rendered += newline
    payload = (codecs.BOM_UTF8 if has_bom else b"") + rendered.encode("utf-8")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(payload)
    return changed, skipped


__all__ = ["extract_structured_json", "patch_structured_json"]
