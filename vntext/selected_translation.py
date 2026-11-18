"""Per-key selected-job accounting; package readiness is a separate fact."""
from __future__ import annotations

from vntext.mt_classify import classify_row_authoritative


def selected_outcomes(rows, keys, *, protected_keys=(), applied_keys=None):
    by_key = {str(row.get("key", "")): row for row in rows}
    protected = set(protected_keys)
    applied = None if applied_keys is None else set(applied_keys)
    outcomes = []
    for key in dict.fromkeys(keys):
        row = by_key.get(key)
        if row is None:
            status, reason = "failed", "missing_key"
        else:
            action, reason, _ = classify_row_authoritative({**row, "translation": ""})
            if key in protected:
                status, reason = "review", "manual_review_protected"
            elif action in {"skip_technical", "unsupported"}:
                status = "skipped"
            elif action == "review_only":
                status = "review"
            elif str(row.get("translation", "")).strip() and (applied is None or key in applied):
                status, reason = "applied", "translation_saved"
            else:
                status, reason = "failed", "translation_not_saved"
        outcomes.append({"key": key, "status": status, "reason": reason})
    counts = {name: sum(item["status"] == name for item in outcomes)
              for name in ("applied", "skipped", "review", "failed")}
    return outcomes, counts
