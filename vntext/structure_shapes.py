"""Anonymous structure of Unity bundles / serialized files and ZIP-style archives: headers, version fields, block and entry tables, size classes and the place a
parse failed (relative offset + error kind).  Never file contents, never object or entry names (those only appear as a count)."""
from __future__ import annotations

import struct
import zipfile
from pathlib import Path

SHAPE_VERSION = 1
MAX_READ_BYTES = 512 * 1024 * 1024
SIZE_CLASSES = (("lt1k", 1024), ("lt64k", 64 * 1024), ("lt1m", 1024 ** 2), ("lt64m", 64 * 1024 ** 2))


def size_class(size: int) -> str:
    for name, limit in SIZE_CLASSES:
        if size < limit:
            return name
    return "ge64m"


def _classes(sizes) -> dict[str, int]:
    out: dict[str, int] = {}
    for size in sizes:
        key = size_class(int(size))
        out[key] = out.get(key, 0) + 1
    return dict(sorted(out.items()))


def _error(kind: str, offset: int, total: int, detail: str = "") -> dict:
    return {"kind": kind, "relative_offset": round(offset / total, 4) if total else 0.0, "offset": int(offset), "detail": detail[:80]}


def _cstring(data: bytes, pos: int) -> tuple[str, int]:
    end = data.index(b"\0", pos)
    return data[pos:end].decode("ascii", "replace"), end + 1


_COMPRESSION = {0: "none", 1: "lzma", 2: "lz4", 3: "lz4hc", 4: "lzham"}


def unityfs_shape(path: str | Path) -> dict:
    """Header and block/node tables of a UnityFS bundle."""
    path = Path(path)
    total = path.stat().st_size
    shape: dict = {"kind": "unityfs", "file_size": total}
    try:
        with path.open("rb") as stream:
            head = stream.read(4096)
            if not head.startswith(b"UnityFS\0"):
                shape["error"] = _error("bad_magic", 0, total)
                return shape
            pos = 8
            fmt = struct.unpack_from(">I", head, pos)[0]
            pos += 4
            player, pos = _cstring(head, pos)
            revision, pos = _cstring(head, pos)
            declared, comp_size, raw_size, flags = struct.unpack_from(">QIII", head, pos)
            pos += 20
            shape.update({"format_version": fmt, "player_version": player, "engine_revision_len": len(revision), "declared_size": declared,
                          "blocks_info_compressed": comp_size, "blocks_info_uncompressed": raw_size, "flags": flags,
                          "blocks_info_compression": _COMPRESSION.get(flags & 0x3F, f"unknown{flags & 0x3F}"), "blocks_info_at_end": bool(flags & 0x80)})
            if fmt >= 7:
                pos += (16 - pos % 16) % 16
            if declared != total:
                shape["size_mismatch"] = {"declared": declared, "actual": total}
            if comp_size > total or raw_size > MAX_READ_BYTES:
                shape["error"] = _error("blocks_info_out_of_range", pos, total)
                return shape
            if flags & 0x80:
                stream.seek(max(0, total - comp_size))
            else:
                stream.seek(pos)
            blob = stream.read(comp_size)
            if len(blob) != comp_size:
                shape["error"] = _error("truncated_blocks_info", pos, total)
                return shape
        mode = flags & 0x3F
        if mode == 0:
            info = blob
        elif mode in (2, 3):
            import lz4.block
            info = lz4.block.decompress(blob, uncompressed_size=raw_size)
        elif mode == 1:
            import lzma
            info = lzma.LZMADecompressor(format=lzma.FORMAT_ALONE).decompress(blob[:5] + struct.pack("<q", raw_size) + blob[5:])
        else:
            shape["error"] = _error("unsupported_blocks_info_compression", pos, total, str(mode))
            return shape
        cursor = 16
        count = struct.unpack_from(">I", info, cursor)[0]
        cursor += 4
        blocks, compression = [], {}
        for _ in range(count):
            raw, packed, block_flags = struct.unpack_from(">IIH", info, cursor)
            cursor += 10
            blocks.append((raw, packed))
            name = _COMPRESSION.get(block_flags & 0x3F, f"unknown{block_flags & 0x3F}")
            compression[name] = compression.get(name, 0) + 1
        nodes = struct.unpack_from(">I", info, cursor)[0]
        cursor += 4
        node_sizes = []
        for _ in range(nodes):
            _offset, size, _node_flags = struct.unpack_from(">QQI", info, cursor)
            cursor += 20
            _name, cursor = _cstring(info, cursor)
            node_sizes.append(size)
        shape.update({"blocks": count, "block_uncompressed_classes": _classes(b[0] for b in blocks), "block_compressed_classes": _classes(b[1] for b in blocks),
                      "block_compression": dict(sorted(compression.items())), "uncompressed_total": sum(b[0] for b in blocks), "nodes": nodes,
                      "node_size_classes": _classes(node_sizes)})
    except (struct.error, ValueError, IndexError, OSError, ImportError) as exc:
        shape["error"] = _error(type(exc).__name__, 0, total, str(exc))
    except Exception as exc:  # noqa: BLE001 - a decompressor failure is itself the evidence
        shape["error"] = _error(type(exc).__name__, 0, total, str(exc))
    return shape


