"""Per-target patch read-back verification.

The patch writer and the read-back verifier are intentionally separate.  A
successful write is recorded as ``PATCHED``; only this module may promote a
target to ``READ_BACK_VERIFIED`` after reopening the copied output and
resolving the exact locator again.
"""

from __future__ import annotations

import codecs
import csv
import json
import multiprocessing
import os
import subprocess
import sys
import sqlite3
import traceback
from pathlib import Path
from typing import Any

from vntext.patch_safety import resolve_game_source_file


PASS = "PASS"
FAIL = "FAIL"
NOT_TESTABLE = "NOT_TESTABLE"
TIMEOUT = "TIMEOUT"

DEFAULT_READBACK_TIMEOUT_SECONDS = 300.0


def readback_timeout_seconds() -> float:
    """Return the finite Unity/read-back deadline used by the patch route."""

    raw = os.environ.get("VNTEXT_PATCH_READBACK_TIMEOUT_SECONDS", "")
    try:
        value = float(raw) if raw.strip() else DEFAULT_READBACK_TIMEOUT_SECONDS
    except (TypeError, ValueError):
        value = DEFAULT_READBACK_TIMEOUT_SECONDS
    return max(1.0, value)

_UNSUPPORTED_METHODS = frozenset(
    {
        "raw_review_only",
        "external_dump_reimport",
        "review_only",
        "raw_fixed_slot",
        "naninovel_blob_string",
        "naninovel_raw_candidate",
    }
)

_UNITY_REOPEN_METHODS = frozenset(
    {
        "unity_textasset_line",
        "unity_textasset_table_cell",
        "unity_textasset_script",
        "unity_ui_text",
        "unity_typetree_field",
        "unity_localization_string",
        "naninovel_script_string",
        "naninovel_choice",
        "naninovel_print",
    }
)


def _locations(entry: dict[str, Any]) -> list[dict[str, Any]]:
    primary = entry.get("locator") or {}
    values = [primary]
    values.extend(
        item.get("locator") if isinstance(item, dict) and "locator" in item else item
        for item in (entry.get("duplicate_locations") or [])
    )
    return [dict(item or {}) for item in values]


def _result(
    entry: dict[str, Any],
    ordinal: int,
    locator: dict[str, Any],
    status: str,
    reason: str,
    *,
    write_status: str | None = None,
    actual: str = "",
) -> dict[str, Any]:
    if write_status is None:
        write_status = "COMPLETED" if status == PASS else status
    return {
        "key": str(entry.get("key") or ""),
        "duplicate_ordinal": ordinal,
        "method": str(entry.get("import_method") or ""),
        "locator": locator,
        "status": status,
        "write_status": write_status,
        "readback_status": status,
        "final_verification": status,
        "reason": str(reason or ""),
        "actual_hash": _sha256(actual) if actual else "",
    }


def _sha256(value: str) -> str:
    import hashlib

    return hashlib.sha256(str(value).encode("utf-8", "surrogatepass")).hexdigest()


def _decode_text(path: Path) -> str:
    return path.read_bytes().decode("utf-8-sig")


def _line_index(locator: dict[str, Any]) -> int | None:
    value = locator.get("line")
    if value is None:
        return None
    try:
        value = int(value)
    except (TypeError, ValueError):
        return None
    return value - 1 if value >= 1 else value


def _verify_plain(
    source: Path,
    target: Path,
    entry: dict[str, Any],
    ordinal: int,
    locator: dict[str, Any],
    translation: str,
) -> dict[str, Any]:
    index = _line_index(locator)
    if index is None:
        return _result(entry, ordinal, locator, NOT_TESTABLE, "line locator missing")
    try:
        source_lines = _decode_text(source).splitlines(keepends=True)
        target_lines = _decode_text(target).splitlines(keepends=True)
    except (OSError, UnicodeDecodeError) as exc:
        return _result(entry, ordinal, locator, FAIL, f"text reopen failed: {exc}", write_status=FAIL)
    if not (0 <= index < len(source_lines)) or not (0 <= index < len(target_lines)):
        return _result(entry, ordinal, locator, FAIL, "line locator out of range", write_status=FAIL)
    source_line = source_lines[index]
    target_line = target_lines[index]
    source_content = source_line.rstrip("\r\n")
    target_content = target_line.rstrip("\r\n")
    source_text = str(entry.get("source_text") or "")
    if source_text not in source_content:
        return _result(entry, ordinal, locator, FAIL, "source precondition drift", write_status=FAIL)
    expected = source_content.replace(source_text, str(translation), 1)
    if target_content != expected:
        return _result(
            entry,
            ordinal,
            locator,
            FAIL,
            "read-back value mismatch",
            write_status=FAIL,
            actual=target_content,
        )
    return _result(entry, ordinal, locator, PASS, "exact line read-back", actual=target_content)


