"""Build and verify the hash-indexed ZIP embedded by Setup.exe."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import zipfile

MANIFEST = "payload-manifest.json"


def _safe_name(name: str) -> str:
    path = PurePosixPath(name)
    if not name or path.is_absolute() or "\\" in name or ":" in name or any(part in ("", ".", "..") for part in name.split("/")):
        raise ValueError(f"unsafe package path: {name!r}")
    return path.as_posix()


def _allowed_payload_name(name: str) -> bool:
    return (
        name in {"VNText Studio.exe", "Uninstall.exe", ".preview/wpf-update-current.zip"}
        or name.startswith("app/")
    )


def build(payload: Path, archive: Path) -> dict:
    payload = payload.resolve()
    files = {}
    seen = set()
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as bundle:
        for source in sorted(payload.rglob("*")):
            if source.is_symlink():
                raise ValueError(f"symlinks are not allowed in Setup payload: {source}")
            if not source.is_file():
                continue
            name = _safe_name(source.relative_to(payload).as_posix())
            if not _allowed_payload_name(name):
                raise ValueError(f"Setup payload file is outside the allowed layout: {name}")
            folded = name.casefold()
            if name == MANIFEST or folded in seen:
                raise ValueError(f"duplicate or reserved package path: {name}")
            seen.add(folded)
            digest = hashlib.sha256()
            size = 0
            with source.open("rb") as input_file, bundle.open(name, "w") as output_file:
                for chunk in iter(lambda: input_file.read(1024 * 1024), b""):
                    output_file.write(chunk)
                    digest.update(chunk)
                    size += len(chunk)
            files[name] = {"sha256": digest.hexdigest(), "size": size}
        if not files:
            raise ValueError("Setup payload is empty")
        manifest = json.dumps({"schema": 1, "files": files}, sort_keys=True, separators=(",", ":")).encode("utf-8")
        bundle.writestr(MANIFEST, manifest)
    return verify(archive)


def verify(archive: Path) -> dict:
    with zipfile.ZipFile(archive) as bundle:
        names = bundle.namelist()
        if len(names) != len(set(name.casefold() for name in names)):
            raise ValueError("duplicate paths in Setup payload")
        for name in names:
            _safe_name(name)
            if name != MANIFEST and not _allowed_payload_name(name):
                raise ValueError(f"Setup payload file is outside the allowed layout: {name}")
        if names.count(MANIFEST) != 1:
            raise ValueError("Setup payload manifest missing or duplicated")
        manifest = json.loads(bundle.read(MANIFEST))
        if manifest.get("schema") != 1 or not isinstance(manifest.get("files"), dict):
            raise ValueError("unsupported Setup payload manifest")
        expected = manifest["files"]
        if set(names) != set(expected) | {MANIFEST}:
            raise ValueError("Setup payload file inventory mismatch")
        for name, item in expected.items():
            _safe_name(name)
            digest = hashlib.sha256()
            size = 0
            with bundle.open(name) as source:
                for chunk in iter(lambda: source.read(1024 * 1024), b""):
                    digest.update(chunk)
                    size += len(chunk)
            if size != item.get("size") or digest.hexdigest() != item.get("sha256"):
                raise ValueError(f"Setup payload hash mismatch: {name}")
        return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("payload", type=Path)
    parser.add_argument("archive", type=Path)
    args = parser.parse_args()
    manifest = build(args.payload, args.archive)
    total = sum(item["size"] for item in manifest["files"].values())
    print(f"payload verified: {len(manifest['files'])} files, {total} bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
