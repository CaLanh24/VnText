"""Pipeline extraction family.

Function bodies are mechanically preserved from the former monolithic vntext.extract module.
"""

from __future__ import annotations

from vntext.extract_constants import (
    Counter,
    DEFAULT_FILE_EXTRACT_TIMEOUT,
    Path,
    SKIP_DEEP_EXTS,
    TEXT_EXTS,
    UNITY_DATA_BLOB_EXTS,
    UNITY_EXTS,
    UNITY_UI_SCAN_MAX_FILE_BYTES,
    _UNITY_OBJ_PROGRESS_RX,
    threading,
    time,
)



def extract_project(
    input_path: str,
    output_mode: str = "safe",
    progress_callback=None,
    extract_level: str = "balanced",
    *,
    file_inventory=None,
):
    from vntext.renpy_adapter import detect_engine
    detected = detect_engine(input_path)
    if detected.engine == "RENPY_LOOSE_SOURCE":
        from vntext.renpy_extract import extract_loose_source
        main, review, stats = extract_loose_source(input_path)
        from vntext.patchability import route_main_flow
        main, review, symmetry = route_main_flow([*main, *review], require_proof=True)
        stats.update({"mode": output_mode, "extract_level": extract_level, "main_entries": len(main), "review_entries": len(review), "errors": [], "symmetry_gate": symmetry})
        return main, review, stats
    from vntext.extract_naninovel import iter_files, rel_path, scan_naninovel_blob, should_naninovel_scan, should_raw_scan
    from vntext.extract_postprocess import _extract_step_timeout, _run_extract_step, dedupe, postprocess_extracted_entries
    from vntext.extract_sqlite import extract_sqlite_text_candidates
    from vntext.extract_yaml import extract_yaml_text_candidates
    from vntext.extract_text import extract_plain_text, format_file_size
    from vntext.structured_csv import extract_structured_csv
    from vntext.structured_json import extract_structured_json
    from vntext.structured_xml import extract_structured_xml
    from vntext.extract_unity import extract_unity_typetree, scan_unity_ui_blob, scan_whole_file
    from vntext.unity_analyzer import detect_resource_kind
    root = Path(input_path)
    base = root if root.is_dir() else root.parent
    all_entries = []
    errors = []
    skipped_deep_files = 0
    skipped_raw_files = 0
    naninovel_scanned_files = 0
    extensionless_text_files = 0
    extensionless_unity_files = 0
    sqlite_inventory_files = 0
    sqlite_review_entries = 0
    yaml_inventory_files = 0
    yaml_review_entries = 0
    file_timings: list[dict[str, Any]] = []
    files = []
    started = time.time()
    progress_scale = 1000
    state = {
        "done": 0,
        "total": 1,
        "file": "Dang loc file Unity/text...",
        "found": 0,
        "detail": "",
        "sub_frac": 0.0,
        "log": True,
    }

    def emit(log: bool = False):
        if not progress_callback:
            return
        done = state["done"]
        total = max(1, state["total"])
        elapsed = time.time() - started
        eta = (elapsed / done) * (total - done) if done else 0
        label = state["file"]
        if state["detail"]:
            label = f"{label} | {state['detail']}"
        progress_callback({
            "done": done,
            "total": total,
            "file": label,
            "found": state["found"],
            "elapsed": elapsed,
            "eta": eta,
            "phase": "extract",
            "log": log or state["log"],
            "step": state.get("step_label", ""),
            "item": state.get("item_label", ""),
        })
        state["log"] = False

    hb_stop = threading.Event()

    def heartbeat():
        while not hb_stop.wait(1.0):
            emit(log=False)

    if progress_callback:
        progress_callback({
            "done": 0,
            "total": 1,
            "file": "Dang loc file Unity/text...",
            "found": 0,
            "elapsed": 0,
            "eta": 0,
            "phase": "extract",
            "log": True,
        })
        threading.Thread(target=heartbeat, daemon=True).start()

    try:
        file_kinds: dict[Path, dict] = {}
        input_files = iter_files(root) if file_inventory is None else file_inventory
        for path in input_files:
            kind = detect_resource_kind(path)
            suffix = path.suffix.lower()
            is_sqlite_file = kind.get("signature") == "sqlite"
            is_yaml_file = suffix in {".yaml", ".yml"}
            is_text_file = not is_sqlite_file and (
                not is_yaml_file and (suffix in TEXT_EXTS or bool(kind.get("is_extensionless_text")))
            )
            is_unity_file = suffix in UNITY_EXTS or bool(kind.get("is_unity_extractable"))
            if is_text_file or is_unity_file or is_sqlite_file or is_yaml_file:
                file_kinds[path] = kind
                if kind.get("is_extensionless_text"):
                    extensionless_text_files += 1
                if kind.get("is_unity_extractable") and suffix not in UNITY_EXTS:
                    extensionless_unity_files += 1
                if is_sqlite_file:
                    sqlite_inventory_files += 1
                if is_yaml_file:
                    yaml_inventory_files += 1
        files = list(file_kinds)
        total_files = len(files)
        state["total"] = total_files * progress_scale
        state["file"] = f"Co {total_files} file text/Unity/SQLite"
        emit(log=True)

        for index, path in enumerate(files, start=1):
            rel = rel_path(path, base)
            try:
                size = path.stat().st_size
            except OSError:
                size = 0
            size_note = f" ({format_file_size(size)})" if size else ""
            file_t0 = time.time()
            state["step_label"] = f"File {index}/{total_files}"
            state["item_label"] = rel
            state["done"] = (index - 1) * progress_scale
            state["sub_frac"] = 0.0
            state["file"] = f"START {rel}{size_note}"
            state["detail"] = ""
            state["found"] = len(all_entries)
            state["log"] = True
            emit(log=True)

            def on_file_progress(detail: str):
                state["detail"] = str(detail or "")
                state["found"] = len(all_entries)
                match = _UNITY_OBJ_PROGRESS_RX.search(state["detail"])
                if match:
                    cur, tot = int(match.group(1)), max(1, int(match.group(2)))
                    state["sub_frac"] = cur / tot
                state["done"] = (index - 1) * progress_scale + int(state["sub_frac"] * (progress_scale - 50))
                emit(log=False)

            suffix = path.suffix.lower()
            kind = file_kinds.get(path, {})
            is_extensionless_text = bool(kind.get("is_extensionless_text"))
            is_sqlite_file = kind.get("signature") == "sqlite"
            is_yaml_file = suffix in {".yaml", ".yml"}
            is_text_file = not is_sqlite_file and not is_yaml_file and (suffix in TEXT_EXTS or is_extensionless_text)
            is_unity_file = suffix in UNITY_EXTS or bool(kind.get("is_unity_extractable"))
            step_plan: list[tuple[str, Callable[[], Iterable[Any]], float]] = []
            if is_text_file:
                if suffix == ".json":
                    step_plan.append(
                        (
                            "structured_json",
                            lambda p=path: extract_structured_json(p, base),
                            _extract_step_timeout("structured_json", size),
                        )
                    )
                elif suffix == ".csv":
                    step_plan.append(
                        (
                            "structured_csv",
                            lambda p=path: extract_structured_csv(p, base),
                            _extract_step_timeout("structured_csv", size),
                        )
                    )
                elif suffix == ".xml":
                    step_plan.append(
                        (
                            "structured_xml",
                            lambda p=path: extract_structured_xml(p, base),
                            _extract_step_timeout("structured_xml", size),
                        )
                    )
                else:
                    step_plan.append(
                        (
                            "plain_text",
                            lambda p=path, detected=is_extensionless_text: extract_plain_text(p, base, detected_text=detected),
                            _extract_step_timeout("plain_text", size),
                        )
                    )
            if is_sqlite_file:
                step_plan.append(
                    (
                        "sqlite_inventory",
                        lambda p=path: extract_sqlite_text_candidates(p, base),
                        _extract_step_timeout("sqlite_inventory", size),
                    )
                )
            if is_yaml_file:
                step_plan.append(
                    (
                        "yaml_inventory",
                        lambda p=path: extract_yaml_text_candidates(p, base),
                        _extract_step_timeout("yaml_inventory", size),
                    )
                )
            if is_unity_file:
                step_plan.append(
                    ("unity_typetree", lambda p=path: extract_unity_typetree(p, base, on_file_progress), _extract_step_timeout("unity_typetree", size))
                )
                if output_mode == "deep" and should_naninovel_scan(path, suffix, is_unity_resource=is_unity_file):
                    step_plan.append(
                        ("naninovel_scan", lambda p=path: scan_naninovel_blob(p, base, extract_level), _extract_step_timeout("naninovel_scan", size))
                    )
                if output_mode == "deep" and size <= UNITY_UI_SCAN_MAX_FILE_BYTES:
                    step_plan.append(
                        ("unity_ui_blob", lambda p=path: scan_unity_ui_blob(p, base, extract_level), _extract_step_timeout("unity_ui_blob", size))
                    )
            if output_mode == "deep" and not is_text_file and not is_unity_file and not is_sqlite_file and not is_yaml_file and should_raw_scan(path, suffix):
                step_plan.append(("raw_scan", lambda p=path: scan_whole_file(p, base), _extract_step_timeout("raw_scan", size)))
            elif output_mode == "deep" and not is_text_file and not is_unity_file and not is_sqlite_file and not is_yaml_file:
                skipped_raw_files += 1
                if suffix in SKIP_DEEP_EXTS or suffix in UNITY_DATA_BLOB_EXTS:
                    skipped_deep_files += 1

            file_deadline = file_t0 + min(DEFAULT_FILE_EXTRACT_TIMEOUT, sum(t for _, _, t in step_plan) + 30)
            file_added = 0
            for step_name, factory, step_timeout in step_plan:
                if time.time() > file_deadline:
                    msg = f"{rel}: het thoi gian file ({DEFAULT_FILE_EXTRACT_TIMEOUT:.0f}s) — bo qua buoc {step_name}"
                    errors.append(msg)
                    state["detail"] = msg
                    emit(log=True)
                    break
                remaining = max(5.0, min(step_timeout, file_deadline - time.time()))
                state["detail"] = step_name
                emit(log=step_name in {"unity_typetree", "naninovel_scan"})
                before = len(all_entries)
                entries, step_elapsed, step_err = _run_extract_step(step_name, factory, remaining)
                if step_err == "timeout":
                    msg = f"{rel}: {step_name} TIMEOUT sau {remaining:.0f}s — bo qua buoc nay"
                    errors.append(msg)
                    state["detail"] = msg
                    emit(log=True)
                    continue
                if step_err:
                    errors.append(f"{rel}: {step_name} loi: {step_err}")
                    continue
                all_entries.extend(entries)
                added = len(all_entries) - before
                file_added += added
                if step_name == "naninovel_scan" and added > 0:
                    naninovel_scanned_files += 1
                if step_name == "sqlite_inventory":
                    sqlite_review_entries += added
                if step_name == "yaml_inventory":
                    yaml_review_entries += added
                file_timings.append(
                    {
                        "file": rel,
                        "size": size,
                        "step": step_name,
                        "elapsed": round(step_elapsed, 2),
                        "added": added,
                    }
                )

            file_elapsed = time.time() - file_t0
            file_timings.append(
                {
                    "file": rel,
                    "size": size,
                    "step": "__file__",
                    "elapsed": round(file_elapsed, 2),
                    "added": file_added,
                }
            )
            state["done"] = index * progress_scale
            state["found"] = len(all_entries)
            state["detail"] = ""
            state["file"] = f"END {rel}{size_note} ({file_elapsed:.1f}s, +{file_added})"
            state["log"] = index == total_files or index % 10 == 0 or file_elapsed >= 30
            emit(log=state["log"])
    finally:
        hb_stop.set()

    merged = postprocess_extracted_entries(dedupe(all_entries))
    from vntext.patchability import route_main_flow

    # Discovery may find useful text without a safe writer.  Keep those rows
    # visible in the review ledger, but never promote them to translation.csv.
    main, review, symmetry_report = route_main_flow(merged, require_proof=True)
    backend_counts = Counter(entry.backend for entry in merged)
    method_counts = Counter(entry.import_method for entry in merged)
    stats = {
        "mode": output_mode,
        "extract_level": extract_level,
        "files_scanned": len(files),
        "main_entries": len(main),
        "review_entries": len(review),
        "backend_counts": dict(backend_counts),
        "method_counts": dict(method_counts),
        "skipped_deep_files": skipped_deep_files,
        "skipped_raw_files": skipped_raw_files,
        "naninovel_scanned_files": naninovel_scanned_files,
        "extensionless_text_files": extensionless_text_files,
        "extensionless_unity_files": extensionless_unity_files,
        "sqlite_inventory_files": sqlite_inventory_files,
        "sqlite_review_entries": sqlite_review_entries,
        "yaml_inventory_files": yaml_inventory_files,
        "yaml_review_entries": yaml_review_entries,
        "symmetry_gate": symmetry_report,
        "elapsed_seconds": round(time.time() - started, 2),
        "file_timings": file_timings,
        "errors": errors,
    }
    return main, review, stats

__all__ = ['extract_project']