def _verify_json(
    source: Path,
    target: Path,
    entry: dict[str, Any],
    ordinal: int,
    locator: dict[str, Any],
    translation: str,
) -> dict[str, Any]:
    from vntext.structured_json import _get_pointer_value

    pointer = str(locator.get("json_pointer") or "")
    if not pointer:
        return _result(entry, ordinal, locator, NOT_TESTABLE, "JSON pointer missing")
    try:
        source_doc = json.loads(_decode_text(source))
        target_doc = json.loads(_decode_text(target))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return _result(entry, ordinal, locator, FAIL, f"JSON reopen failed: {exc}", write_status=FAIL)
    source_value = _get_pointer_value(source_doc, pointer)
    target_value = _get_pointer_value(target_doc, pointer)
    source_text = str(entry.get("source_text") or "")
    if source_value != source_text:
        return _result(entry, ordinal, locator, FAIL, "JSON source precondition drift", write_status=FAIL)
    if target_value != str(translation):
        return _result(entry, ordinal, locator, FAIL, "JSON read-back value mismatch", write_status=FAIL, actual=str(target_value or ""))
    return _result(entry, ordinal, locator, PASS, "JSON pointer read-back", actual=str(target_value))


def _verify_csv(
    source: Path,
    target: Path,
    entry: dict[str, Any],
    ordinal: int,
    locator: dict[str, Any],
    translation: str,
) -> dict[str, Any]:
    from vntext.structured_csv import _read_csv

    try:
        source_rows, _bom, _newline, _dialect = _read_csv(source)
        target_rows, _bom2, _newline2, _dialect2 = _read_csv(target)
        row_index = int(locator.get("row_index"))
        column_index = int(locator.get("column_index"))
    except (OSError, UnicodeDecodeError, csv.Error, TypeError, ValueError) as exc:
        return _result(entry, ordinal, locator, FAIL, f"CSV reopen failed: {exc}", write_status=FAIL)
    source_text = str(entry.get("source_text") or "")
    if not (0 <= row_index < len(source_rows)) or not (0 <= column_index < len(source_rows[row_index])):
        return _result(entry, ordinal, locator, FAIL, "CSV source locator out of range", write_status=FAIL)
    if not (0 <= row_index < len(target_rows)) or not (0 <= column_index < len(target_rows[row_index])):
        return _result(entry, ordinal, locator, FAIL, "CSV target locator out of range", write_status=FAIL)
    if source_rows[row_index][column_index] != source_text:
        return _result(entry, ordinal, locator, FAIL, "CSV source precondition drift", write_status=FAIL)
    actual = target_rows[row_index][column_index]
    if actual != str(translation):
        return _result(entry, ordinal, locator, FAIL, "CSV read-back value mismatch", write_status=FAIL, actual=actual)
    return _result(entry, ordinal, locator, PASS, "CSV cell read-back", actual=actual)


def _verify_xml(
    source: Path,
    target: Path,
    entry: dict[str, Any],
    ordinal: int,
    locator: dict[str, Any],
    translation: str,
) -> dict[str, Any]:
    from vntext.structured_xml import _element_at, _read_xml

    try:
        source_tree, _bom, _newline, _final = _read_xml(source)
        target_tree, _bom2, _newline2, _final2 = _read_xml(target)
    except Exception as exc:
        return _result(entry, ordinal, locator, FAIL, f"XML reopen failed: {exc}", write_status=FAIL)
    source_element = _element_at(source_tree.getroot(), locator.get("xml_path", []))
    target_element = _element_at(target_tree.getroot(), locator.get("xml_path", []))
    if source_element is None or target_element is None:
        return _result(entry, ordinal, locator, FAIL, "XML locator missing", write_status=FAIL)
    kind = str(locator.get("node_kind") or "text")
    attribute = str(locator.get("attribute") or "")
    if kind == "attribute":
        source_value = source_element.attrib.get(attribute)
        actual = target_element.attrib.get(attribute)
    elif kind == "text":
        source_value = source_element.text
        actual = target_element.text
    else:
        return _result(entry, ordinal, locator, NOT_TESTABLE, "XML node kind unsupported")
    if source_value != str(entry.get("source_text") or ""):
        return _result(entry, ordinal, locator, FAIL, "XML source precondition drift", write_status=FAIL)
    expected = str(entry.get("source_text") or "")
    leading = expected[: len(expected) - len(expected.lstrip())]
    trailing = expected[len(expected.rstrip()) :]
    expected_value = f"{leading}{translation}{trailing}"
    if actual != expected_value:
        return _result(entry, ordinal, locator, FAIL, "XML read-back value mismatch", write_status=FAIL, actual=str(actual or ""))
    return _result(entry, ordinal, locator, PASS, "XML value read-back", actual=str(actual))


def _quote_identifier(value: str) -> str:
    return '"' + str(value).replace('"', '""') + '"'


