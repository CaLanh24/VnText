"""Conservative loose-source Ren'Py extraction; IDs always come from Ren'Py."""
from __future__ import annotations

import ast
from dataclasses import dataclass
import hashlib
import re
from pathlib import Path

from vntext.entry import Entry
from vntext.patchability import (
    RENPY_DIALOGUE_PATCH_PROOF,
    RENPY_DIALOGUE_UNIT,
    RENPY_NATIVE_CONTRACT_VERSION,
    RENPY_STRING_PATCH_PROOF,
    RENPY_STRING_UNIT,
    RENPY_GAME_OWNED,
    classify_renpy_provenance,
    is_technical_skip_entry,
    make_renpy_contract,
    validate_renpy_contract,
)

_DIALOGUE = re.compile(r'^\s*(?:(?P<speaker>[A-Za-z_]\w*)\s+)?(?P<quote>"(?:\\.|[^"\\])*")\s*(?:#.*)?$')
_STRING = re.compile(r'_\(\s*("(?:\\.|[^"\\])*")\s*\)')
_MENU = re.compile(r'^\s*menu\s*(?:[A-Za-z_][\w]*\s*)?:\s*(?:#.*)?$')
_MENU_ITEM = re.compile(r'^\s*("(?:\\.|[^"\\])*")\s*:\s*(?:#.*)?$')
_BLOCK = re.compile(r'^\s*translate\s+vietnamese\s+(?P<identifier>\S+)\s*:')
_COMMENT = re.compile(r'^\s*#\s*(?:(?P<speaker>[A-Za-z_]\w*)\s+)?(?P<quote>"(?:\\.|[^"\\])*")')
_NATIVE_BLOCK = re.compile(
    r'^(?P<indent>[ \t]*)translate\s+(?P<language>None|[A-Za-z_]\w*)\s+'
    r'(?P<target>[^:#]+?)\s*:(?:\s*#.*)?$'
)
_PROVENANCE = re.compile(
    r'^\s*#\s+(?P<source_file>[^:#\r\n]+\.(?:rpy|rpym)):(?P<source_line>[1-9]\d*)\s*$'
)
_IDENTIFIER = re.compile(r'^[A-Za-z_]\w*$')
_QUOTE = r'"(?:\\.|[^"\\])*"'
_KEYED_QUOTE = re.compile(r'^(?P<key>old|new)\s+(?P<quote>' + _QUOTE + r')\s*$')
_LABEL = re.compile(r'^label\s+(?P<name>[A-Za-z_]\w*)\s*:\s*(?:#.*)?$')

# ponytail: keep one adjacent dialogue per side; expand only if measured
# translation quality needs a wider window.
_NATIVE_CONTEXT_MAX_ITEMS = 1
_NATIVE_CONTEXT_MAX_CHARS = 240


class RenPyTemplateParseError(ValueError):
    """Raised when a generated Ren'Py template cannot be parsed safely."""


@dataclass(frozen=True)
class RenPyNativeUnit:
    """One typed unit retained from a generated Ren'Py translation artifact."""

    unit_kind: str
    statement_class: str
    language: str
    native_id: str
    source_text: str
    target_text: str
    source_file: str
    source_line: int | None
    template_file: str
    template_line: int
    target_line: int
    order: int
    block_order: int
    speaker: str = ""
    expression: str = ""
    target_speaker: str = ""
    target_expression: str = ""

    @property
    def unit_type(self) -> str:
        return self.unit_kind

    @property
    def kind(self) -> str:
        return self.unit_kind

    @property
    def template_order(self) -> int:
        return self.order

    @property
    def original_text(self) -> str:
        return self.source_text

    @property
    def translation_text(self) -> str:
        return self.target_text

    @property
    def source_filename(self) -> str:
        return self.source_file

    @property
    def identity_kind(self) -> str:
        return "native_id" if self.unit_kind == "dialogue" else "source"

    @property
    def identity_value(self) -> str:
        return self.native_id if self.unit_kind == "dialogue" else self.source_text

    @property
    def native_identity(self) -> tuple[str, str]:
        """Return the identity semantics without deriving an ID from source text."""
        return self.identity_kind, self.identity_value


@dataclass(frozen=True)
class _SourceEnrichment:
    status: str
    reason: str = ""
    speaker: str = ""
    source_span: dict[str, int] | None = None
    context_group: str = ""


