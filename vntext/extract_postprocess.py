"""Postprocess extraction family.

Function bodies are mechanically preserved from the former monolithic vntext.extract module.
"""

from __future__ import annotations

from vntext.extract_constants import (
    DEFAULT_EXTRACT_STEP_TIMEOUT,
    RAW_LOWER_DIALOGUE_WORDS,
    UI_SHORT_TEXT,
    concurrent,
    make_key,
    re,
    time,
)



def dedupe(entries):
    out = {}
    for entry in entries:
        key = (entry.file_path, entry.source_text, entry.import_method)
        if key in out:
            out[key].duplicate_locations.append(entry.locator)
        else:
            out[key] = entry
    return list(out.values())


def _raw_short_dialogue_word_ok(token: str) -> bool:
    token = token.lower().strip("'’")
    if not token:
        return False
    if token in RAW_LOWER_DIALOGUE_WORDS:
        return True
    # Cho phep keo dai chu cai trong tieng keu: ahhh, ughhh, oooh, eeeek...
    patterns = (
        r"a+h+", r"e+h+", r"o+h+", r"o+o+h+", r"u+g+h+", r"h+a+",
        r"h+e+h+e+", r"u+m+", r"m+h+", r"m+m+", r"e+e+k+", r"o+u+c+h+",
        r"k+y+a+", r"k+k+y+a+", r"y+e+s+", r"y+e+a+h+", r"n+o+", r"s+o+r+r+y+",
    )
    return any(re.fullmatch(pat, token) for pat in patterns)


def _looks_like_corrupt_raw_short(text: str, backend: str = "") -> bool:
    """Loc cac raw short fragment hay sinh do scan lech offset: oolice!, oocket., Pll go!, v.v.

    Chi ap dung cho backend raw candidate/main. TextAsset/typetree khong bi demote.
    """
    from vntext.extract_quality import _clean_inline_text
    if not backend.startswith("naninovel_raw_"):
        return False
    cleaned = _clean_inline_text(text)
    if not cleaned:
        return True
    if len(cleaned) > 32:
        return False
    # Dung cho cac cau co dau cau ngan.
    words = re.findall(r"[A-Za-z']+", cleaned)
    if not words:
        return False
    alpha = re.sub(r"[^A-Za-z']", "", cleaned)
    token0 = words[0]
    token0_l = token0.lower().strip("'’")

    # Mot token viet thuong khong nam trong whitelist thuong la bi cat mat chu dau: oolice!, oocean., oocket.
    if cleaned[0].islower() and " " not in cleaned:
        return not _raw_short_dialogue_word_ok(token0_l)

    # Nhieu token nhung token dau viet thuong ky la: ohurry!, oheers!, eender!
    if cleaned[0].islower() and token0_l not in RAW_LOWER_DIALOGUE_WORDS and not _raw_short_dialogue_word_ok(token0_l):
        return True

    # Cac prefix 1 chu cai + tu ngan hay la byte rac truoc mot cau ngan: Pll go!, Fo girl?
    if re.match(r"^[A-Z][a-z]{1,2}\s+[a-z]", cleaned) and cleaned[-1] in ".!?…":
        if token0_l not in {"i", "a", "my", "no", "ok", "oh"}:
            return True

    # Dang oH./uH. la offset lech; Oh./Uh. hop le phai viet hoa chu dau va chu sau thuong.
    if re.fullmatch(r"[a-z][A-Z][.!?…]*", cleaned):
        return True

    # Chu in hoa random 2-4 token ngan khong phai UI/thoai ro rang: SALA NIEK NOS!
    if cleaned.isupper() and len(words) >= 2 and cleaned.lower() not in UI_SHORT_TEXT:
        if not any(w in {"HEY", "HELP", "STOP", "NO", "YES", "OK", "NEW", "LOAD", "SAVE", "SKIP", "AUTO"} for w in words):
            return True

    return False


def _force_candidate(entry: Entry) -> Entry:
    entry.review_only = True
    entry.safety = "unsafe"
    if entry.import_method == "naninovel_blob_string":
        entry.import_method = "naninovel_raw_candidate"
    if not entry.backend.endswith("_candidate") and entry.backend in {"naninovel_7bit_string_scan", "naninovel_msgpack_string_scan"}:
        entry.backend = f"{entry.backend}_candidate"
    return entry


