"""Package-local cache for validated translation candidates.

Cache entries are never used as proof by themselves: callers run the current
structural/quality gate again before writing CSV.  A changed fingerprint is a
selective miss, so patch/UI/installer changes do not invalidate translation
work accidentally.
"""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


CACHE_SCHEMA_VERSION = 1
CACHE_DIR_NAME = "v2"
CACHE_DB_NAME = "translation_cache.sqlite3"
CACHE_LOCK_NAME = "translation_cache.lock"
VALIDATED = "PASS"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _hash(value: Any) -> str:
    return hashlib.sha256(_json(value).encode("utf-8", "surrogatepass")).hexdigest()


def _source_hash(source: str) -> str:
    return hashlib.sha256(str(source or "").encode("utf-8", "surrogatepass")).hexdigest()


def _context_hash(row: Mapping[str, Any]) -> str:
    """Hash ordered context, preserving an extractor-provided window exactly."""

    context = row.get("context_window")
    if context is None:
        context = row.get("context") or ""
    return _hash(
        {
            "ordered_context": context,
            "scene": row.get("scene") or row.get("scene_id") or "",
            "speaker": row.get("speaker") or "",
            "truncation_policy": row.get("context_truncation_policy") or "none",
        }
    )


def _glossary_hash(glossary: Mapping[str, Any] | None, explicit: str = "") -> str:
    return str(explicit or _hash(dict(glossary or {})))


def compute_cache_fingerprint(
    row: Mapping[str, Any],
    *,
    model_metadata: Mapping[str, Any],
    glossary: Mapping[str, Any] | None = None,
    glossary_hash: str = "",
    memory_scope: str = "",
    classifier_policy_version: str = "",
    classifier_policy_hash: str = "",
    strategy_version: str = "local-translation-v2-strategy-1",
    protected_span_schema_version: str = "1",
    context_builder_version: str = "none",
    decoding: Mapping[str, Any] | None = None,
    engine_profile: str = "",
) -> dict[str, Any]:
    source = str(row.get("source_text") or "")
    fingerprint = {
        "cache_schema_version": CACHE_SCHEMA_VERSION,
        "stable_key": str(row.get("key") or ""),
        "source_hash": _source_hash(source),
        "context_hash": _context_hash(row),
        "glossary_hash": _glossary_hash(glossary, glossary_hash),
        "classifier_policy_version": str(classifier_policy_version or ""),
        "classifier_policy_hash": str(classifier_policy_hash or ""),
        "model_id": str(model_metadata.get("model_id") or ""),
        "model_revision": str(model_metadata.get("model_revision") or ""),
        "adapter_id": str(model_metadata.get("adapter_id") or ""),
        "strategy_version": str(strategy_version or ""),
        "engine_profile": str(engine_profile or row.get("import_method") or ""),
        "protected_span_schema_version": str(protected_span_schema_version or ""),
        "context_builder_version": str(context_builder_version or ""),
        "decoding": dict(decoding or {}),
        "memory_scope": str(memory_scope or ""),
    }
    return {"fingerprint": fingerprint, "cache_key": _hash(fingerprint)}


class TranslationCacheError(RuntimeError):
    pass


