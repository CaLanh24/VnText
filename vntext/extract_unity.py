"""Unity extraction family.

Function bodies are mechanically preserved from the former monolithic vntext.extract module.
"""

from __future__ import annotations

from vntext.extract_constants import (
    CODE_NAME_RE,
    Entry,
    GUID_RE,
    HEX_RE,
    MAX_RAW_GROUP_BYTES,
    NANINOVEL_SKIP_WORDS,
    PATH_RE,
    PRINTABLE_UTF8,
    Path,
    TEXT_FIELD_WORDS,
    UI_MONO_CLASSES,
    UI_SHORT_TEXT,
    UNITY_UI_SCAN_MAX_FILE_BYTES,
    UTF16LE_ASCII,
    _ALIGNED_PRINTABLE,
    mmap,
    re,
    struct,
    time,
)



def ui_raw_text_quality(text: str) -> bool:
    """Strict full-file Unity UI filter.

    Used for missed UI/age-gate strings stored outside TextAsset/Naninovel windows,
    e.g. "Are you legally an adult?". Keep only complete display-looking text so
    exhaustive scan does not flood translation.csv with binary fragments.
    """
    from vntext.extract_naninovel import _strip_raw_tail_noise
    from vntext.extract_quality import _clean_inline_text, has_binary_garbage, has_vietnamese_chars, looks_like_code_or_asset_token, looks_like_demo_or_placeholder, looks_like_markup_or_config, raw_has_stray_control_or_binary
    cleaned = _strip_raw_tail_noise(_clean_inline_text(text)).strip(' \t\x00"“”')
    if ((len(cleaned) < 2 and not has_vietnamese_chars(cleaned)) or len(cleaned) > 240):
        return False
    if has_binary_garbage(cleaned):
        return False
    if looks_like_demo_or_placeholder(cleaned) or looks_like_code_or_asset_token(cleaned) or looks_like_markup_or_config(cleaned):
        return False
    if has_vietnamese_chars(cleaned):
        return True
    if raw_has_stray_control_or_binary(cleaned):
        return False
    lowered = cleaned.lower()
    if lowered in NANINOVEL_SKIP_WORDS:
        return False
    if any(tok in lowered for tok in (
        "unityengine", "monobehaviour", "scriptableobject", "assembly-csharp",
        "m_script", "m_name", "guid", "localidentifierinfile", "serialized",
        "resources/", "assets/", "images/", "audio/", "sprite", "shader", "prefab",
    )):
        return False
    if PATH_RE.search(cleaned) and " " not in cleaned:
        return False
    if GUID_RE.match(cleaned) or HEX_RE.match(cleaned) or CODE_NAME_RE.match(cleaned):
        return False
    if cleaned[0].islower():
        return False
    words = re.findall(r"[A-Za-z']+", cleaned)
    long_words = [w for w in words if len(w.strip("'’")) >= 3]
    visible = sum(not ch.isspace() for ch in cleaned)
    letters = sum(ch.isalpha() for ch in cleaned)
    digits = sum(ch.isdigit() for ch in cleaned)
    symbols = max(0, visible - letters - digits)
    if visible == 0 or letters / visible < 0.55:
        return False
    if digits > max(6, letters * 2) and " " not in cleaned:
        return False
    if symbols / visible > 0.34 and not any(mark in cleaned for mark in "♡♥…"):
        return False
    if lowered in UI_SHORT_TEXT:
        return True
    # Complete UI/dialogue sentence: menu prompt, warning, title, question, short instruction.
    has_space = " " in cleaned
    has_mark = any(mark in cleaned for mark in ".!?,:;…♡♥")
    ends_clean = cleaned[-1] in '.!?…♡♥)”\']}>:'
    if has_space and len(long_words) >= 3 and (has_mark or ends_clean):
        return True
    if has_space and len(words) >= 4:
        return True
    return False


