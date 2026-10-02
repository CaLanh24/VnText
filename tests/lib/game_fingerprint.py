"""Small generic file-fingerprint helpers for opt-in external-fixture tests."""
from __future__ import annotations

import hashlib
from pathlib import Path

def fingerprint_files(root: Path, relative_paths: list[str]) -> dict[str, str | None]:
    root = Path(root).resolve()
    result: dict[str, str | None] = {}
    for relative in relative_paths:
        path = root / relative
        if not path.is_file():
            result[relative] = None
            continue
        result[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result


def fingerprint_mismatches(root: Path, expected: dict[str, str | None]) -> list[dict]:
    """Return ``{path, expected, current}`` records for changed external files."""
    current = fingerprint_files(root, list(expected))
    out: list[dict] = []
    for relative, recorded in expected.items():
        if current.get(relative) != recorded:
            out.append({"path": relative, "expected": recorded, "current": current.get(relative)})
    return out


def original_game_fingerprint_ok(root: Path, expected: dict[str, str | None]) -> bool:
    return not fingerprint_mismatches(root, expected)
