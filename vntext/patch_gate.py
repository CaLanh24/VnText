"""Patch eligibility gate — read-only audit; never mutates translation.csv."""
from __future__ import annotations

import contextlib
import contextvars
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
    "review_only": "Không ghi được vào game: chưa tìm được vị trí ghi an toàn cho dòng này, nên Tạo patch sẽ bỏ qua (bản dịch vẫn được lưu)",
    "mt_blocked": "Máy dịch không cho ra bản dịch an toàn cho dòng này; cần tự dịch",
    "human_review": "Bản dịch máy đang chờ bạn duyệt",
    "review_resolved_unsaved": "Đã dịch — bấm Lưu để đưa dòng này vào patch",
    "existing_translation_conflict": "Game đã có bản dịch tiếng Việt khác cho câu này",
    "no_translation": "Chưa có bản dịch trong translation.csv",
    "garbage_repetition": "Rác lặp từ/ký tự",
    "html_garbage": "HTML/entity rác",
    "synonym_manual": "Dòng synonym — dịch thủ công",
    "placeholder mismatch": "Mất/sai placeholder {…}",
    "tag mismatch": "Hỏng tag <…>",
    "synonym prefix mismatch": "Synonym sai tiền tố",
    "synonym variant count": "Synonym sai số biến thể",
    "literal newline count": "Sai số \\n",
    "actual newline mismatch": "Sai xuống dòng",
    "heart glyph count": "Sai số ký hiệu ♡",
    "RandPick variant count": "Sai số biến thể RandPick",
    "english suffix after placeholder": "Hậu tố Anh sau placeholder",
    "validation": "Validation MT",
    "legacy_profile_unsupported": "Gói dùng profile legacy không được hỗ trợ; hãy extract lại",
    "legacy_external_reference": "Locator tham chiếu ngoài không được hỗ trợ; hãy extract lại",
    "retranslate_blocked": "Dịch lại vẫn bị chặn",
}

RETRANSLATE_STILL_BLOCKED_NOTE = "Dịch lại vẫn bị chặn"

# What the person can DO about each reason (Owner report 0.1.35: a status without a way out is a dead end).  Shown next to the reason in
# Sửa CSV and in the Tạo patch list; the codes are the same in both places so the two screens always count the same rows.
REASON_ACTIONS_VI: dict[str, str] = {
    "no_translation": "Dịch dòng này (tích chọn rồi 'Dịch đã chọn', hoặc gõ bản dịch) rồi bấm Lưu.",
    "mt_blocked": "Tự gõ bản dịch rồi bấm Lưu: dòng sẽ được patch. Hoặc 'Bỏ qua dòng này' nếu không cần dịch.",
    "retranslate_blocked": "Tự gõ bản dịch rồi bấm Lưu: dòng sẽ được patch. Hoặc 'Bỏ qua dòng này' nếu không cần dịch.",
    "human_review": "Bấm 'Chấp nhận đề xuất' để dùng bản dịch máy, hoặc tự sửa rồi Lưu. Hoặc 'Bỏ qua dòng này'.",
    "review_resolved_unsaved": "Bấm Lưu.",
    "review_only": "Không cần làm gì: Patch bỏ qua dòng này, game giữ nguyên câu gốc. Nếu không muốn thấy nữa, bấm 'Bỏ qua dòng này' (xóa khỏi CSV).",
    "existing_translation_conflict": "Game giữ bản dịch có sẵn. Muốn dùng bản của bạn: gỡ bản dịch có sẵn khỏi game (sao lưu trước) rồi tạo patch lại.",
    "placeholder mismatch": "Sửa bản dịch cho giữ đúng các mục {…}/[…] như câu gốc rồi Lưu.",
    "tag mismatch": "Sửa bản dịch cho giữ đúng các thẻ <…>/{…} như câu gốc rồi Lưu.",
    "garbage_repetition": "Bản dịch bị lặp rác: sửa tay hoặc 'Dịch đã chọn' lại rồi Lưu.",
    "html_garbage": "Bản dịch có mã HTML rác: sửa tay rồi Lưu.",
    "synonym_manual": "Dòng nhiều biến thể: tự dịch từng biến thể rồi Lưu.",
}
_DEFAULT_ACTION_VI = "Sửa bản dịch trong Sửa CSV cho đúng rồi bấm Lưu; hoặc 'Bỏ qua dòng này' nếu không cần dịch."


