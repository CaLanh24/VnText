"""Safe field-level XML extraction and patching.

The route deliberately rewrites a parsed XML tree instead of applying byte
offset guesses.  Locators identify an element by its child-element path and
distinguish element text from selected text-like attributes.  The writer
checks the original value before changing anything and preserves UTF-8 BOM,
newline style and final-newline presence.  Formatting may be canonicalized by
``ElementTree``; callers must use the reopen/semantic gate before promotion.
"""

from __future__ import annotations

import codecs
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Iterable

from vntext.entry import Entry
from vntext.extract_text import textasset_line_quality
from vntext.patchability import STRUCTURED_XML_PATCH_PROOF


_TEXT_ATTRIBUTE_NAMES = {
    "text",
    "value",
    "translation",
    "label",
    "displayname",
    "display_name",
    "content",
    "description",
    "dialogue",
    "sentence",
    "message",
}
_XML_DECLARATION_RE = re.compile(r"^\s*<\?xml\b", re.IGNORECASE)
_UNSAFE_XML_DECLARATION_RE = re.compile(r"<!\s*(?:DOCTYPE|ENTITY)\b", re.IGNORECASE)


def _read_xml(path: Path) -> tuple[ET.ElementTree, bool, str, bool]:
    raw = path.read_bytes()
    has_bom = raw.startswith(codecs.BOM_UTF8)
    text = raw.decode("utf-8-sig")
    if _UNSAFE_XML_DECLARATION_RE.search(text):
        raise ValueError("DTD/entity XML is outside the safe structured writer route")
    original_newline = "\r\n" if "\r\n" in text else "\n"
    had_final_newline = text.endswith(("\n", "\r"))
    parser = ET.XMLParser(target=ET.TreeBuilder(insert_comments=True, insert_pis=True))
    root = ET.fromstring(text, parser=parser)
    return ET.ElementTree(root), has_bom, original_newline, had_final_newline


def _element_children(element: ET.Element) -> list[ET.Element]:
    return [child for child in list(element) if isinstance(child.tag, str)]


def _element_at(root: ET.Element, path: Iterable[Any]) -> ET.Element | None:
    current = root
    try:
        for raw_index in path:
            index = int(raw_index)
            children = _element_children(current)
            if not 0 <= index < len(children):
                return None
            current = children[index]
    except (TypeError, ValueError):
        return None
    return current


def _element_path(root: ET.Element, target: ET.Element) -> list[int] | None:
    if root is target:
        return []

    def walk(current: ET.Element, prefix: list[int]) -> list[int] | None:
        for index, child in enumerate(_element_children(current)):
            candidate = [*prefix, index]
            if child is target:
                return candidate
            found = walk(child, candidate)
            if found is not None:
                return found
        return None

    return walk(root, [])


def _eligible(value: str | None) -> bool:
    return bool(value and value.strip() and textasset_line_quality(value.strip()))


def _entry(path: Path, root: Path, value: str, locator: dict[str, Any], context: str) -> Entry:
    rel = path.relative_to(root).as_posix()
    return Entry(
        source_text=value,
        file_path=rel,
        context=context,
        object_info=f"XML {context}",
        import_method="structured_xml_value",
        safety="safe",
        locator=locator,
        backend="structured_xml",
        patch_proof=dict(STRUCTURED_XML_PATCH_PROOF),
    ).finalize()


def extract_structured_xml(path: Path, root: Path) -> Iterable[Entry]:
    """Yield text nodes and explicitly text-like attributes from valid XML."""

    try:
        tree, _has_bom, _newline, _final_newline = _read_xml(path)
    except (OSError, UnicodeDecodeError, ET.ParseError, ValueError):
        return

    xml_root = tree.getroot()
    stack = [xml_root]
    while stack:
        element = stack.pop()
        element_path = _element_path(xml_root, element)
        if element_path is None:
            continue
        for name in sorted(element.attrib):
            local_name = str(name).rsplit("}", 1)[-1]
            normalized = local_name.casefold().replace("-", "_")
            if normalized not in _TEXT_ATTRIBUTE_NAMES:
                continue
            value = element.attrib.get(name)
            if _eligible(value):
                yield _entry(
                    path,
                    root,
                    str(value),
                    {
                        "xml_path": element_path,
                        "node_kind": "attribute",
                        "attribute": name,
                    },
                    f"element_path=/{'/'.join(map(str, element_path))}/@{name}",
                )
        if _eligible(element.text):
            yield _entry(
                path,
                root,
                str(element.text),
                {"xml_path": element_path, "node_kind": "text"},
                f"element_path=/{'/'.join(map(str, element_path))}",
            )
        stack.extend(reversed(_element_children(element)))


def _preserve_outer_whitespace(source: str, replacement: str) -> str:
    leading = source[: len(source) - len(source.lstrip())]
    trailing = source[len(source.rstrip()) :]
    return f"{leading}{replacement}{trailing}"


def patch_structured_xml(
    source: Path,
    target: Path,
    items: Iterable[tuple[dict, str]],
) -> tuple[int, int]:
    """Patch XML values using path/kind locators and source preconditions."""

    tree, has_bom, original_newline, had_final_newline = _read_xml(source)
    root = tree.getroot()
    changed = 0
    skipped = 0
    for entry, translation in items:
        locator = entry.get("locator") or {}
        element = _element_at(root, locator.get("xml_path", []))
        kind = str(locator.get("node_kind") or "text")
        source_text = str(entry.get("source_text") or "")
        if element is None or not source_text:
            skipped += 1
            continue
        if kind == "attribute":
            attribute = str(locator.get("attribute") or "")
            current = element.attrib.get(attribute)
            if current != source_text:
                skipped += 1
                continue
            element.attrib[attribute] = _preserve_outer_whitespace(source_text, str(translation))
        elif kind == "text":
            current = element.text
            if current != source_text:
                skipped += 1
                continue
            element.text = _preserve_outer_whitespace(source_text, str(translation))
        else:
            skipped += 1
            continue
        changed += 1

    xml_declaration = bool(_XML_DECLARATION_RE.match(source.read_text(encoding="utf-8-sig")))
    rendered = ET.tostring(root, encoding="utf-8", xml_declaration=xml_declaration).decode("utf-8")
    if original_newline == "\r\n":
        rendered = rendered.replace("\r\n", "\n").replace("\n", "\r\n")
    if had_final_newline and not rendered.endswith(original_newline):
        rendered += original_newline
    elif not had_final_newline:
        rendered = rendered.rstrip("\r\n")
    payload = (codecs.BOM_UTF8 if has_bom else b"") + rendered.encode("utf-8")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(payload)
    return changed, skipped


__all__ = ["extract_structured_xml", "patch_structured_xml"]