_ENRICHMENT_RESOLVED = "RESOLVED"
_ENRICHMENT_UNAVAILABLE = "UNAVAILABLE"
_ENRICHMENT_MISMATCH = "MISMATCH"
_ENRICHMENT_AMBIGUOUS = "AMBIGUOUS"


def _template_paths(template_root: str | Path) -> tuple[Path, list[Path]]:
    root = Path(template_root).resolve()
    if root.is_file():
        return root.parent, [root]
    if not root.is_dir():
        raise RenPyTemplateParseError(f"template root is not a file or directory: {root}")
    paths = [*root.rglob("*.rpy"), *root.rglob("*.rpym")]
    paths.sort(key=lambda path: path.relative_to(root).as_posix())
    return root, paths


def _quote_end(value: str, start: int) -> int:
    escaped = False
    for index in range(start + 1, len(value)):
        char = value[index]
        if escaped:
            escaped = False
        elif char == "\\":
            escaped = True
        elif char == '"':
            return index
    raise ValueError("unterminated quoted Ren'Py string")


def _statement(value: str, *, comment: bool = False) -> tuple[str, str, str]:
    text = value.strip()
    if comment:
        if not text.startswith("#"):
            raise ValueError("expected a source statement comment")
        text = text[1:].lstrip()
    quote_start = text.find('"')
    if quote_start < 0:
        raise ValueError("statement has no quoted text")
    quote_end = _quote_end(text, quote_start)
    suffix = text[quote_end + 1:].strip()
    if suffix and not suffix.startswith("#"):
        raise ValueError("statement has an ambiguous suffix")
    prefix = text[:quote_start].strip()
    if prefix:
        parts = prefix.split()
        if not all(_IDENTIFIER.fullmatch(part) for part in parts):
            raise ValueError("speaker/expression is not unambiguous")
        speaker = parts[0]
        expression = " ".join(parts[1:])
    else:
        speaker = expression = ""
    return str(ast.literal_eval(text[quote_start:quote_end + 1])), speaker, expression


def _keyed_string(value: str) -> tuple[str, str]:
    match = _KEYED_QUOTE.fullmatch(value.strip())
    if not match:
        raise ValueError("string unit must contain exactly one old/new quoted slot")
    return match.group("key"), str(ast.literal_eval(match.group("quote")))


def _error(template_file: str, line: int, message: str) -> RenPyTemplateParseError:
    return RenPyTemplateParseError(f"{template_file}:{line}: {message}")


def _provenance_before(lines: list[str], header_line: int) -> tuple[str, int] | None:
    index = header_line - 2
    if index < 0:
        return None
    match = _PROVENANCE.fullmatch(lines[index])
    if not match:
        return None
    return match.group("source_file"), int(match.group("source_line"))


