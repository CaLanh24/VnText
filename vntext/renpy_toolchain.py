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
import time
import stat
from vntext.renpy_archive import RenPyArchive, RenPyArchiveError


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
    """Return the optional-tool cache; DEV shares .dev-env/tools, never game input."""
    data_root = os.environ.get("VNTEXT_DATA_ROOT")
    if data_root:
        repo = Path(__file__).resolve().parent.parent
        if Path(data_root).expanduser().resolve().is_relative_to(repo / "DEV_RUN"):
            return repo / ".dev-env" / "tools" / f"renpy-{SUPPORTED_VERSION}"
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
    repo = Path(__file__).resolve().parent.parent
    dev_cache = Path(__file__).resolve().parent.parent / ".dev-env" / "tools" / f"renpy-{SUPPORTED_VERSION}"
    if (repo / ".git").exists() and (destination == repo or repo in destination.parents) and destination != dev_cache:
        raise RenPyToolchainError("managed Ren'Py SDK cache must not be inside the repository")
    for item in (destination, *destination.parents):
        if item.exists() and (item.is_symlink() or getattr(item.stat(), "st_file_attributes", 0) & 0x400):
            raise RenPyToolchainError("managed Ren'Py SDK cache must not follow links")
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


def copy_template_workspace(source: str | Path, target: str | Path, *, is_cancelled=None, translation_only=False) -> dict:
    """Isolated native workspace; optional translation slice excludes runtime/media."""
    source = Path(source).resolve(); target = Path(target).resolve()
    if target.is_relative_to(source):
        raise RenPyToolchainError("Thư mục xuất phải nằm ngoài game để tạo workspace Ren'Py an toàn.")
    media = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".avif", ".svg", ".mp3", ".ogg", ".wav", ".flac", ".opus", ".m4a", ".mp4", ".webm", ".avi", ".ogv", ".mov"}
    def selected(p):
        if not translation_only: return True
        relative = p.relative_to(source)
        if not relative.parts or relative.parts[0] != "game": return False
        if any(part in {"cache", "saves", "__pycache__"} for part in relative.parts): return False
        if p.suffix.lower() in {".rpa", ".rpyc", ".rpymc"}:
            if p.suffix.lower() == ".rpa": return False
            counterpart = p.with_suffix(".rpy" if p.suffix.lower()==".rpyc" else ".rpym")
            return not counterpart.is_file()
        return p.suffix.lower() not in media
    total = 0; files = 0
    deadline = time.monotonic() + 30
    for p in source.rglob("*"):
        if is_cancelled and is_cancelled():
            raise RenPyToolchainError("cancelled")
        if time.monotonic() >= deadline:
            raise RenPyToolchainError("Kiểm kê workspace Ren'Py quá thời gian; chưa tạo bản sao.")
        info = p.lstat()
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
            raise RenPyToolchainError("Workspace Ren'Py không hỗ trợ link/reparse point; chưa tạo bản sao.")
        if p.is_file() and selected(p):
            total += info.st_size; files += 1
    archive_sources = []
    archive_member_names: set[str] = set()
    if translation_only:
        for archive_path in sorted((source / "game").rglob("*.rpa")) if (source / "game").is_dir() else []:
            archive_relative = archive_path.relative_to(source).as_posix()
            if any(part.casefold() in {"cache", "saves", "__pycache__", "tl"} for part in Path(archive_relative).parts):
                continue
            try:
                archive = RenPyArchive(archive_path)
                for member in archive.members:
                    member_path = Path(member)
                    if member_path.parts[0].casefold() != "game" or member_path.suffix.casefold() not in {".rpy", ".rpym"}:
                        continue
                    if any(part.casefold() in {"cache", "saves", "__pycache__", "tl"} for part in member_path.parts):
                        continue
                    loose = source / Path(*member_path.parts)
                    if loose.is_file():
                        continue
                    if member in archive_member_names:
                        raise RenPyToolchainError(f"RPA scripts collide at {member}; refusing ambiguous source ownership")
                    archived = archive.read_member(member)
                    archive_member_names.add(member)
                    total += len(archived["content"]); files += 1
                    archive_sources.append({"archive_path": archive_relative, "archive_sha256": archived["container_sha256"],
                                            "member_name": member, "member_sha256": archived["member_sha256"],
                                            "size": len(archived["content"])})
            except RenPyArchiveError as exc:
                raise RenPyToolchainError(f"Ren'Py archive is unsupported or unsafe ({archive_relative}): {exc}") from exc
        if total > 128 * 1024 * 1024:
            raise RenPyToolchainError("Archived Ren'Py source exceeds 128 MiB workspace limit")
    if shutil.disk_usage(target.parent).free < total + 16 * 1024 * 1024:
        raise RenPyToolchainError(f"Không đủ dung lượng workspace Ren'Py ({total} bytes); chọn nơi xuất còn trống hoặc lấy text một phần không SDK.")
    repo = Path(__file__).resolve().parent.parent
    if (repo / ".git").exists() and target.is_relative_to(repo):
        # DEV reuses the canonical read-only inventory; installed apps have no test dependency.
        from tests.tools.cleanup_work_artifacts import _project_size_snapshot
        approved = repo / "TEST_RUN/renpy-complete/game-copy"
        quota = _project_size_snapshot(approved_game_copy=source) if source == approved else _project_size_snapshot()
        if not quota["complete"] or not quota["within_limit"] or quota["non_exempt_bytes"] + total + 16 * 1024 * 1024 > quota["limit_bytes"]:
            raise RenPyToolchainError("DEV workspace vượt copy budget/quota hoặc inventory chưa đầy đủ; chưa tạo bản sao. Giữ input và xử lý artifact owned trước.")
    copied = 0
    def copy_file(src, dst):
        nonlocal copied
        if is_cancelled and is_cancelled():
            raise RenPyToolchainError("cancelled")
        p = Path(src); info = p.lstat()
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
            raise RenPyToolchainError("Workspace source changed to a link")
        copied += info.st_size
        if copied > total:
            raise RenPyToolchainError("Workspace source grew after preflight; stopped copy")
        return shutil.copy2(src, dst)
    def ignored(directory, names):
        return [name for name in names if not selected(Path(directory) / name)]
    shutil.copytree(source, target, copy_function=copy_file, ignore=ignored if translation_only else None)
    resolved_archive_sources = {}
    for record in archive_sources:
        if is_cancelled and is_cancelled(): raise RenPyToolchainError("cancelled")
        archive = RenPyArchive(source / record["archive_path"])
        if archive.container_sha256 != record["archive_sha256"]:
            raise RenPyToolchainError(f"RPA container changed during workspace copy: {record['archive_path']}")
        member = archive.read_member(record["member_name"])
        if member["member_sha256"] != record["member_sha256"]:
            raise RenPyToolchainError(f"RPA script changed during workspace copy: {record['member_name']}")
        destination = target / Path(*Path(record["member_name"]).parts)
        destination.parent.mkdir(parents=True, exist_ok=True)
        try:
            with destination.open("xb") as stream: stream.write(member["content"])
        except FileExistsError as exc:
            raise RenPyToolchainError(f"RPA script collides with copied source: {record['member_name']}") from exc
        copied += len(member["content"])
        if copied > total: raise RenPyToolchainError("RPA source grew after preflight; stopped copy")
        resolved_archive_sources[record["member_name"]] = {**record}
    return {"files": files, "bytes": total, "archive_sources": resolved_archive_sources}