def reason_action_vi(reason: str) -> str:
    bucket = reason_bucket(reason) if reason else ""
    return REASON_ACTIONS_VI.get(bucket, REASON_ACTIONS_VI.get(reason, _DEFAULT_ACTION_VI))


# Review-ledger kinds.  review_only.csv mixes rows with no proven write route (extraction evidence) and rows the machine translator could not
# translate safely (or that wait for a human decision).  The second kind is resolved by a valid manual translation; the first never is.
RESOLVABLE_REVIEW_KINDS = frozenset({"mt_blocked", "human_review", "retranslate_blocked"})


def review_kind_for_note(note: str) -> str:
    note = str(note or "")
    if "HUMAN_REVIEW_REQUIRED" in note:
        return "human_review"
    if RETRANSLATE_STILL_BLOCKED_NOTE in note:
        return "retranslate_blocked"
    if note.startswith("MT blocked"):
        return "mt_blocked"
    return "review_only"


def load_review_kinds(package_dir: Path) -> dict[str, str]:
    """key -> review kind for every key of the review ledger (manifest review entries included)."""
    kinds = {key: "review_only" for key in load_review_only_keys(package_dir)}
    review_path = Path(package_dir) / "review_only.csv"
    if review_path.is_file():
        with review_path.open(encoding="utf-8-sig", newline="") as fh:
            for row in csv.DictReader(fh):
                key = str(row.get("key") or "")
                if key:
                    kinds[key] = review_kind_for_note(row.get("patch_note"))
    try:
        manifest = json.loads((Path(package_dir) / "manifest.json").read_text(encoding="utf-8-sig"))
        for entry in manifest.get("entries", []) or []:
            if isinstance(entry, dict) and entry.get("review_only") and entry.get("key"):
                kinds[str(entry["key"])] = "review_only"      # extraction evidence never becomes resolvable by a translation
    except (OSError, ValueError):
        pass
    return kinds


def load_review_candidates(package_dir: Path) -> dict[str, str]:
    """key -> the machine candidate waiting for a human decision (from the CT2 blocker inventory)."""
    path = Path(package_dir) / ".mt" / "blocker_inventory.json"
    try:
        rows = json.loads(path.read_text(encoding="utf-8")).get("rows") or []
    except (OSError, ValueError, AttributeError):
        return {}
    return {str(row.get("key")): str(row.get("candidate") or "") for row in rows
            if isinstance(row, dict) and row.get("key") and str(row.get("candidate") or "").strip()}


def load_review_only_keys(package_dir: Path) -> set[str]:
    manifest_path = package_dir / "manifest.json"
    manifest_keys = set()
    if manifest_path.is_file():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
        if manifest.get('unified_document') is True:
            manifest_keys = {str(e['key']) for e in manifest.get('entries', []) if e.get('review_only') and e.get('key')}
    review_path = package_dir / "review_only.csv"
    if not review_path.is_file():
        return manifest_keys
    with review_path.open(encoding="utf-8-sig", newline="") as fh:
        return manifest_keys | {str(row.get("key") or "") for row in csv.DictReader(fh) if row.get("key")}


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
    # Ren'Py text tags ({a=https://...}, {/a}, {w}) and bare URLs are markup, not prose: their '/' characters are not CT2 filler.
    plain = re.sub(r"\{[^{}]*\}", "", plain)
    plain = re.sub(r"(?i)\bhttps?://\S+", "", plain)
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
    from vntext.mt_classify import is_renpy_control_text
    if str(entry.get("import_method") or "").startswith("renpy_") and is_renpy_control_text(src):
        return "technical_control"
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


