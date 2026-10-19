"""Frozen synthetic EN-to-VI evaluator and bounded local OPUS baseline.

This is evaluation-only tooling. It does not edit a translation package or
change the product route. Semantic quality remains UNKNOWN until independent
bilingual review is recorded outside this machine-computed report.
"""

from __future__ import annotations

import argparse
import collections
import ctypes
import hashlib
import importlib.metadata
import json
import os
import platform
import subprocess
import sys
import time
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from vntext.mt_check import structural_problems  # noqa: E402

DATASET_PATH = ROOT / "evaluation" / "translation_quality_phase1" / "dataset.v1.json"
EVIDENCE_ROOT = ROOT / "DEV_RUN" / "translation-quality-phase1"
DEFAULT_REPORT_PATH = EVIDENCE_ROOT / "opus-baseline.v1.json"
MODEL_DIR = ROOT / ".dev-env" / "cache" / "models" / "opus-mt-en-vi-int8"
EXPECTED_GROUP_COUNTS = {
    "dialogue": {"development": 12, "held_out": 4},
    "idioms": {"development": 13, "held_out": 4},
    "address_register": {"development": 13, "held_out": 4},
    "ui": {"development": 13, "held_out": 4},
    "terminology": {"development": 15, "held_out": 2},
    "protected_tokens": {"development": 14, "held_out": 2},
}
SPLIT_COUNTS = {"development": 80, "held_out": 20}
EXPECTED_ROW_COUNT = 100
MAX_INTERNAL_SECONDS = 840
WRAPPER_TIMEOUT_SECONDS = 900
MAX_PEAK_WORKING_SET_BYTES = 1024 * 1024 * 1024


class DatasetValidationError(ValueError):
    """The frozen dataset is malformed or violates its provenance contract."""


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def normalized_source(value: str) -> str:
    """Normalize Unicode/case and remove punctuation for duplicate detection."""
    normalized = unicodedata.normalize("NFKC", value).casefold()
    return "".join(char for char in normalized if char.isalnum())


