"""Safe field-level CSV extraction and patching."""

from __future__ import annotations

import codecs
import csv
import io
from pathlib import Path
from typing import Any, Iterable

from vntext.entry import Entry
from vntext.extract_constants import LANGUAGE_COLUMN_NAMES, TEXT_FIELD_WORDS
from vntext.extract_text import textasset_line_quality
from vntext.patchability import STRUCTURED_CSV_PATCH_PROOF


_TEXT_COLUMN_NAMES = LANGUAGE_COLUMN_NAMES | TEXT_FIELD_WORDS | {
    "value", "body", "sentence", "dialog", "dialogue", "textvalue"
}
_TECHNICAL_COLUMN_NAMES = {"name", "key", "id", "guid", "path", "address", "file"}


def _read_csv(path: Path) -> tuple[list[list[str]], bool, str, csv.Dialect]:
    raw = path.read_bytes()
    has_bom = raw.startswith(codecs.BOM_UTF8)
    text = raw.decode("utf-8-sig")
    sample = text[: 128 * 1024]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
    except csv.Error:
        dialect = csv.excel
    try:
        rows = list(csv.reader(io.StringIO(text, newline=""), dialect))
    except csv.Error:
        raise
    newline = "\r\n" if "\r\n" in text else "\n"
    return rows, has_bom, newline, dialect


def _header_indices(header: list[str]) -> list[int]:
    indices: list[int] = []
    for index, cell in enumerate(header):
        name = str(cell or "").strip().casefold().replace("-", "_")
        if name in _TECHNICAL_COLUMN_NAMES:
            continue
        if name in {item.casefold().replace("-", "_") for item in _TEXT_COLUMN_NAMES}:
            indices.append(index)
    return indices


def has_text_header(text: str) -> bool:
    """Return whether a bounded CSV sample has an explicit text-like header."""

    sample = str(text or "")[: 128 * 1024]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
        rows = list(csv.reader(io.StringIO(sample, newline=""), dialect))
    except (csv.Error, UnicodeError):
        return False
    return len(rows) >= 2 and bool(_header_indices(rows[0]))


def extract_structured_csv(path: Path, root: Path) -> Iterable[Entry]:
    """Yield eligible cells from a CSV with an explicit text-like header."""

    try:
        rows, _has_bom, _newline, _dialect = _read_csv(path)
    except (OSError, UnicodeDecodeError, csv.Error):
        return
    if len(rows) < 2:
        return
    columns = _header_indices(rows[0])
    if not columns:
        return
    rel = path.relative_to(root).as_posix()
    for row_index, row in enumerate(rows[1:], start=1):
        for column_index in columns:
            if column_index >= len(row):
                continue
            value = row[column_index]
            if not value or value != value.strip() or not textasset_line_quality(value):
                continue
            header = str(rows[0][column_index] or "").strip()
            yield Entry(
                source_text=value,
                file_path=rel,
                context=f"csv:row={row_index},column={column_index}",
                object_info=f"CSV row {row_index}, column {column_index} ({header})",
                import_method="structured_csv_cell",
                safety="safe",
                locator={
                    "row_index": row_index,
                    "column_index": column_index,
                    "header": header,
                },
                backend="structured_csv",
                patch_proof=dict(STRUCTURED_CSV_PATCH_PROOF),
            ).finalize()


def patch_structured_csv(
    source: Path,
    target: Path,
    items: Iterable[tuple[dict, str]],
) -> tuple[int, int]:
    """Patch CSV cells, checking row/column and original value preconditions."""

    rows, has_bom, original_newline, dialect = _read_csv(source)
    changed = 0
    skipped = 0
    for entry, translation in items:
        locator = entry.get("locator") or {}
        try:
            row_index = int(locator.get("row_index"))
            column_index = int(locator.get("column_index"))
        except (TypeError, ValueError):
            skipped += 1
            continue
        source_text = str(entry.get("source_text") or "")
        if not (0 <= row_index < len(rows)) or not (0 <= column_index < len(rows[row_index])):
            skipped += 1
            continue
        if rows[row_index][column_index] != source_text:
            skipped += 1
            continue
        rows[row_index][column_index] = str(translation)
        changed += 1

    output = io.StringIO(newline="")
    writer = csv.writer(output, dialect=dialect, lineterminator=original_newline)
    writer.writerows(rows)
    rendered = output.getvalue()
    if not source.read_text(encoding="utf-8-sig").endswith(("\n", "\r")):
        rendered = rendered.rstrip("\r\n")
    payload = (codecs.BOM_UTF8 if has_bom else b"") + rendered.encode("utf-8")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(payload)
    return changed, skipped


__all__ = ["extract_structured_csv", "has_text_header", "patch_structured_csv"]