def scan_unity_ui_blob(path: Path, root: Path, extract_level: str = "balanced") -> Iterable[Entry]:
    """Full-file Unity UI fallback.

    TextAsset/Naninovel scanners are preferred. This catches short prompts and UI
    text stored in MonoBehaviour/TMP objects that UnityPy TypeTree may not decode.
    Entries use raw_fixed_slot with original byte slot length; importer patches only
    if translated bytes fit into the original slot, otherwise it skips safely.
    """
    from vntext.extract_naninovel import decode_candidate, rel_path
    from vntext.extract_text import decode_length_prefixed_at
    rel = rel_path(path, root)
    try:
        size = path.stat().st_size
    except OSError:
        return
    if size <= 0 or size > UNITY_UI_SCAN_MAX_FILE_BYTES:
        return
    seen = set()

    def emit(text: str, context: str, locator: dict, backend: str):
        from vntext.extract_naninovel import _strip_raw_tail_noise
        from vntext.extract_quality import _clean_inline_text
        cleaned = _strip_raw_tail_noise(_clean_inline_text(text)).strip(' \t\x00"“”')
        if cleaned in seen or not ui_raw_text_quality(cleaned):
            return None
        seen.add(cleaned)
        return Entry(
            source_text=cleaned,
            file_path=rel,
            context=context,
            object_info="unity_full_file_ui_fallback",
            import_method="raw_fixed_slot",
            safety="conditional_fit",
            locator=locator,
            backend=backend,
            review_only=False,
        ).finalize()

    with path.open("rb") as fh:
        with mmap.mmap(fh.fileno(), 0, access=mmap.ACCESS_READ) as data:
            # Unity serialized strings are usually 4-byte length-prefixed and aligned.
            # Chi quet byte-by-byte tren file nho; file >2MB dung step=4 de tranh treo extract.
            step = 1 if size <= 2 * 1024 * 1024 else 4
            limit = max(0, size - 4)
            offset = 0
            while offset <= limit:
                decoded = decode_length_prefixed_at(data, offset, size, min_len=3, max_len=512)
                if decoded:
                    text, text_start, length, padded_end, encoding = decoded
                    entry = emit(
                        text,
                        f"UnityUIString@0x{text_start:x}",
                        {"offset": text_start, "length": length, "encoding": encoding, "length_offset": offset, "slot_kind": "unity_lenpref"},
                        "unity_ui_length_prefixed_scan",
                    )
                    if entry:
                        yield entry
                        offset = max(offset + step, min(padded_end, size))
                        continue
                offset += step

            # UTF-16LE literal fallback for Unity UI/TMP strings not length-prefixed in the visible blob.
            # Import stays conditional: only patch if translated UTF-16LE fits in the original slot.
            for match in UTF16LE_ASCII.finditer(data):
                raw = match.group(0)
                text = decode_candidate(raw, "utf-16le", strict=True)
                if not text:
                    continue
                entry = emit(
                    text,
                    f"UnityUIUtf16@0x{match.start():x}",
                    {"offset": match.start(), "length": len(raw), "encoding": "utf-16le", "slot_kind": "utf16_literal"},
                    "unity_ui_utf16_scan",
                )
                if entry:
                    yield entry


def scan_whole_file(path: Path, root: Path, min_len: int = 4, max_len: int = 8192) -> Iterable[Entry]:
    from vntext.extract_naninovel import decode_candidate_parts, rel_path
    from vntext.extract_quality import raw_text_quality
    rel = rel_path(path, root)
    size = path.stat().st_size
    if size <= 0:
        return
    seen_text = set()

    def emit_once(text: str, context: str, method: str, safety: str, locator: dict, backend: str, review_only: bool):
        if text in seen_text:
            return None
        seen_text.add(text)
        return Entry(
            source_text=text,
            file_path=rel,
            context=context,
            import_method=method,
            safety=safety,
            locator=locator,
            backend=backend,
            review_only=review_only,
        ).finalize()

    with path.open("rb") as fh:
        with mmap.mmap(fh.fileno(), 0, access=mmap.ACCESS_READ) as data:
            for match in PRINTABLE_UTF8.finditer(data):
                raw = match.group(0)
                if len(raw) < min_len or len(raw) > MAX_RAW_GROUP_BYTES:
                    continue
                for text in decode_candidate_parts(raw, "utf-8", strict=True):
                    if not raw_text_quality(text, for_main=False):
                        continue
                    entry = emit_once(
                        text,
                        f"raw:utf8@0x{match.start():x}",
                        "raw_review_only",
                        "unsafe",
                        {"offset": match.start(), "length": len(raw), "encoding": "utf-8"},
                        "whole_file_scan",
                        True,
                    )
                    if entry:
                        yield entry

            for match in UTF16LE_ASCII.finditer(data):
                raw = match.group(0)
                if len(raw) > MAX_RAW_GROUP_BYTES:
                    continue
                for text in decode_candidate_parts(raw, "utf-16le", strict=True):
                    if not raw_text_quality(text, for_main=False):
                        continue
                    entry = emit_once(
                        text,
                        f"raw:utf16le@0x{match.start():x}",
                        "raw_review_only",
                        "unsafe",
                        {"offset": match.start(), "length": len(raw), "encoding": "utf-16le"},
                        "whole_file_scan",
                        True,
                    )
                    if entry:
                        yield entry

            limit = max(0, size - 4)
            for offset in range(0, limit, 4):
                length = struct.unpack_from("<I", data, offset)[0]
                if length < min_len or length > max_len:
                    continue
                start = offset + 4
                end = start + length
                if end > size:
                    continue
                for text in decode_candidate_parts(data[start:end], "utf-8", strict=True):
                    if not raw_text_quality(text, for_main=True):
                        continue
                    entry = emit_once(
                        text,
                        f"raw:length_prefixed@0x{offset:x}",
                        "raw_fixed_slot",
                        "conditional",
                        {"offset": start, "length": length, "encoding": "utf-8", "length_offset": offset},
                        "length_prefixed_scan",
                        False,
                    )
                    if entry:
                        yield entry


