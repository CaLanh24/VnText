# -*- coding: utf-8 -*-

"""Đối chiếu golden_mapping ↔ translation.csv và điền gap VH đã dịch.

Không full MT. Không chép VH khi match position lệch. Báo cáo từng dòng.
"""

from __future__ import annotations

import sys
from pathlib import Path

def _tests_lib_on_path() -> None:
    cur = Path(__file__).resolve().parent
    while cur.name != "tests" and cur.parent != cur:
        cur = cur.parent
    lib = cur / "lib"
    p = str(lib)
    if p not in sys.path:
        sys.path.insert(0, p)

_tests_lib_on_path()
from bootstrap import bootstrap
TESTS, ROOT, LIB = bootstrap(__file__)

sys.path.insert(0, str(TESTS / "harness" / "crash"))
sys.path.insert(0, str(TESTS / "harness" / "vh_parity"))
sys.path.insert(0, str(TESTS / "harness" / "naninovel"))

import argparse
import csv
import json
import re
import shutil
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


from vntext.mt_classify import classify_row, is_sound_effect_line, is_hesitation_keep_line  # noqa: E402
from vntext.mt_classify import is_star_sfx_line, is_proper_name_keep_line, is_stylized_keep_line  # noqa: E402
from vntext.mt_ui_labels import resolve_ui_label_translation  # noqa: E402
from vntext.mt_check import load_whitelist  # noqa: E402
from vntext.package_io import read_csv_rows_file, write_csv_rows_file  # noqa: E402
from vntext.patch_gate import (  # noqa: E402
    has_intentional_echo,
    has_garbage_repetition,
    load_review_only_keys,
    patch_skip_reason,
    reason_bucket,
)
from work_paths import WORK_ROOT  # noqa: E402

STRUCTURAL_REASONS = {
    "garbage_repetition",
    "html_garbage",
    "placeholder mismatch",
    "tag mismatch",
    "literal newline count",
    "synonym prefix mismatch",
}

# Không dùng re.I — IGNORECASE làm class Unicode khớp nhầm chữ Latin (YES/NO…).
VI_RX = re.compile(r"[ÀÁẢÃẠĂẰẮẲẴẶÂẦẤẨẪẬÈÉẺẼẸÊỀẾỂỄỆÌÍỈĨỊÒÓỎÕỌÔỒỐỔỖỘƠỜỚỞỠỢÙÚỦŨỤƯỪỨỬỮỰỲÝỶỸỴĐàáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđ]")
PKG = WORK_ROOT / "mt_pipeline_copy"
GOLD = WORK_ROOT / "vh_parity" / "golden_mapping.csv"
OUT = WORK_ROOT / "vh_parity"
HUD_FORCE = {
    "no",
    "yes",
    "auto",
    "hide",
    "load",
    "save",
    "title",
    "continue",
    "skip",
    "settings",
    "log",
    "tips",
    "tip",
    "new game",
    "back",
    "exit",
    "start",
    "menu",
    "close",
    "return",
    "text",
}


def has_vi(s: str) -> bool:
    return bool(s and VI_RX.search(s))


def is_localized(tr: str, src: str) -> bool:
    """Có bản địa hóa: dấu Việt, hoặc khác EN rõ (vd. Tua ← SKIP)."""
    tr_s, src_s = (tr or "").strip(), (src or "").strip()
    if not tr_s:
        return False
    if has_vi(tr_s):
        return True
    if tr_s == src_s:
        return False
    # Glossary hit không dấu (Tua) vẫn tính đã dịch
    gloss = resolve_ui_label_translation(src_s, "")
    if gloss and gloss.strip() == tr_s and gloss.strip() != src_s:
        return True
    # Đổi chữ, không còn nguyên EN
    if tr_s.casefold() != src_s.casefold() and not re.fullmatch(r"[A-Za-z0-9 \-_./:]+", tr_s):
        return True
    if tr_s.casefold() != src_s.casefold() and len(tr_s) <= 24 and len(tr_s.split()) <= 4:
        # Nhãn ngắn đã đổi (Tua, OK giữ dạng không dấu)
        return not re.fullmatch(r"[A-Z0-9 \-_]+", tr_s) or tr_s.casefold() in {
            "tua",
            "ok",
            "menu",
        }
    return False


def strip_vh_prefix(vh: str, en: str) -> str:
    vh = (vh or "").strip()
    if ": " in vh and len((en or "").strip()) <= 32:
        left, right = vh.split(": ", 1)
        if "." in left and not has_vi(left) and right.strip():
            return right.strip()
    return vh