def generate_empty_vietnamese_template(sdk: RenPySdk, workspace: str | Path, *, timeout: int = 120, is_cancelled=None) -> subprocess.CompletedProcess[str]:
    """Ask Ren'Py itself to create native IDs in an already-approved copy."""
    target = Path(workspace).resolve()
    if not (target / "game").is_dir():
        raise RenPyToolchainError("template workspace must be a Ren'Py game copy with game/")
    command = [str(sdk.python), str(sdk.renpy_py), str(target), "translate", "vietnamese", "--empty", "--no-todo", "--savedir", str(target / ".native-saves")]
    temp = target / ".native-temp"; temp.mkdir(exist_ok=True)
    env = os.environ.copy()
    env.update(PYTHONDONTWRITEBYTECODE="1", TEMP=str(temp), TMP=str(temp), TMPDIR=str(temp))
    proc = subprocess.Popen(
        command,
        cwd=sdk.root, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env,
    )
    deadline = time.monotonic() + timeout
    try:
        while True:
            if is_cancelled and is_cancelled():
                raise RenPyToolchainError("cancelled")
            if time.monotonic() >= deadline:
                raise RenPyToolchainError("Ren'Py template generation timed out; workspace chưa hoàn tất.")
            try:
                stdout, stderr = proc.communicate(timeout=min(0.1, max(0.001, deadline - time.monotonic())))
                break
            except subprocess.TimeoutExpired:
                continue
    finally:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill(); proc.communicate()
    result = subprocess.CompletedProcess(command, proc.returncode, stdout, stderr)
    if result.returncode:
        raise RenPyToolchainError(f"Ren'Py template generation failed: {(result.stderr or result.stdout)[:500]}")
    return result