# Owner decision (2026-11-02, scoped): coverage completeness and per-entry patch eligibility are separate facts.  A PARTIAL extraction whose ONLY
# open items are the expected static-extraction limitations may patch the already verified MAIN rows; the PARTIAL coverage stays on record.
EXPECTED_PATCH_LIMITATIONS = frozenset({"RUNTIME_DYNAMIC_UNRESOLVED", "ARCHIVE_SOURCE_RUNTIME_UNPROVEN", "REVIEW_SCREEN_CANDIDATES_UNPROMOTED"})
# Real-game finding (2026-11-02): static screen text candidates (``renpy_screen_candidate``: formats such as "[page]", "<", "{#auto_page}A") stay review-only
# evidence, are never MAIN and never patched; when they are the ONLY review rows they count as excluded coverage, not as a reason to block the verified subset.
REVIEW_SCREEN_LIMITATION = "REVIEW_SCREEN_CANDIDATES_UNPROMOTED"


_PARTIAL_PATCH_OVERRIDE: contextvars.ContextVar[bool] = contextvars.ContextVar("vntext_partial_patch_override", default=False)


@contextlib.contextmanager
def partial_patch_override(enabled: bool):
    """Owner-confirmed 'patch only the safe valid subset'.  It relaxes ONLY the extraction-status check of validate_patch_package_identity:
    every per-row structural/hash/schema/path/placeholder/locator check and the row-level skip rules still apply to each included row."""
    token = _PARTIAL_PATCH_OVERRIDE.set(bool(enabled))
    try:
        yield
    finally:
        _PARTIAL_PATCH_OVERRIDE.reset(token)


def partial_override_eligible(status: dict) -> bool:
    """A user override may relax a PARTIAL extraction only; FAILED/EMPTY/unknown/COMPLETE-with-flags stay with the normal rules."""
    return isinstance(status, dict) and status.get("status") == "PARTIAL" and status.get("complete") is False


def partial_override_coverage(status: dict) -> list[dict]:
    """Excluded coverage of an override patch: the recorded limitations, or one honest generic record when the sidecar lists none."""
    recorded = excluded_coverage(status)
    if recorded:
        return recorded
    return [{"code": "USER_PARTIAL_OVERRIDE", "count": 0,
             "message": "Extraction was PARTIAL; only rows that pass every per-row check were patched, everything else is unpatched."}]


def scoped_patch_eligible(status: dict) -> bool:
    """True only for: PARTIAL, no error, SDK-backed (no review-only rows), native accounting complete, non-empty MAIN, and at least one
    limitation, all from the expected set.  Anything else (errors, no-SDK/review rows, EMPTY/FAILED, unknown limitation) stays blocked."""
    if not isinstance(status, dict) or status.get("status") != "PARTIAL" or status.get("complete") is not False:
        return False
    limitations = status.get("limitations")
    if not isinstance(limitations, list) or not limitations:
        return False
    if any(not isinstance(item, dict) or item.get("code") not in EXPECTED_PATCH_LIMITATIONS for item in limitations):
        return False
    counts = (status.get("main"), status.get("review"), status.get("errors"))
    if any(isinstance(value, bool) or not isinstance(value, int) for value in counts):
        return False
    unpromoted = sum(int(item.get("count") or 0) for item in limitations if item.get("code") == REVIEW_SCREEN_LIMITATION)
    return (
        status.get("patch_scope") == "VERIFIED_MAIN_SUBSET"
        and counts[0] > 0 and counts[1] == unpromoted and counts[2] == 0
        and status.get("native_accounting_complete") is True
        and status.get("severity") == "warning"
    )


def excluded_coverage(status: dict) -> list[dict]:
    """The explicit, non-patched coverage of a scoped patch (one record per limitation)."""
    if not isinstance(status, dict):
        return []
    return [
        {"code": str(item.get("code") or ""), "count": int(item.get("count") or 0), "message": str(item.get("message") or "")}
        for item in (status.get("limitations") or []) if isinstance(item, dict)
    ]


