"""Status responsibilities split from mt_ct2."""

from __future__ import annotations

from vntext.mt_ct2_constants import (
    CSV_FIELDS,
    Path,
    apply_batch,
    candidate_quality_issues,
    classify_row_authoritative,
    classify_source_row,
    csv,
    json,
    postprocess,
    read_csv_rows_file,
    reason_label_vi,
    translation_passes_patch_gate,
    validate_candidate,
    write_csv_rows_file,
)


class TranslateStatusError(RuntimeError):
    """Raised when persisted package status cannot be measured safely.

    A status file is an operation-level ledger.  Treating a corrupt or
    unreadable ledger as ``blocked=0`` would make a package appear complete
    even though its unresolved state is unknown, so callers must surface this
    error and keep completion fail-closed.
    """


def _strict_count(value: object, field: str, *, source: str) -> int:
    """Validate a persisted/caller count without lossy normalization."""

    if isinstance(value, bool) or not isinstance(value, int):
        raise TranslateStatusError(
            f"Trạng thái package {source} có {field} không hợp lệ: phải là số nguyên"
        )
    if value < 0:
        raise TranslateStatusError(
            f"Trạng thái package {source} có {field} âm: {value}"
        )
    return value


def _validate_status_counts(status: object, *, source: str) -> dict:
    """Validate measured status data before it can affect completion."""

    if not isinstance(status, dict):
        raise TranslateStatusError(
            f"Trạng thái package {source} phải là JSON object"
        )
    validated = dict(status)
    for field in ("pending", "review_only", "blocked"):
        if field not in validated:
            raise TranslateStatusError(
                f"Trạng thái package {source} thiếu trường {field}"
            )
        validated[field] = _strict_count(validated[field], field, source=source)
    if "complete" in validated and not isinstance(validated["complete"], bool):
        raise TranslateStatusError(
            f"Trạng thái package {source} có complete không hợp lệ: phải là boolean"
        )
    return validated



def _safe_candidate(
    row: dict,
    raw: str,
    whitelist: set[str],
    *,
    quality: bool = False,
    preserve_candidate: bool = False,
) -> tuple[str | None, list[str]]:
    # Package glossary/memory entries are already authoritative translations.
    # Re-running the generic lexical repair pass here can silently rewrite a
    # deliberate wording such as ``Bắt đầu game``.
    candidate = str(raw or "") if preserve_candidate else postprocess(row["source_text"], raw)
    reasons = validate_candidate(row, candidate, whitelist)
    if not reasons:
        gate_ok, gate_reason = translation_passes_patch_gate(row, candidate, whitelist)
        if gate_ok:
            if quality:
                quality_reasons = candidate_quality_issues(row, candidate, whitelist)
                if quality_reasons:
                    return None, quality_reasons
            return candidate, []
        return None, [f"Patch Gate: {reason_label_vi(gate_reason)}"]
    fixed = candidate if preserve_candidate else postprocess(row["source_text"], candidate)
    reasons2 = validate_candidate(row, fixed, whitelist)
    if not reasons2:
        gate_ok, gate_reason = translation_passes_patch_gate(row, fixed, whitelist)
        if gate_ok:
            if quality:
                quality_reasons = candidate_quality_issues(row, fixed, whitelist)
                if quality_reasons:
                    return None, quality_reasons
            return fixed, reasons
        return None, [f"Patch Gate: {reason_label_vi(gate_reason)}"]
    return None, reasons2


def _load_human_review_keys(package_dir: Path) -> set[str]:
    """Return keys whose persisted review provenance requires human promotion."""
    review_path = package_dir / "review_only.csv"
    if not review_path.is_file():
        return set()
    _fields, review_rows = read_csv_rows_file(review_path)
    review_keys = {
        str(row.get("key") or "")
        for row in review_rows
        if str(row.get("key") or "")
    }
    human_keys = {
        str(row.get("key") or "")
        for row in review_rows
        if str(row.get("key") or "")
        and "HUMAN_REVIEW_REQUIRED" in str(row.get("patch_note") or "")
    }
    inventory_path = package_dir / ".mt" / "blocker_inventory.json"
    if inventory_path.is_file():
        try:
            inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
        except (OSError, TypeError, ValueError):
            inventory = {}
        human_keys.update(
            str(row.get("key") or "")
            for row in inventory.get("rows") or []
            if isinstance(row, dict)
            and str(row.get("key") or "") in review_keys
            and row.get("route") == "human_review_required"
        )
    return human_keys


