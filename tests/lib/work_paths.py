"""Canonical locations and lifecycle registry for test artifacts.

All workflow temp files go under tests/golden/_work/. An optional external
Unity fixture is supplied explicitly through ``VNTEXT_GAME_FOLDER``; a fresh
clone never infers a developer's game path.

The registry is deliberately small and additive.  Cleanup policy lives in
``tests/tools/cleanup_work_artifacts.py``; this module owns path safety,
registration and the test-facing lifecycle context manager.
"""

from __future__ import annotations

from contextlib import contextmanager
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path

LIB = Path(__file__).resolve().parent
TESTS = LIB.parent
ROOT = TESTS.parent
GOLDEN = TESTS / 'golden'
WORK_ROOT = GOLDEN / "_work"
ARTIFACT_NAMESPACE = hashlib.sha256(str(WORK_ROOT.resolve()).encode("utf-8")).hexdigest()[:12]
E2E_GAME_COPY = WORK_ROOT / "game_copy"
MANIFEST_PATH = WORK_ROOT / "artifacts_manifest.json"
MANIFEST_SCHEMA_VERSION = 2
RUN_OUTCOMES = frozenset(
    {
        "PASS",
        "FAIL",
        "TIMEOUT",
        "START_ERROR",
        "CANCELLED",
        "UNKNOWN",
        "PROVEN_BLOCKED",
        "PREMISE_INVALID",
        "PM_DECISION_REQUIRED",
    }
)

LIFECYCLE_STATES = frozenset(
    {
        "PROTECTED",
        "RETAINED",
        "DISPOSABLE",
        "UNKNOWN",
        "MISSING",
        "STALE",
    }
)
ACTIVE_LIFECYCLE_STATES = frozenset({"PROTECTED", "RETAINED", "DISPOSABLE", "UNKNOWN"})

# Evidence (reports, screenshots and logs) — not launchable game copies.
UNITY_E2E_EVIDENCE = WORK_ROOT / "unity_e2e"
UNITY_STAGING = WORK_ROOT / "unity_staging"
FILE_ROUNDTRIP_STAGING = WORK_ROOT / "file_roundtrip"

# External game fixtures are opt-in and must never be inferred from the host
# machine's drive layout. The default is a non-existent sentinel so a fresh
# clone can classify the fixture as unavailable.
_EXTERNAL_GAME_ROOT = Path(
    os.environ.get("VNTEXT_READ_ONLY_GAME_ROOT", str(Path.home() / "VNTextExternalGameFixture"))
).expanduser().resolve()

# Optional external Unity source, never a default tracked/test fixture.
GAME_FOLDER_PRIMARY = Path(
    os.environ.get("VNTEXT_GAME_FOLDER", str(_EXTERNAL_GAME_ROOT / "game"))
).expanduser()

DEV_ROOT = ROOT.resolve()
EXTERNAL_GAME_ROOT = _EXTERNAL_GAME_ROOT
UNTRUSTED_EXTERNAL_NAMES = ("fixture-copy-a", "fixture-copy-b", "fixture-copy-c")
# Unknown external games have no safe default list of files to reset.  Callers
# must provide explicit relative paths or request a full isolated reseed.
RESET_RELS: tuple[str, ...] = ()

PROTECTED_PATH_PREFIXES = (
    str((ROOT / "VNText_Output").resolve()),
    str((Path.home() / ".vnloc").resolve()),
    str((ROOT / "vntext").resolve()),
    str((ROOT / "specs").resolve()),
    str((ROOT / "docs").resolve()),
    str((ROOT / ".git").resolve()),
    str((ROOT / ".venv").resolve()),
)


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def new_scope_id(prefix: str = "scope") -> str:
    """Return a unique identifier for one isolated test/artifact scope."""

    safe = "".join(ch if ch.isalnum() or ch in "_-" else "_" for ch in str(prefix or "scope"))
    return f"{safe}-{uuid.uuid4().hex}"


