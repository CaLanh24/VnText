"""Quality extraction family.

Function bodies are mechanically preserved from the former monolithic vntext.extract module.
"""

from __future__ import annotations

from vntext.extract_constants import (
    ASSIGNMENT_OR_CODE_RE,
    BAD_RAW_EDGE_RE,
    CONTROL_JUNK_RE,
    DEMO_OR_PLACEHOLDER_RE,
    GAME_TEXT_HINT_PARTS,
    NANINOVEL_SKIP_WORDS,
    TECH_FILE_NAMES,
    TECH_PATH_PARTS,
    UI_SHORT_TEXT,
    XML_CONFIG_RE,
    XML_TAG_LINE_RE,
    _CAMEL_TYPE_RE,
    _COMMON_DIALOGUE_WORDS,
    _SHORT_DIALOGUE_WORDS,
    _STAGE_DIRECTION_PREFIX_RE,
    _UI_TITLE_LABEL_RE,
    _VIETNAMESE_CHARS,
    re,
    unicodedata,
)



def looks_like_demo_or_placeholder(text: str) -> bool:
    cleaned = re.sub(r"\s+", " ", text.strip())
    if not cleaned:
        return True
    lowered = cleaned.lower()
    if DEMO_OR_PLACEHOLDER_RE.search(cleaned):
        return True
    if lowered in {"1. lorem ipsum", "sample choice"}:
        return True
    return False


def has_vietnamese_chars(text: str) -> bool:
    """True when text contains Vietnamese-specific letters/tones.

    This is intentionally a character-level signal for extracting an already
    localized fixture. It is not a general language detector and does not
    bypass explicit binary/code/path rejection performed by callers.
    """
    cleaned = str(text or "")
    if any(ch in _VIETNAMESE_CHARS for ch in cleaned):
        return True
    # Also accept decomposed Unicode input (base + combining tone mark).
    normalized = unicodedata.normalize("NFD", cleaned)
    return any(
        unicodedata.combining(ch) and ch in "\u0300\u0301\u0303\u0309\u0323"
        for ch in normalized
    ) and any(ch.isalpha() for ch in normalized)


def has_binary_garbage(text: str) -> bool:
    cleaned = text.strip()
    if CONTROL_JUNK_RE.search(cleaned):
        return True
    if "�" in cleaned or "\x00" in cleaned:
        return True
    # Raw Unity windows sometimes decode as short Latin text with one stray CJK char, e.g. f潢n.
    if has_vietnamese_chars(cleaned):
        return False
    non_ascii = [ch for ch in cleaned if ord(ch) > 127 and ch not in "…♡♥‘’“”–—éáàèùôêâîûçñÉÁÀÈÙÔÊÂÎÛÇÑ"]
    if non_ascii and len(cleaned) <= 10 and not any(mark in cleaned for mark in "♡♥…"):
        return True
    return False


def is_ui_label_text(text: str) -> bool:
    """HUD/button labels: OK, Willpower, Super Hot, Remaining AP."""
    cleaned = str(text or "").strip()
    if not cleaned or len(cleaned) > 48:
        return False
    lowered = cleaned.lower()
    if lowered in UI_SHORT_TEXT:
        return True
    if cleaned.isupper() and 3 <= len(cleaned) <= 32:
        return True
    if not _UI_TITLE_LABEL_RE.fullmatch(cleaned):
        return False
    if " " not in cleaned and _CAMEL_TYPE_RE.search(cleaned):
        return False
    return 2 <= len(cleaned) <= 40


def looks_like_code_or_asset_token(text: str) -> bool:
    cleaned = text.strip()
    lowered = cleaned.lower()
    if ASSIGNMENT_OR_CODE_RE.match(cleaned):
        return True
    if "random(" in lowered:
        return True
    if lowered.startswith(("images/", "assets/", "resources/", "naninovel/")):
        return True
    if any(tok in lowered for tok in (
        "startgameversion", "appscreen", "oview=", "mkeyword", "mcondition",
        "contain(ikeyword", "select2(", "randpick", "tempupskill",
    )):
        return True
    return False


def _clean_inline_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().replace("\\n", " ").replace("\\r", " "))


def _stage_direction_body(text: str) -> str | None:
    """Return dialogue after a bounded *stage direction* prefix, if present."""
    cleaned = _clean_inline_text(text)
    match = _STAGE_DIRECTION_PREFIX_RE.match(cleaned)
    return str(match.group("body")).strip() if match else None


