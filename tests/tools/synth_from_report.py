"""Rebuild a stand-in game folder from an anonymous VNText bug report (report.json inside the zip, or the json itself).

The stand-in has the same folder structure, extensions, size classes, archive kinds and header markers, but stub contents, so engine detection, scans and
the journey can be replayed for a game nobody has.  Usage: python tests/tools/synth_from_report.py REPORT(.zip|.json) DEST_DIR
"""
from __future__ import annotations

import json
import sys
import zipfile
from pathlib import Path

STUB_CAP = 4096
SCRIPT = b'label start:\n    "Hello"\n    return\n'
RPYC = b"RENPY RPC2" + b"\0" * 64


def load(report_path: str | Path) -> dict:
    path = Path(report_path)
    if path.suffix.lower() == ".zip":
        with zipfile.ZipFile(path) as archive:
            return json.loads(archive.read("report.json"))
    return json.loads(path.read_text(encoding="utf-8"))


def _member_payload(extension: str) -> bytes:
    return SCRIPT if extension in {".rpy", ".rpym"} else RPYC if extension in {".rpyc", ".rpymc"} else b"x"


def _write_rpa(path: Path, summary: dict) -> None:
    from tests.unit.test_renpy_archive import write_rpa, write_rpa2
    members: dict[str, bytes] = {}
    for extension, count in (summary.get("extensions") or {}).items():
        ext = "" if extension == "(none)" else extension
        for index in range(min(int(count), 40)):
            members[f"m{index}{ext}"] = _member_payload(ext)
    if not members:
        members["m0.txt"] = b"x"
    (write_rpa2 if summary.get("version") == "2.0" else write_rpa)(path, members)


_CLASS_SIZE = {"lt1k": 512, "lt64k": 32 * 1024, "lt1m": 256 * 1024, "lt64m": 512 * 1024, "ge64m": 512 * 1024}


def _sizes(classes: dict) -> list[int]:
    out: list[int] = []
    for name, count in (classes or {}).items():
        out += [_CLASS_SIZE.get(name, 512)] * min(int(count), 12)
    return out or [16]


def _synth_unityfs(path: Path, shape: dict) -> None:
    import struct
    error = shape.get("error")
    if error and error.get("kind") == "bad_magic":
        path.write_bytes(b"NotUnity" + b"\0" * 64)
        return
    fmt = int(shape.get("format_version") or 6)
    blocks = _sizes(shape.get("block_uncompressed_classes"))
    entries = b"".join(struct.pack(">IIH", size, size, 0) for size in blocks)
    nodes = min(int(shape.get("nodes") or 1), 40)
    node_sizes = _sizes(shape.get("node_size_classes"))
    table = b"".join(struct.pack(">QQI", 0, node_sizes[i % len(node_sizes)], 4) + f"CAB-{i}".encode() + b"\0" for i in range(nodes))
    info = b"\0" * 16 + struct.pack(">I", len(blocks)) + entries + struct.pack(">I", nodes) + table
    flags = int(shape.get("flags") or 0) & ~0x3F & ~0x80          # block info stored plain: the table shape is what is replayed
    player = str(shape.get("player_version") or "5.x.x").encode()
    revision = b"r" * int(shape.get("engine_revision_len") or 1)
    prefix = b"UnityFS\0" + struct.pack(">I", fmt) + player + b"\0" + revision + b"\0"
    if error:        # keep the recorded header sizes so the parser meets the same inconsistency
        comp = int(shape.get("blocks_info_compressed") or len(info))
        info = info.ljust(comp, b"\0")[:comp]
        tail = struct.pack(">III", comp, int(shape.get("blocks_info_uncompressed") or comp), flags)
    else:
        tail = struct.pack(">III", len(info), len(info), flags)
    pad_to = len(prefix) + 8 + len(tail)
    padding = b"\0" * ((16 - pad_to % 16) % 16) if fmt >= 7 else b""
    total = pad_to + len(padding) + len(info) + sum(blocks)
    data = prefix + struct.pack(">Q", total) + tail + padding + info + b"\0" * sum(blocks)
    if error:
        # A parse failure is replayed by cutting the stand-in to the original file size, so the parser stops at the same place.
        data = data[: max(16, min(len(data), int(shape.get("file_size") or len(data))))]
    path.write_bytes(data)