def ambient_scope() -> dict[str, str]:
    """Read scope metadata propagated by a canonical runner."""

    scope_id = str(os.environ.get("VNTEXT_ARTIFACT_SCOPE_ID") or "legacy").strip()
    run_id = str(os.environ.get("VNTEXT_ARTIFACT_RUN_ID") or scope_id).strip()
    scope_root = str(os.environ.get("VNTEXT_ARTIFACT_SCOPE_ROOT") or WORK_ROOT).strip()
    return {"scope_id": scope_id, "run_id": run_id, "scope_root": scope_root}


def make_deletion_provenance(
    *,
    path: Path,
    reason: str,
    deleted_by: str,
    deleted_at: str | None = None,
    bytes_deleted: int = 0,
    evidence_source: str = "runtime_deletion",
    scope_id: str | None = None,
    run_id: str | None = None,
    scope_root: str | Path | None = None,
    deletion_result: str = "deleted",
) -> dict:
    """Build auditable proof for one owner-confirmed artifact deletion."""

    ambient = ambient_scope()
    resolved_scope_id = str(scope_id or ambient["scope_id"]).strip()
    resolved_run_id = str(run_id or ambient["run_id"]).strip()
    resolved_scope_root = str(Path(scope_root or ambient["scope_root"]).expanduser().resolve())
    if not str(reason or "").strip() or not str(deleted_by or "").strip():
        raise ValueError("deletion provenance requires reason and deleted_by")
    result = str(deletion_result or "").strip()
    if result not in {"deleted", "already_absent", "legacy_owner_confirmed_missing"}:
        raise ValueError(f"unknown deletion result: {result}")
    return {
        "schema_version": 1,
        "deleted_at": str(deleted_at or utc_now()),
        "deleted_by": str(deleted_by),
        "reason": str(reason),
        "path": str(Path(path).expanduser().resolve()),
        "bytes": max(0, int(bytes_deleted or 0)),
        "scope_id": resolved_scope_id,
        "run_id": resolved_run_id,
        "scope_root": resolved_scope_root,
        "evidence_source": str(evidence_source or "runtime_deletion"),
        "result": result,
    }


def ensure_work_root() -> Path:
    WORK_ROOT.mkdir(parents=True, exist_ok=True)
    return WORK_ROOT


def path_under_work(path: Path) -> bool:
    resolved = path.resolve()
    work = WORK_ROOT.resolve()
    return resolved == work or work in resolved.parents


def lifecycle_for_entry(entry: dict) -> str:
    """Read the v2 lifecycle, conservatively mapping the legacy ACTIVE flag."""

    raw = str(entry.get("lifecycle") or entry.get("state") or "").upper().strip()
    if raw in LIFECYCLE_STATES:
        return raw
    status = str(entry.get("status") or "").upper().strip()
    if status in LIFECYCLE_STATES:
        return status
    if status.startswith("STALE"):
        return "STALE"
    # Historical ACTIVE entries were retained by the old cleanup policy.  Do
    # not make them disposable merely because the field is ambiguous.
    if status == "ACTIVE":
        return "RETAINED"
    return "UNKNOWN"


def cleanup_target(path: Path, label: str = "cleanup target") -> Path:
    """Validate a deletion target without deleting or killing a process."""

    resolved = Path(path).expanduser().resolve()
    if not path_under_work(resolved):
        raise RuntimeError(f"{label} must stay under {WORK_ROOT}: {resolved}")
    if resolved == E2E_GAME_COPY.resolve() or E2E_GAME_COPY.resolve() in resolved.parents:
        raise RuntimeError(f"{label} must not touch protected game_copy: {resolved}")
    if path_under_external_game(resolved) or is_protected_path(resolved):
        raise RuntimeError(f"{label} is protected: {resolved}")
    return resolved


def path_under_dev(path: Path) -> bool:
    resolved = path.resolve()
    dev = DEV_ROOT
    return resolved == dev or dev in resolved.parents


def path_under_external_game(path: Path) -> bool:
    resolved = path.resolve()
    root = EXTERNAL_GAME_ROOT
    return resolved == root or root in resolved.parents


def external_reject_path(name: str) -> Path:
    """Return an external fixture path used only to prove write rejection."""
    if name not in UNTRUSTED_EXTERNAL_NAMES:
        raise ValueError(f"unknown external fixture name: {name}")
    return EXTERNAL_GAME_ROOT / name