def walk_strings(value: Any, prefix: str = ""):
    from vntext.extract_text import translatable_field
    if isinstance(value, str):
        if translatable_field(prefix, value):
            yield prefix or "$", value
    elif isinstance(value, dict):
        for key, item in value.items():
            child = f"{prefix}.{key}" if prefix else str(key)
            yield from walk_strings(item, child)
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from walk_strings(item, f"{prefix}[{index}]")


def iter_all_typetree_strings(value: Any, prefix: str = ""):
    """Dump moi string trong TypeTree, giong UABEA Export Dump field string."""
    if isinstance(value, str):
        text = value.replace("\x00", "").strip()
        if text:
            yield prefix or "$", value
    elif isinstance(value, dict):
        for key, item in value.items():
            child = f"{prefix}.{key}" if prefix else str(key)
            yield from iter_all_typetree_strings(item, child)
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from iter_all_typetree_strings(item, f"{prefix}[{index}]")


def classify_mono_string(field_path: str, text: str, class_name: str = "") -> str:
    """Sau khi dump het MonoBehaviour: main = dich, review = doi, skip = rac ky thuat."""
    from vntext.extract_quality import has_binary_garbage, looks_like_code_or_asset_token, looks_like_demo_or_placeholder, looks_like_sentence, raw_text_quality
    from vntext.extract_text import is_ui_text_field, translatable_field
    cleaned = str(text or "").strip()
    if not cleaned:
        return "skip"
    if has_binary_garbage(cleaned) or looks_like_code_or_asset_token(cleaned) or looks_like_demo_or_placeholder(cleaned):
        return "skip"
    lowered_path = str(field_path or "").lower()
    last = lowered_path.split(".")[-1].split("[")[0]
    if last in {
        "m_name", "name", "id", "key", "guid", "path", "address", "assetguid",
        "m_script", "unlockableidprefix", "managedtextcategory",
    }:
        return "skip"
    if any(tok in lowered_path for tok in (
        "sampler", "shader", "material", "sprite", "texture", "guid", "fileid",
        "assembly", "typename", "hash", "m_script", "controller", "clip",
    )):
        return "skip"
    if GUID_RE.match(cleaned) or HEX_RE.match(cleaned) or CODE_NAME_RE.match(cleaned):
        return "skip"
    if PATH_RE.search(cleaned) and " " not in cleaned:
        return "skip"
    if cleaned.startswith(("Assets/", "Resources/", "Naninovel/", "nScripts/")):
        return "skip"

    ui_field = is_ui_text_field(field_path) or class_name in UI_MONO_CLASSES
    if ui_field:
        return "main"
    if any(word in lowered_path for word in TEXT_FIELD_WORDS):
        return "main" if raw_text_quality(cleaned, for_main=True) else "skip"
    if cleaned.lower() in UI_SHORT_TEXT:
        return "main"
    if cleaned.isupper() and 3 <= len(cleaned) <= 32 and cleaned.replace(" ", "").isalpha():
        return "main"
    if translatable_field(field_path, cleaned) and looks_like_sentence(cleaned):
        return "main"
    if raw_text_quality(cleaned, for_main=True) and (" " in cleaned or any(ord(ch) > 127 for ch in cleaned)):
        return "review"
    return "skip"


