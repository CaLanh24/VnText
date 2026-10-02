"""Intentional EN/literal keeps — ledger + reconcile review_only orphans."""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from vntext import mt_check
from vntext.mt_classify import (
    classify_row_authoritative,
    is_exclaim_moan_line,
    is_debug_or_symbol_keep_line,
    is_hesitation_keep_line,
    is_proper_name_keep_line,
    is_sound_effect_line,
    is_star_sfx_line,
    is_non_english_scene_marker_line,
    is_numbered_series_marker,
    is_censored_line,
    is_opaque_all_caps_line,
    is_technical_token,
)
from vntext.mt_paths import ensure_mt_dir, paths_for_csv
from vntext.package_io import CSV_FIELDS, read_csv_rows_file, write_csv_rows_file


LogFn = Callable[[str], None] | None

# These are non-lexical vocalisations/SFX from the script.  They are player-
# visible, but translating the token would change the intended sound rather
# than localise a word.  Keep the decision explicit so QA never treats them as
# an unexplained English miss.
_VOCALIZATION_KEEP_EXACT = {
    "Aha ha ha.",
}


def _ledger_path(package_dir: Path) -> Path:
    return paths_for_csv(package_dir / "translation.csv").mt_dir / "intentional_keep_ledger.json"


def load_intentional_keep_ledger(package_dir: Path | str) -> dict:
    path = _ledger_path(Path(package_dir))
    if not path.is_file():
        return {"keys": {}}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"keys": {}}
    if not isinstance(data, dict):
        return {"keys": {}}
    data.setdefault("keys", {})
    return data


