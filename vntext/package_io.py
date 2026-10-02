from __future__ import annotations

import csv
import json
import shutil
from datetime import datetime
from pathlib import Path

from vntext.entry import Entry

CSV_FIELDS = [
    "key",
    "source_text",
    "translation",
    "context",
    "file_path",
    "object_info",
    "import_method",
    "safety",
    "backend",
    "byte_limit",
    "patch_note",
]


def write_csv(path: Path, entries):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for entry in entries:
            writer.writerow(entry.to_csv_row())



def read_csv_rows_file(path: Path) -> tuple[list[str], list[dict]]:
    """Doc CSV, giu nguyen cot goc neu co."""
    if not path.exists():
        return CSV_FIELDS[:], []
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        fields = list(reader.fieldnames or CSV_FIELDS)
        rows = [dict(row) for row in reader]
    # App can cac cot toi thieu nay; khong doi ten cot, chi bo sung neu file bi thieu cot.
    for field in CSV_FIELDS:
        if field not in fields:
            fields.append(field)
    for row in rows:
        for field in fields:
            row.setdefault(field, "")
    return fields, rows


def write_csv_rows_file(path: Path, fields: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    ordered = list(fields or CSV_FIELDS)
    for field in CSV_FIELDS:
        if field not in ordered:
            ordered.append(field)
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=ordered, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in ordered})


def backup_translation_csv(csv_path: str | Path) -> Path:
    """Sao lưu translation.csv trước thao tác ghi hàng loạt."""
    csv_path = Path(csv_path).resolve()
    if not csv_path.is_file():
        raise FileNotFoundError(str(csv_path))
    # Include microseconds: two quick editor operations must never overwrite
    # one another's rollback point.
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    dest_dir = csv_path.parent / ".csv_editor_backups"
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"translation.{stamp}.csv.bak"
    shutil.copy2(csv_path, dest)
    return dest


def resolve_translation_package_dir(path_text: str | Path) -> Path:
    """Cho phep nguoi dung tro vao thu muc package hoac chon nham file CSV."""
    path = Path(str(path_text).strip().strip('"'))
    if path.is_file() and path.suffix.lower() == ".csv":
        return path.parent
    return path



RAW_EXTRACT_ONLY_METHODS = {"raw_fixed_slot", "naninovel_blob_string", "naninovel_raw_candidate", "raw_review_only"}


def is_direct_asset_patchable(entry: Entry) -> bool:
    """True neu dong co the patch tu do bang object/text asset, khong gioi han byte slot.

    v1.34 deliberately keeps raw byte-slot findings out of translation.csv. They are
    useful for debugging missing UI, but not acceptable for the normal user workflow
    because they force short translations and silently skip longer Vietnamese.
    """
    method = getattr(entry, "import_method", "")
    if method in RAW_EXTRACT_ONLY_METHODS:
        return False
    if getattr(entry, "review_only", False):
        return False
    return method in {
        "plain_text_line",
        "unity_textasset_line",
        "unity_textasset_table_cell",
        "unity_textasset_script",
        "unity_typetree_field",
        "unity_ui_text",
        "unity_localization_string",
        "naninovel_script_string",
        "naninovel_choice",
        "naninovel_print",
        "structured_json_value",
        "structured_csv_cell",
        "structured_xml_value",
        "structured_sqlite_value",
        "renpy_dialogue",
        "renpy_string",
    }


def split_asset_patchable_entries(main_entries, review_entries):
    patchable = []
    raw_unpatchable = []
    review_out = []

    for entry in main_entries:
        if is_direct_asset_patchable(entry):
            patchable.append(entry)
        else:
            entry.review_only = True
            if entry.import_method in RAW_EXTRACT_ONLY_METHODS:
                raw_unpatchable.append(entry)
            else:
                review_out.append(entry)

    for entry in review_entries:
        entry.review_only = True
        if entry.import_method in RAW_EXTRACT_ONLY_METHODS:
            raw_unpatchable.append(entry)
        else:
            review_out.append(entry)
    return patchable, raw_unpatchable, review_out

