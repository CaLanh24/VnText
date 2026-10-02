"""Strict Unity Localization StringTable extraction and field access.

Unity Localization stores localized values in serialized ``StringTable``
objects.  The class identity alone is not enough to promote a row: this
module only recognizes the concrete ``m_TableData[*].m_Localized`` field path,
keeps the exact source value as a precondition, and leaves all other table
schemas in review.
"""

from __future__ import annotations

import re
from typing import Any, Iterable

from vntext.entry import Entry
from vntext.patchability import UNITY_LOCALIZATION_PATCH_PROOF


UNITY_LOCALIZATION_TABLE_CLASSES = frozenset({"StringTable"})
_LOCALIZED_FIELD_RE = re.compile(
    r"(?:^|\.)m_tabledata(?:\.array)?(?:\.data)?(?:\[\d+\])\.m_localized$",
    re.IGNORECASE,
)
_PATH_TOKEN_RE = re.compile(r"[^.\[\]]+|\[\d+\]")


def is_unity_localization_table_class(class_name: str) -> bool:
    """Return true only for the supported StringTable object identity."""

    compact = str(class_name or "").rsplit(".", 1)[-1].strip()
    return compact in UNITY_LOCALIZATION_TABLE_CLASSES


def is_localized_value_field_path(field_path: str) -> bool:
    """Recognize a serialized StringTable localized-value field path."""

    return bool(_LOCALIZED_FIELD_RE.fullmatch(str(field_path or "").strip()))


def _path_tokens(field_path: str) -> list[str]:
    return _PATH_TOKEN_RE.findall(str(field_path or ""))


def _get_path_value(tree: Any, field_path: str) -> Any:
    current = tree
    for token in _path_tokens(field_path):
        if token.startswith("["):
            if not isinstance(current, list):
                return None
            index = int(token[1:-1])
            if index < 0 or index >= len(current):
                return None
            current = current[index]
        else:
            if not isinstance(current, dict) or token not in current:
                return None
            current = current[token]
    return current


def get_unity_localization_field(tree: Any, field_path: str) -> str | None:
    """Read a concrete localized field from a UnityPy TypeTree mapping."""

    if not is_localized_value_field_path(field_path):
        return None
    value = _get_path_value(tree, field_path)
    return value if isinstance(value, str) else None


def get_unity_localization_entry_id(tree: Any, field_path: str) -> int | str | None:
    """Return the sibling ``m_Id`` for one StringTable entry when present.

    Unity Localization table entries are semantically identified by ``m_Id``;
    the array index is only a structural locator.  Requiring this identity in
    newly extracted rows prevents a reordered table from silently receiving a
    translation intended for a different key.  The helper remains optional at
    the writer boundary for old packages created before this metadata existed.
    """

    if not is_localized_value_field_path(field_path):
        return None
    id_path = re.sub(r"m_localized$", "m_Id", field_path, flags=re.IGNORECASE)
    value = _get_path_value(tree, id_path)
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        return None
    if isinstance(value, str) and not value.strip():
        return None
    return value


def set_unity_localization_field(tree: Any, field_path: str, source: str, translated: str) -> bool:
    """Set one localized value only when its source precondition still matches."""

    if get_unity_localization_field(tree, field_path) != source:
        return False
    tokens = _path_tokens(field_path)
    if not tokens:
        return False
    current = tree
    for token in tokens[:-1]:
        if token.startswith("["):
            if not isinstance(current, list):
                return False
            index = int(token[1:-1])
            if index < 0 or index >= len(current):
                return False
            current = current[index]
        else:
            if not isinstance(current, dict) or token not in current:
                return False
            current = current[token]
    last = tokens[-1]
    if last.startswith("["):
        return False
    if not isinstance(current, dict) or not isinstance(current.get(last), str):
        return False
    current[last] = translated
    return True


def _localization_value_quality(text: str) -> bool:
    from vntext.extract_quality import is_ui_label_text, raw_text_quality

    cleaned = str(text or "").strip()
    return bool(cleaned) and (
        is_ui_label_text(cleaned) or raw_text_quality(cleaned, for_main=True)
    )


def iter_unity_localization_entries(
    tree: Any,
    rel: str,
    path_id: str,
    object_info: str,
    class_name: str,
) -> Iterable[Entry]:
    """Yield proven StringTable value rows from one TypeTree object."""

    if not is_unity_localization_table_class(class_name):
        return
    for field_path, value in _walk_strings(tree):
        if not is_localized_value_field_path(field_path):
            continue
        source = str(value or "").strip()
        if not _localization_value_quality(source):
            continue
        entry_id = get_unity_localization_entry_id(tree, field_path)
        if entry_id is None:
            # A localized value without its table-entry identity is not safe to
            # promote: the index alone does not survive table reordering.
            continue
        match = re.search(r"\[(\d+)\]\.m_localized$", field_path, re.IGNORECASE)
        entry_index = int(match.group(1)) if match else None
        entry_id_field_path = re.sub(r"m_localized$", "m_Id", field_path, flags=re.IGNORECASE)
        yield Entry(
            source_text=source,
            file_path=rel,
            context=f"UnityLocalization:StringTable:id:{entry_id}:entry:{entry_index}",
            object_info=f"{object_info}:{class_name}",
            import_method="unity_localization_string",
            safety="safe",
            locator={
                "path_id": str(path_id),
                "field_path": field_path,
                "class_name": class_name,
                "table_kind": "StringTable",
                "entry_index": entry_index,
                "entry_id": entry_id,
                "entry_id_field_path": entry_id_field_path,
            },
            backend="unity_localization_string_table",
            patch_proof=dict(UNITY_LOCALIZATION_PATCH_PROOF),
        ).finalize()


def _walk_strings(value: Any, prefix: str = "") -> Iterable[tuple[str, str]]:
    if isinstance(value, str):
        yield prefix or "$", value
    elif isinstance(value, dict):
        for key, item in value.items():
            child = f"{prefix}.{key}" if prefix else str(key)
            yield from _walk_strings(item, child)
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from _walk_strings(item, f"{prefix}[{index}]")


__all__ = [
    "UNITY_LOCALIZATION_TABLE_CLASSES",
    "get_unity_localization_entry_id",
    "get_unity_localization_field",
    "is_localized_value_field_path",
    "is_unity_localization_table_class",
    "iter_unity_localization_entries",
    "set_unity_localization_field",
]
