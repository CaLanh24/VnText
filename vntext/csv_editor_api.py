"""CSV editor API for WPF — load/save/validate/bulk-fix translation.csv (UTF-8 BOM)."""
from __future__ import annotations

import json
import hashlib
import csv
import io
import os
import re
import sys
from pathlib import Path
from typing import Any

from vntext.package_io import CSV_FIELDS, backup_translation_csv, read_csv_rows_file, write_csv_rows_file
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


def _read_editor_csv_bytes(raw: bytes) -> tuple[list[str], list[dict]]:
    try:
        with io.TextIOWrapper(io.BytesIO(raw), encoding="utf-8-sig", newline="") as handle:
            records = csv.reader(handle, strict=True)
            source_fields = next(records, [])
            if (not {"key", "source_text", "translation"}.issubset(source_fields)
                    or any(not field or field != field.strip() for field in source_fields)
                    or len({field.casefold() for field in source_fields}) != len(source_fields)):
                raise ValueError("Header CSV thiếu cột bắt buộc, trùng hoặc không hợp lệ")
            rows = []
            for number, record in enumerate(records, 2):
                if not record:
                    continue
                if len(record) != len(source_fields):
                    raise ValueError(f"Dòng CSV {number} có số cột không khớp header")
                rows.append(dict(zip(source_fields, record)))
    except csv.Error as exc:
        raise ValueError(f"CSV không hợp lệ: {exc}") from exc
    except UnicodeDecodeError as exc:
        raise ValueError("CSV không dùng UTF-8 hợp lệ") from exc
    fields = list(source_fields)
    for field in CSV_FIELDS:
        if field not in fields:
            fields.append(field)
    for row in rows:
        for field in fields:
            row.setdefault(field, "")
    keys = [row["key"] for row in rows]
    if any(not key.strip() for key in keys) or len(set(keys)) != len(keys):
        raise ValueError("CSV có key trống hoặc trùng")
    return fields, rows


def _read_editor_csv(csv_path: Path) -> tuple[list[str], list[dict]]:
    return _read_editor_csv_bytes(csv_path.read_bytes())


def load_document(csv_path: str | Path) -> dict[str, Any]:
    csv_path = Path(csv_path).resolve()
    if not csv_path.is_file():
        raise FileNotFoundError(str(csv_path))
    raw = csv_path.read_bytes()
    fields, rows = _read_editor_csv_bytes(raw)
    source_sha256 = hashlib.sha256(raw).hexdigest()
    package_dir = csv_path.parent
    review_keys = sorted(load_review_only_keys(package_dir))
    return {
        "ok": True,
        "csv_path": str(csv_path),
        "fields": fields,
        "rows": rows,
        "review_keys": review_keys,
        "row_count": len(rows),
        "source_sha256": source_sha256,
    }


def _reviewed_memory_snapshot(csv_path: Path) -> dict:
    """Bind preview to disk authority, approval state and validation inputs."""
    package=csv_path.parent
    names=('manifest.json','.mt/translation_memory.json','.mt/translation_memory_scope.json',
           '.mt/translation_memory_decisions.json','.mt/glossary.json','.mt/v2/glossary.json',
           '.mt/whitelist.json')
    paths={'csv':csv_path,**{name:package/name for name in names}}
    result={}
    for name,path in paths.items():
        for ancestor in (path,*path.parents):
            if ancestor==package.parent:
                break
            if ancestor.exists() and getattr(ancestor.lstat(),'st_file_attributes',0)&0x400:
                raise ValueError('Không dùng dữ liệu gói qua reparse point')
        if path.is_symlink():
            raise ValueError('Không dùng file liên kết để duyệt bản dịch')
        if path.exists() and not path.is_file():
            raise ValueError('Dữ liệu gói không hợp lệ')
        if path.is_file() and path.stat().st_size>32*1024*1024:
            raise ValueError('Dữ liệu duyệt vượt giới hạn an toàn')
        result[name]=hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None
    return result


