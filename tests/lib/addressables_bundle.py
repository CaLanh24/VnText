"""Inspect Addressables UnityFS .bundle children. Copy-only helper; no app writes."""

from __future__ import annotations

import sys
from pathlib import Path

def _tests_lib_on_path() -> None:
    cur = Path(__file__).resolve().parent
    while cur.name != "tests" and cur.parent != cur:
        cur = cur.parent
    lib = cur / "lib"
    p = str(lib)
    if p not in sys.path:
        sys.path.insert(0, p)

_tests_lib_on_path()
from bootstrap import bootstrap
TESTS, ROOT, LIB = bootstrap(__file__)

import os


from work_paths import resolve_game_folder

BUNDLE_REL_GLOB = "**/*.bundle"


def find_original_addressables_bundle(game_folder: Path | None = None) -> Path:
    game = None
    if game_folder is not None:
        game = Path(game_folder).resolve()
        matches = sorted(game.glob(BUNDLE_REL_GLOB))
        if matches:
            return matches[0]
    configured = os.environ.get("VNTEXT_ADDRESSABLES_BUNDLE", "").strip()
    if configured:
        candidate = Path(configured).expanduser().resolve()
        if candidate.is_file():
            return candidate
        raise FileNotFoundError(f"configured Addressables bundle not found: {candidate}")
    game = game or resolve_game_folder()
    matches = sorted(game.glob(BUNDLE_REL_GLOB))
    if not matches:
        raise FileNotFoundError(f"No Addressables bundle under {game / BUNDLE_REL_GLOB}")
    return matches[0]


def _is_serialized_file(child) -> bool:
    try:
        from UnityPy.files.SerializedFile import SerializedFile

        if isinstance(child, SerializedFile):
            return True
    except Exception:
        pass
    return hasattr(child, "objects") and hasattr(child, "header") and hasattr(child, "types")


def _child_size(child) -> int:
    length = int(getattr(child, "Length", 0) or 0)
    if length:
        return length
    reader = getattr(child, "reader", None)
    if reader is not None:
        length = int(getattr(reader, "Length", 0) or 0)
        if length:
            return length
        view = getattr(reader, "view", None)
        if view is not None:
            return len(view)
        data = getattr(reader, "bytes", None)
        if data is not None:
            return len(data)
    header = getattr(child, "header", None)
    file_size = getattr(header, "file_size", None) if header is not None else None
    if file_size:
        return int(file_size)
    return 0


def _first_bytes(child, count: int = 16) -> bytes:
    reader = getattr(child, "reader", child)
    view = getattr(reader, "view", None)
    if view is not None:
        return bytes(view[:count])
    data = getattr(reader, "bytes", None)
    if data is not None:
        return bytes(data[:count])
    if hasattr(reader, "read_bytes"):
        old = getattr(reader, "Position", None)
        try:
            reader.Position = 0
            return bytes(reader.read_bytes(count))
        finally:
            if old is not None:
                try:
                    reader.Position = old
                except Exception:
                    pass
    return b""


def inspect_child(name: str, child) -> dict:
    kind = "serialized_file" if _is_serialized_file(child) else "raw"
    header = _first_bytes(child, 16)
    info = {
        "name": str(name),
        "kind": kind,
        "type_name": type(child).__name__,
        "size": _child_size(child),
        "header_hex": header.hex(" "),
        "object_count": 0,
        "enable_type_tree": None,
    }
    if kind == "serialized_file":
        objects = getattr(child, "objects", None) or {}
        info["object_count"] = len(objects)
        info["enable_type_tree"] = bool(getattr(child, "_enable_type_tree", False))
    return info


def inspect_bundle(path: Path) -> dict:
    import UnityPy

    path = Path(path)
    env = UnityPy.load(str(path))
    root = env.file
    children = []
    files = getattr(root, "files", None) or {}
    for name, child in files.items():
        children.append(inspect_child(str(name), child))
    objects = list(getattr(env, "objects", []) or [])
    magic = path.read_bytes()[:7].decode("ascii", "replace")
    return {
        "path": str(path),
        "size": path.stat().st_size,
        "magic": magic,
        "unityfs_header_ok": magic == "UnityFS",
        "object_count": len(objects),
        "dataflags": int(getattr(root, "dataflags", 0) or 0),
        "block_info_flags": int(getattr(root, "_block_info_flags", 0) or 0),
        "cab_file": str(getattr(root, "cab_file", "") or ""),
        "children": children,
    }


if __name__ == "__main__":
    raise SystemExit("This helper is for explicit external Addressables fixtures; no default fixture is bundled.")