def _mono_class_name(obj) -> str:
    try:
        head = obj.parse_monobehaviour_head()
        script_ptr = getattr(head, "m_Script", None)
        if script_ptr:
            script = script_ptr.deref_parse_as_object()
            return str(getattr(script, "m_ClassName", "") or "")
    except Exception:
        pass
    return ""


def _unity_script_class_name(obj) -> str:
    """Resolve a MonoBehaviour or ScriptableObject script class name."""

    class_name = _mono_class_name(obj)
    if class_name:
        return class_name
    try:
        data = obj.read()
        script_ptr = getattr(data, "m_Script", None)
        if script_ptr is not None and hasattr(script_ptr, "deref_parse_as_object"):
            script = script_ptr.deref_parse_as_object()
            return str(getattr(script, "m_ClassName", "") or "")
    except Exception:
        pass
    return ""


def _unity_string_padding(length: int) -> int:
    return (4 - (int(length) % 4)) % 4


def _drop_nested_unity_strings(found):
    """Keep outer AlignedString matches; inner int32 hits inside a payload are garbage."""
    kept = []
    spans = []
    for item in sorted(found, key=lambda row: (row["offset"], -row["byte_length"])):
        start = item["offset"]
        end = start + 4 + item["byte_length"]
        if any(span_start < start < span_end for span_start, span_end in spans):
            continue
        kept.append(item)
        spans.append((start, end))
    return kept


def _try_unity_string_at(raw: bytes, offset: int, max_string: int = 32768):
    size = len(raw)
    if offset < 0 or offset > size - 4:
        return None
    length = struct.unpack_from("<i", raw, offset)[0]
    if length < 1 or length > max_string:
        return None
    start = offset + 4
    end = start + length
    if end > size:
        return None
    pad = (4 - (length & 3)) & 3
    if end + pad > size:
        return None
    if pad and raw[end:end + pad] != (b"\x00" * pad):
        return None
    payload = raw[start:end]
    if b"\x00" in payload:
        return None
    b0 = payload[0]
    if not (b0 in (9, 10, 13) or 32 <= b0 <= 126 or b0 >= 0xc2):
        return None
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError:
        return None
    if not text:
        return None
    if length >= 80:
        printable = sum(ch.isprintable() or ch in "\r\n\t" for ch in text)
        if printable / len(text) < 0.92:
            return None
    return {
        "offset": offset,
        "data_offset": start,
        "byte_length": length,
        "encoding": "utf-8",
        "text": text,
    }


def find_aligned_unity_strings(raw: bytes, source: str):
    """Locate exact Unity AlignedString payloads for a known source_text."""
    source_text = str(source or "").strip()
    needle = source_text.encode("utf-8")
    found = []
    if not needle or not raw:
        return found
    seen = set()
    start = 0
    while True:
        pos = raw.find(needle, start)
        if pos < 0:
            break
        # Extracted display values are trimmed, while Unity may preserve one
        # or more leading spaces in the serialized payload.  Probe the small
        # prefix window and still require a complete aligned string, so a
        # substring inside another payload cannot become a match.
        for prefix_length in range(0, 9):
            offset = pos - 4 - prefix_length
            if offset < 0:
                continue
            if offset & 3:
                continue
            item = _try_unity_string_at(raw, offset)
            if item is None or str(item.get("text", "")).strip() != source_text:
                continue
            if offset not in seen:
                seen.add(offset)
                found.append(item)
        start = pos + 1
    return found


def find_aligned_unity_strings_containing(raw: bytes, source: str):
    """Locate aligned payloads that contain a known display string.

    Naninovel RandPick values can be embedded in an assignment such as
    ``tempA=RandPick2(\"...\")`` rather than stored as a display-only slot.
    Use the nearest serialized NUL/length boundary as a small probe window and
    still validate the complete Unity string before returning it.
    """
    source_text = str(source or "").strip()
    needle = source_text.encode("utf-8")
    if not needle or not raw:
        return []
    found = []
    seen: set[int] = set()
    start = 0
    while True:
        pos = raw.find(needle, start)
        if pos < 0:
            break
        window_start = max(0, pos - 32768)
        boundary = raw.rfind(b"\x00", window_start, pos)
        center = boundary + 1 - 4
        for offset in range(max(0, center - 8), min(len(raw) - 4, center + 9)):
            if offset in seen:
                continue
            if offset & 3:
                continue
            item = _try_unity_string_at(raw, offset)
            if item is None:
                continue
            if source_text not in str(item.get("text") or ""):
                continue
            seen.add(offset)
            found.append(item)
        start = pos + 1
    return found