def _main_raw_safe_enough(text: str, backend: str = "") -> bool:
    from vntext.extract_naninovel import _strip_raw_tail_noise
    from vntext.extract_quality import _clean_inline_text, dialogue_word_signal, has_binary_garbage, has_vietnamese_chars, looks_like_code_or_asset_token, looks_like_demo_or_placeholder, short_dialogue_fragment_ok
    raw_cleaned = _clean_inline_text(text)
    cleaned = _strip_raw_tail_noise(raw_cleaned)
    if not cleaned:
        return False
    # Neu packed scanner phai cat duoi moi trong sach, de vao raw_candidates thay vi translation.csv.
    if backend in {"naninovel_7bit_string_scan", "naninovel_msgpack_string_scan"} and cleaned != raw_cleaned:
        return False
    lowered = cleaned.lower()
    if _looks_like_corrupt_raw_short(cleaned, backend):
        return False
    if _looks_like_fused_prefix_word(cleaned):
        return False
    if ("{" in cleaned or "}" in cleaned) and not re.search(r"\{[A-Za-z0-9_]+\}", cleaned):
        return False
    if has_vietnamese_chars(cleaned):
        return True
    if any(ch in cleaned for ch in "&\\"):
        return False
    if re.search(r"\b[a-z]+[A-Z][A-Za-z]*", cleaned):
        return False
    if short_dialogue_fragment_ok(cleaned):
        return True
    if lowered in UI_SHORT_TEXT:
        return True
    if has_binary_garbage(cleaned) or looks_like_code_or_asset_token(cleaned) or looks_like_demo_or_placeholder(cleaned):
        return False
    if cleaned[0].islower():
        return False
    if cleaned.endswith("'") and not cleaned.startswith(("'", "\"", "“", "‘")):
        return False
    if re.search(r"[a-z]{2,}[A-Z][A-Za-z]", cleaned):
        return False
    words = re.findall(r"[A-Za-z']+", cleaned)
    long_words = [w for w in words if len(w.strip("'’")) >= 3]
    has_space = " " in cleaned
    has_mark = any(mark in cleaned for mark in ".!?,:;…♡♥")
    ends_clean = cleaned[-1] in '.!?…♡♥)”"]}>'
    # No-space single words like pleasure./ussy./wrinces. are raw fragments, not translation main.
    if not has_space and lowered not in UI_SHORT_TEXT:
        return False
    # Packed 7bit/msgpack is noisy; keep only clearly complete short UI/dialogue.
    if backend in {"naninovel_7bit_string_scan", "naninovel_msgpack_string_scan"}:
        if not ends_clean:
            return False
        if len(cleaned) > 48 and not (has_mark and len(long_words) >= 4):
            return False
    if not ends_clean and len(cleaned) < 96:
        return False
    if has_mark and len(words) >= 2 and dialogue_word_signal(cleaned):
        return True
    if has_mark and len(long_words) >= 4:
        return True
    return False


def rebalance_main_review(entries):
    """Demote raw/packed false-positive khoi translation.csv.

    translation.csv chi nen la text dich chinh. Raw nghi ngo van giu trong
    raw_candidates.csv qua review_only=True + import_method naninovel_raw_candidate.
    """
    out = []
    for entry in entries:
        if not entry.review_only and entry.backend in {"naninovel_7bit_string_scan", "naninovel_msgpack_string_scan", "naninovel_raw_balanced_main"}:
            if not _main_raw_safe_enough(entry.source_text, entry.backend):
                out.append(_force_candidate(entry))
                continue
        if not entry.review_only and entry.import_method == "naninovel_raw_candidate":
            if not _main_raw_safe_enough(entry.source_text, entry.backend):
                out.append(_force_candidate(entry))
                continue
        out.append(entry)
    return out


def _looks_like_fused_prefix_word(cleaned: str) -> bool:
    """Bat loi raw sai offset: EWhile, POf, BEo, XpAh, v.v."""
    words = re.findall(r"[A-Za-z']+", cleaned)
    if not words:
        return False
    first = words[0].strip("'’")
    if len(first) >= 3 and re.match(r"^[A-Z][A-Z][a-z]", first):
        return True
    if len(first) >= 5 and re.match(r"^[A-Z][a-z]", first):
        tail = first[1:].lower()
        common_starts = {
            "while", "where", "what", "when", "why", "how", "the", "this",
            "that", "there", "then", "they", "she", "he", "you", "your", "can",
            "could", "would", "should", "okay", "please", "sorry", "thanks", "thank",
            "after", "before", "again", "because", "someone", "every", "hello", "hino",
        }
        if tail in common_starts:
            return True
    return False


