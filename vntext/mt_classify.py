"""Classify translation.csv rows: player-visible text vs technical identifiers."""
from __future__ import annotations

import re
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from vntext import mt_check
from vntext.extract import is_ui_label_text
from vntext.extract_quality import is_technical_path
from vntext.ui_labels import resolve_ui_label_translation, should_skip_mt_for_ui_label

# Bare resource / path / hash tokens — not player-facing copy.
PATH_LIKE = re.compile(
    r"^(?:[A-Za-z]:\\|/|\./|\.\./|Assets/|StreamingAssets/|"
    r"[A-Za-z0-9_]+(?:/[A-Za-z0-9_.\-]+)+\.[A-Za-z0-9]+)$"
)
HEX_HASH = re.compile(r"^[0-9a-fA-F]{8,}$")
UUID_RX = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)
PURE_CODE = re.compile(r"^[A-Za-z0-9_.\-]+:[A-Za-z0-9_.\-]+$")
NUMERIC_ONLY = re.compile(r"^[\d\s.,:;%+\-*/=<>]+$")
# API/domain-like tokens (randomDate.net, foo.com) — not player copy.
DOMAIN_LIKE = re.compile(r"^[A-Za-z][A-Za-z0-9]*(?:\.[A-Za-z]{2,12})+$")

# V2 is additive and deliberately starts as a measurable decision layer around
# the battle-tested legacy rules below.  The policy fingerprint is explicit so
# trace/cache consumers can invalidate decisions without hashing source files
# or changing the CSV contract.
CLASSIFIER_POLICY_VERSION = "local-translation-v2-classifier-2"
_CLASSIFIER_POLICY_RULES = (
    "hard-technical-veto",
    "metadata-engine-family",
    "authoritative-route-adapter",
    "review-only-and-raw-route-boundary",
    "intentional-keep-ledger",
)
CLASSIFIER_POLICY_HASH = hashlib.sha256(
    json.dumps(
        {"version": CLASSIFIER_POLICY_VERSION, "rules": _CLASSIFIER_POLICY_RULES},
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
).hexdigest()

CLASSIFIER_TRANSLATE = "TRANSLATE"
CLASSIFIER_REVIEW = "REVIEW"
CLASSIFIER_DO_NOT_TRANSLATE = "DO_NOT_TRANSLATE"
CLASSIFIER_UNSUPPORTED = "UNSUPPORTED"

LEDGER_TRANSLATION = "translation"
LEDGER_REVIEW = "review_only"
LEDGER_TECHNICAL = "technical_skipped"
LEDGER_INTENTIONAL_KEEP = "intentional_keep"
LEDGER_FROZEN = "frozen_translation"

_RAW_UNSUPPORTED_METHODS = {
    "raw_fixed_slot",
    "naninovel_blob_string",
    "naninovel_raw_candidate",
    "raw_review_only",
}


@dataclass(frozen=True)
class ClassifierDecision:
    """Stable V2 classification result kept outside ``translation.csv``.

    ``legacy_action`` and ``legacy_reason`` preserve the existing classifier
    surface for callers that still need its exact behavior.  ``decision`` is
    the contract-facing tri-state route (with UNSUPPORTED as a safety boundary)
    and ``ledger`` tells package/trace consumers where the row belongs.
    """

    decision: str
    ledger: str
    reason_code: str
    reason: str
    legacy_action: str
    legacy_reason: str
    confidence: float | None
    evidence: dict[str, Any]
    policy_version: str = CLASSIFIER_POLICY_VERSION
    policy_hash: str = CLASSIFIER_POLICY_HASH

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision": self.decision,
            "ledger": self.ledger,
            "reason_code": self.reason_code,
            "reason": self.reason,
            "legacy_action": self.legacy_action,
            "legacy_reason": self.legacy_reason,
            "confidence": self.confidence,
            "evidence": dict(self.evidence),
            "policy_version": self.policy_version,
            "policy_hash": self.policy_hash,
        }

# Naninovel lưu một số điều kiện, tên scene/animation và key runtime trong
# cùng slot với text. Các token này có thể chứa placeholder, dấu chấm, ngoặc
# hoặc toán tử nhưng không có khoảng trắng tự nhiên của câu thoại.
SCRIPT_RUNTIME_EXPR = re.compile(r"^[!A-Za-z0-9_.${}()\",=<>+\-*/%&]+$")
SCRIPT_FUNCTION_EXPR = re.compile(
    r"^!?\s*(?:StringContains?|HasValue)\s*\(.*\)\s*(?:(?:==|!=)\s*(?:true|false))?\s*$",
    re.IGNORECASE | re.DOTALL,
)

# Naninovel runtime data đôi khi được serialize thành một chuỗi CSV token trong
# cùng slot với display text.  Chỉ nhận diện dạng này khi toàn bộ phần tử là
# identifier và có dấu hiệu rõ ràng của pool runtime (lặp token, PascalCase,
# hoặc hậu tố số).  Câu có khoảng trắng vẫn là copy người chơi nhìn thấy.
_SCRIPT_TOKEN_POOL_ITEM = re.compile(r"^\*?[A-Za-z][A-Za-z0-9_]*$")


def is_naninovel_token_pool(src: str, ctx: str = "", import_method: str = "") -> bool:
    """Nhận diện pool identifier runtime, không nhầm câu thoại dạng CSV."""
    text = str(src or "").strip()
    context = str(ctx or "").lower()
    method = str(import_method or "").lower()
    if "," not in text or any(ch.isspace() for ch in text):
        return False
    if "naninovel" not in context and "naninovel" not in method:
        return False
    if context.endswith(":choice") or context.endswith(":print") or ":choice:" in context:
        return False
    parts = [part.strip() for part in text.split(",")]
    if len(parts) < 3 or any(not _SCRIPT_TOKEN_POOL_ITEM.fullmatch(part) for part in parts):
        return False
    lowered = [part.casefold() for part in parts]
    has_repeat = len(set(lowered)) < len(lowered)
    has_camel_or_suffix = any(
        (re.search(r"[A-Z]", part[1:]) is not None) or re.search(r"\d$", part)
        for part in parts
    )
    has_fragment_marker = any(part.startswith("*") for part in parts)
    return has_repeat or has_camel_or_suffix or has_fragment_marker


