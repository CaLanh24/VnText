"""Bounded, inert font/style evidence. Unresolved expressions remain UNKNOWN."""
from __future__ import annotations
import hashlib
import os
import re
import struct
from pathlib import Path
from vntext.font_coverage import cmap_glyphs
from vntext.patch_font_preflight import required_characters
from vntext.renpy_archive import RenPyArchive

MAX_SCRIPTS = 4096
MAX_SCRIPT_BYTES = 32 * 1024 * 1024
MAX_FONT_BYTES = 16 * 1024 * 1024
MAX_FONT_TOTAL = 64 * 1024 * 1024
TEXT_VARIABLES = {"text_font", "name_text_font", "interface_text_font"}
_STYLE = re.compile(r"^style\s+(\w+)(?:\s+is\s+(\w+))?:\s*(?:#.*)?$")
_GUI = re.compile(r'''^\s*(?:define|default)\s+gui\.(\w*font)\s*=\s*(["'])([^"'\r\n]+)\2\s*(?:#.*)?$''')
_LITERAL = re.compile(r'''^(["'])([^"'\r\n]+)\1\s*(?:#.*)?$''')


def inspect_font_mapping(root, translations, snapshots, archives):
    root = Path(root).resolve(); game = root / "game"
    chars = required_characters(translations)
    scripts = []; fonts = []; compiled = []; names = set(); unresolved = []
    byte_counts = {"scripts": 0, "fonts": 0}; file_count = 0; unresolved_total = 0

    def note(item):
        nonlocal unresolved_total
        unresolved_total += 1
        if len(unresolved) < 128: unresolved.append(item)

    def record(path, digest):
        if path in snapshots and snapshots[path] != digest:
            raise ValueError("Font inventory source changed after preflight")
        snapshots[path] = digest

    def consume(name, data, kind):
        byte_counts[kind] += len(data)
        if byte_counts[kind] > (MAX_SCRIPT_BYTES if kind == "scripts" else MAX_FONT_TOTAL):
            raise ValueError("Font inventory exceeds aggregate byte bounds")
        if kind == "scripts":
            if len(scripts) >= MAX_SCRIPTS: raise ValueError("Font script count exceeds bounds")
            try: scripts.append((name, data.decode("utf-8-sig")))
            except UnicodeError: note({"source": name, "reason": "SCRIPT_ENCODING_UNKNOWN"})
        else:
            if len(fonts) >= 128: raise ValueError("Font count exceeds bounds")
            item = {"source": name, "sha256": hashlib.sha256(data).hexdigest(), "glyph_status": "UNKNOWN"}
            try:
                coverage = cmap_glyphs(data, chars)
                item.update(glyph_status="MISSING" if coverage["missing"] else "PASS",
                            missing_count=len(coverage["missing"]), missing_sample=coverage["missing"][:64])
            except (ValueError, KeyError, IndexError, ArithmeticError, struct.error) as exc:
                item["reason"] = type(exc).__name__ + ": " + str(exc)[:160]
            fonts.append(item)

    for parent, directories, files in os.walk(game, followlinks=False):
        directories.sort()
        for directory in directories:
            path = Path(parent) / directory
            if path.is_symlink() or path.is_junction(): raise ValueError("Unsafe font inventory directory")
        for name in sorted(files):
            file_count += 1
            if file_count > 250000: raise ValueError("Font inventory file count exceeds bounds")
            path = Path(parent) / name; relative = path.relative_to(game).as_posix()
            if "tl" in path.relative_to(game).parts: continue
            names.add(relative.casefold())
            suffix = path.suffix.lower()
            if suffix == ".rpyc": compiled.append(relative)
            if suffix not in {".rpy", ".ttf", ".otf"}: continue
            if path.is_symlink() or not path.resolve().is_relative_to(game): raise ValueError("Unsafe font inventory file")
            if path.stat().st_size > (MAX_SCRIPT_BYTES if suffix == ".rpy" else MAX_FONT_BYTES):
                note({"source": relative, "reason": "FILE_SIZE_BOUND"}); continue
            data = path.read_bytes(); record(path, hashlib.sha256(data).hexdigest())
            consume(relative, data, "scripts" if suffix == ".rpy" else "fonts")
    for path in sorted(game.glob("*.rpa")):
        if path.is_symlink() or not path.resolve().is_relative_to(game): raise ValueError("Unsafe font archive")
        archive = archives.get(path) or RenPyArchive(path)
        record(path, archive.container_sha256)
        for name in sorted(archive.members):
            if "tl" in name.split("/"): continue
            origin = path.name + "::" + name
            names.add(origin.casefold())
            suffix = Path(name).suffix.lower()
            if suffix == ".rpyc": compiled.append(origin)
            if suffix not in {".rpy", ".ttf", ".otf"}: continue
            if archive.member_size(name) > (MAX_SCRIPT_BYTES if suffix == ".rpy" else MAX_FONT_BYTES):
                note({"source": origin, "reason": "ARCHIVE_MEMBER_SIZE_BOUND"}); continue
            consume(origin, archive.read_member(name)["content"], "scripts" if suffix == ".rpy" else "fonts")
    engine_font = root / "renpy/common/DejaVuSans.ttf"
    if engine_font.is_file() and not engine_font.is_symlink() and engine_font.resolve().is_relative_to(root) and engine_font.stat().st_size <= MAX_FONT_BYTES:
        data = engine_font.read_bytes(); record(engine_font, hashlib.sha256(data).hexdigest())
        consume("@engine/DejaVuSans.ttf", data, "fonts")

    variables = {}; styles = []; tags = []; ambiguous_variables = set()
    for origin, script in scripts:
        active = None
        for number, line in enumerate(script.splitlines(), 1):
            gui = _GUI.fullmatch(line)
            if gui:
                variable = "gui." + gui.group(1)
                if variable in variables and variables[variable] != gui.group(3):
                    ambiguous_variables.add(variable)
                    note({"source": origin, "line": number, "reason": "MULTIPLE_GUI_FONT_VALUES", "variable": variable})
                if variable not in ambiguous_variables: variables[variable] = gui.group(3)
                else: variables.pop(variable, None)
            elif re.match(r"^\s*(?:(?:define|default)\s+)?gui\.\w*font\s*=", line):
                variable = re.search(r"gui\.\w*font", line).group(0)
                variables.pop(variable, None)
                ambiguous_variables.add(variable)
                note({"source": origin, "line": number, "reason": "DYNAMIC_GUI_FONT", "variable": variable})
            if line and not line[:1].isspace() and not line.startswith("#"):
                match = _STYLE.fullmatch(line)
                active = {"style": match.group(1), "parent": match.group(2), "source": origin, "line": number,
                          "font": "INHERITED_UNKNOWN", "bold": "INHERITED_UNKNOWN", "italic": "INHERITED_UNKNOWN"} if match else None
                if active:
                    styles.append(active)
                    if len(styles) > 4096: raise ValueError("Font style count exceeds bounds")
            elif active:
                prop = re.fullmatch(r"\s+(font|bold|italic)\s+(.+)", line)
                if prop: active[prop.group(1)] = prop.group(2).strip()[:256]
            if "config.font_replacement_map" in line or "FontGroup(" in line:
                note({"source": origin, "line": number, "reason": "CUSTOM_FALLBACK_OR_REPLACEMENT_MAP"})
            for tag in re.findall(r"\{font=([^{}\r\n]+)\}", line):
                tags.append({"source": origin, "line": number, "font": tag[:256], "mapping_status": "EXPLICIT_TAG_NOT_REPLACED"})
                if len(tags) > 4096: raise ValueError("Font tag count exceeds bounds")
        if len(styles) > 4096: raise ValueError("Font style count exceeds bounds")
    for style in styles:
        expression = style["font"]; literal = _LITERAL.fullmatch(expression)
        style["resolved_font"] = literal.group(2) if literal else variables.get(expression)
        icon_hint = any(part in style["style"].casefold() or part in expression.casefold() for part in ("icon", "glyph"))
        style["purpose"] = "ICON_HINT_PRESERVED" if icon_hint else "TEXT_GUI" if expression.removeprefix("gui.") in TEXT_VARIABLES else "UNKNOWN"
        style["mapping_status"] = "STATIC_REFERENCE" if style["resolved_font"] else "UNRESOLVED"
        if style["resolved_font"]:
            name = style["resolved_font"].replace("\\", "/").casefold()
            candidates = [font for font in fonts if font["source"].casefold() == name]
            if not candidates: candidates = [font for font in fonts if font["source"].casefold().split("::")[-1] == name]
            if not candidates: candidates = [font for font in fonts if font["source"].casefold() == "@engine/" + name]
            if len(candidates) == 1:
                style["font_source"] = candidates[0]["source"]
                style["font_sha256"] = candidates[0]["sha256"]
                style["glyph_status_for_all_translated_characters"] = candidates[0]["glyph_status"]
            else: style["mapping_status"] = "ASSET_UNRESOLVED_OR_AMBIGUOUS"
    missing_source = sorted(name for name in compiled if name[:-1].casefold() not in names)
    return {"schema": 1, "characters_checked": len(chars), "required_codepoints": [f"U+{cp:04X}" for cp in chars],
            "fonts": fonts, "gui_variables": variables, "styles": styles, "font_tags": tags,
            "compiled_without_source_count": len(missing_source), "compiled_without_source_sample": missing_source[:32],
            "unresolved": unresolved[:128], "unresolved_count": unresolved_total,
            "limits": "Static references only. Inheritance, dynamic expressions, explicit tags and variant/fallback mappings are not runtime proof."}
