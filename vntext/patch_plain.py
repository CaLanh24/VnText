"""Plain patch responsibilities."""

from __future__ import annotations

from vntext.patch_constants import (
    _unity_string_padding,
    struct,
)


def _fit_textasset_script_to_slot(orig_text: str, new_text: str) -> str | None:
    """Keep UTF-8 script length <= original so TextAsset object slot need not grow.

    When VI labels need more bytes, shrink the Lorem PreviewText line first, then
    pad with trailing spaces if the result is shorter than the original.
    """
    orig_b = (orig_text or "").encode("utf-8")
    new_b = (new_text or "").encode("utf-8")
    if not orig_b:
        return None
    if len(new_b) <= len(orig_b):
        return new_text + (" " * (len(orig_b) - len(new_b)))
    # Shrink PreviewText / long filler lines.
    lines = new_text.splitlines(keepends=True)
    need = len(new_b) - len(orig_b)
    for i, line in enumerate(lines):
        raw = line.rstrip("\r\n")
        nl = line[len(raw) :]
        if "PreviewText:" not in raw and "Lorem ipsum" not in raw:
            continue
        if ": " not in raw:
            continue
        left, right = raw.split(": ", 1)
        if len(right.encode("utf-8")) <= need:
            continue
        # Drop `need` UTF-8 bytes from the value (not mid-codepoint).
        rb = right.encode("utf-8")
        cut = rb[: max(0, len(rb) - need)]
        while cut and (cut[-1] & 0xC0) == 0x80:
            cut = cut[:-1]
        try:
            right2 = cut.decode("utf-8")
        except UnicodeDecodeError:
            right2 = cut.decode("utf-8", errors="ignore")
        lines[i] = f"{left}: {right2}{nl}"
        new_text = "".join(lines)
        new_b = new_text.encode("utf-8")
        break
    if len(new_b) > len(orig_b):
        return None
    return new_text + (" " * (len(orig_b) - len(new_b)))


def _replace_textasset_script_bytes(orig_raw: bytes, new_script: bytes) -> bytes | None:
    """Replace m_Script byte payload inside a TextAsset object, keeping total size.

    Layout: AlignedString m_Name, then byte[] m_Script (int32 len + bytes + pad4).
    """
    if len(orig_raw) < 8:
        return None
    name_len = struct.unpack_from("<i", orig_raw, 0)[0]
    if name_len < 0 or name_len > 4096:
        return None
    name_pad = _unity_string_padding(name_len)
    script_len_off = 4 + name_len + name_pad
    if script_len_off + 4 > len(orig_raw):
        return None
    old_script_len = struct.unpack_from("<i", orig_raw, script_len_off)[0]
    if old_script_len < 0:
        return None
    script_start = script_len_off + 4
    script_pad = _unity_string_padding(old_script_len)
    script_end = script_start + old_script_len + script_pad
    if script_end > len(orig_raw):
        return None
    # Keep trailing bytes (if any) after the script field.
    tail = orig_raw[script_end:]
    new_pad = _unity_string_padding(len(new_script))
    rebuilt = (
        orig_raw[:script_len_off]
        + struct.pack("<i", len(new_script))
        + new_script
        + (b"\x00" * new_pad)
        + tail
    )
    if len(rebuilt) != len(orig_raw):
        # Adjust by changing script padding / trailing pad inside slot.
        if len(rebuilt) > len(orig_raw):
            return None
        rebuilt = rebuilt + (b"\x00" * (len(orig_raw) - len(rebuilt)))
    return rebuilt


def _apply_unity_length_prefixed_replacements(raw: bytes, items, *, preserve_slot_size: bool = False) -> tuple[bytes, int]:
    data = bytes(raw)
    valid = []
    for item in items:
        old_text = str(item.get("text", ""))
        new_text = str(item.get("new_text", ""))
        offset = int(item.get("offset", -1))
        old_len = int(item.get("byte_length", -1))
        if offset < 0 or old_len < 0 or not old_text or new_text == old_text:
            continue
        try:
            declared = struct.unpack_from("<i", data, offset)[0]
        except Exception:
            continue
        if declared != old_len:
            continue
        start = offset + 4
        end = start + old_len
        old_pad = _unity_string_padding(old_len)
        if end + old_pad > len(data):
            continue
        if old_pad and data[end : end + old_pad] != (b"\x00" * old_pad):
            continue
        old_payload = data[start:end]
        try:
            if old_payload.decode("utf-8") != old_text:
                continue
        except Exception:
            continue
        payload = new_text.encode("utf-8")
        if b"\x00" in payload:
            continue
        if preserve_slot_size:
            # Keep declared length + alignment pad identical to the original slot so
            # the next serialized field stays at the same absolute offset. Shorter
            # UTF-8 is space-padded inside the string body (not after the pad).
            slot_size = 4 + old_len + old_pad
            if len(payload) > old_len:
                continue
            if len(payload) < old_len:
                payload = payload + (b" " * (old_len - len(payload)))
            valid.append((offset, old_len, payload, old_pad, slot_size))
        else:
            valid.append((offset, old_len, payload, None, None))

    filtered = []
    spans = []
    for row in sorted(valid, key=lambda r: (r[0], -r[1])):
        offset, old_len, payload, new_pad, slot_size = row
        end = offset + 4 + old_len
        if any(span_start < offset < span_end for span_start, span_end in spans):
            continue
        filtered.append(row)
        spans.append((offset, end))

    changed = 0
    for offset, old_len, payload, new_pad_fixed, slot_size in sorted(filtered, key=lambda r: r[0], reverse=True):
        start = offset + 4
        end = start + old_len
        old_pad = _unity_string_padding(old_len)
        replace_end = end + old_pad
        if preserve_slot_size and new_pad_fixed is not None:
            # Length prefix stays old_len; payload already padded to old_len.
            if len(payload) != old_len:
                continue
            replacement = struct.pack("<i", old_len) + payload + (b"\x00" * new_pad_fixed)
            if len(replacement) != slot_size:
                continue
        else:
            new_pad = _unity_string_padding(len(payload))
            replacement = struct.pack("<i", len(payload)) + payload + (b"\x00" * new_pad)
        data = data[:offset] + replacement + data[replace_end:]
        changed += 1
    return data, changed

__all__ = ['_fit_textasset_script_to_slot', '_replace_textasset_script_bytes', '_apply_unity_length_prefixed_replacements']
