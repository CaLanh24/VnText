# -*- coding: utf-8 -*-

"""Cache/checkpoint MT theo key + source + kind + strategy + rule_version.

Dùng để chỉ dịch lại dòng fail / bị ảnh hưởng — không full reset.
"""

from __future__ import annotations

import sys
from pathlib import Path

def _tests_lib_on_path() -> None:
    cur = Path(__file__).resolve().parent
    while cur.name != "tests" and cur.parent != cur:
        cur = cur.parent
    lib = cur / "lib"
    p = str(lib)
    if p not in sys.path:
        sys.path.insert(0, p)

_tests_lib_on_path()
from bootstrap import bootstrap
TESTS, ROOT, LIB = bootstrap(__file__)

sys.path.insert(0, str(TESTS / "harness" / "crash"))
sys.path.insert(0, str(TESTS / "harness" / "vh_parity"))
sys.path.insert(0, str(TESTS / "harness" / "naninovel"))

import hashlib
import json
from pathlib import Path
from typing import Any

# Tăng khi đổi rule validate / classify / strategy ảnh hưởng kết quả.
RULE_VERSION = "2026-08-26.tier17"


def sha256_text(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


def entry_fingerprint(row: dict, *, strategy: str = "", kind: str = "") -> dict[str, str]:
    src = str(row.get("source_text") or "")
    return {
        "key": str(row.get("key") or ""),
        "source_sha": sha256_text(src),
        "kind": kind or str(row.get("text_kind") or ""),
        "strategy": strategy,
        "rule_version": RULE_VERSION,
        "translation_sha": sha256_text(str(row.get("translation") or "")),
    }


def load_cache(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {"rule_version": RULE_VERSION, "entries": {}}
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"rule_version": RULE_VERSION, "entries": {}}
    if doc.get("rule_version") != RULE_VERSION:
        # Rule đổi → cache hết hạn (giữ file để audit, entries rỗng logic).
        return {"rule_version": RULE_VERSION, "entries": {}, "stale_from": doc.get("rule_version")}
    doc.setdefault("entries", {})
    return doc


def save_cache(path: Path, doc: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    doc["rule_version"] = RULE_VERSION
    path.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def cache_hit(doc: dict[str, Any], row: dict, *, kind: str = "") -> bool:
    key = str(row.get("key") or "")
    ent = (doc.get("entries") or {}).get(key)
    if not ent or not ent.get("pass"):
        return False
    if ent.get("rule_version") != RULE_VERSION:
        return False
    src_sha = sha256_text(str(row.get("source_text") or ""))
    if ent.get("source_sha") != src_sha:
        return False
    if kind and ent.get("kind") and ent.get("kind") != kind:
        return False
    tr = str(row.get("translation") or "").strip()
    if not tr:
        return False
    return ent.get("translation_sha") == sha256_text(tr)


def record_pass(
    doc: dict[str, Any],
    row: dict,
    *,
    kind: str = "",
    strategy: str = "",
) -> None:
    fp = entry_fingerprint(row, strategy=strategy, kind=kind)
    fp["pass"] = True
    doc.setdefault("entries", {})[fp["key"]] = fp


def record_fail(
    doc: dict[str, Any],
    row: dict,
    *,
    kind: str = "",
    reasons: list[str] | None = None,
) -> None:
    fp = entry_fingerprint(row, kind=kind)
    fp["pass"] = False
    fp["reasons"] = reasons or []
    doc.setdefault("entries", {})[fp["key"]] = fp


def keys_needing_mt(
    rows: list[dict],
    doc: dict[str, Any],
    *,
    fail_keys: set[str] | None = None,
    kinds: set[str] | None = None,
    kind_fn=None,
) -> list[str]:
    """Keys cần MT: fail tường minh, hoặc chưa cache-hit."""
    out: list[str] = []
    for row in rows:
        key = str(row.get("key") or "")
        if not key:
            continue
        kind = kind_fn(row) if kind_fn else ""
        if kinds and kind not in kinds:
            continue
        if fail_keys is not None and key not in fail_keys:
            # Chỉ chạy tập fail khi được chỉ định.
            continue
        if fail_keys is None and cache_hit(doc, row, kind=kind):
            continue
        if fail_keys is not None or not str(row.get("translation") or "").strip() or not cache_hit(doc, row, kind=kind):
            out.append(key)
    return out