def _verify_sqlite(
    source: Path,
    target: Path,
    entry: dict[str, Any],
    ordinal: int,
    locator: dict[str, Any],
    translation: str,
) -> dict[str, Any]:
    table = str(locator.get("table") or "")
    column = str(locator.get("column") or "")
    try:
        rowid = int(locator.get("rowid"))
    except (TypeError, ValueError):
        return _result(entry, ordinal, locator, FAIL, "SQLite rowid invalid", write_status=FAIL)
    if not table or not column:
        return _result(entry, ordinal, locator, FAIL, "SQLite locator incomplete", write_status=FAIL)
    try:
        source_conn = sqlite3.connect(source)
        target_conn = sqlite3.connect(target)
        query = f"SELECT {_quote_identifier(column)} FROM {_quote_identifier(table)} WHERE rowid = ?"
        source_value = source_conn.execute(query, (rowid,)).fetchone()
        target_value = target_conn.execute(query, (rowid,)).fetchone()
    except (OSError, sqlite3.Error) as exc:
        return _result(entry, ordinal, locator, FAIL, f"SQLite reopen failed: {exc}", write_status=FAIL)
    finally:
        try:
            source_conn.close()
        except UnboundLocalError:
            pass
        try:
            target_conn.close()
        except UnboundLocalError:
            pass
    expected_source = str(entry.get("source_text") or "")
    if not source_value or str(source_value[0]) != expected_source:
        return _result(entry, ordinal, locator, FAIL, "SQLite source precondition drift", write_status=FAIL)
    actual = str(target_value[0]) if target_value else ""
    if actual != str(translation):
        return _result(entry, ordinal, locator, FAIL, "SQLite read-back value mismatch", write_status=FAIL, actual=actual)
    return _result(entry, ordinal, locator, PASS, "SQLite value read-back", actual=actual)


def _get_typetree_value(tree: Any, field_path: str) -> Any:
    import re

    tokens = re.findall(r"[^.\[\]]+|\[\d+\]", str(field_path or ""))
    current = tree
    for token in tokens:
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


def _unity_object(env: Any, path_id: str) -> Any:
    for obj in getattr(env, "objects", []) or []:
        if str(getattr(obj, "path_id", "")) == str(path_id):
            return obj
    return None


def _unity_objects_from_map(
    env: Any,
    path_id: str,
    object_map: dict[str, list[Any]] | None,
) -> list[Any]:
    if object_map is not None:
        value = object_map.get(str(path_id)) or []
        return list(value) if isinstance(value, list) else [value]
    return [
        obj
        for obj in getattr(env, "objects", []) or []
        if str(getattr(obj, "path_id", "")) == str(path_id)
    ]


def _unity_object_from_map(
    env: Any,
    path_id: str,
    object_map: dict[str, list[Any]] | None,
) -> Any:
    return next(iter(_unity_objects_from_map(env, path_id, object_map)), None)


def _unity_object_map(env: Any) -> dict[str, list[Any]]:
    """Index every object because UnityFS can reuse path IDs across files."""

    result: dict[str, list[Any]] = {}
    for obj in getattr(env, "objects", []) or []:
        result.setdefault(str(getattr(obj, "path_id", "")), []).append(obj)
    return result


def _textasset_script(obj: Any) -> str | None:
    data = obj.read()
    value = getattr(data, "m_Script", None)
    if value is None:
        value = getattr(data, "script", None)
    if isinstance(value, (bytes, bytearray)):
        return bytes(value).decode("utf-8", errors="ignore")
    return value if isinstance(value, str) else None


def _unity_ui_text_value(obj: Any, data: Any, field_path: str) -> str | None:
    """Read a UI string from either UnityPy's direct view or its TypeTree.

    Simple UI components expose ``m_Text`` directly from ``obj.read()``.  UI
    containers such as Dropdown keep the visible text below nested TypeTree
    paths (for example ``m_Options.m_Options[3].m_Text``), where the direct
    object view has no matching attribute.  Read-back must resolve the same
    locator shape used by extraction/patching instead of silently checking only
    the last path segment.
    """

    path = str(field_path or "m_Text")
    field = path.split(".")[-1]
    paths = [path]
    # The extractor intentionally uses the stable UI locator ``m_Text`` for
    # both legacy UI.Text and TMP components.  TMP's serialized TypeTree uses
    # the lower-case field ``m_text`` instead; read-back must honor that
    # compatibility alias without weakening the path_id check.
    if field == "m_Text":
        paths.extend(path[: -len(field)] + alias for alias in ("m_text", "text"))
    for candidate in paths:
        direct = getattr(data, candidate.split(".")[-1], None)
        if isinstance(direct, str):
            return direct
    try:
        tree = obj.read_typetree()
    except Exception:
        return None
    for candidate in paths:
        value = _get_typetree_value(tree, candidate)
        if isinstance(value, str):
            return value
    return None


def _unity_raw_values(obj: Any) -> list[str]:
    """Return aligned serialized strings without requiring a TypeTree."""

    from vntext.extract_naninovel import _object_raw_bytes
    from vntext.extract_unity import _scan_unity_length_prefixed_strings

    raw = _object_raw_bytes(obj)
    if not raw:
        return []
    return [
        str(item.get("text") or "")
        for item in _scan_unity_length_prefixed_strings(
            raw,
            step=4,
            seeded=len(raw) > 512 * 1024,
        )
        if item.get("text")
    ]


