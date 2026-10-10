"""Small, fail-closed Ren'Py engine boundary.

This module deliberately only identifies the supported loose-source surface.
Extraction and patching live behind this boundary so Unity discovery remains
unchanged.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from vntext.renpy_archive import RenPyArchive, RenPyArchiveError


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
    archived_loose = []
    archive_errors = []
    if game.is_dir():
        for candidate in game.rglob("*"):
            if not candidate.is_file():
                continue
            suffix = candidate.suffix.casefold()
            if suffix in {".rpy", ".rpym"}:
                loose.append(candidate)
            elif suffix in {".rpyc", ".rpymc"}:
                compiled.append(candidate)
            elif suffix == ".rpa":
                try:
                    archive = RenPyArchive(candidate)
                    archived_loose.extend((candidate, member) for member in archive.members
                                          if Path(member).suffix.casefold() in {".rpy", ".rpym"})
                    compiled.extend(candidate for member in archive.members
                                    if Path(member).suffix.casefold() in {".rpyc", ".rpymc"})
                except (OSError, RenPyArchiveError) as exc:
                    archive_errors.append(f"{candidate.name}: {exc}")
    unity = any(root.glob("*_Data")) or any(root.glob("*.unity"))
    renpy_evidence = bool(loose or compiled or archived_loose or archive_errors)
    if unity and renpy_evidence:
        return EngineDetection("MIXED", "REVIEW_REQUIRED", "both Unity and Ren'Py evidence found")
    if archive_errors:
        return EngineDetection("RENPY_ARCHIVE_UNSUPPORTED", "REVIEW_REQUIRED", "; ".join(archive_errors[:3]))
    if archived_loose:
        return EngineDetection("RENPY_ARCHIVE_SOURCE", "SUPPORTED", f"{len(archived_loose)} source script(s) in supported RPA archives")
    if loose:
        return EngineDetection("RENPY_LOOSE_SOURCE", "SUPPORTED", f"{len(loose)} loose Ren'Py script(s)")
    if compiled:
        return EngineDetection("RENPY_COMPILED_ONLY", "EXTRACT_ONLY", f"{len(compiled)} compiled Ren'Py script(s); auto patch unsupported")
    if unity:
        return EngineDetection("UNITY", "SUPPORTED", "Unity evidence found")
    return EngineDetection("UNKNOWN", "REVIEW_REQUIRED", "no strong Unity or Ren'Py evidence")
