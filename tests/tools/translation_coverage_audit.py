# -*- coding: utf-8 -*-
"""Audit translation coverage against a trusted VH mapping.

This tool is read-only with respect to the package and golden inputs.  It
writes a complete per-row ledger plus aggregate JSON under the caller-provided
tests/golden/_work directory.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import Counter
from pathlib import Path


def _configure_utf8_stdio() -> None:
    """Keep the Windows CLI usable when the parent console is still CP1252."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except (OSError, ValueError):
            pass


_configure_utf8_stdio()


def _tests_lib_on_path() -> None:
    cur = Path(__file__).resolve().parent
    while cur.name != "tests" and cur.parent != cur:
        cur = cur.parent
    lib = cur / "lib"
    if str(lib) not in sys.path:
        sys.path.insert(0, str(lib))


_tests_lib_on_path()
from bootstrap import bootstrap  # noqa: E402

TESTS, ROOT, LIB = bootstrap(__file__)
sys.path.insert(0, str(TESTS / "harness" / "vh_parity"))

from vh_parity_coverage_fill import (  # noqa: E402
    has_vi,
    is_localized,
    keep_reason,
    match_reliable,
    vh_is_translated,
)
from vh_parity_local_validate import is_intentional_keep, text_kind  # noqa: E402
from vntext.package_io import read_csv_rows_file  # noqa: E402
from vntext.patch_gate import (  # noqa: E402
    load_review_only_keys,
    load_whitelist,
    patch_skip_reason,
    reason_bucket,
)

VI_RX = re.compile(
    r"[ÀÁẢÃẠĂẰẮẲẴẶÂẦẤẨẪẬÈÉẺẼẸÊỀẾỂỄỆÌÍỈĨỊÒÓỎÕỌÔỒỐỔỖỘƠỜỚỞỠỢÙÚỦŨỤƯỪỨỬỮỰỲÝỶỸỴĐ"
    r"àáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđ]"
)


def _golden_rows(golden: Path) -> list[dict]:
    rows: list[dict] = []
    with golden.open(encoding="utf-8-sig", newline="") as handle:
        rows.extend(csv.DictReader(handle))
    return rows


def _golden_by_key(golden_rows: list[dict]) -> dict[str, dict]:
    """Select one representative per key while preserving raw rows for audit."""
    out: dict[str, dict] = {}
    rank = {"unmatched_en": 0, "position": 1, "locator": 2, "key": 3}
    for row in golden_rows:
        key = str(row.get("key_en") or row.get("key") or "").strip()
        if not key:
            continue
        current = out.get(key)
        if current is None or rank.get(str(row.get("match_method") or ""), 0) > rank.get(
            str(current.get("match_method") or ""), 0
        ):
            out[key] = row
    return out


def _technical_rows(package: Path) -> list[dict]:
    path = package / "technical_skipped.csv"
    if not path.is_file():
        return []
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _app_bucket(row: dict, review_keys: set[str], whitelist: set[str], golden: dict[str, dict], package: Path) -> tuple[str, str]:
    key = str(row.get("key") or "")
    src = str(row.get("source_text") or "").strip()
    tr = str(row.get("translation") or "").strip()
    if key in review_keys:
        return "blocked_review_only", "review_only.csv"
    if not tr:
        return "empty", "translation is empty"
    reason = patch_skip_reason(row, tr, whitelist)
    if reason:
        return "blocked", reason
    if tr == src:
        keep = is_intentional_keep(row, package)
        gr = golden.get(key) or {}
        if not keep and str(gr.get("vh_status") or "") == "keep_en_intentional":
            keep = True
            reason = "vh_oracle_keep_en_intentional"
        if keep:
            return "intentional_keep", reason or "classifier_keep"
        return "identical", "translation equals source"
    if is_localized(tr, src):
        return "localized", ""
    if re.fullmatch(r"[A-Za-z0-9 \-_./'!?♡♥…]+", tr) and not VI_RX.search(tr):
        return "residual_english", "no Vietnamese marker"
    if has_vi(tr):
        return "localized", "Vietnamese marker"
    return "other", "non-empty but not classified as localized"


