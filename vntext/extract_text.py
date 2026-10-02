"""Text extraction family.

Function bodies are mechanically preserved from the former monolithic vntext.extract module.
"""

from __future__ import annotations

from vntext.extract_constants import (
    Entry,
    GUID_RE,
    HEX_RE,
    LANGUAGE_COLUMN_NAMES,
    MAX_TEXT_LINE_CHARS,
    NANINOVEL_SKIP_WORDS,
    PATH_RE,
    PREFERRED_SOURCE_LANGUAGE_COLUMNS,
    TECH_FIELD_WORDS,
    TEXT_FIELD_WORDS,
    UI_SHORT_TEXT,
    re,
    struct,
)



def decode_length_prefixed_at(data, offset: int, size: int, min_len: int = 2, max_len: int = 12000):
    from vntext.extract_naninovel import decode_candidate
    if offset + 4 > size:
        return None
    try:
        length = struct.unpack_from("<I", data, offset)[0]
    except Exception:
        return None
    if length < min_len or length > max_len:
        return None
    start = offset + 4
    end = start + length
    if end > size:
        return None
    raw = data[start:end]
    text = decode_candidate(raw, "utf-8", strict=True)
    if not text:
        text = decode_candidate(raw, "utf-16le", strict=True)
        encoding = "utf-16le"
    else:
        encoding = "utf-8"
    if not text:
        return None
    padded_end = start + ((length + 3) & ~3)
    return text, start, length, padded_end, encoding


def decode_7bit_int_at(data, offset: int, size: int):
    """Doc length kieu .NET BinaryReader 7-bit encoded int."""
    result = 0
    shift = 0
    pos = offset
    for _ in range(5):
        if pos >= size:
            return None
        b = data[pos]
        result |= (b & 0x7F) << shift
        pos += 1
        if not (b & 0x80):
            return result, pos
        shift += 7
    return None


def decode_7bit_length_prefixed_at(data, offset: int, size: int, min_len: int = 2, max_len: int = 12000):
    from vntext.extract_naninovel import decode_candidate
    decoded = decode_7bit_int_at(data, offset, size)
    if not decoded:
        return None
    length, start = decoded
    if length < min_len or length > max_len:
        return None
    end = start + length
    if end > size:
        return None
    raw = data[start:end]
    text = decode_candidate(raw, "utf-8", strict=True)
    encoding = "utf-8"
    if not text:
        return None
    return text, start, length, end, encoding


def decode_msgpack_string_at(data, offset: int, size: int, min_len: int = 2, max_len: int = 12000):
    """Doc string prefix kieu MessagePack: fixstr/str8/str16/str32."""
    from vntext.extract_naninovel import decode_candidate
    if offset >= size:
        return None
    b0 = data[offset]
    if 0xA0 <= b0 <= 0xBF:
        length = b0 & 0x1F
        start = offset + 1
    elif b0 == 0xD9 and offset + 2 <= size:
        length = data[offset + 1]
        start = offset + 2
    elif b0 == 0xDA and offset + 3 <= size:
        length = struct.unpack_from(">H", data, offset + 1)[0]
        start = offset + 3
    elif b0 == 0xDB and offset + 5 <= size:
        length = struct.unpack_from(">I", data, offset + 1)[0]
        start = offset + 5
    else:
        return None
    if length < min_len or length > max_len:
        return None
    end = start + length
    if end > size:
        return None
    raw = data[start:end]
    text = decode_candidate(raw, "utf-8", strict=True)
    if not text:
        return None
    return text, start, length, end, "utf-8"


def stable_packed_naninovel_text(text: str) -> bool:
    from vntext.extract_naninovel import text_noise_score
    from vntext.extract_quality import _clean_inline_text, has_binary_garbage, has_vietnamese_chars, looks_like_code_or_asset_token, looks_like_demo_or_placeholder, strict_complete_dialogue_text
    cleaned = _clean_inline_text(text)
    if not cleaned:
        return False
    if looks_like_demo_or_placeholder(cleaned) or has_binary_garbage(cleaned) or looks_like_code_or_asset_token(cleaned):
        return False
    if has_vietnamese_chars(cleaned):
        return True
    if text_noise_score(cleaned) >= 28:
        return False
    # v1.18: 7-bit/MessagePack false-positive rat nhieu; chi giu string tron cau/UI.
    return strict_complete_dialogue_text(cleaned)


