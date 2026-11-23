"""Anonymous bug-report bundle: enough STRUCTURE of a game folder to reproduce a defect, never its content or identity.

The bundle holds file-size/extension/header statistics, an anonymised tree (names replaced by hashes unless they are generic engine folder names),
the engine verdict, scan timings and a sanitised log tail.  No file contents, no game/file names, no user paths.  ``tests/tools/synth_from_report.py``
rebuilds a stand-in layout from it, so a report from a game nobody else has can still be replayed.
"""
from __future__ import annotations

import hashlib
import json
import os
import platform
import re
import time
import zipfile
from pathlib import Path

# Schema 2 adds "structure": the masked shape of the exact places an extraction could not handle (vntext/shape_mask.py). Readers accept 1 and 2.
SCHEMA = 2
MAX_STRUCTURE_SAMPLES = 50
MAX_FILES = 60000
MAX_LOG_LINES = 400
MAX_RPA_BYTES = 12 * 1024 ** 3
# Generic folder names of the engines (they identify no game); every other name is replaced by a hash.
GENERIC_NAMES = {
    "game", "renpy", "lib", "tl", "images", "audio", "music", "sound", "sounds", "voice", "gui", "fonts", "font", "cache", "saves", "data", "scripts",
    "streamingassets", "managed", "resources", "plugins", "mono", "monobleedingedge", "il2cpp_data", "metadata", "addressables", "aa", "windows", "standalonewindows64",
    "vietnamese", "english", "common", "python-packages", "gallery", "movies", "video", "videos", "bg", "cg", "sprites", "characters", "effects", "ui", "screens",
    "vntext", ".vntext", "install_backup", "copy_to_game_root",
}


def _anon(name: str) -> str:
    lower = name.casefold()
    if lower in GENERIC_NAMES or lower.endswith("_data") and False:
        return name
    stem, dot, ext = name.rpartition(".")
    digest = hashlib.sha256(name.encode("utf-8", "replace")).hexdigest()[:8]
    flags = ("u" if any(ord(c) > 127 for c in name) else "") + ("s" if " " in name else "") + ("L" if len(name) > 60 else "")
    return f"x{digest}{flags}" + (f".{ext.lower()}" if dot and len(ext) <= 8 and ext.isalnum() else "")


def _anon_path(relative: str) -> str:
    parts = relative.replace("\\", "/").split("/")
    out = []
    for index, part in enumerate(parts):
        if part.casefold().endswith("_data") and index == 0:
            out.append("X_Data")
        else:
            out.append(_anon(part))
    return "/".join(out)


def _header(path: Path, suffix: str) -> str:
    try:
        with path.open("rb") as stream:
            head = stream.read(64)
    except OSError:
        return "unreadable"
    if suffix == ".rpa":
        line = head.split(b"\n", 1)[0].decode("ascii", "replace")
        return line.split(" ", 1)[0][:8]
    if suffix in {".rpyc", ".rpymc"}:
        return "RPC2" if head.startswith(b"RENPY RPC2") else "other"
    if suffix in {".ttf", ".otf", ".ttc"}:
        return head[:4].hex()
    if suffix in {".exe", ".dll"}:
        return "MZ" if head.startswith(b"MZ") else "other"
    return ""


def _rpa_summary(path: Path, size: int) -> dict:
    if size > MAX_RPA_BYTES:
        return {"skipped": "too large to index"}
    try:
        from vntext.renpy_archive import RenPyArchive
        archive = RenPyArchive(path)
    except Exception as exc:  # noqa: BLE001 - the failure itself is the evidence
        return {"error": type(exc).__name__ + ": " + str(exc)[:120]}
    extensions: dict[str, int] = {}
    sizes = {"lt1k": 0, "lt1m": 0, "lt64m": 0}
    unicode_names = 0
    for name in archive.members:
        ext = Path(name).suffix.casefold()[:8] or "(none)"
        extensions[ext] = extensions.get(ext, 0) + 1
        unicode_names += any(ord(c) > 127 for c in name)
        member_size = archive.member_size(name)
        sizes["lt1k" if member_size < 1024 else "lt1m" if member_size < 1024 ** 2 else "lt64m"] += 1
    return {"version": archive.version, "members": len(archive.members), "extensions": dict(sorted(extensions.items())), "size_classes": sizes, "unicode_member_names": unicode_names}


