"""Naninovel extraction family.

Function bodies are mechanically preserved from the former monolithic vntext.extract module.
"""

from __future__ import annotations

from typing import Iterable

from vntext.extract_constants import (
    ASCII_WINDOW_TEXT,
    CODE_NAME_RE,
    Entry,
    GUID_RE,
    HEX_RE,
    MAX_RAW_SCAN_FILE_BYTES,
    MIN_NANINOVEL_SCRIPT_OBJECT_BYTES,
    NANINOVEL_SCRIPT_RAW_HINTS,
    NANINOVEL_SCRIPT_TOKENS,
    NANINOVEL_WINDOW_AFTER,
    NANINOVEL_WINDOW_BEFORE,
    PATH_RE,
    SKIP_DEEP_EXTS,
    TEXT_EXTS,
    UI_MONO_CLASSES,
    UI_SHORT_TEXT,
    UNITY_DATA_BLOB_EXTS,
    UNITY_EXTS,
    UNITY_NOISE_WORDS,
    _NANINOVEL_CHOICE_QUOTED_RE,
    _NANINOVEL_NAMED_TEXT_RE,
    _NANINOVEL_SCRIPT_TECH_EXACT,
    _NANINOVEL_SCRIPT_TECH_RE,
    _NANINOVEL_SCRIPT_TECH_WORDS,
    _NANINOVEL_STAGE_ONLY_RE,
    _NANINOVEL_TEXT_CMD_RE,
    _RANDPICK_RE,
    mmap,
    re,
)



def plausible_text(text: str, strict: bool = False) -> bool:
    from vntext.extract_quality import has_vietnamese_chars
    cleaned = text.strip()
    if (len(cleaned) < 2 and not has_vietnamese_chars(cleaned)) or "\x00" in cleaned:
        return False
    if "\ufffd" in cleaned:
        return False
    lowered = cleaned.lower()
    if GUID_RE.match(cleaned) or HEX_RE.match(cleaned):
        return False
    if any(word in lowered for word in UNITY_NOISE_WORDS):
        return False
    if PATH_RE.search(cleaned) and " " not in cleaned:
        return False
    if CODE_NAME_RE.match(cleaned):
        return False
    visible = sum(not ch.isspace() for ch in cleaned)
    if visible == 0:
        return False
    letters = sum(ch.isalpha() for ch in cleaned)
    digits = sum(ch.isdigit() for ch in cleaned)
    symbols = visible - letters - digits
    if letters == 0 and not any(ord(ch) > 127 for ch in cleaned):
        return False
    if len(cleaned) > 24 and " " not in cleaned and "_" in cleaned:
        return False
    if len(cleaned) > 32 and " " not in cleaned and re.search(r"[A-Z][a-z]+[A-Z]", cleaned):
        return False
    if strict:
        if len(cleaned) < 3 and not has_vietnamese_chars(cleaned):
            return False
        if len(cleaned) > 80 and " " not in cleaned:
            return False
        if symbols > letters + 4:
            return False
        if digits > letters * 2 and " " not in cleaned:
            return False
        if "_" in cleaned and " " not in cleaned:
            return False
        short = cleaned.lower()
        if len(cleaned) <= 3 and short not in UI_SHORT_TEXT and not any(ord(ch) > 127 for ch in cleaned):
            return False
    return True


