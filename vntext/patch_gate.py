"""Patch eligibility gate — read-only audit; never mutates translation.csv."""
from __future__ import annotations

import csv
import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

from vntext import mt_check
from vntext.mt_translation_safety import validate_candidate
from vntext.mt_check import is_synonym_row, load_whitelist, structural_problems
from vntext.package_io import read_translation_rows

REASON_LABELS_VI: dict[str, str] = {
    "eligible": "Sẽ patch",
    "review_only": "Trong review_only.csv (cần xem lại thủ công)",
    "no_translation": "Chưa có bản dịch trong translation.csv",
    "garbage_repetition": "Rác lặp từ/ký tự",
    "html_garbage": "HTML/entity rác",
    "synonym_manual": "Dòng synonym — dịch thủ công",
    "placeholder mismatch": "Mất/sai placeholder {…}",
    "tag mismatch": "Hỏng tag <…>",
    "synonym prefix mismatch": "Synonym sai tiền tố",
    "synonym variant count": "Synonym sai số biến thể",
    "literal newline count": "Sai số \\n",
    "heart glyph count": "Sai số ký hiệu ♡",
    "RandPick variant count": "Sai số biến thể RandPick",
    "english suffix after placeholder": "Hậu tố Anh sau placeholder",
    "validation": "Validation MT",
    "legacy_profile_unsupported": "Gói dùng profile legacy không được hỗ trợ; hãy extract lại",
    "legacy_external_reference": "Locator tham chiếu ngoài không được hỗ trợ; hãy extract lại",
    "retranslate_blocked": "Dịch lại vẫn bị chặn",
}

RETRANSLATE_STILL_BLOCKED_NOTE = "Dịch lại vẫn bị chặn"


def load_review_only_keys(package_dir: Path) -> set[str]:
    review_path = package_dir / "review_only.csv"
    if not review_path.is_file():
        return set()
    with review_path.open(encoding="utf-8-sig", newline="") as fh:
        return {str(row.get("key") or "") for row in csv.DictReader(fh) if row.get("key")}


def entry_row(entry: dict) -> dict:
    return {
        "source_text": str(entry.get("source_text") or ""),
        "context": str(entry.get("context") or ""),
        "file_path": str(entry.get("file_path") or ""),
        "object_info": str(entry.get("object_info") or ""),
        "import_method": str(entry.get("import_method") or ""),
        "key": str(entry.get("key") or ""),
    }


def legacy_entry_reason(entry: dict) -> str:
    """Reject rows produced by removed external/profile-based compatibility paths."""

    backend = str(entry.get("backend") or "").strip().casefold()
    if backend.endswith("_slot_reference"):
        return "legacy_external_reference"
    locator = entry.get("locator")
    if isinstance(locator, dict) and any(
        str(key).casefold().startswith("recovered_from_") for key in locator
    ):
        return "legacy_external_reference"
    return ""


def legacy_manifest_reason(manifest: dict) -> str:
    """Return a fail-closed reason for packages carrying removed profile metadata."""

    for field in ("profile", "game_profile", "compatibility_profile"):
        value = manifest.get(field)
        if value not in (None, "", False, [], {}):
            return f"legacy_profile_unsupported; manifest field {field}"
    for entry in manifest.get("entries", []) or []:
        if isinstance(entry, dict) and legacy_entry_reason(entry):
            return "legacy_external_reference; manifest entry"
    return ""