def _parse_native_block(
    *,
    lines: list[str],
    header_line: int,
    end_line: int,
    template_file: str,
    language: str,
    target: str,
    provenance: tuple[str, int] | None,
    order: int,
    block_order: int,
) -> list[RenPyNativeUnit]:
    content = [(number, lines[number - 1]) for number in range(header_line + 1, end_line)]
    if header_line >= len(lines) or lines[header_line].strip():
        raise _error(template_file, header_line, "native translation block must have a blank line after header")

    meaningful: list[tuple[int, str]] = []
    for number, raw in content:
        stripped = raw.strip()
        if not stripped or (not raw[:1].isspace() and stripped.startswith("#")):
            continue
        if not raw[:1].isspace():
            raise _error(template_file, number, "native block content must be indented")
        meaningful.append((number, stripped))

    if target == "strings":
        units: list[RenPyNativeUnit] = []
        index = 0
        while index < len(content):
            line_number, raw = content[index]
            value = raw.strip()
            if not value or (not raw[:1].isspace() and value.startswith("#")):
                index += 1
                continue
            if not raw[:1].isspace():
                raise _error(template_file, line_number, "native block content must be indented")
            provenance_match = _PROVENANCE.fullmatch(value)
            if not provenance_match:
                raise _error(template_file, line_number, "string pair must start with source filename/line provenance")
            if index + 2 >= len(content):
                raise _error(template_file, line_number, "string provenance has no complete old/new pair")
            old_line, old_raw = content[index + 1]
            new_line, new_raw = content[index + 2]
            if not old_raw.strip() or not new_raw.strip():
                raise _error(template_file, line_number, "string provenance must be immediately followed by old/new")
            if not old_raw[:1].isspace() or not new_raw[:1].isspace():
                raise _error(template_file, old_line, "string old/new statements must be indented")
            old_value = old_raw.strip()
            new_value = new_raw.strip()
            try:
                key, source_text = _keyed_string(old_value)
            except (SyntaxError, ValueError) as exc:
                raise _error(template_file, old_line, str(exc)) from exc
            if key != "old":
                raise _error(template_file, old_line, "string unit must start with old")
            try:
                target_key, target_text = _keyed_string(new_value)
            except (SyntaxError, ValueError) as exc:
                raise _error(template_file, new_line, str(exc)) from exc
            if target_key != "new":
                raise _error(template_file, new_line, "string old must be followed by new")
            units.append(
                RenPyNativeUnit(
                    unit_kind="string",
                    statement_class="string",
                    language=language,
                    native_id="",
                    source_text=source_text,
                    target_text=target_text,
                    source_file=provenance_match.group("source_file"),
                    source_line=int(provenance_match.group("source_line")),
                    template_file=template_file,
                    template_line=header_line,
                    target_line=new_line,
                    order=order + len(units),
                    block_order=block_order,
                )
            )
            index += 3
        return units

    if not _IDENTIFIER.fullmatch(target) or target in {"python", "style"}:
        raise _error(template_file, header_line, "unsupported or ambiguous native translation block")
    source_items: list[tuple[int, str, str, str]] = []
    target_items: list[tuple[int, str, str, str]] = []
    for line_number, value in meaningful:
        if value.startswith("#"):
            try:
                parsed = _statement(value, comment=True)
            except (SyntaxError, ValueError) as exc:
                raise _error(template_file, line_number, f"unsupported native dialogue source statement: {exc}") from exc
            source_items.append((line_number, *parsed))
        else:
            try:
                parsed = _statement(value, comment=False)
            except (SyntaxError, ValueError) as exc:
                raise _error(template_file, line_number, f"unsupported native dialogue target statement: {exc}") from exc
            target_items.append((line_number, *parsed))
    if len(source_items) != 1 or len(target_items) != 1:
        raise _error(
            template_file,
            header_line,
            "unsupported multi-statement native dialogue block: "
            f"expected one source and one target statement, found {len(source_items)} source and {len(target_items)} target",
        )
    if provenance is None:
        raise _error(template_file, header_line, "native dialogue block is missing source filename/line provenance")
    source_line, source_text, speaker, expression = source_items[0]
    target_line, target_text, target_speaker, target_expression = target_items[0]
    source_class = "narration" if not speaker else "dialogue"
    target_class = "narration" if not target_speaker else "dialogue"
    if source_class != target_class:
        raise _error(template_file, target_line, "source and target statement classes are ambiguous")
    source_file, emitted_source_line = provenance
    return [
        RenPyNativeUnit(
            unit_kind="dialogue",
            statement_class=source_class,
            language=language,
            native_id=target,
            source_text=source_text,
            target_text=target_text,
            source_file=source_file,
            source_line=emitted_source_line,
            template_file=template_file,
            template_line=header_line,
            target_line=target_line,
            order=order,
            block_order=block_order,
            speaker=speaker,
            expression=expression,
            target_speaker=target_speaker,
            target_expression=target_expression,
        )
    ]


def parse_renpy_translation_templates(
    template_root: str | Path,
    *,
    language: str | None = None,
) -> list[RenPyNativeUnit]:
    """Parse generated native dialogue and string translation templates.

    The parser only accepts the one-to-one generated shapes needed by Wave B.
    It returns no partial result: malformed or unsupported selected blocks raise
    ``RenPyTemplateParseError`` instead of guessing or silently dropping units.
    """
    base, paths = _template_paths(template_root)
    units: list[RenPyNativeUnit] = []
    block_order = 1
    for path in paths:
        template_file = path.relative_to(base).as_posix()
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeError) as exc:
            raise RenPyTemplateParseError(f"{template_file}: cannot read template: {exc}") from exc
        line_number = 1
        while line_number <= len(lines):
            raw = lines[line_number - 1]
            header = _NATIVE_BLOCK.fullmatch(raw)
            if not header:
                if raw.lstrip().startswith("translate ") and not raw[:1].isspace():
                    raise _error(template_file, line_number, "malformed translate header")
                line_number += 1
                continue
            if raw[:1].isspace():
                raise _error(template_file, line_number, "native translate header must be top-level")
            header_provenance = _provenance_before(lines, line_number)
            selected_language = header.group("language")
            end_line = line_number + 1
            while end_line <= len(lines):
                candidate = lines[end_line - 1]
                if _NATIVE_BLOCK.fullmatch(candidate) or (
                    candidate.lstrip().startswith("translate ") and not candidate[:1].isspace()
                ):
                    break
                end_line += 1
            if language is None or selected_language == language:
                target = header.group("target").strip()
                try:
                    parsed = _parse_native_block(
                        lines=lines,
                        header_line=line_number,
                        end_line=end_line,
                        template_file=template_file,
                        language=selected_language,
                        target=target,
                        provenance=header_provenance,
                        order=len(units),
                        block_order=block_order,
                    )
                except RenPyTemplateParseError:
                    raise
                except (SyntaxError, ValueError) as exc:
                    raise _error(template_file, line_number, str(exc)) from exc
                units.extend(parsed)
                block_order += 1
            line_number = end_line
    return units


