"""Bounded, engine-aware context sidecar for Local Translation V2."""

from __future__ import annotations

import json
import os
import uuid
from pathlib import Path
from typing import Any, Mapping


CONTEXT_SCHEMA_VERSION = 1
CONTEXT_BUILDER_VERSION = "local-translation-v2-context-1"
CONTEXT_RELATIVE_PATH = Path(".mt") / "v2" / "context.jsonl"


def _engine_family(row: Mapping[str, Any]) -> str:
    text = " ".join(str(row.get(name) or "").casefold() for name in ("context", "file_path", "import_method", "backend"))
    if "naninovel" in text:
        return "naninovel"
    if "unity" in text or "textasset" in text:
        return "unity"
    if any(token in text for token in ("json", "csv", "xml", "sqlite", "structured")):
        return "structured"
    return "unknown"


def _group_key(row: Mapping[str, Any]) -> tuple[str, str, str] | None:
    """Only group when the extractor provides a real boundary identifier."""

    boundary = row.get("context_group") or row.get("scene_id") or row.get("block_id")
    if not boundary:
        return None
    return (
        str(row.get("file_path") or ""),
        _engine_family(row),
        str(boundary),
    )


def build_context_records(
    rows: list[Mapping[str, Any]],
    *,
    max_chars: int = 1200,
    max_items: int = 1,
) -> list[dict[str, Any]]:
    """Build windows without crossing file/engine/explicit-boundary groups."""

    bounded_chars = max(256, min(int(max_chars), 8000))
    bounded_items = max(0, min(int(max_items), 2))
    groups: dict[tuple[str, str, str], list[int]] = {}
    for index, row in enumerate(rows):
        group = _group_key(row)
        if group is not None:
            groups.setdefault(group, []).append(index)
    records: list[dict[str, Any]] = []
    for index, row in enumerate(rows):
        current = str(row.get("source_text") or "")
        group = _group_key(row)
        peers = groups.get(group, []) if group is not None else []
        position = peers.index(index) if index in peers else -1
        previous = []
        following = []
        if position >= 0:
            previous = [str(rows[peers[position - offset]].get("source_text") or "") for offset in range(1, bounded_items + 1) if position - offset >= 0]
            following = [str(rows[peers[position + offset]].get("source_text") or "") for offset in range(1, bounded_items + 1) if position + offset < len(peers)]
        used = len(current)
        def trim(values: list[str]) -> list[str]:
            nonlocal used
            kept: list[str] = []
            for value in values:
                if used >= bounded_chars:
                    break
                clipped = value[: max(0, bounded_chars - used)]
                kept.append(clipped)
                used += len(clipped)
            return kept
        previous = trim(previous)
        following = trim(following)
        records.append(
            {
                "schema_version": CONTEXT_SCHEMA_VERSION,
                "builder_version": CONTEXT_BUILDER_VERSION,
                "key": str(row.get("key") or ""),
                "engine_family": _engine_family(row),
                "file_path": str(row.get("file_path") or ""),
                "import_method": str(row.get("import_method") or ""),
                "boundary": str((row.get("context_group") or row.get("scene_id") or row.get("block_id") or "")),
                "speaker": str(row.get("speaker") or ""),
                "status": "bounded" if group is not None else "insufficient_metadata",
                "previous": previous,
                "current": current[:bounded_chars],
                "next": following,
            }
        )
    return records


def write_context_sidecar(package_dir: str | Path, records: list[Mapping[str, Any]]) -> Path:
    path = Path(package_dir) / CONTEXT_RELATIVE_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    with temp.open("w", encoding="utf-8", newline="\n") as handle:
        for record in records:
            handle.write(json.dumps(dict(record), ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temp, path)
    return path


def build_context_sidecar(package_dir: str | Path, rows: list[Mapping[str, Any]]) -> dict[str, Any]:
    records = build_context_records(rows)
    path = write_context_sidecar(package_dir, records)
    return {
        "schema_version": CONTEXT_SCHEMA_VERSION,
        "builder_version": CONTEXT_BUILDER_VERSION,
        "status": "METADATA_ONLY",
        "model_injection": False,
        "status_reason": "Context is bounded metadata/fingerprint; the current CT2 contract does not inject it into model prompts.",
        "path": str(path),
        "records": records,
        "bounded_records": sum(record["status"] == "bounded" for record in records),
        "insufficient_metadata": sum(record["status"] == "insufficient_metadata" for record in records),
    }


__all__ = [
    "CONTEXT_SCHEMA_VERSION",
    "CONTEXT_BUILDER_VERSION",
    "build_context_records",
    "write_context_sidecar",
    "build_context_sidecar",
]