def assert_write_destination(path: Path, label: str) -> Path:
    """All test writes stay in the repository, never under an external game root."""
    resolved = path.resolve()
    if path_under_external_game(resolved):
        raise RuntimeError(f"{label} must not write under the read-only external game root: {resolved}")
    temp_root = Path(tempfile.gettempdir()).resolve()
    if path_under_dev(temp_root) and temp_root in resolved.parents:
        raise RuntimeError(f"{label} must not write under system temp: {resolved}")
    if not path_under_dev(resolved):
        raise RuntimeError(f"{label} must stay under DEV repo {DEV_ROOT}: {resolved}")
    return resolved


def assert_artifact_under_work(path: Path, label: str) -> Path:
    assert_write_destination(path, label)
    resolved = path.resolve()
    if not path_under_work(resolved):
        raise RuntimeError(f"{label} must live under {WORK_ROOT}: {resolved}")
    return resolved


def resolve_game_folder() -> Path:
    """Return the explicitly configured external Unity source folder."""
    primary = GAME_FOLDER_PRIMARY
    if primary.is_dir():
        return primary.resolve()
    raise RuntimeError(f"external Unity fixture not found at {primary}; set VNTEXT_GAME_FOLDER to opt in")


def assert_e2e_copy_separate_from_source(copy: Path, orig: Path, *, label: str = "E2E game copy") -> None:
    """An external fixture copy must stay isolated under ``_work/game_copy``."""
    copy_r = copy.resolve()
    orig_r = orig.resolve()
    if copy_r == orig_r:
        raise RuntimeError(f"{label} must not equal original game: {orig_r}")
    if orig_r in copy_r.parents:
        raise RuntimeError(f"{label} must not be inside original game: {copy_r}")
    assert_artifact_under_work(copy_r, label)
    if copy_r.parent == orig_r.parent:
        raise RuntimeError(f"{label} must not be sibling of the original fixture: {copy_r}")
    if copy_r != E2E_GAME_COPY.resolve():
        raise RuntimeError(f"{label} must be the canonical {E2E_GAME_COPY}, got {copy_r}")


def dir_size_bytes(path: Path) -> int:
    if not path.exists():
        return 0
    if path.is_file():
        return path.stat().st_size
    total = 0
    for child in path.rglob("*"):
        if child.is_file():
            total += child.stat().st_size
    return total


def _load_manifest() -> dict:
    if not os.path.lexists(MANIFEST_PATH):
        return {"version": MANIFEST_SCHEMA_VERSION, "schema_version": MANIFEST_SCHEMA_VERSION, "updated_at": utc_now(), "artifacts": []}
    try:
        info = MANIFEST_PATH.lstat()
        attributes = int(getattr(info, "st_file_attributes", 0))
        if (
            stat.S_ISLNK(info.st_mode)
            or attributes & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
            or not stat.S_ISREG(info.st_mode)
        ):
            raise ValueError(f"artifact registry is not a regular file: {MANIFEST_PATH}")
        doc = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"artifact registry is unreadable or malformed: {MANIFEST_PATH}") from exc
    if (
        not isinstance(doc, dict)
        or not isinstance(doc.get("artifacts", []), list)
        or ("archive" in doc and not isinstance(doc["archive"], list))
    ):
        raise ValueError(f"artifact registry structure is invalid: {MANIFEST_PATH}")
    return doc


def _save_manifest(doc: dict) -> None:
    ensure_work_root()
    doc.setdefault("version", MANIFEST_SCHEMA_VERSION)
    doc.setdefault("schema_version", MANIFEST_SCHEMA_VERSION)
    doc["updated_at"] = utc_now()
    MANIFEST_PATH.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def register_artifact(
    *,
    artifact_id: str,
    path: Path,
    kind: str,
    created_by: str,
    purpose: str,
    status: str = "ACTIVE",
    lifecycle: str | None = None,
    owner: str = "",
    scope_id: str | None = None,
    run_id: str | None = None,
    scope_root: str | Path | None = None,
    provenance: dict | None = None,
    size_bytes: int | None = None,
) -> dict:
    return register_artifacts(
        [{
            "artifact_id": artifact_id,
            "path": path,
            "kind": kind,
            "created_by": created_by,
            "purpose": purpose,
            "status": status,
            "lifecycle": lifecycle,
            "owner": owner,
            "scope_id": scope_id,
            "run_id": run_id,
            "scope_root": scope_root,
            "provenance": provenance,
            "size_bytes": size_bytes,
        }]
    )[0]


