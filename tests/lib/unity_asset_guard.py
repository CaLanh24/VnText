"""Fail-fast guards before UnityPy.load for explicitly supplied assets."""
from __future__ import annotations

import gc
from pathlib import Path


def expected_data_unity3d_size(reference: Path | None = None) -> int:
    """Return an optional caller-provided reference size; never infer a game path."""
    if reference is None or not reference.is_file():
        return 0
    return int(reference.stat().st_size)


def assert_data_unity3d_ready(
    path: Path,
    *,
    label: str,
    expected_size: int | None = None,
    min_size: int = 1,
) -> int:
    if not path.is_file():
        raise AssertionError(f"{label}: thiếu file {path}")
    size = int(path.stat().st_size)
    expected = int(expected_size or 0)
    if expected and abs(size - expected) > max(4096, expected // 200):
        raise AssertionError(
            f"{label}: asset size={size} differs from supplied reference size={expected} "
            "(possible truncation/corruption)"
        )
    if size < max(1, int(min_size)):
        raise AssertionError(f"{label}: asset is too small ({size} bytes)")
    return size


def load_unity_environment(path: Path, *, label: str):
    import UnityPy

    assert_data_unity3d_ready(path, label=label)
    gc.collect()
    try:
        return UnityPy.load(str(path))
    except MemoryError as exc:
        size = path.stat().st_size if path.is_file() else 0
        raise AssertionError(
            f"{label}: UnityPy.load MemoryError trên {path} (size={size}). "
            f"Kiểm tra file gốc/trunc trước khi load."
        ) from exc
