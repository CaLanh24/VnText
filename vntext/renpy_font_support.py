"""Language-scoped font styles from inert, bounded Ren'Py source inspection.

No game profiles, script evaluation, font download or original-file writes.
Only explicit text-font styles are selected; icon fonts and dynamic styles are
not rewritten. Ren'Py restores initialized styles when changing language.
"""
from __future__ import annotations

import hashlib
import json
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


REPLACEMENT_BEGIN = "# VNText language-scoped font replacement v1 begin"
REPLACEMENT_END = "# VNText language-scoped font replacement v1 end"
_REPLACEMENT_KEYS_PREFIX = "# keys: "
_REPLACEMENT_KEY = re.compile(r"[A-Za-z0-9_./ -]{1,160}")
_ICON_NAME_HINTS = ("icon", "glyph", "symbol", "dingbat", "awesome", "emoji")
MAX_REPLACEMENT_KEYS = 512


def replacement_keys_for_game_fonts(fonts: dict[str, bytes]) -> list[str]:
    """Spellings (as ``font`` strings may appear in styles, screens and {font} tags) of every game text font that lacks Vietnamese.

    Ren'Py loads ``fonts`` relative to ``game/`` and also to ``game/fonts/``; both spellings, plus a basename that is unique among the game's fonts, are
    emitted.  Case, ``./`` and a ``N@`` collection index are normalised at runtime.  Icon-named fonts and fonts whose cmap does not cover Basic Latin
    (icon/symbol fonts) are never selected; names outside a conservative character set are skipped rather than escaped.
    """

    lacking = text_fonts_lacking_vietnamese(fonts)
    basenames: dict[str, set[str]] = {}
    for name in fonts:
        basenames.setdefault(_font_key(name).rsplit("/", 1)[-1], set()).add(_font_key(name))
    keys: set[str] = set()
    for key in lacking:
        if any(hint in key for hint in _ICON_NAME_HINTS):
            continue
        variants = {key}
        if key.startswith("fonts/"):
            variants.add(key[len("fonts/"):])
        base = key.rsplit("/", 1)[-1]
        if len(basenames.get(base, ())) == 1:
            variants.add(base)
        keys.update(variant for variant in variants if _REPLACEMENT_KEY.fullmatch(variant))
    return sorted(keys)[:MAX_REPLACEMENT_KEYS]


GUARD_LINES = (
        "    def _vntext_font_guard():",
        "        # the game may assign a fresh config.font_replacement_map after language activation: re-wrap it (entries kept) at the next interaction",
        "        try:",
        '            if renpy.game.preferences.language == "vietnamese" and not isinstance(config.font_replacement_map, _VNTextFontMap):',
        "                config.font_replacement_map = _VNTextFontMap(config.font_replacement_map)",
        "        except Exception:",
        "            pass",
        '    config.interact_callbacks[:] = [callback for callback in config.interact_callbacks if getattr(callback, "__name__", "") != "_vntext_font_guard"] + [_vntext_font_guard]',
)


def render_font_replacement(keys: list[str], font_name: str, guard: bool = True) -> str:
    """One generated, ``translate vietnamese python`` block that routes the listed font files to the Vietnamese font through
    ``config.font_replacement_map`` (Ren'Py 8.5.3 ``renpy/text/font.py: get_font`` looks every font request up as ``(file, bold, italic)``)."""

    if not keys:
        return ""
    if any(not _REPLACEMENT_KEY.fullmatch(key) or key != key.lower() for key in keys):
        raise ValueError("unsafe Ren'Py font replacement key")
    if not re.fullmatch(r"[A-Za-z0-9_./-]+", font_name) or ".." in font_name:
        raise ValueError("unsafe font asset name")
    literal = ", ".join('"' + key + '"' for key in sorted(set(keys)))
    return "\n".join([
        REPLACEMENT_BEGIN,
        _REPLACEMENT_KEYS_PREFIX + json.dumps(sorted(set(keys)), ensure_ascii=True),
        "translate vietnamese python:",
        f"    _vntext_font_keys = frozenset([{literal}])",
        f'    _vntext_font_target = "{font_name}"',
        "    class _VNTextFontMap(dict):",
        "        def get(self, key, default=None):",
        "            found = dict.get(self, key, None)",
        "            hit = key if found is None else found",
        "            try:",
        '                if renpy.game.preferences.language == "vietnamese":',
        '                    name = str(hit[0]).replace("\\\\", "/").lower()',
        '                    if "@" in name:',
        '                        name = name.split("@", 1)[1]',
        '                    while name.startswith("./"):',
        "                        name = name[2:]",
        "                    if name in _vntext_font_keys:",
        "                        moved = (_vntext_font_target, hit[1], hit[2])",
        "                        hit = dict.get(self, moved, moved)",
        "            except Exception:",
        "                pass",
        "            if found is None and hit is key:",
        "                return default",
        "            return hit",
        "    if not isinstance(config.font_replacement_map, _VNTextFontMap):",
        "        config.font_replacement_map = _VNTextFontMap(config.font_replacement_map)",
        *(GUARD_LINES if guard else ()),
        REPLACEMENT_END,
        "",
    ])