def has_garbage_repetition(text: str) -> bool:
    if not text or not text.strip():
        return False
    # Bỏ thẻ TMP/HTML trước khi đếm '/' — tránh false positive trên </color>.
    plain = re.sub(r"</?[^>\s][^>]*>", "", text)
    # *GLRK* *GLRK* *GLRK* / *SQUISH*×3 — sfx có chủ đích, không phải rác CT2.
    plain = re.sub(r"(?:\*\s*[A-Za-z]{2,16}\s*\*\s*){2,}", " ", plain)
    if plain.count("/") >= 5:
        return True
    # Underscore/dash runs from CT2 — treat as garbage filler.
    if re.search(r"[_\-]{6,}", plain):
        return True
    # Dấu câu lặp dài (!!!!!!!!!! / ..........) thường là nhấn giọng có chủ
    # đích và phải được giữ theo source; chỉ coi lặp ký tự chữ/số là rác.
    if re.search(r"(?iu)([a-zà-ỹ0-9])\1{9,}", plain):
        return True
    # CT2 cũng có thể lặp dính cả một âm tiết thay vì lặp một ký tự:
    # ``unitunitunit...``.  Chỉ bắt chuỗi đủ dài để không ảnh hưởng từ hợp lệ
    # ngắn hoặc SFX bình thường.
    if len(plain) >= 32 and re.search(
        r"(?iu)([a-zà-ỹ]{2,12})\1{4,}", plain
    ):
        return True
    # CT2 chèn ♪ khi fail (kể cả 1 nốt).
    if "♪" in plain:
        return True
    # CT2 loop cụm VI điển hình.
    low = plain.casefold()
    if low.count("không có tổ cảnh") >= 2:
        return True
    if low.count("hoặc không có") >= 3:
        return True
    if low.count("bán bán") >= 1 or low.count("bán lao") >= 2:
        return True
    # Lặp cụm 4–10 token (kể cả biến thể nhẹ bị bắt bởi exact phrase).
    if re.search(r"((?:\S+\s+){3,9}\S+)(?:\s+\1){1,}", plain):
        return True
    # Lặp token >= 3 lần (a a a), không flag chỉ 1 lần lặp bình thường.
    if re.search(r"(\S{2,})(?:\s+\1){2,}", plain):
        return True
    # CT2 hay nhân đôi token rác cụ thể (không flag cặp hợp lệ như "chậm chậm").
    if re.search(
        r"(?iu)\b(khởi|đang|tiền|bán|lao|hay|đầy|tình)\b\s+\1\b",
        plain,
    ):
        return True
    # Cụm UI ngắn CT2: "vui vui lòng" / "ít ít trừ" / "dấu dấu trừ".
    if re.search(r"(?iu)\bvui\s+vui\s+lòng\b", plain):
        return True
    if re.search(r"(?iu)\bít\s+ít\s+trừ\b", plain):
        return True
    if re.search(r"(?iu)\bdấu\s+dấu\s+trừ\b", plain):
        return True
    # "hành động trên hành động trên hành động"
    if re.search(r"(?iu)(hành\s+động\s+trên\s+){2,}", plain):
        return True
    if re.search(r"(?iu)(không\s+có\s+nhiều[,\s]*){3,}", plain):
        return True
    # Lặp ký tự đơn (u u u u / ♪) — rác CT2 trên fragment ngắn.
    if re.search(r"(\S)(?:\s+\1){4,}", plain):
        return True
    # Lặp bigram (tìm thay tìm thay tìm thay) — rác CT2 điển hình.
    if re.search(r"(\S{2,}\s+\S{2,})(?:\s+\1){2,}", plain):
        return True
    if plain.count("-") >= 3 and re.search(r"-\s*\d+\s*-", plain):
        return True
    if re.match(r"^-\s*\S+\s*-\s*\d+\s*$", plain.strip()):
        return True
    if len(plain) < 40:
        return False
    tokens = re.findall(r"\S+", plain)
    if len(tokens) < 8:
        return False
    top, count = Counter(tokens).most_common(1)[0]
    if count >= 8 and count / len(tokens) > 0.35:
        return True
    return bool(re.search(r"(?:\b(\w{2,})\b)(?:\s+\1){3,}", plain, flags=re.UNICODE))