def _write_package_legacy(
    output_dir: str,
    main_entries,
    review_entries,
    stats,
    separate_review: bool = False,
    enforce_symmetry: bool = False,
):
    from vntext.app_backend import VERSION, auto_candidate_action, cleanup_package_zip_files, format_duration
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    if enforce_symmetry:
        from vntext.patchability import enforce_main_flow, is_technical_skip_entry

        # This is opt-in to preserve the manifest/CSV behavior of legacy
        # callers. New generic extractors must opt in before promoting rows to
        # the main translation flow; raw/review ledgers remain separate.
        enforce_main_flow(
            [entry for entry in main_entries if not is_technical_skip_entry(entry)],
            require_proof=True,
        )

    # v1.34: normal user workflow must not ask for byte-limited translations.
    # Only direct asset/object/text-file entries go into translation.csv.
    # Raw findings remain available for debugging, but are not part of the main patch flow.
    asset_patchable_entries, raw_unpatchable_entries, other_review_entries = split_asset_patchable_entries(main_entries, review_entries)
    main_entries = asset_patchable_entries
    review_entries = other_review_entries

    # Technical strings are useful audit evidence but are not player-visible
    # copy.  Keeping them in translation.csv made the editor report hundreds
    # of apparent "missing translations" and invited accidental MT changes.
    # Classify after the asset split so only the normal extract output is
    # affected; raw/debug findings keep their existing dedicated files.
    from vntext.mt_classify import classify_row_authoritative

    technical_skipped: list[tuple[Entry, str]] = []
    nontechnical_main: list[Entry] = []
    nontechnical_review: list[Entry] = []
    seen_technical: set[str] = set()
    main_ids = {id(entry) for entry in main_entries}
    for entry in list(main_entries) + list(review_entries):
        classifier_row = entry.to_csv_row()
        classifier_row.update(
            {
                # SQLite inventory rows are extractor-owned candidates: a
                # technical key must still reach technical_skipped.csv even
                # though the scanner marks every non-writer row review_only.
                # Explicit review metadata for every other route remains
                # authoritative and fail-closed.
                "review_only": entry.review_only and entry.import_method != "sqlite_text_candidate",
                "locator": entry.locator,
                "patch_proof": entry.patch_proof,
            }
        )
        action, reason, _decision = classify_row_authoritative(classifier_row)
        if action == "skip_technical":
            if entry.key not in seen_technical:
                technical_skipped.append((entry, reason))
                seen_technical.add(entry.key)
            continue
        if id(entry) in main_ids:
            nontechnical_main.append(entry)
        else:
            nontechnical_review.append(entry)
    main_entries = nontechnical_main
    review_entries = nontechnical_review

    technical_path = out / "technical_skipped.csv"
    if technical_skipped:
        rows = []
        for entry, reason in technical_skipped:
            row = entry.to_csv_row()
            row["patch_note"] = f"skip_technical: {reason}"
            rows.append(row)
        write_csv_rows_file(technical_path, CSV_FIELDS, rows)
    elif technical_path.exists():
        technical_path.unlink()

    raw_candidate_entries = [entry for entry in review_entries if entry.import_method == "naninovel_raw_candidate"]
    real_review_entries = [entry for entry in review_entries if entry.import_method != "naninovel_raw_candidate"]

    auto_promoted_entries = []
    auto_kept_raw_entries = []
    auto_rejected_entries = []
    if separate_review and raw_candidate_entries:
        existing_main_keys = {entry.key for entry in main_entries}
        for entry in raw_candidate_entries:
            if enforce_symmetry:
                # Strict extraction has already classified this row as lacking
                # a complete reader/locator/writer proof.  The legacy
                # auto-promote heuristic is intentionally unavailable here;
                # otherwise a review row could silently re-enter MAIN.
                auto_kept_raw_entries.append(entry)
                continue
            action = auto_candidate_action(entry.source_text)
            if action == "promote" and entry.key not in existing_main_keys:
                entry.review_only = False
                entry.safety = "unsafe_candidate"
                auto_promoted_entries.append(entry)
                existing_main_keys.add(entry.key)
            elif action == "reject":
                auto_rejected_entries.append(entry)
            else:
                auto_kept_raw_entries.append(entry)
        raw_candidate_entries = auto_kept_raw_entries
        main_entries = list(main_entries) + auto_promoted_entries

    if separate_review:
        write_csv(out / "translation.csv", main_entries)
        if raw_candidate_entries:
            write_csv(out / "raw_candidates.csv", raw_candidate_entries)
        elif (out / "raw_candidates.csv").exists():
            (out / "raw_candidates.csv").unlink()
        write_csv(out / "review_only.csv", real_review_entries)
        if raw_unpatchable_entries:
            write_csv(out / "raw_unpatchable.csv", raw_unpatchable_entries)
        elif (out / "raw_unpatchable.csv").exists():
            (out / "raw_unpatchable.csv").unlink()
        if auto_rejected_entries:
            write_csv(out / "raw_candidates_rejected.csv", auto_rejected_entries)
        elif (out / "raw_candidates_rejected.csv").exists():
            (out / "raw_candidates_rejected.csv").unlink()
        manifest_entries = list(main_entries) + list(raw_candidate_entries) + list(real_review_entries) + list(raw_unpatchable_entries) + list(auto_rejected_entries)
    else:
        all_entries = list(main_entries) + list(review_entries)
        write_csv(out / "translation.csv", all_entries)
        if raw_unpatchable_entries:
            write_csv(out / "raw_unpatchable.csv", raw_unpatchable_entries)
        for extra_name in ("review_only.csv", "raw_candidates.csv", "raw_candidates_rejected.csv"):
            if (out / extra_name).exists():
                (out / extra_name).unlink()
        manifest_entries = all_entries + list(raw_unpatchable_entries)

    stats = dict(stats)
    stats["technical_skipped_entries"] = len(technical_skipped)
    stats["translation_csv_entries"] = len(main_entries) if separate_review else len(main_entries) + len(review_entries)
    stats["auto_raw_promoted"] = len(auto_promoted_entries)
    stats["auto_raw_rejected"] = len(auto_rejected_entries)
    stats["raw_candidate_entries"] = len(raw_candidate_entries)
    stats["raw_unpatchable_entries"] = len(raw_unpatchable_entries)
    stats["review_only_entries"] = len(real_review_entries)
    manifest = {
        "format": 2,
        "tool": "VNText Studio Core",
        "version": VERSION,
        "entries": [entry.to_manifest() for entry in manifest_entries],
        "technical_skipped": [
            {**entry.to_manifest(), "reason": reason}
            for entry, reason in technical_skipped
        ],
        "stats": stats,
    }
    (out / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), "utf-8")
    report = [
        "VNText Studio extract report",
        f"version: {VERSION}",
        f"mode: {stats.get('mode')}",
        f"extract_level: {stats.get('extract_level', 'balanced')}",
        f"files_scanned: {stats.get('files_scanned')}",
        f"main_entries: {stats.get('main_entries')}",
        f"review_entries: {stats.get('review_entries')}",
        f"translation_csv_entries: {stats['translation_csv_entries']}",
        f"technical_skipped_entries: {len(technical_skipped)}",
        f"raw_candidate_entries: {stats.get('raw_candidate_entries', 0)}",
        f"raw_unpatchable_entries: {stats.get('raw_unpatchable_entries', 0)}",
        f"review_only_entries: {stats.get('review_only_entries', stats.get('review_entries', 0))}",
        f"auto_raw_promoted: {stats.get('auto_raw_promoted', 0)}",
        f"auto_raw_rejected: {stats.get('auto_raw_rejected', 0)}",
        f"skipped_deep_files: {stats.get('skipped_deep_files', 0)}",
        f"skipped_raw_files: {stats.get('skipped_raw_files', 0)}",
        f"naninovel_scanned_files: {stats.get('naninovel_scanned_files', 0)}",
        f"elapsed: {format_duration(stats.get('elapsed_seconds', 0))}",
        "note: v1.31-real: tự động nhận bảng language kiểu UABEA/TextAsset (Key;Description;English;...) và import ngược đúng ô/cột; không dùng raw slot cho menu/UI.",
    ]
    if stats.get("backend_counts"):
        report.append("backend_counts:")
        for name, count in sorted(stats["backend_counts"].items(), key=lambda item: (-item[1], item[0])):
            report.append(f"  {name}: {count}")
    if stats.get("method_counts"):
        report.append("method_counts:")
        for name, count in sorted(stats["method_counts"].items(), key=lambda item: (-item[1], item[0])):
            report.append(f"  {name}: {count}")
    if stats.get("errors"):
        report.append("errors:")
        report.extend(stats["errors"])
    (out / "extract_report.txt").write_text("\n".join(report), "utf-8")
    cleanup_package_zip_files(out)