def classify_source_row(row: dict) -> tuple[str, str]:
    """Classify by source even when an old package already has bad output."""
    action, reason, _decision = classify_row_authoritative({**row, "translation": ""})
    return action, reason

# Onomatopoeia / tiếng rên ngắn — CT2 hay sinh rác lặp (♪ ♪ ♪)
_SOUND_WORD_RX = re.compile(
    r"^(?:ah+|oh+|uh+h*|mm+|nh+|ng+|ha+|hn+|un+|mmh+|a+h+)[.!?…~\s]*$",
    re.IGNORECASE,
)
_MOAN_LIKE_RX = re.compile(
    r"^(?:ah+|oh+|uh+|mm+|ha+|nh+|ng+|hn+|un+|aah+|ooh+|nnh+|mmh+)$",
    re.IGNORECASE,
)

_NON_ENGLISH_MARKER_RX = re.compile(
    r"(?:MOLU|SAMAI|IKI|DOLA|SALA|NIEK|NOS)"
    r"(?:\s*[!?.,…]*\s*(?:MOLU|SAMAI|IKI|DOLA|SALA|NIEK|NOS))+"
    r"[!?.,…\s]*$",
    re.IGNORECASE,
)


def is_non_english_scene_marker_line(src: str) -> bool:
    """Recognise the bounded foreign-language scene markers used by the game.

    Punctuation may occur between repeated words (``NIEK NOS! NIEK NOS!``),
    so a plain whitespace-only pattern would miss an otherwise intentional
    literal keep and send it through CT2.
    """
    plain = re.sub(r"</?[^>]+>", "", str(src or "").strip())
    return bool(plain and _NON_ENGLISH_MARKER_RX.fullmatch(plain))


def is_sound_effect_line(src: str) -> bool:
    """Dòng chỉ có tiếng rên/onomatopoeia — giữ nguyên, không gửi MT."""
    s = str(src or "").strip()
    if not s or len(s) > 64:
        return False
    # Naninovel đôi khi lưu SFX có tiền tố người nói. Đây là âm thanh hiển
    # thị, không phải câu cần dịch; nhận diện theo một token in hoa lặp lại
    # để không bắt nhầm câu thoại thông thường.
    prefixed = re.fullmatch(
        r"[A-Za-z][A-Za-z0-9_ ]{0,24}:\s*([A-Z]{2,10})(?:\s+\1){2,}[.!?…♡♥]*",
        s,
    )
    if prefixed:
        return True
    if re.fullmatch(r"(?i)a\s+ha(?:\s+ha){1,4}[.!?…]*", s):
        return True
    if re.fullmatch(r"(?i)a+h+a?n+g+h*[.!?…♡♥]*", s):
        return True
    if mt_check.PH.search(s):
        return False
    # A colour tag can wrap a standalone vocalisation; classify the inner text
    # while leaving the tag itself intact for the structural gate.
    s = re.sub(r"</?[^>]+>", "", s).strip()
    letters = re.findall(r"[A-Za-z]+", s)
    if len(letters) == 1 and len(letters[0]) <= 32 and re.search(r"[!?…]", s):
        if mt_check.is_onomatopoeia(letters[0]):
            return True
    if len(letters) > 4:
        return False
    if not letters:
        return bool(re.search(r"[♡♥!?.…]{2,}", s))
    if all(len(w) <= 5 for w in letters):
        joined = " ".join(letters)
        if _SOUND_WORD_RX.match(joined):
            return True
        # Có dấu câu chỉ tính sfx khi mọi từ là tiếng rên/ono — không phải "Beg for the!"
        if re.search(r"[♡♥!?.…]", s):
            return all(
                _MOAN_LIKE_RX.match(w) or mt_check.is_onomatopoeia(w) for w in letters
            )
    return False


def is_hesitation_keep_line(src: str) -> bool:
    """Câu ngắn trong ngoặc kiểu ``(Eh.. Name...?)`` — giữ EN."""
    s = str(src or "").strip()
    # Lời chào ngắn Oh hey / Ek... Hey!
    if re.fullmatch(r"(?i)(?:oh|ek|eh|ah)[.\s…]*hey[!?.…]*", s):
        return True
    if re.fullmatch(r"[A-Z][A-Za-z]{1,20},\s*[.…]{2,}[!?]*", s):
        return True
    # (...?) Name — do dự + tên riêng ngắn, giữ EN.
    if re.fullmatch(
        r"\([.…]{2,}\??\)\s+[A-Z][A-Za-z]{1,16}\.?",
        s,
    ):
        return True
    if len(s) < 5 or len(s) > 56:
        return False
    if not (s.startswith("(") and s.endswith(")")):
        return False
    if mt_check.PH.search(s) or mt_check.TAG.search(s):
        return False
    inner = s[1:-1].strip()
    if not inner:
        return False
    # Chủ yếu dấu ngập ngừng / tiếng rên ngắn + tên riêng tùy chọn.
    if re.fullmatch(r"[.…]{2,}[?!.…\s]*", inner):
        return True
    if re.fullmatch(
        r"(?i)(?:eh|oh|uh|ah|eww+|umm+|hmm+|ngh)[.\s…]*"
        r"(?:[A-Z][A-Za-z]{1,16})?[.\s…?]*",
        inner,
    ):
        return True
    letters = re.findall(r"[A-Za-z]+", inner)
    if letters and all(len(w) <= 4 for w in letters):
        if all(_MOAN_LIKE_RX.match(w) or mt_check.is_onomatopoeia(w) for w in letters):
            return True
    return False


