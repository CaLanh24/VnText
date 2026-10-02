"""Pinned Ren'Py 8.5.3 CLI boundary used only on an isolated workspace."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import hashlib
import os
import shutil
import subprocess
import tempfile
import urllib.request
import zipfile


SUPPORTED_VERSION = "8.5.3"
SDK_ARCHIVE_NAME = "renpy-8.5.3-sdk.zip"
SDK_URL = "https://www.renpy.org/dl/8.5.3/renpy-8.5.3-sdk.zip"
SDK_SHA256 = "ff57648f9c04f27e381c48af6d8e3ee3cdec296bed4d3831f47f09b0a71b505e"


class RenPyToolchainError(RuntimeError):
    pass


@dataclass(frozen=True)
class RenPySdk:
    root: Path
    python: Path
    renpy_py: Path
    version: str


def managed_sdk_root() -> Path:
    """Return the dedicated optional-tool cache, never a game or repo path."""
    data_root = os.environ.get("VNTEXT_DATA_ROOT")
    if data_root:
        return Path(data_root).expanduser().resolve() / "tools" / f"renpy-{SUPPORTED_VERSION}"
    configured = os.environ.get("VNTEXT_RENPY_TOOL_ROOT")
    if configured:
        base = Path(configured)
    else:
        base = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "VNText Studio" / "tools"
    return base.expanduser().resolve() / f"renpy-{SUPPORTED_VERSION}"


def managed_sdk() -> RenPySdk | None:
    root = managed_sdk_root()
    if not root.is_dir():
        return None
    return validate_sdk(root)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def install_managed_sdk(archive: str | Path) -> RenPySdk:
    """Atomically install a previously user-approved official archive."""
    archive_path = Path(archive).resolve()
    if not archive_path.is_file() or _sha256(archive_path) != SDK_SHA256:
        raise RenPyToolchainError("Ren'Py SDK archive hash mismatch")
    destination = managed_sdk_root(); parent = destination.parent
    repo = Path.cwd().resolve()
    if destination == repo or repo in destination.parents:
        raise RenPyToolchainError("managed Ren'Py SDK cache must not be inside the repository")
    parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=parent, prefix="renpy-install-") as temp:
        staging = Path(temp) / "payload"
        with zipfile.ZipFile(archive_path) as bundle:
            for info in bundle.infolist():
                target = (staging / info.filename).resolve()
                if staging.resolve() not in target.parents and target != staging.resolve():
                    raise RenPyToolchainError("unsafe Ren'Py SDK archive path")
            bundle.extractall(staging)
        roots = [item for item in staging.iterdir() if item.is_dir()]
        if len(roots) != 1:
            raise RenPyToolchainError("Ren'Py SDK archive has unexpected root layout")
        validate_sdk(roots[0])
        backup = destination.with_name(destination.name + ".previous")
        if backup.exists():
            shutil.rmtree(backup)
        if destination.exists():
            destination.replace(backup)
        try:
            shutil.move(str(roots[0]), str(destination))
        except Exception:
            if backup.exists() and not destination.exists():
                backup.replace(destination)
            raise
        if backup.exists():
            shutil.rmtree(backup)
    return validate_sdk(destination)


def download_and_install_managed_sdk(download: str | Path) -> RenPySdk:
    """Explicit UI action only; never call while merely detecting a game."""
    destination = Path(download).resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    urllib.request.urlretrieve(SDK_URL, destination)
    return install_managed_sdk(destination)


def validate_sdk(path: str | Path) -> RenPySdk:
    root = Path(path).expanduser().resolve()
    renpy_py = root / "renpy.py"
    candidates = sorted((root / "lib").glob("py3-windows-*/python.exe"))
    if not renpy_py.is_file() or len(candidates) != 1:
        raise RenPyToolchainError("supported Ren'Py SDK must contain renpy.py and one Windows runtime")
    python = candidates[0]
    probe = subprocess.run(
        [str(python), str(renpy_py), "--version"], cwd=root, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30, check=False,
    )
    text = (probe.stdout + "\n" + probe.stderr).strip()
    if probe.returncode or SUPPORTED_VERSION not in text:
        raise RenPyToolchainError(f"Ren'Py SDK must be {SUPPORTED_VERSION}; probe returned: {text[:300]}")
    return RenPySdk(root, python, renpy_py, SUPPORTED_VERSION)


def generate_empty_vietnamese_template(sdk: RenPySdk, workspace: str | Path, *, timeout: int = 120) -> subprocess.CompletedProcess[str]:
    """Ask Ren'Py itself to create native IDs in an already-approved copy."""
    target = Path(workspace).resolve()
    if not (target / "game").is_dir():
        raise RenPyToolchainError("template workspace must be a Ren'Py game copy with game/")
    result = subprocess.run(
        [str(sdk.python), str(sdk.renpy_py), str(target), "translate", "vietnamese", "--empty", "--no-todo"],
        cwd=sdk.root, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        timeout=timeout, check=False,
    )
    if result.returncode:
        raise RenPyToolchainError(f"Ren'Py template generation failed: {(result.stderr or result.stdout)[:500]}")
    return result