def raw_has_stray_control_or_binary(text: str) -> bool:
    cleaned = text.strip()
    if has_binary_garbage(cleaned):
        return True
    if any(ch in cleaned for ch in "`|^~"):
        return True
    # Ky tu dieu khien/bytes rac hay sinh ra tu packed scan sai offset.
    if re.search(r"[\x01-\x08\x0b\x0c\x0e-\x1f\x7f]", cleaned):
        return True
    # Cum co nhieu symbol la binary/code hon la subtitle.
    visible = sum(not ch.isspace() for ch in cleaned)
    if visible:
        letters = sum(ch.isalpha() for ch in cleaned)
        digits = sum(ch.isdigit() for ch in cleaned)
        symbols = visible - letters - digits
        if symbols / visible > 0.40 and not any(mark in cleaned for mark in "♡♥…"):
            return True
    return False


def short_dialogue_fragment_ok(text: str) -> bool:
    cleaned = _clean_inline_text(text).strip(" \t\x00\"'“”‘’")
    if not (3 <= len(cleaned) <= 24):
        return False
    # Khong dung raw_has_stray_control_or_binary o day vi Ouch..! co nhieu dau cau.
    if has_binary_garbage(cleaned) or any(ch in cleaned for ch in "`|^~"):
        return False
    if re.search(r"[\x01-\x08\x0b\x0c\x0e-\x1f\x7f]", cleaned):
        return False
    if not re.fullmatch(r"[A-Za-z][A-Za-z'’]*(?:[.!?…]+|\.\.)", cleaned):
        return False
    punct = re.search(r"([.!?…]+)$", cleaned).group(1)
    core = re.sub(r"[.!?…]+$", "", cleaned).lower().strip("'’")
    if core in _SHORT_DIALOGUE_WORDS:
        return True
    vowels = sum(ch in "aeiou" for ch in core)
    repeated = bool(re.search(r"([a-z])\1", core))
    if repeated and vowels >= 1:
        # Chi chap nhan tieng keu ro rang; khong cho lot raw cat lech kieu oolice!/ohurry!/oocean.
        interjection_re = r"(?:a+h+|o+h+|o+o+h+|o+w+|o+a+w+|u+g+h+|u+m+|m+h+|m+m+|n+g+h*|e+e+k+|k+k?y+a+|g+y+a+|h+a+|h+e+h+e+|p+o+u+s+|o+w+e+t+|o+i+s+h+)"
        if re.fullmatch(interjection_re, core):
            return True
    # Combo .! / !. trong word la thuong la byte cat lech, tru khi la whitelist/lap chu.
    if "." in punct and "!" in punct:
        return False
    # Khong doan theo chu cai dau nua: cach cu cho lot rac kieu wrinces./ussy./odown.
    # Chi chap nhan short dialogue neu nam trong whitelist hoac la tieng keu co lap chu ro rang.
    return False


def dialogue_word_signal(text: str) -> bool:
    cleaned = _clean_inline_text(text).lower()
    words = [w.strip("'’") for w in re.findall(r"[A-Za-z']+", cleaned)]
    if not words:
        return False
    common = sum(1 for w in words if w in _COMMON_DIALOGUE_WORDS or w.rstrip("s") in _COMMON_DIALOGUE_WORDS)
    # Placeholder/tag text cua game co the it common words nhung van ro.
    if re.search(r"\{[A-Za-z0-9_]+\}|</?[A-Za-z][^>]{0,40}>", text):
        return True
    if common >= 1 and len(words) <= 4:
        return True
    if common >= 2:
        return True
    return False


def obvious_cut_or_gibberish_fragment(text: str) -> bool:
    cleaned = _clean_inline_text(text)
    if not cleaned:
        return True
    lowered = cleaned.lower()
    if raw_has_stray_control_or_binary(cleaned):
        return True
    # Unity/Naninovel rich-text UI is translatable even without spaces (Roaming@<color>FREE</color>).
    if re.search(r"</?[A-Za-z][^>]{0,40}>", cleaned):
        return False
    if lowered.startswith(("'s ", "'re ", "'ve ", "'m ", "'ll ", "'d ", "s ", "d ", "p ")):
        return True
    if cleaned[0].islower():
        return True
    if re.search(r"[a-z]{2,}[A-Z][A-Za-z]", cleaned):
        return True
    if re.search(r"[.!?…][A-Za-z]{1,4}$", cleaned) and not cleaned.endswith(("...", "…")):
        return True
    if re.search(r"[A-Za-z][@$^`|~][A-Za-z]", cleaned):
        return True
    if re.search(r"[A-Za-z]{1,3}\d|\d[A-Za-z]{1,3}", cleaned) and len(cleaned) < 32:
        return True
    if " " not in cleaned:
        if short_dialogue_fragment_ok(cleaned):
            return False
        # Mot token dai khong dau cau khong nen vao file dich chinh.
        if not any(mark in cleaned for mark in ".!?,:;…♡♥") and cleaned.lower() not in UI_SHORT_TEXT:
            return True
    # Word dau 1 ky tu khong phai I/A la prefix binary.
    first_word = re.findall(r"[A-Za-z']+", cleaned)
    if first_word:
        fw = first_word[0].strip("'’")
        if len(fw) == 1 and fw not in {"I", "A"}:
            return True
    return False


