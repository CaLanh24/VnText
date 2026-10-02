"""Safely reuse translations from an older ``translation.csv`` package."""

from __future__ import annotations

import csv
import hashlib
import io
from pathlib import Path
from typing import Any

from vntext.mt_apply import apply_batch
from vntext.mt_check import load_whitelist
from vntext.mt_ct2_status import _prune_resolved_review_only
from vntext.package_io import read_csv_rows_file
from vntext.patch_gate import translation_passes_patch_gate


class ExternalTranslationImportError(ValueError):
    """The selected source or current package cannot be safely compared."""


_REQUIRED_FIELDS = ("key", "source_text", "translation")
_SAMPLE_LIMIT = 20


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _read_strict_csv(path: Path, label: str) -> tuple[bytes, list[dict[str, str]]]:
    try:
        raw = path.read_bytes()
        table = list(csv.reader(io.StringIO(raw.decode("utf-8-sig"), newline=""), strict=True))
    except (OSError, UnicodeError, csv.Error) as exc:
        raise ExternalTranslationImportError(f"Không đọc được {label}") from exc
    if not table:
        raise ExternalTranslationImportError(f"{label} trống")

    fields = table[0]
    if len(fields) != len(set(fields)):
        raise ExternalTranslationImportError(f"{label} có cột trùng lặp")
    missing = [field for field in _REQUIRED_FIELDS if field not in fields]
    if missing:
        raise ExternalTranslationImportError(
            f"{label} thiếu cột bắt buộc: {', '.join(missing)}"
        )

    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for row_number, values in enumerate(table[1:], start=2):
        if len(values) != len(fields):
            raise ExternalTranslationImportError(
                f"{label} dòng {row_number} có số cột không đúng"
            )
        row = dict(zip(fields, values))
        key = row["key"]
        if not key.strip() or not row["source_text"].strip():
            raise ExternalTranslationImportError(
                f"{label} dòng {row_number} thiếu key hoặc source_text"
            )
        if key in seen:
            raise ExternalTranslationImportError(
                f"{label} có key trùng lặp: {key[:128]}"
            )
        seen.add(key)
        rows.append(row)
    if not rows:
        raise ExternalTranslationImportError(f"{label} không có dòng dữ liệu")
    return raw, rows


def _report(target: Path, source: Path) -> dict[str, Any]:
    return {
        "operation": "external_translation_import",
        "status": "FAIL",
        "target_csv": str(target),
        "source_csv": str(source),
        "target_sha256_before": None,
        "target_sha256_after": None,
        "source_sha256": None,
        "target_rows": 0,
        "source_rows": 0,
        "already_translated": 0,
        "exact_matches": 0,
        "source_missing": 0,
        "source_mismatch": 0,
        "donor_empty": 0,
        "rejected": {},
        "rejected_samples": [],
        "applied": 0,
        "translated": 0,
        "untranslated_remaining": 0,
        "review_pruned": 0,
        "review_only_remaining": 0,
        "complete": False,
        "errors": [],
        "warnings": [],
    }


def _add_rejection(report: dict[str, Any], key: str, reason: str) -> None:
    rejected = report["rejected"]
    rejected[reason] = int(rejected.get(reason) or 0) + 1
    samples = report["rejected_samples"]
    if len(samples) < _SAMPLE_LIMIT:
        samples.append({"key": key, "reason": reason})


def import_existing_translations(
    target_csv: str | Path,
    source_csv: str | Path,
) -> dict[str, Any]:
    """Fill blank current rows only when old and current identity both match.

    The current package remains authoritative: its manifest, locators and all
    non-translation fields are never copied from the old CSV.
    """

    target_input = Path(target_csv).expanduser()
    source_input = Path(source_csv).expanduser()
    report = _report(target_input, source_input)
    try:
        if target_input.is_symlink() or source_input.is_symlink():
            raise ExternalTranslationImportError("Không nhận file CSV liên kết")
        if not target_input.is_file() or not source_input.is_file():
            raise ExternalTranslationImportError("Không tìm thấy translation.csv đã chọn")

        target = target_input.resolve()
        source = source_input.resolve()
        report["target_csv"] = str(target)
        report["source_csv"] = str(source)
        if target == source:
            raise ExternalTranslationImportError("Bản dịch cũ phải là file khác gói hiện tại")
        if not (target.parent / "manifest.json").is_file():
            raise ExternalTranslationImportError("Gói hiện tại thiếu manifest.json")

        target_raw, target_rows = _read_strict_csv(target, "translation.csv hiện tại")
        source_raw, source_rows = _read_strict_csv(source, "translation.csv cũ")
        report.update(
            {
                "target_sha256_before": _sha256(target_raw),
                "source_sha256": _sha256(source_raw),
                "target_rows": len(target_rows),
                "source_rows": len(source_rows),
            }
        )
        source_by_key = {row["key"]: row for row in source_rows}
        whitelist = load_whitelist(target.parent)
        accepted: dict[str, str] = {}

        for row in target_rows:
            key = row["key"]
            if str(row.get("translation") or "").strip():
                report["already_translated"] += 1
                continue
            donor = source_by_key.get(key)
            if donor is None:
                report["source_missing"] += 1
                continue
            if donor["source_text"] != row["source_text"]:
                report["source_mismatch"] += 1
                continue
            report["exact_matches"] += 1
            candidate = donor["translation"]
            if not candidate.strip():
                report["donor_empty"] += 1
                continue
            gate_ok, reason = translation_passes_patch_gate(row, candidate, whitelist)
            if not gate_ok:
                _add_rejection(report, key, reason or "patch_gate")
                continue
            accepted[key] = candidate

        applied = apply_batch(target, accepted, allow_overwrite=False)
        if not applied.ok:
            raise ExternalTranslationImportError(applied.message or "Không thể ghi translation.csv")
        report["applied"] = applied.applied
        _, after_rows = _read_strict_csv(target, "translation.csv sau khi nhập")
        report["translated"] = sum(
            bool(str(row.get("translation") or "").strip()) for row in after_rows
        )
        report["untranslated_remaining"] = len(after_rows) - report["translated"]
        report["target_sha256_after"] = _sha256(target.read_bytes())

        if applied.applied:
            try:
                report["review_pruned"] = _prune_resolved_review_only(
                    target.parent,
                    after_rows,
                    allow_human_review_resolution=True,
                )
            except (OSError, ValueError, csv.Error) as exc:
                report["warnings"].append(
                    f"Không cập nhật review_only.csv: {str(exc) or type(exc).__name__}"
                )

        review_path = target.parent / "review_only.csv"
        if review_path.is_file():
            _, review_rows = read_csv_rows_file(review_path)
            report["review_only_remaining"] = len(review_rows)
        report["complete"] = (
            report["review_only_remaining"] == 0
            and report["untranslated_remaining"] == 0
            and not report["warnings"]
        )
        report["status"] = "PASS"
    except ExternalTranslationImportError as exc:
        report["errors"].append(str(exc))
    except (OSError, ValueError, csv.Error) as exc:
        report["errors"].append(str(exc) or type(exc).__name__)
    return report


__all__ = ["ExternalTranslationImportError", "import_existing_translations"]
