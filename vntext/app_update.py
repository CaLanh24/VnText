"""In-app update: check manifest, download to AppData, swap EXE on restart.

No permanent updater binary beside the release EXE — helper scripts live in AppData only.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from vntext.app_config import default_update_manifest_url
from vntext.runtime_paths import APP_DISPLAY, app_data_root, executable_path, is_frozen, updates_dir

PENDING_EXE = "VNText Studio.new.exe"
APPLY_SCRIPT = "apply_update.bat"
MANIFEST_ENV = "VNTEXT_UPDATE_URL"
UPDATE_TARGET_ENV = "VNTEXT_UPDATE_TARGET_EXE"


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_version(value: str) -> tuple[int, ...]:
    parts: list[int] = []
    for token in (value or "").replace("-", ".").split("."):
        digits = "".join(ch for ch in token if ch.isdigit())
        if digits:
            parts.append(int(digits))
    return tuple(parts) or (0,)


def version_newer(remote: str, local: str) -> bool:
    return parse_version(remote) > parse_version(local)


def manifest_url_override() -> str | None:
    url = (os.environ.get(MANIFEST_ENV) or "").strip()
    return url or None


def sibling_release_manifest() -> Path | None:
    exe = executable_path()
    if exe is None:
        return None
    candidate = exe.parent / "RELEASE.json"
    return candidate if candidate.is_file() else None


def resolve_manifest_sources() -> list[str]:
    """Use an explicit URL, optional bundled URL, then RELEASE.json beside the EXE."""
    sources: list[str] = []
    override = manifest_url_override()
    if override:
        sources.append(override)
    else:
        configured_default = default_update_manifest_url()
        if configured_default:
            sources.append(configured_default)
    sibling = sibling_release_manifest()
    if sibling is not None:
        sources.append(str(sibling))
    return sources


def _read_json_source(source: str) -> dict[str, Any]:
    path = Path(source)
    if path.is_file():
        return json.loads(path.read_text(encoding="utf-8-sig"))
    if source.lower().startswith("file:"):
        file_path = Path(source[8:]) if source.startswith("file:///") else Path(source[5:])
        return json.loads(file_path.read_text(encoding="utf-8-sig"))
    with urllib.request.urlopen(source, timeout=20) as resp:
        return json.loads(resp.read().decode("utf-8-sig"))


def _load_manifest(source: str) -> dict[str, Any]:
    return _read_json_source(source)


def fetch_update_manifest() -> dict[str, Any] | None:
    last_error: Exception | None = None
    for source in resolve_manifest_sources():
        try:
            return _load_manifest(source)
        except (OSError, urllib.error.URLError, json.JSONDecodeError, ValueError) as exc:
            last_error = exc
            continue
    if last_error is not None:
        return None
    return None


def _download(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    path = Path(url)
    if path.is_file():
        dest.write_bytes(path.read_bytes())
        return
    if url.lower().startswith("file:"):
        src = Path(url[8:]) if url.startswith("file:///") else Path(url[5:])
        dest.write_bytes(src.read_bytes())
        return
    with urllib.request.urlopen(url, timeout=120) as resp, dest.open("wb") as out:
        while True:
            chunk = resp.read(1024 * 1024)
            if not chunk:
                break
            out.write(chunk)


def pending_update_path() -> Path:
    return updates_dir() / PENDING_EXE


def write_apply_script(target_exe: Path, pending: Path) -> Path:
    script = app_data_root() / APPLY_SCRIPT
    lines = [
        "@echo off",
        "setlocal EnableExtensions",
        "ping 127.0.0.1 -n 3 >nul",
        f'move /Y "{pending}" "{target_exe}"',
        f'start "" "{target_exe}"',
        "del \"%~f0\"",
    ]
    script.write_text("\r\n".join(lines) + "\r\n", encoding="utf-8")
    return script


def update_target_exe() -> Path | None:
    """Resolve the WPF Release target or the frozen Python executable."""

    override = (os.environ.get(UPDATE_TARGET_ENV) or "").strip()
    if override:
        target = Path(override).expanduser()
        if target.is_file():
            return target.resolve()
        return None
    return executable_path()


def apply_pending_update_on_startup() -> str:
    """If a validated pending EXE exists, launch swap script and exit."""
    if not is_frozen():
        return "dev-skip"
    exe = executable_path()
    pending = pending_update_path()
    meta_path = pending.with_suffix(".json")
    if exe is None or not pending.is_file():
        return "none"
    if meta_path.is_file():
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        expected = (meta.get("sha256") or "").lower()
        if expected and _sha256_file(pending).lower() != expected:
            pending.unlink(missing_ok=True)
            meta_path.unlink(missing_ok=True)
            return "bad-hash"
    script = write_apply_script(exe, pending)
    subprocess.Popen(
        ["cmd.exe", "/c", str(script)],
        creationflags=getattr(subprocess, "DETACHED_PROCESS", 0)
        | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
        close_fds=True,
    )
    return "restarting"


def check_for_update(local_version: str) -> dict[str, Any] | None:
    for source in resolve_manifest_sources():
        try:
            manifest = _load_manifest(source)
        except (OSError, urllib.error.URLError, json.JSONDecodeError, ValueError):
            continue
        remote_version = str(manifest.get("version") or "")
        if not remote_version or not version_newer(remote_version, local_version):
            continue
        download_url = str(manifest.get("url") or manifest.get("download_url") or "")
        if not download_url:
            continue
        return {
            "version": remote_version,
            "url": download_url,
            "sha256": str(manifest.get("sha256") or ""),
            "notes": str(manifest.get("notes") or ""),
            "source": source,
        }
    return None


def download_pending_update(info: dict[str, Any]) -> Path:
    pending = pending_update_path()
    tmp = updates_dir() / f".{PENDING_EXE}.{os.getpid()}.tmp"
    tmp.parent.mkdir(parents=True, exist_ok=True)
    _download(info["url"], tmp)
    if info.get("sha256"):
        got = _sha256_file(tmp).lower()
        if got != str(info["sha256"]).lower():
            tmp.unlink(missing_ok=True)
            raise RuntimeError("SHA256 mismatch for downloaded update")
    pending.parent.mkdir(parents=True, exist_ok=True)
    if pending.is_file():
        pending.unlink()
    tmp.replace(pending)
    meta = {"version": info.get("version"), "sha256": _sha256_file(pending)}
    pending.with_suffix(".json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return pending


def schedule_restart_for_update() -> None:
    target_override = (os.environ.get(UPDATE_TARGET_ENV) or "").strip()
    if not is_frozen() and not target_override:
        raise RuntimeError("Update restart only supported in RELEASE build")
    exe = update_target_exe()
    pending = pending_update_path()
    if exe is None or not pending.is_file():
        raise RuntimeError("No pending update downloaded")
    script = write_apply_script(exe, pending)
    subprocess.Popen(
        ["cmd.exe", "/c", str(script)],
        creationflags=getattr(subprocess, "DETACHED_PROCESS", 0)
        | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
        close_fds=True,
    )
    sys.exit(0)


def maybe_prompt_update(app, local_version: str) -> None:
    """Background check; ask user to restart if a newer build is available."""
    if not is_frozen():
        return
    info = check_for_update(local_version)
    if not info:
        return

    if hasattr(app, "after"):
        _schedule_tk_update_prompt(app, info)
    else:
        _schedule_qt_update_prompt(app, info)


def _schedule_tk_update_prompt(app, info: dict[str, Any]) -> None:
    def _ask():
        from tkinter import messagebox

        notes = info.get("notes") or ""
        msg = f"Có bản mới v{info['version']}.\n\n{notes}\n\nTải và cập nhật khi khởi động lại?"
        if not messagebox.askyesno(APP_DISPLAY, msg):
            return
        try:
            download_pending_update(info)
        except Exception as exc:
            messagebox.showerror(APP_DISPLAY, f"Không tải được bản cập nhật:\n{exc}")
            return
        if messagebox.askyesno(APP_DISPLAY, "Đã tải xong. Khởi động lại ngay?"):
            schedule_restart_for_update()

    app.after(1500, _ask)


def _schedule_qt_update_prompt(app, info: dict[str, Any]) -> None:
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QMessageBox

    def _ask():
        notes = info.get("notes") or ""
        msg = f"Có bản mới v{info['version']}.\n\n{notes}\n\nTải và cập nhật khi khởi động lại?"
        if QMessageBox.question(app, APP_DISPLAY, msg) != QMessageBox.Yes:
            return
        try:
            download_pending_update(info)
        except Exception as exc:
            QMessageBox.critical(app, APP_DISPLAY, f"Không tải được bản cập nhật:\n{exc}")
            return
        if QMessageBox.question(app, APP_DISPLAY, "Đã tải xong. Khởi động lại ngay?") == QMessageBox.Yes:
            schedule_restart_for_update()

    QTimer.singleShot(1500, _ask)
