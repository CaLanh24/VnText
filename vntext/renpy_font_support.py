"""Language-scoped font styles from inert, bounded Ren'Py source inspection.

No game profiles, script evaluation, font download or original-file writes.
Only explicit text-font styles are selected; icon fonts and dynamic styles are
not rewritten. Ren'Py restores initialized styles when changing language.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import re

from vntext.renpy_archive import RenPyArchive
from vntext.renpy_language_support import render_language_support

FALLBACK_SHA256 = "3fdf69cabf06049ea70a00b5919340e2ce1e6d02b0cc3c4b44fb6801bd1e0d22"
MAX_SCRIPT_BYTES = 32 * 1024 * 1024
MAX_SCRIPTS = 4096
_STYLE = re.compile(r"^style ([A-Za-z_]\w*)(?: is [A-Za-z_]\w*)?:\s*(?:#.*)?$")
_TEXT_FONT = re.compile(r"^font\s+gui\.[A-Za-z_]\w*_font\s*(?:#.*)?$")
_TEXT_PROPERTIES = re.compile(r'''^properties\s+gui\.text_properties\(["'][A-Za-z_]\w*["'](?:,\s*accent\s*=\s*(?:True|False))?\)\s*(?:#.*)?$''')


def text_font_styles(scripts: list[str]) -> list[str]:
    """Recognize top-level style blocks, never execute Python expressions."""
    names = {"default"}
    for script in scripts:
        active = None
        for line in script.splitlines():
            if line and not line[:1].isspace() and not line.startswith("#"):
                match = _STYLE.fullmatch(line)
                active = match.group(1) if match else None
            elif active and (_TEXT_FONT.fullmatch(line.strip()) or _TEXT_PROPERTIES.fullmatch(line.strip())):
                names.add(active)
    return sorted(names)


def render_font_support(styles: list[str]) -> str:
    if any(not re.fullmatch(r"[A-Za-z_]\w*", name) for name in styles):
        raise ValueError("unsafe Ren'Py font style identifier")
    lines = ["# VNText language-scoped text font support v1"]
    for name in sorted(set(styles)):
        lines.extend([f"translate vietnamese style {name}:", '    font "DejaVuSans.ttf"', ""])
    return "\n".join(lines) + "\n"


def prepare_font_support(root: Path, snapshots: dict[Path, str], archives: dict[Path, RenPyArchive]) -> str:
    """Return a style prefix only for the verified engine-bundled fallback.

    Add every consumed file/container to the writer's existing hash/CAS checks.
    Unsupported/missing fallback leaves the existing native text route intact;
    it does not imply that the game's custom fonts support Vietnamese.
    """
    font = root / "renpy/common/DejaVuSans.ttf"
    if not font.is_file() or font.is_symlink() or not font.resolve().is_relative_to(root.resolve()):
        return ""
    if font.stat().st_size > 4 * 1024 * 1024:
        return ""
    raw = font.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if digest != FALLBACK_SHA256:
        return ""
    # A game asset with this name would shadow the verified engine font.
    if (root / "game/DejaVuSans.ttf").exists():
        return ""
    scripts: list[str] = []
    total = 0

    def record(path: Path, digest: str) -> None:
        if path in snapshots and snapshots[path] != digest:
            raise ValueError("Ren'Py font source changed after text preflight")
        snapshots[path] = digest

    def consume(data: bytes) -> None:
        nonlocal total
        total += len(data)
        if total > MAX_SCRIPT_BYTES or len(scripts) >= MAX_SCRIPTS:
            raise ValueError("Ren'Py font source inspection exceeds bounds")
        scripts.append(data.decode("utf-8-sig"))

    game = root / "game"
    paths = []
    for parent, directories, files in os.walk(game, followlinks=False):
        for name in directories:
            directory = Path(parent) / name
            if directory.is_symlink() or directory.is_junction() or not directory.resolve().is_relative_to(game.resolve()):
                raise ValueError("unsafe Ren'Py font source directory")
        paths.extend(Path(parent) / name for name in files)
    for path in sorted(paths):
        relative = path.relative_to(game)
        if "tl" in relative.parts or path.suffix.lower() != ".rpy":
            continue
        if path.is_symlink() or not path.is_file() or not path.resolve().is_relative_to(game.resolve()):
            raise ValueError("unsafe Ren'Py font source path")
        if path.stat().st_size > MAX_SCRIPT_BYTES:
            raise ValueError("Ren'Py font source exceeds bounds")
        data = path.read_bytes()
        consume(data)
        record(path, hashlib.sha256(data).hexdigest())
    for path in sorted(game.glob("*.rpa")):
        if path.is_symlink() or not path.resolve().is_relative_to(game.resolve()):
            raise ValueError("unsafe Ren'Py font archive path")
        archive = archives.get(path) or RenPyArchive(path)
        if any(name.casefold() in {"dejavusans.ttf", "game/dejavusans.ttf"} for name in archive.members):
            return ""
        for name in sorted(archive.members):
            if name.lower().endswith(".rpy") and "tl" not in name.split("/"):
                if archive.member_size(name) > MAX_SCRIPT_BYTES:
                    raise ValueError("Ren'Py font archive source exceeds bounds")
                consume(archive.read_member(name)["content"])
        record(path, archive.container_sha256)
    record(font, digest)
    return render_language_support(scripts) + render_font_support(text_font_styles(scripts))