def register_artifacts(registrations: list[dict]) -> list[dict]:
    """Upsert related artifact records with one registry read and write."""

    if not registrations:
        return []
    ambient = ambient_scope()
    prepared: dict[str, dict] = {}
    order: list[str] = []
    for registration in registrations:
        values = dict(registration)
        artifact_id = str(values.get("artifact_id") or "").strip()
        resolved = Path(values.get("path") or "").expanduser().resolve()
        assert_artifact_under_work(resolved, f"artifact {artifact_id}")
        if not artifact_id:
            raise ValueError("artifact_id is required")
        created_by = str(values.get("created_by") or "").strip()
        owner = str(values.get("owner") or created_by).strip()
        purpose = str(values.get("purpose") or "").strip()
        if not created_by or not owner or not purpose:
            raise ValueError("artifact registration requires created_by, owner and purpose")
        requested = str(values.get("lifecycle") or values.get("status") or "UNKNOWN").upper().strip()
        if requested == "ACTIVE":
            requested = "PROTECTED" if resolved == E2E_GAME_COPY.resolve() else "RETAINED"
        if requested not in LIFECYCLE_STATES:
            raise ValueError(f"unknown artifact lifecycle: {requested}")
        scope_id = str(values.get("scope_id") or ambient["scope_id"]).strip()
        run_id = str(values.get("run_id") or ambient["run_id"]).strip()
        scope_root = str(Path(values.get("scope_root") or ambient["scope_root"]).expanduser().resolve())
        provenance = dict(values.get("provenance") or {})
        provenance.setdefault("scope_id", scope_id)
        provenance.setdefault("run_id", run_id)
        provenance.setdefault("scope_root", scope_root)
        provenance.setdefault("registered_by", created_by)
        if not scope_id or not run_id or not scope_root or not provenance.get("registered_by"):
            raise ValueError("artifact registration requires scope/run provenance")
        size_bytes = values.get("size_bytes")
        byte_count = (
            max(0, int(size_bytes))
            if size_bytes is not None
            else (dir_size_bytes(resolved) if resolved.exists() else 0)
        )
        if artifact_id in prepared:
            raise ValueError(f"duplicate artifact id in batch: {artifact_id}")
        order.append(artifact_id)
        prepared[artifact_id] = {
            "id": artifact_id,
            "path": str(resolved),
            "kind": values.get("kind"),
            "created_by": created_by,
            "owner": owner,
            "purpose": purpose,
            "created_at": utc_now(),
            "bytes": byte_count,
            "status": "ACTIVE" if requested in ACTIVE_LIFECYCLE_STATES else requested,
            "lifecycle": requested,
            "scope_id": scope_id,
            "run_id": run_id,
            "scope_root": scope_root,
            "provenance": provenance,
        }

    doc = _load_manifest()
    existing = list(doc.get("artifacts", []))
    existing_by_id: dict[str, list[dict]] = {}
    for item in existing:
        if item.get("id"):
            existing_by_id.setdefault(str(item["id"]), []).append(item)
    for artifact_id, entry in prepared.items():
        previous = existing_by_id.get(artifact_id, [])
        for item in previous:
            old_path = str(item.get("path") or "").strip()
            if old_path and Path(old_path).expanduser().resolve() != Path(entry["path"]):
                raise ValueError(f"artifact id already belongs to another path: {artifact_id}")
        if previous:
            entry["created_at"] = previous[0].get("created_at") or entry["created_at"]

    doc["artifacts"] = [
        prepared.get(str(item.get("id")), item)
        for item in existing
    ] + [prepared[artifact_id] for artifact_id in order if artifact_id not in existing_by_id]
    _save_manifest(doc)
    return [prepared[artifact_id] for artifact_id in order]


