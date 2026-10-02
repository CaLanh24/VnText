"""Read-only Unity game capability analysis and resource inventory.

The analyzer is deliberately independent from the extraction and patch
pipelines.  It answers a narrower, safer question first: what is in a Unity
game directory, which signatures can be identified, and which capabilities
need a reader/writer proof before they may enter the translation workflow.

It never writes below the supplied game root.  The optional CLI output is
written only to an explicitly supplied path and is not part of the game
inventory.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import sys
import xml.etree.ElementTree as ET
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable

from vntext.patchability import (
    PATCHABLE_METHOD_CONTRACTS,
    STRUCTURED_CSV_PATCH_PROOF,
    STRUCTURED_JSON_PATCH_PROOF,
    STRUCTURED_XML_PATCH_PROOF,
    STRUCTURED_SQLITE_PATCH_PROOF,
    UNITY_LOCALIZATION_PATCH_PROOF,
)
from vntext.structured_csv import has_text_header


ANALYZER_VERSION = 5

SUPPORTED_AND_PATCHABLE = "SUPPORTED_AND_PATCHABLE"
EXTRACT_ONLY = "EXTRACT_ONLY"
REVIEW_REQUIRED = "REVIEW_REQUIRED"
UNSUPPORTED = "UNSUPPORTED"
NOT_DETECTED = "NOT_DETECTED"

_STATUSES = frozenset(
    {
        SUPPORTED_AND_PATCHABLE,
        EXTRACT_ONLY,
        REVIEW_REQUIRED,
        UNSUPPORTED,
        NOT_DETECTED,
    }
)

_UNITY_CONTAINER_EXTS = frozenset(
    {".assets", ".bundle", ".unity3d", ".sharedassets", ".resource", ".ress", ".resss"}
)
_TEXT_EXTS = frozenset(
    {".txt", ".json", ".csv", ".xml", ".yaml", ".yml", ".nani", ".scenario", ".bytes"}
)
_RUNTIME_EXTS = frozenset({".dll", ".exe", ".pdb", ".sys", ".lib", ".so", ".dylib"})
_MEDIA_EXTS = frozenset(
    {
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".webp",
        ".dds",
        ".tga",
        ".psd",
        ".wav",
        ".ogg",
        ".mp3",
        ".mp4",
        ".webm",
        ".mov",
        ".avi",
        ".bnk",
        ".bank",
    }
)
_UNITY_SIGNATURES = (b"UnityFS\x00", b"UnityRaw\x00", b"UnityWebData1.0")
_NANINOVEL_MARKERS = (
    b"Naninovel.Commands",
    b"Naninovel.Runtime",
    b"@choice",
    b"@print",
    b"nScripts/",
)
_UNITY_TYPE_NAMES = frozenset(
    {
        "TextAsset",
        "MonoBehaviour",
        "ScriptableObject",
        "TextMeshPro",
        "TextMeshProUGUI",
        "TMP_Text",
        "UI.Text",
    }
)
_UNITY_LOCALIZATION_CLASS_MARKERS = frozenset(
    {
        "assettable",
        "localizedasset",
        "localizedstring",
        "localizationtable",
        "localizationsettings",
        "localizestringevent",
        "locale",
        "sharedtabledata",
        "stringtable",
    }
)
_PRINTABLE_ASCII_RE = re.compile(rb"[\x20-\x7e]{4,}")
_PRINTABLE_UTF16LE_RE = re.compile(rb"(?:[\x20-\x7e]\x00){4,}")
_CONTROL_BYTES = frozenset(range(0, 9)) | frozenset(range(11, 14)) | frozenset(range(14, 32)) | {127}

_CAPABILITY_METHOD_CONTRACTS = {
    "structured_json": ("structured_json_value", STRUCTURED_JSON_PATCH_PROOF),
    "structured_csv": ("structured_csv_cell", STRUCTURED_CSV_PATCH_PROOF),
    "structured_xml": ("structured_xml_value", STRUCTURED_XML_PATCH_PROOF),
    "structured_sqlite": ("structured_sqlite_value", STRUCTURED_SQLITE_PATCH_PROOF),
    "unity_localization": ("unity_localization_string", UNITY_LOCALIZATION_PATCH_PROOF),
}


@dataclass(frozen=True)
class AnalyzerOptions:
    """Bounds for an analysis run.

    ``probe_unity_objects`` is opt-out because object type coverage is useful
    evidence, while ``max_unity_probe_bytes`` prevents a probe from turning a
    directory inventory into an unbounded full-game operation.
    """

    include_sha256: bool = True
    probe_unity_objects: bool = True
    max_unity_probe_bytes: int = 128 * 1024 * 1024
    sample_bytes: int = 1024 * 1024
    candidate_limit: int = 20


@dataclass
class _InventoryContext:
    scan_errors: list[dict[str, str]] = field(default_factory=list)
    progress_callback: Callable[[dict[str, Any]], None] | None = None
    is_cancelled: Callable[[], bool] | None = None

    def check_cancelled(self) -> None:
        if self.is_cancelled is not None and self.is_cancelled():
            raise UnityAnalysisCancelled("Unity analysis cancelled")

    def report_progress(self, step: str, done: int, total: int, item: str = "") -> None:
        self.check_cancelled()
        if self.progress_callback is not None:
            self.progress_callback(
                {"step": step, "done": max(0, int(done)), "total": max(0, int(total)), "item": item}
            )


class UnityAnalysisCancelled(RuntimeError):
    """Raised when an inventory is cancelled before a complete report exists."""


def _normalise_status(value: str) -> str:
    return value if value in _STATUSES else REVIEW_REQUIRED


def _reduce_resource_status(base_status: str, capability_statuses: Iterable[str]) -> str:
    """Keep a resource status no broader than its least-proven capability.

    A resource can expose several observations at once: for example a Unity
    file may contain a safely readable TextAsset and an unproven MonoBehaviour,
    or a JSON catalog may also be an Addressables candidate.  The base reader
    status must never hide the weaker observation.  ``SUPPORTED_AND_PATCHABLE``
    is therefore reserved for a base supported route whose every attached
    capability is independently supported.
    """

    base = _normalise_status(base_status)
    capabilities = [_normalise_status(value) for value in capability_statuses]
    if not capabilities:
        return base
    if base == REVIEW_REQUIRED or REVIEW_REQUIRED in capabilities:
        return REVIEW_REQUIRED

    if base == SUPPORTED_AND_PATCHABLE:
        if all(value == SUPPORTED_AND_PATCHABLE for value in capabilities):
            return SUPPORTED_AND_PATCHABLE
        if EXTRACT_ONLY in capabilities:
            return EXTRACT_ONLY
        return REVIEW_REQUIRED

    if base == EXTRACT_ONLY:
        if any(value in {UNSUPPORTED, NOT_DETECTED} for value in capabilities):
            return REVIEW_REQUIRED
        return EXTRACT_ONLY

    if base == UNSUPPORTED:
        if all(value in {UNSUPPORTED, NOT_DETECTED} for value in capabilities):
            return UNSUPPORTED
        return REVIEW_REQUIRED

    if all(value in {UNSUPPORTED, NOT_DETECTED} for value in capabilities):
        return NOT_DETECTED
    return REVIEW_REQUIRED


def _reduce_capability_statuses(statuses: Iterable[str]) -> str:
    """Aggregate observations without turning mixed evidence into support."""

    values = [_normalise_status(value) for value in statuses]
    if not values:
        return NOT_DETECTED
    if REVIEW_REQUIRED in values:
        return REVIEW_REQUIRED
    if EXTRACT_ONLY in values:
        return EXTRACT_ONLY
    if SUPPORTED_AND_PATCHABLE in values and UNSUPPORTED in values:
        return REVIEW_REQUIRED
    if SUPPORTED_AND_PATCHABLE in values:
        return SUPPORTED_AND_PATCHABLE
    if UNSUPPORTED in values:
        return UNSUPPORTED
    return NOT_DETECTED


def _sha256_file(
    path: Path,
    chunk_size: int = 1024 * 1024,
    *,
    context: _InventoryContext | None = None,
    item: str = "",
) -> str:
    digest = hashlib.sha256()
    total = path.stat().st_size
    done = 0
    if context is not None:
        context.report_progress("unity_hash", done, total, item)
    with path.open("rb") as handle:
        while True:
            if context is not None:
                context.check_cancelled()
            chunk = handle.read(chunk_size)
            if not chunk:
                break
            digest.update(chunk)
            done += len(chunk)
            if context is not None:
                context.report_progress("unity_hash", done, total, item)
    return digest.hexdigest()


def _safe_read(path: Path, limit: int) -> tuple[bytes, str | None]:
    try:
        with path.open("rb") as handle:
            return handle.read(max(0, limit)), None
    except OSError as exc:
        return b"", f"read failed: {exc}"


def _path_parts(path: Path, root: Path) -> tuple[str, ...]:
    try:
        relative = path.relative_to(root)
    except ValueError:
        relative = path
    return tuple(part.lower() for part in relative.parts)


def _is_under(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _find_direct_named_dirs(root: Path, suffix: str) -> list[Path]:
    found: list[Path] = []
    try:
        children = sorted(root.iterdir(), key=lambda item: item.name.lower())
    except OSError:
        return found
    for child in children:
        try:
            if child.is_dir() and child.name.lower().endswith(suffix.lower()):
                found.append(child)
        except OSError:
            continue
    return found


def _find_executables(root: Path, preferred_stem: str = "") -> list[Path]:
    candidates: list[Path] = []
    try:
        direct = [p for p in root.iterdir() if p.is_file() and p.suffix.lower() == ".exe"]
    except OSError:
        direct = []
    candidates.extend(sorted(direct, key=lambda item: item.name.lower()))
    if not candidates:
        try:
            nested = [p for p in root.rglob("*.exe") if p.is_file()]
        except OSError:
            nested = []
        candidates.extend(sorted(nested, key=lambda item: item.as_posix().lower()))
    if preferred_stem:
        candidates.sort(key=lambda item: (item.stem.lower() != preferred_stem.lower(), item.name.lower()))
    return candidates


def _resolve_game(input_path: str | os.PathLike[str]) -> dict[str, Any]:
    supplied = Path(input_path).expanduser()
    try:
        supplied = supplied.resolve(strict=True)
    except OSError:
        supplied = supplied.absolute()

    if supplied.is_file():
        scan_root = supplied.parent
        executable = supplied if supplied.suffix.lower() == ".exe" else None
        data_roots = _find_direct_named_dirs(scan_root, "_data")
        if executable:
            expected = scan_root / f"{executable.stem}_Data"
            data_roots.sort(key=lambda item: (item.name.lower() != expected.name.lower(), item.name.lower()))
    elif supplied.is_dir():
        if supplied.name.lower().endswith("_data"):
            scan_root = supplied.parent
            data_roots = [supplied]
            executable = None
        else:
            scan_root = supplied
            data_roots = _find_direct_named_dirs(scan_root, "_data")
            executable = None
    else:
        return {
            "input_path": str(supplied),
            "scan_root": str(supplied.parent),
            "executable": None,
            "data_roots": [],
            "selected_data_root": None,
            "input_error": f"input path does not exist: {supplied}",
        }

    executables = _find_executables(scan_root, executable.stem if executable else "")
    if executable is None and executables:
        preferred = [
            item
            for item in executables
            if any(item.stem.lower() == data.name[:-5].lower() for data in data_roots)
        ]
        executable = (preferred or executables)[0]

    if executable is not None:
        expected = scan_root / f"{executable.stem}_Data"
        data_roots.sort(key=lambda item: (item.name.lower() != expected.name.lower(), item.name.lower()))

    selected = data_roots[0] if data_roots else None
    return {
        "input_path": str(supplied),
        "scan_root": str(scan_root),
        "executable": str(executable) if executable else None,
        "executables": [str(item) for item in executables],
        "data_roots": [str(item) for item in data_roots],
        "selected_data_root": str(selected) if selected else None,
        "input_error": None,
    }


def _unity_markers(scan_root: Path, data_roots: Iterable[Path]) -> dict[str, Any]:
    markers: list[str] = []
    for data_root in data_roots:
        try:
            names = {item.name.lower() for item in data_root.iterdir()}
        except OSError:
            names = set()
        for name in ("globalgamemanagers", "data.unity3d", "resources.assets", "boot.config"):
            if name in names:
                markers.append(f"{data_root.name}/{name}")
        for directory_name in ("StreamingAssets", "Managed"):
            candidate = data_root / directory_name
            if candidate.is_dir():
                markers.append(f"{data_root.name}/{directory_name}/")
        if (data_root / "UnityPlayer.dll").is_file():
            markers.append(f"{data_root.name}/UnityPlayer.dll")
    if (scan_root / "UnityPlayer.dll").is_file():
        markers.append("UnityPlayer.dll")
    return {"detected": bool(markers), "markers": sorted(set(markers), key=str.lower)}


def _decode_text_sample(raw: bytes) -> tuple[str | None, str | None]:
    if not raw:
        return None, None
    if raw.startswith(b"\xff\xfe") or raw.startswith(b"\xfe\xff"):
        for encoding in ("utf-16", "utf-16-le", "utf-16-be"):
            try:
                return raw.decode(encoding), encoding
            except UnicodeDecodeError:
                continue
    for encoding in ("utf-8-sig", "utf-8"):
        try:
            return raw.decode(encoding), encoding
        except UnicodeDecodeError:
            continue
    return None, None


def _text_candidates(raw: bytes, limit: int) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    seen: set[tuple[int, str]] = set()

    def add(offset: int, text: str, encoding: str) -> None:
        cleaned = " ".join(text.replace("\x00", " ").split())
        if len(cleaned) < 4 or not any(char.isalpha() for char in cleaned):
            return
        key = (offset, cleaned)
        if key in seen or len(candidates) >= limit:
            return
        seen.add(key)
        candidates.append(
            {
                "offset": offset,
                "encoding": encoding,
                "preview": cleaned[:120],
            }
        )

    for match in _PRINTABLE_ASCII_RE.finditer(raw):
        add(match.start(), match.group().decode("ascii", errors="replace"), "ascii")
        if len(candidates) >= limit:
            return candidates
    for match in _PRINTABLE_UTF16LE_RE.finditer(raw):
        try:
            decoded = match.group().decode("utf-16-le")
        except UnicodeDecodeError:
            continue
        add(match.start(), decoded, "utf-16-le")
        if len(candidates) >= limit:
            break
    return candidates


def _looks_like_csv(text: str) -> bool:
    sample = text[:64 * 1024]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
        rows = list(csv.reader(sample.splitlines()[:5], dialect))
    except (csv.Error, UnicodeError):
        return False
    return len(rows) >= 1 and any(len(row) > 1 for row in rows)


def _structured_signature(path: Path, raw: bytes, text: str | None) -> tuple[str | None, list[str], list[str]]:
    """Return signature, categories and reasons from content/path evidence."""

    ext = path.suffix.lower()
    categories: list[str] = []
    reasons: list[str] = []
    if raw.startswith(_UNITY_SIGNATURES):
        signature = "unityfs" if raw.startswith(b"UnityFS\x00") else raw.split(b"\x00", 1)[0].decode("ascii", "replace").lower()
        categories.extend(["UNITY_CONTAINER", "ASSET_BUNDLE"])
        reasons.append("Unity container header detected")
        return signature, categories, reasons
    if raw.startswith(b"SQLite format 3\x00"):
        return "sqlite", ["STRUCTURED", "SQLITE"], ["SQLite header detected"]
    if raw.startswith((b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08")):
        return "zip", ["ARCHIVE"], ["ZIP header detected; inner resources require review"]
    if raw.startswith(b"\x1f\x8b"):
        return "gzip", ["COMPRESSED"], ["gzip header detected; inner resources require review"]

    # Unity serialized resources are binary in normal builds, but a malformed
    # or synthetic fixture may happen to decode as UTF-8.  The stable file
    # name/extension is still stronger evidence for the Unity resource family
    # than the incidental encoding of a short sample.
    if ext in _UNITY_CONTAINER_EXTS or path.name.lower() in {
        "globalgamemanagers",
        "resources.assets",
        "data.unity3d",
    }:
        return "unity_serialized_candidate", ["UNITY_CONTAINER", "SERIALIZED_UNITY"], [
            "Unity resource name/extension detected; header/object probe required"
        ]

    if text is not None:
        stripped = text.lstrip("\ufeff \t\r\n")
        if ext == ".json" or stripped.startswith(("{", "[")):
            try:
                json.loads(text)
                return "json", ["STRUCTURED", "JSON"], ["JSON parsed successfully"]
            except (TypeError, ValueError, json.JSONDecodeError):
                if ext == ".json":
                    return "json_invalid", ["STRUCTURED", "JSON"], [".json extension but JSON parse failed"]
        if ext == ".xml" or stripped.startswith("<"):
            try:
                ET.fromstring(text)
                if re.search(r"<!\s*(?:DOCTYPE|ENTITY)\b", text, re.IGNORECASE):
                    return "xml_unsafe", ["STRUCTURED", "XML"], [
                        "XML parsed but contains DTD/entity declarations; safe writer route is disabled"
                    ]
                return "xml", ["STRUCTURED", "XML"], ["XML parsed successfully"]
            except (ET.ParseError, ValueError):
                if ext == ".xml":
                    return "xml_invalid", ["STRUCTURED", "XML"], [".xml extension but XML parse failed"]
        if ext == ".csv" or _looks_like_csv(text):
            return "csv", ["STRUCTURED", "CSV"], ["delimited table detected"]
        if ext in {".yaml", ".yml"}:
            return "yaml", ["STRUCTURED", "YAML"], ["YAML-like extension detected; parser/writer proof required"]
        if ext in {".nani", ".scenario"}:
            return "text", ["TEXT", "SCRIPT"], ["script-like text extension detected"]
        if text.strip():
            return "text", ["TEXT"], ["decodable text content detected"]
        return "empty", ["EMPTY"], ["file contains no text"]

    if ext in _RUNTIME_EXTS:
        return "runtime_binary", ["RUNTIME"], ["runtime executable/library is not a text resource"]
    if ext in _MEDIA_EXTS:
        return "media_binary", ["MEDIA"], ["media resource is not a text resource"]
    return "binary", ["UNKNOWN"], ["binary content has no recognized signature"]


def _safe_plain_text_sample(raw: bytes, text: str | None, encoding: str | None) -> bool:
    """Reject binary-looking samples before promoting an extensionless file.

    UTF-16 is allowed only when the decoder identified it from a BOM.  For
    UTF-8/ASCII, NUL and control bytes are strong evidence that a file is a
    serialized/runtime resource whose incidental printable strings must stay in
    the analyzer/review path.
    """

    if not text or not text.strip():
        return False
    if encoding and encoding.startswith("utf-16"):
        return True
    if b"\x00" in raw:
        return False
    controls = sum(byte in _CONTROL_BYTES for byte in raw)
    return controls <= max(2, len(raw) // 100)


def detect_resource_kind(path: str | os.PathLike[str], *, sample_bytes: int = 64 * 1024) -> dict[str, Any]:
    """Return a bounded, read-only routing classification for one resource.

    This is intentionally cheaper than :func:`analyze_unity_game`: it reads at
    most ``sample_bytes`` and never imports UnityPy.  Extraction/patch routing
    may use it to recognize extensionless UTF text and Unity containers while
    retaining the legacy suffix behavior for known formats.  A positive
    ``is_unity_extractable`` result means the existing UnityPy/UnityFS route is
    appropriate; raw ``.resource`` sidecars remain inventory-only unless their
    content has an actual Unity container header.
    """

    resource = Path(path)
    extension = resource.suffix.lower()
    raw, read_error = _safe_read(resource, max(1, int(sample_bytes)))
    text, encoding = _decode_text_sample(raw)
    signature, categories, reasons = _structured_signature(resource, raw, text)
    signature = signature or "unreadable"
    has_unity_header = signature in {"unityfs", "unityraw", "unitywebdata1.0"}
    is_unity = has_unity_header or "UNITY_CONTAINER" in categories
    known_unity_name = resource.name.lower() in {"globalgamemanagers", "resources.assets", "data.unity3d"}
    is_unity_extractable = is_unity and (
        has_unity_header
        or (extension not in {".resource", ".ress", ".resss"} and ("SERIALIZED_UNITY" in categories or known_unity_name))
    )
    extensionless_text = (
        not extension
        and not is_unity
        and signature == "text"
        and _safe_plain_text_sample(raw, text, encoding)
    )
    return {
        "path": str(resource),
        "signature": signature,
        "categories": sorted(set(categories)),
        "reasons": list(reasons),
        "encoding": encoding,
        "read_error": read_error,
        "is_text_file": extension in _TEXT_EXTS or extensionless_text,
        "is_extensionless_text": extensionless_text,
        "is_unity": is_unity,
        "is_unity_extractable": is_unity_extractable,
    }


def _unitypy_probe(path: Path, options: AnalyzerOptions) -> dict[str, Any]:
    result: dict[str, Any] = {
        "attempted": False,
        "status": "NOT_RUN",
        "object_count": 0,
        "type_counts": {},
        "script_class_counts": {},
        "error": None,
    }
    try:
        size = path.stat().st_size
    except OSError as exc:
        result.update(status="ERROR", error=f"stat failed: {exc}")
        return result
    if not options.probe_unity_objects:
        result.update(status="DISABLED", error="Unity object probe disabled by options")
        return result
    if size > options.max_unity_probe_bytes:
        result.update(
            status="SKIPPED_SIZE",
            error=f"file size {size} exceeds probe limit {options.max_unity_probe_bytes}",
        )
        return result
    result["attempted"] = True
    try:
        import UnityPy  # type: ignore
    except Exception as exc:
        result.update(status="NOT_AVAILABLE", error=f"UnityPy unavailable: {exc}")
        return result
    try:
        environment = UnityPy.load(str(path))
        counter: Counter[str] = Counter()
        script_classes: Counter[str] = Counter()
        object_count = 0
        for obj in getattr(environment, "objects", ()):
            type_name = getattr(getattr(obj, "type", None), "name", None) or str(getattr(obj, "type", "UNKNOWN"))
            type_name = str(type_name)
            counter[type_name] += 1
            if type_name in {"MonoBehaviour", "ScriptableObject"}:
                try:
                    data = obj.read()
                    script_ptr = getattr(data, "m_Script", None)
                    script_obj = (
                        script_ptr.deref_parse_as_object()
                        if script_ptr is not None and hasattr(script_ptr, "deref_parse_as_object")
                        else None
                    )
                    class_name = str(getattr(script_obj, "m_ClassName", "") or "").strip()
                    namespace = str(getattr(script_obj, "m_Namespace", "") or "").strip()
                    if class_name:
                        script_classes[".".join(part for part in (namespace, class_name) if part)] += 1
                except Exception:
                    pass
            object_count += 1
        result.update(
            status="OPENED",
            object_count=object_count,
            type_counts=dict(sorted(counter.items())),
            script_class_counts=dict(sorted(script_classes.items())),
        )
    except Exception as exc:
        result.update(status="ERROR", error=f"UnityPy open/probe failed: {exc}")
    return result


def _capability(
    name: str,
    status: str,
    reason: str,
    *,
    confidence: float,
    evidence: Iterable[str] = (),
    patch_route: str | None = None,
) -> dict[str, Any]:
    return {
        "name": name,
        "status": _normalise_status(status),
        "reason": reason,
        "confidence": round(max(0.0, min(1.0, confidence)), 3),
        "evidence": list(evidence),
        "patch_route": patch_route,
        "patch_verification": "NOT_RUN",
    }


def _unity_localization_class_evidence(script_class_counts: dict[str, Any]) -> list[str]:
    """Return evidence for known Unity Localization script identities.

    Class identity is discovery evidence only.  It cannot establish a table
    schema, stable key locator, writer, reopen check, or semantic verification.
    """

    evidence: list[str] = []
    for class_name, count in sorted((script_class_counts or {}).items(), key=lambda item: str(item[0]).casefold()):
        compact = re.sub(r"[^a-z0-9]", "", str(class_name).casefold())
        if compact in _UNITY_LOCALIZATION_CLASS_MARKERS or any(
            marker in compact
            for marker in ("stringtable", "sharedtabledata", "localizationtable", "localizestringevent")
        ):
            evidence.append(f"Unity Localization script class: {class_name} (count={int(count)})")
    return evidence


def _path_capability_hints(path: Path, scan_root: Path, raw: bytes) -> tuple[list[str], list[str]]:
    parts = _path_parts(path, scan_root)
    path_text = "/".join(parts)
    categories: list[str] = []
    evidence: list[str] = []
    if "streamingassets" in parts:
        categories.append("STREAMING_ASSETS")
        evidence.append("path contains StreamingAssets")
    if "aa" in parts and "streamingassets" in parts:
        categories.extend(["ADDRESSABLES", "ADDRESSABLES_BUNDLE_CANDIDATE"])
        evidence.append("path is below StreamingAssets/aa")
    if path.name.lower() == "catalog.json":
        categories.append("ADDRESSABLES_CATALOG")
        evidence.append("catalog.json name")
    if any(token in path_text for token in ("localization", "localisation", "stringtable", "sharedtabledata")):
        categories.append("UNITY_LOCALIZATION_CANDIDATE")
        evidence.append("localization path/name marker")
    if "naninovel" in path_text or any(marker in raw for marker in _NANINOVEL_MARKERS):
        categories.append("NANINOVEL_CANDIDATE")
        evidence.append("Naninovel path/content marker")
    return sorted(set(categories)), evidence


def _classify_resource(
    path: Path,
    scan_root: Path,
    options: AnalyzerOptions,
    context: _InventoryContext,
    addressables_roots: Iterable[Path] = (),
) -> dict[str, Any]:
    context.check_cancelled()
    try:
        size = path.stat().st_size
    except OSError as exc:
        error = f"stat failed: {exc}"
        context.scan_errors.append({"path": str(path), "error": error})
        return {
            "path": path.relative_to(scan_root).as_posix() if _is_under(path, scan_root) else str(path),
            "size": None,
            "extension": path.suffix.lower(),
            "signature": "unreadable",
            "categories": ["UNKNOWN"],
            "status": REVIEW_REQUIRED,
            "status_reasons": [error],
            "capabilities": [_capability("resource_inventory", REVIEW_REQUIRED, error, confidence=0.0)],
            "text_candidates": [],
            "sha256": None,
            "probe": {"attempted": False, "status": "ERROR", "error": error},
        }

    raw, read_error = _safe_read(path, options.sample_bytes)
    context.check_cancelled()
    text, encoding = _decode_text_sample(raw)
    signature, categories, reasons = _structured_signature(path, raw, text)
    path_categories, path_evidence = _path_capability_hints(path, scan_root, raw)
    categories = sorted(set(categories + path_categories))
    reasons.extend(path_evidence)
    if "UNITY_CONTAINER" in categories and any(_is_under(path, root) for root in addressables_roots):
        categories.append("ADDRESSABLES_BUNDLE_CANDIDATE")
        reasons.append("Unity container is below a catalog.json directory")
    if read_error:
        context.scan_errors.append({"path": str(path), "error": read_error})
        signature = "unreadable"
        categories = ["UNKNOWN"]
        reasons = [read_error]

    # Printable byte runs in PNG/audio/DLL payloads are usually implementation
    # metadata, not localization candidates.  Keep candidate scanning focused
    # on unknown bytes, text and Unity containers so the inventory does not
    # turn every media file into a false REVIEW_REQUIRED result.
    candidate_scan = (
        text is not None
        or "UNKNOWN" in categories
        or "UNITY_CONTAINER" in categories
    )
    candidates = _text_candidates(raw, options.candidate_limit) if candidate_scan else []
    context.check_cancelled()
    probe: dict[str, Any] = {
        "attempted": False,
        "status": "NOT_APPLICABLE",
        "object_count": 0,
        "type_counts": {},
        "script_class_counts": {},
    }
    unity_candidate = "UNITY_CONTAINER" in categories or signature in {"unityfs", "unityraw", "unitywebdata1.0", "unity_serialized_candidate"}
    if unity_candidate:
        context.check_cancelled()
        probe = _unitypy_probe(path, options)
        context.check_cancelled()
        type_counts = probe.get("type_counts") or {}
        localization_class_evidence = _unity_localization_class_evidence(
            probe.get("script_class_counts") or {}
        )
        if localization_class_evidence:
            categories.append("UNITY_LOCALIZATION_CANDIDATE")
            reasons.extend(localization_class_evidence)
        if type_counts:
            if type_counts.get("TextAsset"):
                categories.append("TEXT_ASSET")
            if type_counts.get("MonoBehaviour"):
                categories.append("MONOBEHAVIOUR")
            if type_counts.get("ScriptableObject"):
                categories.append("SCRIPTABLE_OBJECT")
            if any("TMP" in name or "TextMeshPro" in name or name == "UI.Text" for name in type_counts):
                categories.append("UNITY_UI_TMP")
            categories = sorted(set(categories))

    capabilities: list[dict[str, Any]] = []
    patch_route: str | None = None
    if read_error:
        status = REVIEW_REQUIRED
        reasons.append("resource could not be read; it is retained for review")
        capabilities.append(_capability("resource_inventory", status, reasons[-1], confidence=0.0))
    elif unity_candidate:
        if probe.get("status") == "OPENED" and probe.get("object_count", 0):
            status = EXTRACT_ONLY
            reason = "Unity container opened and object types were inventoried; text writer roundtrip is not proven by analysis"
            patch_route = "vntext.patch_pipeline.unity" if any(
                name in categories for name in ("TEXT_ASSET", "MONOBEHAVIOUR", "SCRIPTABLE_OBJECT", "UNITY_UI_TMP")
            ) else None
            capabilities.append(
                _capability(
                    "unity_serialized_objects",
                    status,
                    reason,
                    confidence=0.95,
                    evidence=[f"UnityPy object_count={probe['object_count']}", *categories],
                    patch_route=patch_route,
                )
            )
            if "TEXT_ASSET" in categories:
                capabilities.append(
                    _capability(
                        "TextAsset",
                        EXTRACT_ONLY,
                        "TextAsset objects were enumerated; row locator and semantic writer roundtrip were not run by analysis",
                        confidence=0.95,
                        evidence=["UnityPy type TextAsset"],
                        patch_route="vntext.patch_unity",
                    )
                )
            if "MONOBEHAVIOUR" in categories:
                capabilities.append(
                    _capability(
                        "MonoBehaviour",
                        REVIEW_REQUIRED,
                        "MonoBehaviour objects were enumerated; custom TypeTree fields need field-level text and writer proof",
                        confidence=0.95,
                        evidence=["UnityPy type MonoBehaviour"],
                        patch_route="vntext.patch_unity",
                    )
                )
            if "SCRIPTABLE_OBJECT" in categories:
                capabilities.append(
                    _capability(
                        "ScriptableObject",
                        REVIEW_REQUIRED,
                        "ScriptableObject objects were enumerated; serialized schema and symmetric writer are not established",
                        confidence=0.9,
                        evidence=["UnityPy type ScriptableObject"],
                        patch_route="vntext.patch_unity",
                    )
                )
            if "UNITY_UI_TMP" in categories:
                capabilities.append(
                    _capability(
                        "Unity_UI_TMP",
                        REVIEW_REQUIRED,
                        "Unity UI/TMP type was enumerated; exact text field locator and reopen/semantic verification are not established",
                        confidence=0.9,
                        evidence=["Unity UI/TMP type name"],
                        patch_route="vntext.patch_unity",
                    )
                )
        elif probe.get("status") in {"SKIPPED_SIZE", "DISABLED", "NOT_AVAILABLE"}:
            status = REVIEW_REQUIRED
            reason = f"Unity container recognized but object probe was not complete: {probe.get('error') or probe.get('status')}"
            capabilities.append(_capability("unity_serialized_objects", status, reason, confidence=0.85, evidence=reasons))
        else:
            status = REVIEW_REQUIRED
            reason = "Unity resource signature/name recognized but object structure could not be opened"
            if probe.get("error"):
                reason += f": {probe['error']}"
            capabilities.append(_capability("unity_serialized_objects", status, reason, confidence=0.8, evidence=reasons))
    elif signature in {"json", "csv", "xml", "yaml"}:
        if signature == "json":
            status = SUPPORTED_AND_PATCHABLE
            reason = "valid JSON detected; JSON Pointer extraction/writer route has field-level reopen proof"
            capabilities.append(
                _capability(
                    "structured_json",
                    status,
                    reason,
                    confidence=0.95,
                    evidence=reasons,
                    patch_route="vntext.structured_json",
                )
            )
        elif signature == "csv":
            if has_text_header(text or ""):
                status = SUPPORTED_AND_PATCHABLE
                reason = "delimited CSV with a text-like header; row/column writer route has field-level reopen proof"
                capabilities.append(
                    _capability(
                        "structured_csv",
                        status,
                        reason,
                        confidence=0.9,
                        evidence=reasons,
                        patch_route="vntext.structured_csv",
                    )
                )
            else:
                status = REVIEW_REQUIRED
                reason = "delimited CSV detected but no explicit text-like header was proven"
                capabilities.append(_capability("structured_csv", status, reason, confidence=0.8, evidence=reasons))
        elif signature == "xml":
            status = SUPPORTED_AND_PATCHABLE
            reason = "valid XML detected; element/attribute locator writer route has field-level reopen proof"
            capabilities.append(
                _capability(
                    "structured_xml",
                    status,
                    reason,
                    confidence=0.85,
                    evidence=reasons,
                    patch_route="vntext.structured_xml",
                )
            )
        else:
            status = REVIEW_REQUIRED
            reason = "structured text detected; semantic locator and symmetric writer are not established"
            capabilities.append(_capability("structured_text", status, reason, confidence=0.95, evidence=reasons))
    elif signature in {"json_invalid", "xml_invalid", "xml_unsafe"}:
        status = REVIEW_REQUIRED
        reason = "structured-text extension detected but safe structured writer validation failed"
        capabilities.append(_capability("structured_text", status, reason, confidence=0.9, evidence=reasons))
    elif signature == "sqlite":
        status = REVIEW_REQUIRED
        reason = "SQLite resource detected; only strict rowid/text-column subset has a proven transactional writer; schema coverage remains review-required"
        capabilities.append(
            _capability(
                "structured_sqlite",
                status,
                reason,
                confidence=0.99,
                evidence=reasons,
                patch_route="vntext.extract_sqlite",
            )
        )
    elif signature == "text" and text is not None and text.strip():
        status = EXTRACT_ONLY
        reason = "text candidate detected; a stable package locator and verified writer are not attached at inventory stage"
        capabilities.append(_capability("plain_text_candidate", status, reason, confidence=0.9, evidence=reasons))
        patch_route = "vntext.patch_plain" if path.suffix.lower() in {".txt", ".nani", ".scenario"} else None
    elif signature in {"zip", "gzip"}:
        status = REVIEW_REQUIRED
        reason = "archive/compressed resource detected; inner resources require a bounded reader and explicit review"
        capabilities.append(_capability("container_resource", status, reason, confidence=0.95, evidence=reasons))
    elif candidates:
        status = REVIEW_REQUIRED
        reason = "unknown/binary resource contains bounded printable string candidates"
        capabilities.append(_capability("unknown_string_candidate", status, reason, confidence=0.65, evidence=reasons))
    elif signature in {"runtime_binary", "media_binary", "zip", "gzip", "binary", "empty"}:
        status = UNSUPPORTED
        reason = "no safe text reader/writer route is known for this resource"
        capabilities.append(_capability("resource", status, reason, confidence=0.8, evidence=reasons))
    else:
        status = NOT_DETECTED
        reason = "no capability signature detected"
        capabilities.append(_capability("resource", status, reason, confidence=0.2, evidence=reasons))

    for category in categories:
        if category == "ADDRESSABLES_CATALOG":
            capabilities.append(
                _capability(
                    "addressables_catalog",
                    REVIEW_REQUIRED,
                    "Addressables catalog detected; catalog metadata must be updated only as part of verified bundle patching",
                    confidence=0.98,
                    evidence=["catalog.json"],
                    patch_route="vntext.addressables",
                )
            )
        elif category == "ADDRESSABLES_BUNDLE_CANDIDATE":
            capabilities.append(
                _capability(
                    "addressables_bundle",
                    REVIEW_REQUIRED,
                    "Addressables bundle candidate detected; catalog linkage and generic bundle writer/reopen verification are not established",
                    confidence=0.9,
                    evidence=["bundle path marker or catalog.json adjacency"],
                )
            )
        elif category == "UNITY_LOCALIZATION_CANDIDATE":
            localization_evidence = [
                *path_evidence,
                *[reason for reason in reasons if reason.startswith("Unity Localization script class:")],
            ]
            capabilities.append(
                _capability(
                    "unity_localization",
                    REVIEW_REQUIRED,
                    "Unity Localization marker detected; table identity and writer roundtrip require capability-specific proof",
                    confidence=0.7,
                    evidence=localization_evidence,
                )
            )
        elif category == "NANINOVEL_CANDIDATE":
            capabilities.append(
                _capability(
                    "naninovel",
                    REVIEW_REQUIRED,
                    "Naninovel marker detected; command/identifier distinction requires Naninovel-specific locator and verification",
                    confidence=0.85,
                    evidence=path_evidence,
                    patch_route="vntext.patch_naninovel",
                )
            )

    relative = path.relative_to(scan_root).as_posix() if _is_under(path, scan_root) else str(path)
    digest = None
    if options.include_sha256:
        try:
            digest = _sha256_file(path, context=context, item=relative)
        except OSError as exc:
            context.scan_errors.append({"path": str(path), "error": f"hash failed: {exc}"})
            reasons.append(f"hash unavailable: {exc}")
            if status == SUPPORTED_AND_PATCHABLE:
                status = REVIEW_REQUIRED

    status = _reduce_resource_status(
        status,
        [capability.get("status", REVIEW_REQUIRED) for capability in capabilities],
    )

    return {
        "path": relative,
        "size": size,
        "extension": path.suffix.lower(),
        "signature": signature,
        "encoding": encoding,
        "categories": sorted(set(categories)),
        "status": _normalise_status(status),
        "status_reasons": list(dict.fromkeys(reasons + [item["reason"] for item in capabilities])),
        "capabilities": capabilities,
        "text_candidates": candidates,
        "text_candidate_count": len(candidates),
        "sha256": digest,
        "probe": probe,
    }


def _iter_files(root: Path, context: _InventoryContext) -> Iterable[Path]:
    def on_error(exc: OSError) -> None:
        context.scan_errors.append({"path": str(getattr(exc, "filename", root)), "error": str(exc)})

    try:
        context.check_cancelled()
        count = 0
        file_names_by_directory: dict[Path, list[str]] = {}
        walked_directories: list[tuple[Path, list[str]]] = []
        for directory, dirnames, filenames in os.walk(root, topdown=True, followlinks=False, onerror=on_error):
            context.check_cancelled()
            directory_path = Path(directory)
            valid_names = set()
            for filename in sorted(filenames, key=str.lower):
                context.check_cancelled()
                path = directory_path / filename
                try:
                    if path.is_file():
                        valid_names.add(filename)
                        count += 1
                        if count == 1 or count % 32 == 0:
                            relative = path.relative_to(root).as_posix() if _is_under(path, root) else str(path)
                            context.report_progress("unity_enumerate", count, 0, relative)
                except OSError as exc:
                    context.scan_errors.append({"path": str(path), "error": str(exc)})
            file_names_by_directory[directory_path] = [
                filename for filename in filenames if filename in valid_names
            ]
            walked_directories.append((directory_path, list(dirnames)))

        # Match Path.rglob("*") directory ordering while retaining os.walk's
        # error callbacks and file-name order for the preflight inventory.
        directories = [root]
        for directory_path, dirnames in walked_directories:
            directories.extend(directory_path / dirname for dirname in dirnames)
        for directory_path in directories:
            context.check_cancelled()
            for filename in file_names_by_directory.get(directory_path, []):
                context.check_cancelled()
                yield directory_path / filename
    except OSError as exc:
        context.scan_errors.append({"path": str(root), "error": str(exc)})


def _aggregate_capabilities(resources: list[dict[str, Any]]) -> list[dict[str, Any]]:
    aggregate: dict[str, dict[str, Any]] = {}
    for resource in resources:
        for capability in resource.get("capabilities", []):
            name = str(capability.get("name") or "resource")
            item = aggregate.setdefault(
                name,
                {
                    "capability": name,
                    "resources": 0,
                    "statuses": Counter(),
                    "patch_routes": set(),
                },
            )
            item["resources"] += 1
            item["statuses"][capability.get("status", REVIEW_REQUIRED)] += 1
            if capability.get("patch_route"):
                item["patch_routes"].add(capability["patch_route"])
    output: list[dict[str, Any]] = []
    for name in sorted(aggregate, key=str.lower):
        item = aggregate[name]
        statuses = dict(sorted(item["statuses"].items()))
        status = _reduce_capability_statuses(statuses)
        output.append(
            {
                "capability": name,
                "resources": item["resources"],
                "status": status,
                "statuses": statuses,
                "patch_routes": sorted(item["patch_routes"]),
                "patch_verification": "NOT_RUN",
            }
        )
    return output


def _coverage_report(resources: list[dict[str, Any]], unknown_resources: int) -> dict[str, Any]:
    """Return measurable coverage without treating read-only detection as proof.

    Resource status and capability status are deliberately separate counts: one
    resource can expose several capability observations.  Writer, locator and
    semantic verification are explicitly ``NOT_RUN`` here because this analyzer
    must not patch a game or infer roundtrip evidence from a UnityPy probe.
    """
    resource_status_counts = Counter(resource.get("status", REVIEW_REQUIRED) for resource in resources)
    capability_observations = [
        capability
        for resource in resources
        for capability in resource.get("capabilities", [])
    ]
    capability_status_counts = Counter(
        capability.get("status", REVIEW_REQUIRED) for capability in capability_observations
    )
    observed_routes = sorted({
        str(capability.get("patch_route"))
        for capability in capability_observations
        if capability.get("patch_route")
    })
    resources_with_routes = sum(
        bool(any(capability.get("patch_route") for capability in resource.get("capabilities", [])))
        for resource in resources
    )
    object_candidates = sum(
        int(resource.get("probe", {}).get("object_count", 0) or 0)
        for resource in resources
    )
    text_candidates = sum(int(resource.get("text_candidate_count", 0) or 0) for resource in resources)
    known_statuses = set(_STATUSES)
    classified = sum(resource.get("status") in known_statuses for resource in resources)
    method_contracts: list[dict[str, Any]] = []
    for capability_name, (method, proof) in sorted(_CAPABILITY_METHOD_CONTRACTS.items()):
        contract = PATCHABLE_METHOD_CONTRACTS[method]
        method_contracts.append(
            {
                "capability": capability_name,
                "method": method,
                "reader": contract.reader,
                "writer": contract.writer,
                "locator_kind": contract.locator_kind,
                "required_locator_fields": list(contract.required_locator_fields),
                "precondition": contract.precondition,
                "growth_policy": contract.growth_policy,
                "proof": dict(proof),
                "proof_complete": all(proof.values()),
                "verification_scope": "microfixture_method_contract",
            }
        )
    contract_by_capability = {item["capability"] for item in method_contracts}
    contract_observations = [
        capability
        for capability in capability_observations
        if capability.get("name") in contract_by_capability
    ]
    proven_contracts = [item for item in method_contracts if item["proof_complete"]]
    return {
        "count_semantics": {
            "resource_counts": "one count per inventoried regular file",
            "capability_counts": "one count per capability observation; a resource may count more than once",
        },
        "resources_detected": len(resources),
        "resources_classified": classified,
        "resource_status_counts": dict(sorted(resource_status_counts.items())),
        "unknown_resources": int(unknown_resources),
        "object_candidates": object_candidates,
        "text_candidates": text_candidates,
        "patchable_text": capability_status_counts[SUPPORTED_AND_PATCHABLE],
        "extract_only_text": capability_status_counts[EXTRACT_ONLY],
        "review_required": capability_status_counts[REVIEW_REQUIRED],
        "unsupported": capability_status_counts[UNSUPPORTED],
        "not_detected": capability_status_counts[NOT_DETECTED],
        "capability_status_counts": dict(sorted(capability_status_counts.items())),
        "writer_coverage": {
            "status": "NOT_RUN",
            "observed_patch_routes": observed_routes,
            "resources_with_patch_route": resources_with_routes,
            "resource_writer_invocations": 0,
            "contract_backed_observations": len(contract_observations),
            "method_contracts": method_contracts,
            "reason": "read-only inventory does not invoke a resource writer; method contracts are reported separately",
        },
        "locator_precondition_coverage": {
            "status": "NOT_RUN",
            "observations_with_patch_route": sum(
                bool(capability.get("patch_route")) for capability in capability_observations
            ),
            "contract_backed_observations": len(contract_observations),
            "method_contracts": [
                {
                    "capability": item["capability"],
                    "method": item["method"],
                    "locator_kind": item["locator_kind"],
                    "required_locator_fields": item["required_locator_fields"],
                    "precondition": item["precondition"],
                    "proof_complete": item["proof_complete"],
                }
                for item in method_contracts
            ],
            "reason": "resource locators and source preconditions are not validated by read-only inventory",
        },
        "patch_verification": {
            "status": "NOT_RUN",
            "method_fixture_verified": len(proven_contracts),
            "resource_verified": 0,
            "verified": 0,
            "failed": 0,
            "reason": "analyzer never patches or reopens the game; method_fixture_verified is contract evidence only",
        },
    }


def analyze_unity_game(
    input_path: str | os.PathLike[str],
    *,
    options: AnalyzerOptions | None = None,
    progress_callback: Callable[[dict[str, Any]], None] | None = None,
    is_cancelled: Callable[[], bool] | None = None,
) -> dict[str, Any]:
    """Analyze a Unity game root or executable without writing to it.

    Every regular file reachable from the resolved scan root is represented in
    ``resources`` unless the operating system reports a scan error.  Errors
    are retained in ``scan_errors`` and make ``inventory_complete`` false;
    callers must not interpret an incomplete inventory as a clean scan.
    """

    options = options or AnalyzerOptions()
    resolution = _resolve_game(input_path)
    scan_root = Path(resolution["scan_root"])
    context = _InventoryContext(progress_callback=progress_callback, is_cancelled=is_cancelled)
    resources: list[dict[str, Any]] = []
    input_error = resolution.get("input_error")
    if input_error:
        context.scan_errors.append({"path": resolution["input_path"], "error": input_error})
    elif scan_root.is_dir():
        context.report_progress("unity_enumerate", 0, 0, str(scan_root))
        paths = list(_iter_files(scan_root, context))
        context.report_progress("unity_enumerate", len(paths), len(paths), str(scan_root))
        addressables_roots = tuple(
            sorted(
                {path.parent for path in paths if path.name.lower() == "catalog.json"},
                key=lambda item: item.as_posix().lower(),
            )
        )
        for index, path in enumerate(paths, start=1):
            relative = path.relative_to(scan_root).as_posix() if _is_under(path, scan_root) else str(path)
            context.check_cancelled()
            context.report_progress("unity_classify", index - 1, len(paths), relative)
            resources.append(
                _classify_resource(path, scan_root, options, context, addressables_roots)
            )
            context.report_progress("unity_classify", index, len(paths), relative)
    else:
        context.scan_errors.append({"path": str(scan_root), "error": "scan root is not a directory"})

    status_counts = Counter(resource["status"] for resource in resources)
    signature_counts = Counter(resource["signature"] for resource in resources)
    category_counts: Counter[str] = Counter()
    object_type_counts: Counter[str] = Counter()
    unknown_resources = 0
    candidate_resources = 0
    for resource in resources:
        category_counts.update(resource.get("categories", []))
        object_type_counts.update(resource.get("probe", {}).get("type_counts", {}))
        if "UNKNOWN" in resource.get("categories", []) or resource.get("signature") in {"binary", "unreadable"}:
            unknown_resources += 1
        if resource.get("text_candidate_count", 0):
            candidate_resources += 1

    unity_markers = _unity_markers(scan_root, [Path(item) for item in resolution.get("data_roots", [])])
    is_unity = bool(resolution.get("data_roots") and (unity_markers["detected"] or resolution.get("executable")))
    if not is_unity and unity_markers["detected"]:
        is_unity = True
    unity_detection_status = "DETECTED" if is_unity else NOT_DETECTED
    if context.scan_errors and resources:
        unity_detection_status = REVIEW_REQUIRED if is_unity else NOT_DETECTED

    return {
        "analyzer_version": ANALYZER_VERSION,
        "input_path": resolution["input_path"],
        "scan_root": str(scan_root),
        "unity": {
            "detected": is_unity,
            "status": unity_detection_status,
            "executable": resolution.get("executable"),
            "executables": resolution.get("executables", []),
            "data_roots": resolution.get("data_roots", []),
            "selected_data_root": resolution.get("selected_data_root"),
            "markers": unity_markers["markers"],
        },
        "inventory_complete": not context.scan_errors and not input_error,
        "scan_errors": context.scan_errors,
        "resources": resources,
        "capabilities": _aggregate_capabilities(resources),
        "coverage": _coverage_report(resources, unknown_resources),
        "summary": {
            "resource_count": len(resources),
            "status_counts": dict(sorted(status_counts.items())),
            "signature_counts": dict(sorted(signature_counts.items())),
            "category_counts": dict(sorted(category_counts.items())),
            "object_type_counts": dict(sorted(object_type_counts.items())),
            "unknown_resources": unknown_resources,
            "text_candidate_resources": candidate_resources,
            "scan_error_count": len(context.scan_errors),
            "sha256_enabled": options.include_sha256,
            "unity_probe_enabled": options.probe_unity_objects,
        },
    }


def _json_default(value: Any) -> Any:
    if isinstance(value, Counter):
        return dict(value)
    raise TypeError(f"not JSON serializable: {type(value)!r}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Read-only Unity capability analyzer")
    parser.add_argument("input_path", help="Unity executable, game root, or *_Data directory")
    parser.add_argument("--output", help="write JSON report to this path; never writes below the game root")
    parser.add_argument("--no-hash", action="store_true", help="skip SHA-256 calculation")
    parser.add_argument("--no-unity-probe", action="store_true", help="skip UnityPy object probing")
    args = parser.parse_args(argv)
    report = analyze_unity_game(
        args.input_path,
        options=AnalyzerOptions(include_sha256=not args.no_hash, probe_unity_objects=not args.no_unity_probe),
    )
    payload = json.dumps(report, ensure_ascii=False, indent=2, default=_json_default) + "\n"
    if args.output:
        output = Path(args.output).expanduser().resolve()
        if _is_under(output, Path(report["scan_root"])):
            parser.error("--output must be outside the analyzed game root")
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(payload, encoding="utf-8")
    else:
        sys.stdout.write(payload)
    return 0


__all__ = [
    "ANALYZER_VERSION",
    "AnalyzerOptions",
    "EXTRACT_ONLY",
    "NOT_DETECTED",
    "REVIEW_REQUIRED",
    "SUPPORTED_AND_PATCHABLE",
    "UnityAnalysisCancelled",
    "UNSUPPORTED",
    "analyze_unity_game",
    "detect_resource_kind",
    "main",
]


if __name__ == "__main__":
    raise SystemExit(main())