def _prune_resolved_review_only(
    package_dir: Path,
    rows: list[dict],
    emit: Callable[[str], None] | None = None,
    *,
    protected_review_keys: set[str] | None = None,
    allow_human_review_resolution: bool = False,
    allow_ct2_junk: bool = False,
) -> int:
    """Drop translated rows and rows reclassified as intentionally technical.

    A previous classifier can have recorded a runtime token in review_only.csv.
    Once the classifier knows that token is technical, leaving it there makes a
    rerun report a false unresolved review item forever. Technical rows are
    removed only when the current source row is explicitly classified as
    ``skip_technical``; player-visible rows still require a real translation.
    """
    review_path = package_dir / "review_only.csv"
    if not review_path.is_file():
        return 0
    fields, existing = read_csv_rows_file(review_path)
    if not existing:
        return 0
    from vntext import mt_check

    whitelist = mt_check.load_whitelist(package_dir)
    protected = (
        {str(key) for key in protected_review_keys if str(key)}
        if protected_review_keys is not None
        else _load_human_review_keys(package_dir)
    )
    translated_keys = {
        str(r.get("key") or "")
        for r in rows
        if str(r.get("key") or "")
        and str(r.get("translation") or "").strip()
        and (allow_human_review_resolution or str(r.get("key") or "") not in protected)
        and translation_passes_patch_gate(
            r,
            str(r.get("translation") or ""),
            whitelist,
            allow_ct2_junk=allow_ct2_junk,
        )[0]
    }
    technical_keys = {
        str(r.get("key") or "")
        for r in rows
        if str(r.get("key") or "")
        and str(r.get("key") or "") not in protected
        and classify_row_authoritative(r)[0] == "skip_technical"
    }
    resolved_keys = translated_keys | technical_keys
    kept = [r for r in existing if str(r.get("key") or "") not in resolved_keys]
    removed = len(existing) - len(kept)
    if removed:
        write_csv_rows_file(review_path, fields or CSV_FIELDS, kept)
        if emit:
            emit(f"review_only: gỡ {removed} key đã dịch hoặc được xác định là technical")
    return removed