class TranslationCache:
    """One-worker SQLite cache with explicit PASS-only writes."""

    def __init__(self, package_dir: str | Path, *, busy_timeout_ms: int = 5000) -> None:
        self.package_dir = Path(package_dir)
        self.meta_dir = self.package_dir / ".mt" / CACHE_DIR_NAME
        self.db_path = self.meta_dir / CACHE_DB_NAME
        self.lock_path = self.meta_dir / CACHE_LOCK_NAME
        self._owner_id = uuid.uuid4().hex
        self._lock = False
        self._connection: sqlite3.Connection | None = None
        self._stats = {"lookups": 0, "hits": 0, "misses": 0, "writes": 0, "invalid_writes": 0}
        self.meta_dir.mkdir(parents=True, exist_ok=True)
        self._acquire_lock()
        try:
            self._connection = sqlite3.connect(self.db_path, timeout=busy_timeout_ms / 1000, isolation_level=None)
            self._connection.execute("PRAGMA journal_mode = WAL")
            self._connection.execute(f"PRAGMA busy_timeout = {int(busy_timeout_ms)}")
            self._connection.execute("PRAGMA synchronous = FULL")
            self._migrate()
        except Exception:
            self.close()
            raise

    @property
    def connection(self) -> sqlite3.Connection:
        if self._connection is None:
            raise TranslationCacheError("translation cache is closed")
        return self._connection

    def _acquire_lock(self) -> None:
        payload = _json({"owner_id": self._owner_id, "pid": os.getpid(), "created_at": _utc_now()})
        try:
            fd = os.open(self.lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError as exc:
            try:
                current = json.loads(self.lock_path.read_text(encoding="utf-8"))
                pid = int(current.get("pid", 0))
            except (OSError, ValueError, TypeError, json.JSONDecodeError) as read_exc:
                raise TranslationCacheError(f"cannot validate cache lock: {self.lock_path}") from read_exc
            if pid and _pid_alive(pid):
                raise TranslationCacheError(f"translation cache is locked by live pid {pid}") from exc
            try:
                self.lock_path.unlink()
            except OSError as unlink_exc:
                raise TranslationCacheError(f"cannot reclaim cache lock: {self.lock_path}") from unlink_exc
            return self._acquire_lock()
        except OSError as exc:
            raise TranslationCacheError(f"cannot create cache lock: {self.lock_path}") from exc
        try:
            os.write(fd, payload.encode("utf-8"))
        finally:
            os.close(fd)
        self._lock = True

    def _migrate(self) -> None:
        version = int(self.connection.execute("PRAGMA user_version").fetchone()[0])
        if version > CACHE_SCHEMA_VERSION:
            raise TranslationCacheError(f"cache schema {version} is newer than supported {CACHE_SCHEMA_VERSION}")
        if version < 1:
            self.connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS cache_entries (
                    cache_key TEXT PRIMARY KEY,
                    source_hash TEXT NOT NULL,
                    translation TEXT NOT NULL,
                    validation_status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    provenance_json TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_cache_source_hash ON cache_entries(source_hash);
                PRAGMA user_version = 1;
                """
            )

    def lookup(self, cache_key: str) -> str | None:
        self._stats["lookups"] += 1
        row = self.connection.execute(
            "SELECT translation FROM cache_entries WHERE cache_key = ? AND validation_status = ?",
            (str(cache_key), VALIDATED),
        ).fetchone()
        if row is None:
            self._stats["misses"] += 1
            return None
        self._stats["hits"] += 1
        return str(row[0])

    def put(
        self,
        cache_key: str,
        row: Mapping[str, Any],
        translation: str,
        *,
        validation_status: str,
        provenance: Mapping[str, Any] | None = None,
    ) -> bool:
        if str(validation_status).upper() != VALIDATED or not str(translation or "").strip():
            self._stats["invalid_writes"] += 1
            return False
        self.connection.execute(
            """
            INSERT INTO cache_entries(cache_key, source_hash, translation, validation_status, created_at, provenance_json)
            VALUES(?, ?, ?, ?, ?, ?)
            ON CONFLICT(cache_key) DO UPDATE SET
                translation = excluded.translation,
                validation_status = excluded.validation_status,
                created_at = excluded.created_at,
                provenance_json = excluded.provenance_json
            """,
            (
                str(cache_key),
                _source_hash(str(row.get("source_text") or "")),
                str(translation),
                VALIDATED,
                _utc_now(),
                _json(dict(provenance or {})),
            ),
        )
        self._stats["writes"] += 1
        return True

    def summary(self) -> dict[str, Any]:
        return {
            "kind": "validated_translation_cache",
            "status": "enabled",
            "schema_version": CACHE_SCHEMA_VERSION,
            "path": str(self.db_path),
            **self._stats,
            "entries": int(self.connection.execute("SELECT COUNT(*) FROM cache_entries").fetchone()[0]),
        }

    def close(self) -> None:
        connection, self._connection = self._connection, None
        if connection is not None:
            connection.close()
        if self._lock:
            try:
                self.lock_path.unlink()
            except FileNotFoundError:
                pass
            finally:
                self._lock = False


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if os.name == "nt":
        # Signal 0 is CTRL_C_EVENT on Windows, not a read-only PID probe.
        # Query the process without signalling it or reclaiming an uncertain lock.
        import ctypes
        from ctypes import wintypes

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel32.OpenProcess.restype = wintypes.HANDLE
        kernel32.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
        kernel32.GetExitCodeProcess.restype = wintypes.BOOL
        kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel32.CloseHandle.restype = wintypes.BOOL
        handle = kernel32.OpenProcess(0x1000, False, pid)
        if not handle:
            # Only ERROR_INVALID_PARAMETER proves this PID does not exist.
            return ctypes.get_last_error() != 87
        try:
            exit_code = wintypes.DWORD()
            if not kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
                return True
            return exit_code.value == 259  # STILL_ACTIVE
        finally:
            kernel32.CloseHandle(handle)
    try:
        os.kill(pid, 0)
    except (OSError, ProcessLookupError):
        return False
    return True


__all__ = [
    "CACHE_SCHEMA_VERSION",
    "TranslationCache",
    "TranslationCacheError",
    "compute_cache_fingerprint",
]