def validate_dataset(document: Any) -> dict[str, Any]:
    if not isinstance(document, dict) or document.get("schema_version") != 1:
        raise DatasetValidationError("unsupported dataset schema")
    if document.get("dataset_id") != "vntext-en-vi-translation-quality-phase1-v1":
        raise DatasetValidationError("unexpected dataset identity")
    if document.get("source_language") != "en" or document.get("target_language") != "vi":
        raise DatasetValidationError("dataset must be EN-to-VI")

    provenance = document.get("provenance")
    if not isinstance(provenance, dict):
        raise DatasetValidationError("dataset provenance is missing")
    if provenance.get("author") != "agent-generated synthetic":
        raise DatasetValidationError("dataset author provenance is not approved")
    if provenance.get("rights") != "generated-for-project":
        raise DatasetValidationError("dataset rights provenance is not approved")
    if provenance.get("semantic_review_status") != "draft/unreviewed":
        raise DatasetValidationError("semantic review must remain draft/unreviewed")

    split_protocol = document.get("split_protocol")
    if not isinstance(split_protocol, dict) or split_protocol.get("frozen_before_baseline") is not True:
        raise DatasetValidationError("split protocol is not frozen before baseline")
    if split_protocol.get("development_rows") != SPLIT_COUNTS["development"]:
        raise DatasetValidationError("development split size mismatch")
    if split_protocol.get("held_out_rows") != SPLIT_COUNTS["held_out"]:
        raise DatasetValidationError("held-out split size mismatch")
    if split_protocol.get("group_counts") != EXPECTED_GROUP_COUNTS:
        raise DatasetValidationError("fixed group/split counts mismatch")

    rubric = document.get("review_rubric")
    if not isinstance(rubric, dict):
        raise DatasetValidationError("review rubric is missing")
    semantic_dimensions = {
        "meaning_error", "omitted_meaning", "added_meaning", "address_or_register",
        "terminology", "naturalness",
    }
    structural_dimensions = {
        "placeholder_or_protected_token_mismatch", "tag_mismatch",
        "literal_newline_mismatch", "format_or_control_token_mismatch",
    }
    if set(rubric.get("semantic_dimensions") or []) != semantic_dimensions:
        raise DatasetValidationError("semantic review dimensions mismatch")
    if set(rubric.get("structural_dimensions") or []) != structural_dimensions:
        raise DatasetValidationError("structural review dimensions mismatch")
    if rubric.get("semantic_acceptance_status") != "UNKNOWN until independent bilingual review and human acceptance":
        raise DatasetValidationError("semantic acceptance must fail closed")

    rows = document.get("rows")
    if not isinstance(rows, list) or len(rows) != EXPECTED_ROW_COUNT:
        raise DatasetValidationError(f"dataset must contain exactly {EXPECTED_ROW_COUNT} rows")

    expected_group_pairs = {
        (group, split): count
        for group, split_counts in EXPECTED_GROUP_COUNTS.items()
        for split, count in split_counts.items()
    }
    actual_group_pairs: collections.Counter[tuple[str, str]] = collections.Counter()
    actual_splits: collections.Counter[str] = collections.Counter()
    seen_ids: set[str] = set()
    seen_sources: dict[str, str] = {}
    scenario_groups: dict[str, dict[str, str]] = {}
    forbidden_translation_fields = {
        "gold_vi", "reference_vi", "target_vi", "gold_translation", "reference_translation",
    }

    for ordinal, row in enumerate(rows, 1):
        if not isinstance(row, dict):
            raise DatasetValidationError(f"row {ordinal} must be an object")
        if forbidden_translation_fields.intersection(row):
            raise DatasetValidationError(f"row {ordinal} contains a reference/gold translation")
        row_id = str(row.get("id") or "")
        source = str(row.get("source_en") or "")
        group = str(row.get("group") or "")
        split = str(row.get("split") or "")
        if not row_id or row_id in seen_ids:
            raise DatasetValidationError(f"missing or duplicate row ID: {row_id}")
        if not source.strip():
            raise DatasetValidationError(f"empty source sentence: {row_id}")
        if group not in EXPECTED_GROUP_COUNTS:
            raise DatasetValidationError(f"unknown group for {row_id}: {group}")
        if split not in SPLIT_COUNTS:
            raise DatasetValidationError(f"unknown split for {row_id}: {split}")
        row_review_status = row.get("semantic_review_status")
        if row_review_status is not None and row_review_status != "draft/unreviewed":
            raise DatasetValidationError(f"semantic review must remain unreviewed: {row_id}")

        normalized = normalized_source(source)
        if not normalized:
            raise DatasetValidationError(f"source normalizes to empty: {row_id}")
        prior_id = seen_sources.get(normalized)
        if prior_id:
            raise DatasetValidationError(
                f"duplicate normalized source across dataset: {prior_id} and {row_id}"
            )

        boundary = row.get("scenario_boundary")
        if not isinstance(boundary, dict):
            raise DatasetValidationError(f"scenario boundary missing: {row_id}")
        file_id = str(boundary.get("file_id") or "")
        scenario_id = str(boundary.get("group_id") or "")
        boundary_kind = str(boundary.get("kind") or "")
        if not file_id or not scenario_id or not boundary_kind:
            raise DatasetValidationError(f"scenario boundary is incomplete: {row_id}")
        if boundary.get("engine") != "synthetic":
            raise DatasetValidationError(f"scenario engine must be synthetic: {row_id}")
        if not isinstance(boundary.get("turn"), int) or boundary["turn"] < 1:
            raise DatasetValidationError(f"scenario turn must be a positive integer: {row_id}")
        prior_group = scenario_groups.get(scenario_id)
        current_group = {"split": split, "file_id": file_id, "category": group, "kind": boundary_kind}
        if prior_group and prior_group != current_group:
            raise DatasetValidationError(f"scenario group crosses split or boundary: {scenario_id}")
        scenario_groups[scenario_id] = current_group
        if group == "address_register" and not str(row.get("address_context") or "").strip():
            raise DatasetValidationError(f"address/register context missing: {row_id}")

        seen_ids.add(row_id)
        seen_sources[normalized] = row_id
        actual_group_pairs[(group, split)] += 1
        actual_splits[split] += 1

    if dict(actual_group_pairs) != expected_group_pairs:
        raise DatasetValidationError(
            f"group/split row counts mismatch: {dict(actual_group_pairs)} != {expected_group_pairs}"
        )
    if dict(actual_splits) != SPLIT_COUNTS:
        raise DatasetValidationError(f"split row counts mismatch: {dict(actual_splits)} != {SPLIT_COUNTS}")
    return {
        "row_count": len(rows),
        "split_counts": dict(actual_splits),
        "group_split_counts": {
            group: {
                split: actual_group_pairs[(group, split)]
                for split in EXPECTED_GROUP_COUNTS[group]
            }
            for group in EXPECTED_GROUP_COUNTS
        },
        "scenario_group_count": len(scenario_groups),
        "unique_normalized_source_count": len(seen_sources),
    }


def load_dataset(path: Path = DATASET_PATH) -> tuple[dict, bytes, dict[str, Any]]:
    raw = path.read_bytes()
    try:
        document = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise DatasetValidationError(f"cannot load UTF-8 JSON dataset: {exc}") from exc
    summary = validate_dataset(document)
    return document, raw, summary