def has_intentional_echo(text: str) -> bool:
    """Câu lặp cụm ngắn có chủ đích (Hurry!×3 / oh fuck... oh fuck...), không phải rác CT2."""
    s = str(text or "").strip()
    if not s:
        return False
    # ``\b\w+\b`` is not reliable for Vietnamese combining/diacritic
    # syllables on all supported Python builds.  Use an explicit letter class
    # so a translated echo such as ``lảm nhảm lảm nhảm lảm nhảm`` is recognised
    # as the same intentional repetition as source ``BLA BLA BLA``.
    letter = r"A-Za-zÀ-ỹĐđ"
    token = rf"[{letter}]+"
    if re.search(
        rf"(?iu)(?<![{letter}])({token})(?![{letter}])(?:[\s!?.…,-♪]*\1){{2,}}",
        s,
    ):
        return True
    # Hurry! hurry! hurry! / Nhanh! Nhanh! Nhanh!
    if re.search(
        r"(?iu)\b([\w]{2,})\b(?:[\s!?.…,]*\b\1\b){2,}",
        s,
    ):
        return True
    # Cụm 2–6 từ lặp lại sau dấu ...
    if re.search(
        r"((?:\b[\w']+\b[\s,…]*){1,6})\.\.\.\s*\1",
        s,
        flags=re.IGNORECASE | re.UNICODE,
    ):
        return True
    plain = re.sub(r"</?[^>\s][^>]*>", "", s)
    phrase = rf"(?:(?:[{letter}]+)\s+){{1,5}}[{letter}]+"
    if re.search(
        rf"({phrase})(?:[\s,…]*\1){{2,}}",
        plain,
        flags=re.IGNORECASE,
    ):
        return True
    # Cụm 3–6 từ lặp ≥3 lần (panic dialogue: "can't be like this" × N).
    if re.search(
        r"((?:\b[\w']+\s+){2,5}[\w']+)(?:[\s,]*\1){2,}",
        plain,
        flags=re.IGNORECASE | re.UNICODE,
    ):
        return True
    return False


def has_html_garbage(text: str) -> bool:
    if not text or not text.strip():
        return False
    if re.search(r"(?:^|[^\w])lt\s*&\s*lt", text, re.IGNORECASE):
        return True
    if re.search(r"&\s*lt\s*;?\s*(?:&\s*lt\s*;?\s*)+", text, re.IGNORECASE):
        return True
    if "indededede" in text.lower():
        return True
    if re.search(r"(?:^|\s)#\s*#+\s*\S", text):
        return True
    # CT2 đôi khi chèn token # rác (# lục # um). Cho phép hashtag hợp lệ (#Lewd #Slut).
    if text.count("#") >= 2 and not re.search(r"&#\d", text):
        if re.sub(r"#[A-Za-z][\w]*", "", text).count("#") >= 1:
            return True
    if re.search(r"&\s*(?:lt|gt|amp|quot)\b(?![^<]*;)", text, re.IGNORECASE):
        return True
    # CT2 phá entity / mask thành "& ld & ld" hoặc "T & & &".
    if re.search(r"&\s*ld\b", text, re.IGNORECASE):
        return True
    if re.search(r"(?:&\s*){2,}&", text) or re.search(r"T\s*&\s*&", text):
        return True
    if "commentcomment" in text.casefold() or re.search(r"m{4,}comment", text, re.IGNORECASE):
        return True
    # Placeholder printf lọt ra UI khi source không có.
    # (kiểm tra kèm source ở patch_skip / is_ct2_junk)
    # Mảnh sentinel mask bị CT2 phá (GeorgeG22, 0.66G33, GGGG, g-g-g-g).
    # Không khớp Ngggghhh (tiếng rên thật).
    if re.search(
        r"[A-Za-z]\d*G\d{2,}|\dG\d+|(?<![A-Za-z])G{4,}(?![A-Za-z])|(?:^|[^A-Za-z])g(?:-g){3,}",
        text,
        re.IGNORECASE,
    ):
        return True
    # Bỏ thẻ HTML/TMPro trước, rồi mới kiểm tra so sánh / lệch <>.
    # Tránh false positive green>30% (dấu > đóng thẻ + số %).
    without_tags = re.sub(r"</?[A-Za-z][^<>]*>", " ", text)
    scrubbed = re.sub(
        r"(?u)\b[\w]+(?:\+[\w]+)*"
        r"\s*(?:<=|>=|<|>|==|!=)\s*-?\d+(?:\.\d+)?",
        " ",
        without_tags,
    )
    scrubbed = re.sub(r"<=|>=|<>|=>", "", scrubbed)
    return scrubbed.count("<") != scrubbed.count(">")