def validate_patch_package_identity(csv_path: str | Path, manifest: dict) -> None:
    translations = read_translation_rows(str(csv_path))
    entries = manifest.get("entries")
    if not isinstance(entries, list):
        raise ValueError("Patch manifest entries must be a list")
    keyed = {}
    for entry in entries:
        key = entry.get("key") if isinstance(entry, dict) else None
        if not isinstance(key, str) or not key or key in keyed:
            raise ValueError("Patch manifest has missing or duplicate entry keys")
        keyed[key] = entry
    for key, row in translations.items():
        entry = keyed.get(key)
        if entry is None or row["source_text"] != entry.get("source_text"):
            raise ValueError(f"CSV/manifest source identity mismatch: {key}")
        for field in ("file_path", "import_method", "backend"):
            if field in row and field in entry and row[field] != str(entry[field] or ""):
                raise ValueError(f"CSV/manifest {field} identity mismatch: {key}")
    sidecar = Path(csv_path).parent / "extract_status.json"
    if sidecar.is_file():
        status = json.loads(sidecar.read_text(encoding="utf-8-sig"))
        if (not (status.get("status") == "COMPLETE" and status.get("complete") is True) and not scoped_patch_eligible(status)
                and not (_PARTIAL_PATCH_OVERRIDE.get() and partial_override_eligible(status))):
            raise ValueError("Extraction is incomplete; final Patch is blocked (choose the explicit safe-subset Patch to patch only verified rows)")


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
    validate_patch_package_identity(csv_path, manifest)
    blocked: Counter[str] = Counter()
    samples: dict[str, list[dict[str, str]]] = {}
    items: list[dict[str, str]] = []
    eligible = 0
    from vntext.package_io import read_csv_rows_file
    from vntext.user_exclusions import load_exclusions
    csv_keys = {str(row.get("key") or "") for row in read_csv_rows_file(csv_path)[1]}
    excluded = set(load_exclusions(package_dir))
    kinds = load_review_kinds(package_dir)
    user_excluded = outside_csv = 0

    def block(bucket, key, entry, trans, reason):
        blocked[bucket] += 1
        _add_sample(samples, bucket, key, entry, trans, reason)
        if len(items) < ITEMS_CAP:
            items.append({"key": key, "source_text": str(entry.get("source_text") or "")[:160], "translation": str(trans or "")[:160],
                          "reason": bucket, "label": REASON_LABELS_VI.get(bucket, bucket), "action": reason_action_vi(bucket)})

    for entry in entries:
        key = str(entry.get("key") or "")
        if not key:
            continue
        if key not in csv_keys:
            # Not a row of the document the person edits: removed by them ("Xóa đã chọn") or extraction-only review evidence kept in
            # review_only.csv.  Neither is a translatable row, so neither counts as "chưa đủ điều kiện"; both are reported apart.
            if key in excluded:
                user_excluded += 1
            else:
                outside_csv += 1
            continue
        trans = str(translations[key].get("translation") or "") if key in translations else ""
        if key in review_keys:
            kind = kinds.get(key, "review_only")
            block(kind, key, entry, trans, kind)
            continue
        if key not in translations:
            block("no_translation", key, entry, "", "no_translation")
            continue
        reason = patch_skip_reason(entry, trans, whitelist, allow_ct2_junk=allow_ct2_junk)
        if reason:
            block(reason_bucket(reason), key, entry, trans, reason)
        else:
            eligible += 1

    blocked_total = sum(blocked.values())
    reason_lines = []
    for code, count in blocked.most_common():
        label = REASON_LABELS_VI.get(code, code)
        reason_lines.append(f"{label}: {count}")

    summary = (
        f"Kiểm tra patch — hợp lệ {eligible}, bị chặn {blocked_total} "
        f"(CSV {len(csv_keys)} dòng, có {len(translations)} bản dịch)"
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
        "reason_actions": {k: reason_action_vi(k) for k in blocked},
        "samples": samples,
        "items": items,
        "items_truncated": blocked_total > len(items),
        "csv_rows": len(csv_keys),
        "user_excluded": user_excluded,
        "outside_csv_review": outside_csv,
        "summary": summary,
        "csv_path": str(csv_path),
        "manifest_path": str(manifest_path),
    }


ITEMS_CAP = 5000


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
    parser.add_argument("--partial-override", action="store_true",
                        help="Owner-confirmed safe-subset preflight: relax ONLY the PARTIAL extraction-status check")
    args = parser.parse_args()
    with partial_patch_override(args.partial_override):
        result = audit_patch_package(args.csv_path, args.manifest_path, game_root=args.game_root)
    if args.json:
        sys.stdout.write(json.dumps(result, ensure_ascii=False) + "\n")
    else:
        sys.stdout.write(format_preflight_log(result) + "\n")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