parse_native_templates = parse_renpy_translation_templates


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _template_identity(template_root: str | Path) -> str:
    digest = hashlib.sha256()
    base, paths = _template_paths(template_root)
    for path in paths:
        try:
            content = path.read_bytes()
        except (OSError, UnicodeError) as exc:
            raise RenPyTemplateParseError(f"{path.relative_to(base).as_posix()}: cannot hash template: {exc}") from exc
        digest.update(path.relative_to(base).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(content)
        digest.update(b"\0")
    return digest.hexdigest()


def _native_source_path(
    root: Path,
    source_file: str,
    template_file: str,
    template_line: int,
    *,
    allow_missing: bool = False,
) -> tuple[str, Path]:
    relative = str(source_file or "").replace("\\", "/")
    candidate = Path(relative)
    if not relative or candidate.is_absolute() or ".." in candidate.parts:
        raise RenPyTemplateParseError(
            f"{template_file}:{template_line}: native source provenance escapes the game root: {source_file!r}"
        )
    source_path = (root / candidate).resolve()
    try:
        source_path.relative_to(root)
    except ValueError as exc:
        raise RenPyTemplateParseError(
            f"{template_file}:{template_line}: native source provenance escapes the game root: {source_file!r}"
        ) from exc
    if not source_path.is_file() and not allow_missing:
        raise RenPyTemplateParseError(
            f"{template_file}:{template_line}: native source provenance is missing: {relative}"
        )
    return source_path.relative_to(root).as_posix(), source_path


def _source_span(line_number: int, start: int, end: int) -> dict[str, int]:
    return {
        "line": line_number,
        "start_column": start + 1,
        "end_column": end,
    }


def _source_context_group(lines: list[str], line_number: int) -> str:
    for raw in reversed(lines[: max(0, line_number - 1)]):
        if raw[:1].isspace():
            continue
        label = _LABEL.fullmatch(raw.strip())
        if label:
            return f"label:{label.group('name')}"
    return ""


def _read_source_lines(path: Path, cache: dict[Path, list[str] | None]) -> list[str] | None:
    if path not in cache:
        try:
            cache[path] = path.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeError):
            cache[path] = None
    return cache[path]


