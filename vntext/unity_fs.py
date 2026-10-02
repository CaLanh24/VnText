from __future__ import annotations

import struct
import tempfile
from pathlib import Path


def _reader_chunks(reader, size, chunk_size=1024 * 1024):
    old_pos = getattr(reader, "Position", None)
    try:
        reader.Position = 0
        remaining = int(size)
        while remaining > 0:
            chunk = bytes(reader.read_bytes(min(chunk_size, remaining)))
            if not chunk:
                raise EOFError(f"Unity child stream ended early; missing {remaining} bytes")
            remaining -= len(chunk)
            yield chunk
    finally:
        if old_pos is not None:
            try:
                reader.Position = old_pos
            except Exception:
                pass


def _file_chunks(stream, chunk_size=1024 * 1024):
    stream.seek(0)
    while True:
        chunk = stream.read(chunk_size)
        if not chunk:
            return
        yield bytes(chunk)


def _chunks_of(data: bytes, chunk_size=1024 * 1024):
    view = memoryview(data)
    for pos in range(0, len(view), chunk_size):
        yield bytes(view[pos:pos + chunk_size])


def _memory_view_chunks(reader, chunk_size=1024 * 1024):
    view = getattr(reader, "view", None)
    if view is None:
        data = bytes(reader.bytes)
        yield from _chunks_of(data, chunk_size)
        return
    for pos in range(0, len(view), chunk_size):
        yield bytes(view[pos:pos + chunk_size])


def _original_child_bytes(child) -> bytes:
    reader = getattr(child, "reader", None)
    if reader is not None and hasattr(reader, "bytes"):
        return bytes(reader.bytes)
    if hasattr(child, "bytes"):
        return bytes(child.bytes)
    length = int(getattr(child, "Length", 0) or 0)
    if length and hasattr(child, "read_bytes"):
        old_pos = getattr(child, "Position", None)
        try:
            child.Position = 0
            return bytes(child.read_bytes(length))
        finally:
            if old_pos is not None:
                child.Position = old_pos
    raise RuntimeError(f"Cannot read original Unity child bytes: {getattr(child, 'name', type(child))}")


def _is_serialized_file(child) -> bool:
    try:
        from UnityPy.files.SerializedFile import SerializedFile
        return isinstance(child, SerializedFile)
    except Exception:
        return hasattr(child, "objects") and hasattr(child, "header") and hasattr(child, "types")


def _object_has_new_data(obj) -> bool:
    return getattr(obj, "data", None) is not None


def _skip_type_tree_blob(raw: bytes, pos: int, endian: str, version: int) -> int:
    node_count = struct.unpack_from(endian + "i", raw, pos)[0]
    stringbuffer_size = struct.unpack_from(endian + "i", raw, pos + 4)[0]
    pos += 8
    node_fmt = endian + "hBBIIiii" + ("Q" if version >= 19 else "")
    node_size = struct.calcsize(node_fmt)
    blob_size = node_size * node_count + stringbuffer_size
    if node_count < 0 or stringbuffer_size < 0 or pos + blob_size > len(raw):
        raise ValueError("Invalid TypeTree blob while preserving SerializedFile metadata")
    return pos + blob_size


def _skip_type_tree_legacy(raw: bytes, pos: int, endian: str, version: int) -> int:
    def skip_node(p: int) -> int:
        p = raw.index(b"\x00", p) + 1
        p = raw.index(b"\x00", p) + 1
        p += 4  # byteSize
        if version == 2:
            p += 4
        if version != 3:
            p += 4  # index
        p += 8  # typeFlags + version
        if version != 3:
            p += 4  # metaFlag
        children = struct.unpack_from(endian + "i", raw, p)[0]
        p += 4
        for _ in range(children):
            p = skip_node(p)
        return p

    return skip_node(pos)


def _skip_serialized_types(raw: bytes, pos: int, child) -> int:
    header = child.header
    endian = header.endian
    version = header.version
    enable_type_tree = bool(getattr(child, "_enable_type_tree", False))
    for typ in child.types:
        pos += 4  # class_id
        if version >= 16:
            pos += 1  # is_stripped_type
        if version >= 17:
            pos += 2  # script_type_index
        if version >= 13:
            class_id = int(getattr(typ, "class_id", 0) or 0)
            if (version < 16 and class_id < 0) or (version >= 16 and class_id == 114):
                pos += 16  # script_id
            pos += 16  # old_type_hash
        if enable_type_tree:
            if version >= 12 or version == 10:
                pos = _skip_type_tree_blob(raw, pos, endian, version)
            else:
                pos = _skip_type_tree_legacy(raw, pos, endian, version)
            if version >= 21:
                dep_count = struct.unpack_from(endian + "i", raw, pos)[0]
                pos += 4 + 4 * dep_count
    return pos


