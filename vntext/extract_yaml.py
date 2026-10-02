"""Bounded YAML text inventory for the generic extraction boundary.

YAML is intentionally not parsed into the patch flow here.  YAML permits
anchors, tags, aliases, flow collections and application-specific scalar
rules, so a line scanner cannot prove a stable writer.  It only exposes
display-like scalar candidates for manual review and never attaches proof.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Iterable

from vntext.entry import Entry


MAX_YAML_BYTES = 8 * 1024 * 1024
MAX_YAML_LINES = 200_000
MAX_YAML_TEXT_CHARS = 16_384
MAX_YAML_ENTRIES = 10_000
_MAPPING_RE = re.compile(r"^(?P<indent>\s*)(?P<key>[^:#\n][^:\n]*):(?P<value>.*)$")
_LIST_RE = re.compile(r"^(?P<indent>\s*)-\s+(?P<value>.+)$")
_BLOCK_MARKERS = {"|", ">", "|-", "|+", ">-", ">+"}
_NULLISH = {"", "null", "~", "true", "false", "yes", "no", "on", "off"}


def _strip_yaml_comment(value: str) -> str:
    quote: str | None = None
    escaped = False
    for index, char in enumerate(value):
        if quote == '"' and escaped:
            escaped = False
            continue
        if quote == '"' and char == "\\":
            escaped = True
            continue
        if char in {"'", '"'}:
            if quote is None:
                quote = char
            elif quote == char:
                quote = None
            continue
        if char == "#" and quote is None and (index == 0 or value[index - 1].isspace()):
            return value[:index].rstrip()
    return value.rstrip()


def _unquote_yaml_scalar(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] == "'":
        return value[1:-1].replace("''", "'")
    if len(value) >= 2 and value[0] == value[-1] == '"':
        try:
            decoded = json.loads(value)
        except (TypeError, ValueError, json.JSONDecodeError):
            return value[1:-1]
        return decoded if isinstance(decoded, str) else value[1:-1]
    return value


def _candidate_scalar(value: str) -> str | None:
    value = _strip_yaml_comment(value)
    value = re.sub(r"^(?:![^\s]+|&[^\s]+)\s+", "", value.strip())
    value = _unquote_yaml_scalar(value)
    if not value or len(value) > MAX_YAML_TEXT_CHARS or "\x00" in value:
        return None
    if value.casefold() in _NULLISH:
        return None
    if value.startswith(("[", "{")) and value.endswith(("]", "}")):
        return None
    if not any(char.isalpha() for char in value):
        return None
    from vntext.extract_naninovel import plausible_text

    return value if plausible_text(value, strict=False) else None


def extract_yaml_text_candidates(path: Path, root: Path) -> Iterable[Entry]:
    """Emit bounded YAML scalar candidates as explicit review-only entries."""

    size = path.stat().st_size
    if size > MAX_YAML_BYTES:
        raise ValueError(f"YAML inventory size {size} exceeds {MAX_YAML_BYTES} bytes")
    raw = path.read_bytes()
    text = raw.decode("utf-8-sig")
    rel = str(path.relative_to(root)) if path.is_relative_to(root) else str(path)
    emitted = 0
    block_parent: tuple[int, str] | None = None
    block_index = 0

    def make_entry(value: str, line_number: int, field: str, column: int) -> Entry | None:
        nonlocal emitted
        candidate = _candidate_scalar(value)
        if candidate is None or emitted >= MAX_YAML_ENTRIES:
            return None
        emitted += 1
        locator = {
            "line": line_number,
            "column": column,
            "yaml_path": field,
            "scalar_kind": "review_candidate",
        }
        return Entry(
            source_text=candidate,
            file_path=rel,
            context=f"yaml:line={line_number}:field={field}",
            object_info=f"yaml_field={field}",
            import_method="yaml_text_candidate",
            safety="review_only",
            locator=locator,
            backend="yaml_inventory",
            review_only=True,
        ).finalize()

    for line_number, raw_line in enumerate(text.splitlines(), start=1):
        if line_number > MAX_YAML_LINES or emitted >= MAX_YAML_ENTRIES:
            break
        line = raw_line.rstrip()
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        indent = len(line) - len(line.lstrip(" "))
        if block_parent is not None:
            parent_indent, field = block_parent
            if indent > parent_indent:
                block_index += 1
                entry = make_entry(
                    line.strip(),
                    line_number,
                    f"{field}.block[{block_index}]",
                    indent + 1,
                )
                if entry is not None:
                    yield entry
                continue
            block_parent = None
            block_index = 0

        mapping = _MAPPING_RE.match(line)
        if mapping:
            key = mapping.group("key").strip()
            value = mapping.group("value").strip()
            if value in _BLOCK_MARKERS:
                block_parent = (indent, key)
                continue
            column = line.find(mapping.group("value")) + 1
            entry = make_entry(value, line_number, key, max(1, column))
            if entry is not None:
                yield entry
            continue

        list_item = _LIST_RE.match(line)
        if list_item:
            value = list_item.group("value").strip()
            column = line.find(list_item.group("value")) + 1
            entry = make_entry(value, line_number, f"list[{line_number}]", max(1, column))
            if entry is not None:
                yield entry


__all__ = [
    "MAX_YAML_BYTES",
    "MAX_YAML_ENTRIES",
    "MAX_YAML_LINES",
    "MAX_YAML_TEXT_CHARS",
    "extract_yaml_text_candidates",
]