def is_ui_text_field(field_path: str) -> bool:
    lowered = str(field_path or "").lower()
    last = lowered.split(".")[-1].split("[")[0]
    if last in {"m_text", "text", "defaultvalue", "caption", "label"}:
        return True
    if "m_options" in lowered and last in {"m_text", "text"}:
        return True
    return False


def translatable_field(field_path: str, text: str) -> bool:
    from vntext.extract_quality import looks_like_code_or_asset_token, looks_like_sentence, raw_text_quality
    lowered_path = field_path.lower()
    last = lowered_path.split(".")[-1].split("[")[0]
    lowered_text = text.strip().lower()
    if is_ui_text_field(field_path):
        return bool(text.strip()) and not looks_like_code_or_asset_token(text)

    # m_Name/name/path/id/guid thuong la ten asset/ky thuat, khong phai text hien thi.
    if last in {"m_name", "name", "id", "key", "guid", "path", "address", "assetguid", "m_script"}:
        return False
    if any(tok in lowered_path for tok in ("sampler", "shader", "material", "sprite", "texture2d", "guid", "fileid")):
        return False
    if any(word in lowered_path for word in TECH_FIELD_WORDS):
        # Ngoai le displayName/titleText... neu field ro la text UI.
        if "displayname" not in lowered_path and "display_name" not in lowered_path:
            return False
    if any(word in lowered_path for word in TEXT_FIELD_WORDS):
        return raw_text_quality(text, for_main=True)
    if lowered_text in UI_SHORT_TEXT:
        return True
    return raw_text_quality(text, for_main=True) and looks_like_sentence(text)


def key_value_line_prefix(raw: str, value: str, key: str) -> str:
    """Keep the exact separator before value (usually ': ').

    Finding the unstripped right-hand side used to drop the space after ':' and
    produce `Key:Value`, which Naninovel managed-text documents do not ingest.
    """
    if value and raw.endswith(value):
        return raw[: len(raw) - len(value)]
    found = raw.find(value) if value else -1
    if found >= 0:
        return raw[:found]
    return f"{key}: "


def parse_translatable_line(line: str):
    from vntext.extract_quality import looks_like_markup_or_config, raw_text_quality
    raw = line.rstrip("\r\n")
    newline = line[len(raw):]
    stripped = raw.strip()
    if not stripped:
        return None
    if stripped.startswith(("@", ";", "//")):
        return None
    if looks_like_markup_or_config(stripped):
        return None
    if ":" in stripped:
        left, right = stripped.split(":", 1)
        key = left.strip()
        value = right.strip()
        if key and value and len(key) <= 80 and "  " not in key and raw_text_quality(value, for_main=True):
            prefix = key_value_line_prefix(raw, value, left)
            return {"text": value, "mode": "key_value", "prefix": prefix, "newline": newline}
    if raw_text_quality(stripped, for_main=True):
        indent_len = len(raw) - len(raw.lstrip())
        return {"text": stripped, "mode": "line", "prefix": raw[:indent_len], "newline": newline}
    return None


def iter_text_lines(text: str):
    lines = text.splitlines(keepends=True)
    if not lines and text:
        lines = [text]
    for index, line in enumerate(lines):
        parsed = parse_translatable_line(line)
        if parsed:
            yield index, parsed


def _semicolon_csv_read(line: str) -> list[str]:
    raw = line.rstrip("\r\n")
    try:
        return next(csv.reader([raw], delimiter=";", quotechar='"'))
    except Exception:
        return raw.split(";")


def _semicolon_csv_write(cells: list[str], newline: str = "") -> str:
    buf = io.StringIO()
    writer = csv.writer(buf, delimiter=";", quotechar='"', lineterminator="", quoting=csv.QUOTE_MINIMAL)
    writer.writerow(cells)
    return buf.getvalue() + newline


def _norm_header_cell(text: str) -> str:
    return str(text or "").strip().lstrip("\ufeff").lower()