def preview_reviewed_memory(csv_path: str | Path, keys: list[str]) -> dict[str, Any]:
    """Read-only preview; selection identifies saved rows, never target text."""
    from vntext.mt_memory import load_translation_memory,_strict_requested,_package_binding
    from vntext.glossary_v2 import candidate_term_issues,load_compatible_entries
    from vntext.mt_translation_safety import validate_candidate
    try:
        raw=Path(csv_path)
        if raw.is_symlink() or raw.parent.is_symlink() or (raw.parent/'.mt').is_symlink():
            raise ValueError('Không dùng đường dẫn liên kết để duyệt bản dịch')
        csv_path=raw.resolve();package=csv_path.parent
        if csv_path.name!='translation.csv' or not (package/'manifest.json').is_file():
            raise ValueError('Hãy mở translation.csv trong gói đã extract')
        if (not isinstance(keys,list) or not keys or len(keys)>1000
                or any(not isinstance(key,str) or not key for key in keys) or len(set(keys))!=len(keys)):
            raise ValueError('Chọn từ 1 đến 1000 dòng khác nhau để duyệt')
        before=_reviewed_memory_snapshot(csv_path)
        _fields,rows=_read_editor_csv(csv_path)
        by_key={row['key']:row for row in rows}
        if any(key not in by_key for key in keys):
            raise ValueError('Dòng đã chọn không còn trong CSV đã lưu')
        memory=load_translation_memory(package)
        strict=_strict_requested(package)
        if strict and memory.get('scope_error'):
            raise ValueError('Bộ nhớ đã duyệt bị thiếu hoặc không hợp lệ; không tự sửa')
        if not strict and before['.mt/translation_memory.json'] is not None:
            legacy=json.loads((package/'.mt/translation_memory.json').read_text(encoding='utf-8'))
            if (not isinstance(legacy,dict) or legacy.get('version')!='1.0.0'
                    or not isinstance(legacy.get('entries'),list)
                    or any(not isinstance(e,dict) or any(not isinstance(e.get(k),str) for k in
                           ('source','translation','context_family','import_method')) for e in legacy['entries'])):
                raise ValueError('Bộ nhớ cũ không hợp lệ; không tự chuyển đổi')
        glossary=load_compatible_entries(package);whitelist=load_whitelist(package)
        scope_fields=('source_text','file_path','context','import_method')
        scope_counts={}
        for row in rows:
            identity=tuple(row.get(k,'') for k in scope_fields)
            scope_counts[identity]=scope_counts.get(identity,0)+1
        selected=[];seen=set()
        for key in keys:
            row=by_key[key]
            if any(not str(row.get(k) or '').strip() for k in
                   ('source_text','translation','file_path','context','import_method')):
                raise ValueError('Dòng duyệt phải có nguồn, bản dịch, file và ngữ cảnh đầy đủ')
            scope=tuple(row[k] for k in ('source_text','file_path','context','import_method'))
            if scope in seen:
                raise ValueError('Có nhiều dòng cùng phạm vi; cần xử lý trước khi duyệt')
            seen.add(scope)
            # Reject ambiguity outside the selection too; keys alone are not a scope.
            if scope_counts[scope]!=1:
                raise ValueError('Phạm vi của dòng không duy nhất trong gói')
            reasons=list(validate_candidate(row,row['translation'],whitelist))
            reasons+=candidate_term_issues(row['source_text'],row,row['translation'],glossary)
            if reasons:
                raise ValueError('Bản dịch chưa qua kiểm tra: '+'; '.join(map(str,reasons)))
            for entry in memory.get('entries',[]) if strict else []:
                if all(row[field]==entry[exact] for field,exact in
                       (('source_text','source_text_exact'),('file_path','file_path_exact'),
                        ('context','context_exact'),('import_method','import_method'))):
                    if row['translation']!=entry['translation']:
                        raise ValueError('Phạm vi đã có bản dịch được duyệt khác; không tự thay thế')
            selected.append({name:row[name] for name in
                             ('key','source_text','translation','file_path','context','import_method')})
        if _reviewed_memory_snapshot(csv_path)!=before:
            raise ValueError('CSV hoặc dữ liệu gói vừa đổi; hãy xem trước lại')
        token_data=dict(version=1,package_binding=_package_binding(package),keys=keys,rows=selected,snapshot=before)
        token=hashlib.sha256(json.dumps(token_data,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode('utf-8')).hexdigest()
        return dict(ok=True,rows=selected,count=len(selected),preview_token=token,
                    _snapshot=before,
                    converts_legacy=not strict and before['.mt/translation_memory.json'] is not None,
                    scope_summary='Chỉ gói hiện tại và đúng nguồn, file, ngữ cảnh, cách nhập; không dùng cho gói khác.')
    except (OSError,ValueError,TypeError,KeyError) as error:
        return dict(ok=False,error=str(error))


def confirm_reviewed_memory(csv_path: str | Path, keys: list[str], preview_token: str) -> dict[str, Any]:
    """Explicit UI confirmation; obtain ownership then recompute disk preview."""
    import uuid
    from vntext.mt_memory import activate_reviewed_memory
    lock=None;owned=None
    try:
        # Validate without writes before creating the ownership marker.
        preview=preview_reviewed_memory(csv_path,keys)
        if not preview.get('ok') or preview.get('preview_token')!=preview_token:
            return dict(ok=False,error=preview.get('error') or 'Dữ liệu đã đổi; hãy xem trước lại')
        path=Path(csv_path).resolve();meta=path.parent/'.mt'
        meta.mkdir(exist_ok=True)
        lock=meta/'translation_memory_approval.lock';owned=uuid.uuid4().hex.encode('ascii')
        try:
            with lock.open('xb') as handle:handle.write(owned)
        except FileExistsError:
            owned=None
            return dict(ok=False,error='Một lượt duyệt khác đang giữ gói; hãy thử lại sau')
        preview=preview_reviewed_memory(path,keys)
        if not preview.get('ok') or preview.get('preview_token')!=preview_token:
            return dict(ok=False,error=preview.get('error') or 'Dữ liệu đã đổi; hãy xem trước lại')
        snapshot=preview['_snapshot']
        return activate_reviewed_memory(path.parent,preview['rows'],snapshot,lambda:_reviewed_memory_snapshot(path))
    except (OSError,ValueError,TypeError,KeyError) as error:
        return dict(ok=False,error=str(error))
    finally:
        if lock is not None and owned is not None and not lock.is_symlink() and lock.is_file() and lock.read_bytes()==owned:
            lock.unlink()


def save_document(
    csv_path: str | Path,
    fields: list[str],
    rows: list[dict],
    expected_sha256: str | None = None,
) -> dict[str, Any]:
    csv_path = Path(csv_path).resolve()
    try:
        baseline_bytes = csv_path.read_bytes()
    except OSError as exc:
        return {"ok": False, "error": str(exc)}
    if expected_sha256 and hashlib.sha256(baseline_bytes).hexdigest().casefold() != expected_sha256.casefold():
        return {"ok": False, "error": "CSV đã thay đổi bên ngoài — hãy tải lại trước khi lưu"}
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
    try:
        baseline_fields, baseline_rows = _read_editor_csv_bytes(baseline_bytes)
    except (ValueError, OSError) as exc:
        return {"ok": False, "error": str(exc)}
    normalized_fields = fields + [field for field in CSV_FIELDS if field not in fields]
    if normalized_fields != baseline_fields or len(rows) != len(baseline_rows):
        return {"ok": False, "error": "Không được đổi cột hoặc số dòng của CSV gốc"}
    for original, updated in zip(baseline_rows, rows):
        if any(updated.get(field, "") != original.get(field, "")
               for field in baseline_fields if field != "translation"):
            return {"ok": False, "error": "Không được đổi key, thứ tự, source hoặc metadata của CSV gốc"}
    # Recheck before creating the backup. The atomic writer checks again after
    # serialization, immediately before replacing the source file.
    if expected_sha256:
        current_sha256 = hashlib.sha256(csv_path.read_bytes()).hexdigest()
        if current_sha256.casefold() != expected_sha256.casefold():
            return {"ok": False, "error": "CSV đã thay đổi bên ngoài — hãy tải lại trước khi lưu"}
    backup_path = backup_translation_csv(csv_path)
    review_path = csv_path.parent / "review_only.csv"
    review_before = review_path.read_bytes() if review_path.is_file() else None
    try:
        saved_sha256 = _atomic_write_csv(csv_path, fields, rows, expected_sha256=expected_sha256)
        review_pruned = 0
        if csv_path.name.casefold() == "translation.csv":
            _fields, saved_rows = _read_editor_csv(csv_path)
            review_pruned = _reconcile_saved_review_rows(csv_path, saved_rows)
    except Exception as exc:
        if isinstance(exc, CsvEditorExternalChange):
            return {"ok": False, "error": "CSV đã thay đổi bên ngoài — hãy tải lại trước khi lưu",
                    "backup_path": str(backup_path)}
        try:
            _atomic_write_bytes(csv_path, backup_path.read_bytes())
            if review_before is not None:
                _atomic_write_bytes(review_path, review_before)
        except OSError as rollback_error:
            return {"ok": False, "error": f"{exc}; rollback thất bại: {rollback_error}",
                    "backup_path": str(backup_path), "rolled_back": False}
        return {"ok": False, "error": str(exc), "backup_path": str(backup_path), "rolled_back": True}
    return {
        "ok": True,
        "csv_path": str(csv_path),
        "row_count": len(rows),
        "source_sha256": saved_sha256,
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


class CsvEditorExternalChange(RuntimeError):
    pass


def _atomic_write_csv(
    csv_path: Path,
    fields: list[str],
    rows: list[dict],
    expected_sha256: str | None = None,
) -> str:
    """Write a CSV without leaving a partially-written user file behind."""
    tmp = csv_path.with_name(f".{csv_path.name}.{os.getpid()}.tmp")
    try:
        write_csv_rows_file(tmp, fields, rows)
        written_sha256 = hashlib.sha256(tmp.read_bytes()).hexdigest()
        if expected_sha256:
            current_sha256 = hashlib.sha256(csv_path.read_bytes()).hexdigest()
            if current_sha256.casefold() != expected_sha256.casefold():
                raise CsvEditorExternalChange("CSV đã thay đổi bên ngoài — hãy tải lại trước khi lưu")
        os.replace(tmp, csv_path)
        return written_sha256
    finally:
        try:
            tmp.unlink()
        except FileNotFoundError:
            pass


def _atomic_write_bytes(path: Path, contents: bytes) -> None:
    tmp = path.with_name(f".{path.name}.{os.getpid()}.restore.tmp")
    try:
        tmp.write_bytes(contents)
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)


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
    p_save.add_argument("--expected-sha256", help="fail if the opened CSV changed before save")

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

    for command in ('preview-reviewed-memory','confirm-reviewed-memory'):
        p_memory=sub.add_parser(command)
        p_memory.add_argument('csv_path',type=Path)
        p_memory.add_argument('--keys',type=Path,required=True)
        if command=='confirm-reviewed-memory':p_memory.add_argument('--preview-token',required=True)

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
        if args.cmd in {'preview-reviewed-memory','confirm-reviewed-memory'}:
            keys=json.loads(args.keys.read_text(encoding='utf-8'))
            result=(preview_reviewed_memory(args.csv_path,keys) if args.cmd=='preview-reviewed-memory'
                    else confirm_reviewed_memory(args.csv_path,keys,args.preview_token))
            result.pop('_snapshot',None)
        elif args.cmd == "load":
            result = load_document(args.csv_path)
        elif args.cmd == "save":
            if not args.payload or not args.payload.is_file():
                raise ValueError("save requires --payload JSON file")
            payload = json.loads(args.payload.read_text(encoding="utf-8"))
            result = save_document(args.csv_path, payload.get("fields") or [], payload.get("rows") or [], args.expected_sha256)
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