def _unity_ui_pair_matches(
    source_obj: Any,
    target_obj: Any,
    source_text: str,
    translation: str,
    field_path: str,
) -> bool:
    def padded_equal(actual: Any, expected: str, *, source_has_padding: bool) -> bool:
        # Fixed-size UI slots use trailing ASCII spaces as binary padding.
        # Treat only that writer-introduced suffix as semantically neutral;
        # preserve intentional leading/internal/trailing spaces in translations.
        return (
            isinstance(actual, str)
            and actual == expected
        ) or (
            isinstance(actual, str)
            and source_has_padding
            and actual.rstrip(" ") == expected.rstrip(" ")
        ) or (
            isinstance(actual, str)
            and not expected.endswith(" ")
            and actual.rstrip(" ") == expected
        )

    source_values = _unity_raw_values(source_obj)
    target_values = _unity_raw_values(target_obj)
    for source_value in source_values:
        if source_text not in source_value:
            continue
        expected = source_value.replace(source_text, translation, 1)
        source_has_padding = bool(source_value.endswith(" ") and not source_text.endswith(" "))
        if any(
            padded_equal(value, expected, source_has_padding=source_has_padding)
            for value in target_values
        ):
            return True
    try:
        source_value = _unity_ui_text_value(source_obj, source_obj.read(), field_path)
        target_value = _unity_ui_text_value(target_obj, target_obj.read(), field_path)
    except Exception:
        return False
    return (
        isinstance(source_value, str)
        and isinstance(target_value, str)
        and source_text in source_value
        and padded_equal(
            target_value,
            source_value.replace(source_text, translation, 1),
            source_has_padding=bool(source_value.endswith(" ") and not source_text.endswith(" ")),
        )
    )


