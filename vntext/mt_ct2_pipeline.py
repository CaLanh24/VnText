"""Pipeline responsibilities split from mt_ct2."""

from __future__ import annotations

import json
import hashlib
import re
import sqlite3
import uuid
from typing import Any

from vntext.mt_ct2_constants import (
    Path,
    RETRANSLATE_STILL_BLOCKED_NOTE,
    classify_row_authoritative,
    classify_source_row,
    ensure_mt_dir,
    mt_check,
    os,
    paths_for_csv,
    retry_row_strategies,
    time,
    translate_synonym_row,
)
from vntext.package_io import read_csv_rows_file


HUMAN_REVIEW_REQUIRED = "HUMAN_REVIEW_REQUIRED"


def _blocker_groups(
    row: dict,
    strategy: str,
    reasons: list[str],
    attempts: list[dict] | None = None,
) -> list[str]:
    """Classify a blocked row without changing any validation decision."""
    text = " ".join(
        [str(strategy or ""), *(str(reason or "") for reason in reasons)]
        + [
            str(item.get("strategy") or "")
            + " "
            + " ".join(str(r) for r in item.get("validation_reasons") or [])
            for item in attempts or []
        ]
    ).lower()
    source = str(row.get("source_text") or "")
    groups: list[str] = []

    def add(name: str) -> None:
        if name not in groups:
            groups.append(name)

    if "human_review_required" in text:
        add("human_review_required")

    if any(token in text for token in ("english-token", "english-weak", "ascii-ratio", "overlap")):
        add("residual_english")
    if "content loss" in text:
        add("content_loss")
    if "identity" in text:
        add("identity")
    if any(token in text for token in ("symbol-only", "symbol_only", "heart glyph")):
        add("special_symbol")
    if any(
        token in text
        for token in (
            "placeholder",
            "tag mismatch",
            "newline",
            "randpick",
            "synonym",
            "structural",
        )
    ):
        add("structural_tag_placeholder_randpick")
    if any(token in text for token in ("garbage", "repetition", "malformed markup", "html_garbage")):
        add("garbage")
    words = mt_check.WORD.findall(mt_check.strip_technical(source))
    if len(words) <= 5:
        add("short_sentence")
    if any(
        token in text
        for token in (
            "literal_newlines",
            "color_wrapped",
            "glrk_br",
            "br_segments",
            "pipe_segments",
            "mask_roundtrip",
            "protected",
            "sentence_segments",
            "full_sentence",
            "copy_literal",
        )
    ):
        add("preprocessing_retry")
    add("retry_exhausted")
    if not groups:
        add("unclassified")
    return groups


def _blocker_record(
    row: dict,
    *,
    strategy: str,
    raw_output: str,
    reasons: list[str],
    attempts: list[dict] | None = None,
    full_raw: str = "",
) -> dict:
    source = str(row.get("source_text") or "")
    source_visible = mt_check.strip_technical(source)
    action, reason, decision = classify_row_authoritative(row)
    return {
        "key": str(row.get("key") or ""),
        "source": source,
        "context": str(row.get("context") or ""),
        "file_path": str(row.get("file_path") or ""),
        "import_method": str(row.get("import_method") or ""),
        "classification": {
            "action": str(action or ""),
            "reason": str(reason or ""),
            "classifier_v2": decision.to_dict(),
        },
        "source_features": {
            "word_count": len(mt_check.WORD.findall(source_visible)),
            "has_tags": bool(re.search(r"<[^>]+>|\[[^\]]+\]", source)),
            "placeholder_count": len(re.findall(r"\{[^{}]*\}", source)),
            "randpick_count": source.count("[RandPick]"),
            "newline_count": source.count("\\n"),
            "special_symbols": re.findall(r"[^\w\s]", source, flags=re.UNICODE),
        },
        "initial": {
            "strategy": "batch",
            "raw_output": str(raw_output or ""),
            "validation_reasons": list(reasons or []),
        },
        "route": str(strategy or ""),
        "candidate": str(row.get("_review_candidate") or ""),
        "full_sentence_raw": str(full_raw or ""),
        "attempts": list(attempts or []),
        "final_strategy": str(strategy or ""),
        "final_reasons": list(reasons or []),
        "groups": _blocker_groups(row, strategy, reasons, attempts),
    }


