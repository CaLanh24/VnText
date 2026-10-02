"""Durable, package-local traceability primitives for Local Translation V2.

Phase 1 deliberately keeps this module independent from extraction,
translation, patching, and the worker protocol.  Later phases can instrument
those pipelines through :class:`TraceSink` without opening SQLite directly.
"""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import tempfile
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator, Mapping, Protocol


TRACE_SCHEMA_VERSION = 2
DEFAULT_BUSY_TIMEOUT_MS = 5000
TRACE_DB_NAME = "traceability.sqlite3"
TRACE_LOCK_NAME = "traceability.lock"
TRACE_SUMMARY_NAME = "trace_summary.json"
TRACE_EXPORT_NAME = "trace_export.jsonl"
TRACE_DIAGNOSTIC_NAME = "diagnostic_summary.json"

CLASSIFICATION_MAIN = "MAIN"
CLASSIFICATION_TRANSLATE = CLASSIFICATION_MAIN
CLASSIFICATION_REVIEW = "REVIEW"
CLASSIFICATION_SKIP = "SKIP"
CLASSIFICATION_DO_NOT_TRANSLATE = CLASSIFICATION_SKIP
CLASSIFICATION_UNSUPPORTED = "UNSUPPORTED"
CLASSIFICATIONS = frozenset(
    {
        CLASSIFICATION_MAIN,
        CLASSIFICATION_REVIEW,
        CLASSIFICATION_SKIP,
        CLASSIFICATION_UNSUPPORTED,
    }
)

STAGE_DISCOVERED = "DISCOVERED"
STAGE_EXTRACTED = "EXTRACTED"
STAGE_CLASSIFIED = "CLASSIFIED"
STAGE_TRANSLATED = "TRANSLATED"
STAGE_VALIDATED = "VALIDATED"
STAGE_PATCHED = "PATCHED"
STAGE_READ_BACK_VERIFIED = "READ_BACK_VERIFIED"
STAGE_RUNTIME_VERIFIED = "RUNTIME_VERIFIED"
STAGE_NOT_TESTABLE = "NOT_TESTABLE"
STAGES = frozenset(
    {
        STAGE_DISCOVERED,
        STAGE_EXTRACTED,
        STAGE_CLASSIFIED,
        STAGE_TRANSLATED,
        STAGE_VALIDATED,
        STAGE_PATCHED,
        STAGE_READ_BACK_VERIFIED,
        STAGE_RUNTIME_VERIFIED,
        STAGE_NOT_TESTABLE,
    }
)

ROOT_CAUSE_EXTRACT_MISSED = "EXTRACT_MISSED"
ROOT_CAUSE_DISCOVERY_GAP = "DISCOVERY_GAP"
ROOT_CAUSE_MISCLASSIFIED = "MISCLASSIFIED"
ROOT_CAUSE_TRANSLATION_MISSED = "TRANSLATION_MISSED"
ROOT_CAUSE_TRANSLATION_INVALID = "TRANSLATION_INVALID"
ROOT_CAUSE_PATCH_FAILED = "PATCH_FAILED"
ROOT_CAUSE_PATCH_VERIFY_FAILED = "PATCH_VERIFY_FAILED"
ROOT_CAUSE_RUNTIME_SOURCE_MISMATCH = "RUNTIME_SOURCE_MISMATCH"
ROOT_CAUSE_FONT_RENDER = "FONT_RENDER"
ROOT_CAUSE_UNKNOWN = "UNKNOWN"
ROOT_CAUSES = frozenset(
    {
        ROOT_CAUSE_EXTRACT_MISSED,
        ROOT_CAUSE_DISCOVERY_GAP,
        ROOT_CAUSE_MISCLASSIFIED,
        ROOT_CAUSE_TRANSLATION_MISSED,
        ROOT_CAUSE_TRANSLATION_INVALID,
        ROOT_CAUSE_PATCH_FAILED,
        ROOT_CAUSE_PATCH_VERIFY_FAILED,
        ROOT_CAUSE_RUNTIME_SOURCE_MISMATCH,
        ROOT_CAUSE_FONT_RENDER,
        ROOT_CAUSE_UNKNOWN,
    }
)

EVENT_STARTED = "STARTED"
EVENT_COMPLETED = "COMPLETED"
EVENT_FAILED = "FAILED"
EVENT_ABORTED = "ABORTED"
EVENT_UNKNOWN = "UNKNOWN"


class TraceStoreError(RuntimeError):
    """Raised when traceability cannot be made safe and deterministic."""


class TraceSink(Protocol):
    """Small instrumentation surface used by later pipeline phases."""

    def register_entry(self, entry: Any, **metadata: Any) -> dict[str, Any]: ...

    def start_event(self, stage: str, **kwargs: Any) -> str: ...

    def finish_event(self, action_id: str, status: str = EVENT_COMPLETED, **kwargs: Any) -> int: ...

    def record_event(self, stage: str, status: str = EVENT_COMPLETED, **kwargs: Any) -> int: ...

    def update_entry(self, trace_id: str, **fields: Any) -> None: ...

    def update_target(self, target_id: str, **fields: Any) -> None: ...


class NullTraceSink:
    """No-op sink for callers that explicitly opt out of persistence."""

    def register_entry(self, entry: Any, **metadata: Any) -> dict[str, Any]:
        return {}

    def start_event(self, stage: str, **kwargs: Any) -> str:
        return ""

    def finish_event(self, action_id: str, status: str = EVENT_COMPLETED, **kwargs: Any) -> int:
        return 0

    def record_event(self, stage: str, status: str = EVENT_COMPLETED, **kwargs: Any) -> int:
        return 0

    def update_entry(self, trace_id: str, **fields: Any) -> None:
        return None

    def update_target(self, target_id: str, **fields: Any) -> None:
        return None