def baseline_protocol(dataset: dict) -> dict[str, Any]:
    from vntext.mt_ct2_constants import MODEL_REPO, MODEL_REVISION

    return {
        "route": "vntext.mt_strategies.translate_row_ct2 + vntext.mt_ct2_model.Ct2Translator",
        "model_repo": MODEL_REPO,
        "model_revision": MODEL_REVISION,
        "model_dir": str(MODEL_DIR.resolve()),
        "device": "cpu",
        "ct2_inter_threads": 1,
        "ct2_intra_threads": 1,
        "glossary_applied": False,
        "translation_memory_applied": False,
        "context_applied": False,
        "context_status": "NOT_APPLIED",
        "row_retries": 0,
        "network_and_download": "disabled; local-only model files",
        "internal_wall_deadline_seconds": MAX_INTERNAL_SECONDS,
        "canonical_wrapper_timeout_seconds": WRAPPER_TIMEOUT_SECONDS,
        "peak_working_set_limit_bytes": MAX_PEAK_WORKING_SET_BYTES,
        "memory_measurement": "Windows PSAPI GetProcessMemoryInfo PeakWorkingSetSize; sample after model load and each row",
        "structural_validator": "vntext.mt_check.structural_problems on the restored route output",
        "semantic_quality_verdict": "UNKNOWN; no reference translation or automatic semantic scoring",
        "development_rows": SPLIT_COUNTS["development"],
        "held_out_rows": SPLIT_COUNTS["held_out"],
        "group_split_counts": dataset["split_protocol"]["group_counts"],
        "metrics": [
            "route-returned rows, source-identical outputs, row errors, and explicit not-run dispositions",
            "structural pass/fail and exact validator reasons",
            "model initialization, per-row route execution, translation-loop wall time, and total wall latency",
            "process current/peak working set bytes",
        ],
    }


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _git_head() -> str | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=5,
            check=True,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return result.stdout.strip() or None


def _version(package: str) -> str | None:
    try:
        return importlib.metadata.version(package)
    except importlib.metadata.PackageNotFoundError:
        return None


