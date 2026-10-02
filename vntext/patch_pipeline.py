"""Pipeline patch responsibilities."""

from __future__ import annotations

from vntext.patch_constants import (
    Path,
    TEXT_EXTS,
    UNITY_EXTS,
    _mono_class_name,
    _object_raw_bytes,
    _semicolon_csv_read,
    _semicolon_csv_write,
    _typetree_field_is_display_text,
    is_ui_text_field,
    iter_naninovel_display_texts,
    json,
    load_review_only_keys,
    load_whitelist,
    patch_skip_reason,
    read_translation_rows,
    shutil,
    time,
)


_RENPY_PATCH_METHODS = frozenset({"renpy_dialogue", "renpy_string"})
_RENPY_UNPATCHABLE_ENGINES = frozenset({"RENPY_COMPILED_ONLY", "MIXED"})


def detect_patch_engine(manifest: dict) -> str:
    """Resolve the patch route from package-owned engine evidence only."""

    if not isinstance(manifest, dict):
        raise ValueError("patch manifest must be a JSON object")
    stats = manifest.get("stats")
    declared = str(stats.get("engine") or "").strip().upper() if isinstance(stats, dict) else ""
    entries = manifest.get("entries")
    if not isinstance(entries, list):
        raise ValueError("patch manifest entries must be a list")
    methods = {str(item.get("import_method") or "").strip() for item in entries if isinstance(item, dict)}
    methods.discard("")
    renpy_methods = methods & _RENPY_PATCH_METHODS
    renpy_backend = any(
        str(item.get("backend") or "").strip().casefold() == "renpy_loose_source"
        for item in entries
        if isinstance(item, dict)
    )

    if declared in _RENPY_UNPATCHABLE_ENGINES:
        label = "compiled-only" if declared == "RENPY_COMPILED_ONLY" else declared
        raise ValueError(f"unsupported Ren'Py patch engine: {label}; Unity delivery is not allowed")
    if declared.startswith("RENPY") and declared != "RENPY_LOOSE_SOURCE":
        raise ValueError(f"unsupported Ren'Py patch engine: {declared}; Unity delivery is not allowed")
    if renpy_methods or renpy_backend or declared == "RENPY_LOOSE_SOURCE":
        if not renpy_methods:
            raise ValueError("Ren'Py package has no native patch route; Unity delivery is not allowed")
        if methods - _RENPY_PATCH_METHODS:
            mixed = ", ".join(sorted(methods - _RENPY_PATCH_METHODS))
            raise ValueError(f"mixed Ren'Py/Unity patch methods are unsupported: {mixed}")
        return "renpy"
    if any(method.startswith("renpy_") for method in methods):
        raise ValueError("unsupported Ren'Py patch method; Unity delivery is not allowed")
    return "unity"