def _synth_zip(path: Path, shape: dict) -> None:
    import zipfile
    if shape.get("error"):
        path.write_bytes(b"PK\3\4 broken archive")
        return
    methods = [int(m) for m, count in (shape.get("compression_methods") or {"8": 1}).items() for _ in range(max(1, int(count)))]
    sizes = _sizes(shape.get("size_classes"))
    extensions = list(shape.get("extensions") or {"(none)": 1})
    with zipfile.ZipFile(path, "w") as archive:
        for index in range(min(int(shape.get("entries") or 1), 60)):
            ext = extensions[index % len(extensions)]
            archive.writestr(zipfile.ZipInfo(f"m{index}" + ("" if ext == "(none)" else ext)), b"x" * sizes[index % len(sizes)],
                             compress_type=methods[index % len(methods)])


def _synth_serialized(path: Path, shape: dict) -> None:
    import struct
    version = int(shape.get("version") or 21)
    head = bytearray(64)
    struct.pack_into(">I", head, 8, version)
    flag = 0 if shape.get("endianness") == "little" else 1
    if version >= 22:
        head[16] = flag
        struct.pack_into(">I", head, 20, int(shape.get("metadata_size") or 0))
        struct.pack_into(">QQ", head, 24, int(shape.get("declared_size") or 64), int(shape.get("data_offset") or 64))
    else:
        struct.pack_into(">II", head, 0, int(shape.get("metadata_size") or 0), int(shape.get("declared_size") or 64))
        struct.pack_into(">I", head, 12, int(shape.get("data_offset") or 64))
        if version >= 9:
            head[16] = flag
    path.write_bytes(bytes(head))


def _synth_container(path: Path, shape: dict) -> bool:
    writer = {"unityfs": _synth_unityfs, "zip": _synth_zip, "serialized": _synth_serialized}.get(shape.get("kind"))
    if writer is None:
        return False
    writer(path, shape)
    return True


def synthesize(report: dict, dest: str | Path) -> Path:
    root = Path(dest)
    root.mkdir(parents=True, exist_ok=True)
    for entry in report["files"]:
        path = root / entry["path"]
        path.parent.mkdir(parents=True, exist_ok=True)
        suffix = path.suffix.casefold()
        rpa = entry.get("rpa")
        if isinstance(entry.get("container"), dict) and _synth_container(path, entry["container"]):
            continue
        if suffix == ".rpa" and isinstance(rpa, dict) and "members" in rpa:
            _write_rpa(path, rpa)
        elif suffix == ".rpa":
            path.write_bytes(b"RPA-3.0 nonsense\n")        # unreadable/skipped archive: the failure shape is what matters
        elif suffix in {".rpy", ".rpym"}:
            path.write_bytes(SCRIPT)
        elif suffix in {".rpyc", ".rpymc"}:
            path.write_bytes(RPYC if entry.get("header") == "RPC2" else b"other")
        elif suffix in {".ttf", ".otf", ".ttc"}:
            head = bytes.fromhex(entry["header"]) if entry.get("header") else b"\0\1\0\0"
            path.write_bytes(head + b"\0" * 28)
        elif suffix in {".exe", ".dll"}:
            path.write_bytes(b"MZ" + b"\0" * 62)
        else:
            path.write_bytes(b"\0" * min(int(entry.get("size") or 0), STUB_CAP))
    return root


def synthesize_native_blocks(report: dict) -> str:
    """Template text (one block per recorded unsupported Ren'Py native block) rebuilt from the masked shapes of a schema-2 report."""
    from vntext.shape_mask import rebuild_text
    blocks = []
    for sample in (report.get("structure") or {}).get("renpy_native_blocks", []):
        # The surrounding lines are kept as comments: they show the neighbourhood without becoming blocks of their own.
        def around(key):
            return "".join(f"## {line}" + chr(10) for line in rebuild_text(sample.get(key) or []).splitlines() if line.strip())
        blocks.append(around("context_before") + rebuild_text(sample.get("shape") or []) + around("context_after"))
    return "\n".join(blocks)


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print(__doc__)
        return 2
    root = synthesize(load(argv[1]), argv[2])
    print(f"stand-in layout written to {root}")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    raise SystemExit(main(sys.argv))
