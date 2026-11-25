"""Per-unit accounting of Ren'Py native units against the package buckets.

Every native unit (SDK dialogue/string unit or proven static display slot) must land in exactly one bucket: a package row (main, review or
technical-skipped), an engine-common exclusion, or a row the user (or the machine-syntax cleanup before translation) removed earlier.  A unit in
none of them is named here - masked: kind, hashed file, line - so a bug report can show WHAT was not counted without any file name or text.
"""
from __future__ import annotations

import hashlib
from collections import Counter
from pathlib import PurePosixPath

SAMPLE_CAP = 50


def mask_file(path: str) -> str:
    """Stable, anonymous label for a game file: a hash of its relative path plus its extension (no name)."""
    normalized = str(path).replace("\\", "/")
    return "f" + hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:10] + PurePosixPath(normalized).suffix.lower()


def reconcile_native_units(index, *, package_contexts, engine_common_contexts, user_excluded_contexts, counts, native_units,
                           sample_cap: int = SAMPLE_CAP) -> dict:
    buckets: Counter = Counter()
    unaccounted = []
    seen: Counter = Counter(str(unit.get("context") or "") for unit in index)
    for unit in index:
        context = str(unit.get("context") or "")
        if context in user_excluded_contexts:
            buckets["user_excluded"] += 1
        elif context in engine_common_contexts:
            buckets["engine_common_excluded"] += 1
        elif context in package_contexts:
            buckets["package_row"] += 1
        else:
            unaccounted.append(unit)
    duplicate_identities = sum(count - 1 for count in seen.values() if count > 1)
    by_kind = Counter(str(unit.get("kind") or "unknown") for unit in unaccounted)
    by_file = Counter(mask_file(str(unit.get("file") or "")) for unit in unaccounted)
    samples = [{"kind": str(unit.get("kind") or "unknown"), "file": mask_file(str(unit.get("file") or "")),
                "line": unit.get("line") if isinstance(unit.get("line"), int) else None}
               for unit in unaccounted[:max(0, int(sample_cap))]]
    return {
        "schema_version": 1,
        "native_units": int(native_units),
        "indexed_units": len(index),
        "index_complete": len(index) == int(native_units),
        "duplicate_identities": duplicate_identities,
        "buckets": dict(sorted(buckets.items())),
        "package_counts": dict(counts),
        "unaccounted_count": len(unaccounted),
        "unaccounted_by_kind": dict(sorted(by_kind.items())),
        "unaccounted_by_file": dict(sorted(by_file.items())),
        "unaccounted": [dict(item) for item in samples],
        "unaccounted_truncated": len(unaccounted) > len(samples),
        "masking": "file = sha256(relative path)[:10] + extension; no file names, no text, no identifiers",
    }