def is_star_sfx_line(src: str) -> bool:
    """*GLRRRK*!!! / *SQUISH* / *GYUK* *GYUK* *GYUK* — sfx trong sao, không MT."""
    s = str(src or "").strip()
    plain = re.sub(r"</?[^>]+>", "", s).strip()
    if re.fullmatch(r"\*[A-Za-z]{2,16}\*[!?.…]*", plain):
        return True
    if re.fullmatch(r"\*[A-Za-z]{2,16}[!?.…~\-]+\*", plain):
        return True
    if re.fullmatch(r"\*[A-Za-z]{2,32}[!?.…♡♥~\-]+\*", plain):
        return True
    if re.fullmatch(r"\*[A-Za-z]{2,5}'s\s+[A-Za-z]{2,5}[!?…]+\*", plain):
        return True
    if re.fullmatch(r"(?:\*[A-Za-z]{2,16}\*\s*){2,}[!?.…]*", plain):
        return True
    # Một số bản script bị lệch dấu * ở giữa chuỗi (ví dụ
    # "*GYUK* GYUK* *GYUK*"). Đây vẫn là một SFX lặp, không phải câu thoại.
    # Keep this bounded and linear.  A repeated-group fullmatch here used to
    # backtrack for seconds on ordinary long dialogue strings.
    malformed_repeat = (
        len(plain) <= 160
        and "*" in plain
        and re.fullmatch(r"[A-Za-z*\s!?.…]+", plain) is not None
    )
    if malformed_repeat:
        words = re.findall(r"[A-Za-z]{2,16}", plain)
        if len(words) >= 2 and len({word.casefold() for word in words}) == 1:
            return True
    # BLABLA... *SNAP*
    if re.fullmatch(r"(?i)[A-Z]{2,12}(?:\.\.\.)?\s*\*[A-Za-z]{2,16}\*", plain):
        return True
    # * nee-nah nee-nah *
    if re.fullmatch(r"\*\s*[a-z\-]+(?:\s+[a-z\-]+){1,6}\s*\*", plain, flags=re.I):
        return True
    return False


def is_stylized_keep_line(src: str) -> bool:
    """(Bo----ri----ng..!) / can't be like this×N — giữ EN có chủ đích."""
    s = str(src or "").strip()
    # Bỏ tag màu để đo độ dài nội dung.
    plain = re.sub(r"</?[^>]+>", "", s).strip()
    if not plain or len(plain) > 800:
        return False
    # Chữ đứt đoạn bằng dấu gạch dài.
    if re.search(r"[A-Za-z]---+[A-Za-z]", plain) and plain.count("-") >= 8:
        return True
    # A repeated phrase is still player-visible prose in most Naninovel
    # lines (``This is not embarrassing`` / laughter prefixes).  Do not turn
    # repetition alone into a literal keep: CT2 must translate the sentence
    # while preserving its wording.  Only an explicit multiplier is opaque.
    if re.search(r"×\s*\d{1,3}\s*$", plain):
        return True
    return False


def is_camel_id_keep_line(src: str) -> bool:
    """Nhãn CamelCase / PascalCase ngắn (Pigman, CafeManager) — giữ EN, CT2 hay ra email rác."""
    s = str(src or "").strip()
    m = re.fullmatch(r"(<color\s*=\s*[^>]+>)(.*?)(</color>)", s, flags=re.I | re.DOTALL)
    if m:
        s = m.group(2).strip()
    if not s or " " in s or len(s) > 40:
        return is_numbered_series_marker(s)
    if re.fullmatch(
        r"[A-Za-z][A-Za-z0-9_]*\{[A-Za-z][A-Za-z0-9_]*\}", s
    ) and "_" in s:
        return True
    if mt_check.PH.search(s) or "[" in s:
        return False
    # ALL-CAPS đơn (PASS/LOG) không phải camel id — để glossary/UI xử lý.
    if s.isupper() and "_" not in s:
        return False
    # Scene/pose identifier, e.g. SampleRoute_2 / QuestOption_4.
    if re.fullmatch(r"[A-Za-z][A-Za-z0-9]*(?:_[A-Za-z0-9]+){1,6}", s):
        return True
    # PascalCase: CafeManager, QuestStage. camelCase: iQuestMsgNotFound.
    if re.fullmatch(r"[A-Z][A-Za-z0-9]*(?:[A-Z][A-Za-z0-9]*)+", s):
        return True
    return bool(re.fullmatch(r"[a-z]+(?:[A-Z][A-Za-z0-9]*){2,}", s))


def is_numbered_series_marker(src: str) -> bool:
    """Recognize a compact acronym/title/number marker without game-specific names."""
    return bool(
        re.fullmatch(
            r"[A-Z]{2,8}\s+[A-Z][A-Za-z]{1,15}\s+\d{1,3}",
            str(src or "").strip(),
            flags=re.IGNORECASE,
        )
    )


def is_proper_name_keep_line(src: str) -> bool:
    """A short proper name wrapped in <color=…> is preserved literally."""
    s = str(src or "").strip()
    m = re.fullmatch(r"(<color\s*=\s*[^>]+>)(.*?)(</color>)", s, flags=re.I | re.DOTALL)
    if not m:
        return False
    inner = m.group(2).strip()
    if not inner or " " in inner or len(inner) > 24:
        return False
    # A standalone all-caps UI token is a translatable label, not a proper
    # name.  Package/user glossary and the selected MT route decide its value.
    if inner.isupper():
        return False
    if mt_check.PH.search(inner) or "_" in inner or "[" in inner:
        return False
    # Một từ viết hoa đầu (tên nhân vật / route label ngắn trong color).
    return bool(re.fullmatch(r"[A-Z][a-zA-Z]{1,20}", inner))