def match_reliable(match: str, en: str, vh: str) -> bool:
    m = (match or "").strip()
    if m.startswith("unmatched") or not m:
        return False
    if m in {"key", "locator"}:
        return True
    if m == "position":
        # Position-only matching is evidence of order, not identity.  It is
        # deliberately never safe for copying VH wording into the EN package.
        return False
    return False


def vh_is_translated(status: str, en: str, vh: str) -> bool:
    st = (status or "").strip().lower()
    en_s, vh_s = (en or "").strip(), (vh or "").strip()
    if not vh_s:
        return False
    if st.startswith("translated"):
        return has_vi(vh_s) or (vh_s != en_s and bool(re.search(r"[A-Za-zÀ-ỹ]", vh_s)))
    if st in {"vh_en_rewrite"} and vh_s != en_s and has_vi(vh_s):
        return True
    # Fallback: VH khác EN và có dấu Việt
    return bool(vh_s and vh_s != en_s and has_vi(vh_s))


def keep_reason(row: dict, en: str, vh: str, status: str) -> str | None:
    """Lý do được phép giữ EN dù VH oracle có bản dịch (hoặc technical)."""
    src = str(row.get("source_text") or en or "").strip()
    gloss = resolve_ui_label_translation(src, str(row.get("context") or ""))
    if gloss is None:
        if is_sound_effect_line(src) or is_star_sfx_line(src) or is_hesitation_keep_line(src):
            return "sfx_or_hesitation"
        if is_stylized_keep_line(src) or has_intentional_echo(src) or has_garbage_repetition(src):
            return "echo_or_stylized_keep"
        if re.fullmatch(r"[A-Za-z♡♥!?.…~\s\-*']{1,48}", src) and len(src) <= 36:
            if not has_vi(src) and (
                src.isupper()
                or re.search(r"(?i)\b(fuck|ugh|ahh+|mmm+|eww+|gulp|kyaa|eeek|nghh)\b", src)
            ):
                return "exclaim_or_moan_short"
        # Hangul source — không ép VI từ map lệch
        if re.search(r"[\uac00-\ud7a3]", src):
            return "hangul_source_keep"
        # Typo / debug UI token
        if src.strip().casefold() in {"udefined", "undefined"}:
            return "debug_brand"
    action, reason = classify_row(
        {
            **row,
            "source_text": src,
            "translation": "",
        }
    )
    if action == "skip_technical":
        return f"technical:{reason}"
    if is_proper_name_keep_line(src):
        return "proper_name"
    if is_sound_effect_line(src) or is_star_sfx_line(src) or is_hesitation_keep_line(src):
        return "sfx_or_hesitation"
    if (status or "").startswith("keep_") or (vh.strip() == src and not has_vi(vh)):
        return "vh_also_en"
    if action == "copy_literal" and "onomatopoeia" in reason:
        return "onomatopoeia"
    if action == "copy_literal" and "debug" in reason:
        return "debug_brand"
    if action == "copy_literal" and ("moan" in reason or "exclaim" in reason or "hesitation" in reason):
        return "exclaim_or_moan_short"
    if action == "copy_source" and "Hangul" in reason:
        return "hangul_source_keep"
    return None


def _is_structural_skip(reason: str | None) -> bool:
    if not reason:
        return False
    bucket = reason_bucket(reason)
    if bucket in STRUCTURAL_REASONS:
        return True
    return any(s in reason for s in ("tag mismatch", "placeholder", "literal newline"))


def _load_golden_by_key() -> dict[str, dict]:
    out: dict[str, dict] = {}
    with GOLD.open(encoding="utf-8-sig", newline="") as fh:
        for gr in csv.DictReader(fh):
            key = str(gr.get("key_en") or gr.get("key") or "").strip()
            if key:
                out[key] = gr
    return out