def _verify_unity(
    source: Path,
    target: Path,
    entry: dict[str, Any],
    ordinal: int,
    locator: dict[str, Any],
    translation: str,
    *,
    environments: tuple[Any, Any] | None = None,
    object_maps: tuple[dict[str, list[Any]], dict[str, list[Any]]] | None = None,
    value_cache: dict[tuple[str, str], Any] | None = None,
) -> dict[str, Any]:
    source_env = None
    target_env = None
    source_obj = None
    target_obj = None
    try:
        if environments is None:
            import UnityPy

            source_env = UnityPy.load(str(source))
            target_env = UnityPy.load(str(target))
        else:
            source_env, target_env = environments
    except Exception as exc:
        return _result(entry, ordinal, locator, NOT_TESTABLE, f"Unity reopen unavailable: {exc}")
    path_id = str(locator.get("path_id") or "")
    source_map = object_maps[0] if object_maps is not None else None
    target_map = object_maps[1] if object_maps is not None else None
    source_obj = _unity_object_from_map(source_env, path_id, source_map)
    target_obj = _unity_object_from_map(target_env, path_id, target_map)
    if source_obj is None or target_obj is None:
        return _result(entry, ordinal, locator, FAIL, "Unity path_id not found after reopen", write_status=FAIL)
    method = str(entry.get("import_method") or "")
    source_text = str(entry.get("source_text") or "")
    value_cache = value_cache if value_cache is not None else {}
    try:
        if method in {"unity_textasset_line", "unity_textasset_table_cell", "unity_textasset_script"}:
            cache_key = ("textasset", path_id)
            scripts = value_cache.get(cache_key)
            if scripts is None:
                scripts = (_textasset_script(source_obj), _textasset_script(target_obj))
                value_cache[cache_key] = scripts
            source_script, target_script = scripts
            if source_script is None or target_script is None:
                return _result(entry, ordinal, locator, FAIL, "TextAsset script missing", write_status=FAIL)
            if method == "unity_textasset_script":
                if source_script != source_text:
                    return _result(entry, ordinal, locator, FAIL, "TextAsset source precondition drift", write_status=FAIL)
                actual = target_script
                if actual != translation:
                    return _result(entry, ordinal, locator, FAIL, "TextAsset script read-back mismatch", write_status=FAIL, actual=actual)
                return _result(entry, ordinal, locator, PASS, "TextAsset script read-back", actual=actual)
            index = int(locator.get("line_index"))
            source_lines = source_script.splitlines(keepends=True)
            target_lines = target_script.splitlines(keepends=True)
            if not (0 <= index < len(source_lines)) or not (0 <= index < len(target_lines)):
                return _result(entry, ordinal, locator, FAIL, "TextAsset line locator out of range", write_status=FAIL)
            source_line = source_lines[index].rstrip("\r\n")
            target_line = target_lines[index].rstrip("\r\n")
            if method == "unity_textasset_table_cell":
                from vntext.patch_constants import _semicolon_csv_read

                column = int(locator.get("column_index"))
                source_cells = _semicolon_csv_read(source_lines[index])
                target_cells = _semicolon_csv_read(target_lines[index])
                if not (0 <= column < len(source_cells)) or not (0 <= column < len(target_cells)):
                    return _result(entry, ordinal, locator, FAIL, "TextAsset table locator out of range", write_status=FAIL)
                if source_cells[column] != source_text:
                    return _result(entry, ordinal, locator, FAIL, "TextAsset table source precondition drift", write_status=FAIL)
                actual = target_cells[column]
            else:
                prefix = str(locator.get("prefix") or "")
                if source_text not in source_line:
                    return _result(entry, ordinal, locator, FAIL, "TextAsset line source precondition drift", write_status=FAIL)
                # Key/value lines can contain the source token in the key as
                # well as in the value (``Default: Default``).  Mirror the
                # writer's suffix/prefix addressing so verification replaces
                # the value occurrence, never the key occurrence.
                if source_line.endswith(source_text):
                    expected_line = source_line[: -len(source_text)] + translation
                else:
                    if prefix and not source_line.startswith(prefix):
                        return _result(entry, ordinal, locator, FAIL, "TextAsset line source precondition drift", write_status=FAIL)
                    value_start = len(prefix)
                    value = source_line[value_start:]
                    if source_text not in value:
                        return _result(entry, ordinal, locator, FAIL, "TextAsset line source precondition drift", write_status=FAIL)
                    expected_line = source_line[:value_start] + value.replace(source_text, translation, 1)
                if target_line != expected_line:
                    return _result(entry, ordinal, locator, FAIL, "TextAsset line read-back mismatch", write_status=FAIL, actual=target_line)
                # The locator addresses a value inside the line.  The exact
                # line comparison above verifies the prefix/suffix, while the
                # value returned to the caller must be the translated value,
                # not the full serialized line (for example ``Key: value``).
                actual = translation
            if actual != translation:
                return _result(entry, ordinal, locator, FAIL, "TextAsset value read-back mismatch", write_status=FAIL, actual=actual)
            return _result(entry, ordinal, locator, PASS, "TextAsset value read-back", actual=actual)

        if method == "unity_ui_text":
            field_path = str(locator.get("field_path") or "m_Text")
            cache_key = ("ui", path_id)
            ui_pairs = value_cache.get(cache_key)
            if ui_pairs is None:
                source_objects = _unity_objects_from_map(source_env, path_id, source_map)
                target_objects = _unity_objects_from_map(target_env, path_id, target_map)
                ui_pairs = list(zip(source_objects, target_objects))
                value_cache[cache_key] = ui_pairs
            for source_candidate, target_candidate in ui_pairs:
                if _unity_ui_pair_matches(
                    source_candidate,
                    target_candidate,
                    source_text,
                    translation,
                    field_path,
                ):
                    return _result(entry, ordinal, locator, PASS, "Unity UI field read-back", actual=translation)
            source_values = [
                value
                for source_candidate, _target_candidate in ui_pairs
                for value in _unity_raw_values(source_candidate)
            ]
            if not any(source_text in value for value in source_values):
                return _result(entry, ordinal, locator, FAIL, "Unity UI source precondition drift", write_status=FAIL)
            return _result(entry, ordinal, locator, FAIL, "Unity UI read-back mismatch", write_status=FAIL)

        if method in {"unity_typetree_field", "unity_localization_string"}:
            cache_key = ("typetree", path_id)
            trees = value_cache.get(cache_key)
            if trees is None:
                trees = (source_obj.read_typetree(), target_obj.read_typetree())
                value_cache[cache_key] = trees
            source_tree, target_tree = trees
            field_path = str(locator.get("field_path") or "")
            if method == "unity_localization_string":
                from vntext.unity_localization import get_unity_localization_field

                source_value = get_unity_localization_field(source_tree, field_path)
                actual = get_unity_localization_field(target_tree, field_path)
            else:
                source_value = _get_typetree_value(source_tree, field_path)
                actual = _get_typetree_value(target_tree, field_path)
            if source_value != source_text:
                return _result(entry, ordinal, locator, FAIL, "Unity TypeTree source precondition drift", write_status=FAIL)
            if actual != translation:
                return _result(entry, ordinal, locator, FAIL, "Unity TypeTree read-back mismatch", write_status=FAIL, actual=str(actual or ""))
            return _result(entry, ordinal, locator, PASS, "Unity serialized field read-back", actual=str(actual))

        if method in {"naninovel_script_string", "naninovel_choice", "naninovel_print"}:
            from vntext.extract_naninovel import (
                _object_raw_bytes,
                _scan_script_object_strings,
                iter_naninovel_display_texts,
            )
            from vntext.extract_unity import (
                find_aligned_unity_strings,
                find_aligned_unity_strings_containing,
            )
            from vntext.patch_naninovel import _replace_text_in_naninovel_command

            cache_key = ("naninovel", path_id)
            strings = value_cache.get(cache_key)
            if strings is None:
                source_raw = _object_raw_bytes(source_obj)
                target_raw = _object_raw_bytes(target_obj)
                source_strings = [
                    str(item.get("text") or "")
                    for item in _scan_script_object_strings(source_raw)
                ]
                target_strings = [
                    str(item.get("text") or "")
                    for item in _scan_script_object_strings(target_raw)
                ]
                strings = {
                    "source_raw": source_raw,
                    "target_raw": target_raw,
                    "source": source_strings,
                    "target": target_strings,
                    "source_exact": set(source_strings),
                    "target_exact": set(target_strings),
                    "source_displays": {
                        display.strip()
                        for value in source_strings
                        for display in iter_naninovel_display_texts(value)
                        if display.strip()
                    },
                    "target_displays": {
                        display.strip()
                        for value in target_strings
                        for display in iter_naninovel_display_texts(value)
                        if display.strip()
                    },
                }
                value_cache[cache_key] = strings
            source_strings = strings["source"]
            target_strings = strings["target"]
            source_exact = strings["source_exact"]
            target_exact = strings["target_exact"]
            source_displays = strings["source_displays"]
            target_displays = strings["target_displays"]
            raw_matches = strings.setdefault("raw_matches", {})

            def has_raw_text(side: str, text: str) -> bool:
                cache_key = (side, text)
                if cache_key in raw_matches:
                    return bool(raw_matches[cache_key])
                raw = strings[side + "_raw"]
                hit = bool(find_aligned_unity_strings(raw, text))
                if not hit:
                    hit = bool(find_aligned_unity_strings_containing(raw, text))
                raw_matches[cache_key] = hit
                return hit

            source_present = (
                source_text in source_exact
                or source_text in source_displays
                or has_raw_text("source", source_text)
            )
            target_present = (
                translation in target_exact
                or translation in target_displays
                or has_raw_text("target", translation)
            )
            if not source_present and not any(source_text in value for value in source_strings):
                return _result(entry, ordinal, locator, FAIL, "Naninovel source precondition drift", write_status=FAIL)
            if target_present or any(translation in value for value in target_strings):
                return _result(entry, ordinal, locator, PASS, "Naninovel serialized string read-back", actual=translation)
            expected_commands = {
                _replace_text_in_naninovel_command(value, source_text, translation)
                for value in source_strings
                if source_text in value
            }
            if any(value in expected_commands for value in target_strings):
                return _result(entry, ordinal, locator, PASS, "Naninovel command read-back", actual=translation)
            return _result(entry, ordinal, locator, FAIL, "Naninovel read-back value mismatch", write_status=FAIL)
    except Exception as exc:
        return _result(entry, ordinal, locator, FAIL, f"Unity read-back failed: {exc}", write_status=FAIL)
    finally:
        source_obj = None
        target_obj = None
        source_env = None
        target_env = None
    return _result(entry, ordinal, locator, NOT_TESTABLE, f"method {method} has no safe reader")


