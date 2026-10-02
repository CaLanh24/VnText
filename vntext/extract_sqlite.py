"""Bounded SQLite discovery and a strict structured writer subset.

SQLite databases are common in Unity games, but a schema alone does not prove
which string columns are player-visible or that a writer can preserve the
game's invariants.  The generic route therefore promotes only ordinary rowid
tables with one ``INTEGER PRIMARY KEY`` and clearly text-like columns.  All
other strings remain explicit review entries.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import sqlite3
import tempfile
from pathlib import Path
from typing import Iterable

from vntext.entry import Entry
from vntext.extract_constants import LANGUAGE_COLUMN_NAMES, TECH_FIELD_WORDS, TEXT_FIELD_WORDS
from vntext.extract_text import textasset_line_quality
from vntext.patchability import STRUCTURED_SQLITE_PATCH_PROOF


MAX_SQLITE_TABLES = 256
MAX_SQLITE_ROWS_PER_TABLE = 2000
MAX_SQLITE_TEXT_CHARS = 16384
MAX_SQLITE_ENTRIES = 10000
SQLITE_PATCH_METHOD = "structured_sqlite_value"


def _quote_identifier(value: str) -> str:
    """Quote an SQLite identifier without interpolating executable SQL."""

    return '"' + str(value).replace('"', '""') + '"'


def _sqlite_uri(path: Path) -> str:
    return f"{path.resolve().as_uri()}?mode=ro"


def _text_value(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text or len(text) > MAX_SQLITE_TEXT_CHARS or "\x00" in text:
        return None
    if not any(char.isalpha() for char in text):
        return None
    return text


def _normalise_column_name(value: str) -> tuple[str, set[str]]:
    normalised = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", str(value or ""))
    normalised = re.sub(r"[^A-Za-z0-9]+", "_", normalised).strip("_").casefold()
    return normalised, {part for part in normalised.split("_") if part}


def _is_safe_text_column(column_name: str, declared_type: str) -> bool:
    """Return whether a column name/type is strong enough for MAIN flow."""

    declared = str(declared_type or "").casefold()
    if not any(token in declared for token in ("char", "clob", "text")):
        return False
    normalised, parts = _normalise_column_name(column_name)
    compact = normalised.replace("_", "")
    if compact in TECH_FIELD_WORDS or parts.intersection(TECH_FIELD_WORDS):
        return False
    text_words = {str(item).casefold().replace("-", "_") for item in TEXT_FIELD_WORDS}
    language_words = {str(item).casefold().replace("-", "_") for item in LANGUAGE_COLUMN_NAMES}
    return compact in text_words or bool(parts.intersection(text_words | language_words))


def _table_schema(connection: sqlite3.Connection, table_name: str) -> dict | None:
    """Return a stable safe-table description, or ``None`` for risky schemas."""

    row = connection.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table_name,),
    ).fetchone()
    table_sql = str(row[0] or "") if row else ""
    if not table_sql or "WITHOUT ROWID" in table_sql.upper() or "VIRTUAL TABLE" in table_sql.upper():
        return None
    columns = connection.execute(
        f"PRAGMA table_info({_quote_identifier(table_name)})"
    ).fetchall()
    if not columns:
        return None
    primary_keys = [column for column in columns if int(column[5] or 0) == 1]
    if len(primary_keys) != 1 or str(primary_keys[0][2] or "").strip().upper() != "INTEGER":
        return None
    if any(int(column[5] or 0) > 1 for column in columns):
        return None
    serial = {
        "table_sql": table_sql,
        "columns": [
            [
                int(column[0]),
                str(column[1]),
                str(column[2] or ""),
                int(column[3] or 0),
                column[4],
                int(column[5] or 0),
            ]
            for column in columns
        ],
    }
    fingerprint = hashlib.sha256(
        json.dumps(serial, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return {
        "table": table_name,
        "columns": columns,
        "primary_key_column": str(primary_keys[0][1]),
        "schema_fingerprint": fingerprint,
        "safe_columns": {
            str(column[1]): str(column[2] or "")
            for column in columns
            if _is_safe_text_column(str(column[1]), str(column[2] or ""))
        },
    }


def _table_has_rowid(connection: sqlite3.Connection, table_name: str) -> bool:
    row = connection.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table_name,),
    ).fetchone()
    sql = str(row[0] or "") if row else ""
    upper = sql.upper()
    return bool(sql) and "WITHOUT ROWID" not in upper and "VIRTUAL TABLE" not in upper


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _has_sqlite_sidecars(path: Path) -> bool:
    return any(
        candidate.exists()
        for candidate in (
            path.with_name(path.name + "-wal"),
            path.with_name(path.name + "-shm"),
        )
    )


def extract_sqlite_text_candidates(path: Path, root: Path) -> Iterable[Entry]:
    """Enumerate bounded SQLite candidates, promoting only proven safe rows."""

    rel = str(path.relative_to(root)) if path.is_relative_to(root) else str(path)
    connection = sqlite3.connect(_sqlite_uri(path), uri=True, timeout=1.0)
    try:
        connection.execute("PRAGMA query_only = ON")
        file_sha256 = _file_sha256(path)
        safe_route_allowed = not _has_sqlite_sidecars(path)
        tables = connection.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type = 'table' AND name NOT LIKE 'sqlite_%' "
            "ORDER BY name LIMIT ?",
            (MAX_SQLITE_TABLES,),
        ).fetchall()
        emitted = 0
        for (table_name_raw,) in tables:
            if emitted >= MAX_SQLITE_ENTRIES:
                break
            table_name = str(table_name_raw)
            columns = connection.execute(
                f"PRAGMA table_info({_quote_identifier(table_name)})"
            ).fetchall()
            if not columns:
                continue
            schema = _table_schema(connection, table_name) if safe_route_allowed else None
            rowid_available = _table_has_rowid(connection, table_name)
            column_names = [str(row[1]) for row in columns]
            quoted_columns = ", ".join(_quote_identifier(name) for name in column_names)
            rowid_prefix = "rowid, " if rowid_available else ""
            cursor = connection.execute(
                f"SELECT {rowid_prefix}{quoted_columns} FROM {_quote_identifier(table_name)} LIMIT ?",
                (MAX_SQLITE_ROWS_PER_TABLE,),
            )
            for row_index, row in enumerate(cursor, start=1):
                rowid = row[0] if rowid_available else None
                for column_index, value in enumerate(row[1:] if rowid_available else row):
                    text = _text_value(value)
                    if text is None:
                        continue
                    column = columns[column_index]
                    column_name = column_names[column_index]
                    locator = {
                        "table": table_name,
                        "column": column_name,
                        "row_index": row_index,
                        "declared_type": str(column[2] or ""),
                    }
                    is_main_candidate = bool(
                        schema
                        and column_name in schema["safe_columns"]
                        and isinstance(value, str)
                        and value == text
                        and textasset_line_quality(text)
                    )
                    if is_main_candidate:
                        locator.update(
                            {
                                "rowid": int(rowid),
                                "primary_key_column": schema["primary_key_column"],
                                "primary_key_value": int(rowid),
                                "schema_fingerprint": schema["schema_fingerprint"],
                                "file_sha256": file_sha256,
                            }
                        )
                    else:
                        if rowid_available:
                            locator["rowid"] = int(rowid) if isinstance(rowid, int) else rowid
                    yield Entry(
                        source_text=text,
                        file_path=rel,
                        context=(
                            f"sqlite:{table_name}:row={row_index}:"
                            f"column={column_name}"
                        ),
                        object_info=(
                            f"sqlite_table={table_name};"
                            f"sqlite_column={column_name}"
                        ),
                        import_method=SQLITE_PATCH_METHOD if is_main_candidate else "sqlite_text_candidate",
                        safety="safe" if is_main_candidate else "review_only",
                        locator=locator,
                        backend="structured_sqlite" if is_main_candidate else "sqlite_inventory",
                        review_only=not is_main_candidate,
                        patch_proof=dict(STRUCTURED_SQLITE_PATCH_PROOF) if is_main_candidate else {},
                    ).finalize()
                    emitted += 1
                    if emitted >= MAX_SQLITE_ENTRIES:
                        break
                if emitted >= MAX_SQLITE_ENTRIES:
                    break
    finally:
        connection.close()


def patch_structured_sqlite(
    source: Path,
    target: Path,
    items: Iterable[tuple[dict, str]],
) -> tuple[int, int]:
    """Patch safe SQLite rows using a copied DB, transaction, and reopen proof.

    The source is never opened in write mode.  Every row must carry the file
    digest, safe-table schema fingerprint, rowid and exact source value.  A
    locator or schema mismatch is skipped without mutating the output.
    """

    materialised = list(items)
    target.parent.mkdir(parents=True, exist_ok=True)
    source_sha256 = _file_sha256(source)
    if _has_sqlite_sidecars(source):
        shutil.copy2(source, target)
        return 0, len(materialised)
    temp_fd, temp_name = tempfile.mkstemp(prefix=f".{target.name}.vntext-", suffix=".tmp", dir=target.parent)
    os.close(temp_fd)
    temp_path = Path(temp_name)
    temp_path.unlink()
    changed = 0
    skipped = 0
    try:
        shutil.copy2(source, temp_path)
        connection = sqlite3.connect(temp_path, timeout=1.0)
        try:
            schema_cache: dict[str, dict | None] = {}
            updates: list[tuple[dict, str, str, int, str]] = []
            for entry, translation in materialised:
                locator = entry.get("locator") or {}
                table = str(locator.get("table") or "")
                column = str(locator.get("column") or "")
                if (
                    locator.get("file_sha256") != source_sha256
                    or not table
                    or not column
                    or locator.get("rowid") is None
                ):
                    skipped += 1
                    continue
                try:
                    rowid = int(locator.get("rowid"))
                except (TypeError, ValueError):
                    skipped += 1
                    continue
                if table not in schema_cache:
                    schema_cache[table] = _table_schema(connection, table)
                schema = schema_cache[table]
                if (
                    schema is None
                    or locator.get("schema_fingerprint") != schema["schema_fingerprint"]
                    or column not in schema["safe_columns"]
                    or str(locator.get("primary_key_column") or "") != schema["primary_key_column"]
                ):
                    skipped += 1
                    continue
                current = connection.execute(
                    f"SELECT rowid, {_quote_identifier(schema['primary_key_column'])}, {_quote_identifier(column)} "
                    f"FROM {_quote_identifier(table)} WHERE rowid = ?",
                    (rowid,),
                ).fetchone()
                source_text = str(entry.get("source_text") or "")
                if (
                    current is None
                    or int(current[0]) != rowid
                    or int(current[1]) != int(locator.get("primary_key_value"))
                    or current[2] != source_text
                ):
                    skipped += 1
                    continue
                updates.append((locator, str(translation), table, rowid, source_text))

            if updates:
                connection.execute("BEGIN IMMEDIATE")
                for locator, translation, table, rowid, source_text in updates:
                    column = str(locator["column"])
                    cursor = connection.execute(
                        f"UPDATE {_quote_identifier(table)} SET {_quote_identifier(column)} = ? "
                        f"WHERE rowid = ? AND {_quote_identifier(column)} = ?",
                        (translation, rowid, source_text),
                    )
                    if cursor.rowcount != 1:
                        connection.rollback()
                        skipped += len(updates)
                        updates = []
                        break
                if updates:
                    connection.commit()
                    changed = len(updates)
        finally:
            connection.close()

        if changed:
            verify = sqlite3.connect(_sqlite_uri(temp_path), uri=True, timeout=1.0)
            try:
                for locator, translation, _table, rowid, _source_text in updates:
                    current = verify.execute(
                        f"SELECT {_quote_identifier(locator['column'])} FROM {_quote_identifier(locator['table'])} WHERE rowid = ?",
                        (rowid,),
                    ).fetchone()
                    if current is None or current[0] != translation:
                        return 0, len(materialised)
            finally:
                verify.close()
        else:
            skipped = max(skipped, len(materialised))
        temp_path.replace(target)
        return changed, skipped
    finally:
        try:
            temp_path.unlink(missing_ok=True)
        except OSError:
            pass


__all__ = [
    "MAX_SQLITE_ENTRIES",
    "MAX_SQLITE_ROWS_PER_TABLE",
    "MAX_SQLITE_TABLES",
    "MAX_SQLITE_TEXT_CHARS",
    "SQLITE_PATCH_METHOD",
    "extract_sqlite_text_candidates",
    "patch_structured_sqlite",
]