def fix_structural_from_oracle(
    pkg: Path,
    rows: list[dict],
    *,
    apply: bool,
) -> tuple[list[dict], list[dict]]:
    """Sửa bản dịch structural bằng VH oracle key/locator tin cậy."""
    wl = load_whitelist(pkg)
    golden = _load_golden_by_key()
    fixed: list[dict] = []
    unresolved: list[dict] = []
    for row in rows:
        key = str(row.get("key") or "").strip()
        src = str(row.get("source_text") or "").strip()
        tr = str(row.get("translation") or "").strip()
        if not key or not tr:
            continue
        entry = {
            "source_text": src,
            "context": row.get("context", ""),
            "file_path": row.get("file_path", ""),
            "import_method": row.get("import_method", ""),
        }
        reason = patch_skip_reason(entry, tr, wl)
        if not _is_structural_skip(reason):
            continue
        gr = golden.get(key)
        if not gr:
            unresolved.append({"key": key, "reason": reason, "gap": "no_golden_key"})
            continue
        en = str(gr.get("source_en") or src).strip()
        vh = str(gr.get("text_vh") or "").strip()
        match = str(gr.get("match_method") or "")
        status = str(gr.get("vh_status") or "")
        if not match_reliable(match, en, vh) or not vh_is_translated(status, en, vh):
            unresolved.append(
                {
                    "key": key,
                    "reason": reason,
                    "gap": "untrusted_match",
                    "match": match,
                }
            )
            continue
        proposal = propose_fill(src, vh, row)
        if not proposal:
            unresolved.append({"key": key, "reason": reason, "gap": "no_safe_proposal"})
            continue
        gate = patch_skip_reason(entry, proposal, wl)
        if gate:
            unresolved.append(
                {
                    "key": key,
                    "reason": reason,
                    "gap": "proposal_gate_fail",
                    "gate": gate,
                }
            )
            continue
        if apply:
            row["translation"] = proposal
        fixed.append(
            {
                "key": key,
                "en": src[:60],
                "from": tr[:60],
                "to": proposal[:80],
                "reason": reason,
            }
        )
    return fixed, unresolved