def _model_identity(model_dir: Path = MODEL_DIR) -> dict[str, Any]:
    resolved = model_dir.resolve()
    if resolved != MODEL_DIR.resolve():
        raise ValueError(f"baseline must use the existing pinned model directory: {resolved}")
    if not (resolved / "model.bin").is_file():
        raise FileNotFoundError(f"local CT2 model.bin is missing: {resolved}")
    files: list[dict[str, Any]] = []
    for path in sorted(resolved.rglob("*"), key=lambda item: item.as_posix().casefold()):
        if path.is_symlink():
            raise ValueError(f"model tree contains a symlink and cannot be fingerprinted safely: {path}")
        if path.is_file():
            files.append({
                "path": path.relative_to(resolved).as_posix(),
                "size_bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            })
    from vntext.mt_ct2_constants import MODEL_REPO, MODEL_REVISION

    return {
        "path": str(resolved),
        "repository": MODEL_REPO,
        "declared_revision": MODEL_REVISION,
        "file_count": len(files),
        "files": files,
        "tree_sha256": sha256_bytes(canonical_json(files).encode("utf-8")),
    }


def _windows_process_memory() -> dict[str, Any]:
    if os.name != "nt":
        return {"available": False, "reason": "Windows PSAPI measurement requires Windows"}

    size_t = ctypes.c_size_t

    class ProcessMemoryCountersEx(ctypes.Structure):
        _fields_ = [
            ("cb", ctypes.c_ulong),
            ("PageFaultCount", ctypes.c_ulong),
            ("PeakWorkingSetSize", size_t),
            ("WorkingSetSize", size_t),
            ("QuotaPeakPagedPoolUsage", size_t),
            ("QuotaPagedPoolUsage", size_t),
            ("QuotaPeakNonPagedPoolUsage", size_t),
            ("QuotaNonPagedPoolUsage", size_t),
            ("PagefileUsage", size_t),
            ("PeakPagefileUsage", size_t),
            ("PrivateUsage", size_t),
        ]

    try:
        psapi = ctypes.WinDLL("psapi", use_last_error=True)
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        get_current_process = kernel32.GetCurrentProcess
        get_current_process.restype = ctypes.c_void_p
        get_memory_info = psapi.GetProcessMemoryInfo
        get_memory_info.argtypes = [
            ctypes.c_void_p,
            ctypes.POINTER(ProcessMemoryCountersEx),
            ctypes.c_ulong,
        ]
        get_memory_info.restype = ctypes.c_int
        counters = ProcessMemoryCountersEx()
        counters.cb = ctypes.sizeof(counters)
        if not get_memory_info(get_current_process(), ctypes.byref(counters), counters.cb):
            code = ctypes.get_last_error()
            raise OSError(code, "GetProcessMemoryInfo failed")
    except (AttributeError, OSError) as exc:
        return {"available": False, "reason": f"{type(exc).__name__}: {exc}"}

    return {
        "available": True,
        "source": "Win32 PSAPI GetProcessMemoryInfo PeakWorkingSetSize",
        "current_working_set_bytes": int(counters.WorkingSetSize),
        "peak_working_set_bytes": int(counters.PeakWorkingSetSize),
        "private_usage_bytes": int(counters.PrivateUsage),
        "peak_pagefile_usage_bytes": int(counters.PeakPagefileUsage),
    }


def _machine_identity() -> dict[str, Any]:
    return {
        "os": platform.platform(),
        "architecture": platform.machine(),
        "cpu": platform.processor(),
        "logical_cpu_count": os.cpu_count(),
    }


def make_report(
    dataset: dict,
    *,
    dataset_sha256: str,
    protocol_sha256: str,
    tool_sha256: str,
    git_head: str | None,
    started_at_utc: str,
) -> dict[str, Any]:
    protocol = baseline_protocol(dataset)
    return {
        "schema_version": 1,
        "run_status": "IN_PROGRESS",
        "started_at_utc": started_at_utc,
        "finished_at_utc": None,
        "source": {
            "git_head": git_head,
            "tool_sha256": tool_sha256,
            "dataset_sha256": dataset_sha256,
            "protocol_sha256": protocol_sha256,
        },
        "dataset": {
            "dataset_id": dataset["dataset_id"],
            "row_count": EXPECTED_ROW_COUNT,
            "split_counts": dict(SPLIT_COUNTS),
            "group_split_counts": dataset["split_protocol"]["group_counts"],
            "provenance": dict(dataset["provenance"]),
            "scenario_group_count": validate_dataset(dataset)["scenario_group_count"],
        },
        "protocol": protocol,
        "model": {"status": "NOT_LOADED"},
        "runtime": {
            "python": platform.python_version(),
            "ctranslate2": _version("ctranslate2"),
            "transformers": _version("transformers"),
        },
        "machine": _machine_identity(),
        "resource_measurements": {
            "limit_peak_working_set_bytes": MAX_PEAK_WORKING_SET_BYTES,
            "samples": [],
        },
        "semantic_quality_verdict": "UNKNOWN",
        "human_acceptance_status": "NOT_CONDUCTED",
        "fatal_error": None,
        "stop_reason": None,
        "elapsed_seconds": 0.0,
        "model_initialization_seconds": None,
        "row_execution_seconds": 0.0,
        "translation_loop_wall_seconds": None,
        "summary": {},
        "rows": [
            {
                "id": row["id"],
                "group": row["group"],
                "split": row["split"],
                "source_en": row["source_en"],
                "scenario_boundary": dict(row["scenario_boundary"]),
                "address_context": row.get("address_context"),
                "disposition": "NOT_RUN",
                "model_calls": [],
                "route_output": None,
                "row_elapsed_seconds": None,
                "structural_verdict": "NOT_RUN",
                "structural_reasons": [],
                "semantic_review_verdict": "UNKNOWN",
                "error": None,
            }
            for row in dataset["rows"]
        ],
    }


def completed_row_result(
    source_row: dict,
    route_output: str,
    model_calls: list[dict[str, Any]],
    elapsed_seconds: float,
) -> dict[str, Any]:
    reasons = structural_problems(
        {"key": source_row["id"], "source_text": source_row["source_en"]},
        route_output,
    )
    return {
        "id": source_row["id"],
        "group": source_row["group"],
        "split": source_row["split"],
        "source_en": source_row["source_en"],
        "scenario_boundary": dict(source_row["scenario_boundary"]),
        "address_context": source_row.get("address_context"),
        "disposition": "ROUTE_RETURNED",
        "output_matches_source": route_output == source_row["source_en"],
        "model_calls": model_calls,
        "route_output": route_output,
        "row_elapsed_seconds": round(max(0.0, elapsed_seconds), 6),
        "structural_verdict": "FAIL" if reasons else "PASS",
        "structural_reasons": list(reasons),
        "semantic_review_verdict": "UNKNOWN",
        "error": None,
    }


def error_row_result(
    source_row: dict,
    model_calls: list[dict[str, Any]],
    elapsed_seconds: float,
    error: BaseException,
) -> dict[str, Any]:
    return {
        "id": source_row["id"],
        "group": source_row["group"],
        "split": source_row["split"],
        "source_en": source_row["source_en"],
        "scenario_boundary": dict(source_row["scenario_boundary"]),
        "address_context": source_row.get("address_context"),
        "disposition": "ROW_ERROR",
        "model_calls": model_calls,
        "route_output": None,
        "row_elapsed_seconds": round(max(0.0, elapsed_seconds), 6),
        "structural_verdict": "NOT_RUN",
        "structural_reasons": [],
        "semantic_review_verdict": "UNKNOWN",
        "error": f"{type(error).__name__}: {error}",
    }


def summarize_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    dispositions = collections.Counter(row["disposition"] for row in rows)
    split_summary: dict[str, dict[str, Any]] = {}
    group_summary: dict[str, dict[str, Any]] = {}
    for split in SPLIT_COUNTS:
        selected = [row for row in rows if row["split"] == split]
        split_summary[split] = {
            "total": len(selected),
            "route_returned": sum(row["disposition"] == "ROUTE_RETURNED" for row in selected),
            "output_identity": sum(row.get("output_matches_source") is True for row in selected),
            "row_errors": sum(row["disposition"] == "ROW_ERROR" for row in selected),
            "not_run_or_in_progress": sum(
                row["disposition"] == "IN_PROGRESS" or row["disposition"].startswith("NOT_RUN")
                for row in selected
            ),
        }
    for group in EXPECTED_GROUP_COUNTS:
        selected = [row for row in rows if row["group"] == group]
        group_summary[group] = {
            "total": len(selected),
            "route_returned": sum(row["disposition"] == "ROUTE_RETURNED" for row in selected),
            "output_identity": sum(row.get("output_matches_source") is True for row in selected),
            "row_errors": sum(row["disposition"] == "ROW_ERROR" for row in selected),
            "not_run_or_in_progress": sum(
                row["disposition"] == "IN_PROGRESS" or row["disposition"].startswith("NOT_RUN")
                for row in selected
            ),
        }
    structural = collections.Counter(row["structural_verdict"] for row in rows)
    return {
        "total_rows": len(rows),
        "route_returned_rows": dispositions.get("ROUTE_RETURNED", 0),
        "output_identity_rows": sum(row.get("output_matches_source") is True for row in rows),
        "row_errors": dispositions.get("ROW_ERROR", 0),
        "not_run_or_in_progress": sum(
            count for name, count in dispositions.items()
            if name == "IN_PROGRESS" or name.startswith("NOT_RUN")
        ),
        "disposition_counts": dict(sorted(dispositions.items())),
        "structural_verdict_counts": {
            name: structural.get(name, 0) for name in ("PASS", "FAIL", "NOT_RUN")
        },
        "by_split": split_summary,
        "by_group": group_summary,
        "semantic_quality_verdict": "UNKNOWN",
    }


def _mark_unrun_rows(rows: list[dict[str, Any]], *, disposition: str, reason: str) -> None:
    """Give every untouched/in-flight row an explicit, reason-coded disposition."""
    if not disposition.startswith("NOT_RUN_"):
        raise ValueError("unrun row disposition must start with NOT_RUN_")
    for row in rows:
        if row.get("disposition") in {"NOT_RUN", "IN_PROGRESS"}:
            row["disposition"] = disposition
            row["error"] = reason


def validate_report(report: Any, dataset: dict) -> dict[str, Any]:
    if not isinstance(report, dict) or report.get("schema_version") != 1:
        raise ValueError("unsupported baseline report schema")
    if report.get("semantic_quality_verdict") != "UNKNOWN":
        raise ValueError("semantic quality cannot be inferred by the evaluator")
    if report.get("human_acceptance_status") != "NOT_CONDUCTED":
        raise ValueError("human acceptance cannot be claimed by the evaluator")
    rows = report.get("rows")
    if not isinstance(rows, list) or len(rows) != EXPECTED_ROW_COUNT:
        raise ValueError("baseline report must retain one disposition for every dataset row")
    for source_row, result in zip(dataset["rows"], rows):
        if not isinstance(result, dict):
            raise ValueError("baseline row result must be an object")
        for field in ("id", "group", "split", "source_en"):
            if result.get(field) != source_row[field]:
                raise ValueError(f"baseline row identity mismatch: {source_row['id']} / {field}")
        if result.get("semantic_review_verdict") != "UNKNOWN":
            raise ValueError(f"semantic verdict must remain UNKNOWN: {source_row['id']}")
        disposition = result.get("disposition")
        if disposition == "ROUTE_RETURNED":
            if not isinstance(result.get("route_output"), str):
                raise ValueError(f"route return output missing: {source_row['id']}")
            if result.get("output_matches_source") is not (result["route_output"] == source_row["source_en"]):
                raise ValueError(f"source identity flag does not match route output: {source_row['id']}")
            if result.get("structural_verdict") not in {"PASS", "FAIL"}:
                raise ValueError(f"route return structural verdict missing: {source_row['id']}")
            if not isinstance(result.get("structural_reasons"), list):
                raise ValueError(f"route return structural reasons missing: {source_row['id']}")
            expected_verdict = "FAIL" if result["structural_reasons"] else "PASS"
            if result["structural_verdict"] != expected_verdict:
                raise ValueError(f"structural reasons and verdict disagree: {source_row['id']}")
        elif disposition == "ROW_ERROR":
            if result.get("route_output") is not None or result.get("structural_verdict") != "NOT_RUN":
                raise ValueError(f"failed row must not fabricate output or structural pass: {source_row['id']}")
            if not result.get("error"):
                raise ValueError(f"failed row must retain its error: {source_row['id']}")
        elif disposition == "IN_PROGRESS" or (isinstance(disposition, str) and disposition.startswith("NOT_RUN")):
            if result.get("route_output") is not None or result.get("structural_verdict") != "NOT_RUN":
                raise ValueError(f"unrun row must not contain a fabricated output: {source_row['id']}")
            if disposition == "IN_PROGRESS" or not result.get("error"):
                raise ValueError(f"unrun row needs a reason-coded final disposition: {source_row['id']}")
        else:
            raise ValueError(f"unknown row disposition for {source_row['id']}: {disposition}")
    expected_summary = summarize_rows(rows)
    if report.get("summary") != expected_summary:
        raise ValueError("baseline report summary does not reconcile with row evidence")
    return expected_summary


def serialize_report(report: dict[str, Any]) -> str:
    return json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n"


def _allowed_report_path(path: Path) -> Path:
    resolved = path.expanduser().resolve()
    evidence_root = EVIDENCE_ROOT.resolve()
    if resolved.parent != evidence_root or resolved.name != DEFAULT_REPORT_PATH.name:
        raise ValueError(f"baseline report must be the owned evidence file {DEFAULT_REPORT_PATH}")
    return resolved


def _write_report(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.tmp.{os.getpid()}")
    with temporary.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(serialize_report(report))
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def _configure_offline_cache() -> None:
    raw_temp_root = os.environ.get("TEMP") or os.environ.get("TMP") or ""
    if not raw_temp_root.strip():
        raise RuntimeError("canonical wrapper must provide a registered TEMP/TMP under TEST_RUN")
    temp_root = Path(raw_temp_root).expanduser().resolve()
    test_root = (ROOT / "TEST_RUN").resolve()
    if temp_root != test_root and test_root not in temp_root.parents:
        raise RuntimeError(f"temporary root must stay inside TEST_RUN: {temp_root}")
    cache_root = temp_root / "translation-quality-phase1-cache"
    cache_root.mkdir(parents=True, exist_ok=True)
    os.environ["HF_HOME"] = str(cache_root / "hf-home")
    os.environ["HF_HUB_CACHE"] = str(cache_root / "hf-hub-cache")
    os.environ["TRANSFORMERS_CACHE"] = str(cache_root / "transformers-cache")
    os.environ["TORCH_HOME"] = str(cache_root / "torch-home")
    os.environ["VNTEXT_DIRECT_GPU_ROOT"] = str(cache_root / "ct2-runtime")
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    os.environ["VNTEXT_NO_MODEL_DOWNLOAD"] = "1"
    os.environ["VNTEXT_CT2_NO_DOWNLOAD"] = "1"
    os.environ["VNTEXT_CT2_INTER_THREADS"] = "1"
    os.environ["VNTEXT_CT2_INTRA_THREADS"] = "1"


class CapturingTranslator:
    def __init__(self, translator: Any) -> None:
        self.translator = translator
        self.calls: list[dict[str, Any]] = []

    def translate(self, text: str) -> str:
        try:
            output = self.translator.translate(text)
        except Exception as exc:
            self.calls.append({
                "input": text,
                "raw_output": None,
                "disposition": "ERROR",
                "error": f"{type(exc).__name__}: {exc}",
            })
            raise
        if not isinstance(output, str):
            error = TypeError(f"translator returned {type(output).__name__}, expected str")
            self.calls.append({
                "input": text,
                "raw_output": None,
                "disposition": "ERROR",
                "error": f"{type(error).__name__}: {error}",
            })
            raise error
        self.calls.append({
            "input": text,
            "raw_output": output,
            "disposition": "RETURNED",
            "error": None,
        })
        return output


def run_baseline(report_path: Path = DEFAULT_REPORT_PATH) -> dict[str, Any]:
    target_report = _allowed_report_path(report_path)
    if target_report.exists():
        raise FileExistsError(f"refusing to overwrite existing baseline evidence: {target_report}")

    dataset, dataset_raw, _dataset_summary = load_dataset()
    protocol = baseline_protocol(dataset)
    protocol_sha256 = sha256_bytes(canonical_json({
        "dataset_id": dataset["dataset_id"],
        "split_protocol": dataset["split_protocol"],
        "review_rubric": dataset["review_rubric"],
        "baseline_protocol": protocol,
    }).encode("utf-8"))
    tool_sha256 = sha256_file(Path(__file__).resolve())
    started_at_utc = _now_utc()
    started = time.perf_counter()
    deadline = started + MAX_INTERNAL_SECONDS
    report = make_report(
        dataset,
        dataset_sha256=sha256_bytes(dataset_raw),
        protocol_sha256=protocol_sha256,
        tool_sha256=tool_sha256,
        git_head=_git_head(),
        started_at_utc=started_at_utc,
    )
    report["resource_measurements"]["initial"] = _windows_process_memory()
    report["resource_measurements"]["samples"].append({
        "phase": "before_model_load",
        **report["resource_measurements"]["initial"],
    })
    report["summary"] = summarize_rows(report["rows"])
    _write_report(target_report, report)

    model_before = None
    translation_started = None
    try:
        _configure_offline_cache()
        memory = report["resource_measurements"]["initial"]
        if not memory.get("available"):
            report["run_status"] = "RESOURCE_MEASUREMENT_UNAVAILABLE"
            report["fatal_error"] = memory.get("reason", "process memory measurement unavailable")
            _mark_unrun_rows(report["rows"], disposition="NOT_RUN_RESOURCE_MEASUREMENT", reason=report["fatal_error"])
            return report
        if memory["peak_working_set_bytes"] >= MAX_PEAK_WORKING_SET_BYTES:
            report["run_status"] = "INITIAL_MEMORY_LIMIT_REACHED"
            report["fatal_error"] = "observed peak working set is already at the 1 GiB limit"
            _mark_unrun_rows(report["rows"], disposition="NOT_RUN_MEMORY_LIMIT", reason=report["fatal_error"])
            return report

        model_before = _model_identity()
        report["model"] = {"status": "FINGERPRINTED", **model_before}
        _write_report(target_report, report)

        from vntext.mt_ct2_model import Ct2Translator
        from vntext.mt_strategies import translate_row_ct2

        init_started = time.perf_counter()
        report["model"]["load_status"] = "IN_PROGRESS"
        _write_report(target_report, report)
        translator = CapturingTranslator(Ct2Translator(MODEL_DIR))
        report["model"]["load_status"] = "LOADED"
        report["model_initialization_seconds"] = round(time.perf_counter() - init_started, 6)
        loaded_memory = _windows_process_memory()
        report["resource_measurements"]["after_model_load"] = loaded_memory
        report["resource_measurements"]["samples"].append({"phase": "after_model_load", **loaded_memory})
        if not loaded_memory.get("available"):
            report["run_status"] = "RESOURCE_MEASUREMENT_UNAVAILABLE"
            report["fatal_error"] = loaded_memory.get("reason", "process memory measurement unavailable")
            _mark_unrun_rows(report["rows"], disposition="NOT_RUN_RESOURCE_MEASUREMENT", reason=report["fatal_error"])
            return report
        if loaded_memory["peak_working_set_bytes"] >= MAX_PEAK_WORKING_SET_BYTES:
            report["run_status"] = "STOPPED_MEMORY_LIMIT"
            report["stop_reason"] = "observed peak working set reached the 1 GiB limit after model load"
            _mark_unrun_rows(report["rows"], disposition="NOT_RUN_MEMORY_LIMIT", reason=report["stop_reason"])
            return report

        translation_started = time.perf_counter()
        report["run_status"] = "IN_PROGRESS"
        for index, source_row in enumerate(dataset["rows"]):
            if time.perf_counter() >= deadline:
                report["run_status"] = "STOPPED_TIMEOUT"
                report["stop_reason"] = f"internal {MAX_INTERNAL_SECONDS}-second deadline reached before row {source_row['id']}"
                _mark_unrun_rows(report["rows"], disposition="NOT_RUN_TIMEOUT", reason=report["stop_reason"])
                break
            row_report = report["rows"][index]
            row_report["disposition"] = "IN_PROGRESS"
            _write_report(target_report, report)
            call_start = len(translator.calls)
            row_started = time.perf_counter()
            try:
                route_output = translate_row_ct2(
                    {"key": source_row["id"], "source_text": source_row["source_en"]},
                    translator,
                )
                row_elapsed = time.perf_counter() - row_started
                report["rows"][index] = completed_row_result(
                    source_row,
                    route_output,
                    translator.calls[call_start:],
                    row_elapsed,
                )
            except Exception as exc:
                row_elapsed = time.perf_counter() - row_started
                report["rows"][index] = error_row_result(
                    source_row,
                    translator.calls[call_start:],
                    row_elapsed,
                    exc,
                )

            memory_after_row = _windows_process_memory()
            if memory_after_row.get("available"):
                report["resource_measurements"]["samples"].append({
                    "phase": f"after_row:{source_row['id']}",
                    **memory_after_row,
                })
                if memory_after_row["peak_working_set_bytes"] >= MAX_PEAK_WORKING_SET_BYTES:
                    report["run_status"] = "STOPPED_MEMORY_LIMIT"
                    report["stop_reason"] = (
                        f"observed peak working set reached the 1 GiB limit after row {source_row['id']}"
                    )
            else:
                report["run_status"] = "RESOURCE_MEASUREMENT_UNAVAILABLE"
                report["stop_reason"] = memory_after_row.get("reason", "memory sampling failed")

            report["row_execution_seconds"] = round(
                sum(
                    row.get("row_elapsed_seconds") or 0.0
                    for row in report["rows"]
                    if row["disposition"] in {"ROUTE_RETURNED", "ROW_ERROR"}
                ),
                6,
            )
            report["translation_loop_wall_seconds"] = round(time.perf_counter() - translation_started, 6)
            report["elapsed_seconds"] = round(time.perf_counter() - started, 6)
            report["summary"] = summarize_rows(report["rows"])
            _write_report(target_report, report)
            if report["run_status"] in {"STOPPED_MEMORY_LIMIT", "RESOURCE_MEASUREMENT_UNAVAILABLE"}:
                disposition = (
                    "NOT_RUN_MEMORY_LIMIT"
                    if report["run_status"] == "STOPPED_MEMORY_LIMIT"
                    else "NOT_RUN_RESOURCE_MEASUREMENT"
                )
                _mark_unrun_rows(
                    report["rows"],
                    disposition=disposition,
                    reason=report["stop_reason"] or report["fatal_error"] or "resource limit",
                )
                break
        else:
            row_errors = sum(row["disposition"] == "ROW_ERROR" for row in report["rows"])
            report["run_status"] = "COMPLETED_WITH_ROW_ERRORS" if row_errors else "COMPLETED"
        if report["run_status"] == "IN_PROGRESS":
            row_errors = sum(row["disposition"] == "ROW_ERROR" for row in report["rows"])
            report["run_status"] = "COMPLETED_WITH_ROW_ERRORS" if row_errors else "COMPLETED"
        report["translation_loop_wall_seconds"] = round(time.perf_counter() - translation_started, 6)
    except KeyboardInterrupt:
        report["run_status"] = "STOPPED_CANCELLED"
        report["stop_reason"] = "KeyboardInterrupt received; remaining rows are explicitly not run"
        _mark_unrun_rows(report["rows"], disposition="NOT_RUN_CANCELLED", reason=report["stop_reason"])
    except Exception as exc:
        if report["model"].get("load_status") == "IN_PROGRESS":
            report["run_status"] = "MODEL_INITIALIZATION_FAILED"
        elif report["model"].get("status") == "FINGERPRINTED":
            report["run_status"] = "BASELINE_FAILED"
        else:
            report["run_status"] = "BASELINE_PREREQUISITE_FAILED"
        report["fatal_error"] = f"{type(exc).__name__}: {exc}"
        _mark_unrun_rows(report["rows"], disposition="NOT_RUN_BASELINE_FAILED", reason=report["fatal_error"])
    finally:
        if translation_started is not None:
            report["translation_loop_wall_seconds"] = round(time.perf_counter() - translation_started, 6)
        report["elapsed_seconds"] = round(time.perf_counter() - started, 6)
        final_memory = _windows_process_memory()
        report["resource_measurements"]["final"] = final_memory
        if final_memory.get("available"):
            report["resource_measurements"]["observed_peak_working_set_bytes"] = max(
                [final_memory["peak_working_set_bytes"]]
                + [
                    int(sample.get("peak_working_set_bytes") or 0)
                    for sample in report["resource_measurements"]["samples"]
                ]
            )
        if model_before is not None:
            try:
                model_after = _model_identity()
                report["model"]["final_tree_sha256"] = model_after["tree_sha256"]
                report["model"]["unchanged_during_run"] = model_after["tree_sha256"] == model_before["tree_sha256"]
                if not report["model"]["unchanged_during_run"]:
                    report["run_status"] = "MODEL_CHANGED_DURING_RUN"
                    report["fatal_error"] = "local model/cache tree hash changed during baseline"
            except Exception as exc:
                report["model"]["unchanged_during_run"] = False
                report["model"]["final_identity_error"] = f"{type(exc).__name__}: {exc}"
                report["run_status"] = "MODEL_IDENTITY_CHECK_FAILED"
        report["finished_at_utc"] = _now_utc()
        report["summary"] = summarize_rows(report["rows"])
        validate_report(report, dataset)
        _write_report(target_report, report)
    return report


def finalize_external_stop(report_path: Path, *, status: str, reason: str) -> dict[str, Any]:
    target = _allowed_report_path(report_path)
    if status not in {"TIMEOUT", "CANCELLED", "START_ERROR", "EXTERNAL_STOP"}:
        raise ValueError("unsupported external stop status")
    report = json.loads(target.read_text(encoding="utf-8"))
    dataset, _raw, _summary = load_dataset()
    _mark_unrun_rows(report.get("rows", []), disposition=f"NOT_RUN_{status}", reason=reason)
    report["run_status"] = f"STOPPED_{status}"
    report["stop_reason"] = reason
    report["finished_at_utc"] = _now_utc()
    report["elapsed_seconds"] = round(float(report.get("elapsed_seconds") or 0.0), 6)
    report["summary"] = summarize_rows(report["rows"])
    validate_report(report, dataset)
    _write_report(target, report)
    return report


def _command_validate(_args: argparse.Namespace) -> int:
    dataset, raw, summary = load_dataset()
    protocol = baseline_protocol(dataset)
    protocol_hash = sha256_bytes(canonical_json({
        "dataset_id": dataset["dataset_id"],
        "split_protocol": dataset["split_protocol"],
        "review_rubric": dataset["review_rubric"],
        "baseline_protocol": protocol,
    }).encode("utf-8"))
    print(json.dumps({
        "status": "PASS",
        "dataset_sha256": sha256_bytes(raw),
        "protocol_sha256": protocol_hash,
        **summary,
    }, ensure_ascii=False, sort_keys=True))
    return 0


def _command_baseline(_args: argparse.Namespace) -> int:
    report = run_baseline()
    print(json.dumps({
        "report": str(DEFAULT_REPORT_PATH.resolve()),
        "run_status": report["run_status"],
        "summary": report["summary"],
        "semantic_quality_verdict": report["semantic_quality_verdict"],
    }, ensure_ascii=False, sort_keys=True))
    return 0 if report["run_status"] in {"COMPLETED", "COMPLETED_WITH_ROW_ERRORS"} else 2


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Frozen synthetic EN-to-VI quality phase 1 evaluator")
    subparsers = parser.add_subparsers(dest="command", required=True)
    validate = subparsers.add_parser("validate-dataset")
    validate.set_defaults(handler=_command_validate)
    baseline = subparsers.add_parser("opus-baseline")
    baseline.set_defaults(handler=_command_baseline)
    finalize = subparsers.add_parser("finalize-external-stop")
    finalize.add_argument("--status", choices=("TIMEOUT", "CANCELLED", "START_ERROR", "EXTERNAL_STOP"), required=True)
    finalize.add_argument("--reason", required=True)
    finalize.set_defaults(handler=lambda args: _command_finalize(args))
    args = parser.parse_args(argv)
    return int(args.handler(args))


def _command_finalize(args: argparse.Namespace) -> int:
    report = finalize_external_stop(DEFAULT_REPORT_PATH, status=args.status, reason=args.reason)
    print(json.dumps({
        "report": str(DEFAULT_REPORT_PATH.resolve()),
        "run_status": report["run_status"],
        "summary": report["summary"],
        "semantic_quality_verdict": report["semantic_quality_verdict"],
    }, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
