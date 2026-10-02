"""Background task runners shared by Tk and Qt UIs (no widget code)."""
from __future__ import annotations

import json
import hashlib
import uuid
import os
import shutil
import tempfile
from pathlib import Path
from typing import Callable

from vntext.mt_ct2 import (
    EmptyCsvError,
    ModelNotReadyError,
    TranslateStatusError,
    TranslateCancelled,
    run_ct2_translate,
    run_ct2_translate_keys,
    write_translate_status,
)
from vntext.package_io import resolve_translation_package_dir
from vntext.app_backend import (
    VERSION,
    apply_translation_package,
    auto_process_raw_candidates,
    build_asset_index,
    extract_project,
    export_unity_internal_dump,
    write_package,
)
from vntext.patch import detect_patch_engine, write_patch_manifest

ProgressFn = Callable[[dict], None]
LogFn = Callable[[str], None]
CompleteFn = Callable[[dict], None]


def _load_trace_manifest(package_dir: Path) -> dict:
    """Load the package identity before any traced task mutates its output."""

    manifest_path = package_dir / "manifest.json"
    if not manifest_path.is_file():
        raise RuntimeError("Traceability requires package manifest.json before task mutation")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError, TypeError) as exc:
        raise RuntimeError(f"Traceability cannot read package manifest: {exc}") from exc
    if not isinstance(manifest, dict):
        raise RuntimeError("Traceability package manifest must be a JSON object")
    return manifest


def _open_package_trace(package_dir: Path, pipeline: str, **metadata):
    from vntext.traceability import TraceStore

    manifest = _load_trace_manifest(package_dir)
    trace = TraceStore.for_package(package_dir, manifest)
    trace.start_run(metadata={"pipeline": pipeline, **metadata})
    return trace, manifest


def _trace_manifest_entries(trace, manifest: dict) -> dict[str, dict]:
    """Register existing package metadata for a task without changing it."""

    from vntext.traceability import (
        CLASSIFICATION_MAIN,
        CLASSIFICATION_REVIEW,
        CLASSIFICATION_SKIP,
    )

    registered: dict[str, dict] = {}
    with trace.batch():
        for item in manifest.get("entries", []) or []:
            if not isinstance(item, dict):
                raise RuntimeError("Traceability manifest entries must be objects")
            if not item.get("key"):
                raise RuntimeError("Traceability manifest entry is missing key")
            review_only = bool(item.get("review_only"))
            info = trace.register_entry(
                item,
                classification=CLASSIFICATION_REVIEW if review_only else CLASSIFICATION_MAIN,
                classification_reason="review_only" if review_only else "main translation flow",
                metadata={"source": "manifest"},
            )
            registered[str(item["key"])] = {"entry": item, **info}
        for item in manifest.get("technical_skipped", []) or []:
            if not isinstance(item, dict):
                raise RuntimeError("Traceability technical_skipped entries must be objects")
            if not item.get("key"):
                raise RuntimeError("Traceability technical_skipped entry is missing key")
            reason = str(item.get("reason") or "technical skip")
            info = trace.register_entry(
                item,
                classification=CLASSIFICATION_SKIP,
                classification_reason=reason,
                metadata={"source": "technical_skipped"},
            )
            registered[str(item["key"])] = {"entry": item, **info}
    return registered


def _trace_finish_run(trace, *, status: str, root_cause: str | None = None) -> None:
    if trace is None or trace.run_id is None:
        return
    trace.finish_run(status, root_cause)


def _trace_abort_actions(
    trace,
    actions: dict[str, dict],
    *,
    error: str,
    root_cause: str | None = None,
) -> None:
    from vntext.traceability import EVENT_ABORTED, ROOT_CAUSE_UNKNOWN

    terminal_root = root_cause or ROOT_CAUSE_UNKNOWN
    for item in actions.values():
        if item.get("finished"):
            continue
        try:
            trace.finish_event(
                item["action_id"],
                EVENT_ABORTED,
                root_cause=terminal_root,
                payload={"error": error, "aborted": True},
            )
            item["finished"] = True
        except Exception:
            # The store's crash recovery remains the final safety net if a
            # terminal trace write itself cannot be made.
            pass


def _sha256_if_file(path: Path) -> str:
    if not path.is_file():
        return ""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _ct2_trace_model_revision(model_dir: str = "") -> str:
    """Resolve the concrete CT2 model path used by trace/cache provenance."""

    try:
        from vntext.mt_ct2_model import resolve_model_dir

        explicit = Path(model_dir) if model_dir else None
        return str(resolve_model_dir(explicit).resolve())
    except (OSError, TypeError, ValueError):
        # Trace setup must not hide the real model-loading error.  Keep a
        # deterministic fallback when an unusual caller supplies a path that
        # cannot be resolved yet.
        return str(Path(model_dir).resolve()) if model_dir else "default"


_DIAGNOSTIC_ROOT_ROUTES = (
    ("PATCH_VERIFY_FAILED", "PATCH"),
    ("PATCH_FAILED", "PATCH"),
    ("TRANSLATION_INVALID", "TRANSLATE"),
    ("TRANSLATION_MISSED", "TRANSLATE"),
    ("MISCLASSIFIED", "CLASSIFY"),
    ("DISCOVERY_GAP", "EXTRACT"),
    ("EXTRACT_MISSED", "EXTRACT"),
    ("RUNTIME_SOURCE_MISMATCH", "RUNTIME"),
    ("FONT_RENDER", "RUNTIME"),
    ("UNKNOWN", "WORKFLOW"),
)


