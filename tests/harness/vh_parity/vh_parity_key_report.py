# -*- coding: utf-8 -*-
"""Key-level parity report: translation.csv vs golden_mapping.csv.

Read-only on source package. Writes artifacts under tests/golden/_work/vh_parity/.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
from collections import Counter
from datetime import datetime, timezone
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
from bootstrap import bootstrap  # noqa: E402
TESTS, ROOT, LIB = bootstrap(__file__)
sys.path.insert(0, str(TESTS / "harness" / "vh_parity"))

from vh_parity_coverage_fill import (  # noqa: E402
    GOLD,
    has_vi,
    is_localized,
    keep_reason,
    match_reliable,
    propose_fill,
    vh_is_translated,
)
from vh_parity_local_validate import text_kind, validate_package  # noqa: E402
from vntext.package_io import read_csv_rows_file  # noqa: E402
from vntext.patch_gate import load_review_only_keys  # noqa: E402
from work_paths import WORK_ROOT  # noqa: E402

OUT = WORK_ROOT / "vh_parity"
RELEASE_READ = (
    Path(os.environ["VNTEXT_RELEASE_PACKAGE"])
    if os.environ.get("VNTEXT_RELEASE_PACKAGE")
    else None
)
VI_RX = re.compile(
    r"[ÀÁẢÃẠĂẰẮẲẴẶÂẦẤẨẪẬÈÉẺẼẸÊỀẾỂỄỆÌÍỈĨỊÒÓỎÕỌÔỒỐỔỖỘƠỜỚỞỠỢÙÚỦŨỤƯỪỨỬỮỰỲÝỶỸỴĐàáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđ]"
)


def _is_choice_row(row: dict) -> bool:
    ctx = (row.get("context") or "").lower()
    meth = (row.get("import_method") or "").lower()
    return "choice" in ctx or "choice" in meth or text_kind(row) == "choice"


def classify_app_row(row: dict, review_keys: set[str]) -> str:
    key = str(row.get("key") or "")
    src = str(row.get("source_text") or "").strip()
    tr = str(row.get("translation") or "").strip()
    if key in review_keys:
        return "blocked_review_only"
    if not tr:
        return "empty"
    if tr == src:
        return "identical"
    if is_localized(tr, src):
        return "localized"
    if re.fullmatch(r"[A-Za-z0-9 \-_./'!?♡♥…]+", tr) and not VI_RX.search(tr):
        return "residual_english"
    return "other"


def audit_keys(package_dir: Path, *, golden: Path) -> dict:
    _, rows = read_csv_rows_file(package_dir / "translation.csv")
    by_key = {str(r.get("key") or ""): r for r in rows if r.get("key")}
    review_keys = load_review_only_keys(package_dir)

    line_rows: list[dict] = []
    buckets: Counter[str] = Counter()
    oracle_trusted_fill = 0
    position_unresolved = 0
    key_absent = 0

    with golden.open(encoding="utf-8-sig", newline="") as fh:
        for gr in csv.DictReader(fh):
            key = str(gr.get("key_en") or gr.get("key") or "")
            en = str(gr.get("source_en") or "").strip()
            vh = str(gr.get("text_vh") or "").strip()
            status = str(gr.get("vh_status") or "")
            match = str(gr.get("match_method") or "")
            kind = str(gr.get("text_kind") or "")

            if not vh_is_translated(status, en, vh):
                continue

            if not match_reliable(match, en, vh):
                position_unresolved += 1
                line_rows.append(
                    {
                        "bucket": "unresolved_match",
                        "key": key,
                        "en": en[:120],
                        "vh": vh[:120],
                        "match": match,
                        "reason": "position_or_unmatched",
                    }
                )
                buckets["unresolved_match"] += 1
                continue

            row = by_key.get(key)
            if not row:
                key_absent += 1
                buckets["key_absent"] += 1
                line_rows.append(
                    {"bucket": "key_absent", "key": key, "en": en[:120], "vh": vh[:120], "match": match}
                )
                continue

            src = str(row.get("source_text") or en).strip()
            tr = str(row.get("translation") or "").strip()
            app_bucket = classify_app_row(row, review_keys)

            if app_bucket == "empty" and propose_fill(src, vh, row):
                oracle_trusted_fill += 1
                line_rows.append(
                    {
                        "bucket": "oracle_vh_app_empty",
                        "key": key,
                        "en": src[:120],
                        "vh": vh[:120],
                        "app": tr,
                        "match": match,
                        "proposal": propose_fill(src, vh, row)[:120],
                    }
                )
                buckets["oracle_vh_app_empty"] += 1
                continue

            reason = keep_reason(row, src, vh, status) if app_bucket in {"identical", "residual_english", "empty"} else None
            if reason and app_bucket != "localized":
                bucket = "intentional_keep"
                buckets[bucket] += 1
                line_rows.append(
                    {
                        "bucket": bucket,
                        "key": key,
                        "en": src[:120],
                        "vh": vh[:120],
                        "app": tr[:120],
                        "reason": reason,
                        "match": match,
                    }
                )
                continue

            buckets[app_bucket] += 1
            line_rows.append(
                {
                    "bucket": app_bucket,
                    "key": key,
                    "en": src[:120],
                    "vh": vh[:120],
                    "app": tr[:120],
                    "match": match,
                    "kind": kind,
                }
            )

    # App-wide stats (all CSV rows)
    empty_all = sum(1 for r in rows if not (r.get("translation") or "").strip())
    review_count = len(review_keys)
    choice_total = sum(1 for r in rows if _is_choice_row(r))
    choice_ok = sum(
        1
        for r in rows
        if _is_choice_row(r)
        and (
            (r.get("translation") or "").strip()
            or str(r.get("key") or "") in review_keys
        )
    )
    choice_with_vi = sum(
        1 for r in rows if _is_choice_row(r) and VI_RX.search(str(r.get("translation") or ""))
    )

    validate = validate_package(package_dir, golden_mapping=golden if golden.is_file() else None)

    report = {
        "utc": datetime.now(timezone.utc).isoformat(),
        "package_dir": str(package_dir),
        "golden_mapping": str(golden),
        "translation_rows": len(rows),
        "empty_translation": empty_all,
        "review_only_keys": review_count,
        "oracle_vh_app_empty_trusted": oracle_trusted_fill,
        "position_or_unmatched": position_unresolved,
        "key_absent_in_csv": key_absent,
        "buckets": dict(buckets),
        "choice_coverage": {"total": choice_total, "ok": choice_ok, "with_vi": choice_with_vi},
        "menu_coverage": validate.get("menu_coverage"),
        "validate_pass": validate.get("pass"),
        "validate_pending": validate.get("pending") if isinstance(validate.get("pending"), int) else len(validate.get("pending") or []),
        "validate_identity_bad": validate.get("identity_bad") if isinstance(validate.get("identity_bad"), int) else len(validate.get("identity_bad") or []),
        "pass": (
            empty_all == 0
            and review_count == 0
            and buckets.get("oracle_vh_app_empty", 0) == 0
            and buckets.get("empty", 0) == 0
            and buckets.get("identical", 0) == 0
            and buckets.get("residual_english", 0) == 0
            and choice_ok == choice_total
            and validate.get("pass") is True
        ),
        "note": "PASS requires full translatable coverage; patch/crash alone is insufficient.",
    }
    return report, line_rows, validate


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--package",
        type=Path,
        default=WORK_ROOT / "vh_parity" / "work_package",
        help="Package dir (default: mirrored work copy)",
    )
    ap.add_argument("--golden", type=Path, default=GOLD)
    ap.add_argument(
        "--out-dir",
        type=Path,
        default=OUT,
        help="Evidence directory for JSON/CSV output (default: tests/golden/_work/vh_parity)",
    )
    ap.add_argument("--compare-release", action="store_true", help="Also audit Release Output read-only")
    args = ap.parse_args()
    out_dir = args.out_dir.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    pkg = args.package
    if args.compare_release:
        if RELEASE_READ is None or not (RELEASE_READ / "translation.csv").is_file():
            raise SystemExit(
                "Release package missing translation.csv: "
                "set VNTEXT_RELEASE_PACKAGE or use --package for an isolated staging package"
            )
        pkg = RELEASE_READ

    report, lines, validate = audit_keys(pkg, golden=args.golden)
    report["read_only"] = RELEASE_READ is not None and pkg.resolve() == RELEASE_READ.resolve()

    out_json = out_dir / "parity_key_report.json"
    out_json.write_text(json.dumps({**report, "validate": validate}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    out_csv = out_dir / "parity_key_lines.csv"
    with out_csv.open("w", encoding="utf-8", newline="") as fh:
        if lines:
            w = csv.DictWriter(fh, fieldnames=sorted({k for row in lines for k in row}), extrasaction="ignore")
            w.writeheader()
            w.writerows(lines)

    print(json.dumps({k: report[k] for k in report if k != "note"}, ensure_ascii=False, indent=2))
    print(f"Wrote {out_json}")
    print(f"Wrote {out_csv}")
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