def color_inner_texts(text: str) -> list[str]:
    return re.findall(r"<color\s*=\s*[^>]+>(.*?)</color>", text or "", flags=re.IGNORECASE | re.DOTALL)


def emptied_color_content(src: str, trans: str) -> bool:
    """True nếu translation làm rỗng nội dung <color> mà source còn chữ."""
    a = color_inner_texts(src)
    b = color_inner_texts(trans)
    if len(a) != len(b):
        return False
    for sa, sb in zip(a, b):
        if sa.strip() and not sb.strip():
            return True
    return False


def is_ct2_junk_translation(src: str, trans: str) -> bool:
    """CT2 hay ra toàn bán/tiền/tìm khi fail — không chấp nhận dù đã collapse."""
    if not trans or not src:
        return False
    from vntext import mt_check

    if "♪" in trans and "♪" not in src:
        return True
    if "%s" in trans and "%s" not in src:
        return True
    if "%d" in trans and "%d" not in src:
        return True
    # CT2 hay collapse UI thành "Comment" / "Không có" / "& dạng" / rác & &.
    tstrip = trans.strip()
    sstrip = src.strip()
    if tstrip in {"Comment", "Theo:", "(inin)", "Không có", "& dạng", "Name", "(ininin)"} and sstrip.casefold() not in {
        "comment",
        "theo:",
        "(inin)",
        "none",
        "n/a",
        "không có",
        "name",
    }:
        return True
    if tstrip == "& dạng" or (tstrip.startswith("& ") and "dạng" in tstrip):
        return True
    if re.search(r"T\s*&\s*&", trans) or re.search(r"&\s*&\s*&", trans):
        return True
    if re.search(r"D{4,}", trans):  # DIIIIII từ DICE ROLL bị vỡ
        return True
    if "đồng thoảng" in trans.casefold():
        return True
    # CT2 hay biến Awww/Ewww thành URL / email rác.
    # Loại SFX Awww/Ewww trước khi bắt www. (tránh false positive trên chính SFX).
    def _without_ew_aw(text: str) -> str:
        return re.sub(r"(?i)\b[ae]w{2,}w*", "SFX", text)

    trans_url = _without_ew_aw(trans)
    src_url = _without_ew_aw(src)
    if re.search(
        r"(?i)www\.|kde\.org|\.org@|[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}",
        trans_url,
    ):
        if not re.search(r"(?i)www\.|https?://|@", src_url):
            return True
    # CT2 CamelCase → "teppi82@ gmail" / "user @ mail" (space làm lệch regex email chuẩn).
    if re.search(r"(?i)@\s*gmail|teppi\d*|@\s*mail\b|/\s*vi@\s*\d+", trans) and not re.search(
        r"(?i)@|gmail|teppi", src
    ):
        return True
    if re.search(r"(?i)@\s*info\s*:|^\s*\[T\b", trans):
        return True
    if re.search(r"(?i)\blnt\b|\blnm\b|\bvini\b|\blnnm\b|\blnd\b|\bltm\b", trans):
        return True
    # CT2 hay vỡ "leaves/except" thành "trừ đi", "pervs"→"tvs", "H-Scene"→"H-Scyne".
    if "trừ đi" in trans.casefold() and "trừ đi" not in src.casefold():
        return True
    if re.search(r"(?i)\btvs\b", trans) and not re.search(r"(?i)\btvs\b", src):
        return True
    if re.search(r"(?i)h-?scyne", trans):
        return True
    if re.search(r"(?i)\bgou\b", trans) and not re.search(r"(?i)\bgou\b", src):
        return True
    # UI nhãn ngắn bị CT2 bẻ thành câu rác.
    if re.search(r"(?i)vì sao nhỏ|khốn khốn|gặp gỡ gỡ", trans):
        return True
    if re.search(r"(?iu)\bvui\s+vui(\s+lòng)?\b", trans):
        return True
    if re.search(r"(?iu)\bít\s+ít\b", trans):
        return True
    if re.search(r"(?iu)\bdấu\s+dấu(\s+trừ)?\b", trans):
        return True
    if re.search(r"(?iu)\bmặc\s+ít\b|\bcông\s+công\b|\bkhông\s+có\s+mô\b", trans):
        return True
    if re.search(r"(?i)_BAR_color|< i>", trans) and "_BAR_color" not in src and "< i>" not in src:
        return True
    # "character" (nhân vật) bị CT2 dịch thành "ký tự".
    if re.search(r"(?i)\bcharacter", src) and re.search(r"(?iu)\bký\s+tự\b", trans):
        return True
    low = trans.casefold()
    if "bán bán" in low or low.count("bán lao") >= 2:
        return True
    if "không có tổ" in low:
        return True
    if len(mt_check.WORD.findall(src)) < 3:
        return False
    tokens = re.findall(r"\S+", trans)
    if len(tokens) < 2:
        return False
    junk = sum(
        1
        for t in tokens
        if re.fullmatch(r"(?i)bán|tiền|tìm|thay|đồng|lao", t.strip(".,!?;:"))
    )
    return junk / len(tokens) >= 0.35