def _resolve_source_enrichment(
    path: Path,
    unit: RenPyNativeUnit,
    lines_cache: dict[Path, list[str] | None],
) -> _SourceEnrichment:
    line_number = unit.source_line
    if not isinstance(line_number, int) or line_number < 1:
        return _SourceEnrichment(_ENRICHMENT_UNAVAILABLE, "native source line provenance is unavailable")
    lines = _read_source_lines(path, lines_cache)
    if lines is None:
        return _SourceEnrichment(_ENRICHMENT_UNAVAILABLE, "native source file could not be read for enrichment")
    if line_number > len(lines):
        return _SourceEnrichment(
            _ENRICHMENT_MISMATCH,
            f"native source line {line_number} is outside the current source file",
        )

    raw = lines[line_number - 1]
    if unit.unit_kind == RENPY_DIALOGUE_UNIT:
        try:
            source_text, speaker, expression = _statement(raw)
            quote_start = raw.find('"')
            quote_end = _quote_end(raw, quote_start) + 1
        except (SyntaxError, ValueError) as exc:
            return _SourceEnrichment(_ENRICHMENT_MISMATCH, f"native source line is not a supported dialogue statement: {exc}")
        if source_text != unit.source_text:
            return _SourceEnrichment(_ENRICHMENT_MISMATCH, "native source text does not match the exact provenance line")
        if speaker != unit.speaker or expression != unit.expression:
            return _SourceEnrichment(_ENRICHMENT_MISMATCH, "native source speaker/expression does not match the native unit")
        return _SourceEnrichment(
            _ENRICHMENT_RESOLVED,
            speaker=speaker,
            source_span=_source_span(line_number, quote_start, quote_end),
            context_group=_source_context_group(lines, line_number),
        )

    if unit.unit_kind != RENPY_STRING_UNIT:
        return _SourceEnrichment(_ENRICHMENT_UNAVAILABLE, f"unsupported native enrichment unit: {unit.unit_kind!r}")

    matches: list[tuple[int, int]] = []
    for match in _STRING.finditer(raw):
        try:
            source_text = str(ast.literal_eval(match.group(1)))
        except (SyntaxError, ValueError) as exc:
            return _SourceEnrichment(_ENRICHMENT_MISMATCH, f"native source line has an invalid string literal: {exc}")
        if source_text == unit.source_text:
            matches.append(match.span(1))
    menu_match = _MENU_ITEM.fullmatch(raw)
    if menu_match:
        try:
            menu_text = str(ast.literal_eval(menu_match.group(1)))
        except (SyntaxError, ValueError) as exc:
            return _SourceEnrichment(_ENRICHMENT_MISMATCH, f"native source menu item has an invalid string literal: {exc}")
        if menu_text == unit.source_text:
            matches.append(menu_match.span(1))
    if len(matches) > 1:
        return _SourceEnrichment(
            _ENRICHMENT_AMBIGUOUS,
            "native source provenance line contains multiple matching string occurrences",
        )
    if not matches:
        return _SourceEnrichment(_ENRICHMENT_MISMATCH, "native source text does not match the exact provenance line")
    start, end = matches[0]
    return _SourceEnrichment(
        _ENRICHMENT_RESOLVED,
        source_span=_source_span(line_number, start, end),
        context_group=_source_context_group(lines, line_number),
    )


def _native_dialogue_neighbors(
    units: list[RenPyNativeUnit],
    enrichments: list[_SourceEnrichment],
) -> list[tuple[list[str], list[str]]]:
    neighbors: list[tuple[list[str], list[str]]] = [([], []) for _unit in units]
    groups: dict[tuple[str, str], list[tuple[int, RenPyNativeUnit, _SourceEnrichment]]] = {}
    for index, (unit, enrichment) in enumerate(zip(units, enrichments)):
        if unit.unit_kind != RENPY_DIALOGUE_UNIT:
            continue
        key = (str(unit.source_file).replace("\\", "/"), enrichment.context_group)
        groups.setdefault(key, []).append((index, unit, enrichment))

    for grouped in groups.values():
        grouped.sort(key=lambda item: (item[1].source_line or 0, item[1].order, item[1].native_id))
        for position, (index, _unit, enrichment) in enumerate(grouped):
            if enrichment.status != _ENRICHMENT_RESOLVED:
                continue
            previous: list[str] = []
            following: list[str] = []
            if position:
                _prior_index, prior_unit, prior_enrichment = grouped[position - 1]
                if prior_enrichment.status == _ENRICHMENT_RESOLVED:
                    previous.append(prior_unit.source_text[:_NATIVE_CONTEXT_MAX_CHARS])
            if position + 1 < len(grouped):
                _next_index, next_unit, next_enrichment = grouped[position + 1]
                if next_enrichment.status == _ENRICHMENT_RESOLVED:
                    following.append(next_unit.source_text[:_NATIVE_CONTEXT_MAX_CHARS])
            neighbors[index] = (
                previous[:_NATIVE_CONTEXT_MAX_ITEMS],
                following[:_NATIVE_CONTEXT_MAX_ITEMS],
            )
    return neighbors