def _canonical_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _canonical_value(value[key]) for key in sorted(value, key=lambda item: str(item))}
    if isinstance(value, (list, tuple)):
        return [_canonical_value(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _canonical_json(value: Any) -> str:
    return json.dumps(
        _canonical_value(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def canonical_identity_text(value: Any) -> str:
    """Canonicalize line endings for stable identity digest input only."""

    text = value if isinstance(value, str) else str(value)
    return text.replace("\r\n", "\n").replace("\r", "\n")


def canonical_locator(locator: Any) -> str:
    """Return the stable JSON representation used by identity and targets."""

    return _canonical_json({} if locator is None else locator)


def _manifest_identity_records(manifest: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Return extraction identity independent of the current ledger bucket.

    Translation status maintenance may move a row from ``entries`` to
    ``technical_skipped``.  That is a classification/ledger transition, not a
    new extraction package, so the durable package identity must not change
    merely because the row moved containers.
    """

    records: list[dict[str, Any]] = []
    for key in ("entries", "technical_skipped"):
        for item in manifest.get(key, []) or []:
            if not isinstance(item, Mapping):
                raise TraceStoreError(f"manifest {key} contains a non-object item")
            records.append(
                {
                    "key": canonical_identity_text(item.get("key", "")),
                    "source_text": canonical_identity_text(item.get("source_text", "")),
                    "file_path": canonical_identity_text(item.get("file_path", "")),
                    "import_method": canonical_identity_text(item.get("import_method", "")),
                    "locator": canonical_locator(item.get("locator", {})),
                }
            )
    return sorted(records, key=_canonical_json)


def compute_package_id(manifest: Mapping[str, Any]) -> str:
    """Hash only canonical extraction identity, never timestamps or statistics."""

    if not isinstance(manifest, Mapping):
        raise TypeError("manifest must be a mapping")
    payload = {"entries": _manifest_identity_records(manifest)}
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


def compute_trace_id(package_id: str, entry_key: str) -> str:
    if not package_id or not entry_key:
        raise ValueError("package_id and entry_key are required")
    raw = f"{package_id}\n{entry_key}".encode("utf-8", "surrogatepass")
    return hashlib.sha256(raw).hexdigest()


def compute_target_id(trace_id: str, locator: Any, duplicate_ordinal: int) -> str:
    if not trace_id:
        raise ValueError("trace_id is required")
    if duplicate_ordinal < 0:
        raise ValueError("duplicate_ordinal must be non-negative")
    raw = f"{trace_id}\n{canonical_locator(locator)}\n{duplicate_ordinal}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def _json_text(value: Any) -> str:
    try:
        return _canonical_json(value if value is not None else {})
    except (TypeError, ValueError) as exc:
        raise TraceStoreError(f"trace payload is not JSON serializable: {exc}") from exc


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if os.name == "nt":
        # os.kill(pid, 0) is not a reliable liveness probe for a Windows
        # process launched without a console (the Release regression runner
        # uses hidden children).  It can report a live owner as absent and
        # make the stale-lock reclaim path unlink an active store lock.
        try:
            import ctypes
            from ctypes import wintypes

            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
            kernel32.OpenProcess.restype = wintypes.HANDLE
            kernel32.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
            kernel32.GetExitCodeProcess.restype = wintypes.BOOL
            kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
            kernel32.CloseHandle.restype = wintypes.BOOL

            process_query_limited_information = 0x1000
            synchronize = 0x00100000
            handle = kernel32.OpenProcess(
                process_query_limited_information | synchronize,
                False,
                pid,
            )
            if not handle:
                # Access denied is inconclusive; fail closed and keep the
                # lock rather than risking concurrent writers.
                return ctypes.get_last_error() == 5
            try:
                exit_code = wintypes.DWORD()
                if not kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
                    return True
                return exit_code.value == 259  # STILL_ACTIVE
            finally:
                kernel32.CloseHandle(handle)
        except (AttributeError, OSError, ValueError):
            # Fall back below for unusual Python/Windows runtimes.
            pass
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def _entry_value(entry: Any, name: str, default: Any = None) -> Any:
    if isinstance(entry, Mapping):
        return entry.get(name, default)
    return getattr(entry, name, default)


def _normalise_root_cause(root_cause: str | None) -> str | None:
    if root_cause is None or root_cause == "":
        return None
    normalised = str(root_cause).upper()
    if normalised not in ROOT_CAUSES:
        raise TraceStoreError(f"unknown root cause: {normalised}")
    return normalised


def _duplicate_locator(item: Any) -> Any:
    if isinstance(item, Mapping) and "locator" in item:
        return item["locator"]
    return item


class TraceStore:
    """One-writer SQLite trace store scoped to one extraction package.

    The lock is acquired before opening the database.  Every normal write is
    committed immediately; ``batch()`` is available only for short groups of
    trace writes and must not surround model calls or Unity file writes.
    """

    def __init__(
        self,
        package_dir: str | Path,
        package_id: str,
        *,
        busy_timeout_ms: int = DEFAULT_BUSY_TIMEOUT_MS,
    ) -> None:
        if not package_id:
            raise ValueError("package_id is required")
        if busy_timeout_ms <= 0:
            raise ValueError("busy_timeout_ms must be positive")
        self.package_dir = Path(package_dir)
        self.meta_dir = self.package_dir / ".mt"
        self.db_path = self.meta_dir / TRACE_DB_NAME
        self.lock_path = self.meta_dir / TRACE_LOCK_NAME
        self.package_id = package_id
        self.busy_timeout_ms = busy_timeout_ms
        self.run_id: str | None = None
        self._owner_id = uuid.uuid4().hex
        self._connection: sqlite3.Connection | None = None
        self._batch_depth = 0
        self._lock_acquired = False

        self.meta_dir.mkdir(parents=True, exist_ok=True)
        self._acquire_lock()
        try:
            self._connection = sqlite3.connect(
                self.db_path,
                timeout=busy_timeout_ms / 1000,
                isolation_level=None,
            )
            self._configure_connection()
            self._migrate()
            self._bind_package()
            self._recover_inflight_runs()
        except Exception:
            self.close()
            raise

    @classmethod
    def for_package(cls, package_dir: str | Path, manifest: Mapping[str, Any], **kwargs: Any) -> "TraceStore":
        return cls(package_dir, compute_package_id(manifest), **kwargs)

    @property
    def connection(self) -> sqlite3.Connection:
        if self._connection is None:
            raise TraceStoreError("trace store is closed")
        return self._connection

    def _acquire_lock(self) -> None:
        owner = {
            "owner_id": self._owner_id,
            "pid": os.getpid(),
            "run_id": self.run_id,
            "created_at": _utc_now(),
        }
        encoded = json.dumps(owner, ensure_ascii=False, sort_keys=True).encode("utf-8")
        for attempt in range(2):
            try:
                fd = os.open(self.lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            except FileExistsError as exc:
                if attempt:
                    raise TraceStoreError(f"trace store is locked: {self.lock_path}") from exc
                try:
                    current = json.loads(self.lock_path.read_text(encoding="utf-8"))
                    pid = int(current.get("pid", 0))
                except (OSError, ValueError, TypeError, json.JSONDecodeError) as read_exc:
                    raise TraceStoreError(f"cannot validate trace lock: {self.lock_path}") from read_exc
                if _pid_alive(pid):
                    raise TraceStoreError(f"trace store is locked by live pid {pid}: {self.lock_path}") from exc
                try:
                    self.lock_path.unlink()
                except FileNotFoundError:
                    pass
                except OSError as unlink_exc:
                    raise TraceStoreError(f"cannot reclaim stale trace lock: {self.lock_path}") from unlink_exc
                continue
            except OSError as exc:
                raise TraceStoreError(f"cannot create trace lock: {self.lock_path}") from exc
            try:
                os.write(fd, encoded)
            finally:
                os.close(fd)
            self._lock_acquired = True
            return
        raise TraceStoreError(f"cannot acquire trace lock: {self.lock_path}")

    def _configure_connection(self) -> None:
        connection = self.connection
        connection.execute("PRAGMA foreign_keys = ON")
        journal = str(connection.execute("PRAGMA journal_mode = WAL").fetchone()[0]).lower()
        if journal != "wal":
            raise TraceStoreError(f"trace store requires WAL journal mode, got {journal!r}")
        connection.execute(f"PRAGMA busy_timeout = {self.busy_timeout_ms}")
        connection.execute("PRAGMA synchronous = FULL")

    def _migrate(self) -> None:
        connection = self.connection
        version = int(connection.execute("PRAGMA user_version").fetchone()[0])
        if version > TRACE_SCHEMA_VERSION:
            raise TraceStoreError(
                f"trace schema {version} is newer than supported {TRACE_SCHEMA_VERSION}"
            )
        if version < 1:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS trace_meta (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS trace_runs (
                    run_id TEXT PRIMARY KEY,
                    package_id TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    finished_at TEXT,
                    status TEXT NOT NULL,
                    root_cause TEXT,
                    metadata_json TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS trace_entries (
                    trace_id TEXT PRIMARY KEY,
                    package_id TEXT NOT NULL,
                    entry_key TEXT NOT NULL,
                    source_text TEXT NOT NULL,
                    source_file TEXT NOT NULL,
                    context TEXT NOT NULL,
                    container TEXT NOT NULL,
                    object_info TEXT NOT NULL,
                    path_id TEXT,
                    field_locator TEXT NOT NULL,
                    locator_json TEXT NOT NULL,
                    import_method TEXT NOT NULL,
                    backend TEXT NOT NULL,
                    classification TEXT NOT NULL,
                    classification_reason TEXT,
                    stage TEXT NOT NULL,
                    status TEXT NOT NULL,
                    model_engine TEXT,
                    model_revision TEXT,
                    glossary_fingerprint TEXT,
                    context_fingerprint TEXT,
                    cache_fingerprint TEXT,
                    memory_fingerprint TEXT,
                    translation TEXT,
                    translation_hash TEXT,
                    validation_result TEXT,
                    patch_status TEXT,
                    write_status TEXT,
                    readback_status TEXT,
                    final_verification TEXT,
                    runtime_status TEXT,
                    root_cause TEXT,
                    metadata_json TEXT NOT NULL,
                    UNIQUE(package_id, entry_key)
                );
                CREATE TABLE IF NOT EXISTS trace_targets (
                    target_id TEXT PRIMARY KEY,
                    trace_id TEXT NOT NULL REFERENCES trace_entries(trace_id),
                    duplicate_ordinal INTEGER NOT NULL,
                    locator_json TEXT NOT NULL,
                    patch_target TEXT,
                    status TEXT NOT NULL,
                    root_cause TEXT,
                    write_status TEXT,
                    readback_status TEXT,
                    final_verification TEXT,
                    UNIQUE(trace_id, duplicate_ordinal)
                );
                CREATE TABLE IF NOT EXISTS trace_events (
                    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    action_id TEXT NOT NULL,
                    run_id TEXT NOT NULL REFERENCES trace_runs(run_id),
                    trace_id TEXT REFERENCES trace_entries(trace_id),
                    target_id TEXT REFERENCES trace_targets(target_id),
                    attempt_id TEXT,
                    stage TEXT NOT NULL,
                    event_status TEXT NOT NULL,
                    root_cause TEXT,
                    created_at TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_trace_events_action ON trace_events(action_id, event_status);
                CREATE INDEX IF NOT EXISTS idx_trace_events_run ON trace_events(run_id, event_status);
                CREATE INDEX IF NOT EXISTS idx_trace_entries_classification ON trace_entries(classification);
                CREATE INDEX IF NOT EXISTS idx_trace_entries_root_cause ON trace_entries(root_cause);
                PRAGMA user_version = 1;
                """
            )
        if version < 2:
            columns = {
                row[1]
                for row in connection.execute("PRAGMA table_info(trace_entries)").fetchall()
            }
            if "memory_fingerprint" not in columns:
                connection.execute(
                    "ALTER TABLE trace_entries ADD COLUMN memory_fingerprint TEXT"
                )
            connection.execute("PRAGMA user_version = 2")

    def _bind_package(self) -> None:
        row = self.connection.execute(
            "SELECT value FROM trace_meta WHERE key = 'package_id'"
        ).fetchone()
        if row and row[0] != self.package_id:
            raise TraceStoreError(
                f"package identity mismatch: store={row[0]!r}, requested={self.package_id!r}"
            )
        if not row:
            self.connection.execute(
                "INSERT INTO trace_meta(key, value) VALUES('package_id', ?)",
                (self.package_id,),
            )

    def _recover_inflight_runs(self) -> None:
        connection = self.connection
        running = connection.execute(
            "SELECT run_id FROM trace_runs WHERE status = 'RUNNING' ORDER BY started_at"
        ).fetchall()
        for (run_id,) in running:
            starts = connection.execute(
                """
                SELECT event_id, action_id, trace_id, target_id, attempt_id, stage
                FROM trace_events AS started
                WHERE started.run_id = ? AND started.event_status = 'STARTED'
                  AND NOT EXISTS (
                      SELECT 1 FROM trace_events AS terminal
                      WHERE terminal.action_id = started.action_id
                        AND terminal.event_status <> 'STARTED'
                  )
                ORDER BY started.event_id
                """,
                (run_id,),
            ).fetchall()
            for _, action_id, trace_id, target_id, attempt_id, stage in starts:
                connection.execute(
                    """
                    INSERT INTO trace_events(
                        action_id, run_id, trace_id, target_id, attempt_id, stage,
                        event_status, root_cause, created_at, payload_json
                    ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        action_id,
                        run_id,
                        trace_id,
                        target_id,
                        attempt_id,
                        stage,
                        EVENT_ABORTED,
                        ROOT_CAUSE_UNKNOWN,
                        _utc_now(),
                        _json_text({"recovered": True, "reason": "in-flight event on reopen"}),
                    ),
                )
                if target_id:
                    connection.execute(
                        "UPDATE trace_targets SET status = ?, root_cause = ? WHERE target_id = ?",
                        (EVENT_ABORTED, ROOT_CAUSE_UNKNOWN, target_id),
                    )
                if trace_id:
                    connection.execute(
                        "UPDATE trace_entries SET status = ?, root_cause = ? WHERE trace_id = ?",
                        (EVENT_ABORTED, ROOT_CAUSE_UNKNOWN, trace_id),
                    )
            connection.execute(
                "UPDATE trace_runs SET status = ?, root_cause = ?, finished_at = ? WHERE run_id = ?",
                (EVENT_ABORTED, ROOT_CAUSE_UNKNOWN, _utc_now(), run_id),
            )

    def _commit_if_needed(self) -> None:
        if self._batch_depth == 0:
            self.connection.commit()

    @contextmanager
    def batch(self) -> Iterator["TraceStore"]:
        """Commit a short trace-only group; never hold it across external work."""

        self._ensure_open()
        outermost = self._batch_depth == 0
        if outermost:
            self.connection.execute("BEGIN IMMEDIATE")
        self._batch_depth += 1
        try:
            yield self
        except Exception:
            self._batch_depth -= 1
            if outermost:
                self.connection.rollback()
            raise
        else:
            self._batch_depth -= 1
            if outermost:
                self.connection.commit()

    def _ensure_open(self) -> None:
        if self._connection is None:
            raise TraceStoreError("trace store is closed")

    def start_run(self, run_id: str | None = None, metadata: Mapping[str, Any] | None = None) -> str:
        self._ensure_open()
        if self.run_id is not None:
            raise TraceStoreError(f"run already active: {self.run_id}")
        self.run_id = run_id or str(uuid.uuid4())
        self.connection.execute(
            """
            INSERT INTO trace_runs(run_id, package_id, started_at, status, metadata_json)
            VALUES(?, ?, ?, 'RUNNING', ?)
            """,
            (self.run_id, self.package_id, _utc_now(), _json_text(metadata)),
        )
        self._commit_if_needed()
        self._write_lock_owner()
        return self.run_id

    begin_run = start_run

    def finish_run(self, status: str = EVENT_COMPLETED, root_cause: str | None = None) -> None:
        self._ensure_open()
        if self.run_id is None:
            raise TraceStoreError("no active run")
        run_row = self.connection.execute(
            "SELECT status FROM trace_runs WHERE run_id = ?", (self.run_id,)
        ).fetchone()
        if not run_row:
            raise TraceStoreError(f"unknown run_id: {self.run_id}")
        if run_row[0] != "RUNNING":
            raise TraceStoreError(f"run is not RUNNING: {self.run_id} ({run_row[0]})")
        status = str(status).upper()
        root_cause = _normalise_root_cause(root_cause)
        if status in {EVENT_COMPLETED, "PASS"}:
            in_flight = self.connection.execute(
                """
                SELECT COUNT(*)
                FROM trace_events AS started
                WHERE started.run_id = ?
                  AND started.event_status = 'STARTED'
                  AND NOT EXISTS (
                      SELECT 1 FROM trace_events AS terminal
                      WHERE terminal.action_id = started.action_id
                        AND terminal.event_status <> 'STARTED'
                  )
                """,
                (self.run_id,),
            ).fetchone()[0]
            if int(in_flight or 0):
                raise TraceStoreError(
                    f"cannot complete run with {int(in_flight)} in-flight trace action(s)"
                )
        self.connection.execute(
            "UPDATE trace_runs SET status = ?, root_cause = ?, finished_at = ? WHERE run_id = ?",
            (status, root_cause, _utc_now(), self.run_id),
        )
        self._commit_if_needed()

    def _write_lock_owner(self) -> None:
        if not self._lock_acquired:
            return
        owner = {
            "owner_id": self._owner_id,
            "pid": os.getpid(),
            "run_id": self.run_id,
            "created_at": _utc_now(),
        }
        fd, temp_name = tempfile.mkstemp(prefix=f"{self.lock_path.name}.", dir=self.meta_dir)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(owner, handle, ensure_ascii=False, sort_keys=True)
            os.replace(temp_name, self.lock_path)
        finally:
            if os.path.exists(temp_name):
                os.unlink(temp_name)

    def register_entry(
        self,
        entry: Any,
        *,
        classification: str | None = None,
        classification_reason: str | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Persist an entry and every locator independently without mutating it."""

        self._ensure_open()
        entry_key = str(_entry_value(entry, "key", "") or "")
        if not entry_key:
            raise TraceStoreError("trace entry requires the existing Entry.key")
        locator = _entry_value(entry, "locator", {})
        if locator is None:
            locator = {}
        trace_id = compute_trace_id(self.package_id, entry_key)
        review_only = bool(_entry_value(entry, "review_only", False))
        classification = str(classification or (CLASSIFICATION_REVIEW if review_only else CLASSIFICATION_MAIN)).upper()
        if classification not in CLASSIFICATIONS:
            raise TraceStoreError(f"unknown classification: {classification}")
        classification_reason = str(classification_reason) if classification_reason is not None else None
        if classification in {
            CLASSIFICATION_REVIEW,
            CLASSIFICATION_SKIP,
            CLASSIFICATION_UNSUPPORTED,
        } and not classification_reason:
            raise TraceStoreError(
                f"classification {classification} requires an explicit reason"
            )
        object_info = str(_entry_value(entry, "object_info", "") or "")
        source_file = str(_entry_value(entry, "file_path", "") or "")
        context = str(_entry_value(entry, "context", "") or "")
        source_text = str(_entry_value(entry, "source_text", "") or "")
        import_method = str(_entry_value(entry, "import_method", "") or "")
        backend = str(_entry_value(entry, "backend", "") or "")
        locator_json = canonical_locator(locator)
        path_id = None
        if isinstance(locator, Mapping) and locator.get("path_id") is not None:
            path_id = str(locator["path_id"])
        field_locator = ""
        if isinstance(locator, Mapping):
            for field_name in ("field_path", "json_pointer", "xml_path", "line_index", "line"):
                if field_name in locator:
                    field_locator = _canonical_json(locator[field_name])
                    break
        previous_metadata: dict[str, Any] = {}
        previous = self.connection.execute(
            "SELECT metadata_json FROM trace_entries WHERE trace_id = ?",
            (trace_id,),
        ).fetchone()
        if previous and previous[0]:
            try:
                decoded = json.loads(previous[0])
            except (TypeError, ValueError, json.JSONDecodeError):
                decoded = {}
            if isinstance(decoded, Mapping):
                previous_metadata = dict(decoded)
        if metadata:
            previous_metadata.update(_canonical_value(dict(metadata)))
        metadata_json = _json_text(previous_metadata)
        self.connection.execute(
            """
            INSERT INTO trace_entries(
                trace_id, package_id, entry_key, source_text, source_file, context,
                container, object_info, path_id, field_locator, locator_json,
                import_method, backend, classification, classification_reason,
                stage, status, metadata_json
            ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(trace_id) DO UPDATE SET
                source_text = excluded.source_text,
                source_file = excluded.source_file,
                context = excluded.context,
                container = excluded.container,
                object_info = excluded.object_info,
                path_id = excluded.path_id,
                field_locator = excluded.field_locator,
                locator_json = excluded.locator_json,
                import_method = excluded.import_method,
                backend = excluded.backend,
                classification = excluded.classification,
                classification_reason = excluded.classification_reason,
                metadata_json = excluded.metadata_json
            """,
            (
                trace_id,
                self.package_id,
                entry_key,
                source_text,
                source_file,
                context,
                source_file,
                object_info,
                path_id,
                field_locator,
                locator_json,
                import_method,
                backend,
                classification,
                classification_reason,
                STAGE_DISCOVERED,
                EVENT_STARTED,
                metadata_json,
            ),
        )
        locations = [locator]
        duplicate_locations = _entry_value(entry, "duplicate_locations", [])
        locations.extend(_duplicate_locator(item) for item in (duplicate_locations or []))
        target_ids: list[str] = []
        for ordinal, target_locator in enumerate(locations):
            target_id = compute_target_id(trace_id, target_locator, ordinal)
            target_ids.append(target_id)
            self.connection.execute(
                """
                INSERT INTO trace_targets(
                    target_id, trace_id, duplicate_ordinal, locator_json,
                    patch_target, status
                ) VALUES(?, ?, ?, ?, ?, 'DISCOVERED')
                ON CONFLICT(target_id) DO UPDATE SET
                    locator_json = excluded.locator_json,
                    patch_target = excluded.patch_target
                """,
                (target_id, trace_id, ordinal, canonical_locator(target_locator), canonical_locator(target_locator)),
            )
        self._commit_if_needed()
        return {"entry_key": entry_key, "trace_id": trace_id, "target_ids": target_ids}

    def register_entries(self, entries: list[Any], **kwargs: Any) -> list[dict[str, Any]]:
        with self.batch():
            return [self.register_entry(entry, **kwargs) for entry in entries]

    def update_entry(self, trace_id: str, **fields: Any) -> None:
        """Update durable entry results without exposing the SQLite connection."""

        self._ensure_open()
        allowed = {
            "classification",
            "classification_reason",
            "stage",
            "status",
            "model_engine",
            "model_revision",
            "glossary_fingerprint",
            "context_fingerprint",
            "cache_fingerprint",
            "memory_fingerprint",
            "translation",
            "translation_hash",
            "validation_result",
            "patch_status",
            "write_status",
            "readback_status",
            "final_verification",
            "runtime_status",
            "root_cause",
        }
        unknown = set(fields) - allowed
        if unknown:
            raise TraceStoreError(f"unsupported trace entry fields: {sorted(unknown)}")
        if not fields:
            return
        if "classification" in fields:
            classification = str(fields["classification"]).upper()
            if classification not in CLASSIFICATIONS:
                raise TraceStoreError(f"unknown classification: {classification}")
            fields["classification"] = classification
        if "stage" in fields:
            stage = str(fields["stage"]).upper()
            if stage not in STAGES:
                raise TraceStoreError(f"unknown trace stage: {stage}")
            fields["stage"] = stage
        if "root_cause" in fields:
            fields["root_cause"] = _normalise_root_cause(fields["root_cause"])
        if "translation" in fields and "translation_hash" not in fields:
            translation = fields["translation"]
            if translation is not None:
                fields["translation_hash"] = hashlib.sha256(
                    str(translation).encode("utf-8", "surrogatepass")
                ).hexdigest()
        assignments = ", ".join(f"{name} = ?" for name in fields)
        values = [fields[name] for name in fields] + [trace_id]
        cursor = self.connection.execute(
            f"UPDATE trace_entries SET {assignments} WHERE trace_id = ?",
            values,
        )
        if cursor.rowcount != 1:
            raise TraceStoreError(f"unknown trace_id: {trace_id}")
        self._commit_if_needed()

    def update_target(self, target_id: str, **fields: Any) -> None:
        """Update a duplicate-aware patch target through the trace API."""

        self._ensure_open()
        allowed = {"patch_target", "status", "root_cause", "write_status", "readback_status", "final_verification"}
        unknown = set(fields) - allowed
        if unknown:
            raise TraceStoreError(f"unsupported trace target fields: {sorted(unknown)}")
        if not fields:
            return
        if "root_cause" in fields:
            fields["root_cause"] = _normalise_root_cause(fields["root_cause"])
        assignments = ", ".join(f"{name} = ?" for name in fields)
        values = [fields[name] for name in fields] + [target_id]
        cursor = self.connection.execute(
            f"UPDATE trace_targets SET {assignments} WHERE target_id = ?",
            values,
        )
        if cursor.rowcount != 1:
            raise TraceStoreError(f"unknown target_id: {target_id}")
        self._commit_if_needed()

    def start_event(
        self,
        stage: str,
        *,
        trace_id: str | None = None,
        target_id: str | None = None,
        attempt_id: str | None = None,
        payload: Mapping[str, Any] | None = None,
        root_cause: str | None = None,
    ) -> str:
        self._ensure_open()
        if self.run_id is None:
            raise TraceStoreError("start_run must be called before recording events")
        run_row = self.connection.execute(
            "SELECT status FROM trace_runs WHERE run_id = ?", (self.run_id,)
        ).fetchone()
        if not run_row:
            raise TraceStoreError(f"unknown run_id: {self.run_id}")
        if run_row[0] != "RUNNING":
            raise TraceStoreError(f"run is not RUNNING: {self.run_id} ({run_row[0]})")
        stage = str(stage).upper()
        if stage not in STAGES:
            raise TraceStoreError(f"unknown trace stage: {stage}")
        root_cause = _normalise_root_cause(root_cause)
        if trace_id and not self.connection.execute(
            "SELECT 1 FROM trace_entries WHERE trace_id = ?", (trace_id,)
        ).fetchone():
            raise TraceStoreError(f"unknown trace_id: {trace_id}")
        if target_id and not self.connection.execute(
            "SELECT 1 FROM trace_targets WHERE target_id = ?", (target_id,)
        ).fetchone():
            raise TraceStoreError(f"unknown target_id: {target_id}")
        action_id = str(uuid.uuid4())
        self.connection.execute(
            """
            INSERT INTO trace_events(
                action_id, run_id, trace_id, target_id, attempt_id, stage,
                event_status, root_cause, created_at, payload_json
            ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                action_id,
                self.run_id,
                trace_id,
                target_id,
                attempt_id,
                stage,
                EVENT_STARTED,
                root_cause,
                _utc_now(),
                _json_text(payload),
            ),
        )
        self._commit_if_needed()
        return action_id

    def finish_event(
        self,
        action_id: str,
        status: str = EVENT_COMPLETED,
        *,
        root_cause: str | None = None,
        payload: Mapping[str, Any] | None = None,
    ) -> int:
        self._ensure_open()
        start = self.connection.execute(
            """
            SELECT run_id, trace_id, target_id, attempt_id, stage
            FROM trace_events WHERE action_id = ? AND event_status = 'STARTED'
            ORDER BY event_id LIMIT 1
            """,
            (action_id,),
        ).fetchone()
        if not start:
            raise TraceStoreError(f"no STARTED event for action_id: {action_id}")
        run_status = self.connection.execute(
            "SELECT status FROM trace_runs WHERE run_id = ?", (start[0],)
        ).fetchone()
        if not run_status:
            raise TraceStoreError(f"unknown run_id: {start[0]}")
        if run_status[0] != "RUNNING":
            raise TraceStoreError(f"run is not RUNNING: {start[0]} ({run_status[0]})")
        if self.connection.execute(
            "SELECT 1 FROM trace_events WHERE action_id = ? AND event_status <> 'STARTED' LIMIT 1",
            (action_id,),
        ).fetchone():
            raise TraceStoreError(f"action already terminal: {action_id}")
        status = str(status).upper()
        event_root_cause = _normalise_root_cause(root_cause)
        event_id = self.connection.execute(
            """
            INSERT INTO trace_events(
                action_id, run_id, trace_id, target_id, attempt_id, stage,
                event_status, root_cause, created_at, payload_json
            ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                action_id,
                start[0],
                start[1],
                start[2],
                start[3],
                start[4],
                status,
                event_root_cause,
                _utc_now(),
                _json_text(payload),
            ),
        ).lastrowid
        if start[2]:
            self.connection.execute(
                "UPDATE trace_targets SET status = ?, root_cause = ? WHERE target_id = ?",
                (status, event_root_cause, start[2]),
            )
        if start[1]:
            self.connection.execute(
                "UPDATE trace_entries SET stage = ?, status = ?, root_cause = ? WHERE trace_id = ?",
                (start[4], status, event_root_cause, start[1]),
            )
        self._commit_if_needed()
        return int(event_id)

    def record_event(
        self,
        stage: str,
        status: str = EVENT_COMPLETED,
        *,
        trace_id: str | None = None,
        target_id: str | None = None,
        attempt_id: str | None = None,
        root_cause: str | None = None,
        payload: Mapping[str, Any] | None = None,
    ) -> int:
        action_id = self.start_event(
            stage,
            trace_id=trace_id,
            target_id=target_id,
            attempt_id=attempt_id,
            root_cause=root_cause,
            payload=payload,
        )
        return self.finish_event(
            action_id,
            status,
            root_cause=root_cause,
            payload=payload,
        )

    def _counts(self, table: str, column: str) -> dict[str, int]:
        if table not in {"trace_entries", "trace_targets", "trace_events", "trace_runs"}:
            raise ValueError(table)
        if column not in {"classification", "stage", "status", "root_cause", "event_status"}:
            raise ValueError(column)
        where = f" WHERE {column} IS NOT NULL AND {column} <> ''" if column == "root_cause" else ""
        rows = self.connection.execute(
            f"SELECT {column}, COUNT(*) FROM {table}{where} GROUP BY {column} ORDER BY {column}"
        ).fetchall()
        return {str(key or "UNKNOWN"): int(count) for key, count in rows}

    def summary(self) -> dict[str, Any]:
        self._ensure_open()
        summary = {
            "schema_version": TRACE_SCHEMA_VERSION,
            "package_id": self.package_id,
            "run_id": self.run_id,
            "entries": int(self.connection.execute("SELECT COUNT(*) FROM trace_entries").fetchone()[0]),
            "targets": int(self.connection.execute("SELECT COUNT(*) FROM trace_targets").fetchone()[0]),
            "events": int(self.connection.execute("SELECT COUNT(*) FROM trace_events").fetchone()[0]),
            "runs": int(self.connection.execute("SELECT COUNT(*) FROM trace_runs").fetchone()[0]),
            "classification_counts": self._counts("trace_entries", "classification"),
            "stage_counts": self._counts("trace_entries", "stage"),
            "entry_status_counts": self._counts("trace_entries", "status"),
            "target_status_counts": self._counts("trace_targets", "status"),
            "event_status_counts": self._counts("trace_events", "event_status"),
            "run_status_counts": self._counts("trace_runs", "status"),
            "root_cause_counts": self._counts("trace_entries", "root_cause"),
            "event_root_cause_counts": self._counts("trace_events", "root_cause"),
        }
        return summary

    def write_summary(
        self,
        path: str | Path | None = None,
        *,
        extra: Mapping[str, Any] | None = None,
    ) -> Path:
        target = Path(path) if path is not None else self.meta_dir / TRACE_SUMMARY_NAME
        target.parent.mkdir(parents=True, exist_ok=True)
        payload = dict(self.summary())
        payload["generated_at"] = _utc_now()
        if extra:
            measurements = {}
            if target.is_file():
                try:
                    previous = json.loads(target.read_text(encoding="utf-8"))
                    if isinstance(previous, Mapping) and isinstance(previous.get("measurements"), Mapping):
                        measurements.update(previous["measurements"])
                except (OSError, ValueError, TypeError, json.JSONDecodeError):
                    pass
            measurements.update(_canonical_value(dict(extra)))
            payload["measurements"] = measurements
        temp = target.with_name(f".{target.name}.{uuid.uuid4().hex}.tmp")
        temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        os.replace(temp, target)
        self.write_diagnostic_summary(summary_payload=payload)
        return target

    def write_diagnostic_summary(
        self,
        path: str | Path | None = None,
        *,
        extra: Mapping[str, Any] | None = None,
        summary_payload: Mapping[str, Any] | None = None,
    ) -> Path:
        """Write a compact, actionable view beside the trace summary.

        Counts are derived from the trace store. Optional measurements are
        copied from pipeline callers without inventing coverage or stage
        results that were not recorded.
        """
        target = Path(path) if path is not None else self.meta_dir / TRACE_DIAGNOSTIC_NAME
        target.parent.mkdir(parents=True, exist_ok=True)
        summary = dict(summary_payload or self.summary())
        measurements = summary.get("measurements")
        if not isinstance(measurements, Mapping):
            measurements = {}
        if extra:
            measurements = {**dict(measurements), **dict(extra)}
        coverage = measurements.get("trace_coverage")
        if not isinstance(coverage, Mapping):
            coverage = {
                "status": "NOT_RECORDED",
                "reason": "Caller did not provide trace coverage metadata.",
                "untraced_caller_count": None,
            }
        translation = measurements.get("translation")
        patch = measurements.get("patch")
        roots = summary.get("root_cause_counts") or {}
        runs = summary.get("run_status_counts") or {}
        if roots.get(ROOT_CAUSE_PATCH_VERIFY_FAILED, 0):
            next_step = "Inspect patch read-back evidence and repair the failing locator before rerunning Patch."
        elif roots.get(ROOT_CAUSE_PATCH_FAILED, 0):
            next_step = "Inspect patch gate/backup evidence and repair the blocked patch route."
        elif roots.get(ROOT_CAUSE_TRANSLATION_INVALID, 0):
            next_step = "Review blocker_inventory.json and retry only invalid translation candidates."
        elif roots.get(ROOT_CAUSE_TRANSLATION_MISSED, 0):
            next_step = "Inspect missing translation candidates and rerun the translation gate."
        elif roots.get(ROOT_CAUSE_MISCLASSIFIED, 0):
            next_step = "Review the authoritative classifier route against the package split before translation."
        elif roots.get(ROOT_CAUSE_DISCOVERY_GAP, 0):
            next_step = "Review discovery inventory and classify unhandled resources before translation."
        elif summary.get("classification_counts", {}).get(CLASSIFICATION_REVIEW, 0) or summary.get("classification_counts", {}).get(CLASSIFICATION_UNSUPPORTED, 0):
            next_step = "Review REVIEW/UNSUPPORTED entries; do not mark the package complete until routed."
        elif runs and runs.get(EVENT_COMPLETED, 0) == 0:
            next_step = "Resolve the non-terminal trace run before trusting downstream completion."
        else:
            next_step = "No actionable failure recorded; continue to the next workflow stage with this evidence."
        payload = {
            "schema_version": 1,
            "package_id": summary.get("package_id"),
            "run_id": summary.get("run_id"),
            "generated_at": _utc_now(),
            "total_candidates": int(summary.get("entries") or 0),
            "classification_counts": summary.get("classification_counts") or {},
            "stage_counts": summary.get("stage_counts") or {},
            "root_cause_counts": roots,
            "trace_coverage": _canonical_value(dict(coverage)),
            "untraced_caller_count": coverage.get("untraced_caller_count"),
            "translation": _canonical_value(translation if isinstance(translation, Mapping) else {}),
            "patch": _canonical_value(patch if isinstance(patch, Mapping) else {}),
            "artifact_lifecycle": _canonical_value(measurements.get("artifact_lifecycle", {})),
            "actionable_next_step": next_step,
            "evidence": {
                "trace_summary": TRACE_SUMMARY_NAME,
                "trace_export": TRACE_EXPORT_NAME,
            },
        }
        temp = target.with_name(f".{target.name}.{uuid.uuid4().hex}.tmp")
        temp.write_text(json.dumps(_canonical_value(payload), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        os.replace(temp, target)
        return target

    def export_jsonl(self, path: str | Path | None = None) -> Path:
        target = Path(path) if path is not None else self.meta_dir / TRACE_EXPORT_NAME
        target.parent.mkdir(parents=True, exist_ok=True)
        rows = self.connection.execute(
            """
            SELECT event_id, action_id, run_id, trace_id, target_id, attempt_id,
                   stage, event_status, root_cause, created_at, payload_json
            FROM trace_events ORDER BY event_id
            """
        ).fetchall()
        with target.open("w", encoding="utf-8", newline="\n") as handle:
            for row in rows:
                record = {
                    "event_id": row[0],
                    "action_id": row[1],
                    "run_id": row[2],
                    "trace_id": row[3],
                    "target_id": row[4],
                    "attempt_id": row[5],
                    "stage": row[6],
                    "event_status": row[7],
                    "root_cause": row[8],
                    "created_at": row[9],
                    "payload": json.loads(row[10]),
                }
                handle.write(_canonical_json(record) + "\n")
        return target

    def close(self) -> None:
        connection, self._connection = self._connection, None
        if connection is not None:
            try:
                if self._batch_depth:
                    connection.rollback()
                connection.close()
            finally:
                self._batch_depth = 0
        if self._lock_acquired:
            try:
                current = json.loads(self.lock_path.read_text(encoding="utf-8"))
                if current.get("owner_id") == self._owner_id:
                    self.lock_path.unlink(missing_ok=True)
            except (FileNotFoundError, OSError, json.JSONDecodeError):
                pass
            finally:
                self._lock_acquired = False

    def __enter__(self) -> "TraceStore":
        return self

    def __exit__(self, exc_type: Any, exc_value: Any, traceback: Any) -> None:
        if self.run_id is not None:
            try:
                row = self.connection.execute(
                    "SELECT status FROM trace_runs WHERE run_id = ?", (self.run_id,)
                ).fetchone()
                if row and row[0] == "RUNNING":
                    if exc_type is None:
                        self.finish_run(EVENT_COMPLETED)
                    else:
                        self.finish_run(EVENT_ABORTED, ROOT_CAUSE_UNKNOWN)
            finally:
                self.close()
        else:
            self.close()


__all__ = [
    "CLASSIFICATION_MAIN",
    "CLASSIFICATION_TRANSLATE",
    "CLASSIFICATION_REVIEW",
    "CLASSIFICATION_SKIP",
    "CLASSIFICATION_DO_NOT_TRANSLATE",
    "CLASSIFICATION_UNSUPPORTED",
    "EVENT_ABORTED",
    "EVENT_COMPLETED",
    "EVENT_FAILED",
    "EVENT_STARTED",
    "EVENT_UNKNOWN",
    "ROOT_CAUSE_DISCOVERY_GAP",
    "ROOT_CAUSE_EXTRACT_MISSED",
    "ROOT_CAUSE_FONT_RENDER",
    "ROOT_CAUSE_MISCLASSIFIED",
    "ROOT_CAUSE_PATCH_FAILED",
    "ROOT_CAUSE_PATCH_VERIFY_FAILED",
    "ROOT_CAUSE_RUNTIME_SOURCE_MISMATCH",
    "ROOT_CAUSE_TRANSLATION_INVALID",
    "ROOT_CAUSE_TRANSLATION_MISSED",
    "ROOT_CAUSE_UNKNOWN",
    "STAGE_CLASSIFIED",
    "STAGE_DISCOVERED",
    "STAGE_EXTRACTED",
    "STAGE_NOT_TESTABLE",
    "STAGE_PATCHED",
    "STAGE_READ_BACK_VERIFIED",
    "STAGE_RUNTIME_VERIFIED",
    "STAGE_TRANSLATED",
    "STAGE_VALIDATED",
    "TRACE_SCHEMA_VERSION",
    "TRACE_DIAGNOSTIC_NAME",
    "TraceSink",
    "TraceStore",
    "TraceStoreError",
    "NullTraceSink",
    "canonical_identity_text",
    "canonical_locator",
    "compute_package_id",
    "compute_target_id",
    "compute_trace_id",
]