def _quarantine_technical_rows(
    package_dir: Path,
    fields: list[str],
    rows: list[dict],
    emit: Callable[[str], None] | None = None,
    *,
    protected_review_keys: set[str] | None = None,
) -> tuple[list[dict], int]:
    """Remove newly-recognised technical rows from an old translation.csv.

    Extraction already writes these rows to technical_skipped.csv.  This second
    guard is needed for packages created by an older classifier: an existing
    translation must not make a runtime token look like completed player copy.
    The original source and reason remain in the technical ledger and manifest.
    """
    protected = {str(key) for key in protected_review_keys or set() if str(key)}
    technical: list[tuple[dict, str]] = []
    kept: list[dict] = []
    for row in rows:
        if str(row.get("key") or "") in protected:
            kept.append(row)
            continue
        action, reason = classify_source_row(row)
        if action == "skip_technical":
            technical.append((row, reason))
        else:
            kept.append(row)
    if not technical:
        return rows, 0

    technical_path = package_dir / "technical_skipped.csv"
    tech_fields, existing_rows = (
        read_csv_rows_file(technical_path)
        if technical_path.is_file()
        else (fields[:], [])
    )
    by_key = {str(row.get("key") or ""): dict(row) for row in existing_rows if row.get("key")}
    for row, reason in technical:
        item = {**row}
        item["patch_note"] = f"skip_technical: {reason}"
        by_key[str(row.get("key") or "")] = item
    write_csv_rows_file(technical_path, tech_fields or fields or CSV_FIELDS, list(by_key.values()))

    technical_keys = set(by_key)
    review_path = package_dir / "review_only.csv"
    if review_path.is_file():
        review_fields, review_rows = read_csv_rows_file(review_path)
        filtered = [
            row for row in review_rows if str(row.get("key") or "") not in technical_keys
        ]
        if len(filtered) != len(review_rows):
            write_csv_rows_file(review_path, review_fields or fields or CSV_FIELDS, filtered)

    manifest_path = package_dir / "manifest.json"
    if manifest_path.is_file():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
        manifest_entries = manifest.get("entries") or []
        entry_by_key = {
            str(entry.get("key") or ""): dict(entry)
            for entry in manifest_entries
            if entry.get("key")
        }
        for row, reason in technical:
            item = entry_by_key.get(str(row.get("key") or ""), {
                "key": row.get("key", ""),
                "source_text": row.get("source_text", ""),
                "file_path": row.get("file_path", ""),
                "context": row.get("context", ""),
                "object_info": row.get("object_info", ""),
                "import_method": row.get("import_method", ""),
                "safety": row.get("safety", ""),
                "locator": {},
                "backend": row.get("backend", ""),
                "review_only": False,
                "duplicate_locations": [],
            })
            item["reason"] = reason
            entry_by_key.pop(str(row.get("key") or ""), None)
            existing_ledger = manifest.setdefault("technical_skipped", [])
            existing_ledger[:] = [
                old for old in existing_ledger
                if str(old.get("key") or "") != str(row.get("key") or "")
            ]
            existing_ledger.append(item)
        manifest["entries"] = list(entry_by_key.values())
        manifest.setdefault("stats", {})["technical_skipped_entries"] = len(
            manifest.get("technical_skipped") or []
        )
        manifest["stats"]["translation_csv_entries"] = len(kept)
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    if emit:
        emit(f"Technical filter: chuyển {len(technical)} dòng cũ sang technical_skipped.csv")
    return kept, len(technical)


def _append_review_rows(package_dir: Path, rows: list[dict]) -> int:
    review_path = package_dir / "review_only.csv"
    fields, existing = read_csv_rows_file(review_path) if review_path.is_file() else (CSV_FIELDS[:], [])
    by_key = {r["key"]: r for r in existing}
    for row in rows:
        by_key[row["key"]] = {**row}
    merged = list(by_key.values())
    write_csv_rows_file(review_path, fields or CSV_FIELDS, merged)
    return len(rows)


def _apply_mapping(
    csv_path: Path,
    mapping: dict[str, str],
    *,
    allow_overwrite: bool,
    emit: Callable[[str], None],
) -> tuple[int, int]:
    if not mapping:
        return 0, 0
    result = apply_batch(csv_path, mapping, allow_overwrite=allow_overwrite)
    if result.ok:
        return result.applied, 0
    applied = 0
    blocked = 0
    for key, translated in mapping.items():
        one = apply_batch(csv_path, {key: translated}, allow_overwrite=allow_overwrite)
        if one.ok:
            applied += 1
        else:
            blocked += 1
            emit(f"Bỏ qua {key}: {one.message}")
    return applied, blocked


def _count_pending(rows: list[dict]) -> dict[str, int]:
    counts = {
        "translate": 0,
        "translate_synonym": 0,
        "copy_source": 0,
        "skip_technical": 0,
        "done": 0,
        "review_only": 0,
        "unsupported": 0,
    }
    for row in rows:
        action, _reason, _decision = classify_row_authoritative(row)
        counts[action] = counts.get(action, 0) + 1
    return counts