def _prepare_trace_plan(
    output_dir: str,
    main_entries,
    review_entries,
    stats,
    separate_review: bool,
    enforce_symmetry: bool,
) -> dict:
    """Build the legacy package decision in memory without touching outputs."""

    from vntext.app_backend import VERSION, auto_candidate_action

    if enforce_symmetry:
        from vntext.patchability import enforce_main_flow, is_technical_skip_entry

        enforce_main_flow(
            [entry for entry in main_entries if not is_technical_skip_entry(entry)],
            require_proof=True,
        )

    candidate_entries = list(main_entries) + list(review_entries)
    asset_patchable_entries, raw_unpatchable_entries, other_review_entries = split_asset_patchable_entries(
        main_entries, review_entries
    )
    main_entries = asset_patchable_entries
    review_entries = other_review_entries

    from vntext.mt_classify import classify_row_authoritative

    technical_skipped: list[tuple[Entry, str]] = []
    nontechnical_main: list[Entry] = []
    nontechnical_review: list[Entry] = []
    seen_technical: set[str] = set()
    main_ids = {id(entry) for entry in main_entries}
    for entry in list(main_entries) + list(review_entries):
        classifier_row = entry.to_csv_row()
        classifier_row.update(
            {
                "review_only": entry.review_only and entry.import_method != "sqlite_text_candidate",
                "locator": entry.locator,
                "patch_proof": entry.patch_proof,
            }
        )
        action, reason, _decision = classify_row_authoritative(classifier_row)
        if action == "skip_technical":
            if entry.key not in seen_technical:
                technical_skipped.append((entry, reason))
                seen_technical.add(entry.key)
            continue
        if id(entry) in main_ids:
            nontechnical_main.append(entry)
        else:
            nontechnical_review.append(entry)
    main_entries = nontechnical_main
    review_entries = nontechnical_review

    raw_candidate_entries = [entry for entry in review_entries if entry.import_method == "naninovel_raw_candidate"]
    real_review_entries = [entry for entry in review_entries if entry.import_method != "naninovel_raw_candidate"]
    auto_promoted_entries = []
    auto_kept_raw_entries = []
    auto_rejected_entries = []
    if separate_review and raw_candidate_entries:
        existing_main_keys = {entry.key for entry in main_entries}
        for entry in raw_candidate_entries:
            if enforce_symmetry:
                auto_kept_raw_entries.append(entry)
                continue
            action = auto_candidate_action(entry.source_text)
            if action == "promote" and entry.key not in existing_main_keys:
                entry.review_only = False
                entry.safety = "unsafe_candidate"
                auto_promoted_entries.append(entry)
                existing_main_keys.add(entry.key)
            elif action == "reject":
                auto_rejected_entries.append(entry)
            else:
                auto_kept_raw_entries.append(entry)
        raw_candidate_entries = auto_kept_raw_entries
        main_entries = list(main_entries) + auto_promoted_entries

    if separate_review:
        manifest_entries = (
            list(main_entries)
            + list(raw_candidate_entries)
            + list(real_review_entries)
            + list(raw_unpatchable_entries)
            + list(auto_rejected_entries)
        )
    else:
        all_entries = list(main_entries) + list(review_entries)
        manifest_entries = all_entries + list(raw_unpatchable_entries)

    stats = dict(stats)
    stats["technical_skipped_entries"] = len(technical_skipped)
    stats["translation_csv_entries"] = len(main_entries) if separate_review else len(main_entries) + len(review_entries)
    stats["auto_raw_promoted"] = len(auto_promoted_entries)
    stats["auto_raw_rejected"] = len(auto_rejected_entries)
    stats["raw_candidate_entries"] = len(raw_candidate_entries)
    stats["raw_unpatchable_entries"] = len(raw_unpatchable_entries)
    stats["review_only_entries"] = len(real_review_entries)
    manifest = {
        "format": 2,
        "tool": "VNText Studio Core",
        "version": VERSION,
        "entries": [entry.to_manifest() for entry in manifest_entries],
        "technical_skipped": [
            {**entry.to_manifest(), "reason": reason}
            for entry, reason in technical_skipped
        ],
        "stats": stats,
    }
    return {
        "out": Path(output_dir),
        "candidate_entries": candidate_entries,
        "main_entries": main_entries,
        "review_entries": review_entries,
        "raw_candidate_entries": raw_candidate_entries,
        "raw_unpatchable_entries": raw_unpatchable_entries,
        "real_review_entries": real_review_entries,
        "auto_promoted_entries": auto_promoted_entries,
        "auto_rejected_entries": auto_rejected_entries,
        "technical_skipped": technical_skipped,
        "manifest": manifest,
        "stats": stats,
        "separate_review": separate_review,
        "inventory": _load_extract_inventory(Path(output_dir)),
    }