def _native_entry(
    root: Path,
    unit: RenPyNativeUnit,
    *,
    template_sha256: str,
    source_hashes: dict[Path, str],
    enrichment: _SourceEnrichment,
    previous_context: list[str],
    next_context: list[str],
    source_available: bool,
) -> Entry:
    allow_missing = unit.unit_kind == RENPY_STRING_UNIT and str(unit.source_file).replace("\\", "/").casefold().startswith("renpy/common/")
    file_path, source_path = _native_source_path(
        root,
        unit.source_file,
        unit.template_file,
        unit.template_line,
        allow_missing=allow_missing,
    )
    source_available = bool(source_available and source_path.is_file())
    source_sha256 = source_hashes.get(source_path) if source_available else ""
    if source_available and source_sha256 is None:
        try:
            source_sha256 = _sha256(source_path)
        except OSError as exc:
            if str(unit.source_file).replace("\\", "/").casefold().startswith("renpy/common/"):
                source_available = False
                source_sha256 = ""
            else:
                raise RenPyTemplateParseError(
                    f"{unit.template_file}:{unit.template_line}: cannot hash native source {file_path}: {exc}"
                ) from exc
        if source_available:
            source_hashes[source_path] = source_sha256

    if unit.unit_kind == RENPY_DIALOGUE_UNIT:
        method = "renpy_dialogue"
        locator = {"native_id": unit.native_id, "unit_type": RENPY_DIALOGUE_UNIT}
        context = f"RenPy:{file_path}:{unit.source_line}:{unit.native_id}"
    elif unit.unit_kind == RENPY_STRING_UNIT:
        method = "renpy_string"
        locator = {"source": unit.source_text, "unit_type": RENPY_STRING_UNIT}
        context = f"RenPy:{file_path}:{unit.source_line}:string:{unit.template_file}:{unit.block_order}"
    else:
        raise RenPyTemplateParseError(
            f"{unit.template_file}:{unit.template_line}: unsupported native unit kind: {unit.unit_kind!r}"
        )

    contract = make_renpy_contract(
        method=method,
        backend="renpy_loose_source",
        unit_type=unit.unit_kind,
        source_text=unit.source_text,
        file_path=file_path,
        source_sha256=source_sha256,
        template_sha256=template_sha256,
        native_id=unit.native_id,
        source_line=unit.source_line,
        block_order=unit.block_order,
        speaker=unit.speaker,
        source_context=context,
        language=unit.language,
    )
    if unit.unit_kind == RENPY_STRING_UNIT:
        provenance = contract["provenance"]
        provenance.update(
            classify_renpy_provenance(
                file_path,
                source_available=source_available,
            )
        )
    if enrichment.source_span is not None:
        contract["provenance"]["source_span"] = dict(enrichment.source_span)
    native_context = contract["context"]
    native_context["enrichment"] = {
        "status": enrichment.status,
        "authoritative": False,
    }
    if enrichment.reason:
        native_context["enrichment"]["reason"] = enrichment.reason
    native_context["previous"] = list(previous_context)
    native_context["next"] = list(next_context)
    native_context["context_truncation_policy"] = (
        f"max_items={_NATIVE_CONTEXT_MAX_ITEMS};max_chars={_NATIVE_CONTEXT_MAX_CHARS}"
    )
    if enrichment.context_group:
        native_context["context_group"] = enrichment.context_group
    entry = Entry(
        unit.source_text,
        file_path,
        context,
        object_info=enrichment.speaker if enrichment.status == _ENRICHMENT_RESOLVED else unit.speaker,
        import_method=method,
        safety="safe",
        backend="renpy_loose_source",
        locator=locator,
        patch_proof=(
            dict(RENPY_DIALOGUE_PATCH_PROOF)
            if unit.unit_kind == RENPY_DIALOGUE_UNIT
            else (
                dict(RENPY_STRING_PATCH_PROOF)
                if contract["provenance"].get("owner") == RENPY_GAME_OWNED
                else {}
            )
        ),
        native_contract=contract,
    ).finalize()
    if unit.unit_kind == RENPY_STRING_UNIT:
        provenance = contract["provenance"]
        technical = (
            provenance.get("disposition") != "sdk_only"
            and is_technical_skip_entry(entry)
        )
        if technical:
            provenance["disposition"] = "technical_skipped"
            provenance["ledger"] = "technical_skipped"
        elif provenance.get("owner") != RENPY_GAME_OWNED:
            entry.review_only = True
    reason = validate_renpy_contract(entry) if contract["provenance"].get("owner") == RENPY_GAME_OWNED else ""
    if reason:
        raise RenPyTemplateParseError(
            f"{unit.template_file}:{unit.template_line}: native unit contract is incomplete: {reason}"
        )
    return entry


