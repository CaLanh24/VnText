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
_LITERAL_FONT = re.compile(r"""^font\s+(['"])[^'"\\\r\n]+\.(?:ttf|otf)\1\s*(?:#.*)?$""", re.IGNORECASE)
_TEXT_PROPERTIES = re.compile(r'''^properties\s+gui\.text_properties\(["'][A-Za-z_]\w*["'](?:,\s*accent\s*=\s*(?:True|False))?\)\s*(?:#.*)?$''')


# Vietnamese letters beyond Basic Latin that a Latin-only decorative (e.g. gothic) font typically lacks.
_VIETNAMESE_PROBE = "ĂăÂâĐđÊêÔôƠơƯưÁáÀàẢảÃãẠạẤấẦầẨẩẪẫẬậẮắẰằẲẳẴẵẶặÉéÈèẺẻẼẽẸẹẾếỀềỂểỄễỆệÍíÌìỈỉĨĩỊịÓóÒòỎỏÕõỌọỐốỒồỔổỖỗỘộỚớỜờỞởỠỡỢợÚúÙùỦủŨũỤụỨứỪừỬửỮữỰựÝýỲỳỶỷỸỹỴỵ"
_BASIC_LATIN = [ord(c) for c in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"]
MAX_GAME_FONT_BYTES = 16 * 1024 * 1024
MAX_GAME_FONT_TOTAL = 64 * 1024 * 1024
MAX_GAME_FONTS = 128


def _font_key(name: str) -> str:
    return str(name).replace("\\", "/").lstrip("./").casefold()


def text_fonts_lacking_vietnamese(fonts: dict[str, bytes]) -> set[str]:
    """Names of game fonts that cover Basic Latin (so they are text fonts, not icon fonts) but miss Vietnamese letters.

    Only bounded, parsed ``cmap`` evidence selects a font; an unparsable font or one without the Latin letters is never selected.
    """
    from vntext.font_coverage import cmap_glyphs

    probe = [ord(c) for c in _VIETNAMESE_PROBE]
    lacking: set[str] = set()
    for name, data in fonts.items():
        try:
            if cmap_glyphs(data, _BASIC_LATIN)["missing"]:
                continue
            if cmap_glyphs(data, probe)["missing"]:
                lacking.add(_font_key(name))
        except (ValueError, KeyError, IndexError, ArithmeticError):
            continue
    return lacking


def text_font_styles(scripts: list[str], lacking_fonts: frozenset[str] | set[str] = frozenset()) -> list[str]:
    """Recognize top-level style blocks, never execute Python expressions.

    ``lacking_fonts`` (casefolded game-relative font names that cover Latin but not Vietnamese) additionally admits a literal ``font`` of ANY style
    that names such a file; this is what remains in custom GUIs whose style names do not follow the default template.
    """
    names = {"default"}
    for script in scripts:
        active = None
        for line in script.splitlines():
            if line and not line[:1].isspace() and not line.startswith("#"):
                match = _STYLE.fullmatch(line)
                active = match.group(1) if match else None
            elif active:
                property_text = line.strip()
                literal_text_role = active in {"say_dialogue", "say_label", "nvl_dialogue", "nvl_label"} or active.endswith("_text")
                literal = _LITERAL_FONT.fullmatch(property_text)
                quoted = re.search(r"""(['"])([^'"\\]+)\1""", property_text) if literal else None
                names_lacking_font = bool(quoted and _font_key(quoted.group(2)) in lacking_fonts)
                if not (_TEXT_FONT.fullmatch(property_text) or _TEXT_PROPERTIES.fullmatch(property_text)
                        or (literal_text_role and literal) or names_lacking_font):
                    continue
                # Icon/glyph roles never inherit the text replacement just because
                # their property also ends in "_font" or uses gui.text_properties.
                if any(part in active.casefold() or part in line.casefold() for part in ("icon", "glyph")):
                    continue
                names.add(active)
    return sorted(names)


def render_font_support(styles: list[str], font_name: str = "DejaVuSans.ttf") -> str:
    if any(not re.fullmatch(r"[A-Za-z_]\w*", name) for name in styles):
        raise ValueError("unsafe Ren'Py font style identifier")
    if not re.fullmatch(r"[A-Za-z0-9_./-]+", font_name) or ".." in font_name:
        raise ValueError("unsafe font asset name")
    lines = ["# VNText language-scoped text font support v1"]
    for name in sorted(set(styles)):
        lines.extend([f"translate vietnamese style {name}:", f'    font "{font_name}"', ""])
    return "\n".join(lines) + "\n"


def prepare_font_support(root: Path, snapshots: dict[Path, str], archives: dict[Path, RenPyArchive], replacement_font: Path | None = None) -> str:
    """Return a style prefix only for the verified engine-bundled fallback.

    Add every consumed file/container to the writer's existing hash/CAS checks.
    Unsupported/missing fallback leaves the existing native text route intact;
    it does not imply that the game's custom fonts support Vietnamese.
    """
    font = replacement_font or root / "renpy/common/DejaVuSans.ttf"
    if not font.is_file() or font.is_symlink() or (replacement_font is None and not font.resolve().is_relative_to(root.resolve())):
        return ""
    if font.stat().st_size > (16 if replacement_font else 4) * 1024 * 1024:
        return ""
    raw = font.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if replacement_font is None and digest != FALLBACK_SHA256:
        return ""
    # A game asset with this name would shadow the verified engine font.
    if replacement_font is None and (root / "game/DejaVuSans.ttf").exists():
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
    game_fonts: dict[str, bytes] = {}
    font_total = 0

    def collect_font(name: str, data: bytes) -> None:
        nonlocal font_total
        font_total += len(data)
        if len(game_fonts) >= MAX_GAME_FONTS or font_total > MAX_GAME_FONT_TOTAL:
            raise ValueError("Ren'Py game font inspection exceeds bounds")
        game_fonts[name] = data

    paths = []
    for parent, directories, files in os.walk(game, followlinks=False):
        for name in directories:
            directory = Path(parent) / name
            if directory.is_symlink() or directory.is_junction() or not directory.resolve().is_relative_to(game.resolve()):
                raise ValueError("unsafe Ren'Py font source directory")
        paths.extend(Path(parent) / name for name in files)
    for path in sorted(paths):
        relative = path.relative_to(game)
        if "tl" not in relative.parts and path.suffix.lower() in {".ttf", ".otf"} and not path.is_symlink() and path.is_file()                 and path.resolve().is_relative_to(game.resolve()) and path.stat().st_size <= MAX_GAME_FONT_BYTES:
            font_bytes = path.read_bytes()
            collect_font(relative.as_posix(), font_bytes)
            record(path, hashlib.sha256(font_bytes).hexdigest())
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
        if replacement_font is None and any(name.casefold() in {"dejavusans.ttf", "game/dejavusans.ttf"} for name in archive.members):
            return ""
        for name in sorted(archive.members):
            if name.lower().endswith((".ttf", ".otf")) and "tl" not in name.split("/") and archive.member_size(name) <= MAX_GAME_FONT_BYTES:
                collect_font(name, archive.read_member(name)["content"])
            if name.lower().endswith(".rpy") and "tl" not in name.split("/"):
                if archive.member_size(name) > MAX_SCRIPT_BYTES:
                    raise ValueError("Ren'Py font archive source exceeds bounds")
                consume(archive.read_member(name)["content"])
        record(path, archive.container_sha256)
    record(font, digest)
    font_name = f"tl/vietnamese/vntext_font_{digest[:16]}{font.suffix.lower()}" if replacement_font else "DejaVuSans.ttf"
    return render_language_support(scripts) + render_font_support(text_font_styles(scripts, text_fonts_lacking_vietnamese(game_fonts)), font_name)
