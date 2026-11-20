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
    font_report_path = output_dir / "font_preflight.json"
    if font_report_path.is_file():
        manifest["font_preflight"] = json.loads(font_report_path.read_text(encoding="utf-8"))
        font_payload = manifest["font_preflight"].get("payload_font")
        if font_payload:
            matching = [file for file in files if file["path"] == font_payload]
            if len(matching) != 1 or matching[0]["source_sha256"] != manifest["font_preflight"]["sha256"]:
                raise ValueError("Prepared font payload differs from glyph preflight")
    if (output_dir / "unity_tmp_adapter.json").is_file():
        # The runtime adapter payload is re-derived from the current game; the installer then also binds the exact TMP/Unity assemblies and registration files.
        from vntext import unity_tmp_adapter
        adapter_evidence = unity_tmp_adapter.verify_staged_payload(game_base, output_dir)
        by_path = {file["path"]: file for file in files}
        for relative, digest in adapter_evidence["payload"].items():
            if by_path.get(relative, {}).get("source_sha256") != digest:
                raise ValueError("Unity adapter payload differs from its evidence: " + relative)
        # Only the player assemblies are identity checks; the two registration files are covered by the per-file original hashes (they change on install).
        manifest["game_checks"] = [check for check in adapter_evidence["game_checks"] if "/Managed/" in check["path"]]
        manifest["unity_tmp_adapter"] = {key: adapter_evidence[key] for key in ("adapter_sha256", "font_sha256", "engine_version", "runtime_status", "scope")}
    (output_dir / "patch_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), "utf-8")
    return manifest


def write_renpy_patch_manifest(output_dir: Path, game_base: Path, version: str, extraction_manifest: dict) -> dict:
    """Installer identity for the verified native overlay, never the whole game."""
    from vntext.extract_output import _no_links
    output_dir, game_base = Path(output_dir), Path(game_base)
    payload_root = output_dir / "COPY_TO_GAME_ROOT"
    checks = []
    sources = {}
    for entry in extraction_manifest.get("entries", []):
        if entry.get("review_only"):
            continue
        contract = entry.get("native_contract") or {}
        container = (contract.get("provenance") or {}).get("source_container") or {}
        precondition = contract.get("precondition") or {}
        relative = container.get("path") or precondition.get("source_file") or entry.get("file_path")
        if not relative:
            continue
        path = game_base / relative
        _no_links(path)
        if not path.resolve().is_relative_to(game_base.resolve()) or not path.is_file():
            raise ValueError("Ren'Py installer source identity missing or outside game")
        digest = sources.get(path)
        if digest is None:
            digest = _sha256_file(path)
        expected = container.get("container_sha256") or precondition.get("source_sha256")
        if expected and expected != digest:
            raise ValueError("Ren'Py source changed after extraction")
        sources[path] = digest
    if not sources or not payload_root.is_dir():
        raise ValueError("Missing Ren'Py source identity or verified overlay")
    for path, digest in sources.items():
        checks.append({"path": path.relative_to(game_base).as_posix(), "sha256": digest})
    font_report_path = output_dir / "font_preflight.json"
    if font_report_path.is_file():
        font_evidence = json.loads(font_report_path.read_text(encoding="utf-8"))
        font_sources = list(font_evidence.get("source_checks", []))
        if font_evidence.get("source_font"):
            font_sources.append(font_evidence["source_font"])
        for font_source in font_sources:
            font_path = game_base / font_source["path"]
            _no_links(font_path)
            if not font_path.resolve().is_relative_to(game_base.resolve()) or _sha256_file(font_path) != font_source["sha256"]:
                raise ValueError("Font source changed before installer packaging")
            if font_source not in checks:
                checks.append(font_source)
    image_report_path = output_dir / "image_overlay.json"
    image_report = None
    if image_report_path.is_file():
        from vntext import renpy_image_overlay
        image_report = json.loads(image_report_path.read_text(encoding="utf-8"))
        renpy_image_overlay.validate_report_payload(image_report, payload_root)
        renpy_image_overlay.verify_baselines(game_base, image_report)
        for check in renpy_image_overlay.baseline_checks(image_report):
            if check not in checks:
                checks.append(check)
    files = []
    for path in sorted(p for p in payload_root.rglob("*") if p.is_file()):
        _no_links(path)
        relative = path.relative_to(payload_root)
        original = game_base / relative
        _no_links(original)
        files.append({"path": relative.as_posix(), "source_sha256": _sha256_file(path),
                      "original_exists": original.is_file(), "original_sha256": _sha256_file(original) if original.is_file() else ""})
    manifest = {"format": 1, "engine": "renpy", "version": version, "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "game_data_sha256": "", "game_checks": checks, "files": files}
    font_report_path = output_dir / "font_preflight.json"
    if font_report_path.is_file():
        manifest["font_preflight"] = json.loads(font_report_path.read_text(encoding="utf-8"))
        font_payload = manifest["font_preflight"].get("payload_font")
        if font_payload:
            matching = [file for file in files if file["path"] == font_payload]
            if len(matching) != 1 or matching[0]["source_sha256"] != manifest["font_preflight"]["sha256"]:
                raise ValueError("Prepared font payload differs from glyph preflight")
        fallback = manifest["font_preflight"].get("glyph_fallback")
        if isinstance(fallback, dict):
            matching = [file for file in files if file["path"] == fallback.get("payload_font")]
            if len(matching) != 1 or matching[0]["source_sha256"] != fallback.get("sha256"):
                raise ValueError("Prepared glyph fallback font differs from its preflight")
    if image_report is not None:
        manifest["image_overlay"] = image_report
        by_path = {file["path"]: file for file in files}
        for image in image_report["images"]:
            staged = by_path.get(image["target"])
            if staged is None or staged["source_sha256"] != image["sha256"]:
                raise ValueError("Prepared image payload differs from its overlay report")
    (output_dir / "patch_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
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