def prune_review_only_gate_ok(pkg: Path, *, apply: bool) -> dict:
    """Gỡ review_only khi translation.csv đã pass patch gate."""
    review_path = pkg / "review_only.csv"
    if not review_path.is_file():
        return {"removed": 0, "kept": 0, "unresolved": 0}
    review_rows = list(csv.DictReader(review_path.open(encoding="utf-8-sig")))
    fields = list(review_rows[0].keys()) if review_rows else []
    _, rows = read_csv_rows_file(pkg / "translation.csv")
    by_key = {str(r.get("key") or ""): r for r in rows}
    wl = load_whitelist(pkg)
    kept, removed, unresolved = [], [], []
    for rrow in review_rows:
        key = str(rrow.get("key") or "")
        trow = by_key.get(key)
        if not trow:
            kept.append(rrow)
            continue
        tr = (trow.get("translation") or "").strip()
        if not tr:
            unresolved.append({"key": key, "gap": "empty_translation"})
            kept.append(rrow)
            continue
        entry = {
            "source_text": trow.get("source_text", ""),
            "context": trow.get("context", ""),
            "file_path": trow.get("file_path", ""),
            "import_method": trow.get("import_method", ""),
        }
        if patch_skip_reason(entry, tr, wl):
            unresolved.append({"key": key, "gap": "gate_fail"})
            kept.append(rrow)
            continue
        removed.append(key)
    if apply and removed:
        bak = review_path.with_suffix(
            f".bak.{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.csv"
        )
        shutil.copy2(review_path, bak)
        kept_rows = [r for r in review_rows if str(r.get("key") or "") not in set(removed)]
        with review_path.open("w", encoding="utf-8-sig", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
            w.writeheader()
            w.writerows(kept_rows)
    else:
        bak = None
    return {
        "removed": len(removed),
        "kept": len(kept) if apply else len(review_rows) - len(removed),
        "unresolved": len(unresolved),
        "removed_sample": removed[:20],
        "unresolved_sample": unresolved[:20],
        "backup": str(bak) if bak else None,
    }


def propose_fill(en: str, vh: str, row: dict) -> str | None:
    src = str(row.get("source_text") or en).strip()
    gloss = resolve_ui_label_translation(src, str(row.get("context") or ""))
    if gloss and gloss.strip() != src and (has_vi(gloss) or gloss.casefold() != src.casefold()):
        return gloss.strip()
    proposed = strip_vh_prefix(vh, src)
    # Chỉ nhận VH khi cùng “họ” độ dài (tránh thoại lệch)
    if proposed and has_vi(proposed) and proposed != src:
        if abs(len(proposed) - len(src)) <= max(40, int(len(src) * 1.8)) or len(src) <= 24:
            # Nhãn ngắn: VH sau strip phải ngắn tương đương
            if len(src) <= 24 and len(proposed) > max(40, len(src) * 4):
                return gloss.strip() if gloss and gloss != src else None
            return proposed
    if gloss and gloss.strip() != src and has_vi(gloss):
        return gloss.strip()
    return None


def audit_and_fill(*, apply: bool, package_dir: Path | None = None) -> dict:
    pkg = package_dir or PKG
    fields, rows = read_csv_rows_file(pkg / "translation.csv")
    by_key = {str(r.get("key") or ""): r for r in rows if r.get("key")}

    vh_translated = 0
    app_ok = 0
    missing: list[dict] = []
    kept: list[dict] = []
    filled: list[dict] = []
    unmatched = 0

    with GOLD.open(encoding="utf-8-sig", newline="") as fh:
        for gr in csv.DictReader(fh):
            en = str(gr.get("source_en") or "").strip()
            vh = str(gr.get("text_vh") or "").strip()
            status = str(gr.get("vh_status") or "")
            match = str(gr.get("match_method") or "")
            kind = str(gr.get("text_kind") or "")
            key = str(gr.get("key_en") or gr.get("key") or "")
            if not vh_is_translated(status, en, vh):
                continue
            vh_translated += 1

            if not match_reliable(match, en, vh) or not key:
                unmatched += 1
                kept.append(
                    {
                        "key": key,
                        "en": en[:80],
                        "vh": vh[:80],
                        "reason": "unmatched_or_bad_position",
                        "kind": kind,
                        "match": match,
                    }
                )
                continue

            row = by_key.get(key)
            if not row:
                unmatched += 1
                kept.append(
                    {
                        "key": key,
                        "en": en[:80],
                        "vh": vh[:80],
                        "reason": "key_absent_in_csv",
                        "kind": kind,
                        "match": match,
                    }
                )
                continue

            src = str(row.get("source_text") or en).strip()
            tr = str(row.get("translation") or "").strip()
            if is_localized(tr, src):
                app_ok += 1
                continue

            reason = keep_reason(row, src, vh, status)
            # HUD force: không keep_en nếu glossary/VH có VI
            plain = re.sub(r"</?[^>]+>", "", src).strip().casefold()
            hud_force = plain in HUD_FORCE

            proposal = propose_fill(src, vh, row)
            if reason and not hud_force:
                kept.append(
                    {
                        "key": key,
                        "en": src[:80],
                        "vh": vh[:80],
                        "app": tr[:80],
                        "reason": reason,
                        "kind": kind,
                        "match": match,
                    }
                )
                continue

            if not proposal:
                # Không có bản VI an toàn → ghi missing
                missing.append(
                    {
                        "key": key,
                        "en": src[:100],
                        "vh": vh[:100],
                        "app": tr[:80],
                        "kind": kind,
                        "match": match,
                        "status": status,
                        "gap": "empty" if not tr else "still_en",
                    }
                )
                continue

            missing.append(
                {
                    "key": key,
                    "en": src[:100],
                    "vh": vh[:100],
                    "app": tr[:80],
                    "kind": kind,
                    "match": match,
                    "status": status,
                    "gap": "empty" if not tr else "still_en",
                    "will_fill": proposal[:100],
                }
            )
            if apply:
                row["translation"] = proposal
                filled.append({"key": key, "en": src[:60], "from": tr[:40], "to": proposal[:80], "kind": kind})

    # Force HUD labels trên toàn CSV (kể cả VH TextAsset còn EN) — ưu tiên user.
    hud_forced = 0
    if apply:
        for row in rows:
            src = str(row.get("source_text") or "").strip()
            plain = re.sub(r"</?[^>]+>", "", src).strip()
            if plain.casefold() not in HUD_FORCE:
                continue
            tr = str(row.get("translation") or "").strip()
            if is_localized(tr, src):
                continue
            gloss = resolve_ui_label_translation(src, str(row.get("context") or ""))
            if not gloss or gloss.strip() == src:
                continue
            if not is_localized(gloss, src) and not has_vi(gloss):
                continue
            row["translation"] = gloss.strip()
            hud_forced += 1
            filled.append(
                {
                    "key": row.get("key"),
                    "en": src[:60],
                    "from": tr[:40],
                    "to": gloss.strip()[:80],
                    "kind": "hud_force",
                }
            )

    structural_fixed: list[dict] = []
    structural_unresolved: list[dict] = []
    review_only_before = len(load_review_only_keys(pkg)) if pkg.is_dir() else 0
    if apply:
        structural_fixed, structural_unresolved = fix_structural_from_oracle(pkg, rows, apply=True)
        if structural_fixed:
            filled.extend(
                {
                    "key": x["key"],
                    "en": x["en"],
                    "from": x["from"],
                    "to": x["to"],
                    "kind": "structural_fix",
                }
                for x in structural_fixed
            )
    else:
        structural_fixed, structural_unresolved = fix_structural_from_oracle(pkg, rows, apply=False)

    review_prune = {"removed": 0, "kept": 0, "unresolved": 0}
    if apply:
        review_prune = prune_review_only_gate_ok(pkg, apply=True)

    if apply and (filled or structural_fixed or review_prune.get("removed")):
        bak_dir = pkg / ".csv_editor_backups"
        bak_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        bak = bak_dir / f"translation.before_coverage_fill_{ts}.csv.bak"
        shutil.copy2(pkg / "translation.csv", bak)
        write_csv_rows_file(pkg / "translation.csv", fields, rows)

    # Re-count app_ok after fill
    if apply:
        app_ok = 0
        still_missing: list[dict] = []
        with GOLD.open(encoding="utf-8-sig", newline="") as fh:
            for gr in csv.DictReader(fh):
                en = str(gr.get("source_en") or "").strip()
                vh = str(gr.get("text_vh") or "").strip()
                status = str(gr.get("vh_status") or "")
                match = str(gr.get("match_method") or "")
                key = str(gr.get("key_en") or "")
                if not vh_is_translated(status, en, vh):
                    continue
                if not match_reliable(match, en, vh) or not key or key not in by_key:
                    continue
                row = by_key[key]
                tr = str(row.get("translation") or "").strip()
                src = str(row.get("source_text") or en).strip()
                if is_localized(tr, src):
                    app_ok += 1
                    continue
                reason = keep_reason(row, src, vh, status)
                plain = re.sub(r"</?[^>]+>", "", src).strip().casefold()
                if reason and plain not in HUD_FORCE:
                    continue
                still_missing.append(
                    {
                        "key": key,
                        "en": src[:100],
                        "vh": vh[:100],
                        "app": tr[:80],
                        "kind": gr.get("text_kind"),
                        "match": match,
                    }
                )
        missing_final = still_missing
    else:
        missing_final = [m for m in missing if "will_fill" in m or True]
        # dry-run: missing = those needing fill (exclude already classified kept)
        missing_final = missing

    report = {
        "utc": datetime.now(timezone.utc).isoformat(),
        "package_dir": str(pkg),
        "apply": apply,
        "vh_translated_total": vh_translated,
        "app_translated_vi": app_ok,
        "missing_need_vi": len(missing_final),
        "kept_with_reason": len(kept),
        "kept_by_reason": dict(Counter(k["reason"] for k in kept)),
        "filled_count": len(filled),
        "structural_fixed_count": len(structural_fixed),
        "structural_unresolved_count": len(structural_unresolved),
        "structural_unresolved_sample": structural_unresolved[:30],
        "review_only_prune": review_prune,
        "review_only_keys_before": review_only_before,
        "hud_forced": hud_forced if apply else 0,
        "unmatched_or_absent": unmatched,
        "pass": len(missing_final) == 0,
        "missing_rows": missing_final,
        "kept_rows": kept[:200],
        "filled_rows": filled[:200],
        "note": "PASS chỉ khi mọi dòng VH đã dịch (match tin cậy) đều có VI hoặc keep có lý do.",
    }
    ledger_path = OUT / "intentional_keep_ledger.json"
    ledger_path.write_text(
        json.dumps(
            {
                "utc": report["utc"],
                "package_dir": str(pkg),
                "kept_by_reason": report["kept_by_reason"],
                "rows": kept,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    report["intentional_keep_ledger"] = str(ledger_path)
    return report


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--package", type=Path, default=PKG)
    ap.add_argument("--out", type=Path, default=OUT / "coverage_fill_report.json")
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    report = audit_and_fill(apply=args.apply, package_dir=args.package)
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    # Line report CSV
    line_csv = OUT / "coverage_line_report.csv"
    with line_csv.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(
            fh,
            fieldnames=["bucket", "key", "en", "vh", "app", "reason", "kind", "match", "to"],
            extrasaction="ignore",
            lineterminator="\n",
        )
        w.writeheader()
        for row in report["missing_rows"]:
            w.writerow({"bucket": "missing", **row, "to": row.get("will_fill", "")})
        for row in report.get("kept_rows") or []:
            w.writerow({"bucket": "kept", **row})
        for row in report.get("filled_rows") or []:
            w.writerow(
                {
                    "bucket": "filled",
                    "key": row.get("key"),
                    "en": row.get("en"),
                    "app": row.get("from"),
                    "to": row.get("to"),
                    "kind": row.get("kind"),
                }
            )
    print(
        f"vh_translated={report['vh_translated_total']} app_vi={report['app_translated_vi']} "
        f"missing={report['missing_need_vi']} kept={report['kept_with_reason']} "
        f"filled={report['filled_count']} pass={report['pass']}",
        flush=True,
    )
    print(f"Wrote {args.out}", flush=True)
    print(f"Wrote {line_csv}", flush=True)
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