def set_artifact_status(artifact_id: str, status: str, **extra) -> None:
    lifecycle = str(extra.pop("lifecycle", status) or "UNKNOWN").upper().strip()
    if lifecycle not in LIFECYCLE_STATES:
        raise ValueError(f"unknown artifact lifecycle: {lifecycle}")
    doc = _load_manifest()
    found = False
    for item in doc.get("artifacts", []):
        if item.get("id") == artifact_id:
            if "path" in extra:
                resolved = assert_artifact_under_work(Path(str(extra["path"])), f"artifact {artifact_id}")
                extra["path"] = str(resolved)
            if "owner" in extra and not str(extra["owner"] or "").strip():
                raise ValueError("artifact status update cannot clear owner")
            if "purpose" in extra and not str(extra["purpose"] or "").strip():
                raise ValueError("artifact status update cannot clear purpose")
            item["status"] = "ACTIVE" if lifecycle in ACTIVE_LIFECYCLE_STATES else lifecycle
            item["lifecycle"] = lifecycle
            item["updated_at"] = utc_now()
            item.setdefault("owner", str(item.get("created_by") or "legacy"))
            item.setdefault("purpose", "state update; review required")
            ambient = ambient_scope()
            item.setdefault("scope_id", ambient["scope_id"])
            item.setdefault("run_id", ambient["run_id"])
            item.setdefault("scope_root", ambient["scope_root"])
            item.setdefault(
                "provenance",
                {
                    "scope_id": item["scope_id"],
                    "run_id": item["run_id"],
                    "scope_root": item["scope_root"],
                    "registered_by": str(item.get("created_by") or "legacy"),
                },
            )
            item.update(extra)
            found = True
            break
    if not found:
        raise KeyError(f"cannot update unregistered artifact: {artifact_id}")
    _save_manifest(doc)


def mark_artifacts_missing_under(
    root: Path,
    *,
    purpose: str = "",
    deletion_provenance: dict | None = None,
    allow_e2e_game_copy: bool = False,
) -> int:
    """Mark registered records below a successfully removed work path terminal."""

    resolved_root = Path(root).expanduser().resolve()
    assert_artifact_under_work(resolved_root, "mark missing artifacts")
    if (
        not allow_e2e_game_copy
        and (resolved_root == E2E_GAME_COPY.resolve() or E2E_GAME_COPY.resolve() in resolved_root.parents)
    ):
        raise RuntimeError(f"mark missing artifacts must not touch protected game_copy: {resolved_root}")
    doc = _load_manifest()
    changed = 0
    for item in doc.get("artifacts", []):
        raw_path = str(item.get("path") or "").strip()
        if not raw_path:
            continue
        candidate = Path(raw_path).expanduser().resolve()
        if candidate != resolved_root and resolved_root not in candidate.parents:
            continue
        if candidate.exists():
            continue
        item["status"] = "MISSING"
        item["lifecycle"] = "MISSING"
        item["bytes"] = 0
        item["updated_at"] = utc_now()
        if purpose:
            item["purpose"] = purpose
        if deletion_provenance:
            proof = dict(deletion_provenance)
            proof["path"] = str(candidate)
            item["deletion_provenance"] = proof
        changed += 1
    if changed:
        _save_manifest(doc)
    return changed


def is_protected_path(path: Path) -> bool:
    # Inventory calls this for every directory in _work.  Path.resolve() does
    # a Windows final-path lookup and can block on a stale/reparse path.  The
    # cleanup caller never follows symlinks, so use a lexical absolute path for
    # ordinary entries and resolve only an entry that is itself a link.
    raw = os.path.abspath(os.fspath(path))
    resolved = os.path.normcase(raw)
    try:
        if os.path.islink(raw):
            resolved = os.path.normcase(os.path.realpath(raw))
    except OSError:
        # A path that cannot be inspected is not silently treated as
        # protected; the inventory records the scan error and fails closed.
        resolved = os.path.normcase(raw)
    name = os.path.basename(raw)
    if name == "__pycache__":
        return False
    e2e = os.path.normcase(os.path.abspath(os.fspath(E2E_GAME_COPY)))
    if resolved == e2e or resolved.startswith(e2e + os.sep):
        return True
    for prefix in PROTECTED_PATH_PREFIXES:
        protected = os.path.normcase(os.path.abspath(os.fspath(prefix)))
        if resolved == protected or resolved.startswith(protected + os.sep):
            return True
    return False


