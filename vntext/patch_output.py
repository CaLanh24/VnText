"""Output patch responsibilities."""

from __future__ import annotations

from vntext.patch_constants import (
    Path,
    hashlib,
    json,
    time,
)


def save_unity_env(env, target_path: Path, progress_callback=None):
    from vntext.unity_fs import save_unity_environment
    save_unity_environment(env, target_path, progress_callback)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_patch_manifest(output_dir: Path, game_base: Path, version: str) -> dict:
    """Describe the final payload and exact pre-patch hashes for the installer."""
    from vntext.patch_safety import resolve_game_source_file
    payload_root = output_dir / "COPY_TO_GAME_ROOT"
    if not payload_root.is_dir():
        raise RuntimeError(f"Thiếu COPY_TO_GAME_ROOT khi tạo manifest: {payload_root}")
    payload_data_dirs = {
        payload.relative_to(payload_root).parts[0]
        for payload in payload_root.rglob("*")
        if payload.is_file() and len(payload.relative_to(payload_root).parts) > 1
        and payload.relative_to(payload_root).parts[0].casefold().endswith("_data")
    }
    data_path = _find_primary_unity_data(game_base, payload_data_dirs)
    executable_path = _find_primary_executable(game_base, data_path)
    files = []
    for payload in sorted((p for p in payload_root.rglob("*") if p.is_file()), key=lambda p: str(p).lower()):
        rel = payload.relative_to(payload_root).as_posix()
        original = game_base / Path(rel)
        if not original.is_file():
            source_candidate, _actual_rel = resolve_game_source_file(game_base, rel)
            original = source_candidate
        files.append({
            "path": rel,
            "source_sha256": _sha256_file(payload),
            "original_sha256": _sha256_file(original) if original.is_file() else "",
            "original_exists": original.is_file(),
        })
    manifest = {
        "format": 1,
        "version": str(version),
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "game_data_path": data_path.relative_to(game_base).as_posix() if data_path and data_path.is_file() else "",
        "game_data_sha256": _sha256_file(data_path) if data_path and data_path.is_file() else "",
        "game_executable": executable_path.name if executable_path else "",
        "files": files,
    }
    (output_dir / "patch_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), "utf-8")
    return manifest


def _find_primary_unity_data(game_base: Path, preferred_data_dirs: set[str] | None = None) -> Path | None:
    """Find the primary Unity data file without assuming a game name."""
    base = Path(game_base)
    if not base.is_dir():
        return None
    try:
        data_dirs = list(sorted(
            (item for item in base.iterdir() if item.is_dir() and item.name.lower().endswith("_data")),
            key=lambda item: item.name.lower(),
        ))
    except OSError:
        return None
    preferred = {str(item).casefold() for item in (preferred_data_dirs or set())}
    if preferred:
        matches = [item for item in data_dirs if item.name.casefold() in preferred]
        if len(matches) == 1:
            data_dirs = matches
        elif len(matches) > 1:
            raise RuntimeError(
                "Không thể chọn Unity *_Data duy nhất từ payload: "
                + ", ".join(item.name for item in matches)
            )
    try:
        executables = sorted(
            (item for item in base.iterdir() if item.is_file() and item.suffix.lower() == ".exe"),
            key=lambda item: item.name.lower(),
        )
    except OSError:
        executables = []
    if executables:
        expected = {f"{item.stem.casefold()}_data" for item in executables}
        matching = [item for item in data_dirs if item.name.casefold() in expected]
        if len(matching) == 1:
            data_dirs = matching
        elif len(matching) > 1 and len(data_dirs) > 1:
            raise RuntimeError(
                "Không thể chọn Unity *_Data duy nhất từ nhiều executable: "
                + ", ".join(item.name for item in matching)
            )
        elif len(data_dirs) > 1:
            raise RuntimeError("Không thể chọn Unity *_Data duy nhất: nhiều data root không có executable tương ứng")
    elif len(data_dirs) > 1:
        raise RuntimeError("Không thể chọn Unity *_Data duy nhất: nhiều data root và không có executable")
    preferred_names = ("data.unity3d", "globalgamemanagers", "resources.assets")
    for data_dir in data_dirs:
        for name in preferred_names:
            candidate = data_dir / name
            if candidate.is_file():
                return candidate
    return None


def _find_primary_executable(game_base: Path, data_path: Path | None) -> Path | None:
    """Return the executable matching the selected Unity ``*_Data`` root."""

    base = Path(game_base)
    if not base.is_dir():
        return None
    try:
        executables = sorted(
            (item for item in base.iterdir() if item.is_file() and item.suffix.lower() == ".exe"),
            key=lambda item: item.name.lower(),
        )
    except OSError:
        return None
    if not executables:
        return None
    if data_path is not None:
        expected = data_path.parent.name.casefold()
        for executable in executables:
            if f"{executable.stem.casefold()}_data" == expected:
                return executable
    return executables[0]

__all__ = ['save_unity_env', '_sha256_file', 'write_patch_manifest']