def _verify_patch_targets_impl(
    patched_root: Path,
    game_root: Path,
    grouped_items: dict[str, list[tuple[dict[str, Any], str]]],
) -> dict[str, Any]:
    """Reopen each patched target and return a per-target report.

    This function is intentionally a top-level process entry target.  UnityPy
    can spend an unbounded amount of time parsing a malformed/very large
    bundle; the public wrapper below runs this function in a disposable child
    when the production patch route supplies a deadline.
    """

    results: list[dict[str, Any]] = []
    for rel, items in grouped_items.items():
        source, resolved_rel = resolve_game_source_file(game_root, rel)
        target = patched_root / resolved_rel
        shared_source_env = None
        shared_target_env = None
        shared_maps: tuple[dict[str, Any], dict[str, Any]] | None = None
        value_cache: dict[tuple[str, str], Any] = {}
        unity_open_error = ""
        needs_unity_reopen = (
            source.is_file()
            and target.is_file()
            and any(
                str(entry.get("import_method") or "") in _UNITY_REOPEN_METHODS
                for entry, _translation in items
            )
        )
        if needs_unity_reopen:
            try:
                import UnityPy

                shared_source_env = UnityPy.load(str(source))
                shared_target_env = UnityPy.load(str(target))
                shared_maps = (
                    _unity_object_map(shared_source_env),
                    _unity_object_map(shared_target_env),
                )
            except Exception as exc:
                unity_open_error = f"Unity reopen unavailable: {exc}"
                shared_source_env = None
                shared_target_env = None
                shared_maps = None

        try:
            for entry, translation in items:
                entry_dict = dict(entry)
                method = str(entry_dict.get("import_method") or "")
                for ordinal, locator in enumerate(_locations(entry_dict)):
                    if method in _UNSUPPORTED_METHODS:
                        results.append(_result(entry_dict, ordinal, locator, NOT_TESTABLE, f"method {method} has no safe reopen route"))
                        continue
                    if not source.is_file() or not target.is_file():
                        results.append(_result(entry_dict, ordinal, locator, FAIL, "source or patched target missing", write_status=FAIL))
                        continue
                    if method == "plain_text_line":
                        results.append(_verify_plain(source, target, entry_dict, ordinal, locator, str(translation)))
                    elif method == "structured_json_value":
                        results.append(_verify_json(source, target, entry_dict, ordinal, locator, str(translation)))
                    elif method == "structured_csv_cell":
                        results.append(_verify_csv(source, target, entry_dict, ordinal, locator, str(translation)))
                    elif method == "structured_xml_value":
                        results.append(_verify_xml(source, target, entry_dict, ordinal, locator, str(translation)))
                    elif method == "structured_sqlite_value":
                        results.append(_verify_sqlite(source, target, entry_dict, ordinal, locator, str(translation)))
                    elif method in _UNITY_REOPEN_METHODS:
                        if unity_open_error:
                            results.append(_result(entry_dict, ordinal, locator, NOT_TESTABLE, unity_open_error))
                        else:
                            results.append(
                                _verify_unity(
                                    source,
                                    target,
                                    entry_dict,
                                    ordinal,
                                    locator,
                                    str(translation),
                                    environments=(shared_source_env, shared_target_env),
                                    object_maps=shared_maps,
                                    value_cache=value_cache,
                                )
                            )
                    else:
                        results.append(_result(entry_dict, ordinal, locator, NOT_TESTABLE, f"method {method} has no safe reader"))
        finally:
            if shared_maps is not None:
                shared_maps[0].clear()
                shared_maps[1].clear()
            shared_maps = None
            shared_source_env = None
            shared_target_env = None
            value_cache.clear()
            import gc

            gc.collect()
    counts: dict[str, int] = {}
    for item in results:
        counts[item["status"]] = counts.get(item["status"], 0) + 1
    return {"schema_version": 1, "counts": counts, "results": results}