def configured_game_processes(process_name: str | None = None) -> list[dict]:
    """List processes by one exact executable name, never by a broad search."""
    process_name = str(
        process_name if process_name is not None else os.environ.get("VNTEXT_GAME_PROCESS_NAME") or ""
    ).strip()
    if not process_name:
        return []
    if not re.fullmatch(r"[A-Za-z0-9_. -]+", process_name):
        raise RuntimeError(f"unsafe game process name: {process_name!r}")
    process_stem = Path(process_name).stem
    cmd = [
        "powershell",
        "-NoProfile",
        "-Command",
        f"$name='{process_stem}'; Get-Process -Name $name -ErrorAction SilentlyContinue | "
        "Select-Object Id, Path | ConvertTo-Json -Compress; exit 0",
    ]
    try:
        raw = subprocess.check_output(cmd, text=True, stderr=subprocess.DEVNULL)
    except (subprocess.CalledProcessError, FileNotFoundError):
        raise RuntimeError(f"unable to verify whether {process_name} is running")
    raw = (raw or "").strip()
    if not raw:
        return []
    data = json.loads(raw)
    if isinstance(data, dict):
        data = [data]
    out = []
    for item in data:
        exe = str(item.get("Path") or "")
        pid = item.get("Id")
        if pid:
            out.append({"pid": int(pid), "exe": exe})
    return out


def kill_processes_using(copy: Path) -> list[int]:
    """Legacy name: verify the copy is idle; never terminate its process."""
    active = processes_using(copy)
    if active:
        raise RuntimeError(f"game copy still in use: {copy} ({active})")
    return []


def processes_using(copy: Path) -> list[dict]:
    copy_res = str(copy.resolve()).lower()
    names = sorted(path.name for path in copy.glob("*.exe") if path.is_file())
    return [
        proc
        for name in names
        for proc in configured_game_processes(name)
        if not proc.get("exe") or str(proc.get("exe")).lower().startswith(copy_res)
    ]


def _robocopy(src: Path, dest: Path, *, label: str = "robocopy") -> None:
    safe_robocopy(src, dest, label=label)


def safe_robocopy(src: Path, dest: Path, *, label: str) -> None:
    assert_write_destination(dest, label)
    orig = resolve_game_folder()
    dest_r = dest.resolve()
    orig_r = orig.resolve()
    if dest_r == orig_r or orig_r in dest_r.parents:
        raise RuntimeError(f"{label} must not robocopy into original game: {dest_r}")
    dest.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "robocopy",
        str(src),
        str(dest),
        "/E",
        "/NFL",
        "/NDL",
        "/NJH",
        "/NJS",
        "/nc",
        "/ns",
        "/np",
        "/R:2",
        "/W:2",
    ]
    code = subprocess.call(cmd)
    if code >= 8:
        raise RuntimeError(f"robocopy failed with code {code} for {label}")


def assert_writable_game_copy(game: Path, label: str) -> Path:
    """Ensure writes target the canonical E2E copy, never the original game."""
    orig = resolve_game_folder()
    assert_e2e_copy_separate_from_source(game, orig, label=label)
    return game.resolve()


def install_patch_to_game_copy(game: Path, patch_copy_root: Path, *, label: str) -> list[str]:
    """Install COPY_TO_GAME_ROOT into canonical E2E game copy only."""
    assert_writable_game_copy(game, label)
    if not patch_copy_root.is_dir():
        raise RuntimeError(f"{label} missing patch root: {patch_copy_root}")
    safe_robocopy(patch_copy_root, game, label=label)
    return [
        str(p.relative_to(patch_copy_root)).replace("\\", "/")
        for p in patch_copy_root.rglob("*")
        if p.is_file()
    ]


