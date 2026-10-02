"""CSV editor API for WPF — load/save/validate/bulk-fix translation.csv (UTF-8 BOM)."""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import Any

from vntext.package_io import backup_translation_csv, read_csv_rows_file, write_csv_rows_file
from vntext.patch_gate import (
    REASON_LABELS_VI,
    load_review_only_issue_reasons,
    load_review_only_keys,
    patch_skip_reason,
    reason_bucket,
    reason_label_vi,
)
from vntext.mt_check import load_whitelist, structural_problems

BATCH_SEMANTIC_ONLY = frozenset(
    {
        "validation",
    }
)

BATCH_STRUCTURAL_BUCKETS = frozenset(
    {
        "garbage_repetition",
        "html_garbage",
        "review_only",
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


def load_document(csv_path: str | Path) -> dict[str, Any]:
    csv_path = Path(csv_path).resolve()
    if not csv_path.is_file():
        raise FileNotFoundError(str(csv_path))
    fields, rows = read_csv_rows_file(csv_path)
    package_dir = csv_path.parent
    review_keys = sorted(load_review_only_keys(package_dir))
    return {
        "ok": True,
        "csv_path": str(csv_path),
        "fields": fields,
        "rows": rows,
        "review_keys": review_keys,
        "row_count": len(rows),
    }


def save_document(csv_path: str | Path, fields: list[str], rows: list[dict]) -> dict[str, Any]:
    csv_path = Path(csv_path).resolve()
    required = {"key", "source_text", "translation"}
    field_set = set(fields or [])
    if not required.issubset(field_set):
        missing = sorted(required - field_set)
        return {"ok": False, "error": f"Thiếu cột bắt buộc: {', '.join(missing)}"}
    if not rows:
        return {"ok": False, "error": "CSV không có dòng dữ liệu"}
    keys = [str(r.get("key") or "").strip() for r in rows]
    if any(not k for k in keys):
        return {"ok": False, "error": "Có dòng thiếu key"}
    if len(set(keys)) != len(keys):
        return {"ok": False, "error": "Trùng key trong CSV"}
    backup_path = backup_translation_csv(csv_path)
    _atomic_write_csv(csv_path, fields, rows)
    _fields, saved_rows = read_csv_rows_file(csv_path)
    review_pruned = _reconcile_saved_review_rows(csv_path, saved_rows)
    return {
        "ok": True,
        "csv_path": str(csv_path),
        "row_count": len(rows),
        "backup_path": str(backup_path),
        "review_pruned": review_pruned,
    }


def _reconcile_saved_review_rows(csv_path: Path, rows: list[dict]) -> int:
    """Remove only gate-valid manual translations from the existing review ledger."""

    from vntext.mt_ct2_status import _prune_resolved_review_only

    return _prune_resolved_review_only(
        csv_path.parent,
        rows,
        allow_human_review_resolution=True,
    )


def _atomic_write_csv(csv_path: Path, fields: list[str], rows: list[dict]) -> None:
    """Write a CSV without leaving a partially-written user file behind."""
    tmp = csv_path.with_name(f".{csv_path.name}.{os.getpid()}.tmp")
    try:
        write_csv_rows_file(tmp, fields, rows)
        os.replace(tmp, csv_path)
    finally:
        try:
            tmp.unlink()
        except FileNotFoundError:
            pass


def _replace_case_insensitive(text: str, needle: str, replacement: str) -> tuple[str, int]:
    if not needle:
        return text, 0
    rx = re.compile(re.escape(needle), re.IGNORECASE)
    return rx.subn(lambda _m: replacement, text)


def preview_replace_translation(
    rows: list[dict],
    find_text: str,
    replacement: str,
    keys: list[str] | None = None,
) -> dict[str, Any]:
    """Preview replacement in translation only; source_text is never a target."""
    if not str(find_text or ""):
        return {"ok": False, "error": "Chuỗi tìm không được để trống"}
    key_filter = {str(k) for k in (keys or []) if str(k)}
    matched: list[str] = []
    replacements = 0
    for row in rows:
        key = str(row.get("key") or "")
        if not key or (key_filter and key not in key_filter):
            continue
        _new, count = _replace_case_insensitive(str(row.get("translation") or ""), find_text, replacement)
        if count:
            matched.append(key)
            replacements += count
    return {
        "ok": True,
        "count": len(matched),
        "replacement_count": replacements,
        "keys": matched,
        "scope": "filtered" if key_filter else "all",
        "action": "replace_translation",
    }


def replace_translation(
    csv_path: str | Path,
    fields: list[str],
    rows: list[dict],
    find_text: str,
    replacement: str,
    keys: list[str] | None = None,
    *,
    dry_run: bool = False,
) -> dict[str, Any]:
    csv_path = Path(csv_path).resolve()
    preview = preview_replace_translation(rows, find_text, replacement, keys)
    if not preview.get("ok") or dry_run:
        return {**preview, "dry_run": dry_run}
    if not preview["keys"]:
        return {**preview, "dry_run": False, "message": "Không tìm thấy chuỗi trong cột bản dịch."}

    # Validate before and after.  A failed post-write validation restores the
    # exact pre-operation bytes from the backup.
    before = validate_document(csv_path, rows)
    if not before.get("ok"):
        return {"ok": False, "error": before.get("error") or "CSV hiện tại không hợp lệ"}
    backup_path = backup_translation_csv(csv_path)
    selected = set(preview["keys"])
    for row in rows:
        if str(row.get("key") or "") not in selected:
            continue
        row["translation"], _ = _replace_case_insensitive(
            str(row.get("translation") or ""), find_text, replacement
        )
    try:
        _atomic_write_csv(csv_path, fields, rows)
        validation = validate_document(csv_path, rows)
        if not validation.get("ok"):
            raise ValueError(validation.get("error") or "Validate sau khi thay thế thất bại")
        _fields, saved_rows = read_csv_rows_file(csv_path)
        review_pruned = _reconcile_saved_review_rows(csv_path, saved_rows)
    except Exception as exc:
        try:
            _atomic_write_csv(csv_path, fields, read_csv_rows_file(backup_path)[1])
        except Exception:
            pass
        return {"ok": False, "error": str(exc), "backup_path": str(backup_path), "rolled_back": True}
    return {
        **preview,
        "dry_run": False,
        "backup_path": str(backup_path),
        "summary": f"Đã thay {preview['replacement_count']} lần trong {preview['count']} dòng; {validation['summary']}",
        "review_pruned": review_pruned,
        **{k: validation[k] for k in ("patch_eligible", "patch_blocked", "batch_actionable", "issues_by_key", "issues_display")},
    }


def restore_backup(csv_path: str | Path, backup_path: str | Path) -> dict[str, Any]:
    csv_path = Path(csv_path).resolve()
    backup = Path(backup_path).resolve()
    if not backup.is_file():
        return {"ok": False, "error": "Không tìm thấy file backup để undo"}
    fields, rows = read_csv_rows_file(backup)
    if not rows:
        return {"ok": False, "error": "File backup không có dữ liệu"}
    _atomic_write_csv(csv_path, fields, rows)
    return {"ok": True, "csv_path": str(csv_path), "row_count": len(rows), "restored_from": str(backup)}


def _row_entry(row: dict) -> dict:
    return {
        "source_text": str(row.get("source_text") or ""),
        "context": str(row.get("context") or ""),
        "file_path": str(row.get("file_path") or ""),
        "import_method": str(row.get("import_method") or ""),
    }


def reason_label_vi(reason: str) -> str:
    from vntext.patch_gate import reason_label_vi as _label

    return _label(reason)


def compute_row_reason(
    row: dict,
    review_keys: set[str],
    whitelist: set[str],
    review_issue_reasons: dict[str, str] | None = None,
) -> str:
    key = str(row.get("key") or "")
    trans = str(row.get("translation") or "")
    if review_issue_reasons and key in review_issue_reasons:
        return review_issue_reasons[key]
    if key in review_keys:
        return "review_only"
    if not trans.strip():
        return "no_translation"
    entry = _row_entry(row)
    entry["key"] = key
    structural = structural_problems(entry, trans)
    if structural:
        return reason_bucket(structural[0])
    reason = patch_skip_reason(entry, trans, whitelist) or ""
    if reason:
        return reason_bucket(reason)
    return ""


def is_batch_actionable(reason: str) -> bool:
    """Chỉ dòng có lỗi cấu trúc chắc chắn — không gồm validation ngữ nghĩa thuần."""
    if not reason or reason in {"no_translation", ""}:
        return False
    bucket = reason_bucket(reason)
    if bucket in BATCH_SEMANTIC_ONLY:
        return False
    if bucket in BATCH_STRUCTURAL_BUCKETS:
        return True
    lowered = bucket.lower()
    return "tag" in lowered or "placeholder" in lowered


def build_issues_by_key(rows: list[dict], package_dir: Path) -> dict[str, str]:
    review_keys = load_review_only_keys(package_dir)
    review_issue_reasons = load_review_only_issue_reasons(package_dir)
    whitelist = load_whitelist(package_dir)
    issues: dict[str, str] = {}
    for row in rows:
        key = str(row.get("key") or "")
        if not key:
            continue
        reason = compute_row_reason(row, review_keys, whitelist, review_issue_reasons)
        if reason:
            issues[key] = reason
    return issues


def _gate_counts(rows: list[dict], issues_by_key: dict[str, str]) -> dict[str, int]:
    eligible = 0
    blocked = 0
    actionable = 0
    for row in rows:
        key = str(row.get("key") or "")
        trans = str(row.get("translation") or "").strip()
        reason = issues_by_key.get(key, "")
        if reason and reason != "no_translation":
            blocked += 1
            if is_batch_actionable(reason):
                actionable += 1
        elif trans:
            eligible += 1
    return {
        "patch_eligible": eligible,
        "patch_blocked": blocked,
        "batch_actionable": actionable,
    }


def validate_document(csv_path: str | Path, rows: list[dict] | None = None) -> dict[str, Any]:
    csv_path = Path(csv_path).resolve()
    package_dir = csv_path.parent
    if rows is None:
        _, rows = read_csv_rows_file(csv_path)

    issues_by_key = build_issues_by_key(rows, package_dir)
    issues_display = {k: reason_label_vi(v) for k, v in issues_by_key.items()}
    counts: dict[str, int] = {}
    for reason in issues_by_key.values():
        counts[reason] = counts.get(reason, 0) + 1

    issues: list[dict[str, str]] = []
    for key, reason in issues_by_key.items():
        if len(issues) >= 200:
            break
        row = next((r for r in rows if str(r.get("key") or "") == key), {})
        trans = str(row.get("translation") or "")
        issues.append(
            {
                "key": key,
                "reason": reason,
                "reason_label": issues_display.get(key, reason),
                "source_text": str(row.get("source_text") or "")[:80],
                "translation": trans[:80],
            }
        )

    gate = _gate_counts(rows, issues_by_key)
    hard = [c for c in counts if c not in {"no_translation", "review_only"}]
    summary = _format_validate_summary(counts, gate)
    return {
        "ok": True,
        "issue_count": sum(counts.values()),
        "reason_counts": counts,
        "issues": issues,
        "issues_by_key": issues_by_key,
        "issues_display": issues_display,
        "has_warnings": len(hard) > 0,
        "summary": summary,
        "patch_eligible": gate["patch_eligible"],
        "patch_blocked": gate["patch_blocked"],
        "batch_actionable": gate["batch_actionable"],
    }


def _format_validate_summary(counts: dict[str, int], gate: dict[str, int]) -> str:
    base = f"Hợp lệ {gate['patch_eligible']}, bị chặn {gate['patch_blocked']}"
    if gate["batch_actionable"]:
        base += f", có thể xử lý hàng loạt {gate['batch_actionable']}"
    if not counts:
        return base + " — không phát hiện lỗi cấu trúc trên các dòng có bản dịch."
    parts = [f"{reason_label_vi(k)}: {v}" for k, v in sorted(counts.items(), key=lambda x: -x[1])]
    return base + ". " + "; ".join(parts[:8])


def backup_document(csv_path: str | Path) -> dict[str, Any]:
    csv_path = Path(csv_path).resolve()
    dest = backup_translation_csv(csv_path)
    return {"ok": True, "backup_path": str(dest)}


def _resolve_target_keys(
    rows: list[dict],
    issues_by_key: dict[str, str],
    keys: list[str] | None,
    *,
    require_translation: bool,
    require_actionable: bool,
) -> list[str]:
    key_filter = {k for k in (keys or []) if k}
    targets: list[str] = []
    for row in rows:
        key = str(row.get("key") or "")
        if not key:
            continue
        if key_filter and key not in key_filter:
            continue
        reason = issues_by_key.get(key, "")
        if require_actionable and not is_batch_actionable(reason):
            continue
        if require_translation and not str(row.get("translation") or "").strip():
            continue
        if not key_filter and require_actionable and not reason:
            continue
        if not key_filter and not require_actionable and not reason:
            continue
        targets.append(key)
    return targets


def preview_clear_blocked(
    csv_path: str | Path,
    rows: list[dict],
    keys: list[str] | None = None,
) -> dict[str, Any]:
    csv_path = Path(csv_path).resolve()
    issues_by_key = build_issues_by_key(rows, csv_path.parent)
    targets = _resolve_target_keys(
        rows,
        issues_by_key,
        keys,
        require_translation=True,
        require_actionable=True,
    )
    return {
        "ok": True,
        "count": len(targets),
        "keys": targets,
        "action": "clear_blocked",
    }


def clear_blocked_translations(
    csv_path: str | Path,
    fields: list[str],
    rows: list[dict],
    keys: list[str] | None = None,
    *,
    dry_run: bool = False,
) -> dict[str, Any]:
    csv_path = Path(csv_path).resolve()
    preview = preview_clear_blocked(csv_path, rows, keys)
    targets = set(preview["keys"])
    if not targets:
        return {
            "ok": True,
            "count": 0,
            "keys": [],
            "dry_run": dry_run,
            "message": "Không có dòng lỗi cấu trúc nào có bản dịch để xóa.",
        }
    if dry_run:
        return {**preview, "dry_run": True}

    backup_path = backup_translation_csv(csv_path)
    for row in rows:
        if str(row.get("key") or "") in targets:
            row["translation"] = ""
    write_csv_rows_file(csv_path, fields, rows)
    validation = validate_document(csv_path, rows)
    return {
        "ok": True,
        "count": len(targets),
        "keys": sorted(targets),
        "backup_path": str(backup_path),
        "dry_run": False,
        **{k: validation[k] for k in ("summary", "patch_eligible", "patch_blocked", "batch_actionable", "issues_by_key", "issues_display")},
    }


def preview_retranslate(
    csv_path: str | Path,
    rows: list[dict],
    keys: list[str] | None = None,
) -> dict[str, Any]:
    csv_path = Path(csv_path).resolve()
    issues_by_key = build_issues_by_key(rows, csv_path.parent)
    key_filter = {k for k in (keys or []) if k}
    targets: list[str] = []
    for row in rows:
        key = str(row.get("key") or "")
        if not key:
            continue
        if not str(row.get("source_text") or "").strip():
            continue
        reason = issues_by_key.get(key, "")
        if key_filter:
            if key not in key_filter:
                continue
            targets.append(key)
            continue
        if is_batch_actionable(reason):
            targets.append(key)
    return {
        "ok": True,
        "count": len(targets),
        "keys": targets,
        "action": "retranslate",
    }


def retranslate_blocked_keys(
    csv_path: str | Path,
    keys: list[str],
    *,
    dry_run: bool = False,
) -> dict[str, Any]:
    from vntext.mt_ct2 import run_ct2_translate_keys

    csv_path = Path(csv_path).resolve()
    _, rows = read_csv_rows_file(csv_path)
    preview = preview_retranslate(csv_path, rows, keys)
    target_keys = preview["keys"]
    if not target_keys:
        return {
            "ok": True,
            "count": 0,
            "keys": [],
            "dry_run": dry_run,
            "message": "Không có dòng lỗi cấu trúc nào để dịch lại.",
        }
    if dry_run:
        return {**preview, "dry_run": True}

    backup_path = backup_translation_csv(csv_path)
    result = run_ct2_translate_keys(
        csv_path,
        target_keys,
        allow_overwrite=True,
        backup=False,
    )
    validation = validate_document(csv_path)
    return {
        "ok": bool(result.get("ok")),
        "count": len(target_keys),
        "keys": target_keys,
        "backup_path": str(backup_path),
        "dry_run": False,
        "applied": int(result.get("applied") or 0),
        "blocked": int(result.get("blocked") or 0),
        "summary": validation.get("summary") or result.get("summary") or "",
        "patch_eligible": validation.get("patch_eligible", 0),
        "patch_blocked": validation.get("patch_blocked", 0),
        "batch_actionable": validation.get("batch_actionable", 0),
        "issues_by_key": validation.get("issues_by_key", {}),
        "issues_display": validation.get("issues_display", {}),
        "error": result.get("error") or "",
    }


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="translation.csv editor API")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_load = sub.add_parser("load")
    p_load.add_argument("csv_path", type=Path)

    p_save = sub.add_parser("save")
    p_save.add_argument("csv_path", type=Path)
    p_save.add_argument("--payload", type=Path, help="JSON file with fields+rows")

    p_val = sub.add_parser("validate")
    p_val.add_argument("csv_path", type=Path)
    p_val.add_argument("--payload", type=Path)

    p_backup = sub.add_parser("backup")
    p_backup.add_argument("csv_path", type=Path)

    def add_payload_arg(p):
        p.add_argument("csv_path", type=Path)
        p.add_argument("--payload", type=Path)
        p.add_argument("--keys", type=Path, help="JSON array of keys")
        p.add_argument("--dry-run", action="store_true")

    p_prev_clear = sub.add_parser("preview-clear")
    add_payload_arg(p_prev_clear)

    p_clear = sub.add_parser("clear-blocked")
    add_payload_arg(p_clear)

    p_prev_rt = sub.add_parser("preview-retranslate")
    add_payload_arg(p_prev_rt)

    p_rt = sub.add_parser("retranslate")
    add_payload_arg(p_rt)

    def add_replace_arg(p):
        p.add_argument("csv_path", type=Path)
        p.add_argument("--payload", type=Path)
        p.add_argument("--keys", type=Path, help="JSON array of keys; omit for all rows")
        p.add_argument("--find", required=True)
        p.add_argument("--replace", default="")
        p.add_argument("--dry-run", action="store_true")

    p_prev_replace = sub.add_parser("preview-replace")
    add_replace_arg(p_prev_replace)
    p_replace = sub.add_parser("replace")
    add_replace_arg(p_replace)

    p_undo = sub.add_parser("undo")
    p_undo.add_argument("csv_path", type=Path)
    p_undo.add_argument("backup_path", type=Path)

    args = parser.parse_args()
    try:
        if args.cmd == "load":
            result = load_document(args.csv_path)
        elif args.cmd == "save":
            if not args.payload or not args.payload.is_file():
                raise ValueError("save requires --payload JSON file")
            payload = json.loads(args.payload.read_text(encoding="utf-8"))
            result = save_document(args.csv_path, payload.get("fields") or [], payload.get("rows") or [])
        elif args.cmd == "backup":
            result = backup_document(args.csv_path)
        elif args.cmd in {"preview-clear", "clear-blocked", "preview-retranslate", "retranslate"}:
            rows = None
            keys = None
            if args.payload and args.payload.is_file():
                payload = json.loads(args.payload.read_text(encoding="utf-8"))
                rows = payload.get("rows")
                fields = payload.get("fields") or []
            else:
                fields = []
            if args.keys and args.keys.is_file():
                keys = json.loads(args.keys.read_text(encoding="utf-8"))
            if rows is None:
                _, rows = read_csv_rows_file(args.csv_path)
            if args.cmd == "preview-clear":
                result = preview_clear_blocked(args.csv_path, rows, keys)
            elif args.cmd == "clear-blocked":
                result = clear_blocked_translations(
                    args.csv_path,
                    fields,
                    rows,
                    keys,
                    dry_run=bool(args.dry_run),
                )
            elif args.cmd == "preview-retranslate":
                result = preview_retranslate(args.csv_path, rows, keys)
            else:
                if not keys:
                    preview = preview_retranslate(args.csv_path, rows, None)
                    keys = preview["keys"]
                result = retranslate_blocked_keys(args.csv_path, keys or [], dry_run=bool(args.dry_run))
        elif args.cmd in {"preview-replace", "replace"}:
            rows = None
            fields = []
            if args.payload and args.payload.is_file():
                payload = json.loads(args.payload.read_text(encoding="utf-8"))
                rows = payload.get("rows")
                fields = payload.get("fields") or []
            if rows is None:
                fields, rows = read_csv_rows_file(args.csv_path)
            keys = None
            if args.keys and args.keys.is_file():
                keys = json.loads(args.keys.read_text(encoding="utf-8"))
            if args.cmd == "preview-replace":
                result = preview_replace_translation(rows, args.find, args.replace, keys)
            else:
                result = replace_translation(
                    args.csv_path, fields, rows, args.find, args.replace, keys,
                    dry_run=bool(args.dry_run),
                )
        elif args.cmd == "undo":
            result = restore_backup(args.csv_path, args.backup_path)
        else:
            rows = None
            if args.payload and args.payload.is_file():
                payload = json.loads(args.payload.read_text(encoding="utf-8"))
                rows = payload.get("rows")
            result = validate_document(args.csv_path, rows)
    except Exception as exc:
        result = {"ok": False, "error": str(exc)}
    sys.stdout.write(json.dumps(result, ensure_ascii=False) + "\n")
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
