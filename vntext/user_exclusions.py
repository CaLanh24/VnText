"""User row exclusions for ONE translation CSV ("Xóa dòng đã chọn").

The user works with a single CSV.  Removing rows is a recorded decision, not a silent edit:
* the CSV is rewritten atomically only if its SHA-256 still equals the revision the user looked at (conflict protection),
  with the same header/schema, UTF-8 BOM and all remaining rows byte-for-byte equal in content;
* each removed row is recorded in the companion ``user_exclusions.json`` by its stable key plus the SHA-256 of its source text and its
  provenance, so a re-extraction of the same package does not resurrect it, while a row whose SOURCE changed (different sha) returns;
* the manifest is never edited: a manifest entry without a CSV row is an omitted (untranslated) row for the patch, never a patched one.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import os
import tempfile
import time
from pathlib import Path

EXCLUSIONS_FILE = "user_exclusions.json"
SCHEMA = 1


class ExclusionConflict(ValueError):
    """The CSV changed since the revision the user selected from (or the selection is not in it)."""


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def source_sha256(text: str) -> str:
    return _sha(text.encode("utf-8"))


def load_exclusions(package_dir: str | Path) -> dict[str, dict]:
    path = Path(package_dir) / EXCLUSIONS_FILE
    if not path.is_file():
        return {}
    try:
        document = json.loads(path.read_text(encoding="utf-8-sig"))
        rows = document.get("rows") if isinstance(document, dict) else None
        return {str(item["key"]): item for item in rows or [] if isinstance(item, dict) and item.get("key")}
    except (OSError, ValueError, KeyError):
        return {}


def _atomic_write(path: Path, data: bytes) -> None:
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=path.name + ".", suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def exclude_rows(csv_path: str | Path, keys: list[str], expected_sha256: str, *, reason: str = "user_removed_non_text") -> dict:
    """Remove the selected rows from the CSV (conflict-checked) and record the decision.  Returns counts and the new CSV SHA-256."""
    csv_path = Path(csv_path)
    wanted = [str(key) for key in keys if str(key)]
    if not wanted:
        raise ExclusionConflict("Chưa chọn dòng nào để xóa.")
    raw = csv_path.read_bytes()
    if _sha(raw) != str(expected_sha256).lower():
        raise ExclusionConflict("CSV đã thay đổi từ lần bạn mở; hãy tải lại CSV rồi chọn lại (không ghi đè).")
    has_bom = raw.startswith(b"\xef\xbb\xbf")
    text = raw.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text, newline=""))
    fields = list(reader.fieldnames or [])
    if "key" not in fields or "source_text" not in fields:
        raise ExclusionConflict("CSV không đúng schema (thiếu cột key/source_text); không thay đổi gì.")
    rows = list(reader)
    by_key = {row["key"]: row for row in rows}
    missing = [key for key in wanted if key not in by_key]
    if missing:
        raise ExclusionConflict(f"{len(missing)} dòng đã chọn không còn trong CSV; hãy tải lại rồi chọn lại.")
    removed = [by_key[key] for key in dict.fromkeys(wanted)]
    keep = [row for row in rows if row["key"] not in set(wanted)]
    out = io.StringIO(newline="")
    writer = csv.DictWriter(out, fieldnames=fields, lineterminator="\r\n")
    writer.writeheader()
    writer.writerows(keep)
    payload = out.getvalue().encode("utf-8")
    if has_bom:
        payload = b"\xef\xbb\xbf" + payload
    package_dir = csv_path.parent
    previous = load_exclusions(package_dir)
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    for row in removed:
        previous[row["key"]] = {"key": row["key"], "source_sha256": source_sha256(row["source_text"]), "reason": reason, "utc": now,
                                "provenance": {"file_path": row.get("file_path", ""), "import_method": row.get("import_method", ""), "context": row.get("context", "")},
                                "source_preview": row["source_text"][:80]}
    document = json.dumps({"schema": SCHEMA, "policy": "user-removed rows; honored on re-extraction while the source text (sha256) is unchanged",
                           "rows": sorted(previous.values(), key=lambda item: item["key"])}, ensure_ascii=False, indent=2).encode("utf-8")
    # Two files, one decision.  A ledger entry whose row is still in the CSV would suppress that row on the next extraction and change review
    # counts, so the pair is transactional: if the CSV write fails the ledger is put back byte-for-byte (a ledger this call created is removed;
    # an existing one is never deleted).  If even the rollback fails the error names the ledger so the state is never silently inconsistent.
    ledger_path = package_dir / EXCLUSIONS_FILE
    previous_ledger = ledger_path.read_bytes() if ledger_path.is_file() else None
    _atomic_write(ledger_path, document)
    try:
        _atomic_write(csv_path, payload)
    except BaseException as exc:
        try:
            if previous_ledger is None:
                ledger_path.unlink(missing_ok=True)
            else:
                _atomic_write(ledger_path, previous_ledger)
        except OSError as rollback:
            raise ExclusionConflict(f"Không ghi được CSV ({exc}) và cũng không hoàn tác được {EXCLUSIONS_FILE} ({rollback}); hãy kiểm tra thư mục package trước khi chạy lại.") from exc
        raise
    return {"removed": len(removed), "remaining": len(keep), "csv_sha256": _sha(payload), "exclusions": len(previous)}


def filter_excluded_entries(entries, package_dir: str | Path):
    """Drop entries the user removed earlier (same stable key AND unchanged source).  Returns (kept, dropped_keys)."""
    recorded = load_exclusions(package_dir)
    if not recorded:
        return list(entries), []
    kept, dropped = [], []
    for entry in entries:
        key = getattr(entry, "key", None) if not isinstance(entry, dict) else entry.get("key")
        text = getattr(entry, "source_text", None) if not isinstance(entry, dict) else entry.get("source_text")
        item = recorded.get(str(key))
        if item is not None and text is not None and item.get("source_sha256") == source_sha256(text):
            dropped.append(str(key))
        else:
            kept.append(entry)
    return kept, dropped


STATIC_CANDIDATE_METHODS = ("renpy_screen_candidate", "renpy_compiled_candidate")


def exclude_machine_technical(csv_path: str | Path) -> int:
    """Legacy packages (written before display-purpose classification) list static screen candidates such as "<", "[page]" or "{#auto_page}A" as
    review rows.  They are machine syntax, never player text: record them as machine exclusions and drop them from the CSV so the user never triages
    syntax.  Only rows whose method is a static-display candidate AND whose visible content has no player-readable words are touched; every other row
    (including human candidates like "Mute All") is left exactly as it is.  Returns the number of rows excluded."""
    from vntext.renpy_static import classify_ui_text

    csv_path = Path(csv_path)
    raw = csv_path.read_bytes()
    reader = csv.DictReader(io.StringIO(raw.decode("utf-8-sig"), newline=""))
    if "key" not in (reader.fieldnames or []) or "import_method" not in (reader.fieldnames or []):
        return 0
    keys = [row["key"] for row in reader
            if row.get("import_method") in STATIC_CANDIDATE_METHODS and not (row.get("translation") or "").strip()
            and classify_ui_text(row.get("source_text") or "")[0] == "TECHNICAL"]
    if not keys:
        return 0
    return exclude_rows(csv_path, keys, _sha(raw), reason="machine_technical")["removed"]
