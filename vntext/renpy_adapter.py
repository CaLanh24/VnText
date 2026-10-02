"""Small, fail-closed Ren'Py engine boundary.

This module deliberately only identifies the supported loose-source surface.
Extraction and patching live behind this boundary so Unity discovery remains
unchanged.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


UNITY_MARKERS = ("*_Data",)


@dataclass(frozen=True)
class EngineDetection:
    engine: str
    status: str
    reason: str


def detect_engine(path: str | Path) -> EngineDetection:
    """Return a conservative engine classification without writing anything."""
    root = Path(path)
    if root.is_file():
        root = root.parent
    if not root.is_dir():
        return EngineDetection("UNKNOWN", "REVIEW_REQUIRED", "game folder does not exist")

    game = root / "game"
    loose = []
    compiled = []
    if game.is_dir():
        for candidate in game.rglob("*"):
            if not candidate.is_file():
                continue
            suffix = candidate.suffix.casefold()
            if suffix in {".rpy", ".rpym"}:
                loose.append(candidate)
            elif suffix in {".rpyc", ".rpymc"}:
                compiled.append(candidate)
    unity = any(root.glob("*_Data")) or any(root.glob("*.unity"))
    if unity and (loose or compiled):
        return EngineDetection("MIXED", "REVIEW_REQUIRED", "both Unity and Ren'Py evidence found")
    if loose:
        return EngineDetection("RENPY_LOOSE_SOURCE", "SUPPORTED", f"{len(loose)} loose Ren'Py script(s)")
    if compiled:
        return EngineDetection("RENPY_COMPILED_ONLY", "EXTRACT_ONLY", f"{len(compiled)} compiled Ren'Py script(s); auto patch unsupported")
    if unity:
        return EngineDetection("UNITY", "SUPPORTED", "Unity evidence found")
    return EngineDetection("UNKNOWN", "REVIEW_REQUIRED", "no strong Unity or Ren'Py evidence")