def detect_semicolon_language_table(lines: list[str]):
    """Return table info if TextAsset script is a UABEA-style localization CSV.

    Typical row from UABEA/TextAsset:
      Key;Description;English;German;Spanish;French;Chinese
      @Inventory;;Inventory;Inventar;Inventario;Inventaire;物品栏
    """
    for header_index, line in enumerate(lines[:8]):
        cells = _semicolon_csv_read(line)
        if len(cells) < 3:
            continue
        norm = [_norm_header_cell(c) for c in cells]
        if "key" not in norm:
            continue
        # Description is common but not mandatory. We need at least one language column.
        source_col = None
        for preferred in PREFERRED_SOURCE_LANGUAGE_COLUMNS:
            if preferred.lower() in norm:
                source_col = norm.index(preferred.lower())
                break
        if source_col is None:
            # fallback: first language-like column after key/description.
            for idx, name in enumerate(norm):
                if idx == norm.index("key"):
                    continue
                if name in LANGUAGE_COLUMN_NAMES:
                    source_col = idx
                    break
        if source_col is None:
            continue
        key_col = norm.index("key")
        return {
            "header_index": header_index,
            "header_cells": cells,
            "key_col": key_col,
            "source_col": source_col,
            "source_col_name": cells[source_col].strip() or f"col{source_col}",
        }
    return None


def iter_textasset_language_table_cells(text: str):
    """Yield translatable cells from semicolon localization tables.

    This is the automatic UABEA-style path: user edits translation.csv, importer
    writes the source language cell back into the TextAsset row. No byte limit.
    """
    lines = text.splitlines(keepends=True)
    if not lines:
        return
    table = detect_semicolon_language_table(lines)
    if not table:
        return
    source_col = table["source_col"]
    key_col = table["key_col"]
    for line_index in range(table["header_index"] + 1, len(lines)):
        line = lines[line_index]
        raw = line.rstrip("\r\n")
        newline = line[len(raw):]
        if not raw.strip() or raw.lstrip().startswith(("//", "#")):
            continue
        cells = _semicolon_csv_read(line)
        if len(cells) <= source_col or len(cells) <= key_col:
            continue
        row_key = cells[key_col].strip()
        value = cells[source_col].strip()
        if not row_key or not value:
            continue
        # UI labels can be short (Buy, Sell, OK), so use lenient TextAsset quality.
        if not textasset_line_quality(value):
            continue
        yield line_index, {
            "text": value,
            "row_key": row_key,
            "column_index": source_col,
            "column_name": table["source_col_name"],
            "header_line_index": table["header_index"],
            "newline": newline,
        }


def textasset_line_quality(text: str) -> bool:
    """Lenient filter for real Unity TextAsset lines.

    TextAsset lines are patchable by path_id/line_index, so keep more display text
    than raw scanners. Reject only obvious config/code/asset tokens/binary garbage.
    """
    from vntext.extract_naninovel import plausible_text
    from vntext.extract_quality import has_binary_garbage, looks_like_code_or_asset_token, looks_like_demo_or_placeholder, looks_like_markup_or_config
    cleaned = text.strip()
    if not cleaned:
        return False
    if len(cleaned) > MAX_TEXT_LINE_CHARS:
        return False
    if not plausible_text(cleaned, strict=False):
        return False
    lowered = cleaned.lower()
    if looks_like_markup_or_config(cleaned) or looks_like_demo_or_placeholder(cleaned) or has_binary_garbage(cleaned):
        return False
    if lowered in NANINOVEL_SKIP_WORDS:
        return False
    if "\x00" in cleaned or "�" in cleaned:
        return False
    # Obvious paths / ids / code-only tokens. Lines with spaces and sentence marks are allowed.
    if looks_like_code_or_asset_token(cleaned):
        if not (" " in cleaned and any(mark in cleaned for mark in ".!?,:;…♡♥")):
            return False
    if PATH_RE.search(cleaned) and " " not in cleaned:
        return False
    if GUID_RE.match(cleaned) or HEX_RE.match(cleaned):
        return False
    # Unity/Naninovel command lines should not be translated as text lines.
    if cleaned.startswith(("@", "//", ";", "#")):
        return False
    # Reject huge symbol tables / regex-like character tables from dump.
    visible = sum(not ch.isspace() for ch in cleaned)
    letters = sum(ch.isalpha() for ch in cleaned)
    digits = sum(ch.isdigit() for ch in cleaned)
    symbols = max(0, visible - letters - digits)
    ascii_letters = len(re.findall(r"[A-Za-z]", cleaned))
    if visible == 0:
        return False
    if len(cleaned) > 64 and " " not in cleaned and ascii_letters < 3:
        return False
    if symbols / visible > 0.68 and ascii_letters < 4 and not any(mark in cleaned for mark in "♡♥"):
        return False
    if digits > max(8, letters * 3) and " " not in cleaned:
        return False
    # One long technical token is usually not UI. Short known UI words pass.
    if " " not in cleaned and lowered not in UI_SHORT_TEXT:
        if len(cleaned) > 32 and not any(mark in cleaned for mark in ".!?,:;…♡♥"):
            return False
    return True