def save_intentional_keep_ledger(package_dir: Path | str, ledger: dict) -> Path:
    pkg = Path(package_dir)
    paths = paths_for_csv(pkg / "translation.csv")
    ensure_mt_dir(paths)
    path = _ledger_path(pkg)
    path.write_text(json.dumps(ledger, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def is_player_visible_row(row: dict) -> bool:
    ctx = str(row.get("context") or "")
    im = str(row.get("import_method") or "")
    if ctx.endswith(":choice") or ctx.endswith(":print") or ":choice:" in ctx:
        return True
    if im in {"naninovel_choice", "naninovel_print"}:
        return True
    if intentional_keep_reason(row):
        return False
    action, _reason, _decision = classify_row_authoritative({**row, "translation": ""})
    return action in {"translate", "translate_synonym", "ui_label_fixed"}


def intentional_keep_reason(row: dict) -> str | None:
    """Return keep reason for literal source==translation, or None if MT/dialogue expected."""
    src = str(row.get("source_text") or "").strip()
    ctx = str(row.get("context") or "")
    if not src:
        return None
    if is_star_sfx_line(src):
        return "star_sfx"
    if is_censored_line(src):
        return "censored_source"
    if is_opaque_all_caps_line(src):
        return "opaque_all_caps_marker"
    if src in _VOCALIZATION_KEEP_EXACT:
        return "vocalization_sfx"
    if "never edit the above lines" in src.casefold() and "auto-save" in src.casefold():
        return "editor_autosave_note"
    if re.fullmatch(r"\(?LOCKED\d*\)?", src, flags=re.IGNORECASE):
        return "status_label_locked"
    if re.fullmatch(r"TRAUMA\+", src, flags=re.IGNORECASE):
        return "status_token"
    if re.fullmatch(r"BP\s*\+\s*\d{1,3}", src, flags=re.IGNORECASE):
        return "status_token"
    if re.fullmatch(r"KARMA\+", src, flags=re.IGNORECASE):
        return "status_token"
    if is_numbered_series_marker(src):
        return "scene_marker"
    if is_non_english_scene_marker_line(src):
        return "non_english_scene_marker"
    if re.fullmatch(r"(?:ha\s*){4,}[.!?…]*", src, flags=re.IGNORECASE):
        return "vocalization_sfx"
    if re.fullmatch(r"(?:la\s*){2,}[.!?…\-]*", src, flags=re.IGNORECASE):
        return "vocalization_sfx"
    if re.fullmatch(r"(?:oink[\s.!?…!]*){2,}", src, flags=re.IGNORECASE):
        return "vocalization_sfx"
    if src.casefold() in {"discord", "subscribestar"}:
        return "brand_name"
    if re.search(r"[\uac00-\ud7a3\u3040-\u30ff\u4e00-\u9fff]", src):
        return "source_non_english"
    if is_sound_effect_line(src):
        return "sound_effect"
    if is_exclaim_moan_line(src):
        return "exclaim_or_moan_short"
    if is_hesitation_keep_line(src):
        return "hesitation_short"
    if is_debug_or_symbol_keep_line(src):
        return "debug_or_brand"
    if is_proper_name_keep_line(src):
        return "proper_name"
    if mt_check.is_script_identifier(src, ctx):
        return "naninovel_script_identifier"
    if is_technical_token(src):
        low = src.lower()
        if "autosave" in low and "do not delete" in low:
            return "editor_autosave_note"
        if re.fullmatch(r"\{[A-Za-z][A-Za-z0-9_]*\}\.[A-Za-z][A-Za-z0-9_]*", src):
            return "naninovel_label_ref"
        if re.fullmatch(
            r"\{[A-Za-z][A-Za-z0-9_]*\}[A-Za-z0-9_]*\.[A-Za-z][A-Za-z0-9_]*", src
        ):
            return "naninovel_tween_id"
        if ("&&" in src or "||" in src) or mt_check.COND_EXPR.search(src):
            return "condition_expression"
        ident = mt_check.identical_reason(src, ctx)
        if ident and ident != "SUSPICIOUS":
            return ident.replace(" ", "_").replace("/", "_")
        return "technical_token"
    return None


def _prune_review_only_keys(package_dir: Path, keys: set[str]) -> int:
    review_path = package_dir / "review_only.csv"
    if not review_path.is_file() or not keys:
        return 0
    fields, existing = read_csv_rows_file(review_path)
    kept = [r for r in existing if str(r.get("key") or "") not in keys]
    removed = len(existing) - len(kept)
    if removed:
        write_csv_rows_file(review_path, fields or CSV_FIELDS, kept)
    return removed


def apply_intentional_keep_batch(
    package_dir: Path | str,
    rows: list[dict] | None = None,
    fields: list[str] | None = None,
    csv_path: Path | str | None = None,
    *,
    emit: LogFn = None,
    protected_review_keys: set[str] | None = None,
) -> dict:
    """Apply literal keep for technical/script rows; update ledger; prune review_only."""
    pkg = Path(package_dir)
    csv_path = Path(csv_path) if csv_path else pkg / "translation.csv"
    if rows is None or fields is None:
        fields, rows = read_csv_rows_file(csv_path)

    review_keys: set[str] = set()
    review_path = pkg / "review_only.csv"
    if review_path.is_file():
        _, rev_rows = read_csv_rows_file(review_path)
        review_keys = {str(r.get("key") or "") for r in rev_rows if r.get("key")}
    protected = {str(key) for key in protected_review_keys or set() if str(key)}

    ledger = load_intentional_keep_ledger(pkg)
    keys_map = ledger.setdefault("keys", {})
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    applied: list[dict] = []
    by_key = {r["key"]: r for r in rows}

    for row in rows:
        key = str(row.get("key") or "")
        if not key or key not in review_keys or key in protected:
            continue
        src = str(row.get("source_text") or "").strip()
        tr = str(row.get("translation") or "").strip()
        reason = intentional_keep_reason(row)
        if not reason or not src:
            continue
        if tr and tr != src:
            continue

        row["translation"] = src
        keys_map[key] = {
            "reason": reason,
            "source_text": src,
            "context": row.get("context", ""),
            "import_method": row.get("import_method", ""),
            "player_visible": is_player_visible_row(row),
            "recorded_at": now,
        }
        applied.append({"key": key, "reason": reason, "player_visible": keys_map[key]["player_visible"]})

    # Reconcile already-literal rows too. A keep is only accepted when the
    # classifier can state a concrete reason; this prevents QA from treating
    # an unreviewed English dialogue row as an intentional keep.
    recorded = 0
    for row in rows:
        key = str(row.get("key") or "")
        src = str(row.get("source_text") or "").strip()
        tr = str(row.get("translation") or "").strip()
        reason = intentional_keep_reason(row)
        if not key or key in protected or not src or tr != src or not reason or key in keys_map:
            continue
        keys_map[key] = {
            "reason": reason,
            "source_text": src,
            "context": row.get("context", ""),
            "import_method": row.get("import_method", ""),
            "player_visible": False,
            "recorded_at": now,
        }
        recorded += 1

    if not applied and not recorded:
        return {"applied": 0, "recorded": 0, "ledger_path": str(_ledger_path(pkg)), "pruned_review": 0}

    write_csv_rows_file(csv_path, fields or CSV_FIELDS, rows)
    ledger["updated_at"] = now
    ledger_path = save_intentional_keep_ledger(pkg, ledger)
    pruned = _prune_review_only_keys(pkg, {a["key"] for a in applied})
    if emit:
        emit(
            f"intentional_keep: {len(applied)} dòng literal "
            f"(ledger ghi thêm {recorded}, review_only gỡ {pruned}) → {ledger_path.name}"
        )
    return {
        "applied": len(applied),
        "recorded": recorded,
        "rows": applied,
        "ledger_path": str(ledger_path),
        "pruned_review": pruned,
    }


def classify_review_only_status(package_dir: Path | str) -> dict:
    """Phân loại review_only còn lại: unresolved vs ledger/intentional."""
    pkg = Path(package_dir)
    ledger = load_intentional_keep_ledger(pkg)
    ledger_keys = set(ledger.get("keys") or {})
    review_path = pkg / "review_only.csv"
    unresolved: list[dict] = []
    if review_path.is_file():
        _, rev = read_csv_rows_file(review_path)
        for r in rev:
            k = str(r.get("key") or "")
            if k in ledger_keys:
                continue
            unresolved.append(
                {
                    "key": k,
                    "source_text": (r.get("source_text") or "")[:120],
                    "patch_note": (r.get("patch_note") or "")[:120],
                }
            )
    return {
        "review_only_total": _count_review_rows(pkg),
        "ledger_keys": len(ledger_keys),
        "review_only_unresolved": len(unresolved),
        "unresolved_samples": unresolved[:10],
    }


def _count_review_rows(pkg: Path) -> int:
    p = pkg / "review_only.csv"
    if not p.is_file():
        return 0
    _, rows = read_csv_rows_file(p)
    return len(rows)
