"""Đo validation trên các dòng đã có bản dịch (dùng bởi kiểm tra pipeline dịch)."""
from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from vntext.mt_check import load_whitelist
from vntext.mt_translation_safety import validate_candidate
from vntext.patch_gate import patch_skip_reason, reason_bucket

SEMANTIC_BUCKETS = frozenset({"validation"})


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