def _clear_known_bad_translations(
    rows: list[dict],
    whitelist: set[str],
    emit: Callable[[str], None] | None = None,
) -> int:
    """Clear gate/quality-proven output so it can be retried safely.

    A row with any non-empty translation is classified as ``done``.  That
    means a previous CT2 failure could otherwise permanently hide malformed
    output from later runs.  Do not clear ordinary validation warnings or
    user-edited text: only hard garbage, structural failures, or a measured
    residual-English/content-quality failure are eligible.  Clearing a bad
    proposal is tightening the route; the same candidate still has to pass
    the normal structural, Patch Gate and quality checks before it is written.
    """
    from vntext.patch_gate import patch_skip_reason
    from vntext.mt_strategies import candidate_quality_issues

    cleared = 0
    hard_prefixes = (
        "garbage_repetition",
        "html_garbage",
        "placeholder mismatch",
        "tag mismatch",
        "literal newline count",
        "heart glyph count",
        "RandPick variant count",
        "english suffix after placeholder",
    )
    for row in rows:
        translation = str(row.get("translation") or "").strip()
        if not translation:
            continue
        reason = patch_skip_reason(row, translation, whitelist)
        quality_bad = bool(candidate_quality_issues(row, translation, whitelist))
        if not ((reason and reason.startswith(hard_prefixes)) or quality_bad):
            continue
        # Production/UI glossary values are frozen before CT2 runs.  When a
        # previous pass left an English token in one of those values, clear-
        # and-recopy would route it back to the same glossary proposal forever
        # (``ui_label_fixed`` is not a CT2 target).  First run the normal
        # source-token repair and keep it only when every existing gate still
        # passes; this is a repair of a measured bad candidate, not a gate
        # bypass or a source/key-specific translation.
        fixed = postprocess(str(row.get("source_text") or ""), translation)
        fixed_reasons = validate_candidate(row, fixed, whitelist)
        if not fixed_reasons:
            fixed_gate_ok, _fixed_gate_reason = translation_passes_patch_gate(
                row, fixed, whitelist
            )
            fixed_quality = candidate_quality_issues(row, fixed, whitelist)
            if fixed_gate_ok and not fixed_quality:
                if fixed != translation:
                    row["translation"] = fixed
                    cleared += 1
                continue

        source_action, _source_reason = classify_source_row(row)
        if source_action not in {"translate", "translate_synonym", "ui_label_fixed"}:
            # Explicit literal/technical keeps are outside this retry route.
            continue
        row["translation"] = ""
        # A deterministic UI glossary proposal that failed quality must be
        # sent to CT2 instead of being copied back by the pre-translation
        # mapping pass.  This marker is in-memory only; CSV fields remain
        # unchanged and all normal gates still apply to the CT2 candidate.
        row["_ct2_force"] = True
        cleared += 1
    if cleared and emit:
        emit(f"Đã xóa {cleared} bản dịch lỗi cứng để dịch lại an toàn")
    return cleared