def serialized_shape(path: str | Path) -> dict:
    """Header of a SerializedFile plus the class-id table (count and size classes per class) when UnityPy can read it."""
    path = Path(path)
    total = path.stat().st_size
    shape: dict = {"kind": "serialized", "file_size": total}
    try:
        with path.open("rb") as stream:
            head = stream.read(64)
        metadata_size, file_size, version, data_offset = struct.unpack_from(">IIII", head, 0)
        shape.update({"version": version, "metadata_size": metadata_size, "declared_size": file_size, "data_offset": data_offset})
        if version >= 22:
            metadata_size = struct.unpack_from(">I", head, 20)[0]
            file_size, data_offset = struct.unpack_from(">QQ", head, 24)
            shape.update({"metadata_size": metadata_size, "declared_size": file_size, "data_offset": data_offset, "endianness": "big" if head[16:17] == b"" else "little"})
        elif version >= 9:
            shape["endianness"] = "big" if head[16:17] == b"" else "little"
        if not 1 <= version <= 100 or shape["declared_size"] > total * 2 + 1024:
            shape["error"] = _error("implausible_header", 0, total, f"version={version}")
            return shape
        if total <= MAX_READ_BYTES:
            from vntext.unity_load import unity_load
            env = unity_load(path)
            classes: dict[int, list[int]] = {}
            for obj in env.objects:
                classes.setdefault(int(obj.type.value), []).append(int(obj.byte_size))
            shape["objects"] = sum(len(v) for v in classes.values())
            shape["classes"] = {str(k): {"count": len(v), "size_classes": _classes(v)} for k, v in sorted(classes.items())}
    except (struct.error, OSError, ImportError) as exc:
        shape["error"] = _error(type(exc).__name__, 0, total, str(exc))
    except Exception as exc:  # noqa: BLE001
        shape["error"] = _error(type(exc).__name__, 0, total, str(exc))
    return shape


def zip_shape(path: str | Path) -> dict:
    path = Path(path)
    total = path.stat().st_size
    shape: dict = {"kind": "zip", "file_size": total}
    try:
        with zipfile.ZipFile(path) as archive:
            infos = archive.infolist()
            methods: dict[str, int] = {}
            for info in infos:
                methods[str(info.compress_type)] = methods.get(str(info.compress_type), 0) + 1
            extensions: dict[str, int] = {}
            for info in infos:
                ext = Path(info.filename).suffix.casefold()[:8] or "(none)"
                extensions[ext] = extensions.get(ext, 0) + 1
            shape.update({"entries": len(infos), "compression_methods": dict(sorted(methods.items())), "extensions": dict(sorted(extensions.items())),
                          "size_classes": _classes(i.file_size for i in infos), "encrypted": sum(1 for i in infos if i.flag_bits & 1),
                          "directories": sum(1 for i in infos if i.is_dir()), "unicode_names": sum(1 for i in infos if any(ord(c) > 127 for c in i.filename))})
    except zipfile.BadZipFile as exc:
        shape["error"] = _error("BadZipFile", 0, total, str(exc))
    except (OSError, ValueError, NotImplementedError) as exc:
        shape["error"] = _error(type(exc).__name__, 0, total, str(exc))
    return shape


def shape_for(path: str | Path, header: bytes) -> dict | None:
    """The structure shape of ``path`` chosen by its first bytes, or None when it is no Unity/ZIP container."""
    if header.startswith(b"UnityFS\0"):
        return unityfs_shape(path)
    if header.startswith(b"PK\3\4") or header.startswith(b"PK\5\6"):
        return zip_shape(path)
    if Path(path).suffix.casefold() in {".assets", ".sharedassets", ".unity3d"} and len(header) >= 16:
        return serialized_shape(path)
    return None