def _load_extract_inventory(output_dir: Path) -> dict:
    """Load only bounded analyzer inventory facts into the trace payload."""

    report_path = output_dir / "unity_analysis.json"
    if not report_path.is_file():
        return {"present": False, "inventory_complete": True}
    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return {"present": True, "inventory_complete": False, "read_error": True}
    if not isinstance(report, dict):
        return {"present": True, "inventory_complete": False, "invalid": True}
    summary = report.get("summary") or {}
    return {
        "present": True,
        "inventory_complete": bool(report.get("inventory_complete", False)),
        "unity_status": str((report.get("unity") or {}).get("status") or ""),
        "resource_count": int(summary.get("resource_count") or 0),
        "unknown_resources": int(summary.get("unknown_resources") or 0),
        "text_candidate_resources": int(summary.get("text_candidate_resources") or 0),
        "scan_error_count": len(report.get("scan_errors") or []),
    }


def _classifier_matches_package_classification(classification: str, decision) -> bool:
    """Check the persisted package bucket against the V2 route semantics.

    The package split has a few deliberate normalisations: technical rows are
    stored in ``technical_skipped.csv`` (``SKIP``), raw candidates may remain
    in a review ledger even though V2 calls their route ``UNSUPPORTED``, and
    intentional keeps remain patchable MAIN rows.  Comparing the literal
    strings ``MAIN``/``TRANSLATE`` would report those safe boundaries as false
    ``MISCLASSIFIED`` failures.
    """

    if decision.decision == "UNSUPPORTED":
        return classification in {"REVIEW", "UNSUPPORTED"}
    if bool((decision.evidence or {}).get("review_only")):
        return classification == "REVIEW"
    if decision.decision == "TRANSLATE":
        return classification == "MAIN"
    if decision.decision == "REVIEW":
        return classification == "REVIEW"
    if decision.decision == "DO_NOT_TRANSLATE":
        if decision.ledger == "technical_skipped":
            return classification == "SKIP"
        return classification == "MAIN"
    return False