def reconcile_mirror_translations(
    rows: list[dict],
    whitelist: set[str],
    *,
    eligible_keys: set[str] | None = None,
) -> int:
    """Use one validated candidate for matching embedded/external copies.

    Unity TextAssets and their exported ``.txt`` counterpart can contain the
    same source line.  CT2 is stochastic, so translating both independently
    creates a mirror mismatch even when both candidates pass the individual
    gates.  Reconcile only rows produced during this invocation (all keys in
    a group must be eligible); pre-existing/user translations remain frozen.
    The selected value must pass structural, Patch Gate and quality checks for
    every row in the group.
    """
    from collections import Counter, defaultdict

    forced = eligible_keys if eligible_keys is not None else {
        str(row.get("key") or "") for row in rows
    }
    groups: dict[tuple[str, str], dict[str, list[dict]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for row in rows:
        ctx = str(row.get("context") or "")
        fp = str(row.get("file_path") or "")
        base: str | None = None
        if ctx.startswith("TextAsset:"):
            base = ctx.split(":", 1)[1].split(":")[0]
            side = "embedded"
        elif fp.lower().endswith(".txt"):
            base = Path(fp).stem
            side = "external"
        else:
            continue
        key = str(row.get("key") or "")
        if base and key in forced and str(row.get("translation") or "").strip():
            groups[(base, str(row.get("source_text") or ""))][side].append(row)

    changed = 0
    for sides in groups.values():
        if "embedded" not in sides or "external" not in sides:
            continue
        group_rows = sides["embedded"] + sides["external"]
        values = [str(row.get("translation") or "").strip() for row in group_rows]
        counts = Counter(values)
        if len(counts) <= 1:
            continue
        # Prefer the most common candidate; tie-break lexically so the result
        # is deterministic across batch ordering and worker restarts.
        candidates = sorted(counts, key=lambda value: (-counts[value], value.casefold(), value))
        selected: str | None = None
        for candidate in candidates:
            valid = True
            for row in group_rows:
                if validate_candidate(row, candidate, whitelist):
                    valid = False
                    break
                gate_ok, _gate_reason = translation_passes_patch_gate(
                    row, candidate, whitelist
                )
                if not gate_ok or candidate_quality_issues(row, candidate, whitelist):
                    valid = False
                    break
            if valid:
                selected = candidate
                break
        if selected is None:
            continue
        for row in group_rows:
            if str(row.get("translation") or "").strip() != selected:
                row["translation"] = selected
                changed += 1
    return changed


def _count_review_only_rows(package_dir: Path) -> int:
    review_path = package_dir / "review_only.csv"
    if not review_path.is_file():
        return 0
    with review_path.open(encoding="utf-8-sig", newline="") as fh:
        return sum(1 for _ in csv.DictReader(fh))


def _build_translate_result(
    package_dir: Path,
    rows: list[dict],
    *,
    applied: int,
    copied_vi: int,
    skipped_technical: int,
    blocked: int,
    summary: str,
    pipeline_liveness: bool = False,
) -> dict:
    translated_count = sum(1 for r in rows if str(r.get("translation") or "").strip())
    pending_counts = _count_pending(rows)
    # Synonym pools are still player-visible translation work.  They have a
    # separate classifier action because their comma/variant structure needs
    # a dedicated strategy, but an unresolved synonym must not disappear from
    # the strict completion gate.
    pending = sum(
        pending_counts.get(action, 0)
        for action in ("translate", "translate_synonym", "review_only", "unsupported")
    )
    review_total = _count_review_only_rows(package_dir)
    # ``blocked`` is the final unresolved-row count.  It must participate in
    # completion even when a backend happened to leave a non-empty
    # translation behind. Transient batch failures are not included here;
    # callers retry the affected rows and only final review/apply failures are
    # counted.
    blocked = _strict_count(blocked, "blocked", source="translation result")
    complete = pending == 0 and review_total == 0 and blocked == 0
    # ok = đã có tiến độ dịch thật (applied/copy) hoặc hoàn tất — không dùng CT2 chạy xong.
    ok = complete or applied > 0 or copied_vi > 0
    if pending > 0 and applied == 0 and copied_vi == 0:
        ok = False
    return {
        "ok": ok,
        "translated": translated_count,
        "applied": applied,
        "copied_vi": copied_vi,
        "skipped_technical": skipped_technical,
        "blocked": blocked,
        "review_only": review_total,
        "pending": pending,
        "classifier_review": pending_counts.get("review_only", 0),
        "classifier_unsupported": pending_counts.get("unsupported", 0),
        "total": len(rows),
        "summary": summary,
        "complete": complete,
        "pipeline_liveness": bool(pipeline_liveness),
    }


def _snapshot_translate_status_canonical(package_dir: Path, csv_path: Path | None = None) -> dict:
    from vntext.mt_ct2_io import _load_csv
    csv_path = Path(csv_path) if csv_path else package_dir / "translation.csv"
    _fields, rows = _load_csv(csv_path)
    pending_counts = _count_pending(rows)
    pending = sum(
        pending_counts.get(action, 0)
        for action in ("translate", "translate_synonym", "review_only", "unsupported")
    )
    review_total = _count_review_only_rows(package_dir)
    translated_count = sum(1 for r in rows if str(r.get("translation") or "").strip())
    # Blocked is an operation-level count, so retain the last persisted value
    # until the next status write explicitly clears it.  This prevents a
    # read-only status refresh from turning a failed apply into completion.
    blocked = 0
    status_path = package_dir / ".mt" / "translate_status.json"
    try:
        status_info = status_path.stat()
    except FileNotFoundError:
        status_info = None
    except OSError as exc:
        raise TranslateStatusError(
            f"Không đọc được trạng thái package {status_path}: {exc}"
        ) from exc
    if status_info is not None:
        if not status_path.is_file():
            raise TranslateStatusError(
                f"Trạng thái package {status_path} không phải file thường"
            )
        try:
            persisted = json.loads(status_path.read_text(encoding="utf-8"))
        except (OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise TranslateStatusError(
                f"Không đọc được trạng thái package {status_path}: {exc}"
            ) from exc
        persisted = _validate_status_counts(persisted, source=str(status_path))
        blocked = persisted["blocked"]
    complete = pending == 0 and review_total == 0 and blocked == 0
    return {
        "complete": complete,
        "pending": pending,
        "review_only": review_total,
        "blocked": blocked,
        "translated": translated_count,
    }


def snapshot_translate_status(package_dir: Path, csv_path: Path | None = None) -> dict:
    """Read canonical package status for callers and status diagnostics."""

    return _snapshot_translate_status_canonical(package_dir, csv_path)


def write_translate_status(
    package_dir: Path,
    csv_path: Path | None = None,
    *,
    measured_status: dict | None = None,
    package_wide_verified: bool = False,
    **extra,
) -> dict:
    # Always measure the canonical package state.  ``measured_status`` is an
    # optional diagnostic from an earlier read; it is authenticated against
    # the fresh snapshot and can never replace it with optimistic counts.
    canonical = _snapshot_translate_status_canonical(package_dir, csv_path)
    if measured_status is not None:
        candidate = _validate_status_counts(measured_status, source="caller measured_status")
        if any(candidate[field] != canonical[field] for field in ("pending", "review_only", "blocked")):
            raise TranslateStatusError(
                "measured_status không khớp trạng thái package canonical hiện tại"
            )
    status = dict(canonical)
    persisted_blocked = canonical["blocked"]
    if not isinstance(package_wide_verified, bool):
        raise TranslateStatusError("package_wide_verified phải là boolean")
    for key, value in extra.items():
        if key in {"pending", "review_only", "blocked"}:
            if value is None:
                raise TranslateStatusError(
                    f"Trạng thái package caller thiếu trường {key}"
                )
            _strict_count(value, key, source="caller")
        if key == "complete" and value is not None and not isinstance(value, bool):
            raise TranslateStatusError(
                "Trạng thái package caller có complete không hợp lệ: phải là boolean"
            )
        # Pending/review/complete are derived from canonical state, never
        # caller-provided scope values.  ``blocked`` is handled below so a
        # previous operation-level failure cannot be erased accidentally.
        if key in {"pending", "review_only", "blocked", "complete"}:
            continue
        if value is not None:
            status[key] = value
    requested_blocked = persisted_blocked
    if "blocked" in extra:
        requested_blocked = _strict_count(extra["blocked"], "blocked", source="caller")
    # A retry result is scoped to its selected keys.  Preserve persisted
    # blocked evidence unless an explicit package-wide verification proves the
    # package has no pending/review rows and the caller requests a clear.
    if not package_wide_verified or status["pending"] or status["review_only"]:
        status["blocked"] = max(persisted_blocked, requested_blocked)
    else:
        status["blocked"] = requested_blocked
    # Completion is derived from the freshly measured counts.  Preserving a
    # stale ``complete=false`` would make a previously blocked package stay
    # incomplete forever after a successful retry; trusting ``complete=true``
    # would have the opposite (unsafe) effect when counts are non-zero.
    status["complete"] = not any(
        status[name] for name in ("pending", "review_only", "blocked")
    )
    path = package_dir / ".mt" / "translate_status.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(status, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return status

__all__ = ['TranslateStatusError', '_safe_candidate', '_prune_resolved_review_only', '_quarantine_technical_rows', '_append_review_rows', '_apply_mapping', '_count_pending', '_clear_known_bad_translations', '_count_review_only_rows', '_build_translate_result', 'snapshot_translate_status', 'write_translate_status']
