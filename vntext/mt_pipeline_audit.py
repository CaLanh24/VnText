"""Audit Patch Gate cho vòng lặp pipeline dịch."""
from __future__ import annotations

import csv
import re
from collections import Counter
from pathlib import Path
from typing import Any

from vntext.mt_translation_safety import validate_candidate
from vntext.mt_classify import classify_row_authoritative, is_sound_effect_line
from vntext.ui_labels import resolve_ui_label_translation
from vntext.mt_check import is_synonym_row, load_whitelist
from vntext.package_io import read_csv_rows_file
from vntext.patch_gate import audit_patch_package, patch_skip_reason, reason_bucket, reason_label_vi

STRUCTURAL_BUCKETS = frozenset(
    {
        "garbage_repetition",
        "html_garbage",
        "placeholder mismatch",
        "tag mismatch",
        "synonym_manual",
        "synonym prefix mismatch",
        "synonym variant count",
        "literal newline count",
        "heart glyph count",
        "RandPick variant count",
        "english suffix after placeholder",
    }
)

SEMANTIC_BUCKETS = frozenset(
    {
        "validation",
    }
)

NON_STRUCTURAL_STATUS = frozenset(
    {
        "no_translation",
        "review_only",
        "retranslate_blocked",
    }
)

PENDING_CATEGORIES = (
    "garbage_repetition",
    "html_garbage",
    "tag",
    "placeholder",
    "synonym",
    "short_ui",
    "technical",
    "sound_fx_candidate",
    "pending_mt",
    "other_review",
)


def classify_reason_counts(reason_counts: dict[str, int]) -> dict[str, Any]:
    structural: dict[str, int] = {}
    semantic: dict[str, int] = {}
    status: dict[str, int] = {}
    for code, count in reason_counts.items():
        if code in STRUCTURAL_BUCKETS or (
            code not in SEMANTIC_BUCKETS and code not in NON_STRUCTURAL_STATUS and "tag" in code.lower()
        ):
            structural[code] = count
        elif code in SEMANTIC_BUCKETS:
            semantic[code] = count
        else:
            status[code] = count
    return {
        "structural": structural,
        "semantic": semantic,
        "status": status,
        "structural_total": sum(structural.values()),
        "semantic_total": sum(semantic.values()),
    }


def measure_semantic_on_translated(rows: list[dict], package_dir: Path) -> dict[str, Any]:
    """Đo validation/UI trên các dòng ĐÃ CÓ translation — không suy diễn từ manifest audit."""
    whitelist = load_whitelist(package_dir)
    counts: Counter[str] = Counter()
    samples: dict[str, dict] = {}
    scanned = 0
    for row in rows:
        trans = str(row.get("translation") or "").strip()
        if not trans:
            continue
        scanned += 1
        entry = {
            "source_text": str(row.get("source_text") or ""),
            "context": str(row.get("context") or ""),
            "file_path": str(row.get("file_path") or ""),
            "import_method": str(row.get("import_method") or ""),
        }
        skip = patch_skip_reason(entry, trans, whitelist)
        if skip:
            bucket = reason_bucket(skip)
            if bucket in SEMANTIC_BUCKETS or bucket == "validation":
                counts[bucket] += 1
                if bucket not in samples:
                    samples[bucket] = {
                        "key": row.get("key", ""),
                        "source": entry["source_text"][:100],
                        "translation": trans[:100],
                    }
        reasons = validate_candidate(row, trans, whitelist)
        if reasons and "validation" not in counts:
            counts["validation_mt_check"] += 1
    return {
        "measured": True,
        "rows_scanned": scanned,
        "counts": dict(counts),
        "samples": samples,
        "note": (
            "Đã quét từng dòng có translation trong CSV. "
            "0 nghĩa là không phát hiện lỗi validation trên bản dịch hiện có."
            if scanned
            else "Không có dòng nào để đo."
        ),
    }


DIALOGUE_ACTIONS = frozenset(
    {
        "translate",
        "translate_synonym",
        "skip_ui_label",
        "ui_label_fixed",
        "copy_literal",
    }
)