def reason_bucket(reason: str) -> str:
    if not reason:
        return "eligible"
    head = reason.split(";")[0].strip()
    if head.startswith("validation:"):
        return "validation"
    return head.split(" ")[0] if head.startswith("synonym variant") else head


def patch_skip_reason(
    entry: dict,
    trans: str,
    whitelist: set[str],
    *,
    allow_ct2_junk: bool = False,
) -> str:
    row = entry_row(entry)
    src = row["source_text"]
    legacy_reason = legacy_entry_reason(entry)
    if legacy_reason:
        return legacy_reason
    if str(trans or "").strip() in {"*", "..."}:
        from vntext.mt_classify import classify_row_authoritative

        action, _reason, _decision = classify_row_authoritative({**row, "translation": ""})
        if action in {"translate", "translate_synonym", "ui_label_fixed"}:
            return "symbol_only_translation"
    from vntext.mt_translation_safety import is_moan_with_tech_line

    if has_garbage_repetition(trans):
        # Cho phép giữ nguyên tiếng rên lặp / câu source vốn đã lặp có chủ đích.
        # Cho phép bản dịch echo cùng kiểu (Hurry!×3 → Nhanh!×3).
        # RandPick pools are comma-separated variants, not one intentional
        # repeated sentence.  Do not let an MT loop such as "bởi bởi bởi..."
        # pass merely because the source also contains repeated tokens.
        is_randpick_pool = mt_check.tight_commas(src) >= 2
        if (
            trans.strip() == src.strip()
            and (
                is_moan_with_tech_line(src)
                or is_sound_effect_safe(src)
                or has_garbage_repetition(src)
                or has_intentional_echo(src)
            )
        ) or (not is_randpick_pool and has_intentional_echo(src) and has_intentional_echo(trans)):
            pass
        else:
            return "garbage_repetition"
    if not allow_ct2_junk and is_ct2_junk_translation(src, trans):
        return "garbage_repetition"
    if has_html_garbage(trans):
        # Source game đôi khi lệch < > (\\n trong tag) — giữ nguyên source vẫn OK.
        if trans.strip() != src.strip():
            return "html_garbage"
    if emptied_color_content(src, trans):
        return "html_garbage"
    problems = structural_problems(row, trans)
    if problems:
        return ";".join(problems)
    reasons = validate_candidate(row, trans, whitelist)
    if reasons:
        return "validation:" + ";".join(reasons)
    return ""


