# -*- coding: utf-8 -*-

"""Safe cleanup for the reproducible test workspace.

Only registered or explicitly audited disposable paths may be removed.  The
tool never deletes source trees, external fixtures, user data, or an
unclassified artifact.  New test output must use ``work_paths`` registration
instead of adding a name-based exception here.
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

import argparse
from dataclasses import dataclass, field
import hashlib
import json
import math
import os
import shutil
import stat
import subprocess
import tempfile
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from work_paths import (  # noqa: E402
    E2E_GAME_COPY,
    MANIFEST_PATH,
    WORK_ROOT,
    cleanup_target,
    dir_size_bytes,
    ensure_work_root,
    assert_artifact_under_work,
    ambient_scope,
    is_protected_path,
    kill_processes_using,
    make_deletion_provenance,
    path_under_work,
    processes_using,
    register_artifact,
    new_scope_id,
    RUN_OUTCOMES,
    ACTIVE_LIFECYCLE_STATES,
    LIFECYCLE_STATES,
)

EVIDENCE = WORK_ROOT / "evidence"
CLEANUP_MANIFEST = WORK_ROOT / "cleanup_manifest.json"
SIZE_REPORT = WORK_ROOT / "size_report_before_cleanup.json"
REPORT_INLINE_RECORD_LIMIT = 100
PROJECT_SIZE_LIMIT_BYTES = 1024 ** 3
PROJECT_EXEMPT_SIZE_LIMIT_BYTES = 5 * 1024 ** 3
PROJECT_SIZE_EXEMPTIONS = {
    ".venv": "project Python virtual environment",
    "DEV_RUN/dotnet-sdk-10": "publisher .NET SDK",
    "DEV_RUN/python": "private DEV Python runtime",
    "DEV_RUN/.venv": "DEV worker virtual environment",
    "DEV_RUN/cache": "DEV runtime cache",
    "tests/golden/_work/r12i": "Owner-approved pristine public v0.1 installed baseline",
    "DEV_RUN/v01_audit/installed": "Owner-approved protected installed baseline with data/models",
    "DEV_RUN/baselines/fullapp-013": "Owner-approved real installed full-app acceptance witness",
}

# Keep relative to WORK_ROOT
KEEP_PATHS = {
    "game_copy",
    "mt_pipeline_copy",
    "artifacts_manifest.json",
    "evidence",
    "models",
    "release_verify",
}

# Entire directories under _work that are safe to remove when not locked
DELETE_DIR_NAMES = {
    "game_copy_vi",
    "release_e2e",
    "wpf_ui_screenshot",
    "mt_pipeline_endurance",
    "mt_pipeline_bench500",
    "mt_pipeline_bench_strat500",
    "vh_parity_bench500",
    "worker_translate",
    "worker_tasks",
    "qa_m3",
    "mt_endurance_5fix",
    "artifacts_hard_probe",
    "icon_probe",
    "smoke_m3",
    "smoke_patch_dbg",
    "tests",
    "crash_investigation",
    "addr_isolation",
    "phase3_flags_probe",
}

# Explicit migration paths retained for generic, reproducible test output.
# A future similarly-named directory is not automatically disposable.
EXTRA_DELETE_PATHS = {
    "coverage/file_roundtrip",
}

EXTRA_DELETE_GLOBS = {
    "unity_patch/previous_patch_out_*",
}


# Cleanup is allowed to inspect a large, pre-existing _work tree, but it must
# never make the caller wait forever while trying to classify it.  These are
# safety limits, not completeness shortcuts: exhausting either limit makes
# the run REVIEW_REQUIRED and prevents deletion.
DEFAULT_INVENTORY_TIMEOUT_SECONDS = 30.0
DEFAULT_INVENTORY_MAX_ITEMS = 100_000
# Hashing every small file in a retained Python/runtime tree can turn a
# bounded inventory into a multi-gigabyte read.  Size/mtime remain the primary
# modification signature; exact hashes are retained for genuinely small
# files, which is sufficient for duplicate measurement and focused tests.
DEFAULT_HASH_MAX_BYTES = 64 * 1024
DEFAULT_HASH_BUDGET_BYTES = 32 * 1024 * 1024

PROSPECTIVE_EPOCH_SCHEMA_VERSION = 1
PROSPECTIVE_EPOCH_POLICY_VERSION = "prospective-artifact-registry-v1"
INCIDENT_SCOPE_ID = "registry-incident-20260921-f1be76ac406840afb654f151df148bc8"
INCIDENT_REGISTRY_SHA256 = "2091DC0FFCBCC0FE30F748CF63A0D6F7CFC0CAE3129A241331C6B0DC81251EDB"
INCIDENT_REGISTRY_COUNT = 6
HISTORICAL_REGISTRY_SHA256 = "26FD19AB082EEA28ED0F8DA0BEF63EB4521F8FC05FB01B4FE24EE41AE7D3B948"
HISTORICAL_REGISTRY_COUNT = 19030


class InventoryFailure(RuntimeError):
    """A bounded inventory could not establish a complete classification."""

    def __init__(self, details: dict):
        self.details = dict(details)
        super().__init__(str(self.details.get("reason") or "inventory failed"))


@dataclass
class InventoryBudget:
    """Shared wall-clock/item budget for one cleanup operation."""

    timeout_seconds: float = DEFAULT_INVENTORY_TIMEOUT_SECONDS
    max_items: int = DEFAULT_INVENTORY_MAX_ITEMS
    max_hash_bytes: int = DEFAULT_HASH_BUDGET_BYTES
    started: float = field(default_factory=time.monotonic)
    items_seen: int = 0
    hashed_bytes: int = 0
    failure: dict | None = None

    def __post_init__(self) -> None:
        try:
            self.timeout_seconds = float(self.timeout_seconds)
        except (TypeError, ValueError):
            self.timeout_seconds = DEFAULT_INVENTORY_TIMEOUT_SECONDS
        if not math.isfinite(self.timeout_seconds):
            self.timeout_seconds = DEFAULT_INVENTORY_TIMEOUT_SECONDS
        try:
            self.max_items = int(self.max_items)
        except (TypeError, ValueError):
            self.max_items = DEFAULT_INVENTORY_MAX_ITEMS
        self.max_items = max(1, self.max_items)
        try:
            self.max_hash_bytes = int(self.max_hash_bytes)
        except (TypeError, ValueError):
            self.max_hash_bytes = DEFAULT_HASH_BUDGET_BYTES
        self.max_hash_bytes = max(0, self.max_hash_bytes)

    def reserve_hash(self, size: int) -> bool:
        """Bound optional duplicate-measurement I/O without failing inventory."""

        amount = max(0, int(size))
        if self.hashed_bytes + amount > self.max_hash_bytes:
            return False
        self.hashed_bytes += amount
        return True

    def check_deadline(self, path: Path, *, phase: str = "inventory") -> None:
        """Check the shared wall-clock deadline without consuming an item slot."""

        if self.failure:
            raise InventoryFailure(self.failure)
        if self.timeout_seconds <= 0 or time.monotonic() - self.started >= self.timeout_seconds:
            reason = "inventory_timeout" if phase == "inventory" else "cleanup_timeout"
            self.failure = {
                "status": "TIMEOUT",
                "reason": reason,
                "phase": phase,
                "path": str(path),
                "items_seen": self.items_seen,
                "timeout_seconds": self.timeout_seconds,
                "max_items": self.max_items,
            }
            raise InventoryFailure(self.failure)

    def check(self, path: Path) -> None:
        """Raise as soon as the bounded operation can no longer be trusted."""

        self.check_deadline(path, phase="inventory")
        if self.items_seen >= self.max_items:
            self.failure = {
                "status": "LIMIT",
                "reason": "inventory_item_limit",
                "path": str(path),
                "items_seen": self.items_seen,
                "timeout_seconds": self.timeout_seconds,
                "max_items": self.max_items,
            }
            raise InventoryFailure(self.failure)
        self.items_seen += 1

    def report(self) -> dict:
        failure = dict(self.failure or {})
        return {
            "complete": self.failure is None,
            "status": str(failure.get("status") or "PASS"),
            "reason": failure.get("reason"),
            "path": failure.get("path"),
            "items_seen": self.items_seen,
            "timeout_seconds": self.timeout_seconds,
            "max_items": self.max_items,
            "hashed_bytes": self.hashed_bytes,
            "hash_budget_bytes": self.max_hash_bytes,
            "failure": failure or None,
        }


def _new_inventory_budget(
    budget: InventoryBudget | None = None,
    *,
    timeout_seconds: float | None = None,
    max_items: int | None = None,
) -> InventoryBudget:
    if budget is not None:
        return budget
    return InventoryBudget(
        timeout_seconds=(
            DEFAULT_INVENTORY_TIMEOUT_SECONDS
            if timeout_seconds is None
            else timeout_seconds
        ),
        max_items=(DEFAULT_INVENTORY_MAX_ITEMS if max_items is None else max_items),
    )


def _inventory_error(path: Path, exc: BaseException) -> dict:
    if isinstance(exc, InventoryFailure):
        return dict(exc.details)
    return {
        "status": "ERROR",
        "reason": "inventory_error",
        "path": str(path),
        "error": str(exc),
    }


def _bounded_dir_size(
    path: Path,
    budget: InventoryBudget,
    *,
    include_protected: bool = False,
    skip_retained: bool = False,
) -> int:
    """Return size without following protected trees or leaving the budget."""

    path = _absolute_path(Path(path).expanduser())
    if not path.exists():
        return 0
    if not include_protected and (
        is_protected_path(path) or (skip_retained and _is_explicit_keep(path))
    ):
        return 0
    total = 0
    pending = [path]
    while pending:
        current = pending.pop()
        budget.check(current)
        try:
            if current.is_symlink():
                continue
            if current.is_file():
                total += int(current.stat().st_size)
                continue
            with os.scandir(current) as entries:
                for entry in entries:
                    child = Path(entry.path)
                    budget.check(child)
                    if entry.is_symlink():
                        continue
                    if entry.is_dir(follow_symlinks=False):
                        resolved = _absolute_path(child)
                        if not include_protected and (
                            is_protected_path(resolved)
                            or (skip_retained and _is_explicit_keep(resolved))
                        ):
                            continue
                        pending.append(child)
                    else:
                        total += int(entry.stat(follow_symlinks=False).st_size)
        except OSError as exc:
            raise InventoryFailure(_inventory_error(current, exc)) from exc
    return total


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def human_gb(n: int) -> float:
    return round(n / (1024**3), 3)


def size_tree(
    path: Path,
    depth: int = 1,
    *,
    budget: InventoryBudget | None = None,
    include_protected: bool = False,
    skip_retained: bool = False,
) -> dict:
    budget = _new_inventory_budget(budget)
    path = _absolute_path(Path(path).expanduser())
    out: dict = {
        "path": str(path),
        "bytes": 0,
        "gb": 0.0,
        "children": [],
        "complete": True,
        "inventory": budget.report(),
    }
    if not path.exists():
        return out
    try:
        total = _bounded_dir_size(
            path,
            budget,
            include_protected=include_protected,
            skip_retained=skip_retained,
        )
    except InventoryFailure as exc:
        out["complete"] = False
        out["error"] = _inventory_error(path, exc)
        out["inventory"] = budget.report()
        return out
    out["bytes"] = total
    out["gb"] = human_gb(total)
    if depth <= 0 or path.is_file() or is_protected_path(path) and not include_protected:
        out["inventory"] = budget.report()
        return out
    kids = []
    try:
        with os.scandir(path) as entries:
            for entry in entries:
                child = Path(entry.path)
                try:
                    budget.check(child)
                    if entry.is_symlink():
                        continue
                    protected = entry.is_dir(follow_symlinks=False) and is_protected_path(child)
                    retained = entry.is_dir(follow_symlinks=False) and _is_explicit_keep(child)
                    if (protected or (skip_retained and retained)) and not include_protected:
                        kids.append(
                            {
                                "name": child.name,
                                "bytes": 0,
                                "gb": 0.0,
                                "is_dir": True,
                                "protected": True,
                                "complete": True,
                            }
                        )
                        continue
                    b = _bounded_dir_size(
                        child,
                        budget,
                        include_protected=include_protected,
                        skip_retained=skip_retained,
                    )
                    kids.append(
                        {
                            "name": child.name,
                            "bytes": b,
                            "gb": human_gb(b),
                            "is_dir": entry.is_dir(follow_symlinks=False),
                            "complete": True,
                        }
                    )
                except (InventoryFailure, OSError) as exc:
                    out["complete"] = False
                    out.setdefault("errors", []).append(_inventory_error(child, exc))
                    if isinstance(exc, InventoryFailure):
                        break
    except OSError as exc:
        out["complete"] = False
        out.setdefault("errors", []).append(_inventory_error(path, exc))
    if out["complete"]:
        kids.sort(key=lambda x: x["bytes"], reverse=True)
        out["children"] = kids[:40]
    else:
        out["children"] = kids[:40]
    out["inventory"] = budget.report()
    return out


def write_size_report(
    dest: Path | None = None,
    *,
    timeout_seconds: float | None = None,
    max_items: int | None = None,
) -> dict:
    dest = dest or SIZE_REPORT
    ensure_work_root()
    budget = _new_inventory_budget(
        timeout_seconds=timeout_seconds,
        max_items=max_items,
    )
    report = {
        "utc": utc_now(),
        "dev_root": str(ROOT),
        "work_root": str(WORK_ROOT),
        "dev_total": size_tree(ROOT, depth=0, budget=budget),
        "work": size_tree(WORK_ROOT, depth=1, budget=budget),
        "evidence": size_tree(WORK_ROOT / "evidence", depth=1, budget=budget),
    }
    # fill totals
    report["dev_total_gb"] = report["dev_total"]["gb"] if report["dev_total"]["complete"] else None
    report["work_total_gb"] = report["work"]["gb"] if report["work"]["complete"] else None
    report["inventory"] = budget.report()
    dest.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def _rel_under_work(path: Path) -> str:
    return str(path.resolve().relative_to(WORK_ROOT.resolve())).replace("\\", "/")


def is_keep(path: Path, *, allow_registered_disposable: bool = False) -> bool:
    if is_protected_path(path):
        return True
    if not path_under_work(path):
        return True  # never delete outside _work from this tool
    rel = _rel_under_work(path)
    if rel in KEEP_PATHS and not allow_registered_disposable:
        return True
    for keep in KEEP_PATHS:
        if not allow_registered_disposable and (rel == keep or rel.startswith(keep.rstrip("/") + "/")):
            return True
    # always keep mt_pipeline_copy backups folder (csv.bak)
    if rel.startswith("mt_pipeline_copy/"):
        return True
    if path == E2E_GAME_COPY or E2E_GAME_COPY.resolve() in path.resolve().parents or path.resolve() == E2E_GAME_COPY.resolve():
        return True
    return False


def safe_rmtree(
    path: Path,
    deleted: list[dict],
    *,
    reason: str,
    budget: InventoryBudget | None = None,
    allow_registered_disposable: bool = False,
    registered_entries: list[dict] | None = None,
) -> bool:
    # Do not resolve and then delete through a registered symlink/reparse
    # point. The project-size inventory also marks links incomplete.
    try:
        link_stat = path.lstat()
    except FileNotFoundError:
        return False
    except OSError as exc:
        deleted.append({"path": str(path), "skipped": True, "reason": f"stat_error:{exc}"})
        return False
    if stat.S_ISLNK(link_stat.st_mode) or getattr(link_stat, "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400):
        deleted.append({"path": str(path), "skipped": True, "reason": "link_or_reparse_point"})
        return False
    if not path.exists():
        return False
    try:
        path = cleanup_target(path, "safe cleanup")
    except RuntimeError as exc:
        deleted.append({"path": str(path), "skipped": True, "reason": "protected_or_outside", "error": str(exc)})
        return False
    if is_keep(path, allow_registered_disposable=allow_registered_disposable):
        deleted.append({"path": str(path), "skipped": True, "reason": "keep_policy"})
        return False
    if allow_registered_disposable:
        if registered_entries is None:
            from work_paths import _load_manifest

            registered_entries = _load_manifest().get("artifacts", [])
        keeper = _registered_keep_blocker(path, registered_entries)
        if keeper is not None:
            deleted.append({
                "path": str(path),
                "skipped": True,
                "reason": "registered_non_disposable_descendant",
                "blocking_id": keeper.get("id"),
            })
            return False
    # Never kill a process as part of cleanup.  A live game process makes the
    # target LOCKED and the caller must fail closed or retry later.
    if path.is_dir() and processes_using(path):
        deleted.append({"path": str(path), "skipped": True, "reason": "locked_by_process"})
        return False
    budget = _new_inventory_budget(budget)
    try:
        nbytes = _bounded_dir_size(path, budget)
    except (InventoryFailure, OSError) as exc:
        deleted.append(
            {
                "path": str(path),
                "skipped": True,
                "reason": _inventory_error(path, exc)["reason"],
                "error": _inventory_error(path, exc),
            }
        )
        return False
    try:
        if path.is_file() or path.is_symlink():
            path.unlink(missing_ok=True)
        else:
            shutil.rmtree(path, ignore_errors=False)
    except OSError as exc:
        deleted.append({"path": str(path), "skipped": True, "reason": f"os_error:{exc}", "bytes": nbytes})
        return False
    deleted.append(
        {
            "path": str(path),
            "deleted": True,
            "deleted_at": utc_now(),
            "reason": reason,
            "bytes": nbytes,
            "gb": human_gb(nbytes),
        }
    )
    return True


def _snapshot_phase_budget(budget: InventoryBudget) -> InventoryBudget:
    """Give one complete tree inventory its own quota within one deadline."""

    phase_budget = InventoryBudget(
        timeout_seconds=budget.timeout_seconds,
        max_items=budget.max_items,
        max_hash_bytes=budget.max_hash_bytes,
        started=budget.started,
    )
    if budget.failure:
        phase_budget.failure = dict(budget.failure)
    return phase_budget


def _record_snapshot_failure(budget: InventoryBudget, phase_budget: InventoryBudget) -> None:
    """Carry a failed inventory proof into the enclosing fail-closed report."""

    if phase_budget.failure and not budget.failure:
        budget.items_seen = phase_budget.items_seen
        budget.hashed_bytes = phase_budget.hashed_bytes
        budget.failure = dict(phase_budget.failure)


def _entry_path(entry: dict) -> Path:
    raw_value = str(entry.get("path") or "").strip()
    if not raw_value:
        raise ValueError(f"artifact entry {entry.get('id')} has no path")
    raw = Path(raw_value)
    if not raw.is_absolute():
        raw = WORK_ROOT / raw
    # Registry reconciliation is read-only and may contain old MISSING paths
    # or paths below a very large tree.  ``Path.resolve()`` performs Windows
    # filesystem final-path lookups and was the second unbounded choke point
    # after recursive inventory.  Normalize lexically here; deletion still
    # goes through cleanup_target(), which performs the real safety check.
    return Path(os.path.abspath(os.fspath(raw)))


def _registered_keep_blocker(path: Path, entries: list[dict]) -> dict | None:
    """Find any live non-disposable claim on a deletion root or its descendants."""

    target = _absolute_path(path)
    if not isinstance(entries, list):
        return {"id": "malformed_registry", "lifecycle": "UNKNOWN", "reason": "registry_entries_not_a_list"}
    for entry in entries:
        if not isinstance(entry, dict):
            return {"id": "malformed_registry_entry", "lifecycle": "UNKNOWN", "reason": "registry_entry_not_an_object"}
        lifecycle_raw = str(entry.get("lifecycle") or entry.get("state") or "").upper().strip()
        status = str(entry.get("status") or "").upper().strip()
        if lifecycle_raw:
            lifecycle = lifecycle_raw if lifecycle_raw in LIFECYCLE_STATES else "UNKNOWN"
        else:
            lifecycle = status if status in LIFECYCLE_STATES else ("RETAINED" if status == "ACTIVE" else "UNKNOWN")
        try:
            keeper = _entry_path(entry)
        except (KeyError, TypeError, ValueError, OSError):
            return {**entry, "lifecycle": "UNKNOWN", "reason": "registered_claim_path_invalid"}
        if lifecycle == "DISPOSABLE":
            continue
        related = keeper == target or target in keeper.parents
        exists = os.path.lexists(keeper)
        if lifecycle == "MISSING":
            if related and exists:
                return {**entry, "lifecycle": "STALE", "reason": "missing_claim_path_still_exists"}
            continue
        if related and exists:
            return {**entry, "lifecycle": lifecycle}
    return None


def _absolute_path(path: Path) -> Path:
    """Normalize a local path without a Windows final-path filesystem call."""

    return Path(os.path.abspath(os.fspath(path)))


def _path_key(path: Path) -> str:
    """Return a cheap normalized key for exact/ancestor path lookups."""

    return os.path.normcase(os.path.abspath(os.fspath(path)))


class _PathEntryIndex:
    """Index registry paths for O(depth) ownership/lifecycle lookups.

    The old metrics path scanned every registry entry for every inventory item.
    Keeping exact path maps and walking only the candidate's ancestors avoids
    that inventory-size by registry-size cross-product while preserving the
    longest-path-wins semantics.
    """

    def __init__(
        self,
        entries: list[dict],
        *,
        budget: InventoryBudget | None = None,
        phase: str = "reconciliation",
    ) -> None:
        self.budget = budget
        self.phase = phase
        self.exact: dict[str, tuple[Path, dict]] = {}
        self.disposable: dict[str, tuple[Path, dict]] = {}
        for entry in entries:
            if budget is not None:
                budget.check_deadline(
                    Path(str(entry.get("path") or "<missing-path>")),
                    phase=phase,
                )
            try:
                entry_path = _entry_path(entry)
            except (KeyError, TypeError, ValueError, OSError):
                continue
            key = _path_key(entry_path)
            self.exact.setdefault(key, (entry_path, entry))
            if str(entry.get("lifecycle") or "").upper() == "DISPOSABLE":
                self.disposable.setdefault(key, (entry_path, entry))

    def exact_entry(self, path: Path) -> dict | None:
        item = self.exact.get(_path_key(path))
        return item[1] if item is not None else None

    def scoped_entry(self, path: Path, *, allow_disposable_parent: bool = True) -> dict | None:
        resolved = _absolute_path(path)
        if self.budget is not None:
            self.budget.check_deadline(resolved, phase=self.phase)
        item = self.exact.get(_path_key(resolved))
        if item is not None:
            return item[1]
        if not allow_disposable_parent:
            return None
        for parent in resolved.parents:
            if self.budget is not None:
                self.budget.check_deadline(parent, phase=self.phase)
            item = self.disposable.get(_path_key(parent))
            if item is not None:
                return item[1]
        return None

    def lifecycle_for(self, path: Path) -> str | None:
        resolved = _absolute_path(path)
        for candidate in (resolved, *resolved.parents):
            if self.budget is not None:
                self.budget.check_deadline(candidate, phase=self.phase)
            item = self.exact.get(_path_key(candidate))
            if item is not None:
                return str(item[1].get("lifecycle") or "UNKNOWN").upper()
        return None


def _rel_path(path: Path) -> str:
    try:
        return str(_absolute_path(path).relative_to(_absolute_path(WORK_ROOT))).replace("\\", "/")
    except ValueError:
        return str(_absolute_path(path))


def _normalized_physical_path(path: Path) -> str:
    """Return a case/separator-normalized absolute path for stable IDs."""

    resolved = Path(path).expanduser().resolve()
    return os.path.normcase(str(resolved)).replace("\\", "/")


def _stable_path_artifact_id(prefix: str, path: Path) -> str:
    """Namespace an artifact ID by its physical path without migrating history.

    The digest prevents collisions between worktrees while the readable path
    namespace keeps the registry entry auditable.  ``register_artifact`` still
    owns the strict ID-to-path guard for every registration.
    """

    normalized = _normalized_physical_path(path)
    digest = hashlib.sha256(normalized.encode("utf-8", "surrogatepass")).hexdigest()
    namespace = normalized.replace(":", "").replace("/", "_")
    return f"{prefix}:pathns:{digest}:{namespace}"


def _legacy_disposable_paths() -> set[str]:
    """Return the explicitly audited pre-registry allowlist.

    These entries are migration-only.  New tests must register their output
    with lifecycle=DISPOSABLE instead of relying on names or age.
    """

    paths = set(DELETE_DIR_NAMES) | set(EXTRA_DELETE_PATHS)
    for pattern in EXTRA_DELETE_GLOBS:
        for path in WORK_ROOT.glob(pattern):
            paths.add(_rel_path(path))
    return paths


def _is_explicit_keep(path: Path) -> bool:
    rel = _rel_path(path)
    if rel == "game_copy" or rel.startswith("game_copy/"):
        return True
    if rel in KEEP_PATHS:
        return True
    return any(rel.startswith(item.rstrip("/") + "/") for item in KEEP_PATHS)


def snapshot_tree(
    root: Path = WORK_ROOT,
    *,
    include_protected: bool = False,
    budget: InventoryBudget | None = None,
    include_hashes: bool = True,
    skip_retained: bool = False,
) -> dict:
    """Return a recursive, non-mutating inventory with cheap file signatures.

    Protected canonical game data is represented by its root only.  This keeps
    every runner bounded on the multi-gigabyte fixture while still detecting
    unregistered nested output in normal test scopes.
    """

    budget = _new_inventory_budget(budget)
    root = _absolute_path(Path(root).expanduser())
    root_abs = os.path.abspath(os.fspath(root))
    root_text = os.path.normcase(root_abs)
    result: dict[str, dict] = {}
    errors: list[dict] = []
    if not root.exists():
        return {
            "root": str(root),
            "items": result,
            "errors": errors,
            "complete": True,
            "inventory": budget.report(),
        }
    pending = [root]
    while pending:
        current = pending.pop()
        try:
            budget.check(current)
            if not current.is_dir():
                continue
            entries = os.scandir(current)
        except (InventoryFailure, OSError) as exc:
            errors.append(_inventory_error(current, exc))
            if isinstance(exc, InventoryFailure):
                break
            continue
        try:
            with entries:
                for entry in entries:
                    child = Path(entry.path)
                    try:
                        budget.check(child)
                        # ``os.scandir`` is rooted at an absolute path here;
                        # keep the lexical entry path instead of resolving it
                        # through the Windows filesystem for every item.
                        resolved = child
                        stat = entry.stat(follow_symlinks=False)
                        if entry.is_symlink():
                            kind = "symlink"
                        elif entry.is_dir(follow_symlinks=False):
                            kind = "directory"
                        else:
                            kind = "file"
                        resolved_abs = os.fspath(resolved)
                        resolved_text = os.path.normcase(resolved_abs)
                        root_prefix = root_text.rstrip("\\/") + os.sep
                        if resolved_text == root_text:
                            rel = ""
                        elif resolved_text.startswith(root_prefix):
                            rel = resolved_abs[len(root_abs.rstrip("\\/")) + 1 :].replace("\\", "/")
                        else:
                            raise ValueError(f"inventory entry escaped root: {resolved}")
                        item = {
                            "path": str(resolved),
                            "relative_path": rel,
                            "kind": kind,
                            "bytes": int(stat.st_size) if kind == "file" else 0,
                            "mtime_ns": int(
                                getattr(stat, "st_mtime_ns", int(stat.st_mtime * 1_000_000_000))
                            ),
                        }
                        if (
                            include_hashes
                            and kind == "file"
                            and stat.st_size <= DEFAULT_HASH_MAX_BYTES
                            and budget.reserve_hash(stat.st_size)
                        ):
                            import hashlib

                            digest = hashlib.sha256()
                            with child.open("rb") as fh:
                                while True:
                                    # Hash blocks are work within one
                                    # filesystem item; they must consume the
                                    # shared deadline but not inflate the
                                    # item-count guard by file size.
                                    budget.check_deadline(child, phase="inventory_hash")
                                    block = fh.read(1024 * 1024)
                                    if not block:
                                        break
                                    digest.update(block)
                            item["sha256"] = digest.hexdigest()
                        result[rel] = item
                        protected = kind == "directory" and is_protected_path(resolved)
                        retained = kind == "directory" and _is_explicit_keep(resolved)
                        if kind == "directory" and (
                            include_protected
                            or (not protected and not (skip_retained and retained))
                        ):
                            pending.append(child)
                    except (InventoryFailure, OSError, ValueError) as exc:
                        errors.append(_inventory_error(child, exc))
                        if isinstance(exc, InventoryFailure):
                            break
        except OSError as exc:
            errors.append(_inventory_error(current, exc))
        if budget.failure:
            break
    return {
        "root": str(root),
        "items": result,
        "errors": errors,
        "complete": not errors and budget.failure is None,
        "inventory": budget.report(),
    }


def _report_inventory_snapshot(snapshot: dict | None) -> dict | None:
    """Keep inventory status and a stable digest, not every repeated path row."""

    if snapshot is None:
        return None
    report = dict(snapshot)
    for name in ("items", "root_inventory"):
        values = report.pop(name, None)
        if not isinstance(values, (dict, list)):
            if values is not None:
                report[name] = values
            continue
        digest = hashlib.sha256()
        if isinstance(values, dict):
            rows = ((key, values[key]) for key in sorted(values))
            count = len(values)
            for key, value in rows:
                payload = json.dumps(
                    [key, value], ensure_ascii=False, sort_keys=True, separators=(",", ":")
                ).encode("utf-8")
                digest.update(len(payload).to_bytes(8, "big"))
                digest.update(payload)
        else:
            count = len(values)
            for index, value in enumerate(values):
                payload = json.dumps(
                    [index, value], ensure_ascii=False, sort_keys=True, separators=(",", ":")
                ).encode("utf-8")
                digest.update(len(payload).to_bytes(8, "big"))
                digest.update(payload)
        report[f"{name}_count"] = count
        report[f"{name}_sha256"] = digest.hexdigest().upper()
        report[f"{name}_omitted"] = True
    return report


def _compact_report_records(report: dict, names: tuple[str, ...]) -> None:
    """Bound duplicated registry rows in reports; the canonical registry keeps full records."""

    for name in names:
        records = report.get(name)
        if not isinstance(records, list) or len(records) <= REPORT_INLINE_RECORD_LIMIT:
            continue
        digest = hashlib.sha256()
        for record in records:
            payload = json.dumps(
                record, ensure_ascii=False, sort_keys=True, separators=(",", ":")
            ).encode("utf-8")
            digest.update(len(payload).to_bytes(8, "big"))
            digest.update(payload)
        report[name] = records[:REPORT_INLINE_RECORD_LIMIT]
        report[f"{name}_summary"] = {
            "count": len(records),
            "sha256": digest.hexdigest().upper(),
            "included": REPORT_INLINE_RECORD_LIMIT,
            "omitted": True,
        }


def scan_root_inventory(
    *,
    recursive: bool = True,
    budget: InventoryBudget | None = None,
    snapshot: dict | None = None,
) -> list[dict]:
    """Inventory _work, including nested paths, without mutation."""

    if not WORK_ROOT.is_dir():
        return []
    if recursive:
        snap = snapshot or snapshot_tree(WORK_ROOT, budget=budget)
        return [snap["items"][key] for key in sorted(snap["items"])]
    output: list[dict] = []
    budget = _new_inventory_budget(budget)
    for path in sorted(WORK_ROOT.iterdir(), key=lambda item: item.name.lower()):
        budget.check(path)
        output.append(
            {
                "path": str(path.resolve()),
                "relative_path": _rel_path(path),
                "kind": "directory" if path.is_dir() else "file",
                "bytes": _bounded_dir_size(path, budget),
            }
        )
    return output


def _reconcile_registry_impl(
    *,
    persist: bool = False,
    budget: InventoryBudget | None = None,
    inventory: dict | None = None,
    measure_sizes: bool = False,
) -> dict:
    """Reconcile registry entries and root artifacts without guessing deletes."""

    from work_paths import lifecycle_for_entry, _save_manifest

    budget = _new_inventory_budget(budget)
    inventory_snapshot = inventory or snapshot_tree(
        WORK_ROOT,
        budget=budget,
        include_hashes=False,
        skip_retained=True,
    )
    inventory_errors = list(inventory_snapshot.get("errors") or [])
    manifest, _raw_manifest, registry_errors = _strict_registry_snapshot()
    entries_value = manifest.get("artifacts")
    entries = entries_value if isinstance(entries_value, list) else []
    by_path: dict[str, dict] = {}
    normalized: list[dict] = []
    updates: list[dict] = []
    seen_ids: set[str] = set()
    metadata_issues: list[dict] = [
        {"path": str(MANIFEST_PATH), "reason": reason} for reason in registry_errors
    ]
    if not isinstance(entries_value, list):
        metadata_issues.append({"path": str(MANIFEST_PATH), "reason": "registry_artifacts_not_a_list"})
    if "archive" in manifest and not isinstance(manifest.get("archive"), list):
        metadata_issues.append({"path": str(MANIFEST_PATH), "reason": "registry_archive_not_a_list"})
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            metadata_issues.append({"path": str(MANIFEST_PATH), "index": index, "reason": "registry_entry_not_an_object"})
            continue
        budget.check_deadline(Path(str(entry.get("path") or "<missing-path>")), phase="reconciliation")
        item = dict(entry)
        artifact_id = str(item.get("id") or "").strip()
        if not artifact_id:
            metadata_issues.append({"path": str(MANIFEST_PATH), "index": index, "reason": "registry_entry_missing_id"})
        elif artifact_id in seen_ids:
            metadata_issues.append({"id": artifact_id, "path": item.get("path"), "index": index, "reason": "registry_entry_duplicate_id"})
        else:
            seen_ids.add(artifact_id)
        raw_lifecycle = str(item.get("lifecycle") or "").upper().strip()
        if raw_lifecycle and raw_lifecycle not in LIFECYCLE_STATES:
            metadata_issues.append({"id": artifact_id or None, "path": item.get("path"), "reason": "registry_entry_invalid_lifecycle"})
            lifecycle = "UNKNOWN"
        else:
            lifecycle = lifecycle_for_entry(item)
        try:
            path = _entry_path(item)
        except (KeyError, TypeError, ValueError, OSError) as exc:
            metadata_issues.append({"id": item.get("id"), "path": item.get("path"), "reason": "registered_claim_path_invalid", "error": str(exc)})
            continue
        try:
            exists = os.path.lexists(path)
        except (OSError, ValueError) as exc:
            metadata_issues.append({"id": item.get("id"), "path": str(path), "reason": "registered_claim_stat_failed", "error": str(exc)})
            continue
        if path == _absolute_path(MANIFEST_PATH):
            # The registry is itself a retained control-plane artifact.  An
            # older cleanup run may have recorded it as inventory UNKNOWN;
            # normalize that legacy state instead of reporting the registry
            # as an unregistered output on every subsequent dry-run.
            lifecycle = "RETAINED"
            item["owner"] = str(item.get("owner") or "cleanup_work_artifacts.py")
            item["purpose"] = str(item.get("purpose") or "artifact lifecycle registry")
        if not exists and lifecycle in {"PROTECTED", "RETAINED", "DISPOSABLE", "UNKNOWN"}:
            lifecycle = "MISSING"
        if exists and _path_is_under(path, WORK_ROOT) and _is_explicit_keep(path):
            lifecycle = "PROTECTED" if _rel_path(path) == "game_copy" or _rel_path(path).startswith("game_copy/") else lifecycle
        item["lifecycle"] = lifecycle
        item["status"] = "ACTIVE" if lifecycle in {"PROTECTED", "RETAINED", "DISPOSABLE", "UNKNOWN"} else lifecycle
        if not str(item.get("owner") or "").strip():
            metadata_issues.append({"id": item.get("id"), "path": str(path), "reason": "missing_owner"})
        if not str(item.get("purpose") or "").strip():
            metadata_issues.append({"id": item.get("id"), "path": str(path), "reason": "missing_purpose"})
        item["owner"] = str(item.get("owner") or item.get("created_by") or "unknown")
        item["purpose"] = str(item.get("purpose") or "unclassified artifact; manual review required")
        ambient = {
            "scope_id": str(item.get("scope_id") or "legacy"),
            "run_id": str(item.get("run_id") or item.get("scope_id") or "legacy"),
            "scope_root": str(item.get("scope_root") or WORK_ROOT.resolve()),
        }
        item.setdefault("scope_id", ambient["scope_id"])
        item.setdefault("run_id", ambient["run_id"])
        item.setdefault("scope_root", ambient["scope_root"])
        if not isinstance(item.get("provenance"), dict):
            metadata_issues.append({"id": item.get("id"), "path": str(path), "reason": "missing_provenance"})
            item["provenance"] = {
                "scope_id": item["scope_id"],
                "run_id": item["run_id"],
                "scope_root": item["scope_root"],
                "registered_by": str(item.get("created_by") or "cleanup_work_artifacts.py"),
            }
        if exists and not measure_sizes and path.is_file() and not budget.failure:
            try:
                budget.check(path)
                item["bytes"] = int(path.stat().st_size)
            except (InventoryFailure, OSError) as exc:
                inventory_errors.append(_inventory_error(path, exc))
        elif exists and measure_sizes and not budget.failure:
            try:
                item["bytes"] = _bounded_dir_size(path, budget)
            except (InventoryFailure, OSError) as exc:
                inventory_errors.append(_inventory_error(path, exc))
        normalized.append(item)
        if _path_is_under(path, WORK_ROOT):
            by_path[str(path)] = item
        if item.get("lifecycle") != lifecycle_for_entry(entry) or item.get("bytes") != entry.get("bytes"):
            updates.append({"id": item.get("id"), "path": str(path), "lifecycle": lifecycle})

    metadata_bad_ids = {str(item.get("id")) for item in metadata_issues if item.get("id")}
    for item in normalized:
        if str(item.get("id")) in metadata_bad_ids:
            item["lifecycle"] = "UNKNOWN"
            item["status"] = "ACTIVE"

    registered_relative_paths: set[str] = set()
    for entry in normalized:
        budget.check_deadline(Path(str(entry.get("path") or "<missing-path>")), phase="reconciliation")
        if not entry.get("path"):
            continue
        entry_path = _entry_path(entry)
        if _path_is_under(entry_path, WORK_ROOT):
            registered_relative_paths.add(_rel_path(entry_path).rstrip("/"))

    unknown: list[dict] = []
    known_roots: set[str] = set()
    root_inventory = [
        inventory_snapshot["items"][key]
        for key in sorted(inventory_snapshot.get("items") or {})
    ]
    manifest_path = _absolute_path(MANIFEST_PATH)
    work_root = _absolute_path(WORK_ROOT)
    for path in root_inventory:
        budget.check_deadline(Path(str(path.get("path") or WORK_ROOT)), phase="reconciliation")
        root_rel = path["relative_path"]
        root_path = _absolute_path(WORK_ROOT / root_rel)
        root_key = str(root_path)
        if root_key == str(manifest_path):
            known_roots.add(root_rel)
            continue
        if root_key in by_path:
            known_roots.add(root_rel)
            continue
        covered = False
        parts = root_rel.split("/")
        for index in range(len(parts), 0, -1):
            if "/".join(parts[:index]) in registered_relative_paths:
                covered = True
                break
        if covered:
            known_roots.add(root_rel)
            continue
        protected_root = root_rel == "game_copy" or root_rel.startswith("game_copy/")
        retained_root = _is_explicit_keep(root_path)
        unknown.append(
            {
                "id": f"inventory:{root_rel}",
                "path": str(root_path),
                "relative_path": root_rel,
                "kind": path["kind"],
                "owner": "unknown",
                "purpose": "canonical game fixture" if protected_root else ("explicit retained registry/report path" if retained_root else "unregistered root artifact; manual review required"),
                "lifecycle": "PROTECTED" if protected_root else ("RETAINED" if retained_root else "UNKNOWN"),
                "status": "ACTIVE",
                "bytes": path["bytes"],
                "scope_id": "inventory",
                "run_id": "inventory",
                "scope_root": str(work_root),
                "provenance": {
                    "scope_id": "inventory",
                    "run_id": "inventory",
                    "scope_root": str(work_root),
                    "registered_by": "cleanup_work_artifacts.py",
                },
            }
        )

    inventory_complete = bool(
        inventory_snapshot.get("complete", True)
        and not inventory_errors
        and budget.failure is None
    )
    if persist and inventory_complete and not metadata_issues:
        manifest["version"] = 2
        manifest["schema_version"] = 2
        manifest["artifacts"] = normalized + [item for item in unknown if item["id"] not in {x.get("id") for x in normalized}]
        _save_manifest(manifest)
    return {
        "manifest": manifest,
        "entries": normalized,
        "unknown": unknown,
        "updates": updates,
        "metadata_issues": metadata_issues,
        "root_inventory": root_inventory,
        "inventory": inventory_snapshot,
        "inventory_complete": inventory_complete,
        "inventory_errors": inventory_errors,
    }


def _incomplete_reconciliation(inventory: dict, budget: InventoryBudget) -> dict:
    """Return a non-mutating registry view after a bounded failure."""

    from work_paths import _load_manifest

    try:
        manifest = _load_manifest()
        registry_read_error = None
    except (OSError, ValueError) as exc:
        manifest = {}
        registry_read_error = str(exc)
    if not isinstance(manifest, dict):
        manifest = {}
    raw_entries = manifest.get("artifacts", [])
    entries = [dict(item) for item in raw_entries if isinstance(item, dict)] if isinstance(raw_entries, list) else []
    failure = dict(budget.failure or {
        "status": "ERROR",
        "reason": "reconciliation_incomplete",
    })
    return {
        "manifest": manifest,
        "entries": entries,
        "unknown": [],
        "updates": [],
        "metadata_issues": (
            [{"path": str(MANIFEST_PATH), "reason": "registry_artifacts_not_a_list"}]
            if not isinstance(raw_entries, list)
            else ([{"path": str(MANIFEST_PATH), "reason": "registry_manifest_invalid", "error": registry_read_error}] if registry_read_error else [])
        ),
        "root_inventory": [
            inventory.get("items", {}).get(key)
            for key in sorted(inventory.get("items", {}))
            if inventory.get("items", {}).get(key) is not None
        ],
        "inventory": inventory,
        "inventory_complete": False,
        "inventory_errors": [failure],
    }


def reconcile_registry(
    *,
    persist: bool = False,
    budget: InventoryBudget | None = None,
    inventory: dict | None = None,
    measure_sizes: bool = False,
) -> dict:
    """Reconcile the registry and return a terminal bounded failure view."""

    budget = _new_inventory_budget(budget)
    try:
        return _reconcile_registry_impl(
            persist=persist,
            budget=budget,
            inventory=inventory,
            measure_sizes=measure_sizes,
        )
    except InventoryFailure:
        snapshot = inventory or {
            "root": str(WORK_ROOT),
            "items": {},
            "errors": [],
            "complete": False,
            "inventory": budget.report(),
        }
        return _incomplete_reconciliation(snapshot, budget)


def _candidate_entries(reconciled: dict, *, registered_only: bool = False) -> list[dict]:
    candidates: dict[str, dict] = {}
    for entry in reconciled["entries"]:
        if entry.get("lifecycle") == "DISPOSABLE":
            if not entry.get("path"):
                continue
            try:
                path = _entry_path(entry)
            except (KeyError, TypeError, ValueError, OSError):
                continue
            if os.path.lexists(path):
                candidates[str(path)] = {"path": path, "id": entry.get("id"), "reason": "registered_disposable"}
    if not registered_only:
        # Migration allowlist is explicit and path-based; no wildcard age/name
        # inference is allowed for new artifacts.
        for rel in _legacy_disposable_paths():
            path = (WORK_ROOT / rel).resolve()
            if path.exists():
                candidates.setdefault(str(path), {"path": path, "id": f"legacy:{rel}", "reason": "audited_legacy_allowlist"})
    return sorted(candidates.values(), key=lambda item: str(item["path"]))


def consolidate_evidence() -> list[str]:
    """Copy explicitly named reports into the retained evidence directory."""
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    copied = []
    sources = [
        WORK_ROOT / "reports" / "summary.json",
        WORK_ROOT / "reports" / "coverage.json",
        WORK_ROOT / "reports" / "fingerprint.json",
        WORK_ROOT / "reports" / "verification.json",
        WORK_ROOT / "reports" / "import_report.txt",
    ]
    for src in sources:
        if not src.is_file():
            continue
        dest = EVIDENCE / src.name
        if src.resolve() != dest.resolve():
            shutil.copy2(src, dest)
            copied.append(str(dest))
    # Keep at most eight explicitly produced screenshots, if any exist.
    probe = WORK_ROOT / "screenshots"
    shot_dir = EVIDENCE / "screenshots"
    shot_dir.mkdir(exist_ok=True)
    if probe.is_dir():
        for src in sorted(probe.glob("*.png"))[:8]:
            if src.is_file():
                shutil.copy2(src, shot_dir / src.name)
                copied.append(str(shot_dir / src.name))
    (EVIDENCE / "README.txt").write_text(
        "Evidence kept after workspace cleanup.\n"
        "Reports and representative screenshots are retained only when explicitly supplied.\n",
        encoding="utf-8",
    )
    register_artifact(
        artifact_id="retained_evidence",
        path=EVIDENCE,
        kind="evidence",
        created_by="cleanup_work_artifacts.py",
        purpose="Retained evidence after cleanup",
        status="ACTIVE",
    )
    return copied


def _size_snapshot(
    *,
    budget: InventoryBudget | None = None,
    timeout_seconds: float | None = None,
    max_items: int | None = None,
    inventory: dict | None = None,
) -> dict:
    """Build a size snapshot without creating a report file."""

    budget = _new_inventory_budget(
        budget,
        timeout_seconds=timeout_seconds,
        max_items=max_items,
    )
    # Cleanup owns _work, not the whole development checkout.  Scanning ROOT
    # here used to recurse through the entire historical workspace before the
    # registry could even be reconciled.  Keep the dev-root field for schema
    # compatibility, but make its intentionally unscanned state explicit.
    dev_total = {
        "path": str(ROOT),
        "bytes": None,
        "gb": None,
        "children": [],
        "complete": False,
        "status": "NOT_SCANNED",
        "reason": "cleanup_scope_is_work_root",
    }
    if inventory is None:
        work = size_tree(WORK_ROOT, depth=0, budget=budget, skip_retained=True)
    else:
        total = sum(
            int(item.get("bytes") or 0)
            for item in (inventory.get("items") or {}).values()
            if item.get("kind") == "file"
        )
        work = {
            "path": str(WORK_ROOT),
            "bytes": total,
            "gb": human_gb(total),
            "children": [],
            "complete": bool(inventory.get("complete", False)),
            "inventory": inventory.get("inventory") or budget.report(),
        }
        if inventory.get("errors"):
            work["errors"] = list(inventory["errors"])
    return {
        "utc": utc_now(),
        "dev_root": str(ROOT),
        "work_root": str(WORK_ROOT),
        "dev_total_gb": None,
        "work_total_gb": work["gb"] if work.get("complete") else None,
        "work": work,
        "inventory": budget.report(),
    }


_LIFECYCLE_STATES = ("PROTECTED", "RETAINED", "DISPOSABLE", "UNKNOWN", "MISSING", "STALE")


def _snapshot_lifecycle_metrics(
    snapshot: dict | None,
    reconciled: dict | None,
    *,
    budget: InventoryBudget | None = None,
) -> dict:
    """Return bounded, machine-readable size/lifecycle evidence for a snapshot.

    File bytes come from the actual inventory, while registry counts also
    include MISSING/STALE entries that are intentionally absent from that
    inventory.  Duplicate bytes are measured only for files with an exact
    bounded SHA-256 signature; un-hashed large files are not guessed.
    """

    snapshot = snapshot or {}
    items = snapshot.get("items") or {}
    entries: list[dict] = []
    if reconciled:
        entries.extend(item for item in reconciled.get("entries", []) if isinstance(item, dict))
        entries.extend(item for item in reconciled.get("unknown", []) if isinstance(item, dict))

    resolved_entries: list[tuple[Path, str, dict]] = []
    for entry in entries:
        if budget is not None:
            budget.check_deadline(
                Path(str(entry.get("path") or "<missing-path>")),
                phase="lifecycle_metrics",
            )
        try:
            entry_path = _entry_path(entry)
        except (KeyError, TypeError, ValueError, OSError):
            continue
        lifecycle = str(entry.get("lifecycle") or "UNKNOWN").upper()
        if lifecycle not in _LIFECYCLE_STATES:
            lifecycle = "UNKNOWN"
        resolved_entries.append((entry_path, lifecycle, entry))
    entry_index = _PathEntryIndex(entries, budget=budget, phase="lifecycle_metrics")

    def lifecycle_for(path: Path) -> str:
        resolved = _absolute_path(path)
        if budget is not None:
            budget.check_deadline(path, phase="lifecycle_metrics")
        lifecycle = entry_index.lifecycle_for(path)
        if lifecycle in _LIFECYCLE_STATES:
            return lifecycle
        try:
            relative = _rel_path(resolved)
        except (OSError, ValueError):
            relative = ""
        if relative == "game_copy" or relative.startswith("game_copy/"):
            return "PROTECTED"
        if relative in KEEP_PATHS or any(
            relative.startswith(str(keep).rstrip("/") + "/") for keep in KEEP_PATHS
        ):
            return "RETAINED"
        return "UNKNOWN"

    files_by = {state: 0 for state in _LIFECYCLE_STATES}
    dirs_by = {state: 0 for state in _LIFECYCLE_STATES}
    bytes_by = {state: 0 for state in _LIFECYCLE_STATES}
    duplicate_groups: dict[tuple[str, int], list[tuple[str, str]]] = {}
    hashed_files = 0
    total_files = 0
    total_dirs = 0
    total_bytes = 0
    for item in items.values():
        if not isinstance(item, dict):
            continue
        if budget is not None:
            budget.check_deadline(Path(str(item.get("path") or WORK_ROOT)), phase="lifecycle_metrics")
        kind = str(item.get("kind") or "")
        path = Path(str(item.get("path") or ""))
        lifecycle = lifecycle_for(path)
        if kind == "file":
            total_files += 1
            size = max(0, int(item.get("bytes") or 0))
            total_bytes += size
            files_by[lifecycle] += 1
            bytes_by[lifecycle] += size
            digest = str(item.get("sha256") or "")
            if digest:
                hashed_files += 1
                duplicate_groups.setdefault((digest, size), []).append(
                    (str(path), lifecycle)
                )
        elif kind == "directory":
            total_dirs += 1
            dirs_by[lifecycle] += 1

    duplicate_group_count = 0
    duplicate_bytes = 0
    for (_digest, size), files in duplicate_groups.items():
        if len(files) > 1:
            duplicate_group_count += 1
            duplicate_bytes += size * (len(files) - 1)

    registry_counts = {state: 0 for state in _LIFECYCLE_STATES}
    registry_bytes = {state: 0 for state in _LIFECYCLE_STATES}
    registry_status_counts: dict[str, int] = {}
    for _path, lifecycle, entry in resolved_entries:
        registry_counts[lifecycle] += 1
        status = str(entry.get("status") or "ACTIVE").upper()
        registry_status_counts[status] = registry_status_counts.get(status, 0) + 1
        try:
            registry_bytes[lifecycle] += max(0, int(entry.get("bytes") or 0))
        except (TypeError, ValueError):
            pass
    missing_entries = [entry for _path, lifecycle, entry in resolved_entries if lifecycle == "MISSING"]
    expected_missing, unexpected_missing = _split_missing(missing_entries)
    unresolved_registry_counts = {
        "UNKNOWN": registry_counts["UNKNOWN"],
        "MISSING": len(unexpected_missing),
        "STALE": registry_counts["STALE"],
    }

    archived_counts: dict[str, int] = {}
    if reconciled and isinstance(reconciled.get("manifest"), dict):
        for item in reconciled["manifest"].get("archive", []) or []:
            if not isinstance(item, dict):
                continue
            state = str(item.get("lifecycle_before_archive") or item.get("lifecycle") or "UNKNOWN").upper()
            archived_counts[state] = archived_counts.get(state, 0) + 1

    return {
        "file_count": total_files,
        "directory_count": total_dirs,
        "total_bytes": total_bytes,
        "bytes_by_lifecycle": bytes_by,
        "file_count_by_lifecycle": files_by,
        "directory_count_by_lifecycle": dirs_by,
        "disposable_bytes": bytes_by["DISPOSABLE"],
        "retained_bytes": bytes_by["RETAINED"],
        "protected_bytes": bytes_by["PROTECTED"],
        "unknown_bytes": bytes_by["UNKNOWN"],
        "registry_counts": registry_counts,
        "expected_missing_count": len(expected_missing),
        "unexpected_missing_count": len(unexpected_missing),
        "unresolved_registry_counts": unresolved_registry_counts,
        "registry_status_counts": registry_status_counts,
        "archived_registry_counts": archived_counts,
        "archived_registry_count": sum(archived_counts.values()),
        "active_registry_count": registry_status_counts.get("ACTIVE", 0),
        "registry_bytes_by_lifecycle": registry_bytes,
        "duplicate_measurement": {
            "status": "MEASURED_BOUNDED" if hashed_files else "NOT_MEASURED",
            "hashed_file_count": hashed_files,
            "duplicate_groups": duplicate_group_count,
            "duplicate_bytes": duplicate_bytes,
            "scope": "exact sha256 and size only; large/unhashed files excluded",
        },
        "inventory_complete": bool(snapshot.get("complete", True)),
        "locked_count": 0,
    }


def _entry_for_path(entries: list[dict], path: Path) -> dict | None:
    key = _path_key(path)
    for entry in entries:
        try:
            if _path_key(_entry_path(entry)) == key:
                return entry
        except (KeyError, TypeError, ValueError, OSError):
            continue
    return None


def _state_groups(entries: list[dict], unknown: list[dict]) -> dict[str, list[dict]]:
    groups = {state: [] for state in ("PROTECTED", "RETAINED", "DISPOSABLE", "UNKNOWN", "MISSING", "STALE")}
    for entry in entries + unknown:
        groups.setdefault(str(entry.get("lifecycle") or "UNKNOWN"), []).append(entry)
    return groups


_DELETION_PROVENANCE_FIELDS = {
    "schema_version",
    "deleted_at",
    "deleted_by",
    "reason",
    "path",
    "scope_id",
    "run_id",
    "scope_root",
    "evidence_source",
    "result",
}


def _valid_deletion_provenance(entry: dict) -> bool:
    proof = entry.get("deletion_provenance")
    if not isinstance(proof, dict) or not _DELETION_PROVENANCE_FIELDS.issubset(proof):
        return False
    if any(not str(proof.get(field) or "").strip() for field in _DELETION_PROVENANCE_FIELDS - {"schema_version"}):
        return False
    try:
        return _path_key(Path(str(proof["path"]))) == _path_key(_entry_path(entry))
    except (KeyError, TypeError, ValueError, OSError):
        return False


def _split_missing(entries: list[dict]) -> tuple[list[dict], list[dict]]:
    expected: list[dict] = []
    unexpected: list[dict] = []
    for entry in entries:
        (expected if _valid_deletion_provenance(entry) else unexpected).append(entry)
    return expected, unexpected


def _proof_from_deleted_record(
    record: dict,
    *,
    entry: dict | None = None,
    deleted_by: str,
    evidence_source: str,
) -> dict:
    path = _entry_path(entry) if entry is not None else Path(str(record["path"]))
    return make_deletion_provenance(
        path=path,
        reason=str(record.get("reason") or "registered artifact cleanup"),
        deleted_by=deleted_by,
        deleted_at=str(record.get("deleted_at") or utc_now()),
        bytes_deleted=int(record.get("bytes") or 0),
        evidence_source=evidence_source,
        scope_id=str((entry or {}).get("scope_id") or ambient_scope()["scope_id"]),
        run_id=str((entry or {}).get("run_id") or ambient_scope()["run_id"]),
        scope_root=str((entry or {}).get("scope_root") or ambient_scope()["scope_root"]),
        deletion_result=str(record.get("deletion_result") or "deleted"),
    )


def backfill_missing_deletion_provenance(*, dry_run: bool = True) -> dict:
    """Attach primary historical deletion proof without hiding registry history."""

    from work_paths import _load_manifest, _save_manifest

    manifest = _load_manifest()
    history_path = WORK_ROOT / "cleanup_post_test.jsonl"
    history_by_path: dict[str, dict] = {}
    history_errors: list[dict] = []
    if history_path.is_file():
        for line_number, raw in enumerate(history_path.read_text(encoding="utf-8").splitlines(), start=1):
            if not raw.strip():
                continue
            try:
                event = json.loads(raw)
            except json.JSONDecodeError as exc:
                history_errors.append({"line": line_number, "error": str(exc)})
                continue
            for deletion in event.get("deleted") or []:
                if not isinstance(deletion, dict) or not deletion.get("deleted") or not deletion.get("path"):
                    continue
                record = dict(deletion)
                record.setdefault("deleted_at", event.get("utc"))
                record.setdefault("reason", event.get("reason"))
                history_by_path[_path_key(Path(str(record["path"])))] = record

    plans: list[dict] = []
    unresolved: list[dict] = []
    for entry in manifest.get("artifacts", []) or []:
        if str(entry.get("lifecycle") or "").upper() != "MISSING" or _valid_deletion_provenance(entry):
            continue
        try:
            entry_path = _entry_path(entry)
        except (KeyError, TypeError, ValueError, OSError) as exc:
            unresolved.append({"id": entry.get("id"), "path": entry.get("path"), "reason": f"invalid_path:{exc}"})
            continue
        record = history_by_path.get(_path_key(entry_path))
        if record is not None:
            proof = _proof_from_deleted_record(
                record,
                entry=entry,
                deleted_by="cleanup_after_test",
                evidence_source="cleanup_post_test.jsonl",
            )
        elif str(entry.get("id") or "") == "e2e_game_copy" and _path_key(entry_path) == _path_key(E2E_GAME_COPY):
            proof = make_deletion_provenance(
                path=entry_path,
                reason=str(entry.get("purpose") or "historical owner-controlled e2e disposal"),
                deleted_by="dispose_e2e_game_copy",
                deleted_at=str(entry.get("updated_at") or entry.get("created_at") or utc_now()),
                bytes_deleted=int(entry.get("bytes") or 0),
                evidence_source="historical_terminal_registry_record",
                scope_id=str(entry.get("scope_id") or "legacy"),
                run_id=str(entry.get("run_id") or "legacy"),
                scope_root=str(entry.get("scope_root") or WORK_ROOT),
                deletion_result="legacy_owner_confirmed_missing",
            )
        else:
            unresolved.append({"id": entry.get("id"), "path": str(entry_path), "reason": "no_primary_deletion_evidence"})
            continue
        plans.append({"id": entry.get("id"), "path": str(entry_path), "deletion_provenance": proof})

    if not dry_run and plans:
        by_id = {str(item["id"]): item for item in plans}
        for entry in manifest.get("artifacts", []) or []:
            plan = by_id.get(str(entry.get("id")))
            if plan is not None:
                entry["deletion_provenance"] = dict(plan["deletion_provenance"])
        _save_manifest(manifest)

    ok = not history_errors and not unresolved
    return {
        "schema_version": 1,
        "utc": utc_now(),
        "dry_run": bool(dry_run),
        "applied": not dry_run,
        "manifest_path": str(MANIFEST_PATH),
        "history_path": str(history_path),
        "planned_count": len(plans),
        "planned_records": plans,
        "unresolved_count": len(unresolved),
        "unresolved_records": unresolved,
        "history_errors": history_errors,
        "ok": ok,
        "status": "PASS" if ok else "REVIEW_REQUIRED",
    }


def _project_inventory_root() -> Path:
    """Nested canonical snapshots share their containing checkout's quota.

    This does not redirect ownership or deletion: WORK_ROOT remains local to
    the run. No environment variable can exempt a nested clone from its parent.
    """
    local = ROOT.resolve()
    inventory_root = local
    for parent in local.parents:
        relative = local.relative_to(parent).parts
        nested = relative[:1] == (".scratch",) or relative[:3] == ("tests", "golden", "_work")
        if nested and (parent / "tests/tools/cleanup_work_artifacts.py").is_file() and (parent / "tests/lib/work_paths.py").is_file():
            inventory_root = parent
    return inventory_root


def _project_size_snapshot(*, timeout_seconds: float = DEFAULT_INVENTORY_TIMEOUT_SECONDS,
                           max_items: int = DEFAULT_INVENTORY_MAX_ITEMS) -> dict:
    """Measure regular files only; links, special nodes and scan errors fail closed."""

    root = _project_inventory_root()
    budget = InventoryBudget(timeout_seconds=timeout_seconds, max_items=max_items)
    exclusions = {
        _path_key(root / relative.replace("/", os.sep)): (relative, reason)
        for relative, reason in PROJECT_SIZE_EXEMPTIONS.items()
    }
    exempt_bytes = {relative: 0 for relative in PROJECT_SIZE_EXEMPTIONS}
    project_bytes = 0
    stack = [(root, None)]
    errors: list[dict] = []
    while stack and not budget.failure:
        directory, inherited_exemption = stack.pop()
        try:
            with os.scandir(directory) as children:
                for child in children:
                    path = Path(child.path)
                    try:
                        budget.check(path)
                        info = child.stat(follow_symlinks=False)
                        attrs = int(getattr(info, "st_file_attributes", 0))
                        is_reparse = bool(attrs & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))
                        if stat.S_ISLNK(info.st_mode) or is_reparse:
                            errors.append({"path": str(path), "error": "link_or_reparse_point"})
                            continue
                        key = _path_key(path)
                        exemption = inherited_exemption or exclusions.get(key)
                        if stat.S_ISDIR(info.st_mode):
                            stack.append((path, exemption))
                            continue
                        if not stat.S_ISREG(info.st_mode):
                            errors.append({"path": str(path), "error": "unsupported_special_file"})
                            continue
                        size = int(info.st_size)
                        if exemption:
                            exempt_bytes[exemption[0]] += size
                        else:
                            project_bytes += size
                    except InventoryFailure as exc:
                        errors.append({
                            "path": str(exc.details.get("path") or path),
                            "error": str(exc.details.get("reason") or exc),
                        })
                        break
                    except OSError as exc:
                        errors.append({"path": str(path), "error": f"{type(exc).__name__}: {exc}"})
        except (InventoryFailure, OSError) as exc:
            details = getattr(exc, "details", {})
            errors.append({
                "path": str(details.get("path") or directory),
                "error": str(details.get("reason") or exc),
            })
    complete = not errors and budget.failure is None
    exemptions = []
    for relative, reason in PROJECT_SIZE_EXEMPTIONS.items():
        exempt_root = root / relative.replace("/", os.sep)
        if exempt_bytes[relative] or os.path.lexists(exempt_root):
            exemptions.append({"path": relative, "bytes": exempt_bytes[relative], "reason": reason})
    return {
        "root": str(root),
        "non_exempt_bytes": project_bytes if complete else None,
        "limit_bytes": PROJECT_SIZE_LIMIT_BYTES,
        "exempt_bytes": sum(exempt_bytes.values()) if complete else None,
        "exempt_limit_bytes": PROJECT_EXEMPT_SIZE_LIMIT_BYTES,
        "within_limit": complete and project_bytes <= PROJECT_SIZE_LIMIT_BYTES and sum(exempt_bytes.values()) <= PROJECT_EXEMPT_SIZE_LIMIT_BYTES,
        "complete": complete,
        "exemptions": exemptions,
        "inventory": budget.report(),
        "errors": errors[:REPORT_INLINE_RECORD_LIMIT],
    }


def _migration_source_sha() -> str:
    configured = str(os.environ.get("VNTEXT_SOURCE_SHA") or "").strip()
    if configured:
        return configured
    try:
        return subprocess.check_output(
            ["git", "-C", str(ROOT), "rev-parse", "HEAD"],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return "unavailable"


def _migration_default_field(value: object, *, field: str) -> bool:
    text = str(value or "").strip().casefold()
    if not text:
        return True
    if field == "owner":
        return text in {"unknown", "legacy", "cleanup_work_artifacts.py"} or text.startswith("legacy:")
    return (
        text in {"unknown", "legacy", "manual review required"}
        or "unclassified" in text
        or "manual review" in text
        or "legacy artifact" in text
    )


def _migration_preference(entry: dict) -> tuple[int, str, str]:
    default_fields = int(_migration_default_field(entry.get("owner"), field="owner"))
    default_fields += int(_migration_default_field(entry.get("purpose"), field="purpose"))
    # ISO timestamps sort oldest-first; missing metadata is least preferred.
    created = str(entry.get("created_at") or "9999-12-31T23:59:59Z")
    return default_fields, created, str(entry.get("id") or "")


def _archive_record(
    entry: dict,
    *,
    reason: str,
    source_sha: str,
    source_schema: object,
) -> dict:
    record = dict(entry)
    record.update(
        {
            "archive_id": f"{entry.get('id')}:{reason}",
            "archived_at": utc_now(),
            "archive_reason": reason,
            "migration_source_sha": source_sha,
            "migration_source_schema": source_schema,
            "lifecycle_before_archive": str(entry.get("lifecycle") or "UNKNOWN"),
            "status_before_archive": str(entry.get("status") or "ACTIVE"),
        }
    )
    return record


def migrate_registry(*, dry_run: bool = True, source_sha: str | None = None) -> dict:
    """Archive terminal/duplicate registry metadata without deleting files.

    MISSING/STALE entries are historical terminal records. UNKNOWN entries are
    only deduplicated when the same physical path has multiple registrations;
    a lone UNKNOWN remains live and unresolved.
    """

    from work_paths import _load_manifest, _save_manifest

    manifest = _load_manifest()
    artifacts = [dict(item) for item in manifest.get("artifacts", []) if isinstance(item, dict)]
    archive = [dict(item) for item in manifest.get("archive", []) if isinstance(item, dict)]
    source = str(source_sha or _migration_source_sha())
    source_schema = manifest.get("schema_version", manifest.get("version", "unknown"))
    existing_archive_keys = {
        (str(item.get("id") or ""), str(item.get("archive_reason") or ""))
        for item in archive
    }
    plans: list[dict] = []

    for entry in artifacts:
        lifecycle = str(entry.get("lifecycle") or entry.get("status") or "UNKNOWN").upper()
        if lifecycle in {"MISSING", "STALE"}:
            reason = f"historical_{lifecycle.casefold()}"
            plans.append(
                {
                    "entry": entry,
                    "reason": reason,
                    "archive_key": (str(entry.get("id") or ""), reason),
                }
            )

    unknown_by_path: dict[str, list[dict]] = {}
    for entry in artifacts:
        lifecycle = str(entry.get("lifecycle") or entry.get("status") or "UNKNOWN").upper()
        if lifecycle != "UNKNOWN":
            continue
        try:
            path = _entry_path(entry)
        except (KeyError, TypeError, ValueError, OSError):
            continue
        if not path.exists():
            continue
        unknown_by_path.setdefault(_path_key(path), []).append(entry)
    for path_key, entries in unknown_by_path.items():
        if len(entries) < 2:
            continue
        canonical = sorted(entries, key=_migration_preference)[0]
        for entry in entries:
            if str(entry.get("id")) == str(canonical.get("id")):
                continue
            plans.append(
                {
                    "entry": entry,
                    "reason": "duplicate_unknown_registration",
                    "canonical_id": canonical.get("id"),
                    "path_key": path_key,
                    "archive_key": (str(entry.get("id") or ""), "duplicate_unknown_registration"),
                }
            )

    planned_ids = {str(item["entry"].get("id") or "") for item in plans}
    simulated = [item for item in artifacts if str(item.get("id") or "") not in planned_ids]
    active_counts: dict[str, int] = {}
    for item in artifacts:
        state = str(item.get("lifecycle") or item.get("status") or "UNKNOWN").upper()
        active_counts[state] = active_counts.get(state, 0) + 1
    simulated_counts: dict[str, int] = {}
    for item in simulated:
        state = str(item.get("lifecycle") or item.get("status") or "UNKNOWN").upper()
        simulated_counts[state] = simulated_counts.get(state, 0) + 1

    archive_counts: dict[str, int] = {}
    planned_records = []
    for plan in plans:
        entry = plan["entry"]
        reason = str(plan["reason"])
        archive_counts[reason] = archive_counts.get(reason, 0) + 1
        planned_records.append(
            {
                "id": entry.get("id"),
                "path": entry.get("path"),
                "reason": reason,
                "canonical_id": plan.get("canonical_id"),
                "already_archived": plan["archive_key"] in existing_archive_keys,
            }
        )
    physical = {"existing": 0, "missing": 0, "invalid": 0}
    for entry in artifacts:
        try:
            physical["existing" if _entry_path(entry).exists() else "missing"] += 1
        except (KeyError, TypeError, ValueError, OSError):
            physical["invalid"] += 1
    live_unresolved = {
        state: count
        for state, count in simulated_counts.items()
        if state in {"UNKNOWN", "MISSING", "STALE"} and count
    }
    applied = not dry_run
    if applied and plans:
        for plan in plans:
            if plan["archive_key"] not in existing_archive_keys:
                archive.append(
                    _archive_record(
                        plan["entry"],
                        reason=str(plan["reason"]),
                        source_sha=source,
                        source_schema=source_schema,
                    )
                )
        manifest["artifacts"] = [item for item in artifacts if str(item.get("id") or "") not in planned_ids]
        manifest["archive"] = archive
        _save_manifest(manifest)

    return {
        "schema_version": 1,
        "utc": utc_now(),
        "dry_run": bool(dry_run),
        "applied": applied,
        "manifest_path": str(MANIFEST_PATH),
        "migration_source_sha": source,
        "migration_source_schema": source_schema,
        "planned_archive_count": len(plans),
        "planned_archive_records": planned_records,
        "archive_counts_by_reason": archive_counts,
        "existing_archive_count": len(archive),
        "active_counts_before": active_counts,
        "active_counts_after": simulated_counts,
        "live_unresolved": live_unresolved,
        "physical_inventory": physical,
        "ok": not bool(live_unresolved),
        "status": "PASS" if not live_unresolved else "REVIEW_REQUIRED",
    }


def _prospective_epoch_root() -> Path:
    return WORK_ROOT / "artifact-registry-epochs"


def _prospective_epoch_incident_path() -> Path:
    return WORK_ROOT / INCIDENT_SCOPE_ID / "artifacts_manifest.before-recovery.json"


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def _git_repository_state() -> dict:
    try:
        head = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True, stderr=subprocess.STDOUT
        ).strip()
        dirty = subprocess.check_output(
            ["git", "status", "--porcelain=v1"], cwd=ROOT, text=True, stderr=subprocess.STDOUT
        ).strip()
    except (OSError, subprocess.CalledProcessError) as exc:
        return {"head": "", "dirty": True, "error": str(exc)}
    return {"head": head, "dirty": bool(dirty), "error": ""}


def _prospective_epoch_writer_status() -> dict:
    lock = WORK_ROOT / ".artifact-registry-epoch.writer.lock"
    marker = str(os.environ.get("VNTEXT_ARTIFACT_REGISTRY_WRITER") or "").strip()
    return {
        "active": bool(marker or lock.exists()),
        "marker": marker,
        "lock_path": str(lock),
    }


def _valid_epoch_id(epoch_id: str) -> bool:
    return bool(epoch_id) and all(ch.isalnum() or ch in "-_" for ch in epoch_id) and len(epoch_id) <= 96


def _incident_identity() -> dict:
    path = _prospective_epoch_incident_path()
    if not os.path.lexists(path):
        return {"scope_id": INCIDENT_SCOPE_ID, "path": str(path), "status": "MISSING"}
    try:
        info = path.lstat()
        attributes = int(getattr(info, "st_file_attributes", 0))
        is_reparse = bool(attributes & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))
        if stat.S_ISLNK(info.st_mode) or is_reparse or not stat.S_ISREG(info.st_mode):
            return {"scope_id": INCIDENT_SCOPE_ID, "path": str(path), "status": "INVALID", "error": "incident_not_regular_file"}
        document = json.loads(path.read_text(encoding="utf-8"))
        count = len(document.get("artifacts") or [])
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, AttributeError, TypeError) as exc:
        return {"scope_id": INCIDENT_SCOPE_ID, "path": str(path), "status": "INVALID", "error": str(exc)}
    actual = _sha256_file(path)
    return {
        "scope_id": INCIDENT_SCOPE_ID,
        "path": str(path),
        "sha256": actual,
        "artifact_count": count,
        "expected_sha256": INCIDENT_REGISTRY_SHA256,
        "expected_artifact_count": INCIDENT_REGISTRY_COUNT,
        "status": "PASS" if actual == INCIDENT_REGISTRY_SHA256 and count == INCIDENT_REGISTRY_COUNT else "FAIL",
    }


def _epoch_scope_boundary() -> dict:
    return {
        "root": str(_absolute_path(WORK_ROOT)),
        "allowed_roots": [str(_absolute_path(WORK_ROOT))],
        "external_game_data": "excluded",
        "user_data": "excluded",
        "deletion": "forbidden",
    }


def _prospective_epoch_pending_reasons(manifest: dict, *, allow_pending_scope: Path | None = None) -> list[str]:
    """Detect interrupted or unregistered epoch transactions without writing."""

    root = _prospective_epoch_root()
    if not root.exists():
        return []
    if not root.is_dir():
        return ["prospective_epoch_root_not_directory"]
    active = manifest.get("prospective_epoch")
    active_id = str(active.get("epoch_id")) if isinstance(active, dict) else ""
    allowed = allow_pending_scope.resolve() if allow_pending_scope is not None else None
    reasons = []
    try:
        children = list(root.iterdir())
    except OSError as exc:
        return [f"prospective_epoch_root_unreadable:{type(exc).__name__}"]
    for child in children:
        if not child.is_dir() or child.is_symlink():
            reasons.append(f"unregistered_epoch_path:{child.name}")
            continue
        if child.name != active_id:
            reasons.append(f"unregistered_epoch_scope:{child.name}")
            continue
        if (child / ".pending.json").exists() and child.resolve() != allowed:
            reasons.append("prospective_epoch_transaction_pending")
    return reasons


def _atomic_write_bytes(path: Path, data: bytes) -> None:
    """Replace a control-plane file without exposing a truncated manifest."""

    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temp_path = Path(temp_name)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, path)
    finally:
        try:
            temp_path.unlink()
        except FileNotFoundError:
            pass


def _restore_manifest(raw_manifest: bytes | None) -> None:
    if raw_manifest is None:
        try:
            MANIFEST_PATH.unlink()
        except FileNotFoundError:
            pass
        return
    if not MANIFEST_PATH.is_file() or MANIFEST_PATH.read_bytes() != raw_manifest:
        _atomic_write_bytes(MANIFEST_PATH, raw_manifest)


def _remove_new_epoch_scope(scope: Path) -> None:
    root = _prospective_epoch_root().resolve()
    candidate = scope.resolve()
    if candidate.parent != root or candidate == root or candidate.is_symlink():
        raise RuntimeError(f"refusing transaction cleanup outside new epoch scope: {candidate}")
    if candidate.exists():
        shutil.rmtree(candidate)


def _epoch_acceptance_conditions() -> list[str]:
    return [
        "rollback snapshot exists and hash matches before canonical mutation",
        "the preserved incident matches its identity, or an authorized empty-state reset is recorded",
        "source SHA and clean tree are verified with no active registry writer",
        "bounded current inventory is complete and not budget-limited",
        "known items retain evidence-backed lifecycle; unproven items remain UNKNOWN",
        "apply performs no artifact deletion and rerun is idempotent",
        "historical registry identity remains NOT_RECOVERABLE/UNVERIFIABLE",
    ]


def _epoch_provenance(
    *, epoch_id: str, source_sha: str, effective_at: str,
    reset_provenance: dict | None = None,
) -> dict:
    provenance = {
        "policy_version": PROSPECTIVE_EPOCH_POLICY_VERSION,
        "schema_version": PROSPECTIVE_EPOCH_SCHEMA_VERSION,
        "epoch_id": epoch_id,
        "effective_at": effective_at,
        "source_sha": source_sha,
        "manifest_schema": {"version": 2, "schema_version": 2},
        "scope_boundary": _epoch_scope_boundary(),
        "original_incident_identity": _incident_identity(),
        "audit_identity": {
            "actor": "Codex",
            "component": "tests/tools/cleanup_work_artifacts.py",
            "audit_id": f"artifact-registry-audit:{epoch_id}",
        },
        "acceptance_conditions": _epoch_acceptance_conditions(),
        "historical_hygiene": "NOT_RECOVERABLE/UNVERIFIABLE",
        "historical_registry_identity": {
            "artifact_count": HISTORICAL_REGISTRY_COUNT,
            "sha256": HISTORICAL_REGISTRY_SHA256,
            "status": "NOT_RECOVERABLE/UNVERIFIABLE",
        },
        "no_deletion": True,
    }
    if reset_provenance is not None:
        provenance["reset_provenance"] = dict(reset_provenance)
    return provenance


def _epoch_manifest_shape(manifest: dict) -> list[str]:
    failures = []
    if manifest.get("version") != 2 or manifest.get("schema_version") != 2:
        failures.append("manifest_schema_must_be_2")
    if not isinstance(manifest.get("artifacts"), list) or not isinstance(manifest.get("archive", []), list):
        failures.append("manifest_artifacts_and_archive_must_be_lists")
    return failures


def _strict_registry_snapshot() -> tuple[dict, bytes | None, list[str]]:
    """Read the registry strictly and retain exact bytes for rollback checks."""

    if not os.path.lexists(MANIFEST_PATH):
        return {
            "version": 2,
            "schema_version": 2,
            "artifacts": [],
        }, None, []
    try:
        info = MANIFEST_PATH.lstat()
        attributes = int(getattr(info, "st_file_attributes", 0))
        is_reparse = bool(attributes & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))
        if stat.S_ISLNK(info.st_mode) or is_reparse or not stat.S_ISREG(info.st_mode):
            return {}, None, ["registry_manifest_not_regular_file"]
        raw = MANIFEST_PATH.read_bytes()
        manifest = json.loads(raw.decode("utf-8"))
        if not isinstance(manifest, dict):
            return {}, raw, ["registry_manifest_invalid"]
        return manifest, raw, []
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return {}, None, ["registry_manifest_invalid"]


def _classify_prospective_inventory(inventory: dict, reconciled: dict) -> list[dict]:
    entries = [item for item in reconciled.get("entries", []) if isinstance(item, dict)]
    index = _PathEntryIndex(entries)
    output = []
    for relative in sorted(inventory.get("items", {})):
        item = dict(inventory["items"][relative])
        path = _absolute_path(Path(str(item["path"])))
        matched = index.scoped_entry(path, allow_disposable_parent=True)
        if matched is not None:
            lifecycle = str(matched.get("lifecycle") or "UNKNOWN").upper()
            source = "registered"
            owner = str(matched.get("owner") or "unknown")
            purpose = str(matched.get("purpose") or "unclassified artifact; manual review required")
            artifact_id = matched.get("id")
            provenance = matched.get("provenance") if isinstance(matched.get("provenance"), dict) else None
        elif path == _absolute_path(E2E_GAME_COPY) or _path_is_under(path, E2E_GAME_COPY):
            lifecycle, source, owner, purpose = "PROTECTED", "protected_scope_rule", "cleanup_work_artifacts.py", "canonical game fixture"
            artifact_id, provenance = f"inventory:{relative}", None
        elif path == _absolute_path(MANIFEST_PATH) or _is_explicit_keep(path):
            lifecycle, source, owner, purpose = "RETAINED", "scope_rule", "cleanup_work_artifacts.py", "retained control-plane or evidence path"
            artifact_id, provenance = f"inventory:{relative}", None
        else:
            lifecycle, source, owner, purpose = "UNKNOWN", "unregistered_inventory", "unknown", "unregistered current artifact; manual review required"
            artifact_id, provenance = f"unknown:{relative}", None
        record = {
            "id": artifact_id,
            "path": str(path),
            "relative_path": relative,
            "kind": item.get("kind"),
            "bytes": int(item.get("bytes") or 0),
            "lifecycle": lifecycle,
            "status": "ACTIVE" if lifecycle in ACTIVE_LIFECYCLE_STATES else lifecycle,
            "classification_source": source,
            "owner": owner,
            "purpose": purpose,
        }
        if provenance is not None:
            record["provenance"] = provenance
        output.append(record)
    return output


def _epoch_verify_files(epoch: dict, *, manifest: dict | None = None) -> list[str]:
    failures = []
    manifest = manifest or json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    failures.extend(_epoch_manifest_shape(manifest))
    if epoch.get("status") != "ACTIVE":
        failures.append("prospective_epoch_not_active")
    if epoch.get("schema_version") != PROSPECTIVE_EPOCH_SCHEMA_VERSION:
        failures.append("epoch_schema_incomplete")
    for field in ("epoch_id", "effective_at", "source_sha", "scope_boundary", "original_incident_identity", "audit_identity", "acceptance_conditions"):
        if not epoch.get(field):
            failures.append(f"epoch_provenance_missing:{field}")
    rollback_value = epoch.get("rollback")
    rollback = rollback_value if isinstance(rollback_value, dict) else {}
    if not isinstance(rollback_value, dict):
        failures.append("rollback_record_invalid")
    rollback_path = Path(str(rollback.get("path") or ""))
    rollback_size = None
    if not rollback_path.is_file():
        failures.append("rollback_snapshot_missing")
    else:
        try:
            rollback_size = rollback_path.stat().st_size
            if _sha256_file(rollback_path) != str(rollback.get("sha256") or "").upper():
                failures.append("rollback_snapshot_hash_mismatch")
            if rollback_size != rollback.get("bytes"):
                failures.append("rollback_snapshot_size_mismatch")
        except OSError:
            failures.append("rollback_snapshot_unreadable")
    rollback_metadata_path = Path(str(epoch.get("rollback_metadata_path") or ""))
    if not rollback_metadata_path.is_file():
        failures.append("rollback_metadata_missing")
    else:
        try:
            if _sha256_file(rollback_metadata_path) != str(epoch.get("rollback_metadata_sha256") or "").upper():
                failures.append("rollback_metadata_hash_mismatch")
            rollback_metadata = json.loads(rollback_metadata_path.read_text(encoding="utf-8"))
            if rollback_metadata.get("rollback") != rollback:
                failures.append("rollback_metadata_record_mismatch")
            if rollback_metadata.get("reset_provenance") != epoch.get("reset_provenance"):
                failures.append("rollback_metadata_reset_record_mismatch")
        except (OSError, json.JSONDecodeError):
            failures.append("rollback_metadata_invalid")
    reset = epoch.get("reset_provenance")
    if reset is not None:
        rollback_absent = rollback.get("manifest_absent") is True
        expected_manifest_state = "ABSENT" if rollback_absent else "PRESENT"
        expected_manifest_sha = None if rollback_absent else rollback.get("sha256")
        reset_record = reset if isinstance(reset, dict) else {}
        valid_reset = isinstance(reset, dict) and (
            reset_record.get("status") == "OWNER_AUTHORIZED_RESET"
            and reset_record.get("owner_reported_reset") == {"manifest": "ABSENT", "incident": "REMOVED"}
            and reset_record.get("manifest_before") == expected_manifest_state
            and reset_record.get("manifest_before_sha256") == expected_manifest_sha
            and reset_record.get("manifest_before_bytes") == rollback.get("bytes")
            and isinstance(reset_record.get("incident_before"), dict)
            and reset_record.get("incident_before", {}).get("status") == "MISSING"
            and reset_record.get("historical_hygiene") == "NOT_RECOVERABLE/UNVERIFIABLE"
            and isinstance(reset_record.get("authorization"), str)
            and bool(reset_record.get("authorization", "").strip())
            and reset_record.get("incident_before") == epoch.get("original_incident_identity")
        )
        if not valid_reset:
            failures.append("owner_reset_record_invalid")
        rollback_matches_reset_state = bool(
            isinstance(reset, dict)
            and reset_record.get("manifest_before") == expected_manifest_state
            and reset_record.get("manifest_before_sha256") == expected_manifest_sha
            and reset_record.get("manifest_before_bytes") == rollback.get("bytes")
            and (
                (rollback_absent and rollback.get("bytes") == 0 and rollback_size == 0)
                or (not rollback_absent and rollback.get("bytes", 0) > 0)
            )
        )
        if not rollback_matches_reset_state:
            failures.append("owner_reset_rollback_metadata_invalid")
        try:
            policy_path = Path(str(epoch.get("policy_path") or ""))
            policy_doc = json.loads(policy_path.read_text(encoding="utf-8"))
            if _sha256_file(policy_path) != str(epoch.get("policy_sha256") or "").upper():
                failures.append("epoch_policy_hash_mismatch")
            if policy_doc.get("reset_provenance") != reset:
                failures.append("epoch_policy_reset_record_mismatch")
        except (OSError, json.JSONDecodeError):
            failures.append("epoch_policy_invalid")
    elif _incident_identity().get("status") != "PASS":
        failures.append("incident_preservation_failed")
    ledger_value = epoch.get("ledger")
    ledger = ledger_value if isinstance(ledger_value, dict) else {}
    if not isinstance(ledger_value, dict):
        failures.append("prospective_ledger_record_invalid")
    ledger_path = Path(str(ledger.get("path") or ""))
    if not ledger_path.is_file():
        failures.append("prospective_ledger_missing")
    elif _sha256_file(ledger_path) != str(ledger.get("sha256") or "").upper():
        failures.append("prospective_ledger_hash_mismatch")
    return failures


def verify_prospective_epoch(*, _allow_pending_scope: Path | None = None) -> dict:
    """Verify the active prospective epoch without writing any file."""

    manifest, _raw_manifest, manifest_errors = _strict_registry_snapshot()
    if manifest_errors:
        return {"status": "PROVEN_BLOCKED", "ok": False, "reasons": manifest_errors}
    epoch = manifest.get("prospective_epoch")
    if not isinstance(epoch, dict):
        return {"status": "PROVEN_BLOCKED", "ok": False, "reasons": ["no_active_prospective_epoch"]}
    reasons = _epoch_verify_files(epoch, manifest=manifest)
    reasons.extend(_prospective_epoch_pending_reasons(manifest, allow_pending_scope=_allow_pending_scope))
    return {
        "status": "PASS" if not reasons else "PROVEN_BLOCKED",
        "ok": not reasons,
        "epoch_id": epoch.get("epoch_id"),
        "reasons": reasons,
        "manifest_sha256": _sha256_file(MANIFEST_PATH) if MANIFEST_PATH.is_file() else None,
    }


def activate_prospective_epoch(
    *,
    dry_run: bool = True,
    epoch_id: str | None = None,
    source_sha: str | None = None,
    owner_reset_authorization: str | None = None,
    timeout_seconds: float = DEFAULT_INVENTORY_TIMEOUT_SECONDS,
    max_items: int = DEFAULT_INVENTORY_MAX_ITEMS,
) -> dict:
    """Plan or apply one additive, no-delete prospective registry epoch."""

    manifest, raw_manifest, manifest_errors = _strict_registry_snapshot()
    manifest_existed = os.path.lexists(MANIFEST_PATH)
    reasons = list(manifest_errors)
    reasons.extend(_epoch_manifest_shape(manifest))
    state = _git_repository_state()
    expected_sha = str(source_sha or state.get("head") or "").strip()
    if not expected_sha or state.get("head") != expected_sha:
        reasons.append("source_sha_mismatch")
    if state.get("dirty"):
        reasons.append("working_tree_dirty")
    writer = _prospective_epoch_writer_status()
    if writer["active"]:
        reasons.append("registry_writer_active")
    reasons.extend(_prospective_epoch_pending_reasons(manifest))
    incident = _incident_identity()
    reset_provenance = None
    if incident.get("status") == "MISSING":
        authorization = str(owner_reset_authorization or "").strip()
        if not authorization:
            reasons.append("owner_reset_authorization_required")
        else:
            reset_provenance = {
                "status": "OWNER_AUTHORIZED_RESET",
                "authorization": authorization,
                "owner_reported_reset": {"manifest": "ABSENT", "incident": "REMOVED"},
                "manifest_before": "PRESENT" if manifest_existed else "ABSENT",
                "manifest_before_sha256": hashlib.sha256(raw_manifest).hexdigest().upper() if raw_manifest is not None else None,
                "manifest_before_bytes": len(raw_manifest or b""),
                "incident_before": incident,
                "historical_hygiene": "NOT_RECOVERABLE/UNVERIFIABLE",
            }
    elif incident.get("status") != "PASS":
        reasons.append("incident_preservation_failed")
    active = manifest.get("prospective_epoch")
    if isinstance(active, dict):
        if epoch_id and str(active.get("epoch_id")) == str(epoch_id):
            verification = verify_prospective_epoch()
            verification["idempotent"] = True
            return verification
        reasons.append("conflicting_active_epoch")
    if epoch_id is None:
        epoch_id = f"epoch-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex[:12]}"
    if not _valid_epoch_id(epoch_id):
        reasons.append("invalid_epoch_id")
    effective_at = utc_now()
    boundary = _epoch_scope_boundary()
    budget = InventoryBudget(timeout_seconds=timeout_seconds, max_items=max_items)
    inventory = snapshot_tree(WORK_ROOT, budget=budget, include_hashes=False, skip_retained=False)
    if not inventory.get("complete") or budget.failure:
        reasons.append("current_inventory_incomplete_or_budget_limited")
    reconciled = reconcile_registry(persist=False, budget=budget, inventory=inventory)
    if not reconciled.get("inventory_complete"):
        reasons.append("registry_reconciliation_incomplete")
    if reconciled.get("metadata_issues"):
        reasons.append("registry_metadata_incomplete")
    items = _classify_prospective_inventory(inventory, reconciled)
    counts = {}
    for item in items:
        counts[item["lifecycle"]] = counts.get(item["lifecycle"], 0) + 1
    plan = {
        "status": "PASS" if not reasons else "PROVEN_BLOCKED",
        "ok": not reasons,
        "dry_run": bool(dry_run),
        "epoch_id": epoch_id,
        "source_sha": expected_sha,
        "effective_at": effective_at,
        "scope_boundary": boundary,
        "incident": incident,
        "reset_provenance": reset_provenance,
        "inventory_complete": bool(inventory.get("complete") and reconciled.get("inventory_complete")),
        "inventory_count": len(items),
        "counts": counts,
        "reasons": reasons,
        "historical_hygiene": "NOT_RECOVERABLE/UNVERIFIABLE",
        "deletions": [],
    }
    if dry_run or reasons:
        return plan

    lock = WORK_ROOT / ".artifact-registry-epoch.writer.lock"
    scope = _prospective_epoch_root() / str(epoch_id)
    scope_created = False
    committed = False
    transaction_result = None
    try:
        lock.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(str(lock), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(json.dumps({"epoch_id": epoch_id, "source_sha": expected_sha, "pid": os.getpid()}))
    except FileExistsError:
        plan["status"] = "PROVEN_BLOCKED"
        plan["ok"] = False
        plan["reasons"].append("registry_writer_active")
        return plan
    try:
        _current_manifest, current_raw_manifest, current_manifest_errors = _strict_registry_snapshot()
        if (
            current_manifest_errors
            or os.path.lexists(MANIFEST_PATH) != manifest_existed
            or current_raw_manifest != raw_manifest
        ):
            plan["status"] = "PROVEN_BLOCKED"
            plan["ok"] = False
            plan["reasons"].append("registry_state_changed_during_preflight")
            return plan
        if scope.exists():
            plan["status"] = "PROVEN_BLOCKED"
            plan["ok"] = False
            plan["reasons"].append("epoch_scope_already_exists")
            return plan
        scope.mkdir(parents=True)
        scope_created = True
        pending_path = scope / ".pending.json"
        pending_path.write_text(
            json.dumps(
                {
                    "epoch_id": epoch_id,
                    "source_sha": expected_sha,
                    "manifest_sha256": _sha256_file(MANIFEST_PATH) if MANIFEST_PATH.is_file() else None,
                    "state": "PENDING",
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        rollback_path = scope / "rollback_manifest.json"
        rollback_path.write_bytes(raw_manifest or b"")
        rollback = {
            "path": str(rollback_path),
            "sha256": _sha256_file(rollback_path),
            "bytes": len(raw_manifest or b""),
            "manifest_absent": raw_manifest is None,
            "artifact_count": len(manifest.get("artifacts", [])),
            "archive_count": len(manifest.get("archive", [])),
            "manifest_schema": {"version": manifest.get("version"), "schema_version": manifest.get("schema_version")},
            "source_sha": expected_sha,
            "captured_at": utc_now(),
            "provenance": {"scope_id": epoch_id, "run_id": epoch_id, "scope_root": str(scope), "registered_by": "cleanup_work_artifacts.py"},
        }
        current_manifest_matches = (
            not MANIFEST_PATH.exists()
            if raw_manifest is None
            else MANIFEST_PATH.is_file() and rollback["sha256"] == _sha256_file(MANIFEST_PATH)
        )
        if not current_manifest_matches:
            plan["status"] = "PROVEN_BLOCKED"
            plan["ok"] = False
            plan["reasons"].append("rollback_snapshot_hash_mismatch")
            return plan
        provenance = _epoch_provenance(
            epoch_id=epoch_id, source_sha=expected_sha, effective_at=effective_at,
            reset_provenance=reset_provenance,
        )
        ledger = {
            "schema_version": 1,
            "epoch_id": epoch_id,
            "captured_at": effective_at,
            "source_sha": expected_sha,
            "scope_boundary": boundary,
            "inventory": inventory.get("inventory", {}),
            "inventory_complete": True,
            "item_count": len(items),
            "counts": counts,
            "items": items,
            "unknown_preserved": counts.get("UNKNOWN", 0),
            "historical_hygiene": "NOT_RECOVERABLE/UNVERIFIABLE",
            "no_deletion": True,
        }
        ledger_path = scope / "prospective_ledger.json"
        ledger_path.write_text(json.dumps(ledger, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        policy_path = scope / "epoch_policy.json"
        policy_path.write_text(json.dumps(provenance, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        rollback_meta_path = scope / "rollback_metadata.json"
        rollback_meta_path.write_text(
            json.dumps({"rollback": rollback, "reset_provenance": reset_provenance}, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        rollback_metadata_sha256 = _sha256_file(rollback_meta_path)
        created_inventory = snapshot_tree(WORK_ROOT, budget=InventoryBudget(timeout_seconds=timeout_seconds, max_items=max_items), include_hashes=False, skip_retained=False)
        deleted = sorted(set(inventory.get("items", {})) - set(created_inventory.get("items", {})))
        if not created_inventory.get("complete") or deleted:
            plan["status"] = "PROVEN_BLOCKED"
            plan["ok"] = False
            plan["reasons"].append("post_snapshot_incomplete_or_deletion_detected")
            plan["deletions"] = deleted
            return plan
        provenance["rollback"] = rollback
        provenance["ledger"] = {"path": str(ledger_path), "sha256": _sha256_file(ledger_path), "item_count": len(items), "counts": counts}
        provenance["policy_path"] = str(policy_path)
        provenance["rollback_metadata_path"] = str(rollback_meta_path)
        provenance["rollback_metadata_sha256"] = rollback_metadata_sha256
        policy_path.write_text(json.dumps(provenance, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        provenance["policy_sha256"] = _sha256_file(policy_path)
        next_manifest = dict(manifest)
        retained = []
        for name, path, kind, purpose in (
            ("scope", scope, "artifact_registry_epoch", "retained prospective artifact registry epoch scope"),
            ("rollback", rollback_path, "artifact_registry_rollback", "retained exact pre-transition manifest rollback snapshot"),
            ("ledger", ledger_path, "artifact_registry_prospective_ledger", "current prospective artifact lifecycle baseline"),
            ("policy", policy_path, "artifact_registry_epoch_policy", "auditable prospective epoch policy"),
            ("rollback_metadata", rollback_meta_path, "artifact_registry_rollback_metadata", "rollback snapshot provenance and hash"),
        ):
            retained.append({
                "id": f"artifact-registry-epoch:{epoch_id}:{name}",
                "path": str(path),
                "kind": kind,
                "created_by": "cleanup_work_artifacts.py",
                "owner": "artifact_registry_epoch",
                "purpose": purpose,
                "created_at": effective_at,
                "bytes": dir_size_bytes(path),
                "status": "ACTIVE",
                "lifecycle": "RETAINED",
                "scope_id": epoch_id,
                "run_id": epoch_id,
                "scope_root": str(scope),
                "provenance": {"scope_id": epoch_id, "run_id": epoch_id, "scope_root": str(scope), "registered_by": "cleanup_work_artifacts.py", "source_sha": expected_sha},
            })
        next_manifest["artifacts"] = list(next_manifest.get("artifacts", [])) + retained
        next_manifest["version"] = 2
        next_manifest["schema_version"] = 2
        next_manifest["updated_at"] = utc_now()
        pending_epoch = dict(provenance)
        pending_epoch["pending_path"] = str(pending_path)
        pending_epoch["status"] = "PENDING"
        pending_epoch["no_deletion"] = True
        next_manifest["prospective_epoch"] = pending_epoch
        _atomic_write_bytes(
            MANIFEST_PATH,
            (json.dumps(next_manifest, ensure_ascii=False, indent=2) + "\n").encode("utf-8"),
        )
        active_manifest = dict(next_manifest)
        active_manifest["prospective_epoch"] = dict(provenance)
        active_manifest["prospective_epoch"]["status"] = "ACTIVE"
        active_manifest["prospective_epoch"]["no_deletion"] = True
        _atomic_write_bytes(
            MANIFEST_PATH,
            (json.dumps(active_manifest, ensure_ascii=False, indent=2) + "\n").encode("utf-8"),
        )
        verification = verify_prospective_epoch(_allow_pending_scope=scope)
        final = dict(plan)
        final.update(verification)
        final.update({"status": "PASS" if verification.get("ok") else "PROVEN_BLOCKED", "ok": bool(verification.get("ok")), "applied": False, "rollback": rollback, "ledger": provenance["ledger"], "counts": counts, "inventory_count": len(items), "deletions": deleted})
        if verification.get("ok"):
            pending_path.unlink()
            committed = True
            final["applied"] = True
            final["reasons"] = []
        else:
            plan.update(final)
        transaction_result = final
    except Exception as exc:
        plan["status"] = "PROVEN_BLOCKED"
        plan["ok"] = False
        plan["reasons"].append(f"transaction_failed:{type(exc).__name__}")
    finally:
        if scope_created and not committed:
            try:
                _restore_manifest(raw_manifest)
            except Exception as exc:
                plan["reasons"].append(f"rollback_manifest_failed:{type(exc).__name__}")
            try:
                _remove_new_epoch_scope(scope)
            except Exception as exc:
                plan["reasons"].append(f"rollback_scope_failed:{type(exc).__name__}")
        try:
            lock.unlink()
        except FileNotFoundError:
            pass
    if transaction_result is not None:
        if not committed:
            transaction_result["reasons"] = list(plan["reasons"])
        return transaction_result
    return plan


def _persist_reconciliation(reconciled: dict, *, deleted: list[dict], unknown: list[dict]) -> None:
    from work_paths import _save_manifest

    if reconciled.get("metadata_issues") or reconciled.get("inventory_errors"):
        return
    manifest, _raw_manifest, registry_errors = _strict_registry_snapshot()
    if registry_errors or not isinstance(manifest.get("artifacts"), list):
        return
    if any(not isinstance(item, dict) for item in manifest["artifacts"]):
        return
    current = {str(item.get("id")): dict(item) for item in reconciled["entries"] if item.get("id")}
    current_by_path: dict[str, list[dict]] = {}
    for item in current.values():
        try:
            current_by_path.setdefault(_path_key(_entry_path(item)), []).append(item)
        except (KeyError, TypeError, ValueError, OSError):
            continue
    for item in unknown:
        current.setdefault(str(item["id"]), dict(item))
    for item in deleted:
        if not item.get("deleted"):
            continue
        path = _absolute_path(Path(str(item["path"])))
        existing_entries = current_by_path.get(_path_key(path), [])
        if not existing_entries:
            rel = _rel_path(path)
            existing = {
                "id": f"legacy:{rel}",
                "path": str(path),
                "kind": "legacy_disposable",
                "created_by": "cleanup_work_artifacts.py",
                "owner": "cleanup_work_artifacts.py",
                "purpose": "audited legacy artifact removed by cleanup",
                "created_at": utc_now(),
            }
            current[existing["id"]] = existing
            existing_entries = [existing]
            current_by_path[_path_key(path)] = existing_entries
        for existing in existing_entries:
            existing["lifecycle"] = "MISSING"
            existing["status"] = "MISSING"
            existing["bytes"] = int(item.get("bytes") or 0)
            existing["updated_at"] = utc_now()
            existing["deletion_provenance"] = _proof_from_deleted_record(
                item,
                entry=existing,
                deleted_by="cleanup_work_artifacts._persist_reconciliation",
                evidence_source="cleanup_reconciliation",
            )
    manifest["version"] = 2
    manifest["schema_version"] = 2
    manifest["artifacts"] = list(current.values())
    _save_manifest(manifest)


def _normalize_outcome(outcome: str | None) -> str:
    value = str(outcome or "UNKNOWN").upper().strip()
    if value not in RUN_OUTCOMES:
        raise ValueError(f"unknown cleanup outcome: {value}")
    return value


def _snapshot_delta(before: dict, after: dict) -> tuple[list[dict], list[dict], list[dict]]:
    before_items = dict(before.get("items") or {})
    after_items = dict(after.get("items") or {})
    created = [after_items[key] for key in sorted(after_items.keys() - before_items.keys())]
    deleted = [before_items[key] for key in sorted(before_items.keys() - after_items.keys())]
    modified = [
        after_items[key]
        for key in sorted(before_items.keys() & after_items.keys())
        if after_items[key].get("kind") != "directory"
        and (
            any(
                before_items[key].get(field) != after_items[key].get(field)
                for field in ("kind", "bytes", "mtime_ns")
            )
            or (
                before_items[key].get("sha256") is not None
                and after_items[key].get("sha256") is not None
                and before_items[key]["sha256"] != after_items[key]["sha256"]
            )
        )
    ]
    return created, modified, deleted


def _path_is_under(path: Path, parent: Path) -> bool:
    resolved = _absolute_path(path)
    base = _absolute_path(parent)
    return resolved == base or base in resolved.parents


def _scope_entry_for_path(
    entries: list[dict],
    path: Path,
    *,
    allow_disposable_parent: bool = True,
    index: _PathEntryIndex | None = None,
) -> dict | None:
    return (index or _PathEntryIndex(entries)).scoped_entry(
        path,
        allow_disposable_parent=allow_disposable_parent,
    )


def _unknown_ledger_entry(
    item: dict,
    *,
    scope_id: str,
    run_id: str,
    scope_root: Path,
    reason: str,
) -> dict:
    relative = str(item.get("relative_path") or _rel_path(Path(item["path"])))
    return {
        "id": f"unknown:{scope_id}:{relative}",
        "path": str(Path(item["path"]).resolve()),
        "relative_path": relative,
        "kind": item.get("kind", "unknown"),
        "created_by": "cleanup_work_artifacts.py",
        "owner": "cleanup_work_artifacts.py",
        "purpose": reason,
        "created_at": utc_now(),
        "bytes": int(item.get("bytes") or 0),
        "status": "ACTIVE",
        "lifecycle": "UNKNOWN",
        "scope_id": scope_id,
        "run_id": run_id,
        "scope_root": str(scope_root.resolve()),
        "provenance": {
            "scope_id": scope_id,
            "run_id": run_id,
            "scope_root": str(scope_root.resolve()),
            "registered_by": "cleanup_work_artifacts.py",
            "observed_relative_path": relative,
            "reason": reason,
        },
    }


def _persist_unknown_entries(entries: list[dict]) -> None:
    if not entries:
        return
    from work_paths import _save_manifest

    manifest, _raw_manifest, registry_errors = _strict_registry_snapshot()
    if registry_errors or not isinstance(manifest.get("artifacts"), list):
        return
    if any(not isinstance(item, dict) for item in manifest["artifacts"]):
        return
    current = {str(item.get("id")): dict(item) for item in manifest.get("artifacts", []) if item.get("id")}
    for entry in entries:
        current[entry["id"]] = entry
    manifest["artifacts"] = list(current.values())
    manifest["version"] = 2
    manifest["schema_version"] = 2
    _save_manifest(manifest)


def _finalize_scope_impl(
    *,
    scope_id: str,
    run_id: str,
    scope_root: Path,
    before: dict | None,
    outcome: str = "UNKNOWN",
    timeout_seconds: float | None = None,
    max_items: int | None = None,
    _budget: InventoryBudget | None = None,
) -> dict:
    """Finalize exactly one run and fail closed on unregistered changes."""

    outcome = _normalize_outcome(outcome)
    scope_root = assert_artifact_under_work(Path(scope_root), "artifact scope root")
    budget = _new_inventory_budget(
        _budget,
        timeout_seconds=timeout_seconds,
        max_items=max_items,
    )
    before_tree = dict(before or {"root": str(scope_root), "items": {}, "errors": []})
    before_size = _size_snapshot(budget=budget, inventory=before_tree)
    snapshot_hashes = any(
        "sha256" in item for item in before_tree.get("items", {}).values()
    )
    before_project_size = _project_size_snapshot(
        timeout_seconds=budget.timeout_seconds,
        max_items=budget.max_items,
    )

    run_budget = _snapshot_phase_budget(budget)
    run_tree = snapshot_tree(
        scope_root,
        budget=run_budget,
        include_hashes=snapshot_hashes,
        # Keep the before/after traversal boundary identical.  Retained
        # subtrees are represented by their root in the initial snapshot;
        # expanding them only in the final snapshot creates false
        # "unregistered" deltas for historical evidence.
        skip_retained=True,
    )
    _record_snapshot_failure(budget, run_budget)
    created, modified, externally_deleted = _snapshot_delta(before_tree, run_tree)
    # The manifest and append-only post-test history are cleanup control-plane
    # files.  Canonical child scopes may update them while the release scope is
    # running; their mtime/write deltas are not unregistered test payloads.
    ignored = {
        _path_key(MANIFEST_PATH),
        _path_key(WORK_ROOT / "cleanup_post_test.jsonl"),
    }
    reconcile_inventory = (
        run_tree
        if _absolute_path(scope_root) == _absolute_path(WORK_ROOT)
        else None
    )
    reconciled = reconcile_registry(
        persist=False,
        budget=budget,
        inventory=reconcile_inventory,
    )
    scoped_entries = [
        entry
        for entry in reconciled["entries"]
        if str(entry.get("scope_id") or "") == str(scope_id)
    ]
    scoped_index = _PathEntryIndex(
        scoped_entries,
        budget=budget,
        phase="scope_reconciliation",
    )
    unknown: list[dict] = []
    modified_outside: list[dict] = []
    retained: list[dict] = []
    protected: list[dict] = []
    errors: list[dict] = list(run_tree.get("errors") or [])

    for item in created:
        budget.check_deadline(Path(str(item.get("path") or scope_root)), phase="scope_reconciliation")
        if _path_key(Path(item["path"])) in ignored:
            continue
        registered = _scope_entry_for_path(
            scoped_entries,
            Path(item["path"]),
            index=scoped_index,
        )
        if registered is None:
            unknown.append(_unknown_ledger_entry(
                item,
                scope_id=scope_id,
                run_id=run_id,
                scope_root=scope_root,
                reason="unregistered artifact created in scope",
            ))
    for item in modified:
        budget.check_deadline(Path(str(item.get("path") or scope_root)), phase="scope_reconciliation")
        if _path_key(Path(item["path"])) in ignored:
            continue
        registered = _scope_entry_for_path(
            scoped_entries,
            Path(item["path"]),
            index=scoped_index,
        )
        if registered is None:
            modified_outside.append({**item, "reason": "modified artifact outside registered scope"})
    for item in externally_deleted:
        budget.check_deadline(Path(str(item.get("path") or scope_root)), phase="scope_reconciliation")
        if _path_key(Path(item["path"])) in ignored:
            continue
        registered = _scope_entry_for_path(
            scoped_entries,
            Path(item["path"]),
            allow_disposable_parent=False,
            index=scoped_index,
        )
        if registered is None:
            errors.append({**item, "reason": "deleted artifact outside registered scope"})

    for entry in scoped_entries:
        lifecycle = str(entry.get("lifecycle") or "UNKNOWN").upper()
        try:
            path = _entry_path(entry) if entry.get("path") else None
        except (KeyError, TypeError, ValueError, OSError):
            path = None
        if lifecycle == "PROTECTED":
            protected.append(entry)
        elif lifecycle in {"RETAINED", "UNKNOWN"} and path is not None and os.path.lexists(path):
            retained.append(entry)

    if not budget.failure:
        _persist_unknown_entries(unknown)
    deleted: list[dict] = []
    cleanup_candidates = [
        entry for entry in scoped_entries
        if str(entry.get("lifecycle") or "").upper() == "DISPOSABLE"
        and entry.get("path")
        and os.path.lexists(_entry_path(entry))
    ]
    cleanup_candidates.sort(key=lambda entry: len(Path(str(entry["path"])).parts))
    keep_paths = [
        (_entry_path(entry), str(entry["id"])) for entry in reconciled["entries"]
        if str(entry.get("lifecycle") or "").upper() in {"RETAINED", "PROTECTED", "UNKNOWN"}
        and entry.get("path")
    ]
    candidate_roots: list[Path] = []
    deletion_allowed = bool(
        not budget.failure
        and reconciled.get("inventory_complete", False)
        and not reconciled.get("metadata_issues")
        and not reconciled.get("inventory_errors")
    )
    if deletion_allowed:
        for entry in cleanup_candidates:
            path = _entry_path(entry)
            if any(path == root or root in path.parents for root in candidate_roots):
                continue
            keeper = next((item for item in keep_paths if (item[0] == path or path in item[0].parents) and os.path.lexists(item[0])), None)
            if keeper is not None:
                deleted.append({"path": str(path), "skipped": True, "reason": "registered_non_disposable_descendant", "blocking_id": keeper[1]})
                continue
            if safe_rmtree(
                path,
                deleted,
                reason=f"scope:{scope_id}",
                budget=budget,
                allow_registered_disposable=True,
                registered_entries=reconciled["entries"],
            ):
                candidate_roots.append(path)
    else:
        for entry in cleanup_candidates:
            retained.append(entry)
        if cleanup_candidates and not budget.failure:
            _persist_reconciliation(reconciled, deleted=[], unknown=unknown)

    if not budget.failure and reconciled.get("inventory_complete", False):
        _persist_reconciliation(reconciled, deleted=deleted, unknown=unknown)

    locked = [item for item in deleted if item.get("reason") == "locked_by_process"]
    errors.extend(
        item for item in deleted
        if item.get("skipped") and item.get("reason") not in {"keep_policy", "protected_or_outside", "locked_by_process", "registered_non_disposable_descendant", "registered_retained_or_protected_descendant"}
    )
    after_budget = _snapshot_phase_budget(budget)
    after_tree = snapshot_tree(
        scope_root,
        budget=after_budget,
        include_hashes=snapshot_hashes,
        skip_retained=True,
    )
    _record_snapshot_failure(budget, after_budget)
    after_size = _size_snapshot(budget=budget, inventory=after_tree)
    after_project_size = _project_size_snapshot(
        timeout_seconds=budget.timeout_seconds,
        max_items=budget.max_items,
    )
    deleted_roots = [
        Path(str(item["path"])).expanduser().resolve()
        for item in deleted
        if item.get("deleted") and item.get("path")
    ]
    deleted_by_root = {
        _path_key(Path(str(item["path"]))): item
        for item in deleted
        if item.get("deleted") and item.get("path")
    }
    after_entries: list[dict] = []
    for original in reconciled.get("entries", []):
        item = dict(original)
        try:
            item_path = _entry_path(item)
        except (KeyError, TypeError, ValueError, OSError):
            item_path = None
        if item_path is not None and any(
            item_path == root or root in item_path.parents for root in deleted_roots
        ):
            deleted_root = next(
                root for root in deleted_roots
                if item_path == root or root in item_path.parents
            )
            deletion_record = deleted_by_root[_path_key(deleted_root)]
            item["lifecycle"] = "MISSING"
            item["status"] = "MISSING"
            item["bytes"] = 0
            item["deletion_provenance"] = _proof_from_deleted_record(
                deletion_record,
                entry=item,
                deleted_by="cleanup_work_artifacts.finalize_scope",
                evidence_source="scoped_cleanup_finalization",
            )
        after_entries.append(item)
    reconciled_after = {
        "entries": after_entries,
        "unknown": [dict(item) for item in reconciled.get("unknown", [])],
    }
    before_metrics = None
    after_metrics = None
    if not budget.failure:
        before_metrics = _snapshot_lifecycle_metrics(before_tree, reconciled, budget=budget)
        after_metrics = _snapshot_lifecycle_metrics(after_tree, reconciled_after, budget=budget)
    if after_metrics is not None:
        after_metrics["locked_count"] = len(locked)
    scoped_after_entries = [
        item for item in after_entries
        if str(item.get("scope_id") or "") == str(scope_id)
    ]
    after_groups = _state_groups(scoped_after_entries, unknown)
    expected_missing, unexpected_missing = _split_missing(after_groups["MISSING"])
    inventory_failed = bool(
        not run_tree.get("complete", True)
        or not after_tree.get("complete", True)
        or not reconciled.get("inventory_complete", True)
        or not before_size.get("inventory", {}).get("complete", True)
        or not after_size.get("inventory", {}).get("complete", True)
    )
    cleanup_failed = bool(
        unknown
        or modified_outside
        or errors
        or locked
        or run_tree.get("errors")
        or inventory_failed
        or reconciled.get("inventory_errors")
        or reconciled.get("metadata_issues")
        or unexpected_missing
        or not before_project_size.get("complete")
        or not after_project_size.get("complete")
        or after_project_size.get("non_exempt_bytes") is None
        or not after_project_size.get("within_limit")
        or any(item.get("skipped") for item in deleted)
    )
    cleanup_ok = not cleanup_failed and all(item.get("deleted") for item in deleted if not item.get("skipped"))
    status = "PASS" if cleanup_ok else "REVIEW_REQUIRED"
    report = {
        "schema_version": 4,
        "utc": utc_now(),
        "scope_id": scope_id,
        "run_id": run_id,
        "scope_root": str(scope_root),
        "outcome": outcome,
        "status": status,
        "ok": status == "PASS",
        "before": before_size,
        "after": after_size,
        "project_size": {"before": before_project_size, "after": after_project_size},
        "before_metrics": before_metrics,
        "after_metrics": after_metrics,
        "lifecycle_metrics": {"before": before_metrics, "after": after_metrics},
        "before_inventory": _report_inventory_snapshot(before_tree),
        "run_inventory": _report_inventory_snapshot(run_tree),
        "after_inventory": _report_inventory_snapshot(after_tree),
        "created": created,
        "modified": modified_outside,
        "deleted": deleted,
        "retained": retained,
        "protected": protected,
        "unknown": unknown,
        "missing": after_groups["MISSING"],
        "expected_missing": expected_missing,
        "unexpected_missing": unexpected_missing,
        "locked": locked,
        "errors": errors,
        "metadata_issues": reconciled.get("metadata_issues") or [],
        "inventory_complete": not inventory_failed,
        "inventory": {
            "budget": budget.report(),
            "run": run_tree.get("inventory"),
            "reconcile": _report_inventory_snapshot(reconciled.get("inventory")),
            "reconcile_errors": reconciled.get("inventory_errors") or [],
            "before_size": before_size.get("inventory"),
            "after": after_tree.get("inventory"),
            "after_size": after_size.get("inventory"),
        },
        "freed_gb": human_gb(sum(int(item.get("bytes") or 0) for item in deleted if item.get("deleted"))),
        "terminal_status": outcome,
        "cleanup_status": status,
    }
    _compact_report_records(
        report,
        ("retained", "protected", "unknown", "missing", "expected_missing", "unexpected_missing"),
    )
    return report


def _terminal_finalize_report(
    *,
    scope_id: str,
    run_id: str,
    scope_root: Path,
    before: dict | None,
    outcome: str,
    budget: InventoryBudget,
    error: dict,
) -> dict:
    """Build a report without further filesystem work after finalization fails."""

    terminal_status = str(error.get("status") or "FAIL").upper()
    if terminal_status not in {"TIMEOUT", "FAIL", "START_ERROR", "CANCELLED", "UNKNOWN", "ERROR"}:
        terminal_status = "FAIL"
    if not budget.failure:
        budget.failure = {
            "status": terminal_status,
            "reason": str(error.get("reason") or "finalize_error"),
            "phase": str(error.get("phase") or "finalization"),
            "path": str(scope_root),
            "items_seen": budget.items_seen,
            "timeout_seconds": budget.timeout_seconds,
            "max_items": budget.max_items,
        }
    before_inventory = dict(before or {
        "root": str(scope_root),
        "items": {},
        "errors": [],
        "complete": False,
    })
    before_size = {
        "utc": utc_now(),
        "dev_root": str(ROOT),
        "work_root": str(WORK_ROOT),
        "dev_total_gb": None,
        "work_total_gb": None,
        "work": {
            "path": str(scope_root),
            "bytes": None,
            "gb": None,
            "children": [],
            "complete": False,
            "status": "FINALIZATION_FAILED",
            "reason": str(error.get("reason") or "finalize_error"),
        },
        "inventory": budget.report(),
    }
    return {
        "schema_version": 4,
        "utc": utc_now(),
        "scope_id": scope_id,
        "run_id": run_id,
        "scope_root": str(scope_root),
        "outcome": outcome,
        "status": "REVIEW_REQUIRED",
        "terminal_status": terminal_status,
        "ok": False,
        "before": before_size,
        "after": None,
        "before_metrics": None,
        "after_metrics": None,
        "lifecycle_metrics": {"before": None, "after": None},
        "before_inventory": _report_inventory_snapshot(before_inventory),
        "run_inventory": None,
        "after_inventory": None,
        "created": [],
        "modified": [],
        "deleted": [],
        "retained": [],
        "protected": [],
        "unknown": [],
        "missing": [],
        "locked": [],
        "errors": [dict(error)],
        "metadata_issues": [],
        "inventory_complete": False,
        "inventory": {
            "budget": budget.report(),
            "failure": dict(error),
        },
        "freed_gb": 0.0,
    }


def finalize_scope(
    *,
    scope_id: str,
    run_id: str,
    scope_root: Path,
    before: dict | None,
    outcome: str = "UNKNOWN",
    timeout_seconds: float | None = None,
    max_items: int | None = None,
) -> dict:
    """Finalize one scope and always return a terminal fail-closed report."""

    outcome = _normalize_outcome(outcome)
    scope_root = assert_artifact_under_work(Path(scope_root), "artifact scope root")
    budget = _new_inventory_budget(
        timeout_seconds=timeout_seconds,
        max_items=max_items,
    )
    try:
        return _finalize_scope_impl(
            scope_id=scope_id,
            run_id=run_id,
            scope_root=scope_root,
            before=before,
            outcome=outcome,
            _budget=budget,
        )
    except InventoryFailure as exc:
        return _terminal_finalize_report(
            scope_id=scope_id,
            run_id=run_id,
            scope_root=scope_root,
            before=before,
            outcome=outcome,
            budget=budget,
            error=dict(exc.details),
        )
    except BaseException as exc:  # noqa: BLE001
        return _terminal_finalize_report(
            scope_id=scope_id,
            run_id=run_id,
            scope_root=scope_root,
            before=before,
            outcome=outcome,
            budget=budget,
            error={
                "status": "FAIL",
                "reason": "finalize_exception",
                "phase": "finalization",
                "error": str(exc),
            },
        )


def cleanup_work(
    *,
    dry_run: bool = False,
    registered_only: bool = False,
    outcome: str = "UNKNOWN",
    scope_id: str | None = None,
    run_id: str | None = None,
    scope_root: Path | None = None,
    before: dict | None = None,
    timeout_seconds: float | None = None,
    max_items: int | None = None,
) -> dict:
    """Reconcile and clean only registered/audited DISPOSABLE artifacts.

    The dry-run branch is intentionally pure: it does not create a directory,
    report, registry entry, evidence copy or process side effect.
    """

    outcome = _normalize_outcome(outcome)
    if scope_id:
        return finalize_scope(
            scope_id=str(scope_id),
            run_id=str(run_id or scope_id),
            scope_root=Path(scope_root or WORK_ROOT),
            before=before,
            outcome=outcome,
            timeout_seconds=timeout_seconds,
            max_items=max_items,
        )
    budget = _new_inventory_budget(
        timeout_seconds=timeout_seconds,
        max_items=max_items,
    )
    if budget.timeout_seconds <= 0:
        try:
            budget.check(WORK_ROOT)
        except InventoryFailure as exc:
            before_inventory = {
                "root": str(WORK_ROOT),
                "items": {},
                "errors": [_inventory_error(WORK_ROOT, exc)],
                "complete": False,
                "inventory": budget.report(),
            }
    else:
        before_budget = _snapshot_phase_budget(budget)
        before_inventory = snapshot_tree(
            WORK_ROOT,
            budget=before_budget,
            include_hashes=True,
            skip_retained=True,
        )
        _record_snapshot_failure(budget, before_budget)
    before = _size_snapshot(budget=budget, inventory=before_inventory)
    before_project_size = _project_size_snapshot(
        timeout_seconds=budget.timeout_seconds,
        max_items=budget.max_items,
    )
    if not dry_run and not registered_only:
        copied = consolidate_evidence()
    else:
        copied = []
    reconcile_inventory = before_inventory
    if not dry_run and not registered_only:
        reconcile_budget = _snapshot_phase_budget(budget)
        reconcile_inventory = snapshot_tree(
            WORK_ROOT,
            budget=reconcile_budget,
            include_hashes=True,
            skip_retained=True,
        )
        _record_snapshot_failure(budget, reconcile_budget)
    reconciled = reconcile_registry(
        persist=False,
        budget=budget,
        inventory=reconcile_inventory,
    )
    plan: list[dict] = []
    blocked: list[dict] = []
    deleted: list[dict] = []
    candidate_errors: list[dict] = []
    registry_issues = list(reconciled.get("metadata_issues") or [])
    registry_issues.extend(reconciled.get("inventory_errors") or [])
    deletion_allowed = bool(
        reconciled.get("inventory_complete", False)
        and not budget.failure
        and not registry_issues
    )
    candidates = (
        _candidate_entries(reconciled, registered_only=registered_only)
        if deletion_allowed
        else []
    )
    if registry_issues:
        blocked.extend({
            "path": issue.get("path") or str(MANIFEST_PATH),
            "reason": "registry_metadata_invalid",
            "details": issue.get("reason") or issue.get("error") or "registry reconciliation reported an issue",
        } for issue in registry_issues)
    entries_by_id = {
        str(entry.get("id")): entry
        for entry in reconciled.get("entries", [])
        if entry.get("id")
    }
    for candidate in candidates:
        path = Path(candidate["path"])
        keeper = _registered_keep_blocker(path, reconciled.get("entries", []))
        if keeper is not None:
            blocker = {
                "path": str(path),
                "id": candidate.get("id"),
                "reason": "registered_non_disposable_descendant",
                "blocking_id": keeper.get("id"),
            }
            blocked.append(blocker)
            if not dry_run:
                deleted.append({**blocker, "skipped": True})
            continue
        if dry_run:
            # Dry-run is a planning operation.  Use the registered byte
            # snapshot rather than rescanning each candidate; a stale/absent
            # value is reported as 0 and never authorizes deletion.
            candidate_bytes = int(
                entries_by_id.get(str(candidate.get("id")), {}).get("bytes") or 0
            )
        else:
            try:
                candidate_bytes = _bounded_dir_size(path, budget)
            except (InventoryFailure, OSError) as exc:
                candidate_error = _inventory_error(path, exc)
                candidate_errors.append(candidate_error)
                continue
        item = {
            "path": str(path),
            "id": candidate.get("id"),
            "bytes": candidate_bytes,
            "reason": candidate.get("reason"),
        }
        if dry_run:
            plan.append({**item, "action": "DELETE"})
        else:
            safe_rmtree(
                path,
                deleted,
                reason=str(candidate.get("reason") or "disposable"),
                budget=budget,
                allow_registered_disposable=True,
                registered_entries=reconciled.get("entries", []),
            )

    if dry_run:
        after = before
        before_metrics = (
            None
            if budget.failure
            else _snapshot_lifecycle_metrics(before_inventory, reconciled, budget=budget)
        )
        groups = _state_groups(reconciled["entries"], reconciled["unknown"])
        expected_missing, unexpected_missing = _split_missing(groups["MISSING"])
        unresolved = groups["UNKNOWN"] + unexpected_missing + groups["STALE"] + (reconciled.get("metadata_issues") or [])
        inventory_failed = bool(
            not before.get("inventory", {}).get("complete", True)
            or not reconciled.get("inventory_complete", True)
            or budget.failure
            or candidate_errors
        )
        dry_run_status = "PASS" if not (
            unresolved or inventory_failed or blocked
            or not before_project_size.get("complete")
            or not before_project_size.get("within_limit")
        ) else "REVIEW_REQUIRED"
        result = {
            "schema_version": 3,
            "utc": utc_now(),
            "dry_run": True,
            "registered_only": registered_only,
            "outcome": outcome,
            "ok": dry_run_status == "PASS",
            "status": dry_run_status,
            "cleanup_status": dry_run_status,
            "terminal_status": outcome,
            "before": before,
            "after": None,
            "before_metrics": before_metrics,
            "after_metrics": None,
            "lifecycle_metrics": {
                "before": before_metrics,
                "after": None,
            },
            "freed_gb": 0.0,
            "deleted": [],
            "blocked": blocked,
            "would_delete": plan,
            "retained": groups["RETAINED"],
            "protected": groups["PROTECTED"],
            "unknown": groups["UNKNOWN"],
            "missing": groups["MISSING"],
            "expected_missing": expected_missing,
            "unexpected_missing": unexpected_missing,
            "locked": [],
            "errors": candidate_errors,
            "inventory_complete": not inventory_failed,
            "inventory": {
                "budget": budget.report(),
                "before_size": before.get("inventory"),
                "reconcile": _report_inventory_snapshot(reconciled.get("inventory")),
                "reconcile_errors": reconciled.get("inventory_errors") or [],
                "candidate_errors": candidate_errors,
            },
            "evidence_copied": [],
            "project_size": {"before": before_project_size, "after": None},
        }
        _compact_report_records(
            result,
            ("retained", "protected", "unknown", "missing", "expected_missing", "unexpected_missing", "blocked"),
        )
        return result

    if not budget.failure:
        _persist_reconciliation(
            reconciled,
            deleted=deleted,
            unknown=[] if registered_only else reconciled["unknown"],
        )
    after_budget = _snapshot_phase_budget(budget)
    after_inventory = snapshot_tree(
        WORK_ROOT,
        budget=after_budget,
        include_hashes=True,
        skip_retained=True,
    )
    _record_snapshot_failure(budget, after_budget)
    after = _size_snapshot(budget=budget, inventory=after_inventory)
    after_project_size = _project_size_snapshot(
        timeout_seconds=budget.timeout_seconds,
        max_items=budget.max_items,
    )
    freed = sum(int(item.get("bytes") or 0) for item in deleted if item.get("deleted"))
    locked = [item for item in deleted if item.get("reason") == "locked_by_process"]
    errors = [
        item for item in deleted
        if item.get("skipped") and item.get("reason") not in {
            "keep_policy",
            "protected_or_outside",
            "registered_non_disposable_descendant",
            "registered_retained_or_protected_descendant",
        }
    ]
    refreshed = reconcile_registry(
        persist=False,
        budget=budget,
        inventory=after_inventory,
    )
    groups = _state_groups(refreshed["entries"], refreshed["unknown"])
    expected_missing, unexpected_missing = _split_missing(groups["MISSING"])
    unresolved = groups["UNKNOWN"] + unexpected_missing + groups["STALE"] + (refreshed.get("metadata_issues") or [])
    inventory_failed = bool(
        not before.get("inventory", {}).get("complete", True)
        or not after.get("inventory", {}).get("complete", True)
        or not refreshed.get("inventory_complete", True)
        or budget.failure
        or candidate_errors
        or blocked
        or any(item.get("skipped") for item in deleted)
        or not before_project_size.get("complete")
        or not after_project_size.get("complete")
        or not after_project_size.get("within_limit")
    )
    before_metrics = None
    after_metrics = None
    if not budget.failure:
        before_metrics = _snapshot_lifecycle_metrics(before_inventory, reconciled, budget=budget)
        after_metrics = _snapshot_lifecycle_metrics(after_inventory, refreshed, budget=budget)
        after_metrics["locked_count"] = len(locked)
    result = {
        "schema_version": 3,
        "utc": utc_now(),
        "dry_run": False,
        "ok": not bool(unresolved or locked or errors or inventory_failed),
        "status": "PASS" if not (unresolved or locked or errors or inventory_failed) else "REVIEW_REQUIRED",
        "cleanup_status": "PASS" if not (unresolved or locked or errors or inventory_failed) else "REVIEW_REQUIRED",
        "terminal_status": outcome,
        "before": before,
        "after": after,
        "before_metrics": before_metrics,
        "after_metrics": after_metrics,
        "lifecycle_metrics": {
            "before": before_metrics,
            "after": after_metrics,
        },
        "freed_gb": human_gb(freed),
        "deleted": deleted,
        "blocked": blocked,
        "would_delete": [],
        "retained": groups["RETAINED"],
        "protected": groups["PROTECTED"],
        "unknown": groups["UNKNOWN"],
        "missing": groups["MISSING"],
        "expected_missing": expected_missing,
        "unexpected_missing": unexpected_missing,
        "locked": locked,
        "errors": errors,
        "inventory_complete": not inventory_failed,
        "inventory": {
            "budget": budget.report(),
            "before_size": before.get("inventory"),
            "after_size": after.get("inventory"),
            "reconcile": _report_inventory_snapshot(refreshed.get("inventory")),
            "reconcile_errors": refreshed.get("inventory_errors") or [],
            "candidate_errors": candidate_errors,
        },
        "registered_only": registered_only,
        "outcome": outcome,
        "evidence_copied": copied,
        "project_size": {"before": before_project_size, "after": after_project_size},
    }
    _compact_report_records(
        result,
        ("retained", "protected", "unknown", "missing", "expected_missing", "unexpected_missing", "blocked"),
    )
    if not registered_only:
        write_size_report(WORK_ROOT / "size_report_before_cleanup.json")
        write_size_report(WORK_ROOT / "size_report_after_cleanup.json")
        CLEANUP_MANIFEST.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        # The report is retained evidence and is separate from the registry.
        from work_paths import register_artifact

        register_artifact(
            artifact_id="cleanup_manifest",
            path=CLEANUP_MANIFEST,
            kind="cleanup_report",
            created_by="cleanup_work_artifacts.py",
            owner="cleanup_work_artifacts.py",
            purpose="Current cleanup report with before/after and lifecycle decisions",
            lifecycle="RETAINED",
        )
    return result


def cleanup_after_test(
    paths: list[Path] | list[str],
    *,
    reason: str = "post_test_tmp",
    outcome: str = "UNKNOWN",
    scope_id: str | None = None,
    run_id: str | None = None,
    disposable_paths: list[Path] | list[str] | None = None,
) -> dict:
    """Apply lifecycle semantics; explicitly disposable game copies always delete."""

    from work_paths import (
        _load_manifest,
        lifecycle_for_entry,
        mark_artifacts_missing_under,
        register_artifact,
        set_artifact_status,
    )

    outcome = _normalize_outcome(outcome)
    disposable_targets = {_absolute_path(Path(raw).expanduser()) for raw in disposable_paths or []}
    seen_paths: set[Path] = set()
    ambient = ambient_scope()
    scope_id = str(scope_id or ambient["scope_id"])
    if scope_id == "legacy":
        scope_id = new_scope_id("post-test")
    run_id = str(run_id or ambient["run_id"])
    if run_id == "legacy":
        run_id = scope_id
    before_project_size = _project_size_snapshot()
    deleted: list[dict] = []
    retained: list[dict] = []
    errors: list[dict] = []
    for raw in paths:
        path = _absolute_path(Path(raw).expanduser())
        seen_paths.add(path)
        if not path_under_work(path):
            errors.append({"path": str(path), "reason": "outside_work"})
            continue
        if path == E2E_GAME_COPY.resolve() or E2E_GAME_COPY.resolve() in path.parents:
            errors.append({"path": str(path), "reason": "protected_game_copy"})
            continue
        always_dispose = path in disposable_targets
        if always_dispose:
            exact_game_copy = False
            for entry in _load_manifest().get("artifacts", []):
                if not isinstance(entry, dict):
                    continue
                try:
                    entry_path = _entry_path(entry)
                except (KeyError, TypeError, ValueError, OSError):
                    continue
                if (
                    entry_path == path
                    and lifecycle_for_entry(entry) == "DISPOSABLE"
                    and str(entry.get("kind") or "") == "test_game_copy"
                    and str(entry.get("owner") or "").strip()
                    and str(entry.get("purpose") or "").strip()
                ):
                    exact_game_copy = True
                    break
            if not exact_game_copy:
                errors.append({"path": str(path), "reason": "game_copy_not_registered_disposable"})
                continue
        artifact_id = f"run:{scope_id}:{_rel_path(path)}"
        if outcome != "UNKNOWN" or always_dispose:
            register_artifact(
                artifact_id=artifact_id,
                path=path,
                kind="test_game_copy" if always_dispose else "test_output",
                created_by=reason,
                owner=reason,
                purpose=reason,
                lifecycle="DISPOSABLE",
                scope_id=scope_id,
                run_id=run_id,
            )
            proof = None
            if os.path.lexists(path):
                deletion_start = len(deleted)
                safe_rmtree(path, deleted, reason=reason, allow_registered_disposable=True)
                path_key = _path_key(path)
                own_deletion = next(
                    (
                        item for item in deleted[deletion_start:]
                        if item.get("deleted") and item.get("path")
                        and _path_key(Path(str(item["path"]))) == path_key
                    ),
                    None,
                )
                if own_deletion is not None:
                    proof = _proof_from_deleted_record(
                        own_deletion,
                        deleted_by="cleanup_after_test",
                        evidence_source="cleanup_after_test",
                    )
                else:
                    failure = deleted[deletion_start:] or [{"reason": "deletion_not_confirmed"}]
                    errors.append({
                        "path": str(path),
                        "reason": "disposable_deletion_not_proven",
                        "details": failure[0],
                        "path_absent_after_attempt": not os.path.lexists(path),
                    })
                    # Disappearance after a failed attempt is a race, not
                    # proof that this cleanup invocation deleted the path.
                    continue
            else:
                proof = make_deletion_provenance(
                    path=path,
                    reason=reason,
                    deleted_by="cleanup_after_test",
                    evidence_source="owner_confirmed_absent_after_cleanup",
                    scope_id=scope_id,
                    run_id=run_id,
                    scope_root=WORK_ROOT,
                    deletion_result="already_absent",
                )
                set_artifact_status(
                    artifact_id,
                    "MISSING",
                    lifecycle="MISSING",
                    purpose=reason,
                    deletion_provenance=proof,
                )
            set_artifact_status(
                artifact_id,
                "MISSING",
                lifecycle="MISSING",
                purpose=reason,
                deletion_provenance=proof,
            )
            if proof is not None and not os.path.lexists(path):
                mark_artifacts_missing_under(path, purpose=reason, deletion_provenance=proof)
        else:
            lifecycle = "UNKNOWN" if outcome == "UNKNOWN" else "RETAINED"
            register_artifact(
                artifact_id=artifact_id,
                path=path,
                kind="test_evidence",
                created_by=reason,
                owner=reason,
                purpose=reason,
                lifecycle=lifecycle,
                scope_id=scope_id,
                run_id=run_id,
            )
            retained.append({"path": str(path), "lifecycle": lifecycle})
    for path in disposable_targets - seen_paths:
        errors.append({"path": str(path), "reason": "game_copy_not_in_cleanup_paths"})
    freed = sum(int(item.get("bytes") or 0) for item in deleted if item.get("deleted"))
    after_project_size = _project_size_snapshot()
    locked = [item for item in deleted if item.get("reason") == "locked_by_process"]
    cleanup_ok = (
        not errors
        and not any(item.get("skipped") for item in deleted)
        and before_project_size.get("complete")
        and after_project_size.get("complete")
        and after_project_size.get("within_limit")
    )
    doc = {
        "schema_version": 2,
        "utc": utc_now(),
        "reason": reason,
        "outcome": outcome,
        "ok": cleanup_ok,
        "cleanup_status": "PASS" if cleanup_ok else "REVIEW_REQUIRED",
        "terminal_status": outcome,
        "project_size": {"before": before_project_size, "after": after_project_size},
        "deleted": deleted,
        "locked": locked,
        "retained": retained,
        "errors": errors,
        "freed_gb": human_gb(freed),
    }
    # The small history is itself registered retained evidence.
    ensure_work_root()
    hist_path = WORK_ROOT / "cleanup_post_test.jsonl"
    history_id = _stable_path_artifact_id("cleanup_post_test_history", hist_path)
    register_artifact(
        artifact_id=history_id,
        path=hist_path,
        kind="cleanup_history",
        created_by="cleanup_work_artifacts.py",
        owner="cleanup_work_artifacts.py",
        purpose="append-only post-test cleanup history",
        lifecycle="RETAINED",
        scope_id=scope_id,
        run_id=run_id,
    )
    with hist_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(doc, ensure_ascii=False) + "\n")
    return doc


def main() -> int:
    ap = argparse.ArgumentParser(description="Safe cleanup of tests/golden/_work")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--report-only", action="store_true")
    ap.add_argument("--registered-only", action="store_true", help="Clean only registered DISPOSABLE artifacts")
    ap.add_argument("--outcome", choices=tuple(sorted(RUN_OUTCOMES)), default="UNKNOWN")
    ap.add_argument("--scope-id", default=None)
    ap.add_argument("--run-id", default=None)
    ap.add_argument("--scope-root", type=Path, default=None)
    ap.add_argument("--before", type=Path, default=None, help="JSON recursive snapshot captured before a scoped run")
    ap.add_argument(
        "--inventory-timeout-seconds",
        type=float,
        default=DEFAULT_INVENTORY_TIMEOUT_SECONDS,
        help="Maximum wall-clock time for one cleanup inventory (fail-closed)",
    )
    ap.add_argument(
        "--inventory-max-items",
        type=int,
        default=DEFAULT_INVENTORY_MAX_ITEMS,
        help="Maximum filesystem entries inspected by one cleanup inventory (fail-closed)",
    )
    ap.add_argument("--snapshot", action="store_true", help="Write a recursive snapshot to --output")
    migration = ap.add_mutually_exclusive_group()
    migration.add_argument(
        "--migrate-registry",
        action="store_true",
        help="Read-only registry migration plan; archive metadata is not applied",
    )
    migration.add_argument(
        "--apply-migration",
        action="store_true",
        help="Apply registry migration metadata without deleting physical files",
    )
    provenance = ap.add_mutually_exclusive_group()
    provenance.add_argument(
        "--backfill-missing-provenance",
        action="store_true",
        help="Read-only plan to attach primary deletion evidence to MISSING records",
    )
    provenance.add_argument(
        "--apply-missing-provenance",
        action="store_true",
        help="Attach primary deletion evidence without archiving historical records",
    )
    epoch = ap.add_mutually_exclusive_group()
    epoch.add_argument("--prospective-epoch-plan", action="store_true", help="Read-only prospective epoch plan")
    epoch.add_argument("--apply-prospective-epoch", action="store_true", help="Apply one no-delete prospective epoch")
    epoch.add_argument("--verify-prospective-epoch", action="store_true", help="Verify the active prospective epoch")
    ap.add_argument("--epoch-id", default=None)
    ap.add_argument("--source-sha", default=None)
    ap.add_argument(
        "--owner-reset-authorization",
        default=None,
        help="Explicit Owner authorization statement required when the preserved incident registry is missing",
    )
    ap.add_argument("--register-path", action="append", default=[], help="Register one runner artifact")
    ap.add_argument("--owner", default="cleanup caller")
    ap.add_argument("--purpose", default="registered cleanup-run artifact")
    ap.add_argument("--lifecycle", choices=("PROTECTED", "RETAINED", "DISPOSABLE", "UNKNOWN"), default="RETAINED")
    ap.add_argument("--output", type=Path, default=None, help="Optional report path; dry-run output must be outside _work")
    args = ap.parse_args()
    if args.prospective_epoch_plan or args.apply_prospective_epoch or args.verify_prospective_epoch:
        if args.verify_prospective_epoch:
            result = verify_prospective_epoch()
        else:
            result = activate_prospective_epoch(
                dry_run=not args.apply_prospective_epoch,
                epoch_id=args.epoch_id,
                source_sha=args.source_sha,
                owner_reset_authorization=args.owner_reset_authorization,
                timeout_seconds=args.inventory_timeout_seconds,
                max_items=args.inventory_max_items,
            )
        if args.output:
            target = args.output.expanduser().resolve()
            if path_under_work(target) and not args.apply_prospective_epoch:
                print("--output for a read-only prospective epoch command must be outside _work", file=sys.stderr)
                return 2
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result.get("ok") else 1
    if args.migrate_registry or args.apply_migration:
        result = migrate_registry(dry_run=not args.apply_migration)
        if args.output:
            target = args.output.expanduser().resolve()
            if args.migrate_registry and path_under_work(target):
                print("--output for --migrate-registry must be outside _work", file=sys.stderr)
                return 2
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result["ok"] else 1
    if args.backfill_missing_provenance or args.apply_missing_provenance:
        result = backfill_missing_deletion_provenance(
            dry_run=not args.apply_missing_provenance,
        )
        if args.output:
            target = args.output.expanduser().resolve()
            if args.backfill_missing_provenance and path_under_work(target):
                print("--output for --backfill-missing-provenance must be outside _work", file=sys.stderr)
                return 2
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result["ok"] else 1
    if args.dry_run and (args.register_path or args.snapshot):
        print("--register-path/--snapshot cannot be combined with --dry-run", file=sys.stderr)
        return 2
    if args.register_path:
        if not args.scope_id:
            print("--register-path requires --scope-id", file=sys.stderr)
            return 2
        for raw_path in args.register_path:
            target = Path(raw_path).expanduser().resolve()
            register_artifact(
                artifact_id=f"cli:{args.scope_id}:{_rel_path(target)}",
                path=target,
                kind="runner_artifact",
                created_by="cleanup_work_artifacts.py",
                owner=args.owner,
                purpose=args.purpose,
                lifecycle=args.lifecycle,
                scope_id=args.scope_id,
                run_id=args.run_id or args.scope_id,
                scope_root=args.scope_root or WORK_ROOT,
            )
        if not args.snapshot and not args.output:
            return 0
    if args.snapshot:
        if not args.output:
            print("--snapshot requires --output", file=sys.stderr)
            return 2
        target = args.output.expanduser().resolve()
        if path_under_work(target) and not args.scope_id:
            print("--snapshot output under _work requires --scope-id", file=sys.stderr)
            return 2
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            json.dumps(
                snapshot_tree(
                    args.scope_root or WORK_ROOT,
                    budget=InventoryBudget(
                        timeout_seconds=args.inventory_timeout_seconds,
                        max_items=args.inventory_max_items,
                    ),
                    include_hashes=False,
                    skip_retained=True,
                ),
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        if args.scope_id and path_under_work(target):
            register_artifact(
                artifact_id=f"cli:{args.scope_id}:{_rel_path(target)}",
                path=target,
                kind="runner_artifact",
                created_by="cleanup_work_artifacts.py",
                owner=args.owner,
                purpose=args.purpose,
                lifecycle=args.lifecycle,
                scope_id=args.scope_id,
                run_id=args.run_id or args.scope_id,
                scope_root=args.scope_root or WORK_ROOT,
            )
        snapshot = json.loads(target.read_text(encoding="utf-8"))
        return 0 if snapshot.get("complete", False) else 1
    if args.report_only:
        rep = _size_snapshot()
        print(json.dumps({"dev_gb": rep["dev_total_gb"], "work_gb": rep["work_total_gb"]}, indent=2))
        return 0
    before = None
    if args.before:
        before = json.loads(args.before.expanduser().resolve().read_text(encoding="utf-8"))
    try:
        result = cleanup_work(
            dry_run=args.dry_run,
            registered_only=args.registered_only,
            outcome=args.outcome,
            scope_id=args.scope_id,
            run_id=args.run_id,
            scope_root=args.scope_root,
            before=before,
            timeout_seconds=args.inventory_timeout_seconds,
            max_items=args.inventory_max_items,
        )
    except BaseException as exc:  # noqa: BLE001
        # A cleanup tool must still provide a terminal, machine-readable
        # fail-closed result if an unexpected filesystem/runtime error escapes
        # the bounded helpers.  In particular, never turn this into PASS or
        # attempt a best-effort deletion.
        result = {
            "schema_version": 3,
            "utc": utc_now(),
            "dry_run": bool(args.dry_run),
            "registered_only": bool(args.registered_only),
            "outcome": args.outcome,
            "status": "REVIEW_REQUIRED",
            "terminal_status": "FAIL",
            "ok": False,
            "before": {"work_total_gb": None},
            "after": None,
            "freed_gb": 0.0,
            "deleted": [],
            "blocked": [],
            "would_delete": [],
            "retained": [],
            "protected": [],
            "unknown": [],
            "missing": [],
            "locked": [],
            "errors": [{"reason": "cleanup_exception", "error": str(exc)}],
            "inventory_complete": False,
            "inventory": {
                "budget": {
                    "complete": False,
                    "status": "ERROR",
                    "reason": "cleanup_exception",
                    "error": str(exc),
                }
            },
            "evidence_copied": [],
        }
    if args.output:
        target = args.output.expanduser().resolve()
        if args.dry_run and path_under_work(target):
            print("--output for --dry-run must be outside _work", file=sys.stderr)
            return 2
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        if args.scope_id and path_under_work(target):
            register_artifact(
                artifact_id=f"cli:{args.scope_id}:{_rel_path(target)}",
                path=target,
                kind="runner_artifact",
                created_by="cleanup_work_artifacts.py",
                owner=args.owner,
                purpose=args.purpose,
                lifecycle="RETAINED",
                scope_id=args.scope_id,
                run_id=args.run_id or args.scope_id,
                scope_root=args.scope_root or WORK_ROOT,
            )
    print(json.dumps({
        "dry_run": result.get("dry_run", False),
        "status": result["status"],
        "terminal_status": result.get("terminal_status") or result["status"],
        "ok": result["ok"],
        "before_work_gb": result["before"]["work_total_gb"],
        "after_work_gb": result.get("after", {}).get("work_total_gb") if result.get("after") else None,
        "freed_gb": result.get("freed_gb"),
        "deleted_count": len(result.get("deleted") or []),
        "would_delete_count": len(result.get("would_delete") or []),
        "would_delete_sample": [
            {"path": item.get("path"), "bytes": item.get("bytes")}
            for item in (result.get("would_delete") or [])[:20]
        ],
        "blocked_count": len(result.get("blocked") or []),
        "blocked_sample": [
            {"path": item.get("path"), "reason": item.get("reason"), "blocking_id": item.get("blocking_id")}
            for item in (result.get("blocked") or [])[:20]
        ],
        "unknown_count": len(result.get("unknown") or []),
        "missing_count": len(result.get("missing") or []),
        "expected_missing_count": len(result.get("expected_missing") or []),
        "unexpected_missing_count": len(result.get("unexpected_missing") or []),
        "locked_count": len(result.get("locked") or []),
        "inventory_complete": result.get("inventory_complete", False),
        "inventory_status": result.get("inventory", {}).get("budget", {}).get("status"),
        "inventory_reason": result.get("inventory", {}).get("budget", {}).get("reason"),
    }, indent=2), flush=True)
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