def is_exclaim_moan_line(src: str) -> bool:
    """Ahh!! GENTLY!!!!! / Ewww! ugh... / grr... k... — giữ EN."""
    s = str(src or "").strip()
    plain = re.sub(r"</?[^>]+>", "", s).strip()
    if not plain or len(plain) > 96:
        return False
    if mt_check.PH.search(plain):
        return False
    # Cười/hehe lặp: (He-he-he-he) / He he he
    if re.fullmatch(r"\(?\s*(?:he[-\s]*){2,}he?\s*\!?\)?", plain, flags=re.I):
        return True
    letters = re.findall(r"[A-Za-z]+", plain)
    if not letters or len(letters) > 10:
        return False
    # These are short player-facing utterances, not merely vocalisations.
    # The old heuristic treated "it hurts", "please" and "sorry" as SFX,
    # which silently left real dialogue in English after a successful run.
    dialogue_words = {
        "be", "cheese", "cumming", "fuck", "gently", "harder", "hurts",
        "it", "pervert", "please", "sorry", "stop", "thirsty", "whoa",
    }
    if any(word.casefold() in dialogue_words for word in letters):
        return False
    # Phải có nhiều dấu cảm thán / ngập ngừng
    if len(re.findall(r"[!?.…♥♡]", plain)) < 2 and "..." not in plain and ".." not in plain:
        return False
    keep_words = {
        "gently", "ugh", "ughh", "eww", "ewww", "eek", "eeek", "eeeeek", "geeek",
        "gulp", "he", "haa", "haaa", "haaah", "haaaah", "haaaa",
        "ouch", "it", "hurts", "hurrrrrrts", "hurrts", "pervert", "please",
        "oh", "no", "heeek", "khk", "gek", "ghkkk", "khh", "ukh",
        "im", "i", "m", "dy", "ahheh", "n", "h",
        "grrrrrlk", "grrrlk", "grr", "gr", "uggh",
        "ahhh", "aahhhh", "aaah", "ahh", "ah", "aah", "aahh", "ahaa", "ahaha",
        "aw", "aww", "awww", "awwwh", "umm", "ummh", "mmmmh", "mmmh",
        "kyaa", "wow", "whoa", "whooa", "eh", "bla", "karl", "kehk", "hi",
        "gilk", "ummkh", "phh", "ummph", "sto", "fuuuck", "fuuuuck", "fuck",
        "cumming", "sorry", "k", "sob", "hehe",
        "ammh", "mmh", "heh",
        # Moan + imperative ngắn (Hgh!.. be gentle..!) — CT2 hay sinh rác lặp.
        "be", "gentle", "gently", "slow", "softer", "harder",
        "hgh", "ngh", "nngh", "mph", "mngh",
    }
    return all(
        len(w) <= 12
        and (
            _MOAN_LIKE_RX.match(w)
            or mt_check.is_onomatopoeia(w)
            or w.lower() in keep_words
            or re.fullmatch(r"(?i)h+a+h*|a+h+|u+g+h*|n+g+h*|e+w+", w)
        )
        for w in letters
    )


def is_censored_line(src: str) -> bool:
    """True for deliberately redacted/corrupted display text.

    Asterisks embedded inside several words (``EX**SE``/``T*E``) are a
    source-level censoring convention, not a recoverable English sentence.
    Keep the exact glyph pattern so CT2 cannot invent a misleading phrase.
    """
    plain = re.sub(r"</?[^>]+>", "", str(src or "").strip())
    if not plain or plain.count("*") < 3:
        return False
    masked_word = bool(re.search(r"[A-Za-z]\*+[A-Za-z]", plain))
    # Standalone ``*GLRK*``/``*GUK*`` SFX markers are not censored words; when
    # followed by ``[br]`` they prefix a real dialogue tail that must still be
    # translated.  Only embedded asterisks inside alphabetic text are treated
    # as an opaque censoring convention.
    return masked_word


def is_opaque_all_caps_line(src: str) -> bool:
    """Keep bounded non-language all-caps markers that cannot be translated.

    This covers the game's deliberately opaque strings (for example
    ``EOCND ANJSRK TNTKDGKS WNANS!``) without allowing ordinary all-caps
    English: any known English/lexical word disqualifies the marker.
    """
    plain = re.sub(r"</?[^>]+>", "", str(src or "").strip())
    words = re.findall(r"[A-Za-z]+", plain)
    if len(words) < 3 or len(words) > 12 or not all(w.isupper() for w in words):
        return False
    known = mt_check.ENG_STRONG | mt_check.ENG_WEAK
    if any(w.casefold() in known for w in words):
        return False
    # Short repeated glyph-like tokens (``XXX XXX X X X``) are another
    # opaque vocalisation form; ordinary all-caps English such as ``STOP IT``
    # is excluded by the known-word check above.
    return all(len(w) >= 4 for w in words) or len(set(words)) < len(words)


def is_debug_or_symbol_keep_line(src: str) -> bool:
    """(Debug) UI / Beep- / ◇◇◇ / brand — giữ EN."""
    s = str(src or "").strip()
    if re.match(r"(?i)^\(?\s*debug\s*\)?\b", s):
        return True
    plain = re.sub(r"</?[^>]+>", "", s).strip()
    if re.fullmatch(r"[◇◆■□●○★☆\s?!]+", plain):
        return True
    if re.fullmatch(r"(?i)(?:beep[-\s]*){2,}beep-?", plain):
        return True
    if re.fullmatch(r"(?i)subscribestar|patreon|fanbox", plain):
        return True
    # Imported editor noise occasionally arrives as one long repeated token
    # (``integerinteger...``).  It has no translatable sentence semantics and
    # is safer as an explicit literal/debug keep than as a fabricated MT row.
    if re.fullmatch(r"(?i)(?:[a-z]{6,}){3,}(?:\s+(?:[a-z]{6,})+)+", plain):
        return True
    if re.fullmatch(r"(?i)udefined|undefined", plain):
        return True
    return False