def count_dialogue_pending(rows: list[dict]) -> dict[str, Any]:
    """Đếm thoại cần dịch (không gồm skip_technical)."""
    by_action: Counter[str] = Counter()
    total = 0
    for row in rows:
        if str(row.get("translation") or "").strip():
            continue
        action, _ = _classify_intent(row)
        if action == "skip_technical":
            continue
        by_action[action] += 1
        total += 1
    return {"total": total, "by_action": dict(by_action)}


def count_technical_skipped(rows: list[dict]) -> int:
    n = 0
    for row in rows:
        action, _ = _classify_intent(row)
        if action == "skip_technical":
            n += 1
    return n


def _classify_intent(row: dict) -> tuple[str, str]:
    saved = row.get("translation", "")
    row["translation"] = ""
    action, reason, _decision = classify_row_authoritative(row)
    row["translation"] = saved
    return action, reason


def _note_category(note: str) -> str:
    n = (note or "").lower()
    if "synonym" in n:
        return "synonym"
    if "ui label" in n:
        return "short_ui"
    if "placeholder" in n:
        return "placeholder"
    if "tag" in n:
        return "tag"
    if "html" in n or "entity" in n:
        return "html_garbage"
    if "rác" in n or "garbage" in n or "repetition" in n:
        return "garbage_repetition"
    if "validation" in n:
        return "validation"
    return "other_review"


def classify_pending_rows(package_dir: Path) -> dict[str, Any]:
    """Phân loại dòng chưa có translation (pending ~12k)."""
    csv_path = package_dir / "translation.csv"
    _, rows = read_csv_rows_file(csv_path)
    review_notes: dict[str, str] = {}
    review_path = package_dir / "review_only.csv"
    if review_path.is_file():
        with review_path.open(encoding="utf-8-sig", newline="") as fh:
            for row in csv.DictReader(fh):
                key = str(row.get("key") or "")
                if key:
                    review_notes[key] = str(row.get("patch_note") or "")

    counts: Counter[str] = Counter()
    samples: dict[str, dict] = {}

    for row in rows:
        trans = str(row.get("translation") or "").strip()
        if trans:
            continue
        key = str(row.get("key") or "")
        src = str(row.get("source_text") or "")

        if is_synonym_row(row):
            cat = "synonym"
        elif key in review_notes:
            cat = _note_category(review_notes[key])
        else:
            intent, _ = _classify_intent(row)
            if intent == "skip_technical":
                cat = "technical"
            elif intent == "skip_ui_label":
                cat = "short_ui"
            elif intent == "copy_literal":
                cat = "sound_fx_candidate"
            elif intent == "translate":
                cat = "pending_mt"
            else:
                cat = f"intent_{intent}"

        counts[cat] += 1
        if cat not in samples:
            samples[cat] = {
                "key": key,
                "source": src[:120],
                "patch_note": review_notes.get(key, "")[:120],
            }

    return {
        "total_no_translation": sum(counts.values()),
        "counts": dict(counts),
        "samples": samples,
    }


def explain_applied_vs_eligible(
    rows: list[dict],
    *,
    applied: int,
    copied_vi: int = 0,
) -> dict[str, Any]:
    """Giải thích eligible (dòng có translation hợp lệ) vs applied CT2 lần chạy."""
    with_trans = sum(1 for r in rows if str(r.get("translation") or "").strip())
    ui_fixed = 0
    copy_src = 0
    copy_lit = 0
    ct2_in_csv = 0
    for row in rows:
        tr = str(row.get("translation") or "").strip()
        if not tr:
            continue
        src = str(row.get("source_text") or "")
        ctx = str(row.get("context") or "")
        fixed = resolve_ui_label_translation(src, ctx)
        if fixed is not None and tr == fixed:
            ui_fixed += 1
        elif is_sound_effect_line(src) and tr == src.strip():
            copy_lit += 1
        elif tr == src.strip() and classify_row_authoritative({**row, "translation": ""})[0] == "copy_source":
            copy_src += 1
        else:
            ct2_in_csv += 1
    non_ct2 = ui_fixed + copy_src + copy_lit
    accounted = ct2_in_csv + non_ct2
    tail = ""
    if accounted != with_trans:
        tail = f"; chưa phân loại {with_trans - accounted} (dịch tay / run cũ)"
    return {
        "applied_ct2_last_run": applied,
        "ct2_rows_in_csv": ct2_in_csv,
        "ui_label_fixed": ui_fixed,
        "copy_source_vi": copy_src,
        "copy_literal": copy_lit,
        "copied_vi_reported": copied_vi,
        "rows_with_translation": with_trans,
        "non_ct2_writes": non_ct2,
        "explanation": (
            f"eligible={with_trans} = CT2 trong CSV ({ct2_in_csv}; lần chạy applied={applied}) + "
            f"ui_label_fixed ({ui_fixed}) + copy_source ({copy_src}) + copy_literal ({copy_lit}) "
            f"= {accounted}{tail}."
        ),
    }