def parse_textasset_translatable_line(line: str):
    raw = line.rstrip("\r\n")
    newline = line[len(raw):]
    stripped = raw.strip()
    if not textasset_line_quality(stripped):
        return None
    # Preserve key/value prefixes when clearly present.
    if ":" in stripped:
        left, right = stripped.split(":", 1)
        key = left.strip()
        value = right.strip()
        if key and value and len(key) <= 80 and textasset_line_quality(value):
            prefix = key_value_line_prefix(raw, value, left)
            return {"text": value, "mode": "key_value", "prefix": prefix, "newline": newline}
    indent_len = len(raw) - len(raw.lstrip())
    return {"text": stripped, "mode": "line", "prefix": raw[:indent_len], "newline": newline}


def iter_textasset_lines(text: str):
    lines = text.splitlines(keepends=True)
    if not lines and text:
        lines = [text]
    for index, line in enumerate(lines):
        parsed = parse_textasset_translatable_line(line)
        if parsed:
            yield index, parsed


def format_duration(seconds: float) -> str:
    seconds = max(0, int(seconds))
    minutes, sec = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}h {minutes}m {sec}s"
    if minutes:
        return f"{minutes}m {sec}s"
    return f"{sec}s"


def format_file_size(num_bytes: int) -> str:
    if num_bytes >= 1024 * 1024:
        return f"{num_bytes / (1024 * 1024):.0f}MB"
    if num_bytes >= 1024:
        return f"{num_bytes / 1024:.0f}KB"
    return f"{max(0, int(num_bytes))}B"


def extract_plain_text(path: Path, root: Path, *, detected_text: bool = False):
    from vntext.extract_naninovel import rel_path
    from vntext.extract_quality import looks_like_markup_or_config, raw_text_quality, should_extract_text_file
    suffix = path.suffix.lower()
    if not detected_text and not should_extract_text_file(path, suffix):
        return
    patch_proof = {}
    # The line writer is proven for ordinary text/script files and for the
    # signature-detected extensionless fixture.  Structured formats remain
    # review/extract-only until they have field-level locators and writers.
    if detected_text or suffix in {".txt", ".nani", ".scenario"}:
        from vntext.patchability import PLAIN_TEXT_PATCH_PROOF

        patch_proof = dict(PLAIN_TEXT_PATCH_PROOF)
    rel = rel_path(path, root)
    try:
        fh = path.open("r", encoding="utf-8-sig", errors="ignore")
    except OSError:
        return
    with fh:
        for index, line in enumerate(fh, start=1):
            if len(line) > MAX_TEXT_LINE_CHARS:
                continue
            text = line.strip()
            if looks_like_markup_or_config(text):
                continue
            if raw_text_quality(text, for_main=True):
                entry = Entry(
                    source_text=text,
                    file_path=rel,
                    context=f"line:{index}",
                    import_method="plain_text_line",
                    safety="safe",
                    locator={"line": index},
                    backend="plain_text",
                    patch_proof=dict(patch_proof),
                )
                yield entry.finalize()

__all__ = ['decode_length_prefixed_at', 'decode_7bit_int_at', 'decode_7bit_length_prefixed_at', 'decode_msgpack_string_at', 'stable_packed_naninovel_text', 'is_ui_text_field', 'translatable_field', 'key_value_line_prefix', 'parse_translatable_line', 'iter_text_lines', '_semicolon_csv_read', '_semicolon_csv_write', '_norm_header_cell', 'detect_semicolon_language_table', 'iter_textasset_language_table_cells', 'textasset_line_quality', 'parse_textasset_translatable_line', 'iter_textasset_lines', 'format_duration', 'format_file_size', 'extract_plain_text']