def is_technical_token(src: str) -> bool:
    s = src.strip()
    runtime_s = re.sub(r"</?[^>]+>", "", s).strip()
    if not s:
        return True
    if PATH_LIKE.match(s):
        return True
    if HEX_HASH.match(s) or UUID_RX.match(s):
        return True
    if PURE_CODE.match(s) and "/" not in s and " " not in s:
        return True
    # {tempA}.Start / {var}.Method — token kỹ thuật engine
    if re.fullmatch(r"\{[A-Za-z][A-Za-z0-9_]*\}\.[A-Za-z][A-Za-z0-9_]*", s):
        return True
    # {Photo}_After.SlideIn — tween/anim id
    if re.fullmatch(r"\{[A-Za-z][A-Za-z0-9_]*\}[A-Za-z0-9_]*\.[A-Za-z][A-Za-z0-9_]*", s):
        return True
    # TRandbox.Phero{rand} / Engine.Key{var} — token script kỹ thuật
    if re.fullmatch(
        r"[A-Za-z][A-Za-z0-9]*\.[A-Za-z][A-Za-z0-9]*\{[A-Za-z][A-Za-z0-9_]*\}",
        s,
    ):
        return True
    if DOMAIN_LIKE.match(s) and " " not in s:
        return True
    if NUMERIC_ONLY.match(s):
        return True
    # Date/time format strings are runtime formatting tokens, not UI copy.
    if re.fullmatch(
        r"[yMdHhms]{2,4}(?:[-/: .]+[yMdHhms]{1,4}){2,6}", s
    ):
        return True
    if mt_check.HEX_COLOR.match(s):
        return True
    # Điều kiện Naninovel: StringContain(s), StringContains(s), HasValue(...)
    # và các biến phủ định. Chỉ nhận diện trong token không có khoảng trắng;
    # câu thoại có chữ trong ngoặc vẫn đi tiếp xuống MT.
    if SCRIPT_FUNCTION_EXPR.fullmatch(runtime_s):
        return True
    # Scene/animation/runtime IDs may contain variables, separators or
    # operators. Không coi tên một từ là technical.
    if (
        not re.search(r"\s", runtime_s)
        and any(marker in runtime_s for marker in ("{", "}", ".", "_", "%", "&&", "||", "==", "!="))
        and SCRIPT_RUNTIME_EXPR.fullmatch(runtime_s)
    ):
        return True
    # Ghi chú editor / autosave — không phải thoại người chơi
    if "autosave" in s.lower() and "do not delete" in s.lower():
        return True
    # Version / build stamp
    if re.fullmatch(r"(?i)ver(?:sion)?\s*[\d.]+", s):
        return True
    # Biểu thức điều kiện gọn: a&&b, x||y (có thể có dấu cách quanh toán tử)
    if ("&&" in s or "||" in s) and not re.search(
        r"[A-Za-zÀ-ỹ]{5,}\s+[A-Za-zÀ-ỹ]{5,}", s
    ):
        return True
    if mt_check.COND_EXPR.search(s) and " " not in s and len(s) <= 80:
        return True
    # {skill_x+skill_y}<N / {var}<5 — điều kiện skill/HUD
    if re.fullmatch(
        r"\{[A-Za-z][A-Za-z0-9_]*\}(?:\s*[+\-]\s*\{[A-Za-z][A-Za-z0-9_]*\})*"
        r"\s*(?:<=|>=|<|>|==|!=)\s*-?\d+(?:\.\d+)?",
        s,
    ):
        return True
    return False


