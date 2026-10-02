"""Naninovel patch responsibilities."""

from __future__ import annotations

from vntext.patch_constants import (
    _NANO_SCRIPT_SKIP_TOKENS,
    _mono_class_name,
    _object_raw_bytes,
    _replace_text_in_naninovel_command,
    _scan_unity_length_prefixed_strings,
    find_aligned_unity_strings,
    find_aligned_unity_strings_containing,
    re,
)


def patch_naninovel_script_object(obj, replacements: dict[str, str]) -> int:
    """Patch Naninovel Script AlignedStrings via command-scoped edits only.

    Does not blind-replace every length-prefixed occurrence of a source token
    (that caused thousands of false hits). Only @print / @choice / @: command
    strings are rewritten; object growth is allowed (unity_fs rebuilds data).
    """
    from vntext.patch_plain import _apply_unity_length_prefixed_replacements
    if str(getattr(getattr(obj, "type", None), "name", "")) != "MonoBehaviour":
        return 0
    if _mono_class_name(obj) != "Script":
        return 0
    safe: dict[str, str] = {}
    for source, translated in (replacements or {}).items():
        src = str(source or "").strip()
        dst = str(translated or "")
        if not src or src == dst:
            continue
        if src.casefold() in _NANO_SCRIPT_SKIP_TOKENS:
            continue
        # Rows have already passed the patch gate and are path-scoped here;
        # short recovered dialogue/choice labels must not be dropped merely
        # because they are shorter than the old heuristic threshold.
        safe[src] = dst
    if not safe:
        return 0
    raw = _object_raw_bytes(obj)
    if not raw:
        return 0
    patch_items = []
    used_offsets: set[int] = set()
    patch_items_by_offset: dict[int, dict] = {}
    # 1) Command-scoped (@print/@choice/@:)
    for item in _scan_unity_length_prefixed_strings(raw, step=4, seeded=len(raw) > 512 * 1024):
        raw_text = str(item.get("text", ""))
        text = raw_text.strip()
        offset = int(item.get("offset", -1))
        if offset in used_offsets:
            continue
        if text.lstrip().startswith("@"):
            new_text = raw_text
            for source, translated in safe.items():
                updated = _replace_text_in_naninovel_command(new_text, source, translated)
                if updated != new_text:
                    new_text = updated
            if new_text != raw_text:
                patch_items.append({**item, "new_text": new_text})
                patch_items_by_offset[offset] = patch_items[-1]
                used_offsets.add(offset)
            continue
        # 2) Exact plain AlignedString equality (full string == source)
        key = text
        if key in safe:
            if offset in patch_items_by_offset:
                continue
            left = raw_text[: len(raw_text) - len(raw_text.lstrip())]
            right = raw_text[len(raw_text.rstrip()) :]
            patch_items.append({**item, "new_text": left + safe[key] + right})
            patch_items_by_offset[offset] = patch_items[-1]
            used_offsets.add(offset)
    # Some display values are nested in non-@ Naninovel commands (most
    # notably RandPick assignments) and therefore absent from the seeded
    # scan. Recover the containing aligned payload only for a source explicitly
    # selected for this Script path_id; never scan arbitrary raw substrings.
    fallback_items: dict[int, dict] = {}
    for source in safe:
        for item in find_aligned_unity_strings(raw, source):
            fallback_items.setdefault(int(item.get("offset", -1)), item)
        for item in find_aligned_unity_strings_containing(raw, source):
            fallback_items.setdefault(int(item.get("offset", -1)), item)

    def replace_fallback_text(raw_text: str) -> str:
        pick = re.search(r'RandPick\d*\(\s*"(?P<body>(?:\\.|[^"])*)"\s*\)', raw_text, re.I)
        if pick:
            body = pick.group("body")
            parts = []
            for part in body.split("@"):
                stripped = part.strip()
                translated = safe.get(stripped)
                if translated is None or translated == stripped:
                    parts.append(part)
                    continue
                left = part[: len(part) - len(part.lstrip())]
                right = part[len(part.rstrip()) :]
                parts.append(left + translated + right)
            updated_body = "@".join(parts)
            return raw_text[: pick.start("body")] + updated_body + raw_text[pick.end("body") :]
        stripped = raw_text.strip()
        translated = safe.get(stripped)
        if translated is not None and translated != stripped:
            left = raw_text[: len(raw_text) - len(raw_text.lstrip())]
            right = raw_text[len(raw_text.rstrip()) :]
            return left + translated + right
        # A non-RandPick aligned string is one extracted display value.  Do
        # not replace arbitrary substrings: that can mutate a longer no-op
        # row when another short source happens to be contained in it.
        return raw_text

    for offset, item in fallback_items.items():
        if offset in patch_items_by_offset:
            continue
        raw_text = str(item.get("text", ""))
        new_text = replace_fallback_text(raw_text)
        if new_text != raw_text:
            patch_items.append({**item, "new_text": new_text})
            patch_items_by_offset[offset] = patch_items[-1]
            used_offsets.add(offset)
    if not patch_items:
        return 0
    new_raw, changed = _apply_unity_length_prefixed_replacements(
        raw, patch_items, preserve_slot_size=False
    )
    if changed:
        obj.set_raw_data(new_raw)
    return changed


def patch_naninovel_scripts_in_env(env, by_pid: dict[str, dict[str, str]], global_repl: dict[str, str] | None = None) -> int:
    """Patch Script objects. Prefer path_id-scoped replacements to avoid corrupting other scripts."""
    changed = 0
    global_repl = global_repl or {}
    for obj in env.objects:
        pid = str(getattr(obj, "path_id", ""))
        local = dict(by_pid.get(pid) or {})
        if not local and not global_repl:
            continue
        if global_repl:
            raw = _object_raw_bytes(obj)
            if raw:
                present = {
                    str(item.get("text", "")).strip()
                    for item in _scan_unity_length_prefixed_strings(raw, step=4, seeded=len(raw) > 512 * 1024)
                }
                for source, translated in global_repl.items():
                    if source in present and source not in local:
                        local[source] = translated
        if local:
            changed += patch_naninovel_script_object(obj, local)
    return changed


def set_by_field_path(tree, field_path: str, value: str) -> bool:
    if not field_path:
        return False
    current = tree
    parts = re.findall(r"[^.\[\]]+|\[\d+\]", field_path)
    for part in parts[:-1]:
        if part.startswith("["):
            index = int(part[1:-1])
            if not isinstance(current, list) or index >= len(current):
                return False
            current = current[index]
        else:
            if not isinstance(current, dict) or part not in current:
                return False
            current = current[part]
    last = parts[-1] if parts else field_path
    if last.startswith("["):
        index = int(last[1:-1])
        if isinstance(current, list) and index < len(current) and isinstance(current[index], str):
            current[index] = value
            return True
    elif isinstance(current, dict) and isinstance(current.get(last), str):
        current[last] = value
        return True
    return False

__all__ = ['patch_naninovel_script_object', 'patch_naninovel_scripts_in_env', 'set_by_field_path']
