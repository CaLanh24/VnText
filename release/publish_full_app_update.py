"""Build an immutable full-app update delta from an installed baseline to a Release tree."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import tempfile
from uuid import uuid4
import zipfile


MANIFEST_NAME = "full-app-update-manifest.json"
FEED_NAME = "full-app-update-current.json"
PACKAGE_PREFIX = "full-app-update-"
MAX_PACKAGE_BYTES = 512 * 1024 * 1024
MAX_FILE_COUNT = 20_000
VERSION_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)(?:-([A-Za-z0-9]+(?:[.-][A-Za-z0-9]+)*))?$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
SOURCE_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
REPARSE_POINT = 0x400


def _safe_name(name: str) -> str:
    path = PurePosixPath(name)
    if (not name or path.is_absolute() or "\\" in name or ":" in name or
            any(part in ("", ".", "..") for part in name.split("/"))):
        raise ValueError(f"unsafe update path: {name!r}")
    if name != "VNText Studio.exe" and not name.startswith("app/"):
        raise ValueError(f"update path is outside the application inventory: {name}")
    if name.casefold().startswith("app/data/"):
        raise ValueError(f"update path is inside protected application data: {name}")
    return path.as_posix()


def _assert_regular_path(path: Path, *, must_exist: bool = True) -> None:
    path = path.absolute()
    for item in reversed((path, *path.parents)):
        if not item.exists():
            if must_exist:
                raise FileNotFoundError(item)
            continue
        if item.lstat().st_file_attributes & REPARSE_POINT:
            raise ValueError(f"reparse point is not allowed: {item}")


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
        raise ValueError(f"invalid app version: {value}")
    return tuple(int(match.group(i)) for i in range(1, 4)), match.group(4) or ""


def _is_newer(current: str, candidate: str) -> bool:
    old_core, old_suffix = _version(current)
    new_core, new_suffix = _version(candidate)
    return new_core > old_core or (new_core == old_core and bool(old_suffix) and not new_suffix)


def _inventory(root: Path) -> dict[str, dict[str, object]]:
    exe = root / "VNText Studio.exe"
    app = root / "app"
    _assert_regular_path(exe)
    _assert_regular_path(app)
    if not exe.is_file() or not app.is_dir():
        raise ValueError(f"not a VNText Studio install/publish root: {root}")
    files = [exe]
    for path in app.rglob("*"):
        _assert_regular_path(path)
        if path.is_file():
            files.append(path)
        elif not path.is_dir():
            raise ValueError(f"special application file is not allowed: {path}")
    result: dict[str, dict[str, object]] = {}
    for path in files:
        relative = "VNText Studio.exe" if path == exe else "app/" + path.relative_to(app).as_posix()
        relative = _safe_name(relative)
        key = relative.casefold()
        if any(name.casefold() == key for name in result):
            raise ValueError(f"case-insensitive duplicate application path: {relative}")
        result[relative] = _record(path)
    if len(result) > MAX_FILE_COUNT:
        raise ValueError(f"application inventory exceeds {MAX_FILE_COUNT} files")
    for required in ("VNText Studio.exe", "app/RELEASE.json", "app/VERSION.txt"):
        if required not in result:
            raise ValueError(f"required application file is missing: {required}")
    return result


def _validate_protected_model(baseline: dict[str, dict[str, object]],
                              candidate: dict[str, dict[str, object]]) -> None:
    protected = lambda inventory: {
        name: record for name, record in inventory.items()
        if name.casefold().startswith("app/worker/models/")
    }
    if protected(baseline) != protected(candidate):
        raise ValueError("full-app update cannot add, replace, or delete model files")


def _installed_version(root: Path) -> str:
    version = (root / "app" / "VERSION.txt").read_text(encoding="utf-8").strip()
    release = json.loads((root / "app" / "RELEASE.json").read_text(encoding="utf-8"))
    if release.get("version") != version or str(release.get("sha256", "")).lower() != _sha256(root / "VNText Studio.exe"):
        raise ValueError("installed baseline metadata or executable hash is inconsistent")
    return version


def _candidate_version(root: Path, version: str, source_sha: str, source_tree_sha256: str) -> None:
    if (root / "app" / "VERSION.txt").read_text(encoding="utf-8").strip() != version:
        raise ValueError("candidate VERSION.txt does not match the requested version")
    release = json.loads((root / "app" / "RELEASE.json").read_text(encoding="utf-8"))
    if release.get("version") != version or str(release.get("sha256", "")).lower() != _sha256(root / "VNText Studio.exe"):
        raise ValueError("candidate RELEASE.json does not match its executable and version")
    if str(release.get("source_sha", "")).lower() != source_sha:
        raise ValueError("candidate RELEASE.json source_sha does not match the package source")
    if str(release.get("source_tree_sha256", "")).lower() != source_tree_sha256:
        raise ValueError("candidate RELEASE.json source_tree_sha256 does not match the package source")


def _read_feed(updates: Path) -> dict[str, object] | None:
    feed_path = updates / FEED_NAME
    if not feed_path.exists():
        return None
    _assert_regular_path(feed_path)
    feed = json.loads(feed_path.read_text(encoding="utf-8"))
    if not isinstance(feed, dict) or feed.get("schema") != 1:
        raise ValueError("current full-app Updates manifest is invalid")
    package_file = feed.get("package_file")
    package_sha = feed.get("package_sha256")
    if (not isinstance(package_file, str) or Path(package_file).name != package_file or
            not package_file.startswith(PACKAGE_PREFIX) or not package_file.endswith(".zip") or
            not isinstance(package_sha, str) or not SHA256_RE.fullmatch(package_sha)):
        raise ValueError("current full-app package path or hash is invalid")
    package = updates / package_file
    _assert_regular_path(package)
    if _sha256(package) != package_sha:
        raise ValueError("current full-app package SHA-256 mismatch")
    return feed


def _updates_size(updates: Path) -> tuple[int, int]:
    packages = []
    allowed_feeds = {FEED_NAME, "wpf-update-current.json"}
    for path in updates.iterdir():
        _assert_regular_path(path)
        if path.name in allowed_feeds or path.name.endswith(".tmp") or path.name.startswith(".") and path.name.endswith(".tmp"):
            continue
        if path.is_file() and path.name.startswith((PACKAGE_PREFIX, "wpf-update-")) and path.suffix == ".zip":
            packages.append(path)
        else:
            raise ValueError(f"unexpected item in Updates: {path.name}")
    return len(packages), sum(path.stat().st_size for path in packages)


def publish(baseline_root: Path, candidate_root: Path, updates_root: Path, version: str,
            source_sha: str, source_tree_sha256: str, notes: str = "") -> dict[str, object]:
    _assert_regular_path(baseline_root)
    _assert_regular_path(candidate_root)
    _assert_regular_path(updates_root, must_exist=False)
    baseline = baseline_root.resolve(strict=True)
    candidate = candidate_root.resolve(strict=True)
    updates = updates_root.resolve(strict=False)
    if baseline == updates or baseline in updates.parents or updates in baseline.parents:
        raise ValueError("Updates root must stay outside and separate from the install baseline")
    if not SOURCE_SHA_RE.fullmatch(source_sha):
        raise ValueError("source_sha must be a full lowercase Git SHA-1")
    if not SHA256_RE.fullmatch(source_tree_sha256):
        raise ValueError("source_tree_sha256 must be a full lowercase SHA-256")
    _version(version)

    current_version = _installed_version(baseline)
    if not _is_newer(current_version, version):
        raise ValueError(f"candidate {version} is not newer than installed {current_version}")
    _candidate_version(candidate, version, source_sha, source_tree_sha256)
    base_files = _inventory(baseline)
    files = _inventory(candidate)
    _validate_protected_model(base_files, files)

    added = {name: files[name] for name in sorted(files.keys() - base_files.keys())}
    deleted = sorted(base_files.keys() - files.keys())
    replaced = {
        name: files[name] for name in sorted(files.keys() & base_files.keys())
        if files[name] != base_files[name]
    }
    unchanged = (files.keys() & base_files.keys()) - replaced.keys()
    manifest = {
        "schema": 2, "kind": "full-app", "version": version,
        "source_sha": source_sha, "source_tree_sha256": source_tree_sha256,
        "notes": notes, "files": files, "base_files": base_files,
        "add_files": added, "replace_files": replaced, "delete_files": deleted,
    }

    updates.mkdir(parents=True, exist_ok=True)
    _assert_regular_path(updates)
    previous = _read_feed(updates)
    if previous is not None:
        previous_version = str(previous.get("manifest", {}).get("version", ""))
        if previous_version and not _is_newer(previous_version, version):
            raise ValueError(f"candidate {version} is not newer than current Updates version {previous_version}")

    fd, temp_name = tempfile.mkstemp(prefix=".full-app-update-", suffix=".tmp", dir=updates)
    os.close(fd)
    temp_package = Path(temp_name)
    temp_feed = updates / f".{FEED_NAME}.{uuid4().hex}.tmp"
    try:
        with zipfile.ZipFile(temp_package, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
            archive.writestr(MANIFEST_NAME, json.dumps(manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
            for name in sorted(added.keys() | replaced.keys()):
                source = candidate / name
                archive.write(source, name)
        with temp_package.open("r+b") as stream:
            os.fsync(stream.fileno())
        size = temp_package.stat().st_size
        if size <= 0 or size > MAX_PACKAGE_BYTES:
            raise ValueError(f"full-app package size {size} exceeds the {MAX_PACKAGE_BYTES}-byte limit")
        package_sha = _sha256(temp_package)
        package_path = updates / f"{PACKAGE_PREFIX}{version}-{package_sha[:16]}.zip"
        if package_path.exists():
            _assert_regular_path(package_path)
            if _sha256(package_path) != package_sha:
                raise ValueError("immutable full-app package name already exists with different contents")
            temp_package.unlink()
        else:
            os.replace(temp_package, package_path)

        feed = {"schema": 1, "package_file": package_path.name,
                "package_sha256": package_sha, "manifest": manifest}
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

    package_count, package_bytes = _updates_size(updates)
    return {
        "baseline_root": str(baseline), "candidate_root": str(candidate), "updates_root": str(updates),
        "baseline_version": current_version, "version": version, "source_sha": source_sha,
        "source_tree_sha256": source_tree_sha256, "package_path": str(package_path),
        "package_sha256": package_sha, "package_size": size,
        "added": sorted(added), "replaced": sorted(replaced), "deleted": deleted,
        "unchanged_count": len(unchanged), "target_file_count": len(files),
        "retained_package_count": package_count, "retained_package_bytes": package_bytes,
        "current_manifest": str(updates / FEED_NAME),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline-root", type=Path, required=True)
    parser.add_argument("--candidate-root", type=Path, required=True)
    parser.add_argument("--updates-root", type=Path, required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--source-tree-sha256", required=True)
    parser.add_argument("--notes", default="")
    args = parser.parse_args()
    try:
        result = publish(args.baseline_root, args.candidate_root, args.updates_root,
                         args.version, args.source_sha, args.source_tree_sha256, args.notes)
    except Exception as exc:
        parser.exit(2, f"Full-app update was not published: {exc}\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
