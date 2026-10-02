"""Unity patch responsibilities."""

from __future__ import annotations

from vntext.patch_constants import (
    UI_MONO_CLASSES,
    _mono_class_name,
    _object_raw_bytes,
    _replace_text_in_naninovel_command,
    _scan_unity_length_prefixed_strings,
    find_aligned_unity_strings,
)


def patch_font_replacements_in_env(env, replacements: tuple[tuple[str, str], ...]) -> dict:
    """Apply explicit profile-owned Font payload replacements in one Unity env."""
    result = {"changed": 0, "source_objects": 0, "messages": [], "errors": []}
    if env is None or not replacements:
        return result

    fonts: dict[str, list] = {}
    for obj in getattr(env, "objects", ()):
        if str(getattr(getattr(obj, "type", None), "name", "") or "") != "Font":
            continue
        try:
            data = obj.read()
            name = str(getattr(data, "m_Name", "") or "").strip()
        except Exception as exc:
            result["errors"].append(f"Font object read failed: {type(exc).__name__}: {exc}")
            continue
        if name:
            fonts.setdefault(name.casefold(), []).append((name, obj, data))

    def payload_bytes(value) -> bytes:
        if value is None:
            return b""
        try:
            return bytes(value)
        except (TypeError, ValueError):
            return b""

    for source_name, target_name in replacements:
        source_name = str(source_name or "").strip()
        target_name = str(target_name or "").strip()
        source_items = fonts.get(source_name.casefold(), [])
        if not source_items:
            result["messages"].append(
                f"FONT source={source_name} target={target_name}: source_not_present"
            )
            continue
        result["source_objects"] += len(source_items)
        target_items = fonts.get(target_name.casefold(), [])
        if not target_items:
            result["errors"].append(
                f"FONT source={source_name} target={target_name}: target_not_present"
            )
            continue
        target_data = target_items[0][2]
        target_payload = getattr(target_data, "m_FontData", None)
        target_bytes = payload_bytes(target_payload)
        if not target_bytes:
            result["errors"].append(
                f"FONT source={source_name} target={target_name}: target_payload_empty"
            )
            continue

        changed = 0
        for _actual_name, source_obj, source_data in source_items:
            if payload_bytes(getattr(source_data, "m_FontData", None)) == target_bytes:
                continue
            try:
                current_payload = getattr(source_data, "m_FontData", None)
                if isinstance(current_payload, bytes):
                    source_data.m_FontData = bytes(target_payload)
                elif isinstance(current_payload, bytearray):
                    source_data.m_FontData = bytearray(target_payload)
                else:
                    source_data.m_FontData = list(target_payload)
                source_data.save()
            except Exception as exc:
                result["errors"].append(
                    f"FONT source={source_name} target={target_name}: save_failed "
                    f"{type(exc).__name__}: {exc}"
                )
                continue
            changed += 1
        result["changed"] += changed
        result["messages"].append(
            f"FONT source={source_name} target={target_name}: "
            f"source_objects={len(source_items)} changed={changed}"
        )
    return result


