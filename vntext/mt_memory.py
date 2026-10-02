"""Deterministic package-scoped translation memory for offline MT.

The memory is a consistency aid, not a model or a replacement for review.  It
only reuses a translation when the normalized source, import method and
context family identify one unambiguous previous translation.  User glossary
lookups still run first.
"""
from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path

MEMORY_VERSION = "1.0.0"
MEMORY_NAME = "translation_memory.json"


def normalize_memory_text(value: str) -> str:
    value = unicodedata.normalize("NFKC", str(value or "")).casefold()
    return re.sub(r"\s+", " ", value).strip()


def context_family(row: dict) -> str:
    context = str(row.get("context") or "").strip()
    if not context:
        return ""
    return context.split(":", 1)[0].casefold()


def _memory_key(row: dict) -> tuple[str, str, str]:
    return (
        normalize_memory_text(str(row.get("source_text") or "")),
        str(row.get("import_method") or "").strip(),
        context_family(row),
    )


def build_translation_memory(rows: list[dict], package_dir: str | Path | None = None) -> dict:
    """Build unique, structurally valid source→translation entries.

    Ambiguous source strings are intentionally omitted.  This prevents a
    choice label or repeated line from leaking wording from another context.
    """
    from vntext.mt_translation_safety import validate_candidate
    from vntext.patch_gate import load_whitelist

    whitelist = load_whitelist(Path(package_dir)) if package_dir else set()
    grouped: dict[tuple[str, str, str], set[str]] = {}
    examples: dict[tuple[str, str, str], dict] = {}
    for row in rows:
        source = str(row.get("source_text") or "").strip()
        translation = str(row.get("translation") or "").strip()
        if not source or not translation or source == translation:
            continue
        if validate_candidate(row, translation, whitelist):
            continue
        key = _memory_key(row)
        grouped.setdefault(key, set()).add(translation)
        examples[key] = row

    entries = []
    for (source, method, family), values in sorted(grouped.items()):
        if len(values) != 1:
            continue
        entries.append({
            "source": source,
            "import_method": method,
            "context_family": family,
            "translation": next(iter(values)),
        })
    memory = {
        "version": MEMORY_VERSION,
        "entries": entries,
        "source_rows": len(rows),
        "unique_entries": len(entries),
    }
    if package_dir:
        path = Path(package_dir) / ".mt" / MEMORY_NAME
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(memory, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return memory


def load_translation_memory(package_dir: str | Path | None) -> dict:
    if not package_dir:
        return {"version": MEMORY_VERSION, "entries": []}
    path = Path(package_dir) / ".mt" / MEMORY_NAME
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"version": MEMORY_VERSION, "entries": []}
    if not isinstance(payload, dict) or payload.get("version") != MEMORY_VERSION:
        return {"version": MEMORY_VERSION, "entries": []}
    entries = payload.get("entries")
    if not isinstance(entries, list):
        return {"version": MEMORY_VERSION, "entries": []}
    return {**payload, "entries": [entry for entry in entries if isinstance(entry, dict)]}


def lookup_translation_memory(row: dict, memory: dict | None) -> str | None:
    if not memory:
        return None
    source, method, family = _memory_key(row)
    if not source:
        return None
    exact = [
        entry for entry in memory.get("entries", [])
        if str(entry.get("source") or "") == source
        and str(entry.get("import_method") or "") == method
        and str(entry.get("context_family") or "") == family
    ]
    if len(exact) == 1:
        return str(exact[0].get("translation") or "").strip() or None
    # Fallback only when the same method has one unambiguous wording across
    # context families; context is still part of the preference order above.
    same_method = [
        entry for entry in memory.get("entries", [])
        if str(entry.get("source") or "") == source
        and str(entry.get("import_method") or "") == method
    ]
    values = {str(entry.get("translation") or "").strip() for entry in same_method}
    return next(iter(values)) if len(values) == 1 and next(iter(values), "") else None