def classify_row(row: dict) -> tuple[str, str]:
    """Return (action, reason).

    action:
      - done          — already has translation
      - skip_technical — ID/path/code, not player copy
      - copy_source   — already Vietnamese UI; keep source as translation
      - copy_literal  — onomatopoeia; giữ nguyên source (không MT)
      - ui_label_fixed — glossary UI
      - skip_ui_label — UI ngắn không có glossary
      - translate     — send to MT
    """
    src = str(row.get("source_text") or "")
    if not src.strip():
        return "skip_technical", "empty source"
    # Structured extractors intentionally inspect field values, so a runtime
    # config XML can contain sentence-shaped comments that pass text quality.
    # Apply the same path boundary at the package/MT boundary as plain-text
    # extraction.  This also quarantines rows from packages made by an older
    # classifier when they are rerun.
    file_path = str(row.get("file_path") or "").strip()
    if file_path and is_technical_path(Path(file_path)):
        return "skip_technical", "technical runtime/config path — không phải thoại"
    # Notes/debug placeholders accidentally imported from Naninovel are not
    # player-visible copy and must live in technical_skipped.csv.
    src_fold = src.casefold()
    if "never edit the above lines" in src_fold and "auto-save" in src_fold:
        return "skip_technical", "editor autosave note"
    if re.fullmatch(r"(?:bla\s*){3,}[.!?…]*", src, flags=re.IGNORECASE):
        return "skip_technical", "editor/debug gibberish"
    if "use same scene as" in src_fold:
        return "skip_technical", "editor scene note"
    if str(row.get("translation") or "").strip():
        return "done", "has translation"

    ctx = str(row.get("context") or "")
    if mt_check.is_script_identifier(src, ctx):
        return "skip_technical", "naninovel label/actor id"

    if is_naninovel_token_pool(
        src,
        ctx,
        str(row.get("import_method") or ""),
    ):
        return "skip_technical", "naninovel runtime token pool — không phải thoại"

    if is_technical_token(src):
        # Nhãn choice/menu dạng domain (randomDate.net) vẫn hiện cho người chơi.
        im = str(row.get("import_method") or "")
        ctx_l = ctx.lower()
        if DOMAIN_LIKE.match(src.strip()) and (
            im == "naninovel_choice"
            or ctx_l.endswith(":choice")
            or ":choice" in ctx_l
        ):
            return "copy_literal", "choice domain label — giữ nguyên"
        return "skip_technical", "path/id/hash token — không phải thoại"

    if (
        len(src.strip().split()) == 1
        and mt_check.source_proper_name_tokens(src)
        and not str(ctx).lower().endswith(":choice")
        and str(row.get("import_method") or "") != "naninovel_choice"
    ):
        return "copy_literal", "proper name — giữ nguyên"

    if mt_check.is_synonym_row(row):
        return "translate_synonym", "synonym pool — dịch giá trị sau ="

    if is_sound_effect_line(src):
        return "copy_literal", "onomatopoeia — giữ nguyên"

    if is_non_english_scene_marker_line(src):
        return "copy_literal", "foreign scene marker — giữ nguyên"

    if is_star_sfx_line(src):
        return "copy_literal", "star sfx — giữ nguyên"

    if is_censored_line(src):
        return "copy_literal", "censored source — giữ nguyên"

    if is_opaque_all_caps_line(src):
        return "copy_literal", "opaque all-caps marker — giữ nguyên"

    if is_debug_or_symbol_keep_line(src):
        return "copy_literal", "debug/symbol/brand — giữ nguyên"

    if is_camel_id_keep_line(src):
        return "copy_literal", "camelCase/scene id — giữ nguyên"

    # Glossary UI trước proper-name keep — <color>PASS</color> phải ra Đạt.
    # NaninovelScript chrome (kể cả <color>HIDE</color>): giữ EN — tránh lệch Script slots.
    _NANO_HUD_KEEP = {
        "auto", "hide", "save", "settings", "title", "skip", "load",
        "continue", "back", "return", "yes", "no", "close", "exit",
        "basic", "sound", "text", "submit",
    }
    plain_for_hud = re.sub(r"</?[^>]+>", "", src).strip()
    ctx_l = ctx.lower()
    if (
        plain_for_hud.casefold() in _NANO_HUD_KEEP
        and "naninovelscript" in ctx_l
        and not ctx_l.endswith(":choice")
    ):
        return "copy_literal", "NaninovelScript chrome — giữ EN (ổn định Script)"

    fixed = resolve_ui_label_translation(src, ctx)
    if fixed is not None and fixed.strip():
        if fixed.strip() == src.strip():
            return "copy_literal", "glossary keep EN"
        return "ui_label_fixed", fixed

    if is_proper_name_keep_line(src):
        return "copy_literal", "proper name — giữ nguyên"

    if is_stylized_keep_line(src):
        return "copy_literal", "stylized EN keep"

    if is_exclaim_moan_line(src):
        return "copy_literal", "exclaim/moan — giữ nguyên"

    if is_hesitation_keep_line(src):
        return "copy_literal", "hesitation ngắn — giữ nguyên"

    from vntext.mt_translation_safety import is_moan_with_tech_line

    if is_moan_with_tech_line(src):
        return "copy_literal", "moan + placeholder/tag — giữ nguyên"

    body = mt_check.strip_technical(src)
    body = mt_check.KEY_PREFIX.sub(" ", body)
    body = mt_check.COND_EXPR.sub(" ", body)
    if not mt_check.WORD.findall(body) and not any(ord(c) > 127 for c in body):
        return "skip_technical", "punctuation/number only"

    if mt_check.is_vietnamese_text(src):
        return "copy_source", "source already Vietnamese"

    # Hangul / CJK khác VI — giữ nguyên (không gửi OPUS-MT en→vi).
    if re.search(r"[\uac00-\ud7a3\u3040-\u30ff\u4e00-\u9fff]", src):
        return "copy_source", "source Hangul/CJK — giữ nguyên"

    # ALL-CAPS menu/tab labels in UI localization assets should be translated.
    # Keep ALL-CAPS only for Naninovel script identifiers (handled above) or
    # pure onomatopoeia/sound (handled earlier).
    ctx_l = ctx.lower()
    ui_loc_asset = (
        ctx.startswith("UI:")
        or "textasset:" in ctx_l
        or str(row.get("import_method") or "") in {"unity_ui_text", "naninovel_choice"}
        or ctx_l.endswith(":choice")
    )
    if src.isupper() and len(src) <= 40 and len(src.split()) <= 5 and not mt_check.PH.search(src):
        if ":" not in src and "/" not in src:
            if ui_loc_asset:
                return "translate", "ALL-CAPS UI/menu label — dịch"
            # Generic status marker: do not send a lock token to MT.
            if re.fullmatch(r"\(?LOCKED\d*\)?", src, flags=re.IGNORECASE):
                return "copy_literal", "non-English/status label — giữ nguyên"

    if should_skip_mt_for_ui_label(row):
        # Short UI without glossary: still attempt MT for localization assets;
        # only keep EN for bare technical HUD crumbs outside UI packs.
        if ui_loc_asset or is_ui_label_text(src):
            return "translate", "UI label ngắn — thử MT"
        return "copy_literal", "UI label ngắn — giữ nguyên (không MT)"

    return "translate", "player-visible text"


def _bounded_classifier_text(value: Any, limit: int = 240) -> str:
    text = str(value or "").replace("\x00", "")
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _classifier_engine_family(row: Mapping[str, Any]) -> str:
    values = " ".join(
        str(row.get(name) or "").casefold()
        for name in ("context", "file_path", "import_method", "backend", "object_info")
    )
    if "naninovel" in values:
        return "naninovel"
    if "localization" in values or "stringtable" in values:
        return "unity_localization"
    if any(token in values for token in ("unity_", "unityfs", "assetbundle", "textasset", "typetree")):
        return "unity"
    if any(token in values for token in ("structured_", "json", "csv", "xml", "sqlite")):
        return "structured"
    if any(token in values for token in ("renpy", "rpy")):
        return "renpy_inactive"
    return "unknown"