def _raw_candidate_csv_worthy(text: str) -> bool:
    """Giu raw_candidates.csv gon: chi giu ung vien co kha nang la text that.

    Muc tieu cua file nay la soi thieu, khong phai dump moi offset raw. Nen cac
    substring cat lech byte, control char, code/config, path, token mot-tu bi loai.
    """
    from vntext.extract_naninovel import _strip_raw_tail_noise, _word_stats_for_raw
    from vntext.extract_quality import _clean_inline_text, has_binary_garbage, has_vietnamese_chars, looks_like_code_or_asset_token, looks_like_demo_or_placeholder, raw_has_stray_control_or_binary, short_dialogue_fragment_ok
    cleaned = _strip_raw_tail_noise(_clean_inline_text(text))
    if ((len(cleaned) < 2 and not has_vietnamese_chars(cleaned)) or len(cleaned) > 280):
        return False
    if has_binary_garbage(cleaned):
        return False
    if looks_like_demo_or_placeholder(cleaned) or looks_like_code_or_asset_token(cleaned):
        return False
    if has_vietnamese_chars(cleaned):
        return True
    if raw_has_stray_control_or_binary(cleaned):
        return False
    lowered = cleaned.lower()
    hard_junk = (
        "contain(", "pick2(", "select2", "tempupskill", "radialblur",
        "mtrait", "mkeyword", "mcondition", "mname=", "hash=", "guid",
        "random(", "visit=random", "=false", "=true", "==", "!=",
        "resources/", "images/", "audio/", "sprite", "shader", "prefab",
        "appendlinebreak", "startgameversion", "localidentifierinfile",
    )
    if any(tok in lowered for tok in hard_junk):
        return False
    if any(ch in cleaned for ch in "`|^~"):
        return False
    if re.search(r"[A-Za-z][@$][A-Za-z]", cleaned):
        return False
    if re.search(r"[A-Za-z]{1,3}\d|\d[A-Za-z]{1,3}", cleaned) and len(cleaned) < 40:
        return False
    if re.search(r"[a-z]{2,}[A-Z][A-Za-z]", cleaned):
        return False
    if _looks_like_fused_prefix_word(cleaned):
        return False

    visible, letters, digits, symbols, words, long_words = _word_stats_for_raw(cleaned)
    if visible == 0 or letters / visible < 0.55:
        return False
    if symbols / visible > 0.32 and not any(mark in cleaned for mark in "♡♥…"):
        return False

    if short_dialogue_fragment_ok(cleaned):
        return True

    if cleaned[0].islower():
        # Lowercase raw gan nhu luon la substring giua cau. Chi giu khi no dai, co ket cau,
        # va word dau khong phai manh 1-3 ky tu bi cat mat chu dau.
        first = words[0].lower().strip("'’") if words else ""
        if len(first) < 4:
            return False
        return len(long_words) >= 5 and " " in cleaned and cleaned[-1] in ".!?…♡♥)'\"]}>"

    if " " not in cleaned and lowered not in UI_SHORT_TEXT:
        return False

    # Prefix 1 chu + cau ngan = offset bi lech: Pll go!, Fo girl?, Qal mer!
    if words:
        first = words[0].strip("'’")
        if len(first) == 1 and first not in {"I", "A"}:
            return False
        if re.match(r"^[A-Z][a-z]{1,2}\s+[a-z]", cleaned) and cleaned[-1] in ".!?…":
            return False

    has_mark = any(mark in cleaned for mark in ".!?,:;…♡♥")
    ends_punct = cleaned[-1] in ".!?…♡♥)'\"]}>"
    if len(long_words) >= 4:
        return True
    if len(long_words) >= 2 and (has_mark or ends_punct):
        return True
    if len(words) >= 3 and len(cleaned) >= 16 and cleaned[0].isupper():
        return True
    return False