def _patch_object_directory(meta: bytearray, child, updates: dict[int, tuple[int, int]]) -> None:
    """Patch byte_start/byte_size in the original object directory. Keep type metadata intact."""
    header = child.header
    endian = header.endian
    version = header.version
    if version >= 22:
        raise ValueError("SerializedFile version 22+ is not using metadata-preserving rewrite")
    pos = 20  # v9-21 header: 4*u32 + endian + 3 reserved
    z = meta.index(b"\x00", pos)
    pos = z + 1  # unity version
    pos += 4  # target platform
    if version >= 13:
        pos += 1  # enable type tree
    type_count = struct.unpack_from(endian + "i", meta, pos)[0]
    pos += 4
    if type_count != len(child.types):
        raise ValueError(f"Type count mismatch: file={type_count} parsed={len(child.types)}")
    pos = _skip_serialized_types(meta, pos, child)
    if 7 <= version < 14:
        pos += 4  # big_id_enabled
    obj_count = struct.unpack_from(endian + "i", meta, pos)[0]
    pos += 4
    if obj_count != len(child.objects):
        raise ValueError(f"Object count mismatch: file={obj_count} parsed={len(child.objects)}")
    seen = set()
    for _ in range(obj_count):
        pos += (4 - (pos % 4)) % 4
        path_id = struct.unpack_from(endian + "q", meta, pos)[0]
        pos += 8
        if path_id in updates:
            rel_start, size = updates[path_id]
            struct.pack_into(endian + "I", meta, pos, int(rel_start))
            struct.pack_into(endian + "I", meta, pos + 4, int(size))
            seen.add(path_id)
        pos += 12  # byte_start, byte_size, type_id
    missing = set(updates) - seen
    if missing:
        raise ValueError(f"Object directory missing path_id updates: {len(missing)}")


def _rewrite_serialized_file_inplace(child, original: bytes) -> bytes | None:
    """Patch dirty objects in-place when every new blob fits the original slot.

    Avoids moving ~16k objects in resources.assets (which has triggered Unity
    'resources.assets is corrupted / Position out of bounds' after deep play).
    Returns None when any object grows and a full repack is required.
    """
    dirty: list[tuple[int, int, bytes]] = []
    for obj in child.objects.values():
        if not _object_has_new_data(obj):
            continue
        blob = bytes(obj.data)
        slot = int(obj.byte_size)
        if slot <= 0 or obj.byte_start < 0:
            return None
        if len(blob) > slot:
            return None
        if len(blob) < slot:
            blob = blob + (b"\x00" * (slot - len(blob)))
        end = int(obj.byte_start) + slot
        if end > len(original):
            return None
        dirty.append((int(obj.byte_start), slot, blob))
    if not dirty:
        return original
    out = bytearray(original)
    for start, slot, blob in dirty:
        out[start : start + slot] = blob
    return bytes(out)


def _rewrite_serialized_file_rebuild_data(child, original: bytes) -> bytes:
    """Rebuild object-data section; keep type metadata bytes identical.

    Matches a no-TypeTree resources.assets layout by data offset/object count,
    with an updated directory byte_start+byte_size, grown payloads and
    8-byte alignment.
    Does NOT regenerate TypeTrees (UnityPy SerializedFile.save does — unsafe).
    """
    header = child.header
    data_offset = int(header.data_offset)
    if data_offset <= 0 or data_offset > len(original):
        raise ValueError("Invalid SerializedFile data_offset")
    meta = bytearray(original[:data_offset])
    objects = sorted(child.objects.values(), key=lambda obj: (obj.byte_start, obj.path_id))
    data = bytearray()
    updates: dict[int, tuple[int, int]] = {}
    for obj in objects:
        if _object_has_new_data(obj):
            blob = bytes(obj.data)
        else:
            blob = original[obj.byte_start : obj.byte_start + obj.byte_size]
            if len(blob) != obj.byte_size:
                raise ValueError(f"Original object {obj.path_id} is truncated")
        pad = (8 - (len(data) % 8)) % 8
        if pad:
            data.extend(b"\x00" * pad)
        rel_start = len(data)
        data.extend(blob)
        updates[int(obj.path_id)] = (rel_start, len(blob))
    _patch_object_directory(meta, child, updates)
    file_size = data_offset + len(data)
    # SerializedFile header integers are always big-endian; metadata after that uses header.endian.
    struct.pack_into(">I", meta, 4, file_size)
    return bytes(meta) + bytes(data)