def is_sound_effect_safe(src: str) -> bool:
    try:
        from vntext.mt_classify import is_sound_effect_line

        return is_sound_effect_line(src)
    except Exception:
        return False


def reason_label_vi(reason: str) -> str:
    if not reason:
        return ""
    bucket = reason_bucket(reason)
    return REASON_LABELS_VI.get(bucket, REASON_LABELS_VI.get(reason, bucket))


def translation_passes_patch_gate(
    entry: dict,
    trans: str,
    whitelist: set[str],
    *,
    allow_ct2_junk: bool = False,
) -> tuple[bool, str]:
    """True khi bản dịch đủ điều kiện patch (Patch Gate đầy đủ)."""
    if not str(trans or "").strip():
        return False, "no_translation"
    gate_entry = dict(entry)
    gate_entry.setdefault("source_text", str(entry.get("source_text") or ""))
    gate_entry.setdefault("context", str(entry.get("context") or ""))
    gate_entry.setdefault("file_path", str(entry.get("file_path") or ""))
    gate_entry.setdefault("import_method", str(entry.get("import_method") or ""))
    reason = patch_skip_reason(gate_entry, trans, whitelist, allow_ct2_junk=allow_ct2_junk)
    if reason:
        return False, reason_bucket(reason)
    return True, ""


def is_verified_cloud_repair_output(csv_path: str | Path) -> bool:
    """True only for an unmodified, successful Cloud Repair import output."""

    path = Path(csv_path).resolve()
    report_path = path.parent / ".mt" / "cloud_repair_import_report.json"
    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
        if report.get("status") != "PASS" or not report.get("merge_applied"):
            return False
        if Path(str(report.get("output_path") or "")).resolve() != path:
            return False
        expected = str(report.get("output_sha256") or "")
        result_identity = report.get("result_csv_identity") or {}
        if not expected or result_identity.get("sha256") != expected:
            return False
        return hashlib.sha256(path.read_bytes()).hexdigest() == expected
    except (OSError, TypeError, ValueError):
        return False


def load_review_only_issue_reasons(package_dir: Path) -> dict[str, str]:
    """Map key → issue code (review_only hoặc retranslate_blocked)."""
    review_path = package_dir / "review_only.csv"
    if not review_path.is_file():
        return {}
    reasons: dict[str, str] = {}
    with review_path.open(encoding="utf-8-sig", newline="") as fh:
        for row in csv.DictReader(fh):
            key = str(row.get("key") or "")
            if not key:
                continue
            note = str(row.get("patch_note") or "")
            if RETRANSLATE_STILL_BLOCKED_NOTE in note:
                reasons[key] = "retranslate_blocked"
            else:
                reasons[key] = "review_only"
    return reasons


