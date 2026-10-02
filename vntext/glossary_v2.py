"""Additive, scoped glossary V2 sidecar.

The existing flat ``.mt/glossary.json`` remains supported.  V2 entries are
diagnostic/model metadata and are never copied into ``translation.csv``.
Conflicting equal-priority terms fail closed to REVIEW.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Mapping


SCHEMA_VERSION = 1
GLOSSARY_RELATIVE_PATH = Path(".mt") / "v2" / "glossary.json"
_PROTECTED = re.compile(r"<[^>]*>|\{[^{}]*\}|\\n|\[br\]", re.IGNORECASE)
_KINDS = {"proper_noun", "fixed_phrase", "do_not_translate"}


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _hash(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8", "surrogatepass")).hexdigest()


def _normalise(value: str, case_policy: str = "insensitive") -> str:
    text = " ".join(str(value or "").strip().split())
    return text if case_policy == "sensitive" else text.casefold()


def _tokens(value: str) -> list[str]:
    return _PROTECTED.findall(str(value or ""))


def _entry(raw: Mapping[str, Any], *, source_default: str = "", priority_default: int = 0) -> dict[str, Any] | None:
    source = str(raw.get("source", raw.get("term", source_default)) or "").strip()
    if not source:
        return None
    kind = str(raw.get("kind") or "fixed_phrase").strip().casefold()
    if kind not in _KINDS:
        return None
    target = str(raw.get("target", source) or "")
    if not target or _tokens(source) != _tokens(target):
        return None
    try:
        priority = int(raw.get("priority", priority_default) or priority_default)
    except (TypeError, ValueError):
        priority = priority_default
    case_policy = str(raw.get("case_policy") or "insensitive").casefold()
    if case_policy not in {"insensitive", "sensitive"}:
        case_policy = "insensitive"
    scope = raw.get("scope", "")
    if isinstance(scope, (list, tuple, set)):
        scope = [str(item) for item in scope if str(item).strip()]
    else:
        scope = str(scope or "").strip()
    return {
        "source": source,
        "target": target,
        "kind": kind,
        "priority": priority,
        "proper_noun": bool(raw.get("proper_noun", kind == "proper_noun")),
        "case_policy": case_policy,
        "scope": scope,
        "notes": str(raw.get("notes") or ""),
    }


def load_glossary_v2(package_dir: str | Path | None) -> dict[str, Any]:
    path = Path(package_dir) / GLOSSARY_RELATIVE_PATH if package_dir else Path()
    if not package_dir or not path.is_file():
        payload = {"schema_version": SCHEMA_VERSION, "entries": [], "warnings": [], "source": "missing"}
        payload["fingerprint"] = _hash(payload)
        return payload
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        payload = {"schema_version": SCHEMA_VERSION, "entries": [], "warnings": [f"read_error: {exc}"], "source": str(path)}
        payload["fingerprint"] = _hash(payload)
        return payload
    if not isinstance(raw, Mapping) or int(raw.get("schema_version", 0) or 0) != SCHEMA_VERSION:
        payload = {"schema_version": SCHEMA_VERSION, "entries": [], "warnings": ["unsupported_schema"], "source": str(path)}
        payload["fingerprint"] = _hash(payload)
        return payload
    entries: list[dict[str, Any]] = []
    warnings: list[str] = []
    for index, item in enumerate(raw.get("entries") or []):
        if not isinstance(item, Mapping):
            warnings.append(f"entry_{index}: not_object")
            continue
        value = _entry(item)
        if value is None:
            warnings.append(f"entry_{index}: invalid_or_structural_mismatch")
            continue
        entries.append(value)
    payload = {"schema_version": SCHEMA_VERSION, "entries": entries, "warnings": warnings, "source": str(path)}
    payload["fingerprint"] = _hash({"schema_version": SCHEMA_VERSION, "entries": entries})
    return payload


def load_compatible_entries(package_dir: str | Path | None) -> dict[str, Any]:
    """Merge rich V2 entries with the legacy flat package glossary."""

    payload = load_glossary_v2(package_dir)
    entries = list(payload["entries"])
    if package_dir:
        from vntext.package_glossary import load_user_glossary

        for source, target in load_user_glossary(package_dir).items():
            value = _entry(
                {"source": source, "target": target, "kind": "fixed_phrase"},
                priority_default=0,
            )
            if value:
                entries.append(value)
    return {
        "schema_version": SCHEMA_VERSION,
        "entries": entries,
        "warnings": list(payload.get("warnings") or []),
        "fingerprint": _hash(entries),
    }


def _scope_matches(entry: Mapping[str, Any], row: Mapping[str, Any]) -> bool:
    scope = entry.get("scope")
    if not scope:
        return True
    values = " ".join(str(row.get(name) or "") for name in ("context", "file_path", "import_method", "backend"))
    scopes = scope if isinstance(scope, list) else [scope]
    return all(str(item).casefold() in values.casefold() for item in scopes)


def resolve_exact(source: str, row: Mapping[str, Any], glossary: Mapping[str, Any] | None) -> dict[str, Any]:
    candidates = []
    for item in (glossary or {}).get("entries", []):
        if not isinstance(item, Mapping) or not _scope_matches(item, row):
            continue
        if _normalise(source, str(item.get("case_policy") or "insensitive")) == _normalise(
            str(item.get("source") or ""), str(item.get("case_policy") or "insensitive")
        ):
            if _tokens(source) == _tokens(str(item.get("target") or "")):
                candidates.append(item)
    if not candidates:
        return {"status": "miss", "target": "", "reason": "no_exact_term"}
    highest = max(int(item.get("priority") or 0) for item in candidates)
    targets = {str(item.get("target") or "") for item in candidates if int(item.get("priority") or 0) == highest}
    if len(targets) != 1:
        return {"status": "conflict", "target": "", "reason": "equal_priority_conflict"}
    target = next(iter(targets))
    selected = next(
        item for item in candidates
        if int(item.get("priority") or 0) == highest
        and str(item.get("target") or "") == target
    )
    return {
        "status": "match",
        "target": target,
        "kind": str(selected.get("kind") or "fixed_phrase"),
        "reason": "exact_glossary",
        "priority": highest,
    }


def mask_terms(source: str, row: Mapping[str, Any], glossary: Mapping[str, Any] | None) -> tuple[str, dict[str, str], list[str]]:
    """Mask rich terms only outside tags/placeholders/control tokens."""

    entries = [
        item for item in (glossary or {}).get("entries", [])
        if isinstance(item, Mapping) and _scope_matches(item, row)
    ]
    entries.sort(key=lambda item: (-int(item.get("priority") or 0), -len(str(item.get("source") or ""))))
    restores: dict[str, str] = {}
    conflicts: list[str] = []
    masked = str(source or "")
    token_index = 900000
    for item in entries:
        term = str(item.get("source") or "").strip()
        target = str(item.get("target") or "")
        if not term or not target or _tokens(term) or _tokens(target):
            continue
        exact = resolve_exact(term, {**row, "source_text": term}, glossary)
        if exact.get("status") == "conflict":
            conflicts.append(term)
            continue
        token = f"ZZG{token_index}ZZG"
        token_index += 1
        flags = 0 if str(item.get("case_policy") or "insensitive") == "sensitive" else re.IGNORECASE
        pattern = re.compile(r"(?<!\w)" + re.escape(term) + r"(?!\w)", flags)
        chunks: list[str] = []
        last = 0
        for match in _PROTECTED.finditer(masked):
            segment = masked[last : match.start()]
            segment = pattern.sub(token, segment)
            chunks.append(segment)
            chunks.append(match.group(0))
            last = match.end()
        chunks.append(pattern.sub(token, masked[last:]))
        candidate = "".join(chunks)
        if candidate != masked:
            restores[token] = target
            masked = candidate
    return masked, restores, conflicts


def restore_terms(text: str, restores: Mapping[str, str]) -> str:
    result = str(text or "")
    for token, target in restores.items():
        result = result.replace(token, str(target))
    return result


__all__ = [
    "SCHEMA_VERSION",
    "GLOSSARY_RELATIVE_PATH",
    "load_glossary_v2",
    "load_compatible_entries",
    "resolve_exact",
    "mask_terms",
    "restore_terms",
]