def rewrite_serialized_file_keep_metadata(child) -> bytes:
    """Rewrite object data only. Keep original type trees / type records byte-identical.

    Unity 2019 release builds ship resources.assets without TypeTrees. UnityPy's
    full SerializedFile.save() rewrites metadata and can make the player throw
    'Position out of bounds' before the menu appears. Addressables CABs ship
    with TypeTrees; those bytes are skipped and copied, never regenerated.

    For no-TypeTree files (resources.assets): prefer in-place when every dirty
    object fits. If any dirty object grows, rebuild the object-data section and
    patch the existing directory (same algorithm VH commercial builds use —
    meta size/data_offset stay fixed; only start/size fields and payloads change).
    Blind length-prefix edits are still forbidden at the patch.py layer.
    """
    original = _original_child_bytes(child)
    header = child.header
    if not getattr(child, "is_changed", False) and not any(
        _object_has_new_data(obj) for obj in child.objects.values()
    ):
        return original

    enable_type_tree = bool(getattr(child, "_enable_type_tree", False))
    inplace = _rewrite_serialized_file_inplace(child, original)
    if inplace is not None:
        return inplace
    # Growth required (fits failed). Rebuild data + directory for both TypeTree
    # and no-TypeTree files; never call UnityPy metadata regeneration.
    if not enable_type_tree:
        # Guard: only rebuild when at least one dirty blob actually grows.
        grew = False
        for obj in child.objects.values():
            if not _object_has_new_data(obj):
                continue
            if len(bytes(obj.data)) > int(obj.byte_size):
                grew = True
                break
        if not grew:
            # Dirty blobs shrank or equal but inplace failed for another reason —
            # still safe to rebuild (VH-compatible) rather than silently drop.
            pass
    return _rewrite_serialized_file_rebuild_data(child, original)


def _iter_child_payload(child, chunk_size=1024 * 1024):
    if _is_serialized_file(child):
        changed = getattr(child, "is_changed", False) or any(
            _object_has_new_data(obj) for obj in child.objects.values()
        )
        if changed:
            yield from _chunks_of(rewrite_serialized_file_keep_metadata(child), chunk_size)
            return
        reader = getattr(child, "reader", None)
        if reader is not None:
            yield from _memory_view_chunks(reader, chunk_size)
            return
        yield from _chunks_of(_original_child_bytes(child), chunk_size)
        return
    reader = getattr(child, "reader", child)
    length = int(getattr(reader, "Length", 0) or getattr(child, "Length", 0) or 0)
    if length and hasattr(reader, "read_bytes"):
        yield from _reader_chunks(reader, length, chunk_size)
        return
    view = getattr(reader, "view", None)
    if view is not None:
        yield from _memory_view_chunks(reader, chunk_size)
        return
    yield from _chunks_of(_original_child_bytes(child), chunk_size)


def _compress_lz4(raw: bytes) -> bytes:
    import lz4.block
    packed = lz4.block.compress(raw, mode="high_compression", compression=9, store_size=False)
    return packed