def audit_patch_package(
    csv_path: str | Path,
    manifest_path: str | Path,
    *,
    game_root: str | Path | None = None,
) -> dict[str, Any]:
    csv_path = Path(csv_path).resolve()
    manifest_path = Path(manifest_path).resolve()
    if not csv_path.is_file():
        raise FileNotFoundError(str(csv_path))
    if not manifest_path.is_file():
        raise FileNotFoundError(str(manifest_path))

    package_dir = csv_path.parent
    manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    entries = manifest.get("entries", [])
    translations = read_translation_rows(str(csv_path))
    allow_ct2_junk = is_verified_cloud_repair_output(csv_path)
    review_keys = load_review_only_keys(package_dir)
    whitelist = load_whitelist(package_dir)
    manifest_reason = legacy_manifest_reason(manifest)
    if manifest_reason:
        bucket = manifest_reason.split(";", 1)[0]
        blocked_count = max(1, len(entries))
        label = REASON_LABELS_VI.get(bucket, bucket)
        return {
            "ok": False,
            "eligible": 0,
            "blocked": blocked_count,
            "manifest_entries": len(entries),
            "translated_rows": len(translations),
            "review_only_keys": len(review_keys),
            "reason_counts": {bucket: blocked_count},
            "reason_labels": {bucket: label},
            "samples": {
                bucket: [{
                    "key": "<manifest>",
                    "source_text": "",
                    "translation": "",
                    "reason": manifest_reason,
                }]
            },
            "summary": f"Gói bị chặn: {manifest_reason}",
            "csv_path": str(csv_path),
            "manifest_path": str(manifest_path),
        }
    blocked: Counter[str] = Counter()
    samples: dict[str, list[dict[str, str]]] = {}
    eligible = 0

    for entry in entries:
        key = str(entry.get("key") or "")
        if not key:
            continue
        if key in review_keys:
            bucket = "review_only"
            blocked[bucket] += 1
            _add_sample(samples, bucket, key, entry, "", bucket)
            continue
        if key not in translations:
            bucket = "no_translation"
            blocked[bucket] += 1
            continue
        trans = str(translations[key].get("translation") or "")
        reason = patch_skip_reason(entry, trans, whitelist, allow_ct2_junk=allow_ct2_junk)
        if reason:
            bucket = reason_bucket(reason)
            blocked[bucket] += 1
            _add_sample(samples, bucket, key, entry, trans, reason)
        else:
            eligible += 1

    blocked_total = sum(blocked.values())
    reason_lines = []
    for code, count in blocked.most_common():
        label = REASON_LABELS_VI.get(code, code)
        reason_lines.append(f"{label}: {count}")

    summary = (
        f"Kiểm tra patch — hợp lệ {eligible}, bị chặn {blocked_total} "
        f"(manifest {len(entries)} dòng, translation.csv có {len(translations)} bản dịch)"
    )
    if reason_lines:
        summary += ". " + "; ".join(reason_lines[:6])
        if len(reason_lines) > 6:
            summary += f"; … (+{len(reason_lines) - 6} nhóm)"

    return {
        "ok": eligible > 0,
        "eligible": eligible,
        "blocked": blocked_total,
        "manifest_entries": len(entries),
        "translated_rows": len(translations),
        "review_only_keys": len(review_keys),
        "reason_counts": dict(blocked),
        "reason_labels": {k: REASON_LABELS_VI.get(k, k) for k in blocked},
        "samples": samples,
        "summary": summary,
        "csv_path": str(csv_path),
        "manifest_path": str(manifest_path),
    }


def _add_sample(
    samples: dict[str, list[dict[str, str]]],
    bucket: str,
    key: str,
    entry: dict,
    trans: str,
    reason: str,
    *,
    limit: int = 3,
) -> None:
    if len(samples.get(bucket, [])) >= limit:
        return
    samples.setdefault(bucket, []).append(
        {
            "key": key,
            "source_text": str(entry.get("source_text") or "")[:120],
            "translation": trans[:120],
            "reason": reason[:160],
        }
    )


def format_preflight_log(audit: dict[str, Any]) -> str:
    lines = [audit.get("summary", "")]
    for code, count in Counter(audit.get("reason_counts", {})).most_common():
        label = audit.get("reason_labels", {}).get(code, code)
        lines.append(f"  - {label}: {count}")
        for sample in audit.get("samples", {}).get(code, [])[:2]:
            lines.append(f"      {sample['key']}: {sample.get('reason', code)}")
    return "\n".join(lines)


def main() -> int:
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="Patch preflight audit (read-only)")
    parser.add_argument("csv_path", type=Path)
    parser.add_argument("manifest_path", type=Path)
    parser.add_argument(
        "--game-root",
        type=Path,
        default=None,
        help="Optional selected game root for profile-aware policy checks",
    )
    parser.add_argument("--json", action="store_true", help="Print JSON to stdout")
    args = parser.parse_args()
    result = audit_patch_package(args.csv_path, args.manifest_path, game_root=args.game_root)
    if args.json:
        sys.stdout.write(json.dumps(result, ensure_ascii=False) + "\n")
    else:
        sys.stdout.write(format_preflight_log(result) + "\n")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