def fingerprint(game: str | Path) -> dict:
    root = Path(game)
    base = root.parent if root.is_file() else root
    files = []
    extensions: dict[str, dict] = {}
    started = time.monotonic()
    total = 0
    truncated = False
    longest = 0
    for current, dirs, names in os.walk(base):
        dirs[:] = [d for d in dirs if not os.path.islink(os.path.join(current, d))]
        for name in names:
            full = Path(current) / name
            try:
                info = full.lstat()
            except OSError:
                continue
            if len(files) >= MAX_FILES:
                truncated = True
                continue
            relative = full.relative_to(base).as_posix()
            suffix = full.suffix.casefold()
            longest = max(longest, len(str(full)))
            total += info.st_size
            bucket = extensions.setdefault(suffix or "(none)", {"count": 0, "bytes": 0, "max_bytes": 0})
            bucket["count"] += 1
            bucket["bytes"] += info.st_size
            bucket["max_bytes"] = max(bucket["max_bytes"], info.st_size)
            entry = {"path": _anon_path(relative), "size": info.st_size, "header": _header(full, suffix)}
            if suffix == ".rpa":
                entry["rpa"] = _rpa_summary(full, info.st_size)
            elif suffix != ".rpa" and info.st_size >= 16:
                from vntext.structure_shapes import shape_for
                try:
                    with full.open("rb") as stream:
                        first = stream.read(16)
                    container = shape_for(full, first)
                except OSError:
                    container = None
                if container is not None:
                    entry["container"] = container
            files.append(entry)
    from vntext.renpy_adapter import detect_engine
    detection = detect_engine(base)
    return {
        "schema": SCHEMA,
        "engine_detection": {"engine": detection.engine, "status": detection.status, "reason": _scrub_reason(detection.reason)},
        "totals": {"files": len(files), "bytes": total, "truncated": truncated, "longest_path_chars": longest, "walk_seconds": round(time.monotonic() - started, 2)},
        "extensions": dict(sorted(extensions.items())),
        "files": files,
        "_names": sorted({part for f in files for part in []}),
    }


_FILE_TOKEN = re.compile(r"[^\s:;,\"']+\.(?:rpy|rpyc|rpym|rpymc|rpa|py|json|csv|txt|webp|png|jpg|ttf|otf)\b", re.IGNORECASE)


def _mask_message(text: str) -> str:
    """A diagnostic line with file names, paths and quoted text removed (numbers and the engine's own wording stay)."""
    text = re.sub(r"[A-Za-z]:[\\/][^\s;,]*", "<PATH>", str(text or ""))
    text = _FILE_TOKEN.sub("<FILE>", text)
    text = re.sub(r"\"[^\"]*\"|'[^']*'", "<TEXT>", text)
    return text[:240]


def collect_structure(package_dir: str | Path) -> dict | None:
    """Masked shape of every place the last extraction could not handle, read from the package manifest (never from the game)."""
    from vntext.shape_mask import SHAPE_SCHEMA, mask_block
    manifest_path = Path(package_dir) / "manifest.json"
    if not manifest_path.is_file():
        return None
    try:
        stats = (json.loads(manifest_path.read_text(encoding="utf-8")).get("stats") or {})
    except (OSError, ValueError):
        return {"error": "manifest unreadable"}
    unresolved = [item for item in (stats.get("renpy_native_unresolved") or []) if isinstance(item, dict)]
    samples = []
    for item in unresolved[:MAX_STRUCTURE_SAMPLES]:
        native_id = str(item.get("native_id") or "")
        first = native_id.split(" ")[0]
        samples.append({
            "kind": "renpy_native_block",
            "template_file": _anon_path(str(item.get("template_file") or "")),
            "template_line": item.get("template_line"),
            "target_class": first if first in {"python", "style"} else ("identifier" if native_id.isidentifier() else "other"),
            "reason": re.sub(r"^.*?:\d+:\s*", "", _mask_message(item.get("reason"))),
            "shape": mask_block(str(item.get("raw_block") or "")),
            "context_before": mask_block(str(item.get("context_before") or "")),
            "context_after": mask_block(str(item.get("context_after") or "")),
        })
    counters = {key: stats.get(key) for key in ("native_units", "native_supported_units", "native_unresolved_blocks", "native_technical_blocks_skipped")
                if isinstance(stats.get(key), int)}
    return {"shape_schema": SHAPE_SCHEMA, "renpy_native_blocks": samples, "unresolved_total": len(unresolved), "counters": counters,
            "errors": [_mask_message(item) for item in (stats.get("errors") or [])[:30]]}


