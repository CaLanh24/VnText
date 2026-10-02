# -*- coding: utf-8 -*-

"""Local validator — không gọi MT.

Kiểm: structural, garbage, identity ngoài keep, pending dialogue/choice,
coverage choice/menu theo reference mapping do caller cung cấp (nếu có).
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
from collections import Counter
from pathlib import Path


from vntext.mt_check import load_whitelist  # noqa: E402
from vntext.intentional_keep import (  # noqa: E402
    classify_review_only_status,
    intentional_keep_reason,
    load_intentional_keep_ledger,
)
from vntext.mt_classify import classify_row  # noqa: E402
from vntext.mt_strategies import allow_identity_translation  # noqa: E402
from vntext.package_io import read_csv_rows_file  # noqa: E402
from vntext.patch_gate import (  # noqa: E402
    has_garbage_repetition,
    has_html_garbage,
    has_intentional_echo,
    is_ct2_junk_translation,
    patch_skip_reason,
    reason_bucket,
)
from work_paths import WORK_ROOT  # noqa: E402

STRUCTURAL = {
    "garbage_repetition",
    "html_garbage",
    "placeholder mismatch",
    "tag mismatch",
    "literal newline count",
    "synonym prefix mismatch",
}
DIALOGUE_ACTIONS = {
    "translate",
    "ui_label_fixed",
    "copy_source",
    "copy_literal",
    "skip_ui_label",
}


def text_kind(row: dict) -> str:
    ctx = str(row.get("context") or "")
    im = str(row.get("import_method") or "")
    fp = str(row.get("file_path") or "")
    src = str(row.get("source_text") or "")
    low_ctx, low_fp = ctx.lower(), fp.lower()
    if low_ctx.endswith(":choice") or "naninovel_choice" in im:
        return "choice"
    if low_ctx.endswith(":print"):
        return "dialogue_print"
    if "synonym" in low_fp or "_synonyms" in low_fp:
        return "synonym"
    if "tip" in low_ctx or "tips" in low_fp:
        return "tip"
    if any(x in low_ctx for x in ("uitext", "tmp", "button", "label", "menu", "defaultui")):
        return "ui_menu"
    if "{" in src and "}" in src:
        return "placeholder"
    if "<" in src or "[br]" in src.lower():
        return "tag"
    if "NaninovelScript" in ctx:
        return "dialogue"
    return "other"


def _intent(row: dict) -> str:
    saved = row.get("translation", "")
    row["translation"] = ""
    action, _ = classify_row(row)
    row["translation"] = saved
    return action


def _reference_match(entry: dict, translation: str, references: dict[str, str]) -> bool:
    """Return an audit-only match from an explicitly supplied reference map."""
    expected = references.get(str(entry.get("key") or ""), "").strip()
    return bool(expected) and expected == translation.strip()


def is_intentional_keep(row: dict, package_dir: Path | str | None = None) -> bool:
    src = str(row.get("source_text") or "").strip()
    tr = str(row.get("translation") or "").strip()
    if not src or src != tr:
        return False
    key = str(row.get("key") or "")
    if package_dir and key:
        ledger = load_intentional_keep_ledger(package_dir)
        if key in (ledger.get("keys") or {}):
            return True
    if intentional_keep_reason(row):
        return True
    return allow_identity_translation(row, "copy_literal")


def validate_package(
    package_dir: Path,
    *,
    reference_mapping: Path | None = None,
) -> dict:
    csv_path = package_dir / "translation.csv"
    fields, rows = read_csv_rows_file(csv_path)
    whitelist = load_whitelist(package_dir)

    structural: list[dict] = []
    garbage: list[dict] = []
    identity_bad: list[dict] = []
    pending: list[dict] = []
    by_kind_pending: Counter[str] = Counter()
    by_kind_ok: Counter[str] = Counter()
    choice_total = choice_ok = 0
    menu_total = menu_ok = 0
    oracle_exact_matches = 0
    references: dict[str, str] = {}
    if reference_mapping and reference_mapping.is_file():
        with reference_mapping.open(encoding="utf-8-sig", newline="") as stream:
            for reference in csv.DictReader(stream):
                key = str(reference.get("key") or "").strip()
                value = str(
                    reference.get("reference_translation")
                    or reference.get("translation")
                    or ""
                ).strip()
                if key and value:
                    references[key] = value

    for row in rows:
        key = str(row.get("key") or "")
        src = str(row.get("source_text") or "")
        tr = str(row.get("translation") or "").strip()
        kind = text_kind(row)
        intent = _intent(row)
        entry = {
            "key": key,
            "source_text": src,
            "context": row.get("context", ""),
            "file_path": row.get("file_path", ""),
            "object_info": row.get("object_info", ""),
            "import_method": row.get("import_method", ""),
        }

        if kind == "choice":
            choice_total += 1
        if kind == "ui_menu":
            menu_total += 1

        if intent == "skip_technical":
            by_kind_ok[kind] += 1
            if kind == "choice":
                choice_ok += 1
            if kind == "ui_menu":
                menu_ok += 1
            continue

        if not tr:
            if intent in DIALOGUE_ACTIONS or intent == "translate":
                pending.append({"key": key, "kind": kind, "intent": intent, "source": src[:100]})
                by_kind_pending[kind] += 1
            continue

        # Read-only audit signal only. A reference match never weakens the
        # structural/garbage checks used for a writable package.
        if _reference_match(entry, tr, references):
            oracle_exact_matches += 1

        reason = patch_skip_reason(entry, tr, whitelist)
        bucket = reason_bucket(reason) if reason else ""
        if reason and (
            bucket in STRUCTURAL
            or any(s in reason for s in ("tag mismatch", "placeholder", "literal newline"))
        ):
            structural.append({"key": key, "kind": kind, "reason": reason, "source": src[:80]})
        if has_garbage_repetition(tr) or is_ct2_junk_translation(src, tr) or (
            has_html_garbage(tr) and tr != src.strip()
        ):
            # Giữ nguyên echo/sfx cố ý không tính garbage.
            if tr == src.strip() and (
                is_intentional_keep(row, package_dir)
                or has_intentional_echo(src)
                or has_garbage_repetition(src)
            ):
                pass
            elif has_intentional_echo(src) and has_intentional_echo(tr):
                pass
            else:
                garbage.append({"key": key, "kind": kind, "source": src[:80], "tr": tr[:80]})

        if tr == src.strip() and not is_intentional_keep(row, package_dir):
            if has_intentional_echo(src) or has_garbage_repetition(src):
                pass
            elif intent in ("translate", "ui_label_fixed", "translate_synonym"):
                # Synonym giữ EN ngắn sau = là chấp nhận được.
                if intent == "translate_synonym" and re.match(
                    r"\{[A-Za-z0-9_]+\}=", src.strip()
                ):
                    rest = src.split("=", 1)[-1]
                    if rest and not any("\u00c0" <= c <= "\u1ef9" for c in rest):
                        # Giá trị còn EN — không tính identity_bad cứng (fallback giữ stem).
                        pass
                    else:
                        identity_bad.append({"key": key, "kind": kind, "source": src[:100]})
                else:
                    identity_bad.append({"key": key, "kind": kind, "source": src[:100]})

        if kind == "choice" and tr and (tr != src.strip() or is_intentional_keep(row, package_dir)):
            choice_ok += 1
        if kind == "ui_menu" and tr and (tr != src.strip() or is_intentional_keep(row, package_dir)):
            menu_ok += 1

        if not reason:
            by_kind_ok[kind] += 1

    # Optional reference gaps are audit-only and never supply package output.
    oracle = {
        "reference_translated_mt_empty": 0,
        "reference_translated_mt_identity": 0,
        "reference_gap_ignored_position_mismatch": 0,
        "reference_gap_ignored_technical": 0,
        "samples": [],
    }
    if reference_mapping and reference_mapping.is_file():
        mt_by_key = {str(r.get("key") or ""): r for r in rows}
        with reference_mapping.open(encoding="utf-8-sig", newline="") as fh:
            for gr in csv.DictReader(fh):
                status = str(gr.get("reference_status") or gr.get("status") or "")
                reference_text = str(
                    gr.get("reference_translation")
                    or gr.get("translation")
                    or ""
                ).strip()
                source_text = str(gr.get("source_text") or "").strip()
                match = str(gr.get("match_method") or "")
                # Supplied reference text is never copied into package output.
                reference_is_translation = bool(reference_text) and reference_text != source_text and (
                    status.startswith("translate")
                    or "vi" in status.lower()
                    or any("\u00c0" <= c <= "\u1ef9" for c in reference_text)
                )
                if not reference_is_translation:
                    continue
                # Position-only: ignore a likely mismatched reference mapping.
                if match == "position":
                    if abs(len(reference_text) - len(source_text)) > max(24, int(len(source_text) * 1.5)) and len(source_text) <= 40:
                        oracle["reference_gap_ignored_position_mismatch"] += 1
                        continue
                key = str(gr.get("key") or gr.get("key_en") or "")
                mt = mt_by_key.get(key)
                if not mt:
                    continue
                intent = _intent(mt)
                if intent == "skip_technical":
                    oracle["reference_gap_ignored_technical"] += 1
                    continue
                tr = str(mt.get("translation") or "").strip()
                if not tr:
                    oracle["reference_translated_mt_empty"] += 1
                    if len(oracle["samples"]) < 8:
                        oracle["samples"].append({"key": key, "gap": "empty", "source": source_text[:60]})
                elif tr == source_text:
                    if (
                        is_intentional_keep(mt, package_dir)
                        or has_intentional_echo(source_text)
                        or has_garbage_repetition(source_text)
                    ):
                        continue
                    oracle["reference_translated_mt_identity"] += 1
                    if len(oracle["samples"]) < 8:
                        oracle["samples"].append({"key": key, "gap": "identity", "source": source_text[:60]})
    pass_ok = (
        len(structural) == 0
        and len(garbage) == 0
        and len(identity_bad) == 0
        and len(pending) == 0
    )
    structural_pass = (
        len(structural) == 0 and len(garbage) == 0 and len(pending) == 0
    )
    review_status = classify_review_only_status(package_dir)
    strict_complete = pass_ok and review_status["review_only_unresolved"] == 0
    return {
        "package": str(package_dir),
        "rows": len(rows),
        "structural": len(structural),
        "garbage": len(garbage),
        "identity_bad": len(identity_bad),
        "pending": len(pending),
        "by_kind_pending": dict(by_kind_pending),
        "choice_coverage": {"total": choice_total, "ok": choice_ok},
        "menu_coverage": {"total": menu_total, "ok": menu_ok},
        "oracle": oracle,
        "oracle_exact_matches": oracle_exact_matches,
        "samples": {
            "structural": structural[:5],
            "garbage": garbage[:5],
            "identity_bad": identity_bad[:5],
            "pending": pending[:8],
        },
        "fail_keys": sorted(
            {
                *(x["key"] for x in structural),
                *(x["key"] for x in garbage),
                *(x["key"] for x in identity_bad),
                *(x["key"] for x in pending),
            }
        ),
        "pass": pass_ok,
        "structural_pass": structural_pass,
        "strict_complete": strict_complete,
        "review_only": review_status,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Local validate package (no MT)")
    ap.add_argument(
        "--package",
        type=Path,
        default=WORK_ROOT / "mt_pipeline_bench_strat500",
    )
    ap.add_argument(
        "--reference",
        type=Path,
        default=None,
    )
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()
    report = validate_package(
        args.package,
        reference_mapping=args.reference if args.reference and args.reference.is_file() else None,
    )
    out = args.out or (args.package / "local_validate_report.json")
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        f"local_validate structural_pass={report['structural_pass']} strict_complete={report['strict_complete']} "
        f"structural={report['structural']} garbage={report['garbage']} "
        f"identity_bad={report['identity_bad']} pending={report['pending']} "
        f"review_only_unresolved={report['review_only']['review_only_unresolved']} "
        f"fail_keys={len(report['fail_keys'])}",
        flush=True,
    )
    print(f"Wrote {out}", flush=True)
    return 0 if report["strict_complete"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
