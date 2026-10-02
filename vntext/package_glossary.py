"""Package-owned glossary helpers.

VNText deliberately ships no game-specific translation memory.  A user or
package can opt in to a small exact glossary under ``.mt/glossary.json``;
these helpers preserve placeholders and markup while applying that data.
"""

from __future__ import annotations

import json
import re
from pathlib import Path


_GLOSSARY_PROTECTED = re.compile(r"<[^>]*>|\\{[^{}]*\\}|\\\\n|\\[br\\]", re.IGNORECASE)


def _normalise(value: object) -> str:
    return " ".join(str(value or "").strip().lower().split())


def load_user_glossary(package_dir: str | Path | None = None) -> dict[str, str]:
    """Load a package-owned flat glossary without any bundled fallback data."""

    if not package_dir:
        return {}
    path = Path(package_dir) / ".mt" / "glossary.json"
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(data, dict):
        return {}
    return {
        key: str(value).strip()
        for raw_key, value in data.items()
        if (key := _normalise(raw_key)) and str(value).strip()
    }


def load_package_glossary(package_dir: str | Path | None = None) -> dict[str, str]:
    """Compatibility alias for the package-owned flat glossary."""

    return load_user_glossary(package_dir)


def _structure_tokens(text: str) -> list[str]:
    return _GLOSSARY_PROTECTED.findall(str(text or ""))


def lookup_user_phrase(src: str, glossary: dict[str, str] | None = None) -> str | None:
    """Return an exact user glossary translation only when structure matches."""

    table = glossary or {}
    value = table.get(_normalise(src))
    if value is None:
        value = next(
            (
                candidate
                for candidate_key, candidate in table.items()
                if _normalise(candidate_key) == _normalise(src)
            ),
            None,
        )
    if value is None or _structure_tokens(src) != _structure_tokens(str(value)):
        return None
    return str(value)


def mask_user_glossary_terms(
    src: str, glossary: dict[str, str] | None = None
) -> tuple[str, dict[str, str]]:
    """Mask package-owned terms without matching inside protected tokens."""

    table = glossary or {}
    if not src or not table:
        return src, {}
    terms = [(key, value) for key, value in table.items() if key and value and not _structure_tokens(key)]
    terms.sort(key=lambda item: len(item[0]), reverse=True)
    if not terms:
        return src, {}
    restore: dict[str, str] = {}
    counter = 9000

    def mask_plain(plain: str) -> str:
        nonlocal counter
        result = plain
        for key, value in terms:
            def replace(_match: re.Match[str]) -> str:
                nonlocal counter
                token = f"ZZG{counter:04d}ZZ"
                counter += 1
                restore[token] = str(value)
                return token

            result = re.sub(re.escape(key), replace, result, flags=re.IGNORECASE)
        return result

    parts: list[str] = []
    last = 0
    for match in _GLOSSARY_PROTECTED.finditer(src):
        parts.append(mask_plain(src[last : match.start()]))
        parts.append(match.group(0))
        last = match.end()
    parts.append(mask_plain(src[last:]))
    return "".join(parts), restore


def restore_user_glossary_terms(text: str, restore: dict[str, str]) -> str:
    result = str(text or "")
    for token, value in restore.items():
        result = result.replace(token, value)
    return result


def lookup_short_phrase(src: str, *, glossary: dict[str, str] | None = None) -> str | None:
    """Compatibility helper; only caller-supplied/package glossary data applies."""

    return lookup_user_phrase(src, glossary)