def _trace_extract_plan(trace, plan: dict) -> None:
    from vntext.traceability import (
        CLASSIFICATION_MAIN,
        CLASSIFICATION_REVIEW,
        CLASSIFICATION_SKIP,
        CLASSIFICATION_UNSUPPORTED,
        EVENT_COMPLETED,
        EVENT_FAILED,
        ROOT_CAUSE_DISCOVERY_GAP,
        ROOT_CAUSE_MISCLASSIFIED,
        STAGE_CLASSIFIED,
        STAGE_DISCOVERED,
        STAGE_EXTRACTED,
    )
    from vntext.mt_classify import (
        CLASSIFIER_POLICY_HASH,
        CLASSIFIER_POLICY_VERSION,
        classify_row_v2,
    )

    stats = plan.get("stats") or {}
    inventory = plan.get("inventory") or {}
    discovery_payload = {
        "source": "extract",
        "step": "discovery_inventory",
        "files_scanned": stats.get("files_scanned"),
        "skipped_deep_files": stats.get("skipped_deep_files", 0),
        "skipped_raw_files": stats.get("skipped_raw_files", 0),
        "file_timings": list(stats.get("file_timings") or []),
        "errors": list(stats.get("errors") or [])[:50],
        "inventory": inventory,
    }
    discovery_failed = bool(discovery_payload["errors"]) or (
        inventory.get("inventory_complete") is False
    )
    trace.record_event(
        STAGE_DISCOVERED,
        status=EVENT_FAILED if discovery_failed else EVENT_COMPLETED,
        root_cause=ROOT_CAUSE_DISCOVERY_GAP if discovery_failed else None,
        payload=discovery_payload,
    )
    trace.record_event(
        STAGE_EXTRACTED,
        status=EVENT_FAILED if discovery_failed else EVENT_COMPLETED,
        root_cause=ROOT_CAUSE_DISCOVERY_GAP if discovery_failed else None,
        payload={
            "source": "extract",
            "step": "extract_inventory_boundary",
            "candidate_count": len(plan["candidate_entries"]),
            "inventory_complete": not discovery_failed,
        },
    )

    technical_reasons = {id(entry): reason for entry, reason in plan["technical_skipped"]}
    unsupported_ids = {
        id(entry)
        for entry in plan["raw_unpatchable_entries"] + plan["auto_rejected_entries"]
    }
    review_ids = {
        id(entry)
        for entry in plan["raw_candidate_entries"] + plan["real_review_entries"]
    }
    promoted_ids = {id(entry) for entry in plan["auto_promoted_entries"]}
    main_ids = {id(entry) for entry in plan["main_entries"]}

    classifier_results = {}
    classifier_rows = []
    for entry in plan["candidate_entries"]:
        classifier_row = entry.to_csv_row()
        # These fields are trace-only metadata.  They are deliberately not
        # added to CSV_FIELDS or translation.csv.
        classifier_row.update(
            {
                "key": entry.key,
                "review_only": entry.review_only,
                "locator": entry.locator,
                "patch_proof": entry.patch_proof,
            }
        )
        decision = classify_row_v2(classifier_row)
        classifier_results[id(entry)] = decision
        classifier_rows.append(decision)
    classifier_report = {
        "policy_version": CLASSIFIER_POLICY_VERSION,
        "policy_hash": CLASSIFIER_POLICY_HASH,
        "rows": len(classifier_rows),
        "no_drop": len(classifier_rows) == len(plan["candidate_entries"]),
        "misclassified": 0,
        "decision_counts": {},
        "ledger_counts": {},
    }
    for decision in classifier_rows:
        classifier_report["decision_counts"][decision.decision] = (
            classifier_report["decision_counts"].get(decision.decision, 0) + 1
        )
        classifier_report["ledger_counts"][decision.ledger] = (
            classifier_report["ledger_counts"].get(decision.ledger, 0) + 1
        )

    for start in range(0, len(plan["candidate_entries"]), 500):
        with trace.batch():
            for entry in plan["candidate_entries"][start : start + 500]:
                entry_id = id(entry)
                if entry_id in technical_reasons:
                    classification = CLASSIFICATION_SKIP
                    reason = technical_reasons[entry_id]
                elif entry_id in unsupported_ids:
                    classification = CLASSIFICATION_UNSUPPORTED
                    reason = "raw candidate rejected/unpatchable"
                elif entry_id in review_ids:
                    classification = CLASSIFICATION_REVIEW
                    reason = "raw candidate kept for review" if entry_id not in technical_reasons else technical_reasons[entry_id]
                elif entry_id in main_ids:
                    classification = CLASSIFICATION_MAIN
                    reason = "raw candidate auto-promoted" if entry_id in promoted_ids else "main translation flow"
                else:
                    classification = CLASSIFICATION_REVIEW
                    reason = "candidate not present in final package split"
                result = trace.register_entry(
                    entry,
                    classification=classification,
                    classification_reason=str(reason or classification),
                    metadata={
                        "source": "extract",
                        "emitted_candidate": True,
                        "classifier_v2": classifier_results[entry_id].to_dict(),
                    },
                )
                classifier = classifier_results[entry_id]
                payload = {
                    "source": "extract",
                    "emitted_candidate": True,
                    "classification": classification,
                    "reason": str(reason or classification),
                    "classifier_v2": classifier.to_dict(),
                }
                misclassified = not _classifier_matches_package_classification(
                    classification,
                    classifier,
                )
                if misclassified:
                    classifier_report["misclassified"] += 1
                    payload["classification_mismatch"] = {
                        "actual": classification,
                        "expected_decision": classifier.decision,
                        "expected_ledger": classifier.ledger,
                        "reason_code": classifier.reason_code,
                    }
                trace.record_event(STAGE_DISCOVERED, trace_id=result["trace_id"], payload=payload)
                trace.record_event(STAGE_EXTRACTED, trace_id=result["trace_id"], payload=payload)
                trace.record_event(
                    STAGE_CLASSIFIED,
                    status=EVENT_FAILED if misclassified else EVENT_COMPLETED,
                    trace_id=result["trace_id"],
                    root_cause=ROOT_CAUSE_MISCLASSIFIED if misclassified else None,
                    payload=payload,
                )
    return classifier_report