def audit(package: Path, golden: Path, out_dir: Path) -> dict:
    fields, rows = read_csv_rows_file(package / "translation.csv")
    rows_by_key = {str(row.get("key") or ""): row for row in rows if row.get("key")}
    review_keys = load_review_only_keys(package)
    whitelist = load_whitelist(package)
    golden_rows = _golden_rows(golden)
    golden_by_key = _golden_by_key(golden_rows)
    ledger: list[dict] = []
    app_counts: Counter[str] = Counter()

    for row in rows:
        bucket, reason = _app_bucket(row, review_keys, whitelist, golden_by_key, package)
        app_counts[bucket] += 1
        gr = golden_by_key.get(str(row.get("key") or ""), {})
        ledger.append(
            {
                "scope": "package",
                "bucket": bucket,
                "key": row.get("key", ""),
                "source": str(row.get("source_text") or ""),
                "app_translation": str(row.get("translation") or ""),
                "vh_translation": str(gr.get("text_vh") or ""),
                "match": str(gr.get("match_method") or ""),
                "vh_status": str(gr.get("vh_status") or ""),
                "kind": text_kind(row),
                "reason": reason,
            }
        )

    tech = _technical_rows(package)
    tech_reasons = Counter()
    for row in tech:
        note = str(row.get("patch_note") or "")
        tech_reasons[note.split(":", 1)[-1].strip() if ":" in note else note] += 1
        ledger.append(
            {
                "scope": "technical_skipped",
                "bucket": "technical_skipped",
                "key": row.get("key", ""),
                "source": str(row.get("source_text") or ""),
                "app_translation": "",
                "vh_translation": "",
                "match": "",
                "vh_status": "",
                "kind": "technical",
                "reason": note,
            }
        )

    for bucket in (
        "empty",
        "identical",
        "residual_english",
        "blocked_review_only",
        "blocked",
        "intentional_keep",
        "localized",
    ):
        app_counts.setdefault(bucket, 0)

    golden_counts: Counter[str] = Counter()
    reliable_count = 0
    for gr in golden_rows:
        en = str(gr.get("source_en") or "").strip()
        vh = str(gr.get("text_vh") or "").strip()
        status = str(gr.get("vh_status") or gr.get("status") or "")
        match = str(gr.get("match_method") or "")
        if not vh_is_translated(status, en, vh):
            continue
        if match == "position":
            golden_counts["position_mismatch"] += 1
            continue
        if not match_reliable(match, en, vh):
            golden_counts["unmatched"] += 1
            continue
        reliable_count += 1
        key = str(gr.get("key_en") or gr.get("key") or "")
        row = rows_by_key.get(key)
        if not row:
            golden_counts["key_absent"] += 1
            continue
        src = str(row.get("source_text") or en).strip()
        tr = str(row.get("translation") or "").strip()
        if not tr:
            golden_counts["empty"] += 1
        elif tr == src:
            reason = keep_reason(row, src, vh, status)
            golden_counts["intentional_keep" if reason or status == "keep_en_intentional" else "identical"] += 1
        elif is_localized(tr, src):
            golden_counts["localized"] += 1
        elif has_vi(tr):
            golden_counts["localized"] += 1
        else:
            golden_counts["residual_english"] += 1

    for bucket in ("empty", "identical", "residual_english", "intentional_keep", "position_mismatch", "unmatched", "key_absent"):
        golden_counts.setdefault(bucket, 0)

    out_dir.mkdir(parents=True, exist_ok=True)
    ledger_path = out_dir / "phase1_audit_ledger.csv"
    ledger_fields = [
        "scope", "bucket", "key", "source", "app_translation", "vh_translation",
        "match", "vh_status", "kind", "reason",
    ]
    with ledger_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=ledger_fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(ledger)

    report = {
        "package": str(package),
        "golden": str(golden),
        "translation_rows": len(rows),
        "technical_skipped_rows": len(tech),
        "technical_reasons": dict(tech_reasons),
        "app_buckets": dict(app_counts),
        "golden_vh_buckets": dict(golden_counts),
        "golden_reliable_translated_rows": reliable_count,
        "position_mismatch": golden_counts.get("position_mismatch", 0),
        "review_only": len(review_keys),
        "ledger_rows": len(ledger),
        "pass": (
            app_counts.get("empty", 0) == 0
            and app_counts.get("blocked_review_only", 0) == 0
            and app_counts.get("blocked", 0) == 0
            and app_counts.get("identical", 0) == 0
            and app_counts.get("residual_english", 0) == 0
            and app_counts.get("other", 0) == 0
        ),
        "ledger": str(ledger_path),
        "read_only_inputs": True,
    }
    report_path = out_dir / "phase1_audit.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"Wrote {report_path}")
    print(f"Wrote {ledger_path}")
    return report


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--package", type=Path, required=True)
    ap.add_argument("--golden", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, required=True)
    args = ap.parse_args()
    report = audit(args.package.resolve(), args.golden.resolve(), args.out_dir.resolve())
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