def extract_native_template_entries(
    root: str | Path,
    template_root: str | Path,
    *,
    language: str = "vietnamese",
) -> tuple[list[Entry], list[Entry], dict]:
    """Build canonical Entries from authoritative generated Ren'Py units."""

    game_root = Path(root).resolve()
    if not game_root.is_dir():
        raise RenPyTemplateParseError(f"Ren'Py game root is not a directory: {game_root}")
    units = parse_renpy_translation_templates(template_root, language=language)
    template_sha256 = _template_identity(template_root)
    source_hashes: dict[Path, str] = {}
    source_lines: dict[Path, list[str] | None] = {}
    enrichments: list[_SourceEnrichment] = []
    source_availability: list[bool] = []
    for unit in units:
        normalized_source = str(unit.source_file).replace("\\", "/")
        allow_missing = unit.unit_kind == RENPY_STRING_UNIT and normalized_source.casefold().startswith("renpy/common/")
        _file_path, source_path = _native_source_path(
            game_root,
            unit.source_file,
            unit.template_file,
            unit.template_line,
            allow_missing=allow_missing,
        )
        available = source_path.is_file()
        source_availability.append(available)
        enrichments.append(
            _resolve_source_enrichment(source_path, unit, source_lines)
            if available
            else _SourceEnrichment(
                _ENRICHMENT_UNAVAILABLE,
                "native source file is absent from the runtime game; retained as SDK-only evidence",
            )
        )
    neighbors = _native_dialogue_neighbors(units, enrichments)
    dialogue_ids: dict[str, RenPyNativeUnit] = {}
    string_targets: dict[str, str] = {}
    entries: list[Entry] = []
    for index, unit in enumerate(units):
        if unit.unit_kind == RENPY_DIALOGUE_UNIT:
            prior = dialogue_ids.get(unit.native_id)
            if prior is not None:
                raise RenPyTemplateParseError(
                    f"{unit.template_file}:{unit.template_line}: duplicate native dialogue identifier "
                    f"{unit.native_id!r}; first seen at {prior.template_file}:{prior.template_line}"
                )
            dialogue_ids[unit.native_id] = unit
        elif unit.unit_kind == RENPY_STRING_UNIT:
            prior_target = string_targets.get(unit.source_text)
            if prior_target is not None and prior_target != unit.target_text:
                raise RenPyTemplateParseError(
                    f"{unit.template_file}:{unit.template_line}: conflicting native string source "
                    f"{unit.source_text!r} has multiple target values"
                )
            string_targets.setdefault(unit.source_text, unit.target_text)
        previous_context, next_context = neighbors[index]
        entries.append(
            _native_entry(
                game_root,
                unit,
                template_sha256=template_sha256,
                source_hashes=source_hashes,
                enrichment=enrichments[index],
                previous_context=previous_context,
                next_context=next_context,
                source_available=source_availability[index],
            )
        )
    dialogue_count = sum(unit.unit_kind == RENPY_DIALOGUE_UNIT for unit in units)
    string_count = sum(unit.unit_kind == RENPY_STRING_UNIT for unit in units)
    source_files: set[Path] = set()
    game_dir = game_root / "game"
    if game_dir.is_dir():
        for path in game_dir.rglob("*"):
            if path.is_file() and path.suffix.casefold() in {".rpy", ".rpym"}:
                if "tl" not in {part.casefold() for part in path.relative_to(game_dir).parts}:
                    source_files.add(path)
    string_entries = [entry for entry in entries if entry.import_method == "renpy_string"]
    string_owners: dict[str, int] = {}
    string_ledgers: dict[str, int] = {}
    for entry in string_entries:
        provenance = entry.native_contract.get("provenance", {})
        owner = str(provenance.get("owner") or "unknown")
        ledger = str(provenance.get("ledger") or "missing_source")
        string_owners[owner] = string_owners.get(owner, 0) + 1
        string_ledgers[ledger] = string_ledgers.get(ledger, 0) + 1
    string_reconciliation = {
        "total": string_count,
        "unique_exact_sources": len({unit.source_text for unit in units if unit.unit_kind == RENPY_STRING_UNIT}),
        "ownership_counts": dict(sorted(string_owners.items())),
        "ledger_counts": dict(sorted(string_ledgers.items())),
        "common_runtime_count": sum(
            1
            for entry in string_entries
            if entry.native_contract.get("provenance", {}).get("owner") != RENPY_GAME_OWNED
            and entry.native_contract.get("provenance", {}).get("ledger") != "missing_source"
        ),
        "sdk_only_count": string_ledgers.get("missing_source", 0),
        "auto_patchable_count": string_ledgers.get("translation_csv", 0),
    }
    stats = {
        "engine": "RENPY_LOOSE_SOURCE",
        "native_contract_version": RENPY_NATIVE_CONTRACT_VERSION,
        "native_template": True,
        "native_template_sha256": template_sha256,
        "native_units": len(units),
        "native_dialogue_units": dialogue_count,
        "native_string_units": string_count,
        "native_string_unique_sources": string_reconciliation["unique_exact_sources"],
        "native_string_ownership_counts": string_reconciliation["ownership_counts"],
        "native_string_ledger_counts": string_reconciliation["ledger_counts"],
        "native_string_reconciliation": string_reconciliation,
        "files_scanned": len(source_files),
    }
    return [entry for entry in entries if not entry.review_only], [entry for entry in entries if entry.review_only], stats