def parse_generated_font_replacement(lines: list[str]) -> tuple[int, int, list[str]] | None:
    """Locate a generated block in ``lines``; returns (first, last+1, keys) only if it is byte-for-byte what the generator renders."""

    try:
        first = lines.index(REPLACEMENT_BEGIN)
        last = lines.index(REPLACEMENT_END, first) + 1
    except ValueError:
        return None
    keys_line = lines[first + 1] if first + 1 < len(lines) else ""
    if not keys_line.startswith(_REPLACEMENT_KEYS_PREFIX):
        return None
    try:
        keys = json.loads(keys_line[len(_REPLACEMENT_KEYS_PREFIX):])
        target = next(line for line in lines[first:last] if line.startswith('    _vntext_font_target = "'))
        font_name = target[len('    _vntext_font_target = "'):-1]
        variants = [render_font_replacement(keys, font_name, guard).split("\n")[:-1] for guard in (True, False)]   # current, then the released 0.1.25 form
    except (ValueError, StopIteration):
        return None
    return (first, last, keys) if lines[first:last] in variants else None


MAX_FALLBACK_RANGES = 32
_FALLBACK_NAME = f"tl/vietnamese/vntext_font_{FALLBACK_SHA256[:16]}.ttf"


def glyph_fallback_ranges(codepoints) -> list[tuple[int, int]] | None:
    """Collapse missing SYMBOL code points into FontGroup ranges; None when any is a Latin letter (a Latin-only font is replaced wholesale instead,
    never mixed glyph by glyph) or when the set is too fragmented to stay readable."""

    import unicodedata
    values = sorted({int(cp) for cp in codepoints})
    if not values or any(not 0x20 < cp <= 0x10FFFF or unicodedata.category(chr(cp))[0] in "CZ" or "LATIN" in unicodedata.name(chr(cp), "") for cp in values):
        return None
    ranges: list[tuple[int, int]] = []
    for cp in values:
        if ranges and cp == ranges[-1][1] + 1:
            ranges[-1] = (ranges[-1][0], cp)
        else:
            ranges.append((cp, cp))
    return ranges if len(ranges) <= MAX_FALLBACK_RANGES else None


def _font_expression(font_name: str, fallback) -> str:
    if not fallback:
        return f'"{font_name}"'
    name, ranges = fallback
    if name != _FALLBACK_NAME or not ranges or len(ranges) > MAX_FALLBACK_RANGES:
        raise ValueError("unsafe glyph fallback")
    adds = "".join(f'.add("{name}", 0x{start:X}, 0x{end:X})' for start, end in ranges)
    return f'FontGroup(){adds}.add("{font_name}", None, None)'


_GROUP_LINE = re.compile(r'    font FontGroup\(\)((?:\.add\("[^"\n]+", 0x[0-9A-F]+, 0x[0-9A-F]+\))+)\.add\("([^"\n]+)", None, None\)')
_GROUP_ADD = re.compile(r'\.add\("([^"\n]+)", 0x([0-9A-F]+), 0x([0-9A-F]+)\)')


SCALE_BEGIN = "# VNText font scale begin"
SCALE_END = "# VNText font scale end"
MIN_FONT_SCALE, MAX_FONT_SCALE = 0.70, 1.50
_SCALED_FONT_NAME = re.compile(r"tl/vietnamese/vntext_font_[0-9a-f]{16}\.(?:ttf|otf)")
_SCALE_LINE = re.compile(r'    config\.ftfont_scale\["([^"\n]+)"\] = ([0-9]\.[0-9]{1,2})')


def normalize_font_scale(value) -> float | None:
    """None for "no change" (empty or 1.0); a value rounded to 2 decimals inside [0.70, 1.50]; anything else is refused, never clamped silently."""

    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    try:
        scale = round(float(value), 2)
    except (TypeError, ValueError):
        raise ValueError("Font scale must be a number") from None
    if not MIN_FONT_SCALE <= scale <= MAX_FONT_SCALE:
        raise ValueError(f"Font scale must be between {MIN_FONT_SCALE:.2f} and {MAX_FONT_SCALE:.2f}")
    return None if scale == 1.0 else scale


def render_font_scale(font_name: str, scale: float | None) -> str:
    """One generated block that scales ONLY the generated Vietnamese font file (Ren'Py ``config.ftfont_scale`` is keyed by font file, the same hook the
    engine's own accessibility code uses).  Never emitted for an engine/game font name, whose scaling would also change other languages."""

    scale = normalize_font_scale(scale)
    if scale is None:
        return ""
    if not _SCALED_FONT_NAME.fullmatch(font_name):
        raise ValueError("Font scale applies only to the generated Vietnamese font")
    return "\n".join([SCALE_BEGIN, "translate vietnamese python:", f'    config.ftfont_scale["{font_name}"] = {scale:.2f}'.rstrip("0").rstrip("."), SCALE_END, ""])