def _diagnostic_count(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return 0
    return value


def _diagnostic_completion_fields(
    package_dir: Path,
    *,
    fallback_path: Path | str | None = None,
    fallback_stage: str = "WORKFLOW",
    fallback_root_cause: str | None = None,
    fallback_affected_count: int | None = None,
    fallback_action: str = "",
    fallback_status: str = "FAILED",
) -> dict[str, object]:
    """Adapt package trace evidence into a compact worker completion payload.

    ``diagnostic_summary.json`` is the producer-side evidence.  This helper is
    intentionally conservative: it only selects root causes already recorded
    by the trace store or an explicit caller fallback.  It never invents a
    candidate count and never treats a missing sidecar as a successful run.
    """

    package_dir = Path(package_dir).expanduser().resolve()
    summary_path = package_dir / ".mt" / "diagnostic_summary.json"
    summary: dict[str, object] = {}
    if summary_path.is_file():
        try:
            loaded = json.loads(summary_path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                summary = loaded
        except (OSError, TypeError, ValueError, json.JSONDecodeError):
            summary = {}

    root_counts = summary.get("root_cause_counts")
    if not isinstance(root_counts, dict):
        root_counts = {}
    classification_counts = summary.get("classification_counts")
    if not isinstance(classification_counts, dict):
        classification_counts = {}
    measurements = summary.get("translation")
    if not isinstance(measurements, dict):
        measurements = {}
    patch_measurements = summary.get("patch")
    if not isinstance(patch_measurements, dict):
        patch_measurements = {}

    root = ""
    stage = ""
    affected = 0
    for candidate, candidate_stage in _DIAGNOSTIC_ROOT_ROUTES:
        count = _diagnostic_count(root_counts.get(candidate))
        if count:
            root = candidate
            stage = candidate_stage
            affected = count
            break

    if not root:
        # Some older trace summaries contain measured stage counters but no
        # per-entry root cause.  These counters still identify a bounded
        # translation/patch failure without claiming a more specific cause.
        invalid = _diagnostic_count(measurements.get("translation_invalid"))
        missed = _diagnostic_count(measurements.get("translation_missed"))
        readback_failed = _diagnostic_count(patch_measurements.get("readback_failed_targets"))
        if readback_failed:
            root, stage, affected = "PATCH_VERIFY_FAILED", "PATCH", readback_failed
        elif invalid:
            root, stage, affected = "TRANSLATION_INVALID", "TRANSLATE", invalid
        elif missed:
            root, stage, affected = "TRANSLATION_MISSED", "TRANSLATE", missed

    review_count = _diagnostic_count(classification_counts.get("REVIEW"))
    unsupported_count = _diagnostic_count(classification_counts.get("UNSUPPORTED"))
    if not root and review_count + unsupported_count:
        root, stage, affected = "UNKNOWN", "CLASSIFY", review_count + unsupported_count

    if not root and fallback_root_cause:
        root = str(fallback_root_cause).strip().upper() or "UNKNOWN"
        stage = str(fallback_stage or "WORKFLOW").strip().upper() or "WORKFLOW"
        affected = _diagnostic_count(fallback_affected_count)

    if not root:
        return {}

    if not affected:
        affected = _diagnostic_count(fallback_affected_count) or 1
    action = str(summary.get("actionable_next_step") or fallback_action or "").strip()
    if not action:
        action = "Mở diagnostic evidence và xử lý nguyên nhân trước khi chạy lại bước này."
    status = str(summary.get("status") or fallback_status or "FAILED").strip().upper() or "FAILED"
    evidence_path = summary_path if summary_path.is_file() else None
    if evidence_path is None and fallback_path is not None:
        candidate_path = Path(fallback_path).expanduser().resolve()
        if candidate_path.is_file():
            evidence_path = candidate_path

    fields: dict[str, object] = {
        "diagnostic_stage": stage or str(fallback_stage or "WORKFLOW").strip().upper(),
        "diagnostic_root_cause": root,
        "diagnostic_affected_count": affected,
        "diagnostic_action": action,
        "diagnostic_status": status,
    }
    if evidence_path is not None:
        fields["diagnostic_path"] = str(evidence_path)
    return fields


def _trace_translation_start(
    trace,
    manifest: dict,
    csv_path: Path,
    *,
    only_keys: set[str] | None = None,
    model_dir: str = "",
    model_revision: str = "",
    model_engine: str = "CTranslate2/OPUS-MT",
    overwrite: bool = False,
) -> tuple[dict[str, dict], dict[str, str], dict[str, object]]:
    from vntext.mt_classify import (
        CLASSIFIER_POLICY_HASH,
        CLASSIFIER_POLICY_VERSION,
        classify_row_authoritative,
    )
    from vntext.package_io import read_csv_rows_file
    from vntext.package_io import _classifier_matches_package_classification
    from vntext.traceability import (
        CLASSIFICATION_MAIN,
        EVENT_FAILED,
        ROOT_CAUSE_MISCLASSIFIED,
        STAGE_CLASSIFIED,
        STAGE_TRANSLATED,
    )

    _fields, csv_rows = read_csv_rows_file(csv_path)
    initial = {str(row.get("key") or ""): str(row.get("translation") or "") for row in csv_rows}
    registered = _trace_manifest_entries(trace, manifest)
    actions: dict[str, dict] = {}
    misclassified = 0
    for item in manifest.get("entries", []) or []:
        if not isinstance(item, dict) or not item.get("key"):
            continue
        key = str(item["key"])
        if only_keys is not None and key not in only_keys:
            continue
        if bool(item.get("review_only")):
            continue
        row = {**item, "translation": initial.get(key, "")}
        action, reason, decision = classify_row_authoritative(row)
        if not _classifier_matches_package_classification(CLASSIFICATION_MAIN, decision):
            misclassified += 1
            trace.record_event(
                STAGE_CLASSIFIED,
                status=EVENT_FAILED,
                trace_id=registered[key]["trace_id"],
                root_cause=ROOT_CAUSE_MISCLASSIFIED,
                payload={
                    "source": "translate",
                    "classification": CLASSIFICATION_MAIN,
                    "classifier_v2": decision.to_dict(),
                    "classification_mismatch": {
                        "actual": CLASSIFICATION_MAIN,
                        "expected_decision": decision.decision,
                        "expected_ledger": decision.ledger,
                        "reason_code": decision.reason_code,
                    },
                },
            )
            continue
        if action not in {
            "translate",
            "translate_synonym",
            "done",
            "copy_source",
            "copy_literal",
            "ui_label_fixed",
            "skip_ui_label",
        }:
            continue
        # Trace model attempts plus deterministic and frozen routes.  Existing
        # values remain frozen unless an explicit overwrite pass changes them.
        if initial.get(key, "").strip() and not overwrite:
            if action != "done":
                continue
        info = registered.get(key)
        if not info:
            # A malformed/stale manifest must not silently create a trace-less
            # translation attempt.
            raise RuntimeError(f"Traceability manifest entry missing registration: {key}")
        attempt_id = str(uuid.uuid4())
        provenance = (
            "model"
            if action in {"translate", "translate_synonym"}
            else ("existing_translation" if action == "done" else "deterministic_policy")
        )
        action_id = trace.start_event(
            STAGE_TRANSLATED,
            trace_id=info["trace_id"],
            target_id=info["target_ids"][0] if info.get("target_ids") else None,
            attempt_id=attempt_id,
            payload={
                "classification_action": action,
                "classification_reason": str(reason or action),
                "classifier_v2": decision.to_dict(),
                "model_engine": model_engine,
                "model_revision": model_revision or model_dir or "default",
                "provenance": provenance,
                "glossary_fingerprint": _sha256_if_file(csv_path.parent / ".mt" / "glossary.json"),
                "glossary_v2_fingerprint": _sha256_if_file(csv_path.parent / ".mt" / "v2" / "glossary.json"),
                "context_fingerprint": _sha256_if_file(csv_path.parent / ".mt" / "v2" / "context.jsonl"),
                "context_builder_version": "local-translation-v2-context-1",
                "memory_fingerprint": _sha256_if_file(csv_path.parent / ".mt" / "translation_memory.json"),
            },
        )
        actions[key] = {
            "action_id": action_id,
            "trace_id": info["trace_id"],
            "attempt_id": attempt_id,
            "initial_translation": initial.get(key, ""),
            "finished": False,
            "action": action,
            "classifier_v2": decision.to_dict(),
            "provenance": provenance,
        }
    return actions, initial, {
        "candidate_count": len(actions),
        "misclassified": misclassified,
        "model_engine": model_engine,
        "model_revision": model_revision or model_dir or "default",
        "classifier_policy_version": CLASSIFIER_POLICY_VERSION,
        "classifier_policy_hash": CLASSIFIER_POLICY_HASH,
        "glossary_fingerprint": _sha256_if_file(csv_path.parent / ".mt" / "glossary.json"),
        "glossary_v2_fingerprint": _sha256_if_file(csv_path.parent / ".mt" / "v2" / "glossary.json"),
        "context_fingerprint": _sha256_if_file(csv_path.parent / ".mt" / "v2" / "context.jsonl"),
        "context_builder_version": "local-translation-v2-context-1",
        "context_status": "METADATA_ONLY",
        "trace_coverage": {
            "status": "TRACE_ENABLED",
            "caller": "vntext.app_tasks._run_traced_translation",
            "untraced_caller_count": 0,
        },
        "memory_fingerprint": _sha256_if_file(csv_path.parent / ".mt" / "translation_memory.json"),
        "cache": {
            "kind": "validated_translation_cache",
            "status": "pending",
            "hits": 0,
            "misses": len(actions),
        },
    }


def _trace_translation_finish(
    trace,
    actions: dict[str, dict],
    initial: dict[str, str],
    csv_path: Path,
    result: dict,
    metadata: dict[str, object],
) -> dict[str, int | bool]:
    from vntext.package_io import read_csv_rows_file
    from vntext.traceability import (
        EVENT_FAILED,
        EVENT_COMPLETED,
        ROOT_CAUSE_TRANSLATION_INVALID,
        ROOT_CAUSE_TRANSLATION_MISSED,
        STAGE_VALIDATED,
    )

    _fields, csv_rows = read_csv_rows_file(csv_path)
    current = {str(row.get("key") or ""): row for row in csv_rows}
    cache_result = result.get("cache") if isinstance(result.get("cache"), dict) else None
    cache_fingerprints = result.get("cache_fingerprints")
    if not isinstance(cache_fingerprints, dict):
        cache_fingerprints = {}
    retry_attempts_by_key = result.get("retry_attempts_by_key")
    if not isinstance(retry_attempts_by_key, dict):
        retry_attempts_by_key = {}
    blocker_by_key: dict[str, dict] = {}
    blocker_path = csv_path.parent / ".mt" / "blocker_inventory.json"
    if blocker_path.is_file():
        try:
            blocker_payload = json.loads(blocker_path.read_text(encoding="utf-8"))
            blocker_by_key = {
                str(item.get("key") or ""): item
                for item in blocker_payload.get("rows", [])
                if isinstance(item, dict) and item.get("key")
            }
        except (OSError, ValueError, TypeError):
            blocker_by_key = {}

    translated = 0
    invalid = 0
    missed = 0
    provenance_counts: dict[str, int] = {}
    with trace.batch():
        for key, item in actions.items():
            row = current.get(key, {})
            # Keep the exact CSV value in traceability.  Validation still uses
            # the normalised value below, but the durable hash must describe
            # the bytes that Patch will consume.
            translation = str(row.get("translation") or "")
            before = str(initial.get(key) or "").strip()
            provenance = str(item.get("provenance") or "model")
            provenance_counts[provenance] = provenance_counts.get(provenance, 0) + 1
            if provenance == "model":
                entry_model_engine = str(metadata.get("model_engine") or "CTranslate2/OPUS-MT")
                entry_model_revision = str(metadata.get("model_revision") or "default")
            elif provenance == "existing_translation":
                entry_model_engine = "existing_translation"
                entry_model_revision = "frozen"
            else:
                entry_model_engine = "deterministic_policy"
                entry_model_revision = str(metadata.get("classifier_policy_hash") or "policy")
            payload = {
                "key": key,
                "classifier_v2": item.get("classifier_v2"),
                "provenance": provenance,
                "translation_hash": hashlib.sha256(translation.encode("utf-8", "surrogatepass")).hexdigest()
                if translation
                else "",
                "cache_fingerprint": str(cache_fingerprints.get(key) or ""),
                "result_ok": bool(result.get("ok")),
                "pipeline_liveness": bool(result.get("pipeline_liveness")),
                "attempts": retry_attempts_by_key.get(key)
                if isinstance(retry_attempts_by_key.get(key), list)
                else (blocker_by_key.get(key) or {}).get("attempts", []),
                "cache": cache_result or {},
            }
            blocker = blocker_by_key.get(key) or {}
            if blocker:
                initial_blocker = blocker.get("initial") or {}
                payload["blocker"] = {
                    "route": str(blocker.get("route") or blocker.get("final_strategy") or ""),
                    "raw_candidate": str(initial_blocker.get("raw_output") or ""),
                    "candidate": str(blocker.get("candidate") or ""),
                    "reasons": list(blocker.get("final_reasons") or []),
                }
            if translation.strip() and (not before or translation.strip() != before or result.get("ok")):
                trace.finish_event(item["action_id"], "PASS", payload=payload)
                trace.update_entry(
                    item["trace_id"],
                    stage="TRANSLATED",
                    status="PASS",
                    model_engine=entry_model_engine,
                    model_revision=entry_model_revision,
                    glossary_fingerprint=str(metadata.get("glossary_fingerprint") or ""),
                    context_fingerprint=str(metadata.get("context_fingerprint") or ""),
                    memory_fingerprint=str(metadata.get("memory_fingerprint") or ""),
                    cache_fingerprint=str(cache_fingerprints.get(key) or ""),
                    translation=translation,
                    translation_hash=payload["translation_hash"],
                    validation_result="PASS",
                )
                trace.record_event(
                    STAGE_VALIDATED,
                    status="PASS",
                    trace_id=item["trace_id"],
                    payload={"source": "translation_gate", "validated": True},
                )
                translated += 1
            else:
                root = ROOT_CAUSE_TRANSLATION_INVALID if key in blocker_by_key else ROOT_CAUSE_TRANSLATION_MISSED
                failure = "invalid_candidate" if key in blocker_by_key else "no_output"
                if blocker.get("route") == "human_review_required":
                    failure = "human_review_required"
                trace.finish_event(
                    item["action_id"],
                    EVENT_FAILED,
                    root_cause=root,
                    payload={**payload, "failure": failure},
                )
                trace.update_entry(
                    item["trace_id"],
                    stage="TRANSLATED",
                    status=EVENT_FAILED,
                    model_engine=entry_model_engine,
                    model_revision=entry_model_revision,
                    glossary_fingerprint=str(metadata.get("glossary_fingerprint") or ""),
                    context_fingerprint=str(metadata.get("context_fingerprint") or ""),
                    memory_fingerprint=str(metadata.get("memory_fingerprint") or ""),
                    cache_fingerprint=str(cache_fingerprints.get(key) or ""),
                    validation_result="FAIL",
                    root_cause=root,
                )
                trace.record_event(
                    STAGE_VALIDATED,
                    status=EVENT_FAILED,
                    trace_id=item["trace_id"],
                    root_cause=root,
                    payload={"source": "translation_gate", "validated": False},
                )
                item["finished"] = True
                if key in blocker_by_key:
                    invalid += 1
                else:
                    missed += 1
            item["finished"] = True
    return {
        "candidate_count": len(actions),
        "translated": translated,
        "translation_invalid": invalid,
        "translation_missed": missed,
        "pipeline_liveness": bool(result.get("pipeline_liveness")),
        "cache": cache_result or {"kind": "validated_translation_cache", "status": "unknown"},
        "provenance_counts": provenance_counts,
    }


def _run_traced_translation(
    csv_path: Path,
    package_dir: Path,
    operation: Callable[[], dict],
    *,
    overwrite: bool,
    model_dir: str = "",
    model_revision: str = "",
    model_engine: str = "CTranslate2/OPUS-MT",
    only_keys: set[str] | None = None,
    human_review_required: bool = False,
) -> dict:
    from vntext.traceability import EVENT_ABORTED, EVENT_COMPLETED, ROOT_CAUSE_UNKNOWN

    # Preserve the existing EmptyCsvError contract for an empty/invalid CSV:
    # this is a read-only precondition failure and has no candidate/output
    # mutation that needs a package trace.  A non-empty package without a
    # manifest still fails closed before the translation operation starts.
    if not (package_dir / "manifest.json").is_file():
        from vntext.package_io import read_csv_rows_file

        fields, rows = read_csv_rows_file(csv_path)
        if not fields or "key" not in fields or "translation" not in fields or not rows:
            return operation()

    trace = None
    actions: dict[str, dict] = {}
    run_finished = False
    metadata: dict[str, object] = {}
    try:
        trace, manifest = _open_package_trace(
            package_dir,
            "translate",
            overwrite=bool(overwrite),
            selected_keys=len(only_keys) if only_keys is not None else 0,
            human_review_required=bool(human_review_required),
        )
        actions, initial, metadata = _trace_translation_start(
            trace,
            manifest,
            csv_path,
            only_keys=only_keys,
            model_dir=model_dir,
            model_revision=model_revision,
            model_engine=model_engine,
            overwrite=overwrite,
        )
        metadata["human_review_required"] = bool(human_review_required)
        result = operation()
        metrics = _trace_translation_finish(trace, actions, initial, csv_path, result, metadata)
        trace.finish_run(EVENT_COMPLETED)
        run_finished = True
        trace.write_summary(extra={"translation": {**metadata, **metrics}})
        trace.export_jsonl()
        return result
    except Exception as exc:
        if trace is not None:
            _trace_abort_actions(trace, actions, error=str(exc))
            if trace.run_id is not None and not run_finished:
                try:
                    trace.finish_run(EVENT_ABORTED, ROOT_CAUSE_UNKNOWN)
                except Exception:
                    pass
            try:
                trace.write_summary(extra={"translation": {"error": str(exc), "pipeline_liveness": False}})
                trace.export_jsonl()
            except Exception:
                pass
        raise
    finally:
        if trace is not None:
            trace.close()


def _trace_patch_start(
    trace,
    manifest: dict,
    csv_path: Path,
) -> tuple[dict[str, dict], dict[str, object]]:
    """Create per-target PATCHED actions before the patch writer mutates output."""

    from vntext.package_io import read_translation_rows
    from vntext.patch_gate import (
        is_verified_cloud_repair_output,
        load_review_only_keys,
        load_whitelist,
        patch_skip_reason,
    )
    from vntext.patchability import PATCHABLE_METHOD_CONTRACTS
    from vntext.traceability import (
        EVENT_FAILED,
        ROOT_CAUSE_PATCH_FAILED,
        ROOT_CAUSE_TRANSLATION_INVALID,
        ROOT_CAUSE_TRANSLATION_MISSED,
        STAGE_PATCHED,
    )

    translations = read_translation_rows(csv_path)
    review_keys = load_review_only_keys(csv_path.parent)
    whitelist = load_whitelist(csv_path.parent)
    allow_ct2_junk = is_verified_cloud_repair_output(csv_path)
    registered = _trace_manifest_entries(trace, manifest)
    actions: dict[str, dict] = {}
    skipped = 0
    with trace.batch():
        for item in manifest.get("entries", []) or []:
            if not isinstance(item, dict) or not item.get("key"):
                continue
            key = str(item["key"])
            info = registered.get(key)
            if not info:
                continue
            locators = list(info.get("target_ids") or []) or [None]
            trans_row = translations.get(key)
            raw_translation = str((trans_row or {}).get("translation") or "")
            trans = raw_translation.strip()
            if raw_translation:
                trace.update_entry(info["trace_id"], translation=raw_translation)
            skip_reason = ""
            root_cause = None
            if str(item.get("import_method") or "") not in PATCHABLE_METHOD_CONTRACTS:
                skip_reason = f"unsupported patch method: {item.get('import_method') or 'unknown'}"
                root_cause = ROOT_CAUSE_PATCH_FAILED
            elif trans_row is None or not trans:
                skip_reason = "translation missing"
                root_cause = ROOT_CAUSE_TRANSLATION_MISSED
            elif key in review_keys:
                skip_reason = "review_only"
                root_cause = ROOT_CAUSE_TRANSLATION_INVALID
            else:
                skip_reason = patch_skip_reason(
                    item, trans, whitelist, allow_ct2_junk=allow_ct2_junk
                )
                if skip_reason:
                    root_cause = ROOT_CAUSE_PATCH_FAILED
            if skip_reason:
                skipped += len(locators)
                for ordinal, target_id in enumerate(locators):
                    trace.record_event(
                        STAGE_PATCHED,
                        status="SKIPPED",
                        trace_id=info["trace_id"],
                        target_id=target_id,
                        root_cause=root_cause,
                        payload={
                            "key": key,
                            "preflight": "skipped",
                            "reason": skip_reason,
                            "duplicate_ordinal": ordinal,
                        },
                    )
                    trace.update_target(
                        target_id,
                        status="SKIPPED",
                        write_status="SKIPPED",
                        final_verification="NOT_RUN",
                        root_cause=root_cause,
                    )
                trace.update_entry(
                    info["trace_id"],
                    patch_status="SKIPPED",
                    final_verification="NOT_RUN",
                    root_cause=root_cause,
                )
                continue
            for ordinal, target_id in enumerate(locators):
                attempt_id = str(uuid.uuid4())
                action_id = trace.start_event(
                    STAGE_PATCHED,
                    trace_id=info["trace_id"],
                    target_id=target_id,
                    attempt_id=attempt_id,
                    payload={
                        "key": key,
                        "preflight": "eligible",
                        "duplicate_ordinal": ordinal,
                    },
                )
                actions[f"{key}:{ordinal}"] = {
                    "action_id": action_id,
                    "trace_id": info["trace_id"],
                    "target_id": target_id,
                    "key": key,
                    "duplicate_ordinal": ordinal,
                    "finished": False,
                }
    return actions, {
        "eligible_targets": len(actions),
        "preflight_skipped_targets": skipped,
    }


def _trace_patch_finish(
    trace,
    actions: dict[str, dict],
    patch_out: Path,
    *,
    ok: bool,
    error: str = "",
) -> dict[str, object]:
    from vntext.traceability import (
        EVENT_COMPLETED,
        EVENT_FAILED,
        ROOT_CAUSE_PATCH_FAILED,
        ROOT_CAUSE_PATCH_VERIFY_FAILED,
        STAGE_NOT_TESTABLE,
        STAGE_READ_BACK_VERIFIED,
    )

    report_path = patch_out / "import_report.txt"
    report_text = report_path.read_text(encoding="utf-8", errors="replace") if report_path.is_file() else ""
    verification_path = patch_out / "patch_verification.json"
    verification_by_key: dict[str, dict] = {}
    verification_counts: dict[str, int] = {}
    if verification_path.is_file():
        try:
            verification_payload = json.loads(verification_path.read_text(encoding="utf-8"))
            verification_counts = {
                str(key): int(value)
                for key, value in (verification_payload.get("counts") or {}).items()
            }
            verification_by_key = {
                f"{item.get('key')}:{item.get('duplicate_ordinal', 0)}": item
                for item in verification_payload.get("results", [])
                if isinstance(item, dict) and item.get("key")
            }
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            verification_by_key = {}
    verify_miss = "VERIFY_MISS" in report_text or "PATCH_VERIFY_FAILED" in report_text
    metrics = {
        "write_targets": len(actions),
        "write_failed_targets": 0,
        "verification": "NOT_RUN" if not actions else "NOT_TESTABLE",
        "readback_passed_targets": 0,
        "readback_failed_targets": 0,
        "readback_not_testable_targets": 0,
        "output_exists": (patch_out / "COPY_TO_GAME_ROOT").is_dir(),
    }
    with trace.batch():
        for item in actions.values():
            if item.get("finished"):
                continue
            verification = verification_by_key.get(f"{item['key']}:{item.get('duplicate_ordinal', 0)}")
            if verification is None:
                # A missing machine-readable verification report is itself a
                # failed evidence boundary.  The legacy text report cannot
                # promote PATCHED to VERIFIED.
                readback_status = "FAIL"
                writer_status = "FAILED"
                verification_reason = "per-target verification report missing"
            else:
                readback_status = str(verification.get("status") or "NOT_TESTABLE")
                writer_status = str(verification.get("write_status") or readback_status)
                verification_reason = str(verification.get("reason") or "")
            failure = bool(error) or not ok or verify_miss or writer_status != "COMPLETED"
            status = EVENT_FAILED if failure else EVENT_COMPLETED
            root = ROOT_CAUSE_PATCH_VERIFY_FAILED if failure else None
            payload = {
                "write_status": writer_status,
                "final_verification": readback_status,
                "output_exists": bool(metrics["output_exists"]),
                "readback_reason": verification_reason,
            }
            if error:
                payload["error"] = error
            if verify_miss:
                payload["report_marker"] = "VERIFY_MISS"
            trace.finish_event(item["action_id"], status, root_cause=root, payload=payload)
            trace.update_target(
                item["target_id"],
                status=status,
                write_status=writer_status,
                readback_status=readback_status,
                final_verification=readback_status,
                root_cause=root,
            )
            trace.update_entry(
                item["trace_id"],
                patch_status="FAILED" if failure else "COMPLETED",
                final_verification=readback_status,
                readback_status=readback_status,
                root_cause=root,
            )
            if readback_status == "PASS":
                trace.record_event(
                    STAGE_READ_BACK_VERIFIED,
                    status="PASS",
                    trace_id=item["trace_id"],
                    target_id=item["target_id"],
                    payload={"verified": True, "reason": verification_reason},
                )
                metrics["readback_passed_targets"] = int(metrics["readback_passed_targets"]) + 1
            elif readback_status == "NOT_TESTABLE":
                trace.record_event(
                    STAGE_NOT_TESTABLE,
                    status="NOT_TESTABLE",
                    trace_id=item["trace_id"],
                    target_id=item["target_id"],
                    payload={"verified": False, "reason": verification_reason},
                )
                metrics["readback_not_testable_targets"] = int(metrics["readback_not_testable_targets"]) + 1
            else:
                trace.record_event(
                    STAGE_READ_BACK_VERIFIED,
                    status="FAILED",
                    trace_id=item["trace_id"],
                    target_id=item["target_id"],
                    root_cause=ROOT_CAUSE_PATCH_VERIFY_FAILED,
                    payload={"verified": False, "reason": verification_reason},
                )
                metrics["readback_failed_targets"] = int(metrics["readback_failed_targets"]) + 1
            item["finished"] = True
            if failure:
                metrics["write_failed_targets"] = int(metrics["write_failed_targets"]) + 1
        if actions:
            if int(metrics["readback_failed_targets"]):
                metrics["verification"] = "FAIL"
            elif int(metrics["readback_not_testable_targets"]):
                metrics["verification"] = "NOT_TESTABLE"
            else:
                metrics["verification"] = "PASS"
    return metrics


def _find_patch_installer() -> Path | None:
    """Locate the installer built for the current DEV/RELEASE tree."""
    import os

    candidates = []
    configured = (os.environ.get("VNTEXT_PATCH_INSTALLER") or "").strip()
    if configured:
        candidates.append(Path(configured))
    here = Path(__file__).resolve()
    candidates.extend(
        [
            here.parent / "tools" / "VNTextPatchInstaller.exe",
            here.parents[1] / "release" / "patch_installer_publish" / "VNTextPatchInstaller.exe",
        ]
    )
    return next((path for path in candidates if path.is_file()), None)


def _validate_renpy_overlay_output(patch_out: Path) -> Path:
    """Validate the native overlay payload before exposing install guidance."""

    forbidden = [patch_out / "VNTextPatchInstaller.exe", patch_out / "patch_manifest.json"]
    stale = [str(path) for path in forbidden if path.exists()]
    if stale:
        raise RuntimeError(
            "Ren'Py patch output contains Unity-only artifacts; use a clean patch directory: "
            + ", ".join(stale)
        )
    payload = patch_out / "COPY_TO_GAME_ROOT"
    if not payload.is_dir():
        raise RuntimeError("Ren'Py patch output thiếu COPY_TO_GAME_ROOT")
    expected = {
        "game/tl/vietnamese/vntext.rpy",
        "game/zzz_vntext_vietnamese.rpy",
    }
    files = {
        path.relative_to(payload).as_posix()
        for path in payload.rglob("*")
        if path.is_file()
    }
    if files != expected:
        raise RuntimeError(
            "Ren'Py native overlay layout không hợp lệ; expected="
            + ", ".join(sorted(expected))
            + "; actual="
            + ", ".join(sorted(files))
        )
    return payload


def _renpy_patch_install_instructions(patch_out: Path, game_root: Path) -> str:
    payload = patch_out / "COPY_TO_GAME_ROOT"
    return (
        "Ren'Py native overlay đã sẵn sàng.\n"
        "1. Đóng game.\n"
        f"2. Mở thư mục gói: {payload}\n"
        f"3. Copy toàn bộ nội dung bên trong vào game root: {game_root}\n"
        "4. Giữ nguyên cấu trúc game/tl/vietnamese/ và game/."
    )


def _emit_complete(callback: CompleteFn, *, ok: bool, summary: str = "", error: str = "", **extra) -> None:
    callback({"ok": ok, "summary": summary, "error": error, **extra})


def _strict_status_count(value: object, field: str, *, source: str) -> int:
    """Validate a gate count without coercing malformed data to zero."""

    if isinstance(value, bool) or not isinstance(value, int):
        raise TranslateStatusError(
            f"Trạng thái package {source} có {field} không hợp lệ: phải là số nguyên"
        )
    if value < 0:
        raise TranslateStatusError(
            f"Trạng thái package {source} có {field} âm: {value}"
        )
    return value


def _write_unity_analysis_report(report: dict, output_dir: str | Path) -> Path:
    """Persist analyzer evidence without ever writing below the game root."""

    out = Path(output_dir).expanduser().resolve()
    scan_root = Path(str(report.get("scan_root") or "")).expanduser().resolve()
    try:
        out.relative_to(scan_root)
    except ValueError:
        pass
    else:
        raise ValueError("Thư mục xuất analyzer phải nằm ngoài thư mục game đang phân tích")

    out.mkdir(parents=True, exist_ok=True)
    report_path = out / "unity_analysis.json"
    temp_path = report_path.with_name(report_path.name + ".tmp")
    temp_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temp_path.replace(report_path)
    return report_path


def _run_unity_preflight(
    src: str,
    out: str,
    log: LogFn,
    *,
    progress_callback: ProgressFn | None = None,
    is_cancelled: Callable[[], bool] | None = None,
) -> dict:
    """Analyze a selected input before extraction and retain bounded evidence.

    A non-Unity folder still follows the existing generic filesystem extractor.
    When Unity evidence is present, an incomplete inventory stops extraction so
    an inaccessible resource cannot silently disappear from the package.
    """

    from vntext.unity_analyzer import AnalyzerOptions, analyze_unity_game

    report = analyze_unity_game(
        src,
        options=AnalyzerOptions(include_sha256=False),
        progress_callback=progress_callback,
        is_cancelled=is_cancelled,
    )
    unity = report.get("unity") or {}
    unity_resource_seen = any(
        "UNITY_CONTAINER" in (resource.get("categories") or [])
        for resource in report.get("resources", [])
    )
    unity_input = bool(unity.get("detected") or unity_resource_seen)
    summary = report.get("summary") or {}
    if not unity_input:
        try:
            report_path = _write_unity_analysis_report(report, out)
        except ValueError:
            # A legacy caller may place a generic text package below its input
            # root.  Do not write into that input tree; the Unity route above
            # remains fail-closed when it needs a report.
            log("Unity analyzer: NOT_DETECTED; không ghi report vào input, tiếp tục filesystem route.")
        else:
            log(f"Unity analyzer: NOT_DETECTED; report={report_path}; tiếp tục filesystem route hiện tại.")
        return report

    if not report.get("inventory_complete"):
        errors = "; ".join(
            str(item.get("error") or item.get("path") or "unknown scan error")
            for item in report.get("scan_errors", [])[:3]
        )
        raise RuntimeError(
            "Unity preflight chưa hoàn tất; dừng extract để tránh bỏ sót resource"
            + (f": {errors}" if errors else "")
        )

    report_path = _write_unity_analysis_report(report, out)
    log(
        "Unity analyzer: "
        f"{unity.get('status', 'DETECTED')}; "
        f"resources={summary.get('resource_count', 0)}; "
        f"unknown={summary.get('unknown_resources', 0)}; "
        f"candidates={summary.get('text_candidate_resources', 0)}; "
        f"report={report_path}"
    )
    return report


def run_extract_task(
    src: str,
    out: str,
    mode: str,
    level: str,
    separate_review: bool,
    renpy_sdk_path: str = "",
    renpy_sdk_action: str = "auto",
    *,
    progress: ProgressFn,
    log: LogFn,
    complete: CompleteFn,
    is_cancelled: Callable[[], bool] | None = None,
) -> None:
    from vntext.unity_analyzer import UnityAnalysisCancelled

    try:
        preflight = _run_unity_preflight(
            src,
            out,
            log,
            progress_callback=progress,
            is_cancelled=is_cancelled,
        )
        log(f"Đang extract text, mức lọc raw: {level}...")
        from vntext.renpy_adapter import detect_engine
        engine = detect_engine(src)
        renpy_sdk_missing = False
        if engine.engine == "RENPY_LOOSE_SOURCE":
            from vntext.renpy_extract import extract_loose_source, extract_native_template_entries
            from vntext.renpy_toolchain import RenPyToolchainError, generate_empty_vietnamese_template, managed_sdk, validate_sdk
            sdk = None
            selected = str(renpy_sdk_path or os.environ.get("VNTEXT_RENPY_SDK") or "").strip()
            action = str(renpy_sdk_action or "auto").strip().lower()
            try:
                if action == "download":
                    from vntext.renpy_toolchain import download_and_install_managed_sdk
                    Path(out).mkdir(parents=True, exist_ok=True)
                    with tempfile.NamedTemporaryFile(prefix="renpy-sdk-", suffix=".zip", dir=out, delete=False) as temp_file:
                        archive = Path(temp_file.name)
                    try:
                        log("Đang tải và xác minh Ren'Py SDK 8.5.3…")
                        sdk = download_and_install_managed_sdk(archive)
                    finally:
                        archive.unlink(missing_ok=True)
                elif action == "none":
                    sdk = None
                elif action == "existing":
                    if not selected:
                        raise RenPyToolchainError("Hãy chọn thư mục Ren'Py SDK trước khi extract")
                    sdk = validate_sdk(selected)
                else:
                    sdk = validate_sdk(selected) if selected else managed_sdk()
            except RenPyToolchainError as exc:
                if action in {"download", "existing"}:
                    raise
                log(f"Ren'Py SDK managed không hợp lệ; tiếp tục không native patch: {exc}")
            if sdk is None:
                renpy_sdk_missing = True
                log("Thiếu công cụ Ren'Py: đã lấy text một phần; lời thoại cần mã định danh được giữ để xem lại. Kết quả chưa đầy đủ.")
                main, review, stats = extract_loose_source(src)
            else:
                Path(out).mkdir(parents=True, exist_ok=True)
                with tempfile.TemporaryDirectory(prefix="vntext-renpy-", dir=out) as temp:
                    workspace = Path(temp) / "gamecopy"
                    shutil.copytree(src, workspace)
                    generate_empty_vietnamese_template(sdk, workspace)
                    main, review, stats = extract_native_template_entries(
                        src,
                        workspace / "game" / "tl" / "vietnamese",
                        language="vietnamese",
                    )
                log(f"Ren'Py SDK {sdk.version} đã tạo native template identity trên workspace tạm.")
        else:
            file_inventory = None
            input_root = Path(src)
            scan_root = preflight.get("scan_root")
            if (
                input_root.is_dir()
                and preflight.get("inventory_complete")
                and scan_root
                and Path(scan_root).resolve() == input_root.resolve()
            ):
                file_inventory = [
                    input_root / resource["path"]
                    for resource in preflight.get("resources", [])
                ]
            if file_inventory is None:
                main, review, stats = extract_project(src, mode, progress, level)
            else:
                main, review, stats = extract_project(
                    src,
                    mode,
                    progress,
                    level,
                    file_inventory=file_inventory,
                )
        # New app extraction must never promote an unproven row into the main
        # translation flow.  Legacy direct write_package callers retain their
        # compatibility default; the GUI worker uses the strict boundary.
        write_package(
            out,
            main,
            review,
            stats,
            separate_review,
            enforce_symmetry=True,
            enable_trace=True,
        )
        extract_errors = [str(item) for item in (stats.get("errors") or []) if str(item)]
        if separate_review:
            summary = f"Xong: {len(main)} dòng translation.csv, {len(review)} review_only. Xuất tại: {out}"
        else:
            summary = f"Xong: {len(main) + len(review)} dòng translation.csv. Xuất tại: {out}"
        if extract_errors:
            summary = (
                f"Extract chưa hoàn tất: đã tạo partial package tại {out}; "
                f"{len(extract_errors)} lỗi discovery/extract."
            )
        elif renpy_sdk_missing:
            summary = (
                f"Lấy text chưa đầy đủ do thiếu công cụ Ren'Py; "
                f"{len(review)} lời thoại cần xem lại. Kết quả tại: {out}"
            )
        log(summary)
        log("Gói dịch nằm trong thư mục trên; app không tạo ZIP package nữa.")
        completion_blockers = bool(extract_errors or review or renpy_sdk_missing)
        completion_error = ""
        if extract_errors:
            completion_error = (
                "Extract chưa hoàn tất do lỗi discovery/extract: "
                + " | ".join(extract_errors[:3])
            )
        elif renpy_sdk_missing:
            completion_error = (
                "Lấy text chưa đầy đủ do chưa có công cụ Ren'Py. "
                f"{len(review)} lời thoại cần xem lại; tải công cụ rồi lấy text lại để nhận dạng đầy đủ."
            )
        elif review:
            completion_error = (
                "Extract chưa hoàn tất vì còn "
                f"{len(review)} dòng REVIEW/UNSUPPORTED cần xử lý trước khi dịch."
            )
        payload = {
            "ok": not completion_blockers,
            "summary": summary,
            "error": completion_error,
            "complete": not completion_blockers,
            "pending": 0,
            "review_only": len(review),
            "blocked": 0,
        }
        if extract_errors or review:
            payload.update(
                _diagnostic_completion_fields(
                    Path(out),
                    fallback_stage="EXTRACT",
                    fallback_root_cause="DISCOVERY_GAP" if extract_errors else None,
                    fallback_affected_count=len(extract_errors) or len(review) or int(renpy_sdk_missing),
                    fallback_action=(
                        "Review discovery/extract errors before translating the package."
                        if extract_errors
                        else "Tải công cụ Ren'Py rồi lấy text lại để nhận dạng lời thoại đầy đủ."
                        if renpy_sdk_missing
                        else "Review REVIEW rows before treating Extract as ready for translation."
                    ),
                )
            )
        if engine.engine == "RENPY_LOOSE_SOURCE":
            payload["renpy_sdk_missing"] = renpy_sdk_missing
        complete(payload)
    except UnityAnalysisCancelled:
        _emit_complete(
            complete,
            ok=False,
            error="cancelled",
            complete=False,
            pending=1,
            review_only=0,
            blocked=0,
        )
    except Exception as exc:
        if is_cancelled is not None and is_cancelled():
            _emit_complete(
                complete,
                ok=False,
                error="cancelled",
                complete=False,
                pending=1,
                review_only=0,
                blocked=0,
            )
            return
        _emit_complete(
            complete,
            ok=False,
            error=str(exc),
            complete=False,
            pending=1,
            review_only=1,
            blocked=1,
            **_diagnostic_completion_fields(
                Path(out),
                fallback_stage="EXTRACT",
                fallback_root_cause="UNKNOWN",
                fallback_affected_count=1,
                fallback_action="Inspect the extract error and diagnostic evidence before retrying.",
            ),
        )


def run_dump_task(
    src: str,
    out: str,
    level: str,
    *,
    progress: ProgressFn,
    log: LogFn,
    complete: CompleteFn,
) -> None:
    try:
        log("Đang tự động dump/soi Unity trong app, không cần UABEA...")
        result = export_unity_internal_dump(src, out, level, progress)
        summary = (
            "Xong auto dump: "
            f"{result['asset_index_rows']} object index, "
            f"{result['debug_string_rows']} string debug, "
            f"{result['textasset_dump_files']} TextAsset dump. "
            f"Xem: {result['dump_dir']}"
        )
        log(summary)
        _emit_complete(complete, ok=True, summary=summary)
    except Exception as exc:
        _emit_complete(complete, ok=False, error=str(exc))


def run_auto_raw_task(
    package_dir: Path,
    *,
    progress: ProgressFn,
    log: LogFn,
    complete: CompleteFn,
) -> None:
    try:
        log("Đang auto lọc raw_candidates.csv...")
        result = auto_process_raw_candidates(package_dir, progress)
        summary = (
            f"Xong auto raw: promoted {result['promoted']}, "
            f"giữ lại {result['kept']}, reject {result['rejected']}, "
            f"translation.csv {result['translation_rows']} dòng."
        )
        log(summary)
        _emit_complete(complete, ok=True, summary=summary)
    except Exception as exc:
        _emit_complete(complete, ok=False, error=str(exc))


def run_asset_index_task(
    src: str,
    out: str,
    *,
    progress: ProgressFn,
    log: LogFn,
    complete: CompleteFn,
) -> None:
    try:
        log("Đang lập asset_index.csv để xem bundle/assets...")
        rows, errors = build_asset_index(src, out, progress)
        summary = f"Xong asset browser: {len(rows)} object. Xuất tại: {out}\\asset_index.csv"
        log(summary)
        if errors:
            log(f"Có {len(errors)} file UnityPy không đọc được, xem extract_report/import_report nếu cần.")
        _emit_complete(complete, ok=True, summary=summary)
    except Exception as exc:
        _emit_complete(complete, ok=False, error=str(exc))


def run_translate_ct2_task(
    csv_path: Path,
    package_dir: Path,
    overwrite: bool,
    *,
    model_dir: str = "",
    human_review_required: bool = False,
    progress: ProgressFn,
    log: LogFn,
    complete: CompleteFn,
    is_cancelled: Callable[[], bool] | None = None,
) -> None:
    try:
        log("Đang dịch offline CTranslate2 + OPUS-MT en→vi (INT8). Lần đầu có thể tải model.")
        trace_model_revision = _ct2_trace_model_revision(model_dir)
        translate_kwargs = {
            "allow_overwrite": overwrite,
            "human_review_required": bool(human_review_required),
            "is_cancelled": is_cancelled,
            "progress": progress,
            "log": log,
        }
        result = _run_traced_translation(
            csv_path,
            package_dir,
            lambda: run_ct2_translate(csv_path, model_dir=model_dir or None, **translate_kwargs),
            overwrite=overwrite,
            model_dir=trace_model_revision,
            model_revision=trace_model_revision,
            model_engine="CTranslate2/OPUS-MT",
            human_review_required=human_review_required,
        )
        summary = result.get("summary") or (
            f"Xong dịch: {result.get('translated', '?')}/{result.get('total', '?')} dòng có translation."
        )
        log(summary)
        log(f"State lưu tại: {package_dir / '.mt'}")
        payload = {
            "ok": bool(result.get("ok")),
            "summary": summary,
            "error": "",
            "complete": bool(result.get("complete")),
            "pending": int(result.get("pending") or 0),
            "review_only": int(result.get("review_only") or 0),
            "blocked": int(result.get("blocked") or 0),
            "translated": int(result.get("translated") or 0),
            "applied": int(result.get("applied") or 0),
            "copied_vi": int(result.get("copied_vi") or 0),
            "pipeline_liveness": bool(result.get("pipeline_liveness")),
            "human_review_required_count": int(result.get("human_review_required_count") or 0),
        }
        human_review_count = payload["human_review_required_count"]
        if human_review_count:
            payload["error"] = f"Cần duyệt thủ công {human_review_count} dòng trước khi Patch"
        if not result.get("ok"):
            payload["ok"] = False
            payload["error"] = payload["error"] or result.get("error") or "Dịch không hoàn tất hoặc không có tiến độ"
        if (
            not payload["ok"]
            or not payload["complete"]
            or payload["pending"]
            or payload["review_only"]
            or payload["blocked"]
        ):
            payload.update(
                _diagnostic_completion_fields(
                    package_dir,
                    fallback_stage="TRANSLATE",
                    fallback_root_cause="TRANSLATION_MISSED",
                    fallback_affected_count=max(
                        payload["pending"], payload["review_only"], payload["blocked"], 1
                    ),
                    fallback_action="Review translation blockers and rerun the translation gate.",
                )
            )
        if human_review_count:
            payload.update(
                {
                    "diagnostic_stage": "TRANSLATE",
                    "diagnostic_root_cause": "HUMAN_REVIEW_REQUIRED",
                    "diagnostic_affected_count": human_review_count,
                    "diagnostic_action": "Duyệt bản dịch trong review_only.csv rồi lưu translation.csv trước khi Patch.",
                    "diagnostic_status": "REVIEW_REQUIRED",
                }
            )
        write_translate_status(
            package_dir,
            csv_path,
            package_wide_verified=bool(
                result.get("ok")
                and result.get("complete") is True
                and all(result.get(name) == 0 for name in ("pending", "review_only", "blocked"))
            ),
            complete=bool(result.get("complete")),
            pending=int(result.get("pending") or 0),
            review_only=int(result.get("review_only") or 0),
            blocked=int(result.get("blocked") or 0),
            translated=int(result.get("translated") or 0),
            applied=int(result.get("applied") or 0),
            copied_vi=int(result.get("copied_vi") or 0),
            pipeline_liveness=bool(result.get("pipeline_liveness")),
            model_metadata=result.get("model_metadata"),
            human_review_required_count=human_review_count,
        )
        complete(payload)
    except TranslateCancelled:
        _emit_complete(
            complete,
            ok=False,
            error="cancelled",
            complete=False,
            pending=1,
            review_only=1,
            blocked=1,
            **_diagnostic_completion_fields(
                package_dir,
                fallback_stage="TRANSLATE",
                fallback_root_cause="UNKNOWN",
                fallback_affected_count=1,
                fallback_action="Translation was cancelled; inspect the package state before retrying.",
            ),
        )
    except TranslateStatusError as exc:
        payload = {
            "ok": False,
            "summary": "",
            "error": str(exc),
            "complete": False,
            "pending": 1,
            "review_only": 1,
            "blocked": 1,
        }
        payload.update(
            _diagnostic_completion_fields(
                package_dir,
                fallback_stage="TRANSLATE",
                fallback_root_cause="UNKNOWN",
                fallback_affected_count=1,
                fallback_action="Inspect the invalid persisted translation status before retrying.",
            )
        )
        complete(payload)
    except EmptyCsvError as exc:
        _emit_complete(
            complete,
            ok=False,
            error=str(exc),
            complete=False,
            pending=1,
            review_only=1,
            blocked=1,
            **_diagnostic_completion_fields(
                package_dir,
                fallback_stage="TRANSLATE",
                fallback_root_cause="UNKNOWN",
                fallback_affected_count=1,
                fallback_action="Provide a valid translation package before retrying.",
            ),
        )
    except ModelNotReadyError as exc:
        _emit_complete(
            complete,
            ok=False,
            error=f"Model CTranslate2 chưa sẵn sàng: {exc}",
            complete=False,
            pending=1,
            review_only=1,
            blocked=1,
            **_diagnostic_completion_fields(
                package_dir,
                fallback_stage="TRANSLATE",
                fallback_root_cause="UNKNOWN",
                fallback_affected_count=1,
                fallback_action="Check the local translation model before retrying.",
            ),
        )
    except Exception as exc:
        _emit_complete(
            complete,
            ok=False,
            error=str(exc),
            complete=False,
            pending=1,
            review_only=1,
            blocked=1,
            **_diagnostic_completion_fields(
                package_dir,
                fallback_stage="TRANSLATE",
                fallback_root_cause="UNKNOWN",
                fallback_affected_count=1,
                fallback_action="Inspect the translation diagnostic evidence before retrying.",
            ),
        )


def run_translate_keys_ct2_task(
    csv_path: Path,
    package_dir: Path,
    keys: list[str],
    *,
    model_dir: str = "",
    human_review_required: bool = False,
    progress: ProgressFn,
    log: LogFn,
    complete: CompleteFn,
    is_cancelled: Callable[[], bool] | None = None,
) -> None:
    try:
        log(f"Đang dịch lại {len(keys)} dòng lỗi bằng CTranslate2 + OPUS-MT en→vi (INT8).")
        trace_model_revision = _ct2_trace_model_revision(model_dir)
        translate_kwargs = {
            "allow_overwrite": True,
            "backup": True,
            "human_review_required": bool(human_review_required),
            "is_cancelled": is_cancelled,
            "progress": progress,
            "log": log,
        }
        result = _run_traced_translation(
            csv_path,
            package_dir,
            lambda: run_ct2_translate_keys(csv_path, keys, model_dir=model_dir or None, **translate_kwargs),
            overwrite=True,
            model_dir=trace_model_revision,
            model_revision=trace_model_revision,
            model_engine="CTranslate2/OPUS-MT",
            only_keys=set(keys),
            human_review_required=human_review_required,
        )
        summary = result.get("summary") or f"Dịch lại {result.get('applied', 0)} dòng."
        log(summary)
        validation = None
        try:
            from vntext.csv_editor_api import validate_document
            from vntext.mt_ct2_status import snapshot_translate_status

            validation = validate_document(csv_path)
            if validation.get("summary"):
                log(f"Kiểm tra lại CSV: {validation['summary']}")
        except Exception as exc:
            log(f"Không kiểm tra lại CSV được: {exc}")

        # Retranslate is a scoped operation, but completion is a package-level
        # contract.  Read the current CSV/review ledgers so a retry-by-key
        # cannot report success while unrelated player-visible rows remain.
        # A transient read failure gets one bounded retry.  If both reads fail,
        # do not manufacture zero counts: emit an explicit incomplete result
        # and leave the persisted ledger untouched.
        measured_status = None
        status_read_error = ""
        try:
            measured_status = snapshot_translate_status(package_dir, csv_path)
        except Exception as first_exc:
            try:
                measured_status = snapshot_translate_status(package_dir, csv_path)
                log(f"Đọc trạng thái package lần đầu thất bại, lần hai thành công: {first_exc}")
            except Exception as second_exc:
                status_read_error = (
                    "Không đo được trạng thái package sau khi dịch lại; "
                    f"lần 1: {first_exc}; lần 2: {second_exc}"
                )
                log(status_read_error)

        if measured_status is None:
            # Counts are deliberately conservative sentinels rather than
            # optimistic zeroes.  The CSV/review state is unmeasurable, so a
            # worker/UI consumer must see an unresolved, non-complete result.
            validation_data = validation if isinstance(validation, dict) else {}
            reason_counts = validation_data.get("reason_counts") or {}
            if not isinstance(reason_counts, dict):
                raise TranslateStatusError(
                    "Trạng thái package validation có reason_counts không hợp lệ"
                )
            known_review = _strict_status_count(
                reason_counts.get("review_only", 0),
                "review_only",
                source="validation",
            )
            known_blocked = max(
                _strict_status_count(
                    result["blocked"] if "blocked" in result else 0,
                    "blocked",
                    source="translation result",
                ),
                _strict_status_count(
                    validation_data.get("patch_blocked", 0),
                    "blocked",
                    source="validation",
                ),
            )
            fail_payload = {
                "ok": False,
                "summary": summary,
                "error": status_read_error or "Không đo được trạng thái package sau khi dịch lại",
                "complete": False,
                "pending": 1,
                "review_only": max(known_review, 1),
                "blocked": max(known_blocked, 1),
                "translated": int((validation or {}).get("patch_eligible") or 0),
                "patch_eligible": int((validation or {}).get("patch_eligible") or 0),
                "patch_blocked": int((validation or {}).get("patch_blocked") or 0),
                "pipeline_liveness": bool(result.get("pipeline_liveness")),
            }
            complete(fail_payload)
            return

        measured_pending = _strict_status_count(
            measured_status["pending"], "pending", source="measured status"
        )
        measured_blocked = _strict_status_count(
            measured_status["blocked"], "blocked", source="measured status"
        )
        validation_data = validation if isinstance(validation, dict) else {}
        reason_counts = validation_data.get("reason_counts") or {}
        if not isinstance(reason_counts, dict):
            raise TranslateStatusError(
                "Trạng thái package validation có reason_counts không hợp lệ"
            )
        measured_review = max(
            _strict_status_count(
                measured_status["review_only"], "review_only", source="measured status"
            ),
            _strict_status_count(
                reason_counts.get("review_only", 0),
                "review_only",
                source="validation",
            ),
        )
        operation_blocked = max(
            _strict_status_count(
                result["blocked"] if "blocked" in result else 0,
                "blocked",
                source="translation result",
            ),
            _strict_status_count(
                validation_data.get("patch_blocked", 0),
                "blocked",
                source="validation",
            ),
        )
        # Keep prior operation-level failures until a fresh, package-wide
        # validation explicitly proves that every pending/review row is gone.
        # A key-scoped retry's ``result.blocked=0`` alone is not proof.
        package_wide_verified = bool(
            result.get("ok")
            and validation is not None
            and validation.get("ok") is True
            and measured_pending == 0
            and measured_review == 0
            and operation_blocked == 0
        )
        package_blocked = (
            operation_blocked
            if package_wide_verified
            else max(measured_blocked, operation_blocked)
        )

        payload = {
            "ok": bool(result.get("ok")),
            "summary": summary,
            "error": "",
            "complete": False,
            "pending": measured_pending,
            "review_only": measured_review,
            "blocked": package_blocked,
            "translated": int((validation or {}).get("patch_eligible") or 0),
            "patch_eligible": int((validation or {}).get("patch_eligible") or 0),
            "patch_blocked": int((validation or {}).get("patch_blocked") or 0),
            "pipeline_liveness": bool(result.get("pipeline_liveness")),
            "human_review_required_count": int(result.get("human_review_required_count") or 0),
        }
        human_review_count = payload["human_review_required_count"]
        if not result.get("ok"):
            payload["ok"] = False
            payload["error"] = result.get("error") or "Dịch lại không thành công"
        elif validation is None:
            payload["ok"] = False
            payload["error"] = "Không xác minh được CSV sau khi dịch lại"
        else:
            payload["complete"] = (
                payload["pending"] == 0
                and payload["review_only"] == 0
                and payload["blocked"] == 0
            )
            if not payload["complete"]:
                payload["ok"] = False
                payload["error"] = (
                    "Dịch lại xong nhưng vẫn còn dòng cần xem lại: "
                    f"pending={payload['pending']}, review_only={payload['review_only']}, "
                    f"blocked={payload['blocked']}"
                )
                if human_review_count:
                    payload["error"] = f"Cần duyệt thủ công {human_review_count} dòng trước khi Patch"
        if (
            not payload["ok"]
            or not payload["complete"]
            or payload["pending"]
            or payload["review_only"]
            or payload["blocked"]
        ):
            payload.update(
                _diagnostic_completion_fields(
                    package_dir,
                    fallback_stage="TRANSLATE",
                    fallback_root_cause="TRANSLATION_MISSED",
                    fallback_affected_count=max(
                        payload["pending"], payload["review_only"], payload["blocked"], 1
                    ),
                    fallback_action="Review retranslation blockers and rerun package validation.",
                )
            )
        if human_review_count:
            payload.update(
                {
                    "diagnostic_stage": "TRANSLATE",
                    "diagnostic_root_cause": "HUMAN_REVIEW_REQUIRED",
                    "diagnostic_affected_count": human_review_count,
                    "diagnostic_action": "Duyệt bản dịch trong review_only.csv rồi lưu translation.csv trước khi Patch.",
                    "diagnostic_status": "REVIEW_REQUIRED",
                }
            )
        write_translate_status(
            package_dir,
            csv_path,
            measured_status=measured_status,
            package_wide_verified=package_wide_verified,
            complete=payload["complete"],
            pending=payload["pending"],
            review_only=payload["review_only"],
            blocked=payload["blocked"],
            translated=payload["translated"],
            human_review_required_count=human_review_count,
        )
        complete(payload)
    except TranslateCancelled:
        _emit_complete(
            complete,
            ok=False,
            error="cancelled",
            complete=False,
            pending=1,
            review_only=1,
            blocked=1,
            **_diagnostic_completion_fields(
                package_dir,
                fallback_stage="TRANSLATE",
                fallback_root_cause="UNKNOWN",
                fallback_affected_count=1,
                fallback_action="Retranslation was cancelled; inspect the package state before retrying.",
            ),
        )
    except TranslateStatusError as exc:
        payload = {
            "ok": False,
            "summary": "",
            "error": str(exc),
            "complete": False,
            "pending": 1,
            "review_only": 1,
            "blocked": 1,
        }
        payload.update(
            _diagnostic_completion_fields(
                package_dir,
                fallback_stage="TRANSLATE",
                fallback_root_cause="UNKNOWN",
                fallback_affected_count=1,
                fallback_action="Inspect the invalid persisted translation status before retrying.",
            )
        )
        complete(payload)
    except EmptyCsvError as exc:
        _emit_complete(
            complete,
            ok=False,
            error=str(exc),
            complete=False,
            pending=1,
            review_only=1,
            blocked=1,
            **_diagnostic_completion_fields(
                package_dir,
                fallback_stage="TRANSLATE",
                fallback_root_cause="UNKNOWN",
                fallback_affected_count=1,
                fallback_action="Provide a valid translation package before retrying.",
            ),
        )
    except ModelNotReadyError as exc:
        _emit_complete(
            complete,
            ok=False,
            error=f"Model CTranslate2 chưa sẵn sàng: {exc}",
            complete=False,
            pending=1,
            review_only=1,
            blocked=1,
            **_diagnostic_completion_fields(
                package_dir,
                fallback_stage="TRANSLATE",
                fallback_root_cause="UNKNOWN",
                fallback_affected_count=1,
                fallback_action="Check the local translation model before retrying.",
            ),
        )
    except Exception as exc:
        _emit_complete(
            complete,
            ok=False,
            error=str(exc),
            complete=False,
            pending=1,
            review_only=1,
            blocked=1,
            **_diagnostic_completion_fields(
                package_dir,
                fallback_stage="TRANSLATE",
                fallback_root_cause="UNKNOWN",
                fallback_affected_count=1,
                fallback_action="Inspect the translation diagnostic evidence before retrying.",
            ),
        )


def _write_cloud_repair_report(anchor: Path, operation: str, report: dict) -> Path | None:
    """Keep the structured cloud result beside the package without changing CSV state."""

    try:
        package_dir = anchor if anchor.is_dir() else anchor.parent
        report_dir = package_dir / ".mt"
        report_dir.mkdir(parents=True, exist_ok=True)
        report_path = report_dir / f"cloud_repair_{operation}_report.json"
        temp_path = report_path.with_name(report_path.name + ".tmp")
        temp_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        temp_path.replace(report_path)
        return report_path
    except OSError:
        return None


def _write_external_translation_import_report(anchor: Path, report: dict) -> Path | None:
    try:
        package_dir = anchor if anchor.is_dir() else anchor.parent
        report_dir = package_dir / ".mt"
        report_dir.mkdir(parents=True, exist_ok=True)
        report_path = report_dir / "external_translation_import_report.json"
        temp_path = report_path.with_name(report_path.name + ".tmp")
        temp_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        temp_path.replace(report_path)
        return report_path
    except OSError:
        return None


def _cloud_repair_error(report: dict, operation: str) -> str:
    errors = report.get("errors") if isinstance(report, dict) else None
    detail = str(errors[0]).strip() if isinstance(errors, list) and errors else "unknown validation error"
    lowered = detail.lower()
    if operation == "import":
        if "structural" in lowered or any(
            token in lowered for token in ("placeholder", "tag", "newline", "code")
        ):
            prefix = "Kết quả Cloud Repair bị từ chối vì lỗi cấu trúc placeholder/tag/code/newline"
        elif any(
            token in lowered
            for token in ("source", "identity", "immutable", "row order", "row count", "reference")
        ):
            prefix = "Kết quả Cloud Repair không khớp gói tham chiếu (key/thứ tự/source/field bất biến)"
        elif any(token in lowered for token in ("csv", "header", "field", "utf-8", "empty")):
            prefix = "translation.csv Cloud Repair không hợp lệ"
        else:
            prefix = "Không nhập được kết quả Cloud Repair"
    else:
        prefix = "Không tạo được gói Cloud Repair"
    return f"{prefix}: {detail}"


def run_cloud_repair_export_task(
    package_dir: Path,
    output_zip: Path,
    *,
    log: LogFn,
    complete: CompleteFn,
) -> None:
    """Export one validated package without contacting a cloud provider."""

    report: dict = {"operation": "export", "status": "FAIL", "output_zip": str(output_zip)}
    try:
        from vntext.cloud_repair_package import export_cloud_repair_package

        report = export_cloud_repair_package(package_dir, output_zip)
        report["operation"] = "export"
        report_path = _write_cloud_repair_report(package_dir, "export", report)
        report_note = f" Báo cáo: {report_path}." if report_path else ""
        summary = (
            f"Đã tạo gói Cloud Repair: {report.get('output_zip', output_zip)} "
            f"({int(report.get('row_count') or 0)} dòng). Người dùng tự tải lên dịch vụ bên ngoài."
            f"{report_note}"
        )
        log(summary)
        _emit_complete(
            complete,
            ok=True,
            summary=summary,
            complete=True,
            pending=0,
            review_only=0,
            blocked=0,
        )
    except Exception as exc:  # noqa: BLE001 - task boundary is report-based and fail-closed.
        report["errors"] = [str(exc) or type(exc).__name__]
        report_path = _write_cloud_repair_report(package_dir, "export", report)
        error = _cloud_repair_error(report, "export")
        if report_path:
            error += f" Xem báo cáo: {report_path}."
        log(error)
        _emit_complete(
            complete,
            ok=False,
            error=error,
            complete=False,
            pending=1,
            review_only=0,
            blocked=1,
        )


def run_cloud_repair_import_task(
    package_zip: Path,
    result_csv: Path,
    output_csv: Path,
    *,
    log: LogFn,
    complete: CompleteFn,
) -> None:
    """Validate and atomically merge one returned CSV into a separate output."""

    report: dict = {
        "operation": "import",
        "status": "FAIL",
        "reference_package": {"path": str(package_zip)},
        "result_input": {"path": str(result_csv)},
        "output_path": str(output_csv),
    }
    try:
        from vntext.cloud_repair_import import import_cloud_repair_result

        report = import_cloud_repair_result(package_zip, result_csv, output_csv)
        report["operation"] = "import"
        report_path = _write_cloud_repair_report(output_csv, "import", report)
        ok = report.get("status") == "PASS" and bool(report.get("merge_applied")) and output_csv.is_file()
        if ok:
            report_note = f" Báo cáo: {report_path}." if report_path else ""
            summary = (
                f"Đã nhập Cloud Repair: {report.get('changed_count', 0)} dòng thay đổi, "
                f"{report.get('expected_row_count', 0)} dòng đã kiểm tra. "
                f"CSV mới: {output_csv}.{report_note}"
            )
            log(summary)
            _emit_complete(
                complete,
                ok=True,
                summary=summary,
                complete=True,
                pending=0,
                review_only=0,
                blocked=0,
            )
            return

        error = _cloud_repair_error(report, "import")
        if report_path:
            error += f" Xem báo cáo: {report_path}."
        log(error)
        _emit_complete(
            complete,
            ok=False,
            error=error,
            complete=False,
            pending=1,
            review_only=0,
            blocked=1,
        )
    except Exception as exc:  # noqa: BLE001 - task boundary is report-based and fail-closed.
        report["errors"] = [str(exc) or type(exc).__name__]
        report_path = _write_cloud_repair_report(output_csv, "import", report)
        error = _cloud_repair_error(report, "import")
        if report_path:
            error += f" Xem báo cáo: {report_path}."
        log(error)
        _emit_complete(
            complete,
            ok=False,
            error=error,
            complete=False,
            pending=1,
            review_only=0,
            blocked=1,
        )


def run_external_translation_import_task(
    target_csv: Path,
    source_csv: Path,
    *,
    log: LogFn,
    complete: CompleteFn,
) -> None:
    """Safely fill current blank rows from an older translation.csv."""

    report: dict = {
        "operation": "external_translation_import",
        "status": "FAIL",
        "target_csv": str(target_csv),
        "source_csv": str(source_csv),
        "errors": [],
    }
    try:
        from vntext.external_translation_import import import_existing_translations

        report = import_existing_translations(target_csv, source_csv)
        report_path = _write_external_translation_import_report(target_csv, report)
        if report.get("status") == "PASS":
            applied = int(report.get("applied") or 0)
            review_only = int(report.get("review_only_remaining") or 0)
            unresolved = int(report.get("untranslated_remaining") or 0)
            task_complete = bool(report.get("complete"))
            pending = 0 if task_complete else unresolved
            report_note = f" Báo cáo: {report_path}." if report_path else ""
            summary = (
                f"Đã nhập {applied} dòng khớp an toàn từ bản dịch cũ. "
                + (
                    "Gói hiện tại đã sẵn sàng kiểm tra patch."
                    if task_complete
                    else f"Còn {unresolved} dòng cần xem trong Sửa CSV."
                )
                + report_note
            )
            log(summary)
            _emit_complete(
                complete,
                ok=True,
                summary=summary,
                complete=task_complete,
                pending=pending,
                review_only=review_only,
                blocked=0,
                applied=applied,
                translated=int(report.get("translated") or 0),
            )
            return

        errors = report.get("errors") or []
        detail = str(errors[0]).strip() if errors else "unknown validation error"
        error = f"Không thể nhập bản dịch cũ: {detail}"
        if report_path:
            error += f" Xem báo cáo: {report_path}."
        log(error)
        _emit_complete(
            complete,
            ok=False,
            error=error,
            complete=False,
            pending=0,
            review_only=0,
            blocked=1,
        )
    except Exception as exc:  # noqa: BLE001 - worker boundary must report a usable error.
        report["errors"] = [str(exc) or type(exc).__name__]
        report_path = _write_external_translation_import_report(target_csv, report)
        error = f"Không thể nhập bản dịch cũ: {report['errors'][0]}"
        if report_path:
            error += f" Xem báo cáo: {report_path}."
        log(error)
        _emit_complete(
            complete,
            ok=False,
            error=error,
            complete=False,
            pending=0,
            review_only=0,
            blocked=1,
        )


def run_patch_task(
    csv_path: Path,
    manifest_path: Path,
    src: str,
    out: str,
    *,
    progress: ProgressFn,
    log: LogFn,
    complete: CompleteFn,
    patch_out_override: str | Path | None = None,
    include_installer: bool = True,
    write_manifest_file: bool = True,
    enable_trace: bool = False,
) -> None:
    trace = None
    patch_out: Path | None = None
    patch_engine = ""
    patch_delivery = ""
    patch_payload_path = ""
    patch_install_instructions = ""
    patch_actions: dict[str, dict] = {}
    patch_trace_metadata: dict[str, object] = {}
    trace_run_finished = False
    manifest_for_trace: dict = {}
    try:
        game_root = Path(src)
        if enable_trace:
            trace, manifest_for_trace = _open_package_trace(
                Path(csv_path).parent,
                "patch",
                game_root=str(game_root),
            )
        if trace is not None:
            patch_actions, patch_trace_metadata = _trace_patch_start(
                trace,
                manifest_for_trace,
                Path(csv_path),
            )
        manifest_for_delivery = manifest_for_trace
        if not manifest_for_delivery:
            manifest_for_delivery = json.loads(Path(manifest_path).read_text(encoding="utf-8-sig"))
        patch_engine = detect_patch_engine(manifest_for_delivery)
        patch_out = (
            Path(patch_out_override)
            if patch_out_override is not None
            else Path(out) / "Patch_Viet_Hoa" / f"VNTextPatch_v{VERSION}"
        )
        patch_out.mkdir(parents=True, exist_ok=True)
        if patch_engine == "renpy":
            stale_unity_artifacts = [
                patch_out / "VNTextPatchInstaller.exe",
                patch_out / "patch_manifest.json",
            ]
            if any(path.exists() for path in stale_unity_artifacts):
                raise RuntimeError(
                    "Ren'Py patch output contains Unity-only artifacts; use a clean patch directory"
                )
        log(f"Đang tạo patch Việt hóa theo version: {patch_out}")
        if patch_engine == "unity":
            log("File data.unity3d lớn có thể mất 5–10 phút, xem thanh tiến trình.")
        else:
            log("Ren'Py: đang tạo native overlay.")
        apply_translation_package(str(csv_path), str(manifest_path), src, str(patch_out), progress)
        # Do not let COPY_TO_GAME_ROOT existence or a legacy text report
        # promote a patch.  The writer must have completed the bounded,
        # per-target read-back report before any optional overlay is accepted.
        patch_verification = _require_patch_readback_success(patch_out)
        log(
            "Patch read-back PASS — "
            f"targets={len(patch_verification.get('results') or [])}"
        )
        if patch_engine == "unity":
            if include_installer:
                installer = _find_patch_installer()
                if installer is not None:
                    target_installer = patch_out / "VNTextPatchInstaller.exe"
                    target_installer.parent.mkdir(parents=True, exist_ok=True)
                    import shutil

                    shutil.copy2(installer, target_installer)
                    log(f"Đã thêm installer: {target_installer}")
                else:
                    log("Cảnh báo: chưa tìm thấy VNTextPatchInstaller.exe; cần publish installer trước khi phát hành patch.")
            if write_manifest_file and (patch_out / "COPY_TO_GAME_ROOT").is_dir():
                write_patch_manifest(patch_out, Path(src).resolve(), VERSION)
            elif write_manifest_file:
                log("Cảnh báo: chưa tạo được patch_manifest.json vì patch output không có COPY_TO_GAME_ROOT.")
            patch_delivery = "unity_installer"
            patch_payload_path = str(patch_out / "COPY_TO_GAME_ROOT")
            patch_install_instructions = (
                f"Patch Unity/Naninovel đã sẵn sàng tại {patch_out}. "
                "Mở VNTextPatchInstaller.exe để cài/gỡ."
            )
            summary = f"Xong: patch nằm tại {patch_out}. Mở VNTextPatchInstaller.exe để cài/gỡ."
        else:
            payload = _validate_renpy_overlay_output(patch_out)
            patch_delivery = "renpy_native_overlay"
            patch_payload_path = str(payload)
            patch_install_instructions = _renpy_patch_install_instructions(
                patch_out,
                Path(src).resolve(),
            )
            (patch_out / "HUONG_DAN_CAI_PATCH.txt").write_text(
                patch_install_instructions + "\n",
                encoding="utf-8",
            )
            log("Ren'Py: overlay hợp lệ tại game/tl/vietnamese/; chỉ dùng cấu trúc native này để cài.")
            summary = f"Xong: Ren'Py native overlay nằm tại {patch_out}. Copy nội dung COPY_TO_GAME_ROOT vào game root."
        log(summary)
        if trace is not None:
            from vntext.traceability import EVENT_COMPLETED

            patch_metrics = _trace_patch_finish(
                trace,
                patch_actions,
                patch_out,
                ok=True,
            )
            if patch_metrics.get("verification") != "PASS":
                raise RuntimeError(
                    "Patch chưa đạt read-back verification: "
                    f"{patch_metrics.get('verification')}"
                )
            trace.finish_run(EVENT_COMPLETED)
            trace_run_finished = True
            trace.write_summary(extra={"patch": {**patch_trace_metadata, **patch_metrics}})
            trace.export_jsonl()
        _emit_complete(
            complete,
            ok=True,
            summary=summary,
            patch_engine=patch_engine,
            patch_delivery=patch_delivery,
            patch_payload_path=patch_payload_path,
            patch_install_instructions=patch_install_instructions,
        )
    except Exception as exc:
        if trace is not None:
            from vntext.traceability import (
                EVENT_ABORTED,
                ROOT_CAUSE_PATCH_VERIFY_FAILED,
                ROOT_CAUSE_UNKNOWN,
            )

            patch_root_cause = (
                ROOT_CAUSE_PATCH_VERIFY_FAILED
                if isinstance(exc, PatchReadbackError)
                else ROOT_CAUSE_UNKNOWN
            )
            _trace_abort_actions(
                trace,
                patch_actions,
                error=str(exc),
                root_cause=patch_root_cause,
            )
            if trace.run_id is not None and not trace_run_finished:
                try:
                    trace.finish_run(EVENT_ABORTED, patch_root_cause)
                except Exception:
                    pass
            try:
                trace.write_summary(extra={"patch": {**patch_trace_metadata, "error": str(exc)}})
                trace.export_jsonl()
            except Exception:
                pass
        extra: dict[str, object] = {"complete": False, "pending": 1, "review_only": 1, "blocked": 1}
        if patch_out is not None:
            verification_path = patch_out / "patch_verification.json"
            import_report_path = patch_out / "import_report.txt"
            if verification_path.is_file():
                extra["patch_verification_report"] = str(verification_path)
            if import_report_path.is_file():
                extra["import_report"] = str(import_report_path)
        extra.update(
            _diagnostic_completion_fields(
                Path(csv_path).parent,
                fallback_stage="PATCH",
                fallback_root_cause=(
                    "PATCH_VERIFY_FAILED"
                    if isinstance(exc, PatchReadbackError)
                    else "PATCH_FAILED"
                ),
                fallback_affected_count=1,
                fallback_action="Inspect patch verification and import evidence before retrying Patch.",
            )
        )
        if patch_engine:
            extra.update(
                {
                    "patch_engine": patch_engine,
                    "patch_delivery": patch_delivery,
                    "patch_payload_path": patch_payload_path,
                    "patch_install_instructions": patch_install_instructions,
                }
            )
        _emit_complete(complete, ok=False, error=str(exc), **extra)
    finally:
        if trace is not None:
            trace.close()


def resolve_package_with_csv(output_path: str) -> tuple[Path, Path] | None:
    package_dir = resolve_translation_package_dir(output_path.strip())
    csv_path = package_dir / "translation.csv"
    if csv_path.exists():
        return package_dir, csv_path
    return None


class PatchReadbackError(RuntimeError):
    """Patch output exists but lacks completed read-back proof."""


def _require_patch_readback_success(patch_out: Path) -> dict:
    """Require machine-readable read-back proof before emitting patch PASS."""

    verification_path = patch_out / "patch_verification.json"
    report_path = patch_out / "import_report.txt"
    if not verification_path.is_file() or not report_path.is_file():
        raise PatchReadbackError(
            "Patch read-back verification evidence missing: expected "
            "patch_verification.json and import_report.txt"
        )
    try:
        verification = json.loads(verification_path.read_text(encoding="utf-8"))
    except (OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise PatchReadbackError(f"Patch read-back verification report unreadable: {exc}") from exc
    if not isinstance(verification, dict):
        raise PatchReadbackError("Patch read-back verification report malformed")
    counts = verification.get("counts")
    results = verification.get("results")
    if not isinstance(counts, dict) or not isinstance(results, list) or not results:
        raise PatchReadbackError("Patch read-back verification incomplete: no target evidence")
    try:
        normalized_counts = {}
        for status, value in counts.items():
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError(f"invalid count {status}={value!r}")
            normalized_counts[str(status)] = value
    except (TypeError, ValueError) as exc:
        raise PatchReadbackError(f"Patch read-back verification counts malformed: {exc}") from exc
    non_pass = {
        status: value
        for status, value in normalized_counts.items()
        if status != "PASS" and value > 0
    }
    pass_count = normalized_counts.get("PASS", 0)
    if non_pass or pass_count != len(results) or any(item.get("status") != "PASS" for item in results):
        reason = str(verification.get("reason") or "per-target read-back did not pass")
        detail = ", ".join(f"{key}={value}" for key, value in sorted(non_pass.items()))
        if detail:
            reason = f"{reason}; {detail}"
        raise PatchReadbackError(f"Patch chưa đạt read-back verification: {reason}")
    return verification


def resolve_package_with_manifest(output_path: str) -> tuple[Path, Path, Path] | None:
    package_dir = resolve_translation_package_dir(output_path.strip())
    csv_path = package_dir / "translation.csv"
    manifest_path = package_dir / "manifest.json"
    if csv_path.exists() and manifest_path.exists():
        return package_dir, csv_path, manifest_path
    return None


def resolve_package_with_raw(output_path: str) -> Path | None:
    package_dir = resolve_translation_package_dir(output_path.strip())
    if (package_dir / "translation.csv").exists() and (package_dir / "raw_candidates.csv").exists():
        return package_dir
    return None
