"""Prepare a private, candidate-agnostic semantic review packet.

This test-only tool runs the existing CT2/OPUS application task on the pinned
frozen corpus, then separates machine evidence from a blind human packet.
It never assigns a semantic verdict.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "tests" / "lib"), str(ROOT / "tests" / "tools")]

from cleanup_work_artifacts import cleanup_after_test  # noqa: E402
from local_translation_benchmark import load_frozen_manifest, sha256_path  # noqa: E402
from work_paths import (  # noqa: E402
    WORK_ROOT,
    ambient_scope,
    assert_artifact_under_work,
    new_scope_id,
    register_artifact,
)
from vntext.app_tasks import run_translate_ct2_task  # noqa: E402
from vntext.entry import Entry  # noqa: E402
from vntext.mt_check import english_report, load_whitelist, structural_problems  # noqa: E402
from vntext.mt_strategies import candidate_quality_issues  # noqa: E402
from vntext.package_io import read_csv_rows_file, write_package  # noqa: E402


CACHE_ENV_NAMES = (
    "HF_HOME",
    "HF_HUB_CACHE",
    "TRANSFORMERS_CACHE",
    "TORCH_HOME",
    "VNTEXT_DIRECT_GPU_ROOT",
)
REVIEW_FIELDS = (
    "overall",
    "severe_meaning_error",
    "omission_addition",
    "pronoun_context_error",
    "idiom_slang_sensitive_meaning",
    "vietnamese_fluency",
    "english_residue",
    "terminology_name_consistency",
    "reason",
    "recommend_human_review",
)


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8", "surrogatepass")).hexdigest()


def _source_sha() -> str:
    return subprocess.check_output(
        ["git", "-C", str(ROOT), "rev-parse", "HEAD"],
        text=True,
        stderr=subprocess.DEVNULL,
    ).strip()


def _version(name: str) -> str:
    try:
        from importlib.metadata import version

        return version(name)
    except Exception:
        return "unavailable"


def _file_identity(path: Path) -> dict[str, Any]:
    return {
        "path": str(path.resolve()),
        "bytes": path.stat().st_size,
        "sha256": sha256_path(path),
    }


def _register(path: Path, *, artifact_id: str, kind: str, purpose: str, lifecycle: str) -> None:
    ambient = ambient_scope()
    register_artifact(
        artifact_id=artifact_id,
        path=path,
        kind=kind,
        created_by="opus_semantic_packet.py",
        owner="opus_semantic_packet.py",
        purpose=purpose,
        lifecycle=lifecycle,
        scope_id=ambient["scope_id"],
        run_id=ambient["run_id"],
        scope_root=ambient["scope_root"],
    )


def _entry(row: dict) -> Entry:
    metadata = row.get("source_metadata") or {}
    entry = Entry(
        source_text=str(row["source_text"]),
        file_path=str(metadata.get("file_path") or "frozen_corpus.txt"),
        context=str(metadata.get("scene") or metadata.get("context") or ""),
        import_method="plain_text_line",
        safety="safe",
        locator={"line": metadata.get("line", row["ordinal"])},
        backend="frozen_local_translation_v1",
    ).finalize()
    # Keep the frozen canonical key in the disposable package.  The package
    # is only an input to the production route; no new identity is created.
    entry.key = str(row["key"])
    return entry


def _read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else default
    except (OSError, TypeError, ValueError):
        return default


def _read_context(package: Path) -> dict[str, dict]:
    path = package / ".mt" / "v2" / "context.jsonl"
    if not path.is_file():
        return {}
    records: dict[str, dict] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        item = json.loads(line)
        key = str(item.get("key") or "")
        if key:
            records[key] = item
    return records


def _package_cache_state(package: Path) -> dict[str, bool]:
    cache_dir = package / ".mt" / "v2"
    return {
        "cache": (cache_dir / "translation_cache.sqlite3").exists(),
        "cache_lock": (cache_dir / "translation_cache.lock").exists(),
    }


def _review_context(record: dict | None) -> str:
    if not record:
        return "NO_CONTEXT_AVAILABLE"
    pieces = [
        str(value)
        for values in (record.get("previous") or [], record.get("next") or [])
        for value in values
        if value
    ]
    speaker = str(record.get("speaker") or "").strip()
    if speaker:
        pieces.insert(0, f"Speaker: {speaker}")
    return "\n".join(pieces) if pieces else "NO_CONTEXT_AVAILABLE"


def _blank_reviewer() -> dict[str, str]:
    return {field: "" for field in REVIEW_FIELDS}


def review_schema() -> dict[str, Any]:
    """Return the reusable reviewer contract without candidate-specific rules."""

    return {
        "schema_version": 1,
        "schema_id": "vntext-semantic-review-v1",
        "candidate_agnostic": True,
        "semantic_status_values": ["NOT_REVIEWED", "REVIEWED"],
        "overall_values": ["PASS", "MINOR", "MAJOR", "UNDECIDABLE"],
        "binary_values": ["YES", "NO", "UNDECIDABLE"],
        "recommend_human_review_values": ["YES", "NO"],
        "reviewer_slots": ["reviewer_a", "reviewer_b"],
        "fields": [
            {"name": "overall", "kind": "choice", "values": ["PASS", "MINOR", "MAJOR", "UNDECIDABLE"]},
            {"name": "severe_meaning_error", "kind": "choice", "values": ["YES", "NO", "UNDECIDABLE"]},
            {"name": "omission_addition", "kind": "choice", "values": ["YES", "NO", "UNDECIDABLE"]},
            {"name": "pronoun_context_error", "kind": "choice", "values": ["YES", "NO", "UNDECIDABLE"]},
            {"name": "idiom_slang_sensitive_meaning", "kind": "choice", "values": ["YES", "NO", "UNDECIDABLE"]},
            {"name": "vietnamese_fluency", "kind": "choice", "values": ["PASS", "MINOR", "MAJOR", "UNDECIDABLE"]},
            {"name": "english_residue", "kind": "choice", "values": ["YES", "NO", "UNDECIDABLE"]},
            {"name": "terminology_name_consistency", "kind": "choice", "values": ["PASS", "MINOR", "MAJOR", "UNDECIDABLE"]},
            {"name": "reason", "kind": "free_text"},
            {"name": "recommend_human_review", "kind": "choice", "values": ["YES", "NO"]},
        ],
        "instructions": [
            "Review source meaning against the candidate translation.",
            "Use reviewer context only when it is present; it does not describe model input.",
            "Leave a field blank until a human reviewer makes the decision.",
        ],
    }


def _build_packet(rows: list[dict]) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "packet_type": "semantic_review_packet",
        "review_schema_id": "vntext-semantic-review-v1",
        "candidate_agnostic": True,
        "row_count": len(rows),
        "semantic_status": "NOT_REVIEWED",
        "rows": [
            {
                "anonymized_id": row["anonymized_id"],
                "source_text": row["source"],
                "candidate_translation": row["candidate_translation"],
                "context_for_reviewer": row["reviewer_context"],
                "reviewer_a": _blank_reviewer(),
                "reviewer_b": _blank_reviewer(),
                "semantic_status": "NOT_REVIEWED",
            }
            for row in rows
        ],
    }


def _build_mapping(rows: list[dict], source_sha: str) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "mapping_type": "private_frozen_corpus_review_mapping",
        "source_sha": source_sha,
        "row_count": len(rows),
        "rows": [
            {
                "anonymized_id": row["anonymized_id"],
                "ordinal": row["ordinal"],
                "canonical_key": row["key"],
                "category": row["category"],
            }
            for row in rows
        ],
    }


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _select_output_dir(requested: Path, run_id: str) -> Path:
    """Keep a rerun from reusing a retained packet directory."""

    requested = requested.expanduser().resolve()
    if not requested.exists() or (requested.is_dir() and not any(requested.iterdir())):
        return requested
    candidate = requested.parent / f"{requested.name}_{run_id}"
    suffix = 2
    while candidate.exists():
        candidate = requested.parent / f"{requested.name}_{run_id}_{suffix}"
        suffix += 1
    return candidate


def _completion_gate(
    *,
    status: dict[str, Any],
    expected_rows: list[dict],
    translated_rows: list[dict],
    review_rows: list[dict],
    technical_rows: list[dict],
    report_rows: list[dict],
) -> list[dict[str, Any]]:
    """Return concrete failures for the private baseline completion contract."""

    failures: list[dict[str, Any]] = []
    expected_keys = [str(row.get("key") or "") for row in expected_rows]

    if len(expected_rows) != 30:
        failures.append({"check": "frozen_corpus.row_count", "actual": len(expected_rows), "expected": 30})

    if not isinstance(status, dict):
        failures.append({"check": "translate_status.type", "actual": type(status).__name__, "expected": "object"})
        status = {}
    if status.get("complete") is not True:
        failures.append({"check": "translate_status.complete", "actual": status.get("complete"), "expected": True})
    for field in ("pending", "review_only", "blocked"):
        value = status.get(field)
        if type(value) is not int:
            failures.append({"check": f"translate_status.{field}", "actual": value, "expected": 0})
        elif value != 0:
            failures.append({"check": f"translate_status.{field}", "actual": value, "expected": 0})

    def check_keys(label: str, rows: list[dict]) -> None:
        actual_keys = [str(row.get("key") or "") for row in rows]
        if actual_keys != expected_keys:
            failures.append(
                {
                    "check": f"{label}.keys_order",
                    "actual": actual_keys,
                    "expected": expected_keys,
                }
            )

    check_keys("translation.csv", translated_rows)
    blank_translations = [
        {"ordinal": index, "key": str(row.get("key") or "")}
        for index, row in enumerate(translated_rows, 1)
        if not str(row.get("translation") or "").strip()
    ]
    if blank_translations:
        failures.append(
            {
                "check": "translation.csv.non_empty_translation",
                "actual": blank_translations,
                "expected": "all 30 rows non-blank",
            }
        )

    if review_rows:
        failures.append(
            {
                "check": "review_only.csv.empty",
                "actual": {"count": len(review_rows), "keys": [str(row.get("key") or "") for row in review_rows]},
                "expected": {"count": 0},
            }
        )
    if technical_rows:
        failures.append(
            {
                "check": "technical_skipped.csv.empty",
                "actual": {"count": len(technical_rows), "keys": [str(row.get("key") or "") for row in technical_rows]},
                "expected": {"count": 0},
            }
        )

    check_keys("baseline_report", report_rows)
    if len(report_rows) == len(translated_rows) == len(expected_rows):
        report_translation_mismatches = [
            {
                "ordinal": index,
                "key": expected_keys[index - 1],
                "report": str(report_row.get("candidate_translation") or ""),
                "translation_csv": str(csv_row.get("translation") or ""),
            }
            for index, (report_row, csv_row) in enumerate(zip(report_rows, translated_rows), 1)
            if str(report_row.get("candidate_translation") or "") != str(csv_row.get("translation") or "")
        ]
        if report_translation_mismatches:
            failures.append(
                {
                    "check": "baseline_report.translation_alignment",
                    "actual": report_translation_mismatches,
                    "expected": "report candidate matches translation.csv",
                }
            )

    structural_failures = [
        {
            "ordinal": index,
            "key": str(row.get("key") or ""),
            "actual": row.get("structural_verdict"),
            "expected": "PASS",
        }
        for index, row in enumerate(report_rows, 1)
        if row.get("structural_verdict") != "PASS"
    ]
    if structural_failures:
        failures.append({"check": "baseline_report.structural_verdict", "actual": structural_failures, "expected": "PASS for every row"})

    return failures


def _publish_review_artifacts(
    output: Path,
    report_rows: list[dict],
    source_sha: str,
    *,
    completion_gate_passed: bool,
) -> dict[str, str]:
    """Publish reviewer artifacts only after the completion gate succeeds."""

    if not completion_gate_passed:
        return {}
    paths = {
        "blind_packet": output / "blind_review_packet.json",
        "private_mapping": output / "private_id_mapping.json",
        "review_schema": output / "semantic_review_schema.json",
    }
    _write_json(paths["review_schema"], review_schema())
    _write_json(paths["private_mapping"], _build_mapping(report_rows, source_sha))
    _write_json(paths["blind_packet"], _build_packet(report_rows))
    _register(paths["blind_packet"], artifact_id=f"opus-semantic-packet:{output.name}", kind="semantic_review_packet", purpose="retained blind human review packet", lifecycle="RETAINED")
    _register(paths["private_mapping"], artifact_id=f"opus-semantic-mapping:{output.name}", kind="private_review_mapping", purpose="retained private frozen-row mapping", lifecycle="RETAINED")
    _register(paths["review_schema"], artifact_id=f"opus-semantic-schema:{output.name}", kind="review_schema", purpose="retained candidate-agnostic review rubric", lifecycle="RETAINED")
    return {name: str(path) for name, path in paths.items()}


def _read_output_csv(path: Path, *, required: bool, label: str) -> tuple[list[str], list[dict]]:
    if required and not path.is_file():
        raise FileNotFoundError(f"{label} missing: {path}")
    if not path.is_file():
        return [], []
    try:
        return read_csv_rows_file(path)
    except Exception as exc:
        raise ValueError(f"{label} parse failed: {type(exc).__name__}: {exc}") from exc


def run_baseline(
    manifest_path: Path,
    identity_path: Path,
    source_corpus_path: Path | None,
    model_dir: Path,
    output_dir: Path,
) -> dict[str, Any]:
    source_sha = _source_sha()
    manifest = load_frozen_manifest(
        manifest_path.expanduser().resolve(),
        source_corpus_path=source_corpus_path.expanduser().resolve() if source_corpus_path else None,
        identity_path=identity_path.expanduser().resolve(),
    )
    model = model_dir.expanduser().resolve()
    assert_artifact_under_work(model, "OPUS baseline model")
    if not (model / "model.bin").is_file():
        raise FileNotFoundError(f"OPUS model.bin missing: {model}")

    run_id = new_scope_id("opus-semantic-payload")
    output = _select_output_dir(output_dir, run_id)
    assert_artifact_under_work(output, "retained OPUS semantic packet")
    output.mkdir(parents=True, exist_ok=True)
    _register(output, artifact_id=f"opus-semantic-output:{output.name}", kind="semantic_review_packet", purpose="retained private OPUS baseline evidence and blind packet", lifecycle="RETAINED")

    ambient = ambient_scope()
    payload = WORK_ROOT / "local_translation_benchmark" / run_id
    package = payload / "package"
    cache_root = payload / "cache"
    _register(payload, artifact_id=f"opus-semantic-payload:{run_id}", kind="benchmark_workspace", purpose="disposable production-route package and cache", lifecycle="DISPOSABLE")
    _register(package, artifact_id=f"opus-semantic-package:{run_id}", kind="translation_package", purpose="disposable package for exact production CT2 route", lifecycle="DISPOSABLE")
    _register(cache_root, artifact_id=f"opus-semantic-cache:{run_id}", kind="benchmark_cache", purpose="disposable cache scope for baseline child state", lifecycle="DISPOSABLE")

    report: dict[str, Any] = {
        "schema_version": 1,
        "source_sha": source_sha,
        "branch": "master",
        "command": list(sys.argv),
        "manifest_path": str(manifest_path.expanduser().resolve()),
        "identity_path": str(identity_path.expanduser().resolve()),
        "manifest_sha256": manifest["manifest_sha256"],
        "corpus_sha256": manifest["corpus_sha256"],
        "ordered_key_source_sha256": manifest["ordered_key_source_sha256"],
        "identity_sha256": sha256_path(identity_path.expanduser().resolve()),
        "source_corpus": manifest["source_corpus"],
        "row_count": manifest["row_count"],
        "category_counts": manifest["category_counts"],
        "semantic_status": "NOT_REVIEWED",
        "context_used_by_model": False,
        "human_review_required": False,
        "actual_production_route": [
            "vntext.package_io.write_package(enable_trace=True)",
            "vntext.app_tasks.run_translate_ct2_task",
            "vntext.app_tasks._run_traced_translation",
            "vntext.mt_ct2_pipeline.run_ct2_translate",
            "classify_row_authoritative",
            "load_user_glossary + load_compatible_entries",
            "load_translation_memory/build_translation_memory",
            "_batch_translate_chunk + retry_row_strategies",
            "_safe_candidate + Patch Gate + candidate_quality_issues",
            "_ReviewSink + review reconciliation + write_translate_status",
        ],
        "context_contract": {
            "status": "METADATA_ONLY",
            "model_injection": False,
            "reviewer_context_is_not_model_context": True,
        },
        "clean_baseline": {
            "human_review_required": False,
            "manual_correction": False,
            "test_added_glossary": False,
            "test_added_translation_memory": False,
            "fresh_package": True,
        },
        "model": {
            "engine": "CTranslate2",
            "family": "OPUS",
            "model_dir": str(model),
            "files": [_file_identity(path) for path in sorted(model.iterdir()) if path.is_file()],
            "runtime": {
                "python": platform.python_version(),
                "ctranslate2": _version("ctranslate2"),
                "transformers": _version("transformers"),
            },
        },
        "scope": {
            "scope_id": ambient["scope_id"],
            "run_id": ambient["run_id"],
            "payload_run_id": run_id,
            "payload_root": str(payload),
            "cache_root": str(cache_root),
            "cache_env_names": list(CACHE_ENV_NAMES),
        },
        "requested_output_dir": str(output_dir.expanduser().resolve()),
        "output_dir": str(output),
        "completion_gate": {"status": "NOT_RUN", "failures": []},
        "rows": [],
    }
    old_env = {name: os.environ.get(name) for name in CACHE_ENV_NAMES}
    completions: list[dict] = []
    logs: list[str] = []
    progress: list[dict] = []
    route_error = ""
    try:
        entries = [_entry(row) for row in manifest["rows"]]
        write_package(
            str(package),
            entries,
            [],
            {"files_scanned": 1, "frozen_local_translation_v1": True},
            separate_review=False,
            enable_trace=True,
        )
        initial_fields, initial_rows = read_csv_rows_file(package / "translation.csv")
        initial_keys = [str(row.get("key") or "") for row in initial_rows]
        if len(initial_rows) != 30 or initial_keys != [str(row["key"]) for row in manifest["rows"]]:
            raise ValueError("production package did not preserve exact frozen rows/order")
        report["clean_baseline"]["package_state_before_translation"] = {
            "glossary": (package / ".mt" / "glossary.json").exists(),
            "glossary_v2": (package / ".mt" / "v2" / "glossary.json").exists(),
            "translation_memory": (package / ".mt" / "translation_memory.json").exists(),
            **_package_cache_state(package),
            "csv_fields": initial_fields,
        }
        for name in CACHE_ENV_NAMES:
            os.environ[name] = str(cache_root / name)
        run_translate_ct2_task(
            package / "translation.csv",
            package,
            True,
            model_dir=str(model),
            human_review_required=False,
            progress=lambda payload: progress.append(dict(payload or {})),
            log=lambda message: logs.append(str(message)),
            complete=lambda payload: completions.append(dict(payload or {})),
            is_cancelled=lambda: False,
        )
        fields, translated_rows = _read_output_csv(package / "translation.csv", required=True, label="translation.csv")
        translated_by_key = {str(row.get("key") or ""): row for row in translated_rows}
        _, review_rows = _read_output_csv(package / "review_only.csv", required=False, label="review_only.csv")
        review_by_key = {str(row.get("key") or ""): row for row in review_rows}
        _, technical_rows = _read_output_csv(package / "technical_skipped.csv", required=False, label="technical_skipped.csv")
        technical_by_key = {str(row.get("key") or ""): row for row in technical_rows}
        status = _read_json(package / ".mt" / "translate_status.json", {})
        blocker_inventory = _read_json(package / ".mt" / "blocker_inventory.json", {})
        blocker_by_key = {
            str(item.get("key") or ""): item
            for item in blocker_inventory.get("rows") or []
            if isinstance(item, dict) and item.get("key")
        }
        context_by_key = _read_context(package)
        whitelist = load_whitelist(package)
        model_metadata = status.get("model_metadata") if isinstance(status, dict) else None
        report["route_completion"] = completions[-1] if completions else {}
        report["logs"] = logs
        report["progress_event_count"] = len(progress)
        report["translate_status"] = status
        report["model_metadata"] = model_metadata
        report["trace"] = {
            name: str(package / ".mt" / name)
            for name in ("trace_summary.json", "trace_export.jsonl", "diagnostic_summary.json")
            if (package / ".mt" / name).is_file()
        }
        report["clean_baseline"]["package_state_after_translation"] = {
            "glossary_fingerprint": status.get("glossary_fingerprint", "") if isinstance(status, dict) else "",
            "glossary_v2_fingerprint": status.get("glossary_v2_fingerprint", "") if isinstance(status, dict) else "",
            "memory_fingerprint": status.get("memory_fingerprint", "") if isinstance(status, dict) else "",
            "translation_memory_generated_by_route": (package / ".mt" / "translation_memory.json").is_file(),
            "cache_created_by_route": _package_cache_state(package)["cache"],
            "cache_lock_released": not _package_cache_state(package)["cache_lock"],
        }
        for ordinal, source_row in enumerate(manifest["rows"], 1):
            key = str(source_row["key"])
            translated = translated_by_key.get(key, {})
            review = review_by_key.get(key, {})
            technical = technical_by_key.get(key, {})
            blocker = blocker_by_key.get(key, {})
            candidate = str(translated.get("translation") or "")
            raw_candidate = str(
                ((blocker.get("initial") or {}).get("raw_output") or blocker.get("candidate") or "")
            )
            if candidate:
                structural = structural_problems({"key": key, "source_text": source_row["source_text"]}, candidate)
                quality = candidate_quality_issues({"key": key, "source_text": source_row["source_text"]}, candidate, whitelist)
                english_score, english_reasons = english_report(source_row["source_text"], candidate, whitelist)
                status_value = "TRANSLATED"
            else:
                structural, quality, english_score, english_reasons = [], [], 0, []
                status_value = "BLOCKED_REVIEW_ONLY" if review else ("TECHNICAL_SKIP" if technical else "PENDING")
            context_record = context_by_key.get(key) or {}
            row_record = {
                "anonymized_id": f"ROW-{ordinal:03d}",
                "ordinal": ordinal,
                "key": key,
                "category": source_row["category"],
                "source": source_row["source_text"],
                "candidate_translation": candidate,
                "raw_candidate_if_blocked": raw_candidate,
                "status": status_value,
                "route": str(blocker.get("route") or ("production_ct2" if candidate else "review_only")),
                "structural_verdict": "PASS" if candidate and not structural else ("FAIL" if candidate else "NOT_AVAILABLE"),
                "structural_reasons": structural,
                "automated_quality_verdict": "PASS" if candidate and not quality else ("REVIEW_REQUIRED" if candidate else "NOT_AVAILABLE"),
                "automated_quality_reasons": quality,
                "english_residue": {
                    "score": english_score,
                    "verdict": "PASS" if candidate and not english_reasons else ("REVIEW_REQUIRED" if candidate else "NOT_AVAILABLE"),
                    "reasons": english_reasons,
                },
                "semantic_status": "NOT_REVIEWED",
                "context_availability": "REVIEWER_CONTEXT_AVAILABLE" if _review_context(context_record) != "NO_CONTEXT_AVAILABLE" else "NO_CONTEXT_AVAILABLE",
                "reviewer_context": _review_context(context_record),
                "context_used_by_model": False,
                "context_sidecar_status": str(context_record.get("status") or "METADATA_ONLY"),
                "trace_provenance": {
                    "blocker": blocker,
                    "review_row_present": bool(review),
                    "technical_row_present": bool(technical),
                },
            }
            report["rows"].append(row_record)
        gate_failures = _completion_gate(
            status=status,
            expected_rows=manifest["rows"],
            translated_rows=translated_rows,
            review_rows=review_rows,
            technical_rows=technical_rows,
            report_rows=report["rows"],
        )
        report["completion_gate"] = {
            "status": "PASS" if not gate_failures else "FAIL",
            "failures": gate_failures,
        }
        if gate_failures:
            route_error = f"completion gate failed: {gate_failures[0]['check']}"
            report["baseline_status"] = "BASELINE_FAILED"
            report["error"] = route_error
        else:
            report["baseline_status"] = "BASELINE_COMPLETE"
    except Exception as exc:
        route_error = f"{type(exc).__name__}: {exc}"
        report["baseline_status"] = "BASELINE_FAILED"
        report["error"] = route_error
    finally:
        for name, value in old_env.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value
        try:
            from vntext.mt_ct2_model import reset_translator_cache

            reset_translator_cache()
        except Exception as exc:
            report.setdefault("cleanup_warnings", []).append(f"translator reset: {exc}")
        cleanup_outcome = "PASS" if report.get("baseline_status") == "BASELINE_COMPLETE" else "FAIL"
        report["cleanup"] = cleanup_after_test(
            [payload],
            reason="opus semantic baseline disposable production package",
            outcome=cleanup_outcome,
            scope_id=ambient_scope()["scope_id"],
            run_id=ambient_scope()["run_id"],
        )
        report["cleanup_summary"] = {
            "payload_removed": cleanup_outcome == "PASS" and bool(report["cleanup"].get("ok")),
            "processes_remaining": [],
            "current_scope_unknown": report["cleanup"].get("unknown", []),
            "current_scope_locked": report["cleanup"].get("locked", []),
            "current_scope_stale": report["cleanup"].get("stale", []),
            "released_bytes": report["cleanup"].get("freed_gb", 0),
        }
        report["output_files"] = {
            "baseline_report": str(output / "opus_baseline_report.json"),
            "blind_packet": None,
            "private_mapping": None,
            "review_schema": None,
        }
        report_rows = report.get("rows") or []
        report["output_files"].update(
            _publish_review_artifacts(
                output,
                report_rows,
                source_sha,
                completion_gate_passed=report.get("baseline_status") == "BASELINE_COMPLETE",
            )
        )
        _register(output / "opus_baseline_report.json", artifact_id=f"opus-semantic-report:{output.name}", kind="benchmark_report", purpose="retained private OPUS baseline evidence", lifecycle="RETAINED")
        _write_json(output / "opus_baseline_report.json", report)
    if route_error:
        return report
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run exact OPUS frozen-corpus baseline and prepare blind review packet")
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--identity", type=Path, required=True)
    parser.add_argument("--source-corpus", type=Path, default=None)
    parser.add_argument("--model-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    report = run_baseline(
        args.manifest,
        args.identity,
        args.source_corpus,
        args.model_dir,
        args.output_dir,
    )
    print(
        json.dumps(
            {
                "baseline_status": report.get("baseline_status"),
                "row_count": report.get("row_count"),
                "output_dir": report.get("output_dir"),
            },
            ensure_ascii=False,
        )
    )
    return 0 if report.get("baseline_status") == "BASELINE_COMPLETE" else 1


if __name__ == "__main__":
    raise SystemExit(main())