def write_package(
    output_dir: str,
    main_entries,
    review_entries,
    stats,
    separate_review: bool = False,
    enforce_symmetry: bool = False,
    *,
    enable_trace: bool = False,
):
    """Write a package, optionally recording the worker baseline lifecycle."""

    if not enable_trace:
        return _write_package_legacy(
            output_dir,
            main_entries,
            review_entries,
            stats,
            separate_review,
            enforce_symmetry,
        )

    from vntext.traceability import (
        EVENT_ABORTED,
        EVENT_COMPLETED,
        EVENT_FAILED,
        ROOT_CAUSE_DISCOVERY_GAP,
        ROOT_CAUSE_UNKNOWN,
        TraceStore,
    )
    from vntext.mt_classify import CLASSIFIER_POLICY_HASH, CLASSIFIER_POLICY_VERSION

    plan = _prepare_trace_plan(
        output_dir,
        main_entries,
        review_entries,
        stats,
        separate_review,
        enforce_symmetry,
    )
    trace = TraceStore.for_package(plan["out"], plan["manifest"])
    run_finished = False
    try:
        trace.start_run(
            metadata={
                "pipeline": "extract",
                "separate_review": bool(separate_review),
                "enforce_symmetry": bool(enforce_symmetry),
                "classifier_policy_version": CLASSIFIER_POLICY_VERSION,
                "classifier_policy_hash": CLASSIFIER_POLICY_HASH,
            }
        )
        classifier_report = _trace_extract_plan(trace, plan)
        result = _write_package_legacy(
            output_dir,
            main_entries,
            review_entries,
            stats,
            separate_review,
            enforce_symmetry,
        )
        discovery_failed = bool(plan["stats"].get("errors")) or (
            plan.get("inventory") or {}
        ).get("inventory_complete") is False
        trace.finish_run(
            EVENT_FAILED if discovery_failed else EVENT_COMPLETED,
            ROOT_CAUSE_DISCOVERY_GAP if discovery_failed else None,
        )
        run_finished = True
        trace.write_summary(
            extra={
                "pipeline": "extract",
                "candidate_emitted": len(plan["candidate_entries"]),
                "manifest_entries": len(plan["manifest"]["entries"]),
                "technical_skipped_entries": len(plan["manifest"]["technical_skipped"]),
                "translation_csv_entries": plan["stats"]["translation_csv_entries"],
                "review_only_entries": plan["stats"]["review_only_entries"],
                "raw_unpatchable_entries": plan["stats"]["raw_unpatchable_entries"],
                "auto_raw_promoted": plan["stats"]["auto_raw_promoted"],
                "auto_raw_rejected": plan["stats"]["auto_raw_rejected"],
                "inventory": plan.get("inventory") or {},
                "classifier": classifier_report,
                "trace_coverage": {
                    "status": "TRACE_ENABLED",
                    "caller": "vntext.package_io.write_package",
                    "untraced_caller_count": 0,
                },
            }
        )
        trace.export_jsonl()
        return result
    except Exception:
        if trace.run_id is not None and not run_finished:
            try:
                trace.finish_run(EVENT_ABORTED, ROOT_CAUSE_UNKNOWN)
            except Exception:
                pass
        raise
    finally:
        trace.close()



def read_translation_rows(csv_path: str):
    rows = {}
    with Path(csv_path).open("r", encoding="utf-8-sig", newline="") as fh:
        for row in csv.DictReader(fh):
            key = row.get("key", "").strip()
            text = row.get("translation", "").strip()
            if key and text:
                rows[key] = row
    return rows