def strict_complete_dialogue_text(text: str) -> bool:
    cleaned = _clean_inline_text(text)
    if has_vietnamese_chars(cleaned):
        return bool(
            len(cleaned) >= 1
            and not looks_like_demo_or_placeholder(cleaned)
            and not looks_like_code_or_asset_token(cleaned)
            and "\x00" not in cleaned
            and "�" not in cleaned
        )
    shape_text = _stage_direction_body(cleaned) or cleaned
    if len(shape_text) < 3:
        return False
    if looks_like_demo_or_placeholder(shape_text) or looks_like_code_or_asset_token(shape_text):
        return False
    if obvious_cut_or_gibberish_fragment(shape_text):
        return False
    lowered = shape_text.lower()
    if lowered in UI_SHORT_TEXT:
        return True
    if short_dialogue_fragment_ok(shape_text):
        return True
    if lowered.startswith('title="') and 4 <= len(shape_text) <= 80:
        return True
    words = re.findall(r"[A-Za-z']+", shape_text)
    long_words = [w for w in words if len(w.strip("'’")) >= 3]
    has_space = " " in shape_text
    has_mark = any(mark in shape_text for mark in ".!?,:;…♡♥")
    starts_ok = shape_text[0].isupper() or shape_text[0] in "'\"([{<¿¡…“‘" or any(ord(ch) > 127 for ch in shape_text)
    if not starts_ok:
        return False
    if len(shape_text) < 14 and not has_mark and lowered not in UI_SHORT_TEXT:
        return False
    has_tag_or_placeholder = bool(re.search(r"\{[A-Za-z0-9_]+\}|</?[A-Za-z][^>]{0,40}>", shape_text))
    ends_clean = shape_text[-1] in ".!?…♡♥)’\'\"]}>"
    # v1.19: packed/raw scan sai offset hay sinh mid-string. Muon vao translation.csv
    # phai co ket thuc sach, tru UI short/placeholder/tag ro rang.
    if not ends_clean and lowered not in UI_SHORT_TEXT and not has_tag_or_placeholder:
        return False
    # Packed string khong co dau cau thuong la mid-string fragment; de candidate, khong dua main.
    if not has_mark and not has_tag_or_placeholder and lowered not in UI_SHORT_TEXT:
        return False
    # Packed/raw sai offset hay sinh cum English vo nghia. Can it nhat 1-2 common dialogue words.
    if not dialogue_word_signal(cleaned) and len(cleaned) < 42:
        return False
    if has_space and (has_mark or len(long_words) >= 3):
        return True
    if len(long_words) >= 2 and has_mark:
        return True
    return False


def patchable_blob_text(text: str) -> bool:
    from vntext.extract_naninovel import naninovel_candidate_text, text_noise_score
    if has_binary_garbage(text):
        return False
    cleaned = _clean_inline_text(text)
    if not naninovel_candidate_text(cleaned, for_main=True):
        return False
    if has_vietnamese_chars(cleaned):
        return True
    if looks_like_demo_or_placeholder(cleaned) or has_binary_garbage(cleaned) or looks_like_code_or_asset_token(cleaned):
        return False
    if text_noise_score(cleaned) >= 35:
        return False
    # v1.18: length-prefixed/packed scan sai offset hay sinh mid-string fragment.
    # Chi cho main neu co hinh dang cau/UI tuong doi tron.
    if not strict_complete_dialogue_text(cleaned):
        return False
    return True


def looks_like_sentence(text: str) -> bool:
    cleaned = text.strip()
    if " " in cleaned:
        return True
    return any(mark in cleaned for mark in ".!?,:;…") or any(ord(ch) > 127 for ch in cleaned)


def path_parts_lower(path: Path) -> set[str]:
    return {part.lower() for part in path.parts}