def _scan_unity_length_prefixed_strings(raw: bytes, step: int = 4, max_string: int = 32768, seeded: bool | None = None):
    """Find Unity AlignedString payloads.

    Seeded mode is for huge files. Script/UI objects are small enough to walk every aligned slot.
    """
    found = []
    size = len(raw)
    if size < 6:
        return found
    step = max(1, int(step))
    if seeded is None:
        seeded = step == 4
    seen = set()
    if seeded:
        for match in _ALIGNED_PRINTABLE.finditer(raw):
            start = match.start()
            if start < 4:
                continue
            offset = start - 4
            if offset & 3:
                continue
            if offset in seen:
                continue
            item = _try_unity_string_at(raw, offset, max_string=max_string)
            if item is None:
                continue
            seen.add(offset)
            found.append(item)
        return _drop_nested_unity_strings(found)
    offset = 0
    limit = size - 4
    while offset <= limit:
        item = _try_unity_string_at(raw, offset, max_string=max_string)
        if item is None:
            offset += step
            continue
        found.append(item)
        nxt = item["data_offset"] + item["byte_length"] + _unity_string_padding(item["byte_length"])
        offset = nxt if nxt > offset else offset + step
    return _drop_nested_unity_strings(found)


def _typetree_field_is_display_text(field_path: str) -> bool:
    from vntext.extract_text import is_ui_text_field
    lowered = str(field_path or "").lower()
    if not lowered:
        return False
    if any(tok in lowered for tok in (
        "allowedsamplers", "shader", "material", "sprite", "texture", "guid",
        "fileid", "assembly", "m_script", "typename", "hash",
    )):
        return False
    if is_ui_text_field(field_path):
        return True
    last = lowered.split(".")[-1].split("[")[0]
    # Keep this aligned with the extractor's existing text-field vocabulary:
    # generic TypeTree components commonly call the player-facing field
    # ``scriptText``, ``dialogueText`` or ``description`` rather than m_Text.
    return last in {"displayname", "display_name"} or any(
        token in last for token in TEXT_FIELD_WORDS
    )


def iter_ui_object_entries(obj, rel: str, path_id, object_info: str, class_name: str):
    from vntext.extract_naninovel import _object_raw_bytes
    from vntext.extract_quality import is_ui_label_text, looks_like_code_or_asset_token, raw_text_quality
    from vntext.patchability import UNITY_UI_PATCH_PROOF
    raw = _object_raw_bytes(obj)
    if not raw:
        return
    seen = set()
    step = 1 if len(raw) <= 4096 else 4
    for item in _scan_unity_length_prefixed_strings(raw, step=step):
        text = str(item.get("text", "")).strip()
        if not text or text in seen or text.lstrip().startswith("@"):
            continue
        lowered = text.lower()
        is_label = is_ui_label_text(text)
        if not is_label and not raw_text_quality(text, for_main=True):
            continue
        if looks_like_code_or_asset_token(text):
            continue
        seen.add(text)
        yield Entry(
            source_text=text,
            file_path=rel,
            context=f"UI:{class_name}",
            object_info=f"{object_info}:{class_name}",
            import_method="unity_ui_text",
            safety="safe",
            locator={
                "path_id": str(path_id),
                "field_path": "m_Text",
                "class_name": class_name,
                "encoding": "utf-8",
            },
            backend="unity_ui_object",
            patch_proof=dict(UNITY_UI_PATCH_PROOF),
        ).finalize()