def render_font_support(styles: list[str], font_name: str = "DejaVuSans.ttf", replacement_keys: list[str] | tuple = (), fallback=None, scale: float | None = None) -> str:
    if any(not re.fullmatch(r"[A-Za-z_]\w*", name) for name in styles):
        raise ValueError("unsafe Ren'Py font style identifier")
    if not re.fullmatch(r"[A-Za-z0-9_./-]+", font_name) or ".." in font_name:
        raise ValueError("unsafe font asset name")
    expression = _font_expression(font_name, fallback)
    lines = ["# VNText language-scoped text font support v1"]
    for name in sorted(set(styles)):
        lines.extend([f"translate vietnamese style {name}:", f"    font {expression}", ""])
    return "\n".join(lines) + "\n" + render_font_replacement(list(replacement_keys), font_name) + render_font_scale(font_name, scale)


_HEAD_HEADER = "# VNText language-scoped text font support v1"
_AUTHENTIC_FONT_NAME = re.compile(r"DejaVuSans\.ttf|tl/vietnamese/vntext_font_[0-9a-f]{16}\.(?:ttf|otf)")
_STYLE_LINE = re.compile(r"translate vietnamese style ([A-Za-z_]\w*):")
_FONT_LINE = re.compile(r'    font "([^"\n]+)"')
_TARGET_PREFIX = '    _vntext_font_target = "'


def split_generated_head(text: str) -> tuple[str, str] | None:
    """Split an existing overlay into (generated font head, user translations) when the head is EXACTLY something a known VNText release rendered.

    The head is parsed structurally (style names, one font asset name, optional replacement keys) and accepted only if re-rendering those facts with a
    known variant (0.1.24 style-only, 0.1.25 replacement block without guard, current with guard) reproduces the same bytes.  Any other edit, foreign
    font name or extra line makes this return None so the caller keeps rejecting it."""

    if not text.startswith(_HEAD_HEADER + "\n"):
        return None
    lines = text.split("\n")
    styles: list[str] = []
    font_name = None
    fallback = None
    font_line = None
    index = 1
    while index + 1 < len(lines) and lines[index].startswith("translate vietnamese style "):
        match = _STYLE_LINE.fullmatch(lines[index])
        if not match or (font_line is not None and lines[index + 1] != font_line):
            return None
        if font_line is None:
            font_line = lines[index + 1]
            plain = _FONT_LINE.fullmatch(font_line)
            group = _GROUP_LINE.fullmatch(font_line)
            if plain:
                font_name = plain.group(1)
            elif group:
                font_name = group.group(2)
                adds = _GROUP_ADD.findall(group.group(1))
                if {name for name, _a, _b in adds} != {_FALLBACK_NAME}:
                    return None
                fallback = (_FALLBACK_NAME, [(int(start, 16), int(end, 16)) for _name, start, end in adds])
            else:
                return None
        styles.append(match.group(1))
        index += 3 if lines[index + 2:index + 3] == [""] else 2
    keys: list[str] = []
    if index < len(lines) and lines[index] == REPLACEMENT_BEGIN:
        found = parse_generated_font_replacement(lines[index:])
        if found is None or found[0] != 0:
            return None
        keys = found[2]
        target = next(line for line in lines[index:index + found[1]] if line.startswith(_TARGET_PREFIX))
        replacement_font = target[len(_TARGET_PREFIX):-1]
        if font_name is not None and replacement_font != font_name:
            return None
        font_name = replacement_font
    if font_name is None or not _AUTHENTIC_FONT_NAME.fullmatch(font_name) or styles != sorted(set(styles)):
        return None
    try:
        _font_expression(font_name, fallback)
    except ValueError:
        return None
    for guard in (True, False):
        head = "\n".join([_HEAD_HEADER] + [part for name in styles for part in (f"translate vietnamese style {name}:", f"    font {_font_expression(font_name, fallback)}", "")]) + "\n"
        head += render_font_replacement(keys, font_name, guard)
        if text.startswith(head):
            rest = text[len(head):]
            if rest.startswith(SCALE_BEGIN + "\n"):
                end = rest.find(SCALE_END + "\n")
                block = rest[:end + len(SCALE_END) + 1] if end >= 0 else ""
                match = _SCALE_LINE.fullmatch(block.split("\n")[2]) if block.count("\n") == 4 else None
                if not match or match.group(1) != font_name:
                    return None
                try:
                    if render_font_scale(font_name, float(match.group(2))) != block:
                        return None
                except ValueError:
                    return None
                head, rest = head + block, rest[len(block):]
            return head, rest
    return None


def generated_font_scale(head: str) -> float | None:
    """The scale recorded in a generated head (None when it has no scale block)."""

    match = re.search(r'^    config\.ftfont_scale\["[^"\n]+"\] = ([0-9]\.[0-9]{1,2})$', head, re.MULTILINE)
    return float(match.group(1)) if match else None


def prepare_font_support(root: Path, snapshots: dict[Path, str], archives: dict[Path, RenPyArchive], replacement_font: Path | None = None, glyph_fallback=None, font_scale: float | None = None) -> str:
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
    return render_language_support(scripts) + render_font_support(text_font_styles(scripts, text_fonts_lacking_vietnamese(game_fonts)), font_name, replacement_keys_for_game_fonts(game_fonts), glyph_fallback, font_scale)