extract_native_templates = extract_native_template_entries


def _quoted(value: str) -> str:
    return str(ast.literal_eval(value))


def native_dialogue_ids(template_root: str | Path) -> list[tuple[str, str, str]]:
    """Read the official generated template, never calculate identifiers."""
    found: list[tuple[str, str, str]] = []
    for path in sorted(Path(template_root).rglob("*.rpy")):
        identifier = ""
        for line in path.read_text(encoding="utf-8").splitlines():
            block = _BLOCK.match(line)
            if block:
                identifier = block.group("identifier")
                continue
            comment = _COMMENT.match(line)
            if identifier and comment:
                found.append((_quoted(comment.group("quote")), comment.group("speaker") or "", identifier))
                identifier = ""
    return found


def extract_loose_source(root: str | Path, *, template_root: str | Path | None = None) -> tuple[list[Entry], list[Entry], dict]:
    base = Path(root).resolve()
    game = base / "game"
    ids = native_dialogue_ids(template_root) if template_root else []
    available: dict[tuple[str, str], list[str]] = {}
    for text, speaker, identifier in ids:
        available.setdefault((text, speaker), []).append(identifier)
    main: list[Entry] = []
    review: list[Entry] = []
    for path in sorted([*game.rglob("*.rpy"), *game.rglob("*.rpym")]):
        if "tl" in {part.casefold() for part in path.relative_to(game).parts}:
            continue
        menu_indent: int | None = None
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            rel = path.relative_to(base).as_posix()
            indent = len(line) - len(line.lstrip())
            if _MENU.match(line):
                menu_indent = indent
                continue
            menu_item = _MENU_ITEM.match(line) if menu_indent is not None and indent > menu_indent else None
            if menu_indent is not None and line.strip() and indent <= menu_indent:
                menu_indent = None
            if menu_item:
                text = _quoted(menu_item.group(1))
                entry = Entry(text, rel, f"RenPy:{rel}:{number}:menu", import_method="renpy_string", safety="safe", backend="renpy_loose_source", locator={"line": number, "source": text, "kind": "menu"}, patch_proof=dict(RENPY_STRING_PATCH_PROOF)).finalize()
                main.append(entry)
                continue
            dialog = _DIALOGUE.match(line)
            if dialog:
                text, speaker = _quoted(dialog.group("quote")), dialog.group("speaker") or ""
                identifier_list = available.get((text, speaker), [])
                identifier = identifier_list.pop(0) if identifier_list else ""
                entry = Entry(text, rel, f"RenPy:{rel}:{number}", object_info=speaker, import_method="renpy_dialogue", safety="safe", backend="renpy_loose_source", locator={"line": number, "speaker": speaker, "native_id": identifier}, review_only=not bool(identifier), patch_proof=dict(RENPY_DIALOGUE_PATCH_PROOF) if identifier else {}).finalize()
                (main if identifier else review).append(entry)
            for match in _STRING.finditer(line):
                text = _quoted(match.group(1))
                entry = Entry(text, rel, f"RenPy:{rel}:{number}:string", import_method="renpy_string", safety="safe", backend="renpy_loose_source", locator={"line": number, "source": text}, patch_proof=dict(RENPY_STRING_PATCH_PROOF)).finalize()
                main.append(entry)
    return main, review, {"engine": "RENPY_LOOSE_SOURCE", "native_template": bool(template_root), "files_scanned": len(list(game.rglob("*.rpy"))) + len(list(game.rglob("*.rpym")))}