def _readback_process_entry(
    queue: Any,
    runner: Any,
    grouped_items: dict,
    patched_root: str,
    game_root: str,
) -> None:
    """Process entrypoint kept free of closures for Windows ``spawn``."""

    try:
        queue.put(
            (
                "ok",
                runner(Path(patched_root), Path(game_root), grouped_items),
            )
        )
    except BaseException as exc:  # pragma: no cover - exercised via parent error path
        queue.put(("error", f"{type(exc).__name__}: {exc}\n{traceback.format_exc()}"))


def _timeout_report(
    grouped_items: dict[str, list[tuple[dict[str, Any], str]]],
    *,
    status: str,
    reason: str,
) -> dict[str, Any]:
    """Build machine-readable evidence when the verifier cannot finish."""

    results: list[dict[str, Any]] = []
    for items in grouped_items.values():
        for entry, _translation in items:
            entry_dict = dict(entry)
            method = str(entry_dict.get("import_method") or "")
            for ordinal, locator in enumerate(_locations(entry_dict)):
                if method in _UNSUPPORTED_METHODS:
                    results.append(
                        _result(
                            entry_dict,
                            ordinal,
                            locator,
                            NOT_TESTABLE,
                            f"method {method} has no safe reopen route; verifier {status.lower()}",
                        )
                    )
                else:
                    results.append(
                        _result(
                            entry_dict,
                            ordinal,
                            locator,
                            status,
                            reason,
                            write_status=status,
                        )
                    )
    counts: dict[str, int] = {}
    for item in results:
        counts[item["status"]] = counts.get(item["status"], 0) + 1
    return {
        "schema_version": 1,
        "status": status,
        "reason": reason,
        "counts": counts,
        "results": results,
    }


def _run_readback_process(
    patched_root: Path,
    game_root: Path,
    grouped_items: dict[str, list[tuple[dict[str, Any], str]]],
    timeout_seconds: float,
    runner: Any,
) -> dict[str, Any]:
    """Run Unity read-back in a killable child and always reap it."""

    context = multiprocessing.get_context("spawn")
    queue = context.Queue(maxsize=1)
    process = context.Process(
        target=_readback_process_entry,
        args=(queue, runner, grouped_items, str(patched_root), str(game_root)),
        name="vntext-patch-readback",
    )
    process.daemon = True
    try:
        process.start()
        process.join(timeout=max(1.0, float(timeout_seconds)))
        if process.is_alive():
            process.terminate()
            process.join(timeout=5.0)
            if process.is_alive():  # pragma: no cover - defensive Windows cleanup
                process.kill()
                process.join(timeout=5.0)
            return _timeout_report(
                grouped_items,
                status=TIMEOUT,
                reason=f"patch read-back timed out after {float(timeout_seconds):.3f}s; verifier process terminated",
            )
        if not queue.empty():
            kind, payload = queue.get_nowait()
            if kind == "ok" and isinstance(payload, dict):
                return payload
            return _timeout_report(
                grouped_items,
                status=FAIL,
                reason=f"patch read-back verifier failed: {payload}",
            )
        return _timeout_report(
            grouped_items,
            status=FAIL,
            reason=f"patch read-back verifier exited without a report (exit={process.exitcode})",
        )
    except Exception as exc:
        return _timeout_report(
            grouped_items,
            status=FAIL,
            reason=f"patch read-back process setup failed: {type(exc).__name__}: {exc}",
        )
    finally:
        if process.is_alive():
            process.terminate()
        process.join(timeout=5.0)
        queue.close()
        queue.join_thread()