def write_unityfs_lz4_streaming(root, target_path, progress_callback=None):
    """Rebuild UnityFS. Unchanged children keep original bytes.

    Some Unity data files use block-info-after-header (flag 0x40|0x03), not
    BlocksInfoAtTheEnd. Matching the input layout avoids player load failures.
    """
    from UnityPy.helpers import CompressionHelper
    from UnityPy.streams import EndianBinaryWriter

    target_path = Path(target_path)
    target_path.parent.mkdir(parents=True, exist_ok=True)

    orig_data_flag = int(getattr(root, "dataflags", 0) or 0)
    orig_block_flag = int(getattr(root, "_block_info_flags", 0) or 0)
    data_flag = orig_data_flag or (0x40 | 0x02)
    data_flag |= 0x40
    # Never write encrypted bundles; keep original block-info placement.
    data_flag &= ~0x1400
    block_flag = orig_block_flag or 0x02
    block_flag &= ~0x1400
    if (block_flag & 0x3F) not in {0, 2, 3}:
        block_flag = (block_flag & ~0x3F) | 0x02
    if (data_flag & 0x3F) not in {0, 2, 3}:
        data_flag = (data_flag & ~0x3F) | 0x02

    block_size = 128 * 1024
    block_info = []
    files_meta = []
    pending = bytearray()
    data_offset = 0

    def write_block(dst, raw):
        raw = bytes(raw)
        packed = _compress_lz4(raw)
        # Per-block flags are compression only (0/2/3). Archive bits such as
        # 0x40 BlocksAndDirectoryInfoCombined belong on the UnityFS header.
        if len(packed) >= len(raw):
            dst.write(raw)
            block_info.append((len(raw), len(raw), 0))
        else:
            dst.write(packed)
            block_info.append((len(raw), len(packed), 3))

    def feed(dst, chunks):
        nonlocal pending
        for chunk in chunks:
            view = memoryview(chunk)
            pos = 0
            while pos < len(view):
                take = min(block_size - len(pending), len(view) - pos)
                pending.extend(view[pos:pos + take])
                pos += take
                if len(pending) == block_size:
                    write_block(dst, pending)
                    pending.clear()

    child_items = list(root.files.items())
    with tempfile.NamedTemporaryFile(prefix="vntext_unityfs_", suffix=".blocks", delete=False) as blocks_tmp:
        blocks_path = Path(blocks_tmp.name)
        for index, (name, child) in enumerate(child_items, start=1):
            if callable(progress_callback):
                try:
                    progress_callback(f"Dang ghi UnityFS {name} ({index}/{len(child_items)})")
                except Exception:
                    pass
            flags = int(getattr(child, "flags", 0) or 0)
            child_size = 0
            for chunk in _iter_child_payload(child):
                child_size += len(chunk)
                feed(blocks_tmp, (chunk,))
            files_meta.append((str(name), flags, data_offset, child_size))
            data_offset += child_size
        if pending:
            write_block(blocks_tmp, pending)
            pending.clear()
        blocks_tmp.flush()

    try:
        block_writer = EndianBinaryWriter(b"\x00" * 16)
        block_writer.write_int(len(block_info))
        for unpacked_size, packed_size, flags in block_info:
            block_writer.write_u_int(unpacked_size)
            block_writer.write_u_int(packed_size)
            block_writer.write_u_short(flags)
        block_writer.write_int(len(files_meta))
        for name, flags, offset, size in files_meta:
            block_writer.write_long(offset)
            block_writer.write_long(size)
            block_writer.write_u_int(flags)
            block_writer.write_string_to_null(name)
        block_raw = block_writer.bytes
        block_writer.dispose()
        info_switch = data_flag & 0x3F
        if info_switch in CompressionHelper.COMPRESSION_MAP:
            block_packed = CompressionHelper.COMPRESSION_MAP[info_switch](block_raw)
        else:
            block_packed = CompressionHelper.compress_lz4(block_raw)
            data_flag = (data_flag & ~0x3F) | 0x02

        with target_path.open("wb") as raw_out:
            writer = EndianBinaryWriter(raw_out)
            writer.write_string_to_null(str(root.signature))
            writer.write_u_int(int(root.version))
            writer.write_string_to_null(str(root.version_player))
            writer.write_string_to_null(str(root.version_engine))
            header_pos = writer.Position
            writer.write_long(0)
            writer.write_u_int(len(block_packed))
            writer.write_u_int(len(block_raw))
            writer.write_u_int(data_flag)
            if getattr(root, "_uses_block_alignment", False) or int(root.version) >= 7:
                writer.align_stream(16)
            if data_flag & 0x80:
                with blocks_path.open("rb") as blocks_in:
                    while True:
                        chunk = blocks_in.read(1024 * 1024)
                        if not chunk:
                            break
                        raw_out.write(chunk)
                raw_out.write(block_packed)
            else:
                raw_out.write(block_packed)
                if data_flag & 0x200:
                    pad = (16 - (raw_out.tell() % 16)) % 16
                    if pad:
                        raw_out.write(b"\x00" * pad)
                with blocks_path.open("rb") as blocks_in:
                    while True:
                        chunk = blocks_in.read(1024 * 1024)
                        if not chunk:
                            break
                        raw_out.write(chunk)
            end_pos = raw_out.tell()
            raw_out.seek(header_pos)
            header_writer = EndianBinaryWriter(raw_out)
            header_writer.write_long(end_pos)
            header_writer.write_u_int(len(block_packed))
            header_writer.write_u_int(len(block_raw))
            header_writer.write_u_int(data_flag)
            raw_out.flush()
    finally:
        try:
            blocks_path.unlink(missing_ok=True)
        except TypeError:
            if blocks_path.exists():
                blocks_path.unlink()
    return target_path


def save_unity_environment(env, target_path, progress_callback=None):
    target_path = Path(target_path)
    target_path.parent.mkdir(parents=True, exist_ok=True)
    root = getattr(env, "file", None)
    if root is None:
        raise RuntimeError("UnityPy environment khong co root file de save.")
    signature = str(getattr(root, "signature", "") or "")
    if signature == "UnityFS":
        return write_unityfs_lz4_streaming(root, target_path, progress_callback)
    if callable(progress_callback):
        try:
            progress_callback("Dang ghi Unity asset...")
        except Exception:
            pass
    target_path.write_bytes(bytes(root.save()))
    return target_path