def _write_blocker_inventory(package_dir: Path, records: list[dict]) -> None:
    """Persist complete blocked-row evidence next to the CT2 checkpoint."""
    path = package_dir / ".mt" / "blocker_inventory.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    counts: dict[str, int] = {}
    for record in records:
        for group in record.get("groups") or []:
            counts[group] = counts.get(group, 0) + 1
    payload = {
        "schema_version": 1,
        "source": "ct2",
        "rows": records,
        "counts": dict(sorted(counts.items())),
        "blocked_rows": len(records),
        "complete": not records,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _merge_blocker_inventory(
    package_dir: Path,
    records: list[dict],
    *,
    preserve_keys: set[str] | None = None,
) -> None:
    """Update selected-key blocker evidence without dropping unrelated rows."""
    path = package_dir / ".mt" / "blocker_inventory.json"
    existing: list[dict] = []
    if path.is_file():
        payload = json.loads(path.read_text(encoding="utf-8"))
        existing = [dict(row) for row in payload.get("rows") or [] if isinstance(row, dict)]
    if preserve_keys is None:
        by_key = {str(row.get("key") or ""): row for row in existing if row.get("key")}
    else:
        protected = {str(key) for key in preserve_keys if str(key)}
        by_key = {
            str(row.get("key") or ""): row
            for row in existing
            if row.get("key")
            and str(row.get("key") or "") in protected
            and row.get("route") == "human_review_required"
        }
    for row in records:
        if row.get("key"):
            by_key[str(row["key"])] = row
    _write_blocker_inventory(package_dir, list(by_key.values()))


def _should_human_review(row: dict, enabled: bool) -> bool:
    if not enabled:
        return False
    candidate_row = {**row, "translation": ""}
    return classify_row_authoritative(candidate_row)[0] in {"translate", "translate_synonym"}


def _count_human_review_rows(package_dir: Path) -> int:
    """Count current review rows whose provenance requires manual promotion."""
    review_path = package_dir / "review_only.csv"
    if not review_path.is_file():
        return 0
    _fields, review_rows = read_csv_rows_file(review_path)
    if not review_rows:
        return 0
    inventory_path = package_dir / ".mt" / "blocker_inventory.json"
    route_keys: set[str] = set()
    if inventory_path.is_file():
        inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
        route_keys = {
            str(row.get("key") or "")
            for row in inventory.get("rows") or []
            if isinstance(row, dict) and row.get("route") == "human_review_required"
        }
    return sum(
        1
        for row in review_rows
        if str(row.get("key") or "") in route_keys
        or "HUMAN_REVIEW_REQUIRED" in str(row.get("patch_note") or "")
    )


def _row_uses_user_glossary(row: dict, user_glossary: dict[str, str]) -> bool:
    """Return whether a source row is affected by a package glossary term."""
    if not user_glossary:
        return False
    from vntext.package_glossary import lookup_user_phrase, mask_user_glossary_terms

    source = str(row.get("source_text") or "")
    if lookup_user_phrase(source, user_glossary) is not None:
        return True
    _, restore = mask_user_glossary_terms(source, user_glossary)
    return bool(restore)


def _select_ct2_targets(
    rows: list[dict],
    user_glossary: dict[str, str],
    *,
    allow_overwrite: bool,
    force_keys: set[str] | None = None,
    glossary_v2: dict | None = None,
    protected_review_keys: set[str] | None = None,
) -> tuple[list[dict], int]:
    """Select new rows plus explicitly requested glossary refreshes.

    Existing translations remain frozen by default.  When the user enables
    the existing Overwrite switch, only rows whose source actually contains a
    user glossary entry are refreshed; this makes a newly added glossary
    effective without silently re-translating the entire package.
    """
    forced = force_keys or set()
    protected = {str(key) for key in protected_review_keys or set() if str(key)}
    from vntext.glossary_v2 import resolve_exact

    def is_v2_keep(row: dict) -> bool:
        if str(row.get("key") or "") in forced:
            return False
        match = resolve_exact(str(row.get("source_text") or ""), row, glossary_v2)
        return match.get("status") == "match" and match.get("kind") == "do_not_translate"

    targets = [
        row
        for row in rows
        if str(row.get("key") or "") not in protected
        and (
            str(row.get("key") or "") in forced
        or (
            classify_row_authoritative(row)[0] in ("translate", "translate_synonym")
            and not is_v2_keep(row)
        )
        )
    ]
    if not allow_overwrite or not user_glossary:
        return targets, 0

    target_keys = {str(row.get("key") or "") for row in targets}
    refresh = [
        row
        for row in rows
        if str(row.get("key") or "") not in target_keys
        and str(row.get("key") or "") not in protected
        and str(row.get("translation") or "").strip()
        and not mt_check.is_synonym_row(row)
        and _row_uses_user_glossary(row, user_glossary)
    ]
    return targets + refresh, len(refresh)


def _translation_cache_context(
    package_dir: Path,
    model_adapter,
    user_glossary: dict[str, str],
    translation_memory: dict,
    *,
    allow_overwrite: bool,
    glossary_v2: dict | None = None,
    context_sidecar: dict | None = None,
) -> dict:
    from vntext.mt_classify import CLASSIFIER_POLICY_HASH, CLASSIFIER_POLICY_VERSION

    memory_scope = hashlib.sha256(
        json.dumps(translation_memory or {}, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
            "utf-8", "surrogatepass"
        )
    ).hexdigest()
    glossary_v2_hash = str((glossary_v2 or {}).get("fingerprint") or "")
    glossary_hash = hashlib.sha256(
        json.dumps(
            {"flat": dict(user_glossary or {}), "v2": glossary_v2_hash},
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8", "surrogatepass")
    ).hexdigest()
    metadata = model_adapter.metadata()
    records = (context_sidecar or {}).get("records") or []
    context_by_key = {
        str(item.get("key") or ""): item
        for item in records
        if isinstance(item, dict) and item.get("key")
    }
    return {
        "model_metadata": metadata,
        "glossary": dict(user_glossary or {}),
        "glossary_hash": glossary_hash,
        "memory_scope": memory_scope,
        "classifier_policy_version": CLASSIFIER_POLICY_VERSION,
        "classifier_policy_hash": CLASSIFIER_POLICY_HASH,
        "strategy_version": "ct2-pipeline-1-overwrite" if allow_overwrite else "ct2-pipeline-1-frozen",
        "context_builder_version": str(
            (context_sidecar or {}).get("builder_version") or "none"
        ),
        "context_status": str((context_sidecar or {}).get("status") or "METADATA_ONLY"),
        "context_model_injection": bool((context_sidecar or {}).get("model_injection", False)),
        "decoding": dict(metadata.get("decoding") or {}),
        "context_by_key": context_by_key,
        "protected_span_schema_version": "1",
        "engine_profile": "ct2:" + str(metadata.get("model_id") or "unknown"),
    }


def _open_translation_cache(package_dir: Path):
    from vntext.translation_cache import TranslationCache, TranslationCacheError

    try:
        return TranslationCache(package_dir), ""
    except (OSError, sqlite3.Error, TranslationCacheError) as exc:
        # Cache is an optimization, never a reason to skip model translation.
        # The returned disabled status is surfaced in the task result/trace.
        return None, str(exc)


def _cached_batch_translate_chunk(
    cache,
    translator,
    rows: list[dict],
    user_glossary: dict[str, str],
    translation_memory: dict,
    cache_context: dict,
    *,
    v2_glossary: dict | None = None,
    glossary_conflicts: set[str] | None = None,
    cache_fingerprints: dict[str, str] | None = None,
) -> tuple[dict[str, str], set[str], set[str]]:
    from vntext.mt_ct2_io import _batch_translate_chunk
    from vntext.package_glossary import lookup_user_phrase
    from vntext.mt_memory import lookup_translation_memory
    from vntext.glossary_v2 import resolve_exact
    from vntext.translation_cache import compute_cache_fingerprint

    fingerprint_context = {
        key: value
        for key, value in cache_context.items()
        if key not in {"context_by_key", "context_status", "context_model_injection"}
    }

    def record_fingerprints() -> None:
        if cache_fingerprints is None:
            return
        for row in rows:
            key = str(row.get("key") or "")
            if not key:
                continue
            context_record = cache_context.get("context_by_key", {}).get(key)
            cache_row = {**row, "context_window": context_record} if context_record else row
            fingerprint = compute_cache_fingerprint(cache_row, **fingerprint_context)
            cache_fingerprints[key] = str(fingerprint["cache_key"])

    authoritative_keys = set()
    for row in rows:
        source = str(row.get("source_text") or "")
        exact = resolve_exact(source, row, v2_glossary)
        if exact.get("status") == "match":
            authoritative_keys.add(str(row.get("key") or ""))
        elif lookup_user_phrase(source, user_glossary) is not None:
            authoritative_keys.add(str(row.get("key") or ""))
        elif lookup_translation_memory(row, translation_memory) is not None:
            authoritative_keys.add(str(row.get("key") or ""))

    record_fingerprints()
    if cache is None:
        return (
            _batch_translate_chunk(
                translator,
                rows,
                user_glossary,
                translation_memory,
                v2_glossary=v2_glossary,
                glossary_conflicts=glossary_conflicts,
            ),
            set(),
            authoritative_keys,
        )
    outputs: dict[str, str] = {}
    cached_keys: set[str] = set()
    misses: list[dict] = []
    for row in rows:
        context_record = cache_context.get("context_by_key", {}).get(str(row.get("key") or ""))
        cache_row = {**row, "context_window": context_record} if context_record else row
        fingerprint = compute_cache_fingerprint(cache_row, **fingerprint_context)
        hit = cache.lookup(fingerprint["cache_key"])
        if hit is None:
            misses.append(row)
        else:
            outputs[str(row.get("key") or "")] = hit
            cached_keys.add(str(row.get("key") or ""))
    if misses:
        outputs.update(
            _batch_translate_chunk(
                translator,
                misses,
                user_glossary,
                translation_memory,
                v2_glossary=v2_glossary,
                glossary_conflicts=glossary_conflicts,
            )
        )
    return outputs, cached_keys, authoritative_keys


def _cache_validated_candidate(
    cache,
    row: dict,
    candidate: str,
    cache_context: dict,
    *,
    cache_fingerprints: dict[str, str] | None = None,
) -> None:
    if not candidate:
        return
    from vntext.translation_cache import compute_cache_fingerprint

    context_record = cache_context.get("context_by_key", {}).get(str(row.get("key") or ""))
    cache_row = {**row, "context_window": context_record} if context_record else row
    fingerprint_context = {
        key: value
        for key, value in cache_context.items()
        if key not in {"context_by_key", "context_status", "context_model_injection"}
    }
    fingerprint = compute_cache_fingerprint(cache_row, **fingerprint_context)
    key = str(row.get("key") or "")
    if cache_fingerprints is not None and key:
        cache_fingerprints[key] = str(fingerprint["cache_key"])
    if cache is None:
        return
    cache.put(
        fingerprint["cache_key"],
        row,
        candidate,
        validation_status="PASS",
        provenance={
            "source_key": str(row.get("key") or ""),
            "source_hash": fingerprint["fingerprint"]["source_hash"],
            "fingerprint": fingerprint["fingerprint"],
            "validation": "current _safe_candidate / Patch Gate",
        },
    )



def run_ct2_translate(
    csv_path: str | Path,
    *,
    model_dir: str | Path | None = None,
    model_adapter: Any | None = None,
    human_review_required: bool = False,
    allow_overwrite: bool = False,
    is_cancelled: CancelFn | None = None,
    progress: ProgressFn | None = None,
    log: LogFn | None = None,
) -> dict:
    from vntext.mt_ct2_io import _ReviewSink, _apply_mapping_memory, _batch_translate_chunk, _flush_csv_atomic, _load_csv
    from vntext.mt_ct2_model import EmptyCsvError, TranslateCancelled, _fast_retry_default, _flush_every_rows, get_translator
    from vntext.mt_ct2_status import _build_translate_result, _clear_known_bad_translations, _count_pending, _count_review_only_rows, _load_human_review_keys, _prune_resolved_review_only, _quarantine_technical_rows, _safe_candidate, reconcile_mirror_translations
    csv_path = Path(csv_path).resolve()
    if not csv_path.is_file():
        raise FileNotFoundError(str(csv_path))

    fields, rows = _load_csv(csv_path)
    if not fields or "key" not in fields or "translation" not in fields:
        raise EmptyCsvError("translation.csv header không hợp lệ")
    if not rows:
        raise EmptyCsvError("translation.csv không có dòng dữ liệu")

    package_dir = csv_path.parent
    human_review_keys = _load_human_review_keys(package_dir)
    initial_filled_keys = {
        str(row.get("key") or "")
        for row in rows
        if str(row.get("key") or "") and str(row.get("translation") or "").strip()
    }
    blocker_records: list[dict] = []
    retry_attempts_by_key: dict[str, list[dict]] = {}
    rows, quarantined_technical = _quarantine_technical_rows(
        package_dir,
        fields,
        rows,
        protected_review_keys=human_review_keys,
    )
    if quarantined_technical:
        _flush_csv_atomic(csv_path, fields, rows)
    whitelist = mt_check.load_whitelist(package_dir)
    from vntext.package_glossary import load_user_glossary
    from vntext.mt_memory import build_translation_memory, load_translation_memory
    from vntext.context_builder import build_context_sidecar
    from vntext.glossary_v2 import load_compatible_entries

    user_glossary = load_user_glossary(package_dir)
    glossary_v2 = load_compatible_entries(package_dir)
    context_sidecar = build_context_sidecar(package_dir, rows)
    translation_memory = load_translation_memory(package_dir)
    if not translation_memory.get("entries"):
        translation_memory = build_translation_memory(rows, package_dir)

    def emit(msg: str) -> None:
        if log:
            log(msg)

    def prog(**kwargs) -> None:
        if progress:
            progress(kwargs)

    from vntext.intentional_keep import apply_intentional_keep_batch

    keep_res = apply_intentional_keep_batch(
        package_dir,
        rows,
        fields,
        csv_path,
        emit=emit if log else None,
        protected_review_keys=human_review_keys,
    )

    cleared_bad = _clear_known_bad_translations(rows, whitelist, emit)
    forced_keys = {
        str(row.get("key") or "")
        for row in rows
        if row.get("_ct2_force") and row.get("key")
    }
    # The force marker is an in-memory routing signal only.  Remove it before
    # any CSV flush so the package schema remains exactly CSV_FIELDS.
    for row in rows:
        row.pop("_ct2_force", None)
    if cleared_bad:
        _flush_csv_atomic(csv_path, fields, rows)

    copied_vi = int(keep_res.get("applied") or 0)
    skipped_technical = quarantined_technical + sum(
        1 for r in rows if classify_source_row(r)[0] == "skip_technical"
    )
    skipped_ui_label = 0
    by_key = {r["key"]: r for r in rows}
    copy_map: dict[str, str] = {}
    review_sink_pre = _ReviewSink(emit)
    from vntext.glossary_v2 import resolve_exact
    for row in rows:
        if str(row.get("key") or "") in human_review_keys:
            continue
        v2_exact = resolve_exact(str(row.get("source_text") or ""), row, glossary_v2)
        if (
            str(row.get("key") or "") not in forced_keys
            and v2_exact.get("status") == "match"
            and v2_exact.get("kind") == "do_not_translate"
        ):
            copy_map[row["key"]] = str(v2_exact.get("target") or row.get("source_text") or "")
            continue
        action, reason, _decision = classify_row_authoritative(row)
        if str(row.get("key") or "") in forced_keys:
            continue
        if action == "copy_source":
            copy_map[row["key"]] = row["source_text"]
        elif action == "ui_label_fixed":
            copy_map[row["key"]] = reason
        elif action == "copy_literal":
            copy_map[row["key"]] = row["source_text"]
        elif action == "skip_ui_label":
            # Legacy path: giữ EN thay vì để trống (tránh dialogue_pending vô hạn).
            copy_map[row["key"]] = row["source_text"]
            skipped_ui_label += 1
    if skipped_ui_label:
        emit(f"Nhãn UI ngắn giữ EN (copy): {skipped_ui_label} dòng")
    if copy_map:
        copy_applied, copy_blocked, copy_review = _apply_mapping_memory(
            by_key, copy_map, allow_overwrite=allow_overwrite, whitelist=whitelist,
        )
        copied_vi += copy_applied
        if copy_blocked:
            emit(f"Cảnh báo: {copy_blocked} dòng copy_vi bị chặn")
        for row, attempted, reasons in copy_review:
            blocker_records.append(
                _blocker_record(
                    row,
                    strategy="copy_mapping",
                    raw_output=attempted,
                    reasons=reasons,
                )
            )
        if copied_vi:
            _flush_csv_atomic(csv_path, fields, rows)
            _prune_resolved_review_only(
                package_dir,
                rows,
                emit,
                protected_review_keys=human_review_keys,
            )

    targets, glossary_refresh_count = _select_ct2_targets(
        rows,
        user_glossary,
        allow_overwrite=allow_overwrite,
        force_keys=forced_keys,
        glossary_v2=glossary_v2,
        protected_review_keys=human_review_keys,
    )
    if glossary_refresh_count:
        emit(
            f"Glossary: dịch lại {glossary_refresh_count} dòng đã có bản dịch "
            "(đã bật Ghi đè bản dịch cũ)"
        )
    elif allow_overwrite is False and user_glossary:
        locked_glossary_rows = sum(
            1
            for row in rows
            if str(row.get("translation") or "").strip()
            and _row_uses_user_glossary(row, user_glossary)
        )
        if locked_glossary_rows:
            emit(
                f"Glossary: {locked_glossary_rows} dòng đã có bản dịch; "
                "bật Ghi đè bản dịch cũ để dịch lại theo glossary"
            )
    max_rows = int(os.environ.get("VNTEXT_CT2_MAX_ROWS", "0") or "0")
    if max_rows > 0:
        targets = targets[:max_rows]

    if not targets:
        translated_count = sum(1 for r in rows if str(r.get("translation") or "").strip())
        pending_counts = _count_pending(rows)
        pending = sum(
            pending_counts.get(action, 0)
            for action in ("translate", "translate_synonym", "review_only", "unsupported")
        )
        _prune_resolved_review_only(
            package_dir,
            rows,
            emit,
            protected_review_keys=human_review_keys,
        )
        review_total = _count_review_only_rows(package_dir)
        human_review_count = _count_human_review_rows(package_dir)
        if human_review_count:
            emit(f"Cần duyệt thủ công {human_review_count} dòng trước khi Patch")
        summary = (
            f"Không còn dòng cần dịch MT. Tổng {translated_count}/{len(rows)} có translation; "
            f"copy_vi={copied_vi}, skip_ky_thuat={skipped_technical}, pending={pending}, review={review_total}"
        )
        if human_review_count:
            summary += f". Cần duyệt thủ công {human_review_count} dòng trước khi Patch"
        emit(summary)
        build_translation_memory(rows, package_dir)
        if blocker_records or not review_total:
            _merge_blocker_inventory(
                package_dir,
                blocker_records,
                preserve_keys=human_review_keys,
            )
        result = _build_translate_result(
            package_dir,
            rows,
            applied=0,
            copied_vi=copied_vi,
            skipped_technical=skipped_technical,
            blocked=0,
            summary=summary,
            pipeline_liveness=True,
        )
        if model_adapter is not None:
            result["model_metadata"] = dict(model_adapter.metadata() or {})
        result["human_review_required_count"] = human_review_count
        if human_review_count:
            result["ok"] = False
        return result

    explicit_model = Path(model_dir) if model_dir else None
    if model_adapter is None:
        from vntext.mt_model_adapter import adapt_ct2_translator

        translator = adapt_ct2_translator(get_translator(explicit_model), explicit_model)
    else:
        translator = model_adapter
    cfg = dict(getattr(translator, "config", {}) or {})
    batch_size = max(1, int(cfg.get("batch_size", 4) or 4))
    inter_threads = max(1, int(cfg.get("inter_threads", 1) or 1))
    metadata = dict(getattr(translator, "metadata", lambda: {})() or {})
    model_label = str(metadata.get("model_engine") or "Local translation model")
    cache, cache_error = _open_translation_cache(package_dir)
    cache_context = _translation_cache_context(
        package_dir,
        translator,
        user_glossary,
        translation_memory,
        allow_overwrite=allow_overwrite,
        glossary_v2=glossary_v2,
        context_sidecar=context_sidecar,
    )
    cache_fingerprints: dict[str, str] = {}
    synonym_rows = [
        r for r in targets
        if str(r.get("key") or "") not in forced_keys
        and classify_row_authoritative(r)[0] == "translate_synonym"
    ]
    mt_targets = [
        r for r in targets
        if str(r.get("key") or "") in forced_keys
        or classify_row_authoritative(r)[0] == "translate"
    ]
    flush_every = _flush_every_rows()
    fast_retry = _fast_retry_default(len(mt_targets))
    emit(
        f"{model_label} — {len(mt_targets)} dòng MT"
        f"{f', {len(synonym_rows)} synonym → review' if synonym_rows else ''} "
        f"(batch={batch_size}, inter={inter_threads}, flush={flush_every}"
        f"{', fast_retry' if fast_retry else ''})"
    )

    paths = paths_for_csv(csv_path)
    ensure_mt_dir(paths)
    applied = 0
    blocked = 0
    human_review_count = 0
    review_sink = _ReviewSink(emit)
    total = len(targets)
    delay_ms = int(os.environ.get("VNTEXT_CT2_TEST_DELAY_MS", "0") or "0")
    pending_flush = 0
    done_offset = 0

    def queue_human_review(
        row: dict,
        candidate: str,
        *,
        raw_output: str = "",
        attempts: list[dict] | None = None,
        full_raw: str = "",
    ) -> None:
        nonlocal human_review_count
        row_for_record = dict(row)
        row_for_record["_review_candidate"] = str(candidate or "")
        reasons = [HUMAN_REVIEW_REQUIRED]
        row["translation"] = ""
        review_sink.add(row, candidate, reasons)
        blocker_records.append(
            _blocker_record(
                row_for_record,
                strategy="human_review_required",
                raw_output=raw_output or candidate,
                reasons=reasons,
                attempts=attempts,
                full_raw=full_raw,
            )
        )
        human_review_count += 1

    if synonym_rows:
        syn_map: dict[str, str] = {}
        emit(f"Synonym: {len(synonym_rows)} dòng (dịch từng variant)")
        for si, row in enumerate(synonym_rows, start=1):
            src = str(row.get("source_text") or "")
            # Synonym rows are small and must not be promoted by copying the
            # English pool during the large-job fast path. Translate each
            # variant once; the normal quality gate still rejects bad output.
            raw = translate_synonym_row(row, translator)
            candidate, reasons = _safe_candidate(row, raw, whitelist, quality=True)
            if not candidate and src.strip():
                # Fallback cuối: giữ nguyên pool EN (đủ cấu trúc synonym).
                candidate, reasons = _safe_candidate(row, src, whitelist, quality=True)
                raw = src
            if candidate:
                _cache_validated_candidate(
                    cache,
                    row,
                    candidate,
                    cache_context,
                    cache_fingerprints=cache_fingerprints,
                )
                if _should_human_review(row, human_review_required):
                    queue_human_review(row, candidate, raw_output=raw)
                else:
                    syn_map[row["key"]] = candidate
            else:
                review_sink.add(row, raw, reasons or ["synonym validation failed"])
                blocker_records.append(
                    _blocker_record(
                        row,
                        strategy="synonym",
                        raw_output=raw,
                        reasons=reasons or ["synonym validation failed"],
                    )
                )
                blocked += 1
            if si % 10 == 0 or si == len(synonym_rows):
                emit(f"Tiến độ synonym: {si}/{len(synonym_rows)}")
            if si % 25 == 0:
                if syn_map:
                    syn_applied, syn_blocked, syn_review = _apply_mapping_memory(
                        by_key,
                        syn_map,
                        allow_overwrite=allow_overwrite,
                        whitelist=whitelist,
                    )
                    applied += syn_applied
                    blocked += syn_blocked
                    for brow, attempted, sreasons in syn_review:
                        review_sink.add(brow, attempted, sreasons)
                        blocker_records.append(
                            _blocker_record(
                                brow,
                                strategy="synonym_mapping",
                                raw_output=attempted,
                                reasons=sreasons,
                            )
                        )
                    syn_map.clear()
                review_sink.flush(package_dir)
                _flush_csv_atomic(csv_path, fields, rows)
        if syn_map:
            syn_applied, syn_blocked, syn_review = _apply_mapping_memory(
                by_key, syn_map, allow_overwrite=allow_overwrite, whitelist=whitelist,
            )
            applied += syn_applied
            blocked += syn_blocked
            for row, attempted, reasons in syn_review:
                review_sink.add(row, attempted, reasons)
                blocker_records.append(
                    _blocker_record(
                        row,
                        strategy="synonym_mapping",
                        raw_output=attempted,
                        reasons=reasons,
                    )
                )
        review_sink.flush(package_dir)
        _flush_csv_atomic(csv_path, fields, rows)
        done_offset = len(synonym_rows)
        prog(
            done=done_offset,
            total=total,
            step="Đang dịch OPUS-MT",
            item=f"{done_offset}/{total}",
        )

    for start in range(0, len(mt_targets), batch_size):
        if is_cancelled and is_cancelled():
            _flush_csv_atomic(csv_path, fields, rows)
            review_sink.flush(package_dir)
            raise TranslateCancelled()
        chunk = mt_targets[start : start + batch_size]
        if delay_ms > 0:
            time.sleep(delay_ms * len(chunk) / 1000.0)

        translations: dict[str, str] = {}
        retry_rows: list[tuple[dict, str, list[str]]] = []
        glossary_conflicts: set[str] = set()
        try:
            raw_by_key, cached_keys, authoritative_keys = _cached_batch_translate_chunk(
                cache,
                translator,
                chunk,
                user_glossary,
                translation_memory,
                cache_context,
                v2_glossary=glossary_v2,
                glossary_conflicts=glossary_conflicts,
                cache_fingerprints=cache_fingerprints,
            )
        except Exception as exc:
            emit(f"Lỗi dịch batch chunk {start + 1}-{start + len(chunk)}: {exc}")
            raw_by_key = {}
        for row in chunk:
            raw = raw_by_key.get(row["key"], "")
            candidate, reasons = _safe_candidate(
                row,
                raw,
                whitelist,
                quality=True,
                preserve_candidate=row["key"] in authoritative_keys,
            )
            if candidate:
                _cache_validated_candidate(
                    cache,
                    row,
                    candidate,
                    cache_context,
                    cache_fingerprints=cache_fingerprints,
                )
                if _should_human_review(row, human_review_required):
                    queue_human_review(row, candidate, raw_output=raw)
                else:
                    translations[row["key"]] = candidate
            else:
                if row["key"] in glossary_conflicts:
                    conflict_reasons = ["Glossary V2 conflict — review required"]
                    review_sink.add(row, raw, conflict_reasons)
                    blocker_records.append(
                        _blocker_record(
                            row,
                            strategy="glossary_v2_conflict",
                            raw_output=raw,
                            reasons=conflict_reasons,
                        )
                    )
                    blocked += 1
                else:
                    retry_rows.append((row, raw, reasons))

        # Quality retries are translated as one full-sentence batch.  Calling
        # CT2 once per bad row made a large package appear hung and also gave
        # the model less context than the original sentence.
        full_by_key: dict[str, str] = {}
        if retry_rows:
            try:
                full_outputs = translator.translate_many([r["source_text"] for r, _, _ in retry_rows])
                full_by_key = {
                    row["key"]: output
                    for (row, _, _), output in zip(retry_rows, full_outputs)
                }
            except Exception as exc:
                emit(f"Lỗi retry full-sentence chunk {start + 1}-{start + len(chunk)}: {exc}")
        for row, raw, initial_reasons in retry_rows:
            retry_trace: list[dict] = []
            _strat = "retry"
            try:
                retry_cand, _strat, retry_reasons = retry_row_strategies(
                    row, translator, whitelist, batch_raw=raw, fast=fast_retry,
                    user_glossary=user_glossary, full_raw=full_by_key.get(row["key"], ""),
                    trace=retry_trace,
                )
                if not retry_cand and fast_retry:
                    # Large jobs take the cheap path first.  A failed cheap
                    # candidate still gets the structural/segmentation ladder;
                    # fast retry must not turn a review row into a dead end.
                    retry_cand, _strat, retry_reasons = retry_row_strategies(
                        row,
                        translator,
                        whitelist,
                        batch_raw=raw,
                        fast=False,
                        user_glossary=user_glossary,
                        full_raw=full_by_key.get(row["key"], ""),
                        trace=retry_trace,
                    )
            except Exception as exc:
                # A malformed translator adapter must block this row and send
                # it to review, never abort the whole translation batch.
                retry_cand = None
                retry_reasons = [f"retry adapter error: {exc}"]
                retry_trace.append(
                    {
                        "attempt_id": str(uuid.uuid4()),
                        "strategy": "retry_adapter_error",
                        "raw_output": str(raw or ""),
                        "raw_output_hash": hashlib.sha256(
                            str(raw or "").encode("utf-8", "surrogatepass")
                        ).hexdigest()
                        if raw
                        else "",
                        "candidate": "",
                        "candidate_hash": "",
                        "validation_reasons": list(retry_reasons),
                        "passed": False,
                    }
                )
            retry_attempts_by_key[row["key"]] = retry_trace
            if retry_cand:
                _cache_validated_candidate(
                    cache,
                    row,
                    retry_cand,
                    cache_context,
                    cache_fingerprints=cache_fingerprints,
                )
                if _should_human_review(row, human_review_required):
                    queue_human_review(
                        row,
                        retry_cand,
                        raw_output=full_by_key.get(row["key"], "") or raw,
                        attempts=retry_trace,
                        full_raw=full_by_key.get(row["key"], ""),
                    )
                else:
                    translations[row["key"]] = retry_cand
            else:
                final_reasons = retry_reasons or initial_reasons or ["validation failed"]
                review_sink.add(row, raw, final_reasons)
                blocker_records.append(
                    _blocker_record(
                        row,
                        strategy=_strat,
                        raw_output=raw,
                        reasons=final_reasons,
                        attempts=retry_trace,
                        full_raw=full_by_key.get(row["key"], ""),
                    )
                )
                blocked += 1

        chunk_applied, chunk_blocked, review_triples = _apply_mapping_memory(
            by_key,
            translations,
            allow_overwrite=allow_overwrite,
            whitelist=whitelist,
        )
        applied += chunk_applied
        blocked += chunk_blocked
        for row, attempted, reasons in review_triples:
            review_sink.add(row, attempted, reasons)
            blocker_records.append(
                _blocker_record(
                    row,
                    strategy="apply_mapping",
                    raw_output=attempted,
                    reasons=reasons,
                )
            )

        pending_flush += len(chunk)
        if pending_flush >= flush_every:
            _flush_csv_atomic(csv_path, fields, rows)
            review_sink.flush(package_dir)
            pending_flush = 0
            emit(
                f"Tiến độ MT: {min(start + len(chunk), len(mt_targets))}/{len(mt_targets)} "
                f"(applied={applied}, blocked={blocked})"
            )

        prog(
            done=done_offset + min(start + len(chunk), len(mt_targets)),
            total=total,
            step="Đang dịch OPUS-MT",
            item=f"{done_offset + min(start + len(chunk), len(mt_targets))}/{total}",
        )

    eligible_mirror_keys = {
        str(row.get("key") or "")
        for row in rows
        if str(row.get("key") or "") not in initial_filled_keys
        and str(row.get("key") or "") not in human_review_keys
        and str(row.get("translation") or "").strip()
    }
    mirror_reconciled = reconcile_mirror_translations(
        rows, whitelist, eligible_keys=eligible_mirror_keys
    )
    if mirror_reconciled:
        emit(f"Mirror reconcile: đồng bộ {mirror_reconciled} bản dịch trùng nguồn")
    _flush_csv_atomic(csv_path, fields, rows)
    review_sink.flush(package_dir)
    _prune_resolved_review_only(
        package_dir,
        rows,
        emit,
        protected_review_keys=human_review_keys,
    )
    build_translation_memory(rows, package_dir)
    _merge_blocker_inventory(
        package_dir,
        blocker_records,
        preserve_keys=human_review_keys,
    )
    human_review_count = _count_human_review_rows(package_dir)
    pending_counts = _count_pending(rows)
    pending_total = sum(
        pending_counts.get(action, 0)
        for action in ("translate", "translate_synonym", "review_only", "unsupported")
    )
    summary = (
        f"Dịch: applied={applied}, copy_vi={copied_vi}, skip_ky_thuat={skipped_technical}, "
        f"blocked={blocked}, review={_count_review_only_rows(package_dir)}, "
        f"pending={pending_total}, "
        f"tổng {sum(1 for r in rows if str(r.get('translation') or '').strip())}/{len(rows)} có translation"
    )
    if human_review_count:
        summary += f". Cần duyệt thủ công {human_review_count} dòng trước khi Patch"
        emit(f"Cần duyệt thủ công {human_review_count} dòng trước khi Patch")
    emit(summary)
    result = _build_translate_result(
        package_dir,
        rows,
        applied=applied,
        copied_vi=copied_vi,
        skipped_technical=skipped_technical,
        blocked=blocked,
        summary=summary,
        pipeline_liveness=True,
    )
    result["model_metadata"] = metadata
    result["human_review_required_count"] = human_review_count
    if human_review_count:
        result["ok"] = False
    if cache is not None:
        result["cache"] = cache.summary()
        cache.close()
    else:
        result["cache"] = {
            "kind": "validated_translation_cache",
            "status": "disabled",
            "error": cache_error,
            "hits": 0,
            "misses": 0,
        }
    result["cache_fingerprints"] = cache_fingerprints
    result["retry_attempts_by_key"] = retry_attempts_by_key
    return result


def run_ct2_translate_keys(
    csv_path: str | Path,
    keys: list[str],
    *,
    model_dir: str | Path | None = None,
    model_adapter: Any | None = None,
    human_review_required: bool = False,
    allow_overwrite: bool = True,
    backup: bool = True,
    is_cancelled: CancelFn | None = None,
    progress: ProgressFn | None = None,
    log: LogFn | None = None,
) -> dict:
    """Dịch lại một tập key — dùng cho tab Sửa CSV (xử lý dòng bị gate chặn)."""
    from vntext.mt_ct2_io import _ReviewSink, _apply_mapping_memory, _batch_translate_chunk, _flush_csv_atomic, _load_csv
    from vntext.mt_ct2_model import EmptyCsvError, TranslateCancelled, _flush_every_rows, get_translator
    from vntext.mt_ct2_status import _load_human_review_keys, _safe_candidate
    from vntext.package_io import backup_translation_csv

    csv_path = Path(csv_path).resolve()
    keys_set = {k for k in keys if k}
    if not keys_set:
        existing_review_count = _count_human_review_rows(Path(csv_path).resolve().parent)
        return {
            "ok": existing_review_count == 0,
            "applied": 0,
            "blocked": 0,
            "summary": "Không có key để dịch.",
            "total": 0,
            "pipeline_liveness": True,
            "human_review_required_count": existing_review_count,
            "cache": {"status": "not_applicable", "kind": "validated_translation_cache"},
            "cache_fingerprints": {},
        }

    fields, rows = _load_csv(csv_path)
    if not fields or "key" not in fields or "translation" not in fields:
        raise EmptyCsvError("translation.csv header không hợp lệ")

    package_dir = csv_path.parent
    human_review_keys = _load_human_review_keys(package_dir)
    whitelist = mt_check.load_whitelist(package_dir)
    from vntext.package_glossary import load_user_glossary
    from vntext.mt_memory import build_translation_memory, load_translation_memory
    from vntext.context_builder import build_context_sidecar
    from vntext.glossary_v2 import load_compatible_entries

    user_glossary = load_user_glossary(package_dir)
    glossary_v2 = load_compatible_entries(package_dir)
    context_sidecar = build_context_sidecar(package_dir, rows)
    translation_memory = load_translation_memory(package_dir)
    if not translation_memory.get("entries"):
        translation_memory = build_translation_memory(rows, package_dir)

    def emit(msg: str) -> None:
        if log:
            log(msg)

    def prog(**kwargs) -> None:
        if progress:
            progress(kwargs)

    if backup:
        backup_translation_csv(csv_path)

    mt_targets: list[dict] = []
    for row in rows:
        if row["key"] not in keys_set:
            continue
        if str(row.get("key") or "") in human_review_keys:
            continue
        if not str(row.get("source_text") or "").strip():
            continue
        if mt_check.is_synonym_row(row):
            emit(f"Bỏ qua synonym {row['key']} — cần dịch thủ công")
            continue
        action, _reason, _decision = classify_row_authoritative({**row, "translation": ""})
        if action not in {"translate", "translate_synonym", "ui_label_fixed"}:
            continue
        mt_targets.append(row)

    if not mt_targets:
        existing_review_count = _count_human_review_rows(package_dir)
        return {
            "ok": existing_review_count == 0,
            "applied": 0,
            "blocked": 0,
            "summary": (
                f"Không có dòng MT để dịch lại. Cần duyệt thủ công {existing_review_count} dòng trước khi Patch"
                if existing_review_count
                else "Không có dòng MT để dịch lại."
            ),
            "total": 0,
            "pipeline_liveness": True,
            "human_review_required_count": existing_review_count,
            "cache": {"status": "not_applicable", "kind": "validated_translation_cache"},
            "cache_fingerprints": {},
        }

    explicit_model = Path(model_dir) if model_dir else None
    if model_adapter is None:
        from vntext.mt_model_adapter import adapt_ct2_translator

        translator = adapt_ct2_translator(get_translator(explicit_model), explicit_model)
    else:
        translator = model_adapter
    cfg = dict(getattr(translator, "config", {}) or {})
    batch_size = max(1, int(cfg.get("batch_size", 4) or 4))
    metadata = dict(getattr(translator, "metadata", lambda: {})() or {})
    model_label = str(metadata.get("model_engine") or "Local translation model")
    cache, cache_error = _open_translation_cache(package_dir)
    cache_context = _translation_cache_context(
        package_dir,
        translator,
        user_glossary,
        translation_memory,
        allow_overwrite=allow_overwrite,
        glossary_v2=glossary_v2,
        context_sidecar=context_sidecar,
    )
    cache_fingerprints: dict[str, str] = {}
    retry_attempts_by_key: dict[str, list[dict]] = {}
    by_key = {r["key"]: r for r in rows}
    review_sink = _ReviewSink(emit)
    blocker_records: list[dict] = []
    paths = paths_for_csv(csv_path)
    ensure_mt_dir(paths)

    applied = 0
    blocked = 0
    human_review_count = 0
    flush_every = _flush_every_rows()
    pending_flush = 0
    total = len(mt_targets)
    delay_ms = int(os.environ.get("VNTEXT_CT2_TEST_DELAY_MS", "0") or "0")

    emit(f"Dịch lại {len(mt_targets)} dòng — {model_label}")

    def queue_human_review(
        row: dict,
        candidate: str,
        *,
        raw_output: str = "",
        attempts: list[dict] | None = None,
        full_raw: str = "",
    ) -> None:
        nonlocal human_review_count
        row_for_record = dict(row)
        row_for_record["_review_candidate"] = str(candidate or "")
        reasons = [HUMAN_REVIEW_REQUIRED]
        row["translation"] = ""
        review_sink.add(row, candidate, reasons)
        blocker_records.append(
            _blocker_record(
                row_for_record,
                strategy="human_review_required",
                raw_output=raw_output or candidate,
                reasons=reasons,
                attempts=attempts,
                full_raw=full_raw,
            )
        )
        human_review_count += 1

    for start in range(0, len(mt_targets), batch_size):
        if is_cancelled and is_cancelled():
            _flush_csv_atomic(csv_path, fields, rows)
            review_sink.flush(package_dir)
            raise TranslateCancelled()
        chunk = mt_targets[start : start + batch_size]
        if delay_ms > 0:
            time.sleep(delay_ms * len(chunk) / 1000.0)

        translations: dict[str, str] = {}
        retry_rows: list[tuple[dict, str, list[str]]] = []
        glossary_conflicts: set[str] = set()
        try:
            raw_by_key, cached_keys, authoritative_keys = _cached_batch_translate_chunk(
                cache,
                translator,
                chunk,
                user_glossary,
                translation_memory,
                cache_context,
                v2_glossary=glossary_v2,
                glossary_conflicts=glossary_conflicts,
                cache_fingerprints=cache_fingerprints,
            )
        except Exception as exc:
            emit(f"Lỗi dịch batch chunk {start + 1}-{start + len(chunk)}: {exc}")
            raw_by_key = {}

        for row in chunk:
            raw = raw_by_key.get(row["key"], "")
            candidate, reasons = _safe_candidate(
                row,
                raw,
                whitelist,
                quality=True,
                preserve_candidate=row["key"] in authoritative_keys,
            )
            if candidate:
                _cache_validated_candidate(
                    cache,
                    row,
                    candidate,
                    cache_context,
                    cache_fingerprints=cache_fingerprints,
                )
                if _should_human_review(row, human_review_required):
                    queue_human_review(row, candidate, raw_output=raw)
                else:
                    translations[row["key"]] = candidate
            else:
                if row["key"] in glossary_conflicts:
                    row["translation"] = ""
                    note = "Glossary V2 conflict — review required"
                    review_sink.add(row, raw, [note])
                    blocked += 1
                else:
                    retry_rows.append((row, raw, reasons))

        full_by_key: dict[str, str] = {}
        if retry_rows:
            try:
                full_outputs = translator.translate_many([r["source_text"] for r, _, _ in retry_rows])
                full_by_key = {
                    row["key"]: output
                    for (row, _, _), output in zip(retry_rows, full_outputs)
                }
            except Exception as exc:
                emit(f"Lỗi retry full-sentence chunk {start + 1}-{start + len(chunk)}: {exc}")
        for row, raw, reasons in retry_rows:
            retry_trace: list[dict] = []
            try:
                retry_cand, _strat, retry_reasons = retry_row_strategies(
                    row, translator, whitelist, batch_raw=raw, fast=False,
                    user_glossary=user_glossary, full_raw=full_by_key.get(row["key"], ""),
                    trace=retry_trace,
                )
            except Exception as exc:
                # Keep quality failures row-scoped.  The original translation
                # remains empty and the review ledger records the cause.
                retry_cand = None
                retry_reasons = [f"retry adapter error: {exc}"]
                retry_trace.append(
                    {
                        "attempt_id": str(uuid.uuid4()),
                        "strategy": "retry_adapter_error",
                        "raw_output": str(raw or ""),
                        "raw_output_hash": hashlib.sha256(
                            str(raw or "").encode("utf-8", "surrogatepass")
                        ).hexdigest()
                        if raw
                        else "",
                        "candidate": "",
                        "candidate_hash": "",
                        "validation_reasons": list(retry_reasons),
                        "passed": False,
                    }
                )
            retry_attempts_by_key[row["key"]] = retry_trace
            if retry_cand:
                _cache_validated_candidate(
                    cache,
                    row,
                    retry_cand,
                    cache_context,
                    cache_fingerprints=cache_fingerprints,
                )
                if _should_human_review(row, human_review_required):
                    queue_human_review(
                        row,
                        retry_cand,
                        raw_output=full_by_key.get(row["key"], "") or raw,
                        attempts=retry_trace,
                        full_raw=full_by_key.get(row["key"], ""),
                    )
                else:
                    translations[row["key"]] = retry_cand
            else:
                row["translation"] = ""
                note = "; ".join((retry_reasons or reasons)[:3]) if (retry_reasons or reasons) else "validation failed"
                review_sink.add(row, raw, [f"{RETRANSLATE_STILL_BLOCKED_NOTE}: {note}"])
                blocked += 1

        chunk_applied, chunk_blocked, review_triples = _apply_mapping_memory(
            by_key,
            translations,
            allow_overwrite=allow_overwrite,
            whitelist=whitelist,
        )
        applied += chunk_applied
        blocked += chunk_blocked
        for row, attempted, reasons in review_triples:
            row["translation"] = ""
            review_sink.add(row, attempted, reasons)

        pending_flush += chunk_applied
        if pending_flush >= flush_every:
            _flush_csv_atomic(csv_path, fields, rows)
            review_sink.flush(package_dir)
            pending_flush = 0

        prog(
            done=min(start + len(chunk), len(mt_targets)),
            total=total,
            step="Đang dịch lại dòng lỗi",
            item=f"{min(start + len(chunk), len(mt_targets))}/{total}",
        )

    _flush_csv_atomic(csv_path, fields, rows)
    review_sink.flush(package_dir)
    if blocker_records:
        _merge_blocker_inventory(package_dir, blocker_records)
    human_review_count = _count_human_review_rows(package_dir)
    summary = f"Dịch lại: applied={applied}, blocked={blocked}, tổng {len(mt_targets)} dòng gửi CT2"
    if human_review_count:
        summary += f". Cần duyệt thủ công {human_review_count} dòng trước khi Patch"
        emit(f"Cần duyệt thủ công {human_review_count} dòng trước khi Patch")
    emit(summary)
    result = {
        "ok": applied > 0 and human_review_count == 0,
        "applied": applied,
        "blocked": blocked,
        "summary": summary,
        "total": len(mt_targets),
        "error": (
            f"Cần duyệt thủ công {human_review_count} dòng trước khi Patch"
            if human_review_count
            else ("" if applied > 0 else "Dịch lại vẫn bị chặn — không dòng nào vượt Patch Gate")
        ),
        "pipeline_liveness": True,
        "human_review_required_count": human_review_count,
    }
    from vntext.mt_ct2_status import snapshot_translate_status

    status = snapshot_translate_status(package_dir, csv_path)
    result.update(
        {
            "complete": bool(status.get("complete")),
            "pending": int(status.get("pending") or 0),
            "review_only": int(status.get("review_only") or 0),
        }
    )
    if cache is not None:
        result["cache"] = cache.summary()
        cache.close()
    else:
        result["cache"] = {
            "kind": "validated_translation_cache",
            "status": "disabled",
            "error": cache_error,
            "hits": 0,
            "misses": 0,
        }
    result["cache_fingerprints"] = cache_fingerprints
    result["retry_attempts_by_key"] = retry_attempts_by_key
    return result


def _route_to_review(
    package_dir: Path,
    row: dict,
    attempted: str,
    reasons: list[str],
    emit: Callable[[str], None],
) -> int:
    """Legacy single-row review helper (tests / callers outside run_ct2_translate)."""
    from vntext.mt_ct2_io import _ReviewSink
    sink = _ReviewSink(emit, max_log=1)
    sink.add(row, attempted, reasons)
    return sink.flush(package_dir)

__all__ = [
    'run_ct2_translate',
    'run_ct2_translate_keys',
    '_route_to_review',
    '_row_uses_user_glossary',
    '_select_ct2_targets',
]