def _run_readback_subprocess(
    patched_root: Path,
    game_root: Path,
    grouped_items: dict[str, list[tuple[dict[str, Any], str]]],
    timeout_seconds: float,
) -> dict[str, Any]:
    """Run the verifier through a standalone Python process.

    The worker dispatches patch tasks from a background thread.  Windows
    ``multiprocessing.spawn`` can inherit that thread's import lock, so the
    production path uses a plain subprocess with explicit stdin/stdout and a
    kill/reap sequence instead.
    """

    payload = json.dumps(
        {
            "patched_root": str(patched_root),
            "game_root": str(game_root),
            "grouped_items": grouped_items,
        },
        # Keep stdin ASCII-only: Release's embedded Python may still expose
        # the console stream with a legacy code page even though text files
        # are UTF-8.  Escaped JSON preserves the exact Unicode value.
        ensure_ascii=True,
    )
    launch = _readback_subprocess_launch()
    process: subprocess.Popen[str] | None = None
    try:
        process = subprocess.Popen(
            [launch["executable"], "-m", "vntext.patch_readback", "--worker"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            cwd=str(Path.cwd()),
            creationflags=launch["creationflags"],
        )
        stdout, stderr = process.communicate(
            payload,
            timeout=max(1.0, float(timeout_seconds)),
        )
        if process.returncode == 0:
            try:
                report = json.loads(stdout)
            except (TypeError, ValueError, json.JSONDecodeError) as exc:
                return _timeout_report(
                    grouped_items,
                    status=FAIL,
                    reason=f"patch read-back subprocess emitted malformed report: {exc}",
                )
            if isinstance(report, dict):
                return report
        detail = (stderr or stdout or "no diagnostic").strip()[-2000:]
        return _timeout_report(
            grouped_items,
            status=FAIL,
            reason=f"patch read-back subprocess failed (exit={process.returncode}): {detail}",
        )
    except subprocess.TimeoutExpired:
        if process is not None:
            process.terminate()
            try:
                process.communicate(timeout=5.0)
            except subprocess.TimeoutExpired:
                process.kill()
                process.communicate(timeout=5.0)
        return _timeout_report(
            grouped_items,
            status=TIMEOUT,
            reason=f"patch read-back timed out after {float(timeout_seconds):.3f}s; verifier subprocess terminated",
        )
    except OSError as exc:
        return _timeout_report(
            grouped_items,
            status=FAIL,
            reason=f"patch read-back subprocess setup failed: {type(exc).__name__}: {exc}",
        )
    finally:
        if process is not None and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5.0)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5.0)


def _readback_subprocess_launch() -> dict[str, Any]:
    """Return a console-isolated interpreter/creation policy for read-back.

    The verifier is a long-running child that can parse large Unity assets.  A
    console-attached ``python.exe`` may receive a CTRL+C/window-close event
    independently of the parent task, producing Windows ``0xC000013A`` and
    losing the diagnostic report.  Keep the child killable and fail-closed,
    but detach it from console control events on Windows.
    """

    executable = sys.executable
    creationflags = 0
    if os.name == "nt":
        pythonw = Path(sys.executable).with_name("pythonw.exe")
        if pythonw.is_file():
            executable = str(pythonw)
        creationflags = int(getattr(subprocess, "CREATE_NO_WINDOW", 0)) | int(
            getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        )
    return {"executable": executable, "creationflags": creationflags}


def verify_patch_targets(
    patched_root: Path,
    game_root: Path,
    grouped_items: dict[str, list[tuple[dict[str, Any], str]]],
    *,
    timeout_seconds: float | None = None,
    _runner: Any | None = None,
) -> dict[str, Any]:
    """Reopen every target, optionally inside a bounded disposable process.

    ``None`` preserves the direct/in-process API used by tiny unit fixtures.
    The production patch path passes an explicit finite timeout so a blocked
    Unity/Naninovel reader can never promote partial output to success.
    """

    if timeout_seconds is None:
        return _verify_patch_targets_impl(patched_root, game_root, grouped_items)
    if _runner is None:
        return _run_readback_subprocess(
            Path(patched_root),
            Path(game_root),
            grouped_items,
            max(1.0, float(timeout_seconds)),
        )
    return _run_readback_process(
        Path(patched_root),
        Path(game_root),
        grouped_items,
        max(1.0, float(timeout_seconds)),
        _runner or _verify_patch_targets_impl,
    )


def _worker_main() -> int:
    payload = json.load(sys.stdin)
    report = _verify_patch_targets_impl(
        Path(str(payload["patched_root"])),
        Path(str(payload["game_root"])),
        payload["grouped_items"],
    )
    # Match the ASCII-only request payload so the portable interpreter's
    # console encoding cannot corrupt Vietnamese diagnostics on the pipe.
    sys.stdout.write(json.dumps(report, ensure_ascii=True))
    sys.stdout.flush()
    return 0


def write_patch_verification_report(patch_out: Path, report: dict[str, Any]) -> Path:
    path = patch_out / "patch_verification.json"
    temp = path.with_name(f".{path.name}.tmp")
    temp.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temp.replace(path)
    return path


__all__ = [
    "DEFAULT_READBACK_TIMEOUT_SECONDS",
    "FAIL",
    "NOT_TESTABLE",
    "PASS",
    "TIMEOUT",
    "readback_timeout_seconds",
    "verify_patch_targets",
    "write_patch_verification_report",
]


if __name__ == "__main__":  # pragma: no cover - exercised by patch subprocess
    if len(sys.argv) == 2 and sys.argv[1] == "--worker":
        raise SystemExit(_worker_main())