def compact_raw_candidate_entries(entries):
    """Loc + gom raw_candidates sau khi scan de khong phinh hang chuc nghin dong rac."""
    from vntext.extract_naninovel import _strip_raw_tail_noise
    from vntext.extract_quality import _clean_inline_text
    normal_entries = []
    raw_candidates = []
    for entry in entries:
        if entry.review_only and entry.import_method == "naninovel_raw_candidate":
            if _raw_candidate_csv_worthy(entry.source_text):
                # Cat duoi byte rac neu filter da xac dinh phan dau la text tot.
                cleaned = _strip_raw_tail_noise(_clean_inline_text(entry.source_text))
                if cleaned != entry.source_text:
                    entry.source_text = cleaned
                    entry.key = make_key(entry.file_path, entry.context, entry.source_text, entry.import_method)
                raw_candidates.append(entry)
            continue
        normal_entries.append(entry)

    # Bo substring cua candidate dai hon. Raw scan hay sinh chuoi truot theo tung byte;
    # chi giu ban dai hon.
    raw_candidates.sort(key=lambda e: (-len(_clean_inline_text(e.source_text)), e.file_path, e.context))
    accepted = []
    accepted_norms = []
    for entry in raw_candidates:
        norm = _clean_inline_text(entry.source_text).lower()
        if any(norm in old and len(old) - len(norm) >= 5 for old in accepted_norms):
            continue
        accepted.append(entry)
        accepted_norms.append(norm)

    # Giu thu tu doc de report/CSV de so hon.
    accepted.sort(key=lambda e: (e.file_path, e.context, e.source_text))
    return normal_entries + accepted


def drop_duplicate_ui_raw_entries(entries):
    from vntext.extract_quality import _clean_inline_text
    safe_texts = {
        _clean_inline_text(e.source_text).lower()
        for e in entries
        if not e.review_only and e.backend not in {"unity_ui_length_prefixed_scan", "unity_ui_utf16_scan"}
    }
    out = []
    for entry in entries:
        if entry.backend in {"unity_ui_length_prefixed_scan", "unity_ui_utf16_scan"}:
            if _clean_inline_text(entry.source_text).lower() in safe_texts:
                continue
        out.append(entry)
    return out


def drop_raw_covered_by_script(entries):
    """Prefer patchable Script object rows over blob/raw offsets of the same line."""
    script_keys = {
        (str(entry.file_path or "").replace("\\", "/").lower(), entry.source_text)
        for entry in entries
        if entry.import_method == "naninovel_script_string" and not entry.review_only
    }
    if not script_keys:
        return entries
    raw_methods = {
        "naninovel_blob_string",
        "naninovel_raw_candidate",
        "raw_fixed_slot",
        "raw_review_only",
    }
    out = []
    for entry in entries:
        if entry.import_method in raw_methods:
            key = (str(entry.file_path or "").replace("\\", "/").lower(), entry.source_text)
            if key in script_keys:
                continue
        out.append(entry)
    return out


def postprocess_extracted_entries(entries):
    return compact_raw_candidate_entries(
        rebalance_main_review(
            drop_raw_covered_by_script(drop_duplicate_ui_raw_entries(entries))
        )
    )


def _extract_step_timeout(step: str, size: int) -> float:
    if step == "unity_typetree":
        return max(120.0, min(DEFAULT_EXTRACT_STEP_TIMEOUT, (size / (10 * 1024 * 1024)) * 15 + 60))
    if step == "naninovel_scan":
        return max(90.0, min(DEFAULT_EXTRACT_STEP_TIMEOUT, (size / (50 * 1024 * 1024)) * 90 + 30))
    if step == "unity_ui_blob":
        return min(300.0, DEFAULT_EXTRACT_STEP_TIMEOUT)
    if step == "raw_scan":
        return min(180.0, DEFAULT_EXTRACT_STEP_TIMEOUT)
    return min(120.0, DEFAULT_EXTRACT_STEP_TIMEOUT)


def _run_extract_step(
    step: str,
    factory: Callable[[], Iterable[Any]],
    timeout: float,
) -> tuple[list[Any], float, str | None]:
    """Run an extract sub-step in a worker thread; timeout returns err='timeout'."""
    t0 = time.time()
    bucket: list[Any] = []
    err_holder: list[BaseException] = []

    def work() -> None:
        try:
            bucket.extend(factory())
        except BaseException as exc:
            err_holder.append(exc)

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        fut = pool.submit(work)
        try:
            fut.result(timeout=timeout)
        except concurrent.futures.TimeoutError:
            return [], time.time() - t0, "timeout"
    if err_holder:
        return [], time.time() - t0, str(err_holder[0])
    return bucket, time.time() - t0, None

__all__ = ['dedupe', '_raw_short_dialogue_word_ok', '_looks_like_corrupt_raw_short', '_force_candidate', '_main_raw_safe_enough', 'rebalance_main_review', '_looks_like_fused_prefix_word', '_raw_candidate_csv_worthy', 'compact_raw_candidate_entries', 'drop_duplicate_ui_raw_entries', 'drop_raw_covered_by_script', 'postprocess_extracted_entries', '_extract_step_timeout', '_run_extract_step']