def rel_path(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def iter_files(root: Path):
    if root.is_file():
        yield root
        return
    for path in root.rglob("*"):
        if path.is_file():
            yield path


def should_raw_scan(path: Path, suffix: str) -> bool:
    if suffix in TEXT_EXTS or suffix in UNITY_EXTS or suffix in SKIP_DEEP_EXTS or suffix in UNITY_DATA_BLOB_EXTS:
        return False
    parts = {part.lower() for part in path.parts}
    if {"managed", "monobleedingedge", "plugins", "resources"} & parts:
        return False
    try:
        if path.stat().st_size > MAX_RAW_SCAN_FILE_BYTES:
            return False
    except OSError:
        return False
    return True


def should_naninovel_scan(path: Path, suffix: str, *, is_unity_resource: bool | None = None) -> bool:
    if is_unity_resource is None:
        is_unity_resource = suffix in UNITY_EXTS
    if not is_unity_resource:
        return False
    # UnityFS/WebData1.0 stores serialized assets in compressed blocks.  A
    # file-level ASCII/length-prefix scan sees compressed bytes and produces
    # fragments that have no object locator; the UnityPy object extractor is
    # the authoritative route for these containers.
    try:
        with path.open("rb") as stream:
            header = stream.read(16)
        if header.startswith((b"UnityFS", b"UnityWebData1.0")):
            return False
    except OSError:
        return False
    lowered = str(path).lower()
    name = path.name.lower()
    if "data.unity3d" in name or "naninovel" in lowered or "resources.assets" in name or "sharedassets" in name:
        return True
    try:
        return path.stat().st_size <= 768 * 1024 * 1024
    except OSError:
        return False


def decode_candidate(raw: bytes, encoding: str, strict: bool = False) -> str | None:
    try:
        text = raw.decode(encoding)
    except UnicodeDecodeError:
        return None
    text = text.replace("\r\n", "\n").replace("\r", "\n").strip("\x00 \t")
    return text if plausible_text(text, strict=strict) else None


def naninovel_candidate_text(text: str, for_main: bool = True) -> bool:
    from vntext.extract_quality import has_binary_garbage, looks_like_demo_or_placeholder, raw_text_quality
    cleaned = text.strip().replace("\\n", " ").replace("\\r", " ")
    if not raw_text_quality(cleaned, for_main=for_main):
        return False
    lowered = cleaned.lower()
    if looks_like_demo_or_placeholder(cleaned) or has_binary_garbage(cleaned):
        return False
    if lowered.startswith(("assets/", "library/", "projectsettings/", "packages/", "resources/")):
        return False
    if any(word in lowered for word in (
        "naninovel.", "unity.", "unityengine", "shader", "texture", "sprite",
        "audioclip", "animationclip", "controller", "material", "prefab",
        "assembly-csharp", "serialized", "typetree", "system.", "microsoft.",
    )):
        return False
    if re.fullmatch(r"[A-Za-z0-9_./:@#-]{2,80}", cleaned):
        short = cleaned.lower()
        if short not in UI_SHORT_TEXT and not any(mark in cleaned for mark in ".!?,:;…♡♥"):
            return False
    return " " in cleaned or any(mark in cleaned for mark in ".!?,:;…♡♥") or lowered in UI_SHORT_TEXT or any(ord(ch) > 127 for ch in cleaned)


def text_noise_score(text: str) -> int:
    cleaned = text.strip()
    score = 0
    if not cleaned:
        return 999
    visible = sum(not ch.isspace() for ch in cleaned)
    letters = sum(ch.isalpha() for ch in cleaned)
    digits = sum(ch.isdigit() for ch in cleaned)
    symbols = max(0, visible - letters - digits)
    lowered = cleaned.lower()
    if "\x00" in cleaned or "�" in cleaned:
        score += 100
    if any(word in lowered for word in UNITY_NOISE_WORDS):
        score += 80
    if any(word in lowered for word in ("naninovel.", "unityengine", "system.", "microsoft.", "assembly-csharp", "typetree")):
        score += 80
    if PATH_RE.search(cleaned) and " " not in cleaned:
        score += 70
    if GUID_RE.match(cleaned) or HEX_RE.match(cleaned):
        score += 70
    if CODE_NAME_RE.match(cleaned):
        score += 55
    if visible and symbols / visible > 0.38:
        score += 35
    if digits > max(6, letters * 2) and " " not in cleaned:
        score += 30
    if "`" in cleaned or "|" in cleaned:
        score += 25
    if re.search(r"[A-Za-z][_$^~][A-Za-z]", cleaned):
        score += 30
    if re.search(r"[A-Za-z0-9]{1,3}[_/][A-Za-z0-9]{1,3}", cleaned) and " " not in cleaned:
        score += 25
    if cleaned.startswith(("@", "//", "/*", "#")):
        score += 30
    return score


def looks_like_cut_fragment(text: str) -> bool:
    cleaned = text.strip()
    if not cleaned:
        return True
    lowered = cleaned.lower()
    first = cleaned[0]
    last = cleaned[-1]
    # Cac raw span cat lech byte hay bat dau giua tu: "ith her, but", "om all.".
    if first.islower():
        has_end_punct = last in ".!?…♡♥)”'\"]}"
        has_dialogue_mark = any(mark in cleaned for mark in ("...", "?!", "!?", "♡", "♥"))
        if len(cleaned) < 28 and not has_dialogue_mark:
            return True
        if not has_end_punct and len(cleaned) < 48:
            return True
    # Ket thuc bang ky tu chu cai don le sau dau cau thuong la byte rac dinh o duoi.
    if re.search(r"[.!?…][A-Za-z]$", cleaned):
        return True
    if re.search(r"^[a-z]{1,2}[.!?,]", cleaned):
        return True
    return False


def likely_main_raw_text(text: str) -> bool:
    cleaned = re.sub(r"\s+", " ", text.strip().replace("\\n", " ").replace("\\r", " "))
    if not naninovel_candidate_text(cleaned, for_main=False):
        return False
    if text_noise_score(cleaned) >= 30:
        return False
    if looks_like_cut_fragment(cleaned):
        return False
    lowered = cleaned.lower()
    if lowered in UI_SHORT_TEXT:
        return True
    if len(cleaned) < 5:
        return False
    if cleaned[0].isdigit():
        return False
    # Raw binary cat lech hay tao token nhu Qbody,3$!seo / Q head / Ta mea.
    if re.search(r"[A-Za-z0-9][@$^`|~][A-Za-z0-9]", cleaned):
        return False
    first_word = cleaned.split()[0].strip("'\"([{<") if cleaned.split() else ""
    if re.match(r"^[A-Z]\s+", cleaned) and first_word not in {"I", "A"}:
        return False
    common_short_start = {"I", "A", "Ah", "Oh", "No", "Ok", "OK", "He", "We", "My", "Mr", "Ms", "Dr"}
    if 2 <= len(first_word) <= 3 and first_word not in common_short_start:
        if len(cleaned) < 14 and not any(mark in cleaned for mark in ".!?,:;…♡♥"):
            return False
    if re.search(r"[A-Za-z]{1,3}\d|\d[A-Za-z]{1,3}", cleaned) and " " not in cleaned:
        return False
    if re.search(r"[A-Za-z]{1,3}\d|\d[A-Za-z]{1,3}", cleaned) and len(cleaned) < 18:
        return False
    if any(ch in cleaned for ch in "@$^`|~"):
        return False
    if re.search(r"[A-Za-z]\([^)]{0,20}[,=]", cleaned):
        return False
    if cleaned.count('"') == 1 and "Name=\"" in cleaned:
        return False
    words = re.findall(r"[A-Za-z']+", cleaned)
    long_words = [w for w in words if len(w.strip("'")) >= 3]
    if not long_words and not any(ord(ch) > 127 for ch in cleaned):
        return False
    starts_ok = cleaned[0].isupper() or cleaned[0] in "'\"([{<¿¡…“‘" or cleaned.startswith(("...", "[br]", "<color", "<size")) or any(ord(ch) > 127 for ch in cleaned)
    has_sentence_shape = (
        " " in cleaned
        or any(mark in cleaned for mark in ".!?,:;…♡♥")
        or any(ord(ch) > 127 for ch in cleaned)
    )
    if not starts_ok:
        return False
    # Mot cum raw khong co dau cau va qua ngan thuong la fragment.
    if len(cleaned) < 14 and not any(mark in cleaned for mark in ".!?,:;…♡♥") and len(words) < 3:
        return False
    return has_sentence_shape


def _word_stats_for_raw(cleaned: str):
    visible = sum(not ch.isspace() for ch in cleaned)
    letters = sum(ch.isalpha() for ch in cleaned)
    digits = sum(ch.isdigit() for ch in cleaned)
    symbols = max(0, visible - letters - digits)
    words = re.findall(r"[A-Za-z']+", cleaned)
    long_words = [w for w in words if len(w.strip("'")) >= 3]
    return visible, letters, digits, symbols, words, long_words


def _strip_raw_tail_noise(text: str) -> str:
    """Cat bot phan duoi bi dinh byte sau dau cau."""
    cleaned = re.sub(r"\s+", " ", text.strip().replace("\\n", " ").replace("\\r", " "))
    if not cleaned:
        return cleaned
    m = re.search(r"^(.{3,}?[.!?…]+)[A-Za-z]{1,4}$", cleaned)
    if m:
        return m.group(1).strip()
    m = re.search(r"^(.{3,}?[.!?…]+)\s+[A-Z]?[<%][^ ]{1,32}$", cleaned)
    if m:
        return m.group(1).strip()
    m = re.search(r"^(.{3,}?[.!?…]+)\s+[A-Z][A-Za-z0-9<>%]{2,24}$", cleaned)
    if m and len(cleaned) - len(m.group(1)) <= 18:
        return m.group(1).strip()
    return cleaned


def split_naninovel_raw_fragments(text: str) -> list[str]:
    """Tach raw Naninovel bi ghep bang @ thanh cac cau dich duoc."""
    cleaned = re.sub(r"\s+", " ", text.strip().replace("\\n", " ").replace("\\r", " "))
    if not cleaned:
        return []
    pieces = re.split(r"[@\x00\t]+", cleaned)
    out: list[str] = []
    seen: set[str] = set()
    for piece in pieces:
        seg = _strip_raw_tail_noise(piece.strip(" \t\x00"))
        seg = seg.strip("•·_|~`^\\\" \t\x00")
        if not seg or seg in seen:
            continue
        seen.add(seg)
        out.append(seg)
    return out or [cleaned]


def raw_review_tier(text: str) -> int:
    """0=bo qua, 1=ung vien yeu, 2=ung vien can soi, 3=du sach de vao translation.csv.

    v1.17 tach ro raw candidate: balanced chi dua tier 3 vao translation.csv.
    Tier 1/2 di raw_candidates.csv de khong lam file dich chinh bi rac nhung van khong mat text.
    """
    from vntext.extract_postprocess import _looks_like_corrupt_raw_short
    from vntext.extract_quality import has_vietnamese_chars, short_dialogue_fragment_ok, strict_complete_dialogue_text
    cleaned = _strip_raw_tail_noise(re.sub(r"\s+", " ", text.strip().replace("\\n", " ").replace("\\r", " ")))
    if len(cleaned) < 3 and not has_vietnamese_chars(cleaned):
        return 0
    if _looks_like_corrupt_raw_short(cleaned, "naninovel_raw_balanced_main"):
        return 2
    expressive_short_pre = short_dialogue_fragment_ok(cleaned)
    if expressive_short_pre:
        return 3
    if not naninovel_candidate_text(cleaned, for_main=False):
        return 0
    if has_vietnamese_chars(cleaned):
        return 3

    lowered = cleaned.lower()
    hard_junk = (
        "contain(", "pick2(", "select2", "tempupskill", "radialblur",
        "mtrait", "mkeyword", "mcondition", "mname=", "hash=",
        "guid", "assetbundle", "addressable", "localidentifierinfile",
        "random(", "visit=random", "=false", "=true", "==", "!=",
        "resources/", "images/", "audio/", "sprite", "shader", "prefab",
    )
    if any(tok in lowered for tok in hard_junk):
        return 0
    # Title="... co the la UI title, de candidate chu khong bo thang.
    if lowered.startswith('title="'):
        return 2 if len(cleaned) <= 80 else 0
    if any(ch in cleaned for ch in "`|^~"):
        return 0
    if "_" in cleaned or re.search(r"\d", cleaned):
        return 0
    if '"' in cleaned and not lowered.startswith('title="') and not (cleaned.startswith('"') and cleaned.endswith('"')):
        return 0
    if re.search(r"[.!?…][A-Za-z]{1,4}$", cleaned) and not cleaned.endswith(("...", "…")):
        return 0
    if re.search(r"[a-z]{2,}[A-Z][A-Za-z]*", cleaned):
        return 0
    if ("<" in cleaned or ">" in cleaned) and not re.search(r"</?[A-Za-z][^>]{0,40}>", cleaned):
        return 0
    if cleaned.count("(") != cleaned.count(")") and re.search(r"[A-Za-z0-9][()]|[()][A-Za-z0-9]", cleaned):
        return 0
    if re.search(r"[A-Za-z][@$][A-Za-z]", cleaned):
        return 0
    if re.search(r"[A-Za-z][+*/\\][A-Za-z0-9]|[A-Za-z0-9][+*/\\][A-Za-z]", cleaned):
        return 0
    # CamelCase dai gan nhu token code. Dung regex nhe hon de khong giet cau co I/I'm.
    if re.fullmatch(r"[A-Za-z]{2,}[A-Z][A-Za-z]{2,}", cleaned):
        return 0
    if re.match(r"^[A-Z]\s+", cleaned) and not cleaned.startswith(("I ", "A ")):
        return 0

    noise = text_noise_score(cleaned)
    if noise >= 55:
        return 0

    visible, letters, digits, symbols, words, long_words = _word_stats_for_raw(cleaned)
    if visible == 0:
        return 0

    # Interjection/thoai ngan co the co nhieu dau cham/than: Ouch..!, Kkya!!!!
    expressive_short = short_dialogue_fragment_ok(cleaned)
    if expressive_short:
        return 3

    if " " not in cleaned and any(ch.isdigit() for ch in cleaned):
        return 0
    if " " not in cleaned and any(ch in cleaned for ch in ",$%&=#"):
        return 0
    if letters / visible < 0.42:
        return 0
    if symbols / visible > 0.38:
        return 0
    if re.search(r"[A-Za-z]{1,3}\d|\d[A-Za-z]{1,3}", cleaned) and len(cleaned) < 32:
        return 0

    has_sentence_mark = any(mark in cleaned for mark in ".!?,:;…♡♥")
    ends_clean = cleaned[-1] in ".!?…♡♥)’'\"]}"
    starts_clean = cleaned[0].isupper() or cleaned[0] in "'\"([{<¿¡…“‘" or any(ord(ch) > 127 for ch in cleaned)

    # Interjection/thoai ngan: Ouch..!, Owet?, Pous.., Umm.
    if short_dialogue_fragment_ok(cleaned):
        return 3

    # Chuoi bat dau chu thuong thuong la bi cat dau. Giu candidate de soi,
    # khong cho vao translation.csv balanced nua.
    if cleaned[0].islower():
        if " " in cleaned and (has_sentence_mark or len(long_words) >= 3):
            return 2
        return 1 if len(cleaned) >= 8 else 0

    if " " not in cleaned and not short_dialogue_fragment_ok(cleaned) and lowered not in UI_SHORT_TEXT:
        return 2 if has_sentence_mark and len(long_words) >= 1 else 1

    if likely_main_raw_text(cleaned) and strict_complete_dialogue_text(cleaned):
        return 3
    if starts_clean and ends_clean and len(long_words) >= 1 and has_sentence_mark:
        return 3
    if starts_clean and len(long_words) >= 3 and (has_sentence_mark or len(cleaned) >= 26):
        return 3
    if starts_clean and len(long_words) >= 2 and " " in cleaned:
        return 2
    if has_sentence_mark and len(long_words) >= 1:
        return 2
    return 1 if len(long_words) >= 1 else 0


def naninovel_raw_bucket(text: str, extract_level: str) -> str:
    """Tra ve main/candidate/review/skip cho raw fallback.

    clean: chi text rat chac.
    balanced: translation.csv sach hon; raw nghi la thoai vao raw_candidates.csv.
    exhaustive: dua gan tat ca candidate vao translation.csv de soi thieu.
    """
    from vntext.extract_quality import short_dialogue_fragment_ok, strict_complete_dialogue_text
    level = (extract_level or "balanced").lower()
    tier = raw_review_tier(text)
    if tier <= 0:
        return "skip"
    if level in {"aggressive", "exhaustive", "raw"}:
        # Exhaustive khong duoc nhet het vao translation.csv.
        # Tier 3 moi vao file dich chinh; tier 1/2 giu trong raw_candidates.csv de soi/auto-triage.
        return "main" if tier >= 3 else ("candidate" if tier >= 1 else "skip")
    if level == "clean":
        return "main" if tier >= 3 else ("candidate" if tier >= 2 else "skip")
    # balanced: tier 3 vao translation.csv, tier 1/2 khong bo - chuyen raw_candidates.csv.
    if tier >= 3:
        # v1.18: tier 3 van phai la cau/UI tuong doi tron hoac interjection ngan chac chan.
        return "main" if (strict_complete_dialogue_text(text) or short_dialogue_fragment_ok(text)) else "candidate"
    if tier >= 1:
        return "candidate"
    return "skip"


def decode_candidate_parts(raw: bytes, encoding: str, strict: bool = False):
    try:
        text = raw.decode(encoding)
    except UnicodeDecodeError:
        return
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    pieces = []
    for line in text.split("\n"):
        pieces.extend(re.split(r"[\x00\t]+", line))
    seen = set()
    for piece in pieces:
        cleaned = piece.strip(" \t\x00")
        if cleaned in seen:
            continue
        seen.add(cleaned)
        if plausible_text(cleaned, strict=strict):
            yield cleaned


def merge_ranges(ranges):
    if not ranges:
        return []
    ranges.sort()
    merged = [ranges[0]]
    for start, end in ranges[1:]:
        last_start, last_end = merged[-1]
        if start <= last_end:
            merged[-1] = (last_start, max(last_end, end))
        else:
            merged.append((start, end))
    return merged


def repair_known_ui_raw_fragment(text: str, abs_start: int) -> tuple[str, dict] | None:
    """Sua mot so raw fragment bi cat mat ky tu dau/duoi.

    Case thuc te: age gate hien trong game la "Are you legally an adult?" nhung
    raw fallback bat duoc "re you legally an adult?$". Neu de la candidate unsafe
    thi no khong vao translation.csv va khong patch duoc. Ham nay tao raw_fixed_slot
    co offset lui 1 byte de patch thang chuoi UI trong data.unity3d.
    """
    from vntext.extract_quality import _clean_inline_text
    cleaned = _clean_inline_text(text).strip(" \t\x00\"“”")
    low = cleaned.lower().strip()
    if re.fullmatch(r"re you legally an adult\?\$?", low):
        fixed = "Are you legally an adult?"
        return fixed, {
            "offset": max(0, abs_start - 1),
            "length": len(fixed.encode("utf-8")),
            "encoding": "utf-8",
            "slot_kind": "repaired_age_gate_raw",
            "raw_original": text,
            "raw_offset": abs_start,
        }
    return None


def scan_naninovel_blob(path: Path, root: Path, extract_level: str = "balanced") -> Iterable[Entry]:
    """Naninovel fallback sach hon.

    v1.9 dung ASCII window nen hay cat lech byte thanh rac kieu 'are you okay?d'.
    Ban nay uu tien string co length-prefix trong vung gan token Naninovel -> it rac hon.
    ASCII fragment van duoc xuat review_only, khong vao CSV dich chinh.
    """
    from vntext.extract_quality import patchable_blob_text
    from vntext.extract_text import decode_7bit_length_prefixed_at, decode_length_prefixed_at, decode_msgpack_string_at, stable_packed_naninovel_text
    rel = rel_path(path, root)
    try:
        size = path.stat().st_size
    except OSError:
        return
    if size <= 0:
        return
    seen_main = set()
    seen_review = set()
    windows = []
    with path.open("rb") as fh:
        with mmap.mmap(fh.fileno(), 0, access=mmap.ACCESS_READ) as data:
            for token in NANINOVEL_SCRIPT_TOKENS:
                pos = 0
                while True:
                    found = data.find(token, pos)
                    if found < 0:
                        break
                    pos = found + len(token)
                    windows.append((
                        max(0, found - NANINOVEL_WINDOW_BEFORE),
                        min(size, found + NANINOVEL_WINDOW_AFTER),
                    ))

            # Backend chinh: length-prefixed strings gan command Naninovel.
            occupied = []
            for start, end in merge_ranges(windows):
                offset = start
                while offset <= end - 6:
                    decoded = decode_length_prefixed_at(data, offset, size, min_len=2, max_len=12000)
                    if decoded:
                        text, text_start, length, padded_end, encoding = decoded
                        text = text.strip().replace("\\n", " ").replace("\\r", " ")
                        displays = []
                        if text.lstrip().startswith("@"):
                            displays = [
                                item for item in iter_naninovel_display_texts(text)
                                if item and (patchable_blob_text(item) or item.lower() in UI_SHORT_TEXT or len(item) >= 2)
                            ]
                        elif patchable_blob_text(text):
                            displays = [text]
                        for display in displays:
                            if display in seen_main:
                                continue
                            seen_main.add(display)
                            occupied.append((text_start, text_start + length))
                            from_cmd = text.lstrip().startswith("@")
                            role = _naninovel_command_role(text) if from_cmd else "plain"
                            ctx = f"NaninovelLenString@0x{text_start:x}"
                            if role in {"choice", "print"}:
                                ctx = f"{ctx}:{role}"
                            import_method = (
                                "naninovel_choice" if role == "choice"
                                else ("naninovel_script_string" if from_cmd else "naninovel_blob_string")
                            )
                            yield Entry(
                                source_text=display,
                                file_path=rel,
                                context=ctx,
                                object_info="targeted_naninovel_length_prefixed",
                                import_method=import_method,
                                safety="conditional",
                                locator={
                                    "offset": text_start,
                                    "length": length,
                                    "encoding": encoding,
                                    "length_offset": offset,
                                    "command_text": text if from_cmd else None,
                                    "display_role": role,
                                },
                                backend="naninovel_script_object" if from_cmd else "naninovel_length_prefixed_scan",
                                review_only=False,
                            ).finalize()
                        offset = max(offset + 1, min(padded_end, end))
                    else:
                        offset += 1

            # Backend them: nhieu game/Naninovel luu string bang .NET 7-bit length
            # hoac MessagePack, khong phai Unity 4-byte length. Quet 2 format nay
            # truoc ASCII fallback de lay nguyen cau, giam fragment kieu "ith her, but".
            def raw_overlaps_taken(a: int, b: int) -> bool:
                for x, y in occupied:
                    if a < y and b > x:
                        return True
                return False

            packed_decoders = (
                ("naninovel_7bit_string_scan", decode_7bit_length_prefixed_at),
                ("naninovel_msgpack_string_scan", decode_msgpack_string_at),
            )
            for backend_name, decoder in packed_decoders:
                for start, end in merge_ranges(windows):
                    offset = start
                    while offset <= end - 3:
                        decoded = decoder(data, offset, size, min_len=3, max_len=12000)
                        if not decoded:
                            offset += 1
                            continue
                        text, text_start, length, padded_end, encoding = decoded
                        text = text.strip().replace("\\n", " ").replace("\\r", " ")
                        if raw_overlaps_taken(text_start, text_start + length):
                            offset += 1
                            continue
                        if text not in seen_main and stable_packed_naninovel_text(text):
                            seen_main.add(text)
                            occupied.append((text_start, text_start + length))
                            yield Entry(
                                source_text=text,
                                file_path=rel,
                                context=f"{backend_name}@0x{text_start:x}",
                                object_info="targeted_naninovel_packed_string",
                                import_method="naninovel_blob_string",
                                safety="conditional",
                                locator={"offset": text_start, "length": length, "encoding": encoding, "length_offset": offset, "packed_format": backend_name},
                                backend=backend_name,
                                review_only=False,
                            ).finalize()
                            offset = max(offset + 1, min(padded_end, end))
                        else:
                            # Khong bo mat text nghi ngo; day sang raw_candidates.csv neu giong thoai.
                            # Nhung khong dua vao translation.csv balanced de tranh rac packed sai offset.
                            tier = raw_review_tier(text)
                            if tier >= 2 and text not in seen_review and text not in seen_main:
                                seen_review.add(text)
                                yield Entry(
                                    source_text=text,
                                    file_path=rel,
                                    context=f"{backend_name}Candidate@0x{text_start:x}",
                                    object_info="targeted_naninovel_packed_candidate",
                                    import_method="naninovel_raw_candidate",
                                    safety="unsafe",
                                    locator={"offset": text_start, "length": length, "encoding": encoding, "length_offset": offset, "packed_format": backend_name},
                                    backend=f"{backend_name}_candidate",
                                    review_only=True,
                                ).finalize()
                            offset += 1

            occupied = merge_ranges(occupied)

            def overlaps_taken(a: int, b: int) -> bool:
                # occupied da sort; list thuong khong qua lon nen linear duoc.
                for x, y in occupied:
                    if b <= x:
                        return False
                    if a < y and b > x:
                        return True
                return False

            # Fallback soi thieu: chi review_only. Khong dua vao translation.csv mac dinh.
            for start, end in merge_ranges(windows):
                chunk = data[start:end]
                for match in ASCII_WINDOW_TEXT.finditer(chunk):
                    abs_start = start + match.start()
                    abs_end = start + match.end()
                    if overlaps_taken(abs_start, abs_end):
                        continue
                    raw = match.group(0)
                    try:
                        text = raw.decode("utf-8")
                    except UnicodeDecodeError:
                        continue
                    text = text.strip().replace("\\n", " ").replace("\\r", " ")
                    for piece_index, piece_text in enumerate(split_naninovel_raw_fragments(text)):
                        repaired = repair_known_ui_raw_fragment(piece_text, abs_start)
                        if repaired:
                            fixed_text, fixed_locator = repaired
                            if fixed_text not in seen_main:
                                seen_main.add(fixed_text)
                                yield Entry(
                                    source_text=fixed_text,
                                    file_path=rel,
                                    context=f"UnityUIRepairedRaw@0x{fixed_locator.get('offset', abs_start):x}",
                                    object_info="unity_ui_repaired_age_gate",
                                    import_method="raw_fixed_slot",
                                    safety="conditional_fit",
                                    locator=fixed_locator,
                                    backend="unity_ui_repaired_raw",
                                    review_only=False,
                                ).finalize()
                            continue
                        if piece_text in seen_review or piece_text in seen_main:
                            continue
                        bucket = naninovel_raw_bucket(piece_text, extract_level)
                        if bucket == "skip":
                            continue
                        if bucket == "main":
                            seen_main.add(piece_text)
                        else:
                            seen_review.add(piece_text)
                        as_main = bucket == "main"
                        is_candidate = bucket == "candidate"
                        yield Entry(
                            source_text=piece_text,
                            file_path=rel,
                            context=f"NaninovelReviewRaw@0x{abs_start:x}" + (f"#part{piece_index}" if piece_index else ""),
                            object_info=f"targeted_naninovel_raw_{extract_level}_{bucket}",
                            import_method="naninovel_raw_candidate" if (as_main or is_candidate) else "raw_review_only",
                            safety="unsafe",
                            locator={"offset": abs_start, "length": len(raw), "encoding": "utf-8", "raw_piece": piece_index, "raw_original": text if piece_text != text else None},
                            backend=f"naninovel_raw_{extract_level}_{bucket}",
                            review_only=not as_main,
                        ).finalize()


def iter_naninovel_display_texts(text: str):
    """Lay phan chu hien thi tu lenh Naninovel @choice/@print, khong bo ca dong @."""
    stripped = str(text or "").strip()
    if not stripped:
        return
    pick = _RANDPICK_RE.search(stripped)
    if pick:
        for part in pick.group(1).split("@"):
            part = part.strip()
            if part:
                yield part
        return
    if not stripped.startswith("@"):
        yield stripped
        return
    match = _NANINOVEL_TEXT_CMD_RE.match(stripped)
    if not match:
        return
    rest = str(match.group("rest") or "").strip()
    named = [item.strip() for item in _NANINOVEL_NAMED_TEXT_RE.findall(rest) if item.strip()]
    if named:
        yield from named
        return
    cmd = str(match.group("cmd") or "").lower()
    if cmd in {"choice", "print", ":"} and rest:
        positional = re.split(r"\s+[A-Za-z_][A-Za-z0-9_]*:", rest, maxsplit=1)[0].strip().strip('"')
        if positional:
            yield positional


def _replace_text_in_naninovel_command(command: str, source: str, translated: str) -> str:
    if not command or not source or source == translated:
        return command
    quoted_old = f'"{source}"'
    if quoted_old in command:
        return command.replace(quoted_old, f'"{translated}"', 1)
    pattern = re.compile(
        r"(^@(?:choice|print|:)\s+)(" + re.escape(source) + r")(\s|$)",
        re.I,
    )
    updated, count = pattern.subn(
        lambda m: m.group(1) + translated + m.group(3),
        command,
        count=1,
    )
    return updated if count else command


def _scan_script_object_strings(raw: bytes):
    from vntext.extract_unity import _scan_unity_length_prefixed_strings
    if len(raw) <= 512 * 1024:
        return _scan_unity_length_prefixed_strings(raw, step=4, seeded=False)
    return _scan_unity_length_prefixed_strings(raw, step=4, seeded=True)


def collect_naninovel_script_path_ids(objects) -> set[int]:
    """MonoScript path_ids whose class is Naninovel Script. Cheap; does not walk MonoBehaviours."""
    pids: set[int] = set()
    for obj in objects:
        type_name = str(getattr(getattr(obj, "type", None), "name", "") or "")
        if type_name != "MonoScript":
            continue
        try:
            data = obj.read()
            class_name = str(getattr(data, "m_ClassName", "") or "")
        except Exception:
            continue
        if class_name != "Script":
            continue
        try:
            pids.add(int(obj.path_id))
        except Exception:
            continue
    return pids


def collect_ui_script_path_ids(objects) -> dict[int, str]:
    """MonoScript path_ids for Unity/TMP Text. Used when the file has no TypeTree."""
    pids: dict[int, str] = {}
    for obj in objects:
        type_name = str(getattr(getattr(obj, "type", None), "name", "") or "")
        if type_name != "MonoScript":
            continue
        try:
            data = obj.read()
            class_name = str(getattr(data, "m_ClassName", "") or "")
        except Exception:
            continue
        if class_name not in UI_MONO_CLASSES:
            continue
        try:
            pids[int(obj.path_id)] = class_name
        except Exception:
            continue
    return pids


def _object_byte_size(obj) -> int:
    try:
        return int(getattr(obj, "byte_size", 0) or 0)
    except Exception:
        return 0


def _object_raw_bytes(obj) -> bytes:
    """Prefer in-memory patched payload; UnityPy get_raw_data() still reads the original file."""
    blob = getattr(obj, "data", None)
    if blob is not None:
        return bytes(blob)
    try:
        return bytes(obj.get_raw_data())
    except Exception:
        return b""


def _raw_looks_like_naninovel_script(obj) -> bool:
    """Cheap reject for UI MonoBehaviours before parse_monobehaviour_head."""
    if _object_byte_size(obj) < MIN_NANINOVEL_SCRIPT_OBJECT_BYTES:
        return False
    raw = _object_raw_bytes(obj)
    if not raw:
        return False
    return any(token in raw for token in NANINOVEL_SCRIPT_RAW_HINTS)


def _mono_script_path_id(obj) -> int:
    """Read m_Script path_id without deref'ing the MonoScript object."""
    try:
        head = obj.parse_monobehaviour_head()
        script_ptr = getattr(head, "m_Script", None)
        return int(getattr(script_ptr, "path_id", 0) or 0)
    except Exception:
        return 0


def collect_naninovel_choice_displays_from_bytes(data: bytes) -> set[str]:
    """Collect @choice display labels from raw Unity/Naninovel bytes (ASCII/UTF-8).

    Choice text is often stored both as a full `@choice \"Label\" ...` command and as a
    bare string field in another Script object. File-level collection lets us tag the
    bare field as player-facing without overfitting to one game.
    """
    out: set[str] = set()
    if not data:
        return out
    for match in _NANINOVEL_CHOICE_QUOTED_RE.finditer(data):
        raw = match.group(1)
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            try:
                text = raw.decode("latin-1")
            except UnicodeDecodeError:
                continue
        text = text.replace('\\"', '"').strip()
        if not text or any(ord(ch) < 32 for ch in text):
            continue
        if text:
            out.add(text)
            for part in iter_naninovel_display_texts(f'@choice "{text}"'):
                if part and not any(ord(ch) < 32 for ch in part):
                    out.add(part)
    return out


def collect_naninovel_choice_displays_from_path(path) -> set[str]:
    """Scan a Unity resource for choice labels without materialising the file.

    Large ``data.unity3d`` files can be hundreds of megabytes.  The choice
    labels are only a classification hint for already identified Script
    objects, so map the file read-only instead of calling ``Path.read_bytes``
    and creating a second full-size allocation.  A failed optional hint scan
    must never abort the object extractor; callers still extract all objects
    using their own locators.
    """
    try:
        with path.open("rb") as stream:
            if stream.seek(0, 2) <= 0:
                return set()
            stream.seek(0)
            with mmap.mmap(stream.fileno(), 0, access=mmap.ACCESS_READ) as data:
                return collect_naninovel_choice_displays_from_bytes(data)
    except (OSError, ValueError, MemoryError):
        return set()


def _naninovel_command_role(raw_text: str) -> str:
    """Role of a Naninovel command line: choice | print | other."""
    stripped = str(raw_text or "").strip()
    match = _NANINOVEL_TEXT_CMD_RE.match(stripped)
    if not match:
        return "other"
    cmd = str(match.group("cmd") or "").lower()
    if cmd == "choice":
        return "choice"
    if cmd in {"print", ":"}:
        return "print"
    return "other"


def naninovel_script_display_candidate(text: str, choice_displays: set[str] | None = None) -> bool:
    """Accept a real display string from a recognized Naninovel Script object.

    Script objects are already identified from their MonoScript class, so their
    aligned strings are safer than arbitrary raw-file scans.  The old main-text
    sentence gate still dropped short stage directions such as ``*Slight noise*``
    and short localized labels.  Keep the hard binary/code/config rejects, then
    allow those display-shaped strings through so EN and localized builds have
    the same patchable row set.
    """
    from vntext.extract_quality import _clean_inline_text, has_binary_garbage, has_vietnamese_chars, is_ui_label_text, looks_like_code_or_asset_token, looks_like_demo_or_placeholder
    cleaned = _clean_inline_text(text)
    if not cleaned or len(cleaned) > 280:
        return False
    if has_binary_garbage(cleaned) or looks_like_demo_or_placeholder(cleaned):
        return False
    if looks_like_code_or_asset_token(cleaned):
        return False
    lowered = cleaned.lower()
    if lowered in _NANINOVEL_SCRIPT_TECH_EXACT:
        return False
    if any(word in lowered for word in _NANINOVEL_SCRIPT_TECH_WORDS):
        return False
    if lowered.endswith(".commands") or lowered.endswith(".runtime"):
        return False
    if GUID_RE.fullmatch(cleaned) or HEX_RE.fullmatch(cleaned):
        return False
    if _NANINOVEL_SCRIPT_TECH_RE.fullmatch(cleaned):
        return False
    if cleaned.startswith(("@", "//", ";", "#")) and cleaned not in (choice_displays or set()):
        return False
    if cleaned in (choice_displays or set()):
        return True
    if has_vietnamese_chars(cleaned) or is_ui_label_text(cleaned):
        return True
    if _NANINOVEL_STAGE_ONLY_RE.fullmatch(cleaned):
        inner = cleaned[1:-1].strip()
        return any(ch.isalpha() for ch in inner) and not any(
            word in inner.lower() for word in _NANINOVEL_SCRIPT_TECH_WORDS
        )
    letters = sum(ch.isalpha() for ch in cleaned)
    visible = sum(not ch.isspace() for ch in cleaned)
    if letters < 2 or visible == 0:
        return False
    if (visible - letters) / visible > 0.55:
        return False
    # A no-space token without punctuation is normally an asset/identifier;
    # labels and known short dialogue are handled above.
    if " " not in cleaned and not any(mark in cleaned for mark in ".!?,:;…♡♥"):
        return False
    return True


def iter_naninovel_script_entries(
    obj,
    rel: str,
    path_id,
    object_info: str,
    file_choice_displays: set[str] | None = None,
):
    from vntext.extract_quality import looks_like_code_or_asset_token
    from vntext.patchability import NANINOVEL_PATCH_PROOF
    raw = _object_raw_bytes(obj)
    if not raw:
        return
    scanned = list(_scan_script_object_strings(raw))
    # Collect display strings that appear inside @choice so bare field copies
    # of the same label are classified as player choices, not script ids.
    choice_displays: set[str] = set(file_choice_displays or ())
    for scan_index, item in enumerate(scanned):
        text = str(item.get("text", "")).strip()
        if not text or _naninovel_command_role(text) != "choice":
            continue
        for display in iter_naninovel_display_texts(text):
            if display:
                choice_displays.add(display)

    seen = set()
    for scan_index, item in enumerate(scanned):
        raw_text = str(item.get("text", ""))
        text = raw_text.strip()
        if not text:
            continue
        candidates = list(iter_naninovel_display_texts(text))
        if not candidates:
            continue
        cmd_role = _naninovel_command_role(text)
        for display_index, display in enumerate(candidates):
            if not display or display in seen:
                continue
            if looks_like_code_or_asset_token(display):
                continue
            if display.lstrip().startswith("@") and display == text:
                continue
            if not naninovel_script_display_candidate(display, choice_displays):
                continue
            role = cmd_role if cmd_role in {"choice", "print"} else (
                "choice" if display in choice_displays else "plain"
            )
            seen.add(display)
            ctx = f"NaninovelScript:{path_id}"
            if role in {"choice", "print"}:
                ctx = f"{ctx}:{role}"
            import_method = (
                "naninovel_choice" if role == "choice"
                else ("naninovel_print" if role == "print" else "naninovel_script_string")
            )
            locator = {
                "path_id": str(path_id),
                # The object path_id identifies the script, while this ordinal
                # identifies the string inside that script.  It remains stable
                # when the same script is compared across EN/VH builds even
                # though translated byte offsets and key hashes change.
                "scan_index": scan_index,
                "display_index": display_index,
                "encoding": "utf-8",
                "command_text": text if text.lstrip().startswith("@") else None,
                "display_role": role,
            }
            yield Entry(
                source_text=display,
                file_path=rel,
                context=ctx,
                object_info=f"{object_info}:Script",
                import_method=import_method,
                safety="safe",
                locator=locator,
                backend="naninovel_script_object",
                patch_proof=dict(NANINOVEL_PATCH_PROOF),
            ).finalize()

__all__ = ['plausible_text', 'rel_path', 'iter_files', 'should_raw_scan', 'should_naninovel_scan', 'decode_candidate', 'naninovel_candidate_text', 'text_noise_score', 'looks_like_cut_fragment', 'likely_main_raw_text', '_word_stats_for_raw', '_strip_raw_tail_noise', 'split_naninovel_raw_fragments', 'raw_review_tier', 'naninovel_raw_bucket', 'decode_candidate_parts', 'merge_ranges', 'repair_known_ui_raw_fragment', 'scan_naninovel_blob', 'iter_naninovel_display_texts', '_replace_text_in_naninovel_command', '_scan_script_object_strings', 'collect_naninovel_script_path_ids', 'collect_ui_script_path_ids', '_object_byte_size', '_object_raw_bytes', '_raw_looks_like_naninovel_script', '_mono_script_path_id', 'collect_naninovel_choice_displays_from_bytes', 'collect_naninovel_choice_displays_from_path', '_naninovel_command_role', 'naninovel_script_display_candidate', 'iter_naninovel_script_entries']