def is_technical_path(path: Path) -> bool:
    name = path.name.lower()
    parts = path_parts_lower(path)
    if name in TECH_FILE_NAMES:
        return True
    if parts & TECH_PATH_PARTS:
        # Cho phep folder text/localization that su trong StreamingAssets, con lai bo qua.
        if (parts & GAME_TEXT_HINT_PARTS) and not ({"monobleedingedge", "managed", "addressableslink"} & parts):
            return False
        return True
    return False


def should_extract_text_file(path: Path, suffix: str) -> bool:
    if is_technical_path(path):
        return False
    parts = path_parts_lower(path)
    name = path.name.lower()
    if suffix == ".xml":
        # XML cua Unity/Mono/Addressables gan nhu toan config. Chi cho qua neu nam trong folder text/localization.
        return bool(parts & {"text", "texts", "localization", "localisation", "language", "languages"})
    if suffix == ".csv" and name == "translation.csv":
        return False
    return True


def looks_like_markup_or_config(text: str) -> bool:
    stripped = text.strip()
    if not stripped:
        return True
    if XML_TAG_LINE_RE.match(stripped) or XML_CONFIG_RE.search(stripped):
        return True
    if stripped.startswith(("<?xml", "<!DOCTYPE", "<!--", "</")):
        return True
    lowered = stripped.lower()
    if lowered.startswith(("xmlns", "publickeytoken", "culture=", "processorarchitecture=")):
        return True
    return False


def raw_text_quality(text: str, for_main: bool = False) -> bool:
    from vntext.extract_naninovel import plausible_text
    cleaned = text.strip()
    if not plausible_text(cleaned, strict=True):
        return False
    lowered = cleaned.lower()
    if looks_like_demo_or_placeholder(cleaned) or has_binary_garbage(cleaned):
        return False
    if lowered in NANINOVEL_SKIP_WORDS:
        return False
    if looks_like_markup_or_config(cleaned):
        return False
    # Ro rac binary hay fragment bi cat lech offset.
    if "\x00" in cleaned or "�" in cleaned:
        return False
    if "`" in cleaned or "|" in cleaned:
        return False
    if "\\" in cleaned and not re.search(r"\\[nrt'\"\\]", cleaned):
        return False
    if has_vietnamese_chars(cleaned):
        # A localized game is a high-confidence extraction fixture. Keep all
        # Vietnamese text after the explicit binary/code/config checks above;
        # do not apply English-only start/end/word heuristics to it.
        if looks_like_code_or_asset_token(cleaned):
            return False
        return True
    if BAD_RAW_EDGE_RE.search(cleaned) and _stage_direction_body(cleaned) is None:
        return False
    letters = sum(ch.isalpha() for ch in cleaned)
    digits = sum(ch.isdigit() for ch in cleaned)
    spaces = sum(ch.isspace() for ch in cleaned)
    visible = sum(not ch.isspace() for ch in cleaned)
    symbols = visible - letters - digits
    if visible and symbols / visible > 0.45:
        return False
    if digits > max(6, letters * 2) and spaces == 0:
        return False
    if re.search(r"[A-Za-z0-9]{1,3}[_/][A-Za-z0-9]{1,3}", cleaned) and " " not in cleaned:
        return False
    if re.search(r"[A-Za-z][_$^~][A-Za-z]", cleaned):
        return False
    if re.search(r"[.!?…][A-Za-z]$", cleaned):
        # VD: 'are you okay?d' = fragment bi dinh byte rac o cuoi.
        return False
    if re.search(r"^[a-z]{1,2}[.!?,]", cleaned):
        return False
    if for_main:
        if len(cleaned) <= 3 and lowered not in UI_SHORT_TEXT and not any(ord(ch) > 127 for ch in cleaned):
            return False
        # Main CSV chi nen la cau/choice/UI kha ro, khong phai token mot-tu dai.
        if " " not in cleaned and lowered not in UI_SHORT_TEXT and not is_ui_label_text(cleaned) and not any(mark in cleaned for mark in ".!?,:;…♡♥") and not any(ord(ch) > 127 for ch in cleaned):
            return False
    return True

__all__ = ['looks_like_demo_or_placeholder', 'has_vietnamese_chars', 'has_binary_garbage', 'is_ui_label_text', 'looks_like_code_or_asset_token', '_clean_inline_text', '_stage_direction_body', 'raw_has_stray_control_or_binary', 'short_dialogue_fragment_ok', 'dialogue_word_signal', 'obvious_cut_or_gibberish_fragment', 'strict_complete_dialogue_text', 'patchable_blob_text', 'looks_like_sentence', 'path_parts_lower', 'is_technical_path', 'should_extract_text_file', 'looks_like_markup_or_config', 'raw_text_quality']
