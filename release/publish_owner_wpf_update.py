"""Publish an immutable WPF-only package and atomically switch the local Updates feed."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
from uuid import uuid4
import zipfile


ALLOWLIST = ("VNText Studio.exe", "app/RELEASE.json", "app/VERSION.txt")
FEED_NAME = "wpf-update-current.json"
PACKAGE_PREFIX = "wpf-update-"
VERSION_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)(?:-([A-Za-z0-9]+(?:[.-][A-Za-z0-9]+)*))?$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
SOURCE_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
REPARSE_POINT = 0x400


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _record(path: Path) -> dict[str, object]:
    return {"sha256": _sha256(path), "size": path.stat().st_size}


def _version(value: str) -> tuple[tuple[int, int, int], str]:
    match = VERSION_RE.fullmatch(value)
    if not match:
        raise ValueError(f"Invalid app version: {value}")
    return tuple(int(match.group(i)) for i in range(1, 4)), match.group(4) or ""


def _is_newer(current: str, candidate: str) -> bool:
    old_core, old_suffix = _version(current)
    new_core, new_suffix = _version(candidate)
    return new_core > old_core or (new_core == old_core and bool(old_suffix) and not new_suffix)


def _assert_regular_path(path: Path, *, must_exist: bool = True) -> None:
    path = path.absolute()
    parts = list(reversed((path, *path.parents)))
    for item in parts:
        if not item.exists():
            if must_exist:
                raise FileNotFoundError(item)
            continue
        if item.lstat().st_file_attributes & REPARSE_POINT:
            raise ValueError(f"Reparse point is not allowed: {item}")


def _installed_version(root: Path) -> str:
    exe = root / "VNText Studio.exe"
    version_path = root / "app" / "VERSION.txt"
    release_path = root / "app" / "RELEASE.json"
    for path in (exe, version_path, release_path):
        _assert_regular_path(path)
    version = version_path.read_text(encoding="utf-8").strip()
    release = json.loads(release_path.read_text(encoding="utf-8"))
    if release.get("version") != version or release.get("sha256", "").lower() != _sha256(exe):
        raise ValueError("Installed A version metadata or executable hash is inconsistent.")
    return version


def _manifest_records(value: object, label: str) -> dict[str, dict[str, object]]:
    if not isinstance(value, dict) or set(value) != set(ALLOWLIST):
        raise ValueError(f"{label} inventory must contain exactly the updater allowlist.")
    records: dict[str, dict[str, object]] = {}
    for name, raw in value.items():
        if (not isinstance(raw, dict) or not isinstance(raw.get("sha256"), str) or
                not SHA256_RE.fullmatch(raw["sha256"]) or type(raw.get("size")) is not int or raw["size"] < 0):
            raise ValueError(f"{label} record is invalid: {name}")
        records[name] = {"sha256": raw["sha256"], "size": raw["size"]}
    return records


def _validate_manifest(value: object) -> dict[str, object]:
    if not isinstance(value, dict) or value.get("schema") != 1:
        raise ValueError("WPF package manifest is invalid.")
    version = value.get("version")
    source_sha = value.get("source_sha")
    source_tree_sha256 = value.get("source_tree_sha256")
    notes = value.get("notes")
    if not isinstance(version, str):
        raise ValueError("WPF package version is missing.")
    _version(version)
    if not isinstance(source_sha, str) or not SOURCE_SHA_RE.fullmatch(source_sha):
        raise ValueError("source_sha must be a full lowercase Git SHA-1.")
    if source_tree_sha256 is not None and (not isinstance(source_tree_sha256, str) or not SHA256_RE.fullmatch(source_tree_sha256)):
        raise ValueError("source_tree_sha256 must be a full lowercase SHA-256 or null.")
    if not isinstance(notes, str):
        raise ValueError("WPF package notes must be a string.")
    return {
        "schema": 1, "version": version, "source_sha": source_sha,
        "source_tree_sha256": source_tree_sha256, "notes": notes,
        "files": _manifest_records(value.get("files"), "Package"),
        "base_files": _manifest_records(value.get("base_files"), "Baseline"),
    }


def _same_manifest(left: object, right: object) -> bool:
    try:
        return _validate_manifest(left) == _validate_manifest(right)
    except (TypeError, ValueError):
        return False


def _read_current_feed(updates: Path) -> dict[str, object] | None:
    feed_path = updates / FEED_NAME
    if not feed_path.exists():
        return None
    _assert_regular_path(feed_path)
    feed = json.loads(feed_path.read_text(encoding="utf-8"))
    if not isinstance(feed, dict) or feed.get("schema") != 1:
        raise ValueError("Current Updates manifest is invalid.")
    package_file = feed.get("package_file")
    package_sha256 = feed.get("package_sha256")
    if (not isinstance(package_file, str) or Path(package_file).name != package_file or
            not package_file.startswith(PACKAGE_PREFIX) or not package_file.endswith(".zip") or
            not isinstance(package_sha256, str) or not SHA256_RE.fullmatch(package_sha256)):
        raise ValueError("Current Updates package path or hash is invalid.")
    manifest = _validate_manifest(feed.get("manifest"))
    package = updates / package_file
    _assert_regular_path(package)
    if _sha256(package) != package_sha256:
        raise ValueError("Current Updates package SHA-256 mismatch.")
    try:
        with zipfile.ZipFile(package) as archive:
            if set(archive.namelist()) != {"wpf-update-manifest.json", *ALLOWLIST}:
                raise ValueError("Current WPF package does not match the exact allowlist.")
            if not _same_manifest(manifest, json.loads(archive.read("wpf-update-manifest.json"))):
                raise ValueError("Current Updates manifest does not match its package.")
    except (OSError, zipfile.BadZipFile, json.JSONDecodeError) as exc:
        raise ValueError(f"Current WPF package is unreadable: {exc}") from exc
    return {"package_file": package_file, "manifest": manifest}


def _package_size(updates: Path) -> tuple[int, int]:
    packages = []
    for path in updates.iterdir():
        _assert_regular_path(path)
        if path.name in {FEED_NAME, "full-app-update-current.json"} or path.name.endswith(".tmp"):
            continue
        if path.is_file() and path.name.startswith((PACKAGE_PREFIX, "full-app-update-")) and path.suffix == ".zip":
            packages.append(path)
        else:
            raise ValueError(f"Unexpected item in Updates: {path.name}")
    return len(packages), sum(path.stat().st_size for path in packages)


def publish(wpf_publish_root: Path, install_root: Path, updates_root: Path, version: str,
            source_sha: str, source_tree_sha256: str = "", notes: str = "") -> dict[str, object]:
    _assert_regular_path(install_root)
    _assert_regular_path(wpf_publish_root)
    _assert_regular_path(updates_root, must_exist=False)
    root = install_root.resolve(strict=True)
    candidate = wpf_publish_root.resolve(strict=True)
    updates = updates_root.resolve(strict=False)
    if root == updates or root in updates.parents or updates in root.parents:
        raise ValueError("Updates root must stay outside and separate from the installation.")
    if not SOURCE_SHA_RE.fullmatch(source_sha):
        raise ValueError("source_sha must be a full lowercase Git SHA-1.")
    if source_tree_sha256 and not SHA256_RE.fullmatch(source_tree_sha256):
        raise ValueError("source_tree_sha256 must be a full lowercase SHA-256.")
    _version(version)

    current_version = _installed_version(root)
    if not _is_newer(current_version, version):
        raise ValueError(f"Candidate {version} is not newer than installed {current_version}.")

    outputs = list(candidate.rglob("*"))
    for path in outputs:
        _assert_regular_path(path)
    output_files = sorted(p for p in outputs if p.is_file() and p.suffix.lower() != ".pdb")
    executables = [p for p in output_files if p.relative_to(candidate).as_posix() == "VNText.Studio.App.exe"]
    if len(executables) != 1:
        raise ValueError("WPF publish must contain VNText.Studio.App.exe.")
    exe = executables[0]
    unchanged_support_files = []
    for path in output_files:
        relative = path.relative_to(candidate).as_posix()
        if relative == "VNText.Studio.App.exe":
            continue
        installed = root / "app" / Path(*relative.split("/"))
        if not installed.is_file() or _record(path) != _record(installed):
            raise ValueError(f"WPF output changes file outside the updater allowlist: app/{relative}; use a full Setup.")
        unchanged_support_files.append({"path": f"app/{relative}", **_record(path)})

    exe_record = _record(exe)
    release_bytes = (json.dumps({
        "schema_version": 1, "version": version, "source_sha": source_sha,
        "source_tree_sha256": source_tree_sha256 or None, "sha256": exe_record["sha256"],
    }, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")
    version_bytes = (version + "\n").encode("utf-8")
    manifest = {
        "schema": 1, "version": version, "source_sha": source_sha,
        "source_tree_sha256": source_tree_sha256 or None, "notes": notes,
        "files": {
            "VNText Studio.exe": exe_record,
            "app/RELEASE.json": {"sha256": hashlib.sha256(release_bytes).hexdigest(), "size": len(release_bytes)},
            "app/VERSION.txt": {"sha256": hashlib.sha256(version_bytes).hexdigest(), "size": len(version_bytes)},
        },
        "base_files": {name: _record(root.joinpath(*name.split("/"))) for name in ALLOWLIST},
    }
    manifest = _validate_manifest(manifest)

    updates.mkdir(parents=True, exist_ok=True)
    _assert_regular_path(updates)
    previous = _read_current_feed(updates)
    if previous is not None:
        old_manifest = previous["manifest"]
        if old_manifest["base_files"] == manifest["base_files"] and not _is_newer(old_manifest["version"], version):
            raise ValueError(f"Candidate {version} is not newer than current Updates version {old_manifest['version']} for this baseline.")

    fd, temp_name = tempfile.mkstemp(prefix=".wpf-update-", suffix=".tmp", dir=updates)
    os.close(fd)
    temp_package = Path(temp_name)
    temp_feed = updates / f".{FEED_NAME}.{uuid4().hex}.tmp"
    package_path: Path | None = None
    try:
        with zipfile.ZipFile(temp_package, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("wpf-update-manifest.json", json.dumps(manifest, ensure_ascii=False, separators=(",", ":")))
            archive.write(exe, "VNText Studio.exe")
            archive.writestr("app/RELEASE.json", release_bytes)
            archive.writestr("app/VERSION.txt", version_bytes)
        with temp_package.open("r+b") as stream:
            os.fsync(stream.fileno())
        package_sha256 = _sha256(temp_package)
        package_path = updates / f"{PACKAGE_PREFIX}{version}-{package_sha256[:16]}.zip"
        if package_path.exists():
            _assert_regular_path(package_path)
            if _sha256(package_path) != package_sha256:
                raise ValueError("Immutable WPF package name already exists with different contents.")
            temp_package.unlink()
        else:
            os.replace(temp_package, package_path)

        feed = {"schema": 1, "package_file": package_path.name,
                "package_sha256": package_sha256, "manifest": manifest}
        with temp_feed.open("x", encoding="utf-8", newline="\n") as stream:
            json.dump(feed, stream, ensure_ascii=False, separators=(",", ":"))
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp_feed, updates / FEED_NAME)
    finally:
        for temporary in (temp_package, temp_feed):
            try:
                temporary.unlink()
            except FileNotFoundError:
                pass

    package_count, package_bytes = _package_size(updates)
    return {
        "install_root": str(root), "updates_root": str(updates),
        "current_version": current_version, "version": version, "source_sha": source_sha,
        "package_path": str(package_path), "package_sha256": package_sha256,
        "package_size": package_path.stat().st_size, "allowlist": list(ALLOWLIST),
        "unchanged_support_files": unchanged_support_files,
        "retained_package_count": package_count, "retained_package_bytes": package_bytes,
        "current_manifest": str(updates / FEED_NAME),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wpf-publish-root", type=Path, required=True)
    parser.add_argument("--install-root", type=Path, required=True)
    parser.add_argument("--updates-root", type=Path, required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--source-tree-sha256", default="")
    parser.add_argument("--notes", default="")
    args = parser.parse_args()
    try:
        result = publish(args.wpf_publish_root, args.install_root, args.updates_root,
                         args.version, args.source_sha, args.source_tree_sha256, args.notes)
    except Exception as exc:
        parser.exit(2, f"WPF update was not published: {exc}\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