def reset_copy_files(copy: Path, orig: Path, rels: list[str] | None = None) -> list[str]:
    assert_writable_game_copy(copy, "reset_copy_files")
    if rels is None:
        if copy.exists():
            shutil.rmtree(copy)
        _robocopy(orig, copy, label="reset_copy_files full reseed")
        return ["<entire external fixture>"]
    restored = []
    for rel in rels:
        src = orig / rel
        dest = copy / rel
        if not src.is_file():
            continue
        assert_write_destination(dest, f"reset_copy_files {rel}")
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
        restored.append(rel)
    return restored


def _find_game_executable(root: Path) -> Path | None:
    """Find an external Unity executable without assuming a title name."""
    return next((path for path in sorted(root.glob("*.exe")) if path.is_file()), None)


def prepare_e2e_game_copy(*, label: str, mode: str = "fresh") -> Path:
    """Seed a new canonical E2E copy; ``reset`` remains a fresh-copy alias."""
    if mode not in {"fresh", "reset"}:
        raise ValueError("game E2E copies cannot be reused across test runs")
    orig = resolve_game_folder()
    dest = E2E_GAME_COPY
    from unity_patch_baseline import assert_path_outside_game

    assert_path_outside_game(dest, orig, f"{label} E2E game copy")
    assert_e2e_copy_separate_from_source(dest, orig, label=f"{label} E2E game copy")
    ensure_work_root()
    if dest.exists():
        dispose_e2e_game_copy(reason=f"{label}: dispose prior copy before fresh seed")
    _robocopy(orig, dest, label=f"{label} fresh seed")
    exe = _find_game_executable(dest)
    if exe is None:
        raise RuntimeError(f"{label} missing exe after seed: {dest}")

    orig_exe = _find_game_executable(orig)
    if orig_exe is not None and exe is not None and orig_exe.resolve() == exe.resolve():
        raise RuntimeError("refusing to use original exe as E2E copy")
    register_artifact(
        artifact_id="e2e_game_copy",
        path=dest,
        kind="e2e_game_copy",
        created_by=label,
        purpose="single shared E2E game copy",
        status="ACTIVE",
    )
    return dest


def dispose_e2e_game_copy(*, reason: str) -> bool:
    """Dispose the canonical copy under the owner-controlled E2E lifecycle.

    Generic cleanup deliberately rejects ``game_copy`` as protected.  This
    explicit owner path is the only exception: it requires the canonical
    path, checks the configured game process guard, removes only the copy, and
    records the terminal ``MISSING`` state.  It never infers permission to
    delete an external source fixture or an arbitrary descendant.
    """
    dest = E2E_GAME_COPY
    if not dest.exists():
        try:
            set_artifact_status(
                "e2e_game_copy",
                "MISSING",
                lifecycle="MISSING",
                path=str(dest),
                purpose=reason,
                bytes=0,
            )
        except KeyError:
            register_artifact(
                artifact_id="e2e_game_copy",
                path=dest,
                kind="e2e_game_copy",
                created_by="dispose_e2e_game_copy",
                owner="work_paths",
                purpose=reason,
                lifecycle="MISSING",
            )
        return False
    assert_artifact_under_work(dest, "dispose E2E game copy")
    if not any(
        item.get("id") == "e2e_game_copy"
        and Path(str(item.get("path") or "")).expanduser().resolve() == dest.resolve()
        for item in _load_manifest().get("artifacts", [])
    ):
        raise RuntimeError(f"refusing to dispose unregistered game copy: {dest}")
    if processes_using(dest):
        raise RuntimeError(f"game copy still in use: {dest}")
    size = dir_size_bytes(dest)
    shutil.rmtree(dest)
    proof = make_deletion_provenance(
        path=dest,
        reason=reason,
        deleted_by="dispose_e2e_game_copy",
        bytes_deleted=size,
        evidence_source="owner_controlled_e2e_disposal",
    )
    set_artifact_status(
        "e2e_game_copy",
        "MISSING",
        lifecycle="MISSING",
        path=str(dest),
        purpose=reason,
        bytes=size,
        deletion_provenance=proof,
    )
    mark_artifacts_missing_under(
        dest,
        purpose=reason,
        deletion_provenance=proof,
        allow_e2e_game_copy=True,
    )
    return True