def apply_translation_package(csv_path: str, manifest_path: str, game_root: str, output_dir: str, progress_callback=None):
    import json as _json
    _manifest_probe = _json.loads(Path(manifest_path).read_text(encoding="utf-8-sig"))
    if detect_patch_engine(_manifest_probe) == "renpy":
        from vntext.patch_renpy import apply_renpy_translation_package
        return apply_renpy_translation_package(csv_path, manifest_path, game_root, output_dir, progress_callback)
    from vntext.patch_naninovel import patch_naninovel_scripts_in_env
    from vntext.patch_output import save_unity_env, write_patch_manifest
    from vntext.patch_plain import _fit_textasset_script_to_slot, _replace_textasset_script_bytes
    from vntext.patch_safety import apply_raw_fixed_ops, backup_original_file, inc_backend, iter_patch_locators, report_backend_coverage, resolve_game_source_file, verify_patched_translations
    from vntext.patch_unity import (
        _pop_patched_ui_sources,
        patch_object_length_prefixed_strings,
    )
    from vntext.patch_gate import is_verified_cloud_repair_output, legacy_manifest_reason
    from vntext.unity_analyzer import detect_resource_kind
    from vntext.patch_readback import (
        FAIL as READBACK_FAIL,
        NOT_TESTABLE as READBACK_NOT_TESTABLE,
        PASS as READBACK_PASS,
        TIMEOUT as READBACK_TIMEOUT,
        readback_timeout_seconds,
        verify_patch_targets,
        write_patch_verification_report,
    )
    translations = read_translation_rows(csv_path)
    manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8-sig"))
    legacy_reason = legacy_manifest_reason(manifest)
    if legacy_reason:
        raise ValueError(f"unsupported legacy package: {legacy_reason}")
    entries = manifest.get("entries", [])
    game_base = Path(game_root)
    if game_base.is_file():
        game_base = game_base.parent
    out = Path(output_dir)
    patched_root = out / "COPY_TO_GAME_ROOT"
    backup_root = out / "backup_original"
    report = []
    patched_count = 0
    skipped_count = 0
    backend_counts: dict[str, dict[str, int]] = {}
    duplicate_patch_locations = 0
    patched_addressables: list[tuple[str, Path]] = []

    package_dir = Path(csv_path).parent
    allow_ct2_junk = is_verified_cloud_repair_output(csv_path)
    review_keys = load_review_only_keys(package_dir)
    whitelist = load_whitelist(package_dir)
    gate_skipped = 0

    by_file: dict[str, list[tuple[dict, str]]] = {}
    for entry in entries:
        key = entry.get("key")
        if key not in translations:
            continue
        if key in review_keys:
            gate_skipped += 1
            continue
        trans = translations[key]["translation"]
        reason = patch_skip_reason(entry, trans, whitelist, allow_ct2_junk=allow_ct2_junk)
        if reason:
            gate_skipped += 1
            report.append(f"SKIP key {key}: {reason}")
            continue
        rel = str(entry.get("file_path", "") or "").replace("\\", "/")
        while "//" in rel:
            rel = rel.replace("//", "/")
        # Keep Windows-style for game tree; collapse accidental doubled separators.
        rel = rel.replace("/", "\\")
        by_file.setdefault(rel, []).append((entry, trans))

    file_items = [(rel, items) for rel, items in by_file.items() if rel]
    total_steps = max(1, len(file_items) + 3)
    started = time.time()
    step = {"n": 0}

    def emit(label: str, done: int | None = None, bump: bool = True):
        if done is None:
            if bump:
                step["n"] += 1
            done = step["n"]
        elapsed = time.time() - started
        remaining = max(0, total_steps - done)
        eta = (elapsed / done) * remaining if done else 0
        if callable(progress_callback):
            progress_callback({
                "done": min(max(done, 0), total_steps),
                "total": total_steps,
                "file": label,
                "found": patched_count,
                "elapsed": elapsed,
                "eta": eta,
                "phase": "patch",
            })

    emit("Dang doc translation.csv / manifest.json...", done=0)

    for rel, items in file_items:
        emit(f"Dang patch {rel} ({len(items)} dong)...")
        src, rel = resolve_game_source_file(game_base, rel)
        if not src.exists():
            report.append(f"MISS {rel}: khong tim thay file goc")
            skipped_count += len(items)
            continue
        target = patched_root / rel
        resource_kind = detect_resource_kind(src)
        structured_methods = {
            "structured_json_value": (".json", "vntext.structured_json", "patch_structured_json"),
            "structured_csv_cell": (".csv", "vntext.structured_csv", "patch_structured_csv"),
            "structured_xml_value": (".xml", "vntext.structured_xml", "patch_structured_xml"),
        }
        structured_item = None
        if resource_kind.get("signature") == "sqlite" and any(
            entry.get("import_method") == "structured_sqlite_value" for entry, _trans in items
        ):
            structured_item = (
                "structured_sqlite_value",
                "vntext.extract_sqlite",
                "patch_structured_sqlite",
            )
        else:
            for method, (wanted_suffix, module_name, function_name) in structured_methods.items():
                if src.suffix.lower() == wanted_suffix and any(
                    entry.get("import_method") == method for entry, _trans in items
                ):
                    structured_item = (method, module_name, function_name)
                    break
        if structured_item:
            _method, module_name, function_name = structured_item
            module = __import__(module_name, fromlist=[function_name])
            patch_structured = getattr(module, function_name)

            backup_original_file(src, backup_root, rel)
            changed, skipped = patch_structured(src, target, items)
            patched_count += changed
            skipped_count += skipped
            backend_name = {
                "structured_json_value": "structured_json",
                "structured_csv_cell": "structured_csv",
                "structured_xml_value": "structured_xml",
                "structured_sqlite_value": "structured_sqlite",
            }[_method]
            inc_backend(backend_counts, backend_name, "patched", changed)
            inc_backend(backend_counts, backend_name, "skipped", skipped)
            label = {
                "structured_json_value": "JSON",
                "structured_csv_cell": "CSV",
                "structured_xml_value": "XML",
                "structured_sqlite_value": "SQLite",
            }[_method]
            report.append(f"{label} {rel}: {changed}/{len(items)}")
            continue

        is_plain_text_file = src.suffix.lower() in TEXT_EXTS or bool(resource_kind.get("is_extensionless_text"))
        is_unity_file = src.suffix.lower() in UNITY_EXTS or bool(resource_kind.get("is_unity_extractable"))

        # Plain text files: same translation should apply to every duplicate occurrence.
        if is_plain_text_file:
            target.parent.mkdir(parents=True, exist_ok=True)
            backup_original_file(src, backup_root, rel)
            shutil.copy2(src, target)
            import codecs

            original_bytes = target.read_bytes()
            has_utf8_bom = original_bytes.startswith(codecs.BOM_UTF8)
            text = original_bytes.decode("utf-8-sig", errors="ignore")
            lines = text.splitlines(keepends=True)
            changed = 0
            wanted = 0
            for entry, trans in items:
                old = entry.get("source_text", "")
                locators = iter_patch_locators(entry)
                loc_count = len(locators)
                wanted += max(1, loc_count)
                patched_for_entry = 0
                for locator in locators:
                    if "line" not in locator:
                        # Compatibility fallback for hand-authored/very old
                        # manifests that predate line locators. New extracted
                        # rows always carry a line and use the precise route.
                        if old:
                            for fallback_index, fallback_line in enumerate(lines):
                                fallback_content = fallback_line.rstrip("\r\n")
                                fallback_newline = fallback_line[len(fallback_content):]
                                if old in fallback_content:
                                    lines[fallback_index] = (
                                        fallback_content.replace(old, trans, 1) + fallback_newline
                                    )
                                    patched_for_entry += 1
                                    break
                        continue
                    try:
                        line_value = int(locator.get("line"))
                    except (TypeError, ValueError):
                        line_value = -1
                    # Extractors use one-based lines. Accept zero as the first
                    # line for compatibility with older hand-built fixtures.
                    line_index = line_value - 1 if line_value >= 1 else line_value
                    if not old or not (0 <= line_index < len(lines)):
                        continue
                    original_line = lines[line_index]
                    content = original_line.rstrip("\r\n")
                    newline = original_line[len(content):]
                    if old not in content:
                        continue
                    lines[line_index] = content.replace(old, trans, 1) + newline
                    patched_for_entry += 1
                changed += patched_for_entry
                if loc_count > 1:
                    duplicate_patch_locations += loc_count - 1
                if patched_for_entry:
                    inc_backend(backend_counts, entry.get("backend", "plain_text"), "patched", patched_for_entry)
                else:
                    skipped_count += max(1, loc_count)
                    inc_backend(backend_counts, entry.get("backend", "plain_text"), "skipped", max(1, loc_count))
            text = "".join(lines)
            target.write_bytes((codecs.BOM_UTF8 if has_utf8_bom else b"") + text.encode("utf-8"))
            report.append(f"TEXT {rel}: {changed}/{wanted}")
            patched_count += changed
            continue

        if not is_unity_file:
            report.append(f"SKIP {rel}: khong phai Unity asset/bundle")
            skipped_count += len(items)
            continue

        # Need UnityPy for object/script patches. Raw-only files can be copied and patched in-place.
        unity_object_methods = {
            "unity_textasset_script",
            "unity_textasset_table_cell",
            "unity_textasset_line",
            "unity_localization_string",
            "unity_typetree_field",
            "unity_ui_text",
            "naninovel_script_string",
            "naninovel_blob_string",
            "naninovel_raw_candidate",
            "naninovel_choice",
            "naninovel_print",
        }
        needs_unitypy = any((entry.get("import_method") in unity_object_methods) for entry, _trans in items)
        env = None
        allow_unityfs_growth = False
        objects_by_pid: dict[str, list] = {}

        def get_obj(path_id):
            found = objects_by_pid.get(str(path_id or "")) or []
            return found[0] if found else None

        def get_objs(path_id):
            return list(objects_by_pid.get(str(path_id or "")) or [])

        if needs_unitypy:
            try:
                import UnityPy
            except Exception as exc:
                raise RuntimeError(f"UnityPy not available: {exc}") from exc
            emit(f"Dang mo Unity file {rel}...", bump=False)
            import gc

            gc.collect()
            try:
                env = UnityPy.load(str(src))
            except MemoryError as exc:
                size = src.stat().st_size if src.is_file() else 0
                raise RuntimeError(
                    f"UnityPy.load MemoryError on {src} (size={size}). "
                    f"Kiem tra file trunc/OOM truoc khi patch."
                ) from exc
            allow_unityfs_growth = str(getattr(getattr(env, "file", None), "signature", "") or "") == "UnityFS"
            for obj in env.objects:
                objects_by_pid.setdefault(str(getattr(obj, "path_id", "")), []).append(obj)

        changed = 0
        unity_changed = 0
        raw_fixed_ops: list[dict] = []
        raw_blob_ops: list[dict] = []
        naninovel_by_pid: dict[str, dict[str, str]] = {}
        naninovel_global: dict[str, str] = {}
        ui_by_pid: dict[str, dict[str, str]] = {}
        ui_typetree_by_pid: dict[str, list[tuple[dict, str, str, dict]]] = {}

        # Cache TextAsset reads so many line patches in one object do not overwrite each other.
        textasset_cache: dict[int, dict] = {}
        typetree_cache: dict[int, dict] = {}
        has_noop_translation = any(
            str(trans) == str(entry.get("source_text") or "")
            for entry, trans in items
        )

        def get_textasset_state(obj, path_id):
            if path_id in textasset_cache:
                return textasset_cache[path_id]
            data = obj.read()
            script = getattr(data, "m_Script", None)
            field_name = "m_Script"
            if script is None and hasattr(data, "script"):
                script = getattr(data, "script")
                field_name = "script"
            was_bytes = isinstance(script, (bytes, bytearray))
            if was_bytes:
                try:
                    text_value = bytes(script).decode("utf-8")
                except UnicodeDecodeError:
                    text_value = bytes(script).decode("utf-8", errors="ignore")
            else:
                text_value = str(script)
            state = {
                "obj": obj,
                "data": data,
                "field_name": field_name,
                "was_bytes": was_bytes,
                "lines": text_value.splitlines(keepends=True),
                "dirty": False,
                "orig_size": int(getattr(obj, "byte_size", 0) or 0),
                "orig_raw": _object_raw_bytes(obj),
                "orig_script_text": text_value,
            }
            textasset_cache[path_id] = state
            return state

        def apply_textasset_line(loc: dict, trans: str, entry: dict) -> bool:
            path_id = str(loc.get("path_id", "") or "")
            obj = get_obj(path_id)
            if obj is None:
                report.append(f"MISS {rel}:{path_id}: khong tim thay TextAsset object")
                return False
            state = get_textasset_state(obj, path_id)
            line_index = loc.get("line_index")
            if not isinstance(line_index, int) or not (0 <= line_index < len(state["lines"])):
                report.append(f"SKIP {rel}:{path_id}: line_index khong hop le cho {entry.get('source_text','')[:60]}")
                return False
            original_line = state["lines"][line_index]
            raw = original_line.rstrip("\r\n")
            newline = original_line[len(raw):]
            source = str(entry.get("source_text") or "")
            prefix = loc.get("prefix", "")
            if source and raw.endswith(source):
                prefix = raw[: len(raw) - len(source)]
                state["lines"][line_index] = prefix + trans + newline
            elif source and source in raw and not prefix:
                # A plain line locator may still point at text followed by
                # serialized whitespace. Preserve that whitespace while
                # replacing the addressed value.
                state["lines"][line_index] = raw.replace(source, trans, 1) + newline
            elif source and prefix and raw.startswith(str(prefix)):
                # Key/value locators may omit the delimiter whitespace from
                # ``prefix`` and the source line may carry trailing padding.
                # Replace only inside the value remainder so ``Tip: value``
                # stays ``Tip: translated`` instead of losing the separator.
                value_start = len(str(prefix))
                value = raw[value_start:]
                if source in value:
                    state["lines"][line_index] = (
                        raw[:value_start] + value.replace(source, trans, 1) + newline
                    )
                elif trans and value.strip() == str(trans).strip():
                    # An idempotent patch may be applied to a file that is
                    # already translated.  Keep the serialized line byte
                    # shape intact; a second UnityFS save must not shorten
                    # the TextAsset just because the EN source is gone.
                    return True
                else:
                    # Preserve the delimiter/leading padding even when a
                    # stale locator reaches the addressed key/value line.
                    state["lines"][line_index] = raw[:value_start] + trans + newline
            else:
                if trans and trans in raw:
                    return True
                report.append(
                    f"SKIP {rel}:{path_id}: TextAsset source precondition failed "
                    f"for {entry.get('source_text', '')[:60]}"
                )
                return False
            state["dirty"] = True
            return True

        def apply_textasset_table_cell(loc: dict, trans: str, entry: dict) -> bool:
            path_id = str(loc.get("path_id", "") or "")
            obj = get_obj(path_id)
            if obj is None:
                report.append(f"MISS {rel}:{path_id}: khong tim thay TextAsset language table object")
                return False
            state = get_textasset_state(obj, path_id)
            line_index = loc.get("line_index")
            col_index = loc.get("column_index")
            if not isinstance(line_index, int) or not (0 <= line_index < len(state["lines"])):
                report.append(f"SKIP {rel}:{path_id}: table line_index khong hop le cho {entry.get('source_text','')[:60]}")
                return False
            if not isinstance(col_index, int):
                report.append(f"SKIP {rel}:{path_id}: table column_index khong hop le cho {entry.get('source_text','')[:60]}")
                return False
            original_line = state["lines"][line_index]
            raw = original_line.rstrip("\r\n")
            newline = original_line[len(raw):]
            cells = _semicolon_csv_read(original_line)
            if col_index >= len(cells):
                report.append(f"SKIP {rel}:{path_id}: table khong co cot {col_index} cho {entry.get('source_text','')[:60]}")
                return False
            cells[col_index] = trans
            state["lines"][line_index] = _semicolon_csv_write(cells, newline)
            state["dirty"] = True
            return True

        def apply_textasset_script(loc: dict, trans: str, entry: dict) -> bool:
            path_id = str(loc.get("path_id", "") or "")
            obj = get_obj(path_id)
            if obj is None:
                report.append(f"MISS {rel}:{path_id}: khong tim thay TextAsset object")
                return False
            data = obj.read()
            script = getattr(data, "m_Script", None)
            field_name = "m_Script"
            if script is None and hasattr(data, "script"):
                script = getattr(data, "script")
                field_name = "script"
            if isinstance(script, bytes):
                setattr(data, field_name, trans.encode("utf-8"))
            elif isinstance(script, bytearray):
                setattr(data, field_name, bytearray(trans.encode("utf-8")))
            else:
                setattr(data, field_name, trans)
            data.save()
            return True

        def apply_typetree_field(loc: dict, trans: str, entry: dict) -> bool:
            from vntext.patch_naninovel import set_by_field_path
            path_id = str(loc.get("path_id", "") or "")
            obj = get_obj(path_id)
            if obj is None:
                report.append(f"MISS {rel}:{path_id}: khong tim thay MonoBehaviour/TypeTree object")
                return False
            if path_id in typetree_cache:
                tree = typetree_cache[path_id]["tree"]
            else:
                tree = obj.read_typetree()
                typetree_cache[path_id] = {"obj": obj, "tree": tree, "dirty": False}
            if set_by_field_path(tree, loc.get("field_path", ""), trans):
                typetree_cache[path_id]["dirty"] = True
                return True
            report.append(f"SKIP {rel}:{path_id}: field_path khong set duoc {loc.get('field_path','')}")
            return False

        def apply_ui_typetree_field(loc: dict, trans: str, entry: dict) -> bool:
            """Patch a UI locator whose displayed value lives in a TypeTree."""
            from vntext.patch_naninovel import set_by_field_path
            from vntext.patch_readback import _get_typetree_value

            path_id = str(loc.get("path_id", "") or "")
            obj = get_obj(path_id)
            if obj is None:
                report.append(f"MISS {rel}:{path_id}: khong tim thay UI TypeTree object")
                return False
            if path_id in typetree_cache:
                tree = typetree_cache[path_id]["tree"]
            else:
                try:
                    tree = obj.read_typetree()
                except Exception as exc:
                    report.append(f"SKIP {rel}:{path_id}: UI TypeTree read failed: {exc}")
                    return False
                typetree_cache[path_id] = {"obj": obj, "tree": tree, "dirty": False}
            field_path = str(loc.get("field_path", "") or "")
            source = str(entry.get("source_text", "") or "")
            if _get_typetree_value(tree, field_path) != source:
                report.append(
                    f"SKIP {rel}:{path_id}: UI TypeTree source precondition failed for {field_path}"
                )
                return False
            if set_by_field_path(tree, field_path, trans):
                typetree_cache[path_id]["dirty"] = True
                return True
            report.append(f"SKIP {rel}:{path_id}: UI TypeTree field cannot be set {field_path}")
            return False

        def apply_unity_localization_field(loc: dict, trans: str, entry: dict) -> bool:
            from vntext.unity_localization import (
                get_unity_localization_entry_id,
                is_unity_localization_table_class,
                set_unity_localization_field,
            )

            path_id = str(loc.get("path_id", "") or "")
            obj = get_obj(path_id)
            if obj is None:
                report.append(f"MISS {rel}:{path_id}: khong tim thay Unity Localization StringTable")
                return False
            if not is_unity_localization_table_class(str(loc.get("class_name", "") or "")) or str(
                loc.get("table_kind", "") or ""
            ) != "StringTable":
                report.append(f"SKIP {rel}:{path_id}: Unity Localization locator identity khong hop le")
                return False
            object_class = _mono_class_name(obj)
            if not is_unity_localization_table_class(object_class):
                report.append(
                    f"SKIP {rel}:{path_id}: Unity Localization object class identity khong hop le ({object_class or 'unknown'})"
                )
                return False
            if path_id in typetree_cache:
                tree = typetree_cache[path_id]["tree"]
            else:
                tree = obj.read_typetree()
                typetree_cache[path_id] = {"obj": obj, "tree": tree, "dirty": False}
            source = str(entry.get("source_text", "") or "")
            field_path = str(loc.get("field_path", "") or "")
            if "entry_id" in loc:
                current_id = get_unity_localization_entry_id(tree, field_path)
                if current_id is None or str(current_id) != str(loc.get("entry_id")):
                    report.append(
                        f"SKIP {rel}:{path_id}: Unity Localization entry identity drift for {field_path}"
                    )
                    return False
            if set_unity_localization_field(tree, field_path, source, trans):
                typetree_cache[path_id]["dirty"] = True
                return True
            report.append(
                f"SKIP {rel}:{path_id}: Unity Localization source precondition failed for {field_path}"
            )
            return False

        for entry, trans in items:
            method = entry.get("import_method")
            backend = entry.get("backend", method)
            locators = iter_patch_locators(entry)
            if str(trans) == str(entry.get("source_text") or ""):
                # An intentional keep must preserve the serialized source
                # byte-for-byte.  Do not run a writer that may normalize line
                # padding or aligned-string slots; the file is still copied
                # below so strict read-back can detect stale locators.
                continue
            if len(locators) > 1:
                duplicate_patch_locations += len(locators) - 1
            try:
                if method in {"raw_review_only", "external_dump_reimport", "review_only"}:
                    for _loc in locators:
                        report.append(f"SKIP {rel}: method {method} chi de lay text, khong patch tu dong")
                    skipped_count += len(locators)
                    inc_backend(backend_counts, backend, "skipped", len(locators))
                    continue
                if method == "raw_fixed_slot":
                    for _loc in locators:
                        report.append(f"SKIP {rel}: method {method} la raw/debug, khong patch byte-slot: {entry.get('source_text','')[:80]}")
                    skipped_count += len(locators)
                    inc_backend(backend_counts, backend, "skipped", len(locators))
                    continue
                if method in {
                    "naninovel_blob_string",
                    "naninovel_raw_candidate",
                    "naninovel_script_string",
                    "naninovel_choice",
                    "naninovel_print",
                }:
                    # resources.assets Script objects may grow; unity_fs rebuilds
                    # object-data + directory (VH-compatible). Still skip raw blob
                    # candidates that lack path_id scoping (too unsafe).
                    source = str(entry.get("source_text", "") or "")
                    if source.lstrip().startswith("@"):
                        displays = [item for item in iter_naninovel_display_texts(source) if item]
                        source = displays[0] if displays else ""
                    if not source:
                        skipped_count += len(locators)
                        inc_backend(backend_counts, backend, "skipped", len(locators))
                        continue
                    if method in {"naninovel_blob_string", "naninovel_raw_candidate"}:
                        rel_l = str(rel).replace("\\", "/").lower()
                        if rel_l.endswith("data.unity3d") or rel_l.endswith("resources.assets"):
                            # Unscoped raw blob scans on resources.assets remain blocked.
                            skipped_count += len(locators)
                            inc_backend(backend_counts, backend, "skipped", len(locators))
                            report.append(
                                f"SKIP {rel}: naninovel raw blob disabled on resources.assets "
                                f"key={str(entry.get('key',''))[:16]}"
                            )
                            continue
                    if source and trans:
                        pids = []
                        for loc in locators or [entry.get("locator") or {}]:
                            pid = str((loc or {}).get("path_id", "") or "")
                            if pid:
                                pids.append(pid)
                        if pids:
                            for pid in pids:
                                naninovel_by_pid.setdefault(pid, {})[source] = trans
                        elif len(source) >= 16 and method == "naninovel_script_string":
                            naninovel_global[source] = trans
                        else:
                            skipped_count += len(locators)
                            inc_backend(backend_counts, backend, "skipped", len(locators))
                            continue
                    continue
                if method == "unity_ui_text":
                    source = str(entry.get("source_text", "") or "")
                    if not source or not trans:
                        skipped_count += len(locators)
                        inc_backend(backend_counts, backend or "unity_ui_object", "skipped", len(locators))
                        continue
                    queued = 0
                    for loc in locators:
                        pid = str((loc or {}).get("path_id", "") or "")
                        if pid:
                            field_path = str((loc or {}).get("field_path", "") or "")
                            # Raw aligned-string UI objects use the stable
                            # m_Text locator. Nested Dropdown/ManagedTextProvider
                            # values are TypeTree fields and must keep their
                            # exact path_id + field_path for a symmetric write.
                            if field_path in {"m_Text", "m_text", "text"}:
                                ui_by_pid.setdefault(pid, {})[source] = trans
                            else:
                                ui_typetree_by_pid.setdefault(pid, []).append(
                                    (dict(loc), source, trans, entry)
                                )
                            queued += 1
                        else:
                            skipped_count += 1
                            inc_backend(backend_counts, backend or "unity_ui_object", "skipped", 1)
                    if not queued:
                        report.append(
                            f"SKIP {rel}: unity_ui_text missing path_id key={str(entry.get('key',''))[:16]}"
                        )
                    continue
                if method in {"unity_typetree_field"}:
                    from vntext.patchability import assess_entry

                    symmetry = assess_entry(entry, require_proof=True)
                    if not symmetry.eligible:
                        skipped_count += len(locators)
                        inc_backend(backend_counts, backend, "skipped", len(locators))
                        report.append(
                            f"SKIP {rel}: unity_typetree_field symmetry gate: {symmetry.reason}"
                        )
                        continue
                    loc0 = locators[0] if locators else (entry.get("locator") or {})
                    field_path = str((loc0 or {}).get("field_path", "") or entry.get("context", "") or "")
                    if not is_ui_text_field(field_path) and not _typetree_field_is_display_text(field_path):
                        skipped_count += len(locators)
                        inc_backend(backend_counts, backend, "skipped", len(locators))
                        continue
                    ok_count = 0
                    for loc in locators:
                        if apply_typetree_field(loc, trans, entry):
                            ok_count += 1
                    changed += ok_count
                    unity_changed += ok_count
                    skipped_count += len(locators) - ok_count
                    inc_backend(backend_counts, backend, "patched", ok_count)
                    inc_backend(backend_counts, backend, "skipped", len(locators) - ok_count)
                    continue
                if method == "unity_localization_string":
                    from vntext.patchability import assess_entry

                    symmetry = assess_entry(entry, require_proof=True)
                    if not symmetry.eligible:
                        skipped_count += len(locators)
                        inc_backend(backend_counts, backend, "skipped", len(locators))
                        report.append(
                            f"SKIP {rel}: unity_localization_string symmetry gate: {symmetry.reason}"
                        )
                        continue
                    ok_count = 0
                    for loc in locators:
                        if apply_unity_localization_field(loc, trans, entry):
                            ok_count += 1
                    changed += ok_count
                    unity_changed += ok_count
                    skipped_count += len(locators) - ok_count
                    inc_backend(backend_counts, backend, "patched", ok_count)
                    inc_backend(backend_counts, backend, "skipped", len(locators) - ok_count)
                    continue
                if method == "unity_textasset_script":
                    ok_count = 0
                    for loc in locators:
                        if apply_textasset_script(loc, trans, entry):
                            ok_count += 1
                    changed += ok_count
                    unity_changed += ok_count
                    skipped_count += len(locators) - ok_count
                    inc_backend(backend_counts, backend, "patched", ok_count)
                    inc_backend(backend_counts, backend, "skipped", len(locators) - ok_count)
                    continue
                if method == "unity_textasset_table_cell":
                    ok_count = 0
                    for loc in locators:
                        if apply_textasset_table_cell(loc, trans, entry):
                            ok_count += 1
                    changed += ok_count
                    unity_changed += ok_count
                    skipped_count += len(locators) - ok_count
                    inc_backend(backend_counts, backend, "patched", ok_count)
                    inc_backend(backend_counts, backend, "skipped", len(locators) - ok_count)
                    continue
                if method == "unity_textasset_line":
                    ok_count = 0
                    for loc in locators:
                        if apply_textasset_line(loc, trans, entry):
                            ok_count += 1
                    changed += ok_count
                    unity_changed += ok_count
                    skipped_count += len(locators) - ok_count
                    inc_backend(backend_counts, backend, "patched", ok_count)
                    inc_backend(backend_counts, backend, "skipped", len(locators) - ok_count)
                    continue
                report.append(f"SKIP {rel}: method {method} khong import tu dong")
                skipped_count += len(locators)
                inc_backend(backend_counts, backend, "skipped", len(locators))
            except Exception as exc:
                report.append(f"SKIP {rel}: loi khi patch '{entry.get('source_text','')[:60]}': {exc}")
                skipped_count += len(locators)
                inc_backend(backend_counts, backend, "skipped", len(locators))

        ui_typetree_changed = 0
        ui_typetree_miss = 0
        if env is not None and ui_typetree_by_pid:
            # Queue nested UI fields before the shared TypeTree flush below.
            # Otherwise the cache would be populated after its only flush and
            # the apparent patch would never reach the serialized file.
            for _pid, loc_items in ui_typetree_by_pid.items():
                for loc, _source, trans, entry in loc_items:
                    if apply_ui_typetree_field(loc, trans, entry):
                        ui_typetree_changed += 1
                    else:
                        ui_typetree_miss += 1
            report.append(
                f"UI TypeTree {rel}: {ui_typetree_changed}/"
                f"{sum(len(items) for items in ui_typetree_by_pid.values())}"
            )

        # Flush cached TextAsset and TypeTree changes once per object, UABEA-style.
        if textasset_cache:
            for path_id, state in textasset_cache.items():
                if not state.get("dirty"):
                    continue
                new_text = "".join(state["lines"])
                obj = state.get("obj")
                orig_size = int(state.get("orig_size") or 0)
                orig_raw = state.get("orig_raw") or b""
                # Prefer raw script rewrite that keeps the TextAsset object slot size
                # (resources.assets cannot grow objects without a dangerous full repack).
                if not allow_unityfs_growth:
                    fitted = _fit_textasset_script_to_slot(
                        state.get("orig_script_text") or "",
                        new_text,
                    )
                    if fitted is not None and obj is not None and orig_raw:
                        new_raw = _replace_textasset_script_bytes(orig_raw, fitted.encode("utf-8"))
                        if new_raw is not None and len(new_raw) == orig_size:
                            obj.set_raw_data(new_raw)
                            continue
                if state["was_bytes"]:
                    setattr(state["data"], state["field_name"], new_text.encode("utf-8"))
                else:
                    setattr(state["data"], state["field_name"], new_text)
                state["data"].save()
                # Direct SerializedFile resources may not grow safely through the
                # regular UnityPy save route. UnityFS files are different: the
                # metadata-preserving writer below rebuilds object data and the
                # directory, so a larger serialized object is safe to retain.
                if obj is not None and orig_size > 0 and getattr(obj, "data", None) is not None:
                    new_raw = bytes(obj.data)
                    if len(new_raw) > orig_size and not allow_unityfs_growth:
                        obj.set_raw_data(orig_raw if len(orig_raw) == orig_size else orig_raw[:orig_size])
                        report.append(
                            f"SKIP {rel}:{path_id}: TextAsset grew {len(new_raw)}>{orig_size}; "
                            "kept original (layout-safe)"
                        )
                        skipped_count += 1
                    elif len(new_raw) < orig_size and not allow_unityfs_growth:
                        obj.set_raw_data(new_raw + (b"\x00" * (orig_size - len(new_raw))))
        if typetree_cache:
            for path_id, state in typetree_cache.items():
                if state.get("dirty"):
                    state["obj"].save_typetree(state["tree"])
                    obj = state["obj"]
                    # Keep the direct SerializedFile growth guard. UnityFS is
                    # written by the metadata-preserving rebuild path, which can
                    # update grown object data and the object directory safely.
                    if getattr(obj, "data", None) is not None and int(getattr(obj, "byte_size", 0) or 0) > 0:
                        slot = int(obj.byte_size)
                        new_raw = bytes(obj.data)
                        if len(new_raw) > slot and not allow_unityfs_growth:
                            obj.data = None
                            report.append(
                                f"SKIP {rel}:{getattr(obj, 'path_id', '')}: typetree grew; kept original"
                            )
                        elif len(new_raw) < slot and not allow_unityfs_growth:
                            obj.set_raw_data(new_raw + (b"\x00" * (slot - len(new_raw))))

        if env is not None and (naninovel_by_pid or naninovel_global):
            emit(f"Dang patch Naninovel Script trong {rel}...", bump=False)
            nano_changed = patch_naninovel_scripts_in_env(env, naninovel_by_pid, naninovel_global)
            if nano_changed:
                changed += nano_changed
                unity_changed += nano_changed
                inc_backend(backend_counts, "naninovel_script_object", "patched", nano_changed)
                report.append(f"NANINOVEL {rel}: patched {nano_changed} string slots in Script objects")
            else:
                missed = sum(len(v) for v in naninovel_by_pid.values()) + len(naninovel_global)
                skipped_count += missed
                inc_backend(backend_counts, "naninovel_script_object", "skipped", missed)
                report.append(f"NANINOVEL {rel}: 0 string slots patched")

        if env is not None and (ui_by_pid or ui_typetree_by_pid):
            emit(f"Dang patch UI/TMP trong {rel}...", bump=False)
            ui_changed = ui_typetree_changed
            ui_miss = ui_typetree_miss
            for pid, repl in ui_by_pid.items():
                remaining = dict(repl)
                for obj in get_objs(pid):
                    if _mono_class_name(obj) == "Script":
                        continue
                    # Unity player-backed Text/TMP objects are serialized
                    # component payloads.  Keep the first pass fixed-slot so
                    # shorter labels do not change the serialized field
                    # layout.  A second raw pass is reserved for genuine
                    # overflow; save_unity_env then rebuilds only object data
                    # while preserving the original metadata/type records.
                    n = patch_object_length_prefixed_strings(
                        obj,
                        remaining,
                        preserve_slot_size=True,
                    )
                    if n:
                        ui_changed += n
                        _pop_patched_ui_sources(remaining, obj)
                    if remaining:
                        n = patch_object_length_prefixed_strings(
                            obj,
                            remaining,
                            preserve_slot_size=False,
                        )
                        if n:
                            ui_changed += n
                            _pop_patched_ui_sources(remaining, obj)
                # A source that did not resolve on its exact path_id is a real
                # skipped locator; keep it visible instead of trying another
                # object in the bundle.
                ui_miss += len(remaining)
            if ui_changed:
                changed += ui_changed
                unity_changed += ui_changed
                inc_backend(backend_counts, "unity_ui_object", "patched", ui_changed)
                report.append(f"UI {rel}: patched {ui_changed} m_text/TMP string slots")
            if ui_miss:
                skipped_count += ui_miss
                inc_backend(backend_counts, "unity_ui_object", "skipped", ui_miss)
                report.append(
                    f"UI {rel}: {ui_miss} UI strings not applied; "
                    "fixed-slot-only policy (variable-size UI object rewrite disabled)"
                )

        if changed or raw_fixed_ops or raw_blob_ops or unity_changed or has_noop_translation:
            backup_original_file(src, backup_root, rel)
            if unity_changed:
                emit(f"Dang ghi UnityFS {rel} (file lon co the mat nhieu phut)...", bump=False)

                def save_progress(label):
                    emit(str(label), bump=False)

                save_unity_env(env, target, save_progress)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, target)
            raw_changed, raw_skipped = apply_raw_fixed_ops(target, raw_fixed_ops, report, rel, label="raw_fixed_slot")
            blob_changed, blob_skipped = apply_raw_fixed_ops(target, raw_blob_ops, report, rel, label="naninovel_blob_raw")
            inc_backend(backend_counts, "raw_fixed_slot", "patched", raw_changed)
            inc_backend(backend_counts, "raw_fixed_slot", "skipped", raw_skipped)
            inc_backend(backend_counts, "naninovel_blob_raw", "patched", blob_changed)
            inc_backend(backend_counts, "naninovel_blob_raw", "skipped", blob_skipped)
            changed += raw_changed + blob_changed
            skipped_count += raw_skipped + blob_skipped
            patched_count += changed
            from vntext.addressables_discovery import is_addressables_bundle_candidate
            if is_addressables_bundle_candidate(game_base, rel) and target.exists():
                patched_addressables.append((rel, target))
        report.append(f"UNITY {rel}: {changed}/{sum(len(iter_patch_locators(e)) for e, _t in items)}")

        if env is not None:
            del env
            env = None
            import gc

            gc.collect()

    if patched_addressables:
        emit("Dang cap nhat catalog Addressables...")
        from vntext.addressables_discovery import patch_catalogs_for_bundles_generic
        patch_catalogs_for_bundles_generic(game_base, patched_root, patched_addressables, report)

    emit("Dang ghi patch manifest / kiem tra patch...")

    out.mkdir(parents=True, exist_ok=True)
    # A fully fail-closed package is still a valid patch result: it must carry
    # its report/manifest and make the empty payload explicit instead of
    # crashing because no eligible row created COPY_TO_GAME_ROOT.
    patched_root.mkdir(parents=True, exist_ok=True)
    guide = """HUONG DAN CAI PATCH

Cach dung don gian:
  1. Dong game.
  2. Chay VNTextPatchInstaller.exe.
  3. Chon thu muc GOC cua game, cung cap voi file .exe va thu muc *_Data.
  4. Bam Kiem tra, sau do bam Cai dat. Cung installer nay co the Go cai dat.

Cach copy tay:
  Copy TOAN BO NOI DUNG ben trong thu muc COPY_TO_GAME_ROOT vao thu muc GOC cua game.
  Khong copy ca thu muc Patch_Viet_Hoa vao game.
  Khong copy vao trong thu muc *_Data them mot lan nua.
"""
    (out / "HUONG_DAN_CAI_PATCH.txt").write_text(guide, "utf-8")
    write_patch_manifest(out, game_base, "unknown")
    report_backend_coverage(report, backend_counts)
    verify_patched_translations(patched_root, by_file, report)
    verification = verify_patch_targets(
        patched_root,
        game_base,
        by_file,
        timeout_seconds=readback_timeout_seconds(),
    )
    verification_counts = verification.get("counts") or {}
    if verification.get("status") == READBACK_TIMEOUT or verification_counts.get(READBACK_TIMEOUT):
        verification_status = READBACK_TIMEOUT
    elif verification_counts.get(READBACK_FAIL) or verification_counts.get(READBACK_NOT_TESTABLE):
        verification_status = READBACK_FAIL if verification_counts.get(READBACK_FAIL) else READBACK_NOT_TESTABLE
    elif verification_counts.get(READBACK_PASS):
        verification_status = READBACK_PASS
    else:
        # An empty report is not evidence of a successful patch.  Keep this
        # explicit so the worker cannot treat a 54-file partial copy as PASS.
        verification_status = READBACK_FAIL
        verification["status"] = READBACK_FAIL
        verification["reason"] = "patch read-back produced no target results"
    verification["status"] = verification_status
    if verification_status == READBACK_FAIL and not verification.get("reason"):
        verification["reason"] = "one or more per-target read-back checks failed"
    elif verification_status == READBACK_NOT_TESTABLE and not verification.get("reason"):
        verification["reason"] = "one or more targets have no safe read-back route"
    write_patch_verification_report(out, verification)
    report.append(
        "VERIFY per_target_readback: "
        + ", ".join(
            f"{name}={count}"
            for name, count in sorted((verification.get("counts") or {}).items())
        )
    )
    report.append(f"patch_verification_status: {verification_status}")
    if verification.get("reason"):
        report.append(f"patch_verification_reason: {verification['reason']}")
    report.insert(0, f"patched_lines: {patched_count}")
    report.insert(1, f"skipped_lines: {skipped_count}")
    report.insert(2, f"duplicate_locations_patched_or_attempted: {duplicate_patch_locations}")
    report.insert(3, "Installer: VNTextPatchInstaller.exe; patch_manifest and original-hash backup are required.")
    (out / "import_report.txt").write_text("\n".join(report), "utf-8")
    emit("Xong tao patch", done=total_steps)
    return report

__all__ = ['apply_translation_package', 'detect_patch_engine']