def patch_object_length_prefixed_strings(obj, replacements: dict[str, str], *, preserve_slot_size: bool = False) -> int:
    """UABEA-style import: ghi chuoi vao dung object, khong save_typetree toan MonoBehaviour."""
    from vntext.patch_plain import _apply_unity_length_prefixed_replacements
    if obj is None or not replacements:
        return 0
    raw = _object_raw_bytes(obj)
    if not raw:
        return 0
    by_source = {}
    for item in _scan_unity_length_prefixed_strings(raw, step=4, seeded=len(raw) > 512 * 1024):
        by_source.setdefault(str(item.get("text", "")).strip(), []).append(item)
    patch_items = []
    for source, translated in replacements.items():
        source = str(source or "").strip()
        translated = str(translated or "")
        if not source or not translated or source == translated:
            continue
        if source not in by_source:
            extra = find_aligned_unity_strings(raw, source)
            if extra:
                by_source[source] = extra
        for item in by_source.get(source, []):
            raw_text = str(item.get("text", ""))
            left = raw_text[: len(raw_text) - len(raw_text.lstrip())]
            right = raw_text[len(raw_text.rstrip()):]
            patch_items.append({
                **item,
                "new_text": left + translated + right,
            })
        if source not in by_source:
            for cmd_text, items in by_source.items():
                if not cmd_text.lstrip().startswith("@"):
                    if len(source) >= 10 and source in cmd_text:
                        for item in items:
                            patch_items.append({**item, "new_text": cmd_text.replace(source, translated, 1)})
                    continue
                for item in items:
                    raw_text = str(item.get("text", ""))
                    new_text = _replace_text_in_naninovel_command(raw_text, source, translated)
                    if new_text != raw_text:
                        patch_items.append({**item, "new_text": new_text})
    if not patch_items:
        return 0
    new_raw, changed = _apply_unity_length_prefixed_replacements(raw, patch_items, preserve_slot_size=preserve_slot_size)
    if changed:
        obj.set_raw_data(new_raw)
    return changed


def _pop_patched_ui_sources(replacements: dict[str, str], obj) -> int:
    """Remove sources already matching translated text on the Unity UI object."""
    if obj is None or not replacements:
        return 0
    # UnityPy can keep the object returned by ``read()`` cached after
    # ``set_raw_data``.  Inspect the current serialized bytes first so a
    # successful raw patch is not sent through the direct-field fallback a
    # second time (which can normalize/drop trailing whitespace).
    try:
        raw = _object_raw_bytes(obj)
        values = [
            str(item.get("text") or "")
            for item in _scan_unity_length_prefixed_strings(
                raw,
                step=4,
                seeded=len(raw) > 512 * 1024,
            )
            if item.get("text")
        ]
    except Exception:
        values = []
    if values:
        removed = 0
        for source, trans in list(replacements.items()):
            if str(trans or "") and any(str(trans) in value for value in values) and not any(
                str(source) in value for value in values
            ):
                replacements.pop(source, None)
                removed += 1
        return removed
    try:
        data = obj.read()
    except Exception:
        return 0
    removed = 0
    for attr in ("m_Text", "m_text", "text"):
        val = getattr(data, attr, None)
        if not isinstance(val, str):
            continue
        for source, trans in list(replacements.items()):
            if str(trans or "") and str(trans) in val and str(source or "") not in val:
                replacements.pop(source, None)
                removed += 1
    return removed


def patch_ui_text_fields_via_read(obj, replacements: dict[str, str]) -> int:
    """Fallback when raw slot-preserving patch cannot fit longer VI labels."""
    if obj is None or not replacements:
        return 0
    cls = _mono_class_name(obj) or str(getattr(getattr(obj, "type", None), "name", "") or "")
    if cls not in UI_MONO_CLASSES:
        return 0
    try:
        data = obj.read()
    except Exception:
        return 0
    changed = 0
    for attr in ("m_Text", "m_text", "text"):
        val = getattr(data, attr, None)
        if not isinstance(val, str) or not val.strip():
            continue
        stripped = val.strip()
        for source, trans in list(replacements.items()):
            source = str(source or "").strip()
            trans = str(trans or "")
            if not source or source not in val:
                continue
            if stripped == source:
                left = val[: len(val) - len(val.lstrip())]
                right = val[len(val.rstrip()) :]
                new_val = left + trans + right
            else:
                new_val = val.replace(source, trans, 1)
            if new_val == val:
                continue
            setattr(data, attr, new_val)
            replacements.pop(source, None)
            changed += 1
            break
    if changed:
        data.save()
    return changed

__all__ = [
    'patch_font_replacements_in_env',
    'patch_object_length_prefixed_strings',
    '_pop_patched_ui_sources',
    'patch_ui_text_fields_via_read',
]