def _scrub_reason(reason: str) -> str:
    return re.sub(r"[A-Za-z]:[\\/][^\s;,]*", "<PATH>", reason or "")[:200]


def sanitise_text(text: str, game: Path, extra_names: set[str]) -> str:
    """Remove the game's path, the user's profile and every real file/folder name from free text."""
    result = text
    for needle in {str(game), str(game).replace("\\", "/"), str(game.parent), os.path.expanduser("~"), os.path.expanduser("~").replace("\\", "/")}:
        if needle and len(needle) >= 4 and os.path.isabs(needle):      # a relative or tiny "path" would mangle ordinary text
            result = result.replace(needle, "<PATH>")
    for name in sorted(extra_names, key=len, reverse=True):
        if len(name) >= 3 and name.casefold() not in GENERIC_NAMES:
            result = re.sub(re.escape(name), _anon(name), result, flags=re.IGNORECASE)
    return re.sub(r"[A-Za-z]:[\\/][^\s\"']*", "<PATH>", result)


def build_report(game: str | Path, out_dir: str | Path, *, log_lines: list[str] | None = None, analysis_report: str | Path | None = None,
                 extract_status: str | Path | None = None, app_version: str = "") -> Path:
    game = Path(game)
    base = game.parent if game.is_file() else game
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    data = fingerprint(game)
    data.pop("_names", None)
    names = {p.name for p in base.rglob("*")} if data["totals"]["files"] < MAX_FILES else set()
    names |= {base.name}
    if analysis_report and Path(analysis_report).is_file():
        try:
            report = json.loads(Path(analysis_report).read_text(encoding="utf-8"))
            data["analysis"] = {"summary": report.get("summary"), "timings_seconds": report.get("timings_seconds"),
                                "engine_detection": report.get("engine_detection"), "inventory_complete": report.get("inventory_complete"),
                                "renpy_asset_outcomes": ((report.get("renpy_assets") or {}).get("fonts") or {}).get("outcomes")}
        except (OSError, ValueError):
            data["analysis"] = {"error": "unreadable"}
    if extract_status and Path(extract_status).is_file():
        try:
            data["extract_status"] = json.loads(Path(extract_status).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            data["extract_status"] = {"error": "unreadable"}
    structure = collect_structure(out_dir)
    if structure is not None:
        data["structure"] = structure
    data["environment"] = {"app_version": app_version, "os": platform.platform(), "python": platform.python_version()}
    tail = [sanitise_text(line, base, names) for line in (log_lines or [])[-MAX_LOG_LINES:]]
    stamp = time.strftime("%Y%m%d-%H%M%S")
    target = out_dir / f"vntext-bug-report-{stamp}.zip"
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("report.json", json.dumps(data, ensure_ascii=False, indent=1))
        archive.writestr("log-tail.txt", "\n".join(tail))
        archive.writestr("README.txt", "VNText Studio bug report. Contains anonymised folder structure (sizes, extensions, hashes of names), the engine verdict, timings and a sanitised "
                                       "log tail. It contains no file contents and no game or file names. Where an extraction met a structure it could not handle, "
                                       "'structure' holds the SHAPE of that place only (keywords, nesting, token kinds and lengths; names and strings are replaced). "
                                       "Review report.json before sending if you wish; nothing is uploaded automatically.\n")
    return target