def work_temp_dir(name: str, *, scope_id: str | None = None, run_id: str | None = None) -> Path:
    ambient = ambient_scope()
    requested_scope = str(scope_id or ambient["scope_id"]).strip()
    unique_scope = requested_scope if requested_scope != "legacy" else new_scope_id("temp")
    scope_id = unique_scope
    run_id = str(run_id or (ambient["run_id"] if ambient["run_id"] != "legacy" else unique_scope)).strip()
    temp_root = WORK_ROOT / "tmp"
    register_artifact(
        artifact_id=f"work_temp_root:{ARTIFACT_NAMESPACE}",
        path=temp_root,
        kind="test_temp_root",
        created_by="work_temp_dir",
        owner="work_temp_dir",
        purpose="retained root for canonical temporary workspaces",
        lifecycle="RETAINED",
        scope_id=scope_id,
        run_id=run_id,
    )
    container = temp_root / name
    register_artifact(
        artifact_id=f"work_temp_container:{ARTIFACT_NAMESPACE}:{name}",
        path=container,
        kind="test_temp_container",
        created_by="work_temp_dir",
        owner="work_temp_dir",
        purpose=f"retained container for temporary workspaces named {name}",
        lifecycle="RETAINED",
        scope_id=scope_id,
        run_id=run_id,
    )
    dest = container / unique_scope
    assert_artifact_under_work(dest, name)
    dest.mkdir(parents=True, exist_ok=True)
    register_artifact(
        artifact_id=f"work_temp:{unique_scope}:{name}",
        path=dest,
        kind="test_temp",
        created_by="work_temp_dir",
        owner="work_temp_dir",
        purpose=f"temporary workspace for {name}",
        lifecycle="DISPOSABLE",
        scope_id=unique_scope,
        run_id=run_id,
    )
    return dest


@contextmanager
def artifact_scope(
    path: Path,
    *,
    artifact_id: str,
    kind: str,
    owner: str,
    purpose: str,
):
    """Register a disposable artifact and remove it after every body outcome.

    The original exception is re-raised after cleanup.  Cleanup failure raises
    instead, chained from that exception, so a runner cannot hide the failure.
    """

    resolved = assert_artifact_under_work(Path(path), f"artifact {artifact_id}")
    ambient = ambient_scope()
    scope_id = ambient["scope_id"] if ambient["scope_id"] != "legacy" else new_scope_id(f"artifact-{artifact_id}")
    run_id = ambient["run_id"] if ambient["run_id"] != "legacy" else scope_id
    register_artifact(
        artifact_id=artifact_id,
        path=resolved,
        kind=kind,
        created_by=owner,
        owner=owner,
        purpose=purpose,
        lifecycle="DISPOSABLE",
        scope_id=scope_id,
        run_id=run_id,
    )
    # Avoid a module-level import cycle: cleanup_work_artifacts imports this
    # module for the path/registry primitives.
    from cleanup_work_artifacts import cleanup_after_test

    try:
        yield resolved
    except BaseException as exc:
        if isinstance(exc, (TimeoutError, subprocess.TimeoutExpired)):
            outcome = "TIMEOUT"
        elif isinstance(exc, (KeyboardInterrupt, GeneratorExit)):
            outcome = "CANCELLED"
        else:
            outcome = "FAIL"
        report = cleanup_after_test(
            [resolved],
            reason=f"artifact_scope:{artifact_id}",
            outcome=outcome,
            scope_id=scope_id,
            run_id=run_id,
        )
        if not report.get("ok", False) or os.path.lexists(resolved):
            raise RuntimeError(f"artifact cleanup failed for {artifact_id}: {report}") from exc
        raise
    else:
        report = cleanup_after_test(
            [resolved],
            reason=f"artifact_scope:{artifact_id}",
            outcome="PASS",
            scope_id=scope_id,
            run_id=run_id,
        )
        if report.get("ok", False):
            set_artifact_status(artifact_id, "MISSING", lifecycle="MISSING", purpose=purpose)
        if not report.get("ok", False):
            raise RuntimeError(f"artifact cleanup failed for {artifact_id}: {report}")