def extract_unity_typetree(path: Path, root: Path, progress_callback=None):
    from vntext.extract_naninovel import _mono_script_path_id, _naninovel_command_role, _object_byte_size, collect_naninovel_choice_displays_from_path, collect_naninovel_script_path_ids, collect_ui_script_path_ids, decode_candidate, iter_naninovel_display_texts, iter_naninovel_script_entries, plausible_text, rel_path
    from vntext.extract_text import is_ui_text_field, iter_textasset_language_table_cells, iter_textasset_lines
    from vntext.patchability import UNITY_TYPETREE_PATCH_PROOF, UNITY_UI_PATCH_PROOF
    from vntext.unity_localization import is_unity_localization_table_class, iter_unity_localization_entries
    try:
        import UnityPy
    except Exception:
        return

    rel = rel_path(path, root)
    try:
        if progress_callback:
            progress_callback("Dang mo UnityPy...")
        env = UnityPy.load(str(path))
    except Exception:
        return
    objects = getattr(env, "objects", None) or []
    try:
        total_objs = len(objects)
    except TypeError:
        objects = list(objects)
        total_objs = len(objects)

    has_typetree = False
    for obj in objects:
        assets_file = getattr(obj, "assets_file", None)
        if assets_file is not None:
            has_typetree = bool(getattr(assets_file, "_enable_type_tree", False))
            break

    script_pids = collect_naninovel_script_path_ids(objects)
    ui_script_pids = collect_ui_script_path_ids(objects)
    try:
        file_size = path.stat().st_size
    except OSError:
        file_size = 0
    # This is an optional file-level classification hint.  The helper uses a
    # read-only memory map, so a large data.unity3d does not become a second
    # full-size Python bytes allocation before object extraction starts.
    file_choice_displays: set[str] = collect_naninovel_choice_displays_from_path(path)
    # data.unity3d is huge: only parse likely Script objects (byte_size). Bundles stay thorough.
    min_script_bytes = 4096 if file_size > UNITY_UI_SCAN_MAX_FILE_BYTES else 0
    last_tick = 0.0
    for index, obj in enumerate(objects, start=1):
        if progress_callback:
            now = time.time()
            if index == 1 or index == total_objs or now - last_tick >= 1.0:
                progress_callback(f"Unity object {index}/{total_objs}")
                last_tick = now
        type_name = getattr(obj.type, "name", str(obj.type))
        if type_name not in {"TextAsset", "MonoBehaviour", "ScriptableObject"}:
            continue
        path_id = str(getattr(obj, "path_id", "") or "")
        object_info = f"{type_name}:{path_id}"
        if type_name == "TextAsset":
            try:
                data = obj.read()
                name = getattr(data, "m_Name", "") or getattr(data, "name", "")
                script = getattr(data, "m_Script", None)
                if script is None:
                    script = getattr(data, "script", None)
                if isinstance(script, str):
                    text = script
                    encoding = "utf-8"
                elif isinstance(script, (bytes, bytearray)):
                    text = decode_candidate(bytes(script), "utf-8") or decode_candidate(bytes(script), "utf-16le")
                    encoding = "bytes"
                else:
                    text = None
                    encoding = ""
                if text:
                    from vntext.patchability import UNITY_TEXTASSET_PATCH_PROOF
                    table_hit = False
                    for line_index, parsed in iter_textasset_language_table_cells(text):
                        table_hit = True
                        yield Entry(
                            source_text=parsed["text"],
                            file_path=rel,
                            context=f"TextAsset:{name}:table:{parsed['row_key']}:{parsed['column_name']}",
                            object_info=f"{object_info}:{name}",
                            import_method="unity_textasset_table_cell",
                            safety="safe",
                            locator={
                                "path_id": path_id,
                                "field": "m_Script",
                                "encoding": encoding,
                                "line_index": line_index,
                                "line_mode": "semicolon_language_table",
                                "delimiter": ";",
                                "column_index": parsed["column_index"],
                                "column_name": parsed["column_name"],
                                "row_key": parsed["row_key"],
                                "header_line_index": parsed["header_line_index"],
                            },
                            backend="unitypy_textasset_language_table",
                            patch_proof=dict(UNITY_TEXTASSET_PATCH_PROOF),
                        ).finalize()
                    if not table_hit and plausible_text(text):
                        for line_index, parsed in iter_textasset_lines(text):
                            yield Entry(
                                source_text=parsed["text"],
                                file_path=rel,
                                context=f"TextAsset:{name}:line:{line_index + 1}",
                                object_info=f"{object_info}:{name}",
                                import_method="unity_textasset_line",
                                safety="safe",
                                locator={
                                    "path_id": path_id,
                                    "field": "m_Script",
                                    "encoding": encoding,
                                    "line_index": line_index,
                                    "line_mode": parsed["mode"],
                                    "prefix": parsed["prefix"],
                                },
                                backend="unitypy_textasset",
                                patch_proof=dict(UNITY_TEXTASSET_PATCH_PROOF),
                            ).finalize()
            except Exception:
                pass
            continue
        if type_name == "MonoBehaviour":
            script_pid = _mono_script_path_id(obj)
            if script_pids and script_pid in script_pids and _object_byte_size(obj) >= min_script_bytes:
                yield from iter_naninovel_script_entries(
                    obj,
                    rel,
                    path_id,
                    object_info,
                    file_choice_displays=file_choice_displays,
                )
                continue
            ui_cls = ui_script_pids.get(script_pid, "")
            if ui_cls:
                for entry in iter_ui_object_entries(obj, rel, path_id, object_info, ui_cls):
                    yield entry
                continue
        if not has_typetree:
            continue
        cls = _unity_script_class_name(obj) if type_name in {"MonoBehaviour", "ScriptableObject"} else ""
        tree = None
        try:
            tree = obj.read_typetree()
        except Exception:
            tree = None
        if tree is not None and is_unity_localization_table_class(cls):
            # Only the concrete StringTable value field has a symmetric
            # reader/locator/writer/reopen proof. SharedTableData keys,
            # metadata and other Localization classes stay out of MAIN.
            yield from iter_unity_localization_entries(
                tree,
                rel,
                path_id,
                object_info,
                cls,
            )
            continue
        if tree is not None:
            for field_path, text in iter_all_typetree_strings(tree):
                displays = list(iter_naninovel_display_texts(text)) if str(text).lstrip().startswith("@") else [text]
                for display in displays:
                    if not display:
                        continue
                    bucket = classify_mono_string(field_path, display, cls)
                    if bucket == "skip":
                        continue
                    ui_field = is_ui_text_field(field_path) or cls in UI_MONO_CLASSES
                    from_cmd = str(text).lstrip().startswith("@")
                    role = _naninovel_command_role(text) if from_cmd else "plain"
                    if role == "other" and display in file_choice_displays:
                        role = "choice"
                    ctx = field_path
                    if role in {"choice", "print"}:
                        ctx = f"{field_path}:{role}"
                    import_method = (
                        "naninovel_choice" if role == "choice"
                        else ("naninovel_script_string" if from_cmd else ("unity_ui_text" if ui_field else "unity_typetree_field"))
                    )
                    yield Entry(
                        source_text=display,
                        file_path=rel,
                        context=ctx,
                        object_info=f"{object_info}:{cls}" if cls else object_info,
                        import_method=import_method,
                        safety="safe" if bucket == "main" else "unsafe",
                        locator={
                            "path_id": path_id,
                            "field_path": field_path,
                            "type": type_name,
                            "class_name": cls,
                            "command_text": text if from_cmd else None,
                            "display_role": role,
                        },
                        backend="naninovel_script_object" if from_cmd else ("unity_ui_object" if ui_field else "unitypy_typetree"),
                        review_only=(bucket == "review"),
                        patch_proof=(
                            dict(UNITY_UI_PATCH_PROOF)
                            if import_method == "unity_ui_text" and bucket == "main"
                            else (
                                dict(UNITY_TYPETREE_PATCH_PROOF)
                                if import_method == "unity_typetree_field" and bucket == "main" and _typetree_field_is_display_text(field_path)
                                else {}
                            )
                        ),
                    ).finalize()
        elif cls in UI_MONO_CLASSES:
            yield from iter_ui_object_entries(obj, rel, path_id, object_info, cls)

    # UnityPy keeps cyclic references between ObjectReader and its serialized
    # file.  A caller that extracts several large resources in one process can
    # otherwise retain the decompressed block graph until the cyclic GC runs,
    # causing a later 500+ MiB load to raise MemoryError.  Release the local
    # graph and collect only for the large-file path; small fixtures pay no
    # global-GC cost.
    if file_size > UNITY_UI_SCAN_MAX_FILE_BYTES:
        env = None
        objects = None
        obj = None
        data = None
        tree = None
        assets_file = None
        import gc

        gc.collect()

__all__ = ['ui_raw_text_quality', 'scan_unity_ui_blob', 'scan_whole_file', 'walk_strings', 'iter_all_typetree_strings', 'classify_mono_string', '_mono_class_name', '_unity_script_class_name', '_unity_string_padding', '_drop_nested_unity_strings', '_try_unity_string_at', 'find_aligned_unity_strings', 'find_aligned_unity_strings_containing', '_scan_unity_length_prefixed_strings', '_typetree_field_is_display_text', 'iter_ui_object_entries', 'extract_unity_typetree']