def audit_package(csv_path: Path, manifest_path: Path) -> dict[str, Any]:
    raw = audit_patch_package(csv_path, manifest_path)
    split = classify_reason_counts(raw.get("reason_counts") or {})
    package_dir = csv_path.parent
    _, rows = read_csv_rows_file(csv_path)
    semantic = measure_semantic_on_translated(rows, package_dir)
    pending = classify_pending_rows(package_dir)
    samples = raw.get("samples") or {}
    structural_samples: dict[str, list[dict]] = {}
    for bucket in STRUCTURAL_BUCKETS:
        if bucket in samples:
            structural_samples[bucket] = samples[bucket][:3]
    return {
        **raw,
        **split,
        "structural_samples": structural_samples,
        "pass_structural": split["structural_total"] == 0,
        "semantic_audit": semantic,
        "pending_breakdown": pending,
        "dialogue_pending": count_dialogue_pending(rows),
        "technical_skipped": count_technical_skipped(rows),
    }


def format_round_report(audit: dict[str, Any], *, translate_stats: dict | None = None) -> str:
    lines = [
        f"Hợp lệ (patch): {audit.get('eligible', 0)}",
        f"Bị chặn tổng (manifest): {audit.get('blocked', 0)}",
        f"Lỗi cấu trúc TRONG CSV: {audit.get('structural_total', 0)}",
    ]
    dp = audit.get("dialogue_pending") or {}
    if dp:
        lines.append(
            f"Thoại pending: {dp.get('total', 0)} "
            f"(skip kỹ thuật: {audit.get('technical_skipped', 0)})"
        )
    if translate_stats:
        lines.append(
            f"CT2 applied={translate_stats.get('applied', '?')} | "
            f"blocked lúc dịch={translate_stats.get('blocked', '?')} | "
            f"pending={translate_stats.get('pending', '?')}"
        )
        gap = translate_stats.get("gap") or {}
        if gap.get("explanation"):
            lines.append(f"applied vs eligible: {gap['explanation']}")

    sem = audit.get("semantic_audit") or {}
    if sem.get("measured"):
        lines.append(
            f"Ngữ nghĩa (đã đo {sem.get('rows_scanned', 0)} dòng có translation): "
            + (
                "; ".join(f"{reason_label_vi(k)}: {v}" for k, v in sorted((sem.get("counts") or {}).items()))
                or "không phát hiện validation"
            )
        )
    else:
        lines.append("Ngữ nghĩa: chưa đo")

    pending = audit.get("pending_breakdown") or {}
    pcounts = pending.get("counts") or {}
    if pcounts:
        parts = [f"{k}: {v}" for k, v in sorted(pcounts.items(), key=lambda x: -x[1])]
        lines.append(f"Chưa dịch ({pending.get('total_no_translation', 0)}): " + "; ".join(parts[:8]))

    psamples = pending.get("samples") or {}
    for cat in ("garbage_repetition", "tag", "placeholder", "synonym", "short_ui", "technical"):
        if cat in psamples:
            s = psamples[cat]
            lines.append(f"Mẫu {cat}: {s.get('key')} | {s.get('source', '')[:70]}")

    structural = audit.get("structural") or {}
    if structural:
        parts = [f"{reason_label_vi(k)}: {v}" for k, v in sorted(structural.items(), key=lambda x: -x[1])]
        lines.append("Cấu trúc trong manifest: " + "; ".join(parts[:6]))
    return "\n".join(lines)