def _classifier_source_shape(source: str) -> dict[str, Any]:
    plain = re.sub(r"</?[^>]+>", "", source)
    return {
        "length": len(source),
        "line_count": source.count("\n") + 1,
        "word_count": len(re.findall(r"[A-Za-zÀ-ỹ]+", plain)),
        "has_placeholder": bool(mt_check.PH.search(source)),
        "has_tag": bool(mt_check.TAG.search(source)),
        "has_escape": "\\" in source,
        "has_randpick": "{rand" in source.casefold(),
        "has_markup_or_control": bool(re.search(r"[{}<>\[\]\\]", source)),
    }


def _classifier_patch_proof_state(row: Mapping[str, Any]) -> tuple[bool, bool]:
    """Return (present, complete) without treating omitted legacy metadata as failure."""

    proof = row.get("patch_proof")
    if not isinstance(proof, Mapping):
        return False, False
    if not proof:
        return True, False
    return True, all(bool(value) for value in proof.values())


def _classifier_reason_code(action: str, reason: str) -> str:
    text = f"{action} {reason}".casefold()
    patterns = (
        ("empty source", "EMPTY_SOURCE"),
        ("technical runtime/config path", "TECHNICAL_PATH"),
        ("autosave", "EDITOR_NOTE"),
        ("editor/debug", "EDITOR_GIBBERISH"),
        ("editor scene", "EDITOR_NOTE"),
        ("label/actor", "RUNTIME_IDENTIFIER"),
        ("token pool", "RUNTIME_TOKEN_POOL"),
        ("path/id/hash", "TECHNICAL_TOKEN"),
        ("punctuation/number", "SYMBOL_ONLY"),
        ("already vietnamese", "SOURCE_ALREADY_TARGET"),
        ("hangul/cjk", "NON_LATIN_SOURCE"),
        ("synonym pool", "SYNONYM_POOL"),
        ("glossary", "GLOSSARY_RULE"),
        ("choice domain", "CHOICE_LITERAL"),
        ("onomatopoeia", "SFX_LITERAL"),
        ("scene marker", "SCENE_MARKER_LITERAL"),
        ("star sfx", "SFX_LITERAL"),
        ("censored", "CENSORED_LITERAL"),
        ("opaque all-caps", "OPAQUE_MARKER_LITERAL"),
        ("debug/symbol/brand", "DEBUG_OR_BRAND_LITERAL"),
        ("camelcase/scene id", "RUNTIME_ID_LITERAL"),
        ("proper name", "PROPER_NAME_LITERAL"),
        ("stylized", "STYLIZED_LITERAL"),
        ("exclaim/moan", "VOCALIZATION_LITERAL"),
        ("hesitation", "HESITATION_LITERAL"),
        ("moan + placeholder", "PROTECTED_VOCALIZATION_LITERAL"),
        ("keep name", "PROPER_NAME_LITERAL"),
        ("keep en", "INTENTIONAL_KEEP"),
        ("ui label", "UI_LABEL"),
        ("has translation", "FROZEN_TRANSLATION"),
        ("player-visible", "PLAYER_VISIBLE_COPY"),
    )
    for needle, code in patterns:
        if needle in text:
            return code
    return {
        "done": "FROZEN_TRANSLATION",
        "skip_technical": "TECHNICAL_RULE",
        "copy_literal": "INTENTIONAL_KEEP",
        "copy_source": "INTENTIONAL_KEEP",
        "skip_ui_label": "INTENTIONAL_KEEP",
        "translate_synonym": "SYNONYM_POOL",
        "ui_label_fixed": "UI_LABEL",
        "translate": "PLAYER_VISIBLE_COPY",
    }.get(action, "CLASSIFIER_RULE")


def _classifier_evidence(row: Mapping[str, Any], source: str) -> dict[str, Any]:
    proof_present, proof_complete = _classifier_patch_proof_state(row)
    locator = row.get("locator")
    if not isinstance(locator, Mapping):
        locator = {}
    return {
        "engine_family": _classifier_engine_family(row),
        "file_path": _bounded_classifier_text(row.get("file_path")),
        "context": _bounded_classifier_text(row.get("context")),
        "object_info": _bounded_classifier_text(row.get("object_info")),
        "import_method": _bounded_classifier_text(row.get("import_method"), 96),
        "backend": _bounded_classifier_text(row.get("backend"), 96),
        "review_only": bool(row.get("review_only", False)),
        "raw_route": str(row.get("import_method") or "") in _RAW_UNSUPPORTED_METHODS,
        "locator_present": bool(locator),
        "locator_fields": sorted(str(key) for key in locator),
        "patch_proof_present": proof_present,
        "patch_proof_complete": proof_complete,
        "source_shape": _classifier_source_shape(source),
    }


