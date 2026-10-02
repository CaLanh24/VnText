"""Run a canonical test command and finalize its registered artifacts.

Usage:
    python tests/tools/run_with_cleanup.py --report report.json -- <command> <args...>

The child owns registration through ``work_paths.register_artifact`` or
``artifact_scope``. Unregistered roots are UNKNOWN and are never deleted. A
canonical game copy and exact registered DISPOSABLE outputs are cleaned after
the child exits, regardless of test outcome; compact Markdown evidence remains.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import signal
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


HERE = Path(__file__).resolve()
ROOT = HERE.parents[2]
MAX_SUMMARY_BYTES = 256 * 1024
sys.path[:0] = [str(HERE.parent), str(ROOT / "tests" / "lib")]

from cleanup_work_artifacts import (  # noqa: E402
    InventoryBudget,
    finalize_scope,
    snapshot_tree,
)
from work_paths import (  # noqa: E402
    E2E_GAME_COPY,
    WORK_ROOT,
    assert_artifact_under_work,
    dispose_e2e_game_copy,
    new_scope_id,
    register_artifact,
    register_artifacts,
)


def _request_stop(proc: subprocess.Popen) -> bool:
    """Request normal child shutdown; never escalate to process kill."""

    if proc.poll() is not None:
        return True
    try:
        proc.send_signal(signal.CTRL_BREAK_EVENT if os.name == "nt" else signal.SIGTERM)
        proc.wait(timeout=3)
    except (OSError, subprocess.TimeoutExpired, ValueError):
        return proc.poll() is not None
    return proc.poll() is not None


def _source_sha() -> str:
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


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _runner_path_id(path: Path) -> str:
    identity = os.path.normcase(os.path.abspath(os.fspath(path.resolve())))
    return f"runner-retained-path:{hashlib.sha256(identity.encode('utf-8')).hexdigest()[:32]}"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def _register_retained_path(
    path: Path,
    *,
    kind: str,
    purpose: str,
    scope_id: str,
    run_id: str,
) -> Path:
    resolved = path.expanduser().resolve()
    assert_artifact_under_work(resolved, purpose)
    register_artifact(
        artifact_id=_runner_path_id(resolved),
        path=resolved,
        kind=kind,
        created_by="run_with_cleanup.py",
        owner="run_with_cleanup.py",
        purpose=purpose,
        lifecycle="RETAINED",
        scope_id=scope_id,
        run_id=run_id,
        scope_root=WORK_ROOT,
    )
    return resolved


def _register_disposable_path(path: Path, *, kind: str, purpose: str,
                              scope_id: str, run_id: str) -> Path:
    resolved = path.expanduser().resolve()
    assert_artifact_under_work(resolved, purpose)
    register_artifact(
        artifact_id=_runner_path_id(resolved),
        path=resolved,
        kind=kind,
        created_by="run_with_cleanup.py",
        owner="run_with_cleanup.py",
        purpose=purpose,
        lifecycle="DISPOSABLE",
        scope_id=scope_id,
        run_id=run_id,
        scope_root=WORK_ROOT,
    )
    return resolved


def _register_retained_tree(root: Path, *, scope_id: str, run_id: str) -> None:
    """Register a retained output tree once, using stable IDs per physical path."""

    resolved_root = root.expanduser().resolve()
    if not resolved_root.exists():
        return
    paths = sorted(
        resolved_root.rglob("*"),
        key=lambda item: (len(item.parts), str(item).casefold()),
        reverse=True,
    )
    records = []
    sizes: dict[Path, int] = {}
    for path in paths:
        resolved = path.resolve()
        assert_artifact_under_work(resolved, "explicit retained canonical build output")
        relative = resolved.relative_to(resolved_root).as_posix()
        if resolved.is_file():
            size_bytes = resolved.stat().st_size
        else:
            size_bytes = sizes.get(resolved, 0)
        sizes[resolved.parent] = sizes.get(resolved.parent, 0) + size_bytes
        sizes[resolved] = size_bytes
        records.append({
            "artifact_id": _runner_path_id(resolved),
            "path": resolved,
            "kind": "runner_output_directory" if resolved.is_dir() else "runner_output_file",
            "created_by": "run_with_cleanup.py",
            "owner": "run_with_cleanup.py",
            "purpose": "concrete output under explicit retained canonical build or gate root",
            "lifecycle": "RETAINED",
            "scope_id": scope_id,
            "run_id": run_id,
            "scope_root": WORK_ROOT,
            "provenance": {"retained_root": str(resolved_root), "relative_path": relative},
            "size_bytes": size_bytes,
        })
    register_artifacts(records)


def _primary_output_record(path: Path | None) -> dict | None:
    if path is None or not path.is_file():
        return None
    return {
        "path": str(path),
        "bytes": path.stat().st_size,
        "sha256": _sha256(path),
    }


def _output_excerpt(path: Path | None, *, limit: int = 1800) -> str:
    if path is None or not path.is_file():
        return ""
    try:
        with path.open("rb") as handle:
            handle.seek(max(0, path.stat().st_size - limit))
            raw = handle.read(limit)
        text = raw.decode("utf-8", errors="replace")
        return text[-limit:].strip()
    except OSError as exc:
        return f"<output unreadable: {exc}>"


def _markdown_run_report(result: dict) -> str:
    cleanup = result.get("cleanup") or {}
    project_size = cleanup.get("project_size") or {}
    before = project_size.get("before") or {}
    after = project_size.get("after") or {}
    lines = [
        "# Canonical test run",
        "",
        f"- Outcome: `{result.get('outcome')}`",
        f"- Child exit code: `{result.get('child_exit_code')}`",
        f"- Cleanup status: `{cleanup.get('cleanup_status', cleanup.get('status'))}`",
        f"- Source SHA: `{result.get('source_sha')}`",
        f"- Command: `{subprocess.list2cmdline(result.get('command') or [])}`",
        f"- Child error: `{str(result.get('child_error') or 'none')[:1000]}`",
        f"- Child process state: `{result.get('child_process_state')}` (pid `{result.get('child_pid')}`)",
        f"- Project bytes before/after: `{before.get('non_exempt_bytes')}` / `{after.get('non_exempt_bytes')}` (limit `{after.get('limit_bytes')}`)",
        "- Exempt paths:",
    ]
    for entry in after.get("exemptions", []):
        lines.append(f"  - `{entry['path']}`: {entry['bytes']} bytes; {entry['reason']}")
    summary = result.get("test_summary") or {}
    lines.extend([
        "",
        "## Test summary",
        "",
        f"- Status: `{summary.get('status')}`; tests `{summary.get('tests')}`; failures `{summary.get('failures')}`; errors `{summary.get('errors')}`; skips `{summary.get('skips')}`; warnings `{summary.get('warnings')}`",
        f"- Summary line: `{summary.get('terminal_line') or 'not available'}`",
        f"- Parsed output bytes: `{summary.get('input_bytes')}`; truncated to bounded tail: `{summary.get('input_truncated')}`",
    ])
    for item in (summary.get("skip_reasons") or [])[:20]:
        lines.append(f"- Skip: `{item.get('test')}` — {str(item.get('reason') or '')[:400]}")
    for item in (summary.get("warning_records") or [])[:20]:
        lines.append(f"- Warning: `{item.get('location')}` `{item.get('category')}` — {str(item.get('message') or '')[:400]}")
    for item in (summary.get("failure_records") or [])[:100]:
        lines.extend([
            "",
            f"### {item.get('kind')}: `{item.get('test')}`",
            "",
            "```text",
            str(item.get("details") or "")[:650],
            "```",
        ])
    for name, label in (("stdout_excerpt", "stdout"), ("stderr_excerpt", "stderr")):
        excerpt = str(result.get(name) or "")
        lines.extend(["", f"## {label} excerpt", "", "```text", excerpt or "(empty)", "```"])
    deleted = [item for item in cleanup.get("deleted", []) if item.get("deleted")]
    blocked = [item for item in cleanup.get("blocked", []) if item.get("path")]
    blocked.extend(
        item for item in cleanup.get("deleted", [])
        if item.get("skipped") and item.get("path")
    )
    locked = cleanup.get("locked", [])
    cleanup_errors = cleanup.get("errors", [])
    lines.extend(["", "## Cleanup", "", f"- Deleted roots: {len(deleted)}"])
    for item in deleted[:20]:
        lines.append(f"  - `{item.get('path')}`: {item.get('bytes', 0)} bytes")
    lines.append(f"- Cleanup status: `{cleanup.get('cleanup_status', cleanup.get('status'))}`; blocked roots: {len(blocked)}; locked roots: {len(locked)}; errors: {len(cleanup_errors)}")
    for item in (blocked + locked + cleanup_errors)[:30]:
        detail = item.get("error") or item.get("details") or item.get("reason") or "unspecified cleanup blocker"
        if item.get("pid") is not None:
            detail = f"{detail}; pid={item['pid']}"
        lines.append(f"  - `{item.get('path') or item.get('reason')}`: {detail}")
    return "\n".join(lines) + "\n"


def _parse_unittest_summary(stdout_path: Path | None, stderr_path: Path | None) -> dict:
    chunks: list[str] = []
    input_bytes = 0
    input_truncated = False
    for path in (stdout_path, stderr_path):
        if path is not None and path.is_file():
            try:
                size = path.stat().st_size
                input_bytes += size
                input_truncated = input_truncated or size > MAX_SUMMARY_BYTES
                with path.open("rb") as handle:
                    handle.seek(max(0, size - MAX_SUMMARY_BYTES))
                    chunks.append(handle.read(MAX_SUMMARY_BYTES).decode("utf-8", errors="replace"))
            except OSError as exc:
                chunks.append(f"<summary input unreadable: {type(exc).__name__}: {exc}>")
    if not chunks:
        return {
            "status": "NOT_CAPTURED",
            "tests": None,
            "failures": None,
            "errors": None,
            "skips": None,
            "warnings": None,
            "skip_reasons": [],
            "warning_records": [],
            "failure_records": [],
            "input_bytes": 0,
            "input_truncated": False,
        }
    raw = "\n".join(chunks)
    ran_matches = list(re.finditer(r"^Ran\s+(\d+)\s+tests?\s+in\s+.+$", raw, re.MULTILINE))
    terminal_matches = list(re.finditer(r"^(OK(?:\s*\([^\r\n]*\))?|FAILED\s*\([^\r\n]*\))\s*$", raw, re.MULTILINE))
    skip_records = [
        {"test": match.group(1).strip(), "reason": match.group(2)}
        for match in re.finditer(r"^(.*?)\s+\.\.\.\s+skipped\s+['\"](.*?)['\"]\s*$", raw, re.MULTILINE)
    ]
    warning_records = [
        {"location": match.group(1).strip(), "category": match.group(2), "message": match.group(3).strip()}
        for match in re.finditer(r"^(.+?):\s*([A-Za-z_][A-Za-z0-9_]*Warning):\s*(.*)$", raw, re.MULTILINE)
    ]
    failure_records = []
    failure_matches = list(re.finditer(r"^(FAIL|ERROR):\s*(.+)$", raw, re.MULTILINE))
    for match in failure_matches[:100]:
        next_section = re.search(r"^={5,}\s*$", raw[match.end():], re.MULTILINE)
        end = match.end() + next_section.start() if next_section else min(len(raw), match.end() + 1000)
        detail = raw[match.end():end].strip()
        if len(detail) > 650:
            detail = detail[:140] + "\n... traceback excerpt ...\n" + detail[-490:]
        failure_records.append({
            "kind": match.group(1),
            "test": match.group(2).strip(),
            "details": detail,
        })
    if not ran_matches or not terminal_matches:
        return {
            "status": "NOT_UNITTEST",
            "tests": None,
            "failures": None,
            "errors": None,
            "skips": None,
            "warnings": len(warning_records),
            "skip_reasons": skip_records,
            "warning_records": warning_records,
            "failure_records": failure_records,
            "input_bytes": input_bytes,
            "input_truncated": input_truncated,
        }
    terminal = terminal_matches[-1].group(1)

    def count(label: str) -> int:
        match = re.search(rf"\b{label}=(\d+)\b", terminal)
        return int(match.group(1)) if match else 0

    return {
        "status": "PASS" if terminal.startswith("OK") else "FAIL",
        "terminal_line": terminal,
        "tests": int(ran_matches[-1].group(1)),
        "failures": count("failures"),
        "errors": count("errors"),
        "skips": count("skipped"),
        "warnings": len(warning_records),
        "skip_reasons": skip_records,
        "warning_records": warning_records,
        "failure_records": failure_records,
        "input_bytes": input_bytes,
        "input_truncated": input_truncated,
    }



def _register_runner_report(report_path: Path, *, scope_id: str, run_id: str) -> None:
    resolved = report_path.expanduser().resolve()
    if resolved == WORK_ROOT.resolve() or WORK_ROOT.resolve() in resolved.parents:
        assert_artifact_under_work(resolved, "canonical runner report")
        register_artifact(
            artifact_id=_runner_path_id(resolved),
            path=resolved,
            kind="runner_report",
            created_by="run_with_cleanup.py",
            owner="run_with_cleanup.py",
            purpose="retained canonical runner outcome and lifecycle evidence",
            lifecycle="RETAINED",
            scope_id=scope_id,
            run_id=run_id,
        )


def _register_runner_owned_roots(
    *, env: dict[str, str], scope_id: str, run_id: str, include_release_verify: bool
) -> None:
    """Register explicit redirected runtime roots before the child starts.

    Canonical snapshot runs redirect TEMP/AppData/cache homes below the
    runner's work root.  Those roots are intentionally disposable, but their
    descendants are created by Python, .NET, and native libraries after the
    runner takes its before-snapshot.  Register the exact redirected roots so
    lifecycle ownership is inherited by those descendants without granting
    ownership to the whole live ``_work`` tree.
    """

    roots: dict[str, Path] = {}
    for name in (
        "TEMP",
        "TMP",
        "APPDATA",
        "LOCALAPPDATA",
        "NUGET_PACKAGES",
        "DOTNET_CLI_HOME",
        "HF_HOME",
        "HF_HUB_CACHE",
        "TRANSFORMERS_CACHE",
        "TORCH_HOME",
        "VNTEXT_DIRECT_GPU_ROOT",
    ):
        raw = str(env.get(name) or "").strip()
        if not raw:
            continue
        path = Path(raw).expanduser().resolve()
        if path == WORK_ROOT.resolve() or WORK_ROOT.resolve() not in path.parents:
            continue
        roots[name] = path

    if include_release_verify:
        release_verify = WORK_ROOT / f"release_verify_{scope_id}"
        env["VNTEXT_RELEASE_VERIFY_RUN_ROOT"] = str(release_verify.resolve())
        roots.setdefault("release_verify", release_verify.resolve())
    records = []
    registered_ids = set()
    for name, path in roots.items():
        artifact_id = _runner_path_id(path)
        if artifact_id in registered_ids:
            continue
        registered_ids.add(artifact_id)
        # A registered disposable root must have a real lifecycle.  Creating
        # the exact empty root here guarantees that even an unused optional
        # runtime root is removed with primary deletion provenance instead of
        # becoming a synthetic MISSING record merely because it never existed.
        path.mkdir(parents=True, exist_ok=True)
        records.append({
            "artifact_id": artifact_id,
            "path": path,
            "kind": "canonical_runtime_root",
            "created_by": "run_with_cleanup.py",
            "owner": "run_with_cleanup.py",
            "purpose": f"disposable redirected canonical runtime root: {name}",
            "lifecycle": "DISPOSABLE",
            "scope_id": scope_id,
            "run_id": run_id,
            "scope_root": WORK_ROOT,
        })
    register_artifacts(records)


def run(
    command: list[str],
    *,
    timeout: float,
    report_path: Path | None,
    cleanup_timeout: float = 30.0,
    stdout_log: Path | None = None,
    stderr_log: Path | None = None,
    retained_roots: list[Path] | None = None,
) -> int:
    scope_id = new_scope_id("canonical-run")
    run_id = new_scope_id("run")
    scope_root = WORK_ROOT.resolve()
    WORK_ROOT.mkdir(parents=True, exist_ok=True)
    markdown_report = WORK_ROOT / f"{scope_id}.md"
    stdout_log = stdout_log or WORK_ROOT / f"{scope_id}.stdout.log"
    stderr_log = stderr_log or WORK_ROOT / f"{scope_id}.stderr.log"
    resolved_report = report_path.expanduser().resolve() if report_path else None
    if resolved_report is not None:
        resolved_report.parent.mkdir(parents=True, exist_ok=True)
        if not resolved_report.exists():
            resolved_report.write_text(
                json.dumps({"status": "RUNNING", "scope_id": scope_id, "run_id": run_id}) + "\n",
                encoding="utf-8",
            )
    for path in (stdout_log, stderr_log):
        path.expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)
    for path in retained_roots or []:
        path.expanduser().resolve().mkdir(parents=True, exist_ok=True)
    _register_runner_report(markdown_report, scope_id=scope_id, run_id=run_id)
    if resolved_report is not None:
        _register_runner_report(resolved_report, scope_id=scope_id, run_id=run_id)
    resolved_stdout = _register_disposable_path(
        stdout_log, kind="runner_stdout", purpose="disposable child stdout log",
        scope_id=scope_id, run_id=run_id,
    )
    resolved_stderr = _register_disposable_path(
        stderr_log, kind="runner_stderr", purpose="disposable child stderr log",
        scope_id=scope_id, run_id=run_id,
    )
    markdown_report.write_text(
        f"# Canonical test run\n\n- Outcome: `RUNNING`\n- Command: `{subprocess.list2cmdline(command)}`\n",
        encoding="utf-8",
    )
    before = snapshot_tree(
        scope_root,
        budget=InventoryBudget(timeout_seconds=cleanup_timeout),
        include_hashes=True,
        skip_retained=True,
    )
    for retained_root in retained_roots or []:
        _register_retained_path(
            retained_root,
            kind="runner_output_root",
            purpose="explicit retained canonical build or gate output",
            scope_id=scope_id,
            run_id=run_id,
        )
    proc: subprocess.Popen | None = None
    stdout_handle = None
    stderr_handle = None
    child_exit: int | None = None
    child_error = ""
    outcome = "UNKNOWN"
    child_still_running = False
    cleanup_report: dict
    started_at = _utc_now()
    try:
        env = os.environ.copy()
        env.setdefault("PYTHONDONTWRITEBYTECODE", "1")
        env["VNTEXT_ARTIFACT_SCOPE_ID"] = scope_id
        env["VNTEXT_ARTIFACT_RUN_ID"] = run_id
        env["VNTEXT_ARTIFACT_SCOPE_ROOT"] = str(scope_root)
        if resolved_stdout is not None:
            env["VNTEXT_PARENT_STDOUT_LOG"] = str(resolved_stdout)
        if resolved_stderr is not None:
            env["VNTEXT_PARENT_STDERR_LOG"] = str(resolved_stderr)
        _register_runner_owned_roots(
            env=env,
            scope_id=scope_id,
            run_id=run_id,
            include_release_verify=cleanup_timeout > 0,
        )
        stdout_handle = resolved_stdout.open("wb") if resolved_stdout is not None else None
        stderr_handle = resolved_stderr.open("wb") if resolved_stderr is not None else None
        popen_kwargs = {}
        if os.name == "nt":
            popen_kwargs["creationflags"] = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        else:
            popen_kwargs["start_new_session"] = True
        proc = subprocess.Popen(
            command,
            cwd=str(ROOT),
            env=env,
            stdout=stdout_handle,
            stderr=stderr_handle,
            **popen_kwargs,
        )
        try:
            child_exit = proc.wait(timeout=timeout)
            outcome = "PASS" if child_exit == 0 else "FAIL"
        except subprocess.TimeoutExpired:
            child_error = f"child exceeded timeout {timeout}s"
            outcome = "TIMEOUT"
            child_still_running = not _request_stop(proc)
            child_exit = proc.returncode
    except KeyboardInterrupt:
        child_error = "runner interrupted by keyboard interrupt"
        outcome = "CANCELLED"
        if proc is not None:
            child_still_running = not _request_stop(proc)
        child_exit = proc.returncode if proc is not None else None
    except OSError as exc:
        child_error = str(exc)
        child_exit = None
        outcome = "START_ERROR"
    except BaseException as exc:  # noqa: BLE001
        child_error = str(exc)
        child_exit = proc.returncode if proc is not None else None
        outcome = "UNKNOWN"
    finally:
        if proc is not None and proc.poll() is None:
            child_still_running = not _request_stop(proc)
        if proc is not None and proc.returncode is not None:
            child_exit = proc.returncode
        if stdout_handle is not None:
            stdout_handle.close()
        if stderr_handle is not None:
            stderr_handle.close()
        primary_output = {
            "stdout": _primary_output_record(resolved_stdout),
            "stderr": _primary_output_record(resolved_stderr),
        }
        stdout_excerpt = _output_excerpt(resolved_stdout)
        stderr_excerpt = _output_excerpt(resolved_stderr)
        test_summary = _parse_unittest_summary(resolved_stdout, resolved_stderr)
        game_copy_disposal = None
        if E2E_GAME_COPY.exists() and not child_still_running:
            try:
                removed = dispose_e2e_game_copy(reason=f"run_with_cleanup after {outcome}")
                game_copy_disposal = {
                    "path": str(E2E_GAME_COPY),
                    "removed": removed,
                    "ok": not E2E_GAME_COPY.exists(),
                }
            except Exception as exc:  # noqa: BLE001
                game_copy_disposal = {"path": str(E2E_GAME_COPY), "removed": False, "ok": False, "error": str(exc)}
        try:
            if child_still_running:
                cleanup_report = {
                    "schema_version": 4, "scope_id": scope_id, "run_id": run_id,
                    "scope_root": str(scope_root), "outcome": outcome,
                    "status": "REVIEW_REQUIRED", "cleanup_status": "REVIEW_REQUIRED",
                    "ok": False, "before": {"inventory": before.get("inventory")},
                    "after": None, "deleted": [], "retained": [], "protected": [],
                    "unknown": [], "locked": [], "errors": [{
                        "reason": "child_process_still_running",
                        "pid": proc.pid if proc is not None else None,
                    }], "inventory_complete": False,
                    "process": {"state": "RUNNING", "pid": proc.pid if proc is not None else None},
                }
            else:
                for retained_root in retained_roots or []:
                    _register_retained_tree(retained_root, scope_id=scope_id, run_id=run_id)
                cleanup_report = finalize_scope(
                    scope_id=scope_id,
                    run_id=run_id,
                    scope_root=scope_root,
                    before=before,
                    outcome=outcome,
                    timeout_seconds=cleanup_timeout,
                )
        except BaseException as exc:  # noqa: BLE001
            cleanup_report = {
                "schema_version": 3,
                "scope_id": scope_id,
                "run_id": run_id,
                "scope_root": str(scope_root),
                "outcome": outcome,
                "status": "REVIEW_REQUIRED",
                "cleanup_status": "REVIEW_REQUIRED",
                "ok": False,
                "before": before,
                "after": None,
                "before_metrics": None,
                "after_metrics": None,
                "lifecycle_metrics": {"before": None, "after": None},
                "created": [],
                "modified": [],
                "deleted": [],
                "retained": [],
                "protected": [],
                "unknown": [],
                "locked": [],
                "errors": [{"reason": "finalize_exception", "error": str(exc)}],
                "inventory_complete": False,
                "inventory": {
                    "budget": {
                        "complete": False,
                        "status": "ERROR",
                        "reason": "finalize_exception",
                        "error": str(exc),
                    }
                },
            }
        if game_copy_disposal is not None:
            cleanup_report["game_copy_disposal"] = game_copy_disposal
            if not game_copy_disposal["ok"]:
                cleanup_report.setdefault("errors", []).append(
                    {
                        "path": game_copy_disposal["path"],
                        "reason": "game_copy_disposal_failed",
                        "error": game_copy_disposal.get("error", "copy still exists after disposal"),
                    }
                )
                cleanup_report["ok"] = False
                cleanup_report["status"] = "REVIEW_REQUIRED"
        status = "PASS" if outcome == "PASS" and cleanup_report.get("ok") else "REVIEW_REQUIRED"
        result = {
            "schema_version": 3,
            "source_sha": _source_sha(),
            "status": status,
            "exit_code": 0 if status == "PASS" else 1,
            "outcome": outcome,
            "child_exit_code": child_exit,
            "child_error": child_error,
            "child_process_state": "RUNNING" if child_still_running else ("EXITED" if proc is not None else "NOT_STARTED"),
            "child_pid": proc.pid if proc is not None else None,
            "started_at": started_at,
            "ended_at": _utc_now(),
            "command": command,
            "scope_id": scope_id,
            "run_id": run_id,
            "scope_root": str(scope_root),
            "cleanup": cleanup_report,
            "primary_output": primary_output,
            "stdout_excerpt": stdout_excerpt,
            "stderr_excerpt": stderr_excerpt,
            "test_summary": test_summary,
            "unknown_roots": [item.get("path") for item in cleanup_report.get("unknown", [])],
            "unknown_root_count": cleanup_report.get("unknown_summary", {}).get(
                "count", len(cleanup_report.get("unknown", []))
            ),
            "work_root": str(WORK_ROOT),
            "markdown_report": str(markdown_report),
        }
        markdown_report.write_text(_markdown_run_report(result), encoding="utf-8")
        if resolved_report:
            resolved_report.parent.mkdir(parents=True, exist_ok=True)
            resolved_report.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            if WORK_ROOT.resolve() in resolved_report.parents:
                _register_runner_report(resolved_report, scope_id=scope_id, run_id=run_id)
        # stdout may use the active Windows console code page; escaped JSON
        # remains valid machine output without raising on replacement chars.
        print(json.dumps(result, ensure_ascii=True, indent=2), flush=True)
    return int(result["exit_code"])


def main() -> int:
    parser = argparse.ArgumentParser(description="Run one command with artifact lifecycle cleanup")
    parser.add_argument("--timeout-seconds", type=float, default=900)
    parser.add_argument(
        "--cleanup-timeout-seconds",
        type=float,
        default=30.0,
        help="Maximum inventory time for before/final cleanup snapshots (fail-closed)",
    )
    parser.add_argument("--report", type=Path, default=None)
    parser.add_argument("--stdout-log", type=Path, default=None)
    parser.add_argument("--stderr-log", type=Path, default=None)
    parser.add_argument(
        "--retained-root",
        type=Path,
        action="append",
        default=[],
        help="Exact output root retained and registered for this canonical run",
    )
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = list(args.command)
    if command[:1] == ["--"]:
        command = command[1:]
    if not command:
        parser.error("a command is required after --")
    return run(
        command,
        timeout=args.timeout_seconds,
        report_path=args.report,
        cleanup_timeout=args.cleanup_timeout_seconds,
        stdout_log=args.stdout_log,
        stderr_log=args.stderr_log,
        retained_roots=args.retained_root,
    )


if __name__ == "__main__":
    raise SystemExit(main())