def classify_row_v2(row: Mapping[str, Any]) -> ClassifierDecision:
    """Return a metadata-aware, tri-state route without changing legacy callers.

    The legacy classifier remains the decision oracle for ordinary rows during
    the initial V2 rollout.  Explicit review/raw boundaries are applied first
    so an extract-only route cannot be mistaken for a translatable MAIN row.
    All policy metadata is returned for trace/report storage, never appended to
    the public CSV fields.
    """

    normalized = dict(row or {})
    source = str(normalized.get("source_text") or "")
    legacy_action, legacy_reason = classify_row(normalized)
    raw_route = str(normalized.get("import_method") or "") in _RAW_UNSUPPORTED_METHODS
    has_translation = bool(str(normalized.get("translation") or "").strip())

    if has_translation and legacy_action == "done":
        decision = CLASSIFIER_DO_NOT_TRANSLATE
        ledger = LEDGER_FROZEN
        reason_code = "FROZEN_TRANSLATION"
        confidence = 1.0
    elif raw_route:
        decision = CLASSIFIER_UNSUPPORTED
        ledger = LEDGER_REVIEW
        reason_code = "UNSUPPORTED_RAW_ROUTE"
        confidence = 0.99
    elif bool(normalized.get("review_only", False)):
        decision = CLASSIFIER_REVIEW
        ledger = LEDGER_REVIEW
        reason_code = "EXTRACT_REVIEW_ONLY"
        confidence = 0.99
    elif legacy_action == "skip_technical":
        decision = CLASSIFIER_DO_NOT_TRANSLATE
        ledger = LEDGER_TECHNICAL
        reason_code = _classifier_reason_code(legacy_action, legacy_reason)
        confidence = 0.99
    elif legacy_action in {"copy_literal", "copy_source", "skip_ui_label"}:
        decision = CLASSIFIER_DO_NOT_TRANSLATE
        ledger = LEDGER_INTENTIONAL_KEEP
        reason_code = _classifier_reason_code(legacy_action, legacy_reason)
        confidence = 0.95
    elif legacy_action in {"translate", "translate_synonym", "ui_label_fixed"}:
        decision = CLASSIFIER_TRANSLATE
        ledger = LEDGER_TRANSLATION
        reason_code = _classifier_reason_code(legacy_action, legacy_reason)
        confidence = 0.85
    else:
        decision = CLASSIFIER_REVIEW
        ledger = LEDGER_REVIEW
        reason_code = _classifier_reason_code(legacy_action, legacy_reason)
        confidence = 0.5

    evidence = _classifier_evidence(normalized, source)
    return ClassifierDecision(
        decision=decision,
        ledger=ledger,
        reason_code=reason_code,
        reason=str(legacy_reason or reason_code),
        legacy_action=str(legacy_action),
        legacy_reason=str(legacy_reason or ""),
        confidence=confidence,
        evidence=evidence,
    )


_AUTHORITATIVE_LEGACY_ACTIONS = {
    "done",
    "skip_technical",
    "copy_source",
    "copy_literal",
    "ui_label_fixed",
    "skip_ui_label",
    "translate",
    "translate_synonym",
}


def legacy_action_for_classifier(decision: ClassifierDecision) -> str:
    """Map the V2 decision to the stable action used by existing pipelines."""
    if decision.decision == CLASSIFIER_UNSUPPORTED:
        return "unsupported"
    if decision.decision == CLASSIFIER_REVIEW:
        return "review_only"
    if decision.legacy_action in _AUTHORITATIVE_LEGACY_ACTIONS:
        return decision.legacy_action
    if decision.decision == CLASSIFIER_TRANSLATE:
        return "translate"
    return "skip_technical"


def classify_row_authoritative(
    row: Mapping[str, Any],
) -> tuple[str, str, ClassifierDecision]:
    """Return the normal routing action, reason, and full V2 decision."""
    decision = classify_row_v2(row)
    action = legacy_action_for_classifier(decision)
    return action, str(decision.reason or decision.reason_code), decision


def classify_rows_v2(rows: list[Mapping[str, Any]]) -> list[ClassifierDecision]:
    """Classify a bounded batch while preserving row order and keys."""

    return [classify_row_v2(row) for row in rows]


def evaluate_classifier_v2(
    rows: list[Mapping[str, Any]],
    labels: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Measure routing and optional labeled-corpus errors.

    Labels are keyed by the existing row ``key`` and may be ``technical``,
    ``player_visible``, ``intentional_keep``, ``review`` or ``unsupported``.
    Missing labels intentionally produce null error metrics rather than an
    invented quality score.
    """

    decisions = classify_rows_v2(rows)
    counts = {name: 0 for name in (
        CLASSIFIER_TRANSLATE,
        CLASSIFIER_REVIEW,
        CLASSIFIER_DO_NOT_TRANSLATE,
        CLASSIFIER_UNSUPPORTED,
    )}
    ledger_counts = {
        LEDGER_TRANSLATION: 0,
        LEDGER_REVIEW: 0,
        LEDGER_TECHNICAL: 0,
        LEDGER_INTENTIONAL_KEEP: 0,
        LEDGER_FROZEN: 0,
    }
    for result in decisions:
        counts[result.decision] = counts.get(result.decision, 0) + 1
        ledger_counts[result.ledger] = ledger_counts.get(result.ledger, 0) + 1

    expected = dict(labels or {})
    labeled = []
    for row, result in zip(rows, decisions):
        key = str(row.get("key") or "")
        label = expected.get(key, row.get("expected_label", row.get("label")))
        if label is not None and str(label).strip():
            labeled.append((str(label).casefold().strip(), result))

    technical_rows = [result for label, result in labeled if label in {"technical", "skip", "do_not_translate"}]
    visible_rows = [result for label, result in labeled if label in {"player_visible", "visible", "translate"}]
    fp = sum(result.decision == CLASSIFIER_TRANSLATE for result in technical_rows)
    fn = sum(result.decision != CLASSIFIER_TRANSLATE for result in visible_rows)
    return {
        "policy_version": CLASSIFIER_POLICY_VERSION,
        "policy_hash": CLASSIFIER_POLICY_HASH,
        "rows": len(rows),
        "no_drop": len(decisions) == len(rows),
        "decision_counts": counts,
        "ledger_counts": ledger_counts,
        "candidate_coverage": (counts[CLASSIFIER_TRANSLATE] / len(rows)) if rows else 0.0,
        "review_rate": (counts[CLASSIFIER_REVIEW] / len(rows)) if rows else 0.0,
        "unsupported_rate": (counts[CLASSIFIER_UNSUPPORTED] / len(rows)) if rows else 0.0,
        "labeled_rows": len(labeled),
        "technical_labeled_rows": len(technical_rows),
        "player_visible_labeled_rows": len(visible_rows),
        "technical_false_positive": fp if technical_rows else None,
        "player_visible_false_negative": fn if visible_rows else None,
        "technical_leakage": (fp / len(technical_rows)) if technical_rows else None,
        "player_visible_drop_rate": (fn / len(visible_rows)) if visible_rows else None,
    }
