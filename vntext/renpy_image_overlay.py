"""Conservative Ren'Py locale image overlays for imagemap/imagebutton bitmaps with baked-in text.

Ren'Py loads ``game/tl/<language>/<path>`` instead of ``<path>`` while that language is active, so a localized bitmap can ship as an
additive payload file and the original loose or archived asset is never edited.  This module only *accepts* an already rendered image
for an asset when every one of these holds (anything else fails closed, nothing is guessed or inpainted here):

* the asset path is referenced by a literal ``ground/idle/hover/...`` property inside an ``imagemap``/``imagebutton`` block of a loose
  ``.rpy`` source (inert text scan, no evaluation), so only *known* asset paths are replaced;
* the asset exists exactly once, either loose or in exactly one ``game/*.rpa`` archive, and no locale image exists for it yet;
* the baseline format is lossless (PNG or lossless WebP); lossy baselines cannot keep the pixels outside the regions identical;
* the rendered image has the same dimensions and mode as the baseline, so hotspot rectangles stay valid;
* every changed pixel lies inside the declared regions (hotspot geometry is recorded, and every recorded hotspot stays in bounds).
"""
from __future__ import annotations

import hashlib
import io
import json
import re
from pathlib import Path

from vntext.renpy_archive import RenPyArchive

LANGUAGE = "vietnamese"
LOCALE_ROOT = f"game/tl/{LANGUAGE}/"
MAX_IMAGES = 16
MAX_IMAGE_BYTES = 32 * 1024 * 1024
MAX_PIXELS = 16_000_000
MAX_SCRIPT_BYTES = 8 * 1024 * 1024
MAX_SPEC_BYTES = 65536
_LOSSLESS = {".png": "PNG", ".webp": "WEBP"}
_REFERENCE = re.compile(r"""^(ground|idle|hover|insensitive|selected_idle|selected_hover|selected_insensitive)\s+(['"])([^'"\\\r\n]+)\2\s*(?:#.*)?$""")
_HOTSPOT = re.compile(r"^hotspot\s*\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)")
_BLOCK = re.compile(r"^(imagemap|imagebutton)\b[^#]*:\s*(?:#.*)?$")
_TARGET = re.compile(r"game/tl/" + LANGUAGE + r"/(?:[A-Za-z0-9_.\- ]+/)*[A-Za-z0-9_.\- ]+\.(?:png|webp)", re.IGNORECASE)


class ImageOverlayError(ValueError):
    pass


def _regular(path) -> Path:
    path = Path(path).absolute()
    for part in (path, *path.parents):
        if part.exists() and (part.is_symlink() or getattr(part.stat(), "st_file_attributes", 0) & 0x400):
            raise ImageOverlayError("image overlay paths must not pass through links or reparse points")
    return path


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _asset_path(value) -> str:
    if not isinstance(value, str) or not RenPyArchive._safe_name(value):
        raise ImageOverlayError("unsafe image overlay asset path")
    if Path(value).suffix.lower() not in _LOSSLESS:
        raise ImageOverlayError("image overlay supports only lossless PNG/WebP assets (a lossy baseline cannot keep untouched pixels identical)")
    if any(part.casefold() in {"tl", "saves", "cache"} for part in value.split("/")):
        raise ImageOverlayError("image overlay allows only original static image paths")
    if not _TARGET.fullmatch(LOCALE_ROOT + value):
        raise ImageOverlayError("image overlay asset path has unsupported characters")
    return value


def _decode(data: bytes, relative: str, label: str):
    from PIL import Image
    expected = _LOSSLESS[Path(relative).suffix.lower()]
    if len(data) > MAX_IMAGE_BYTES:
        raise ImageOverlayError(f"{label} exceeds 32 MiB")
    try:
        with Image.open(io.BytesIO(data)) as opened:
            if opened.format != expected:
                raise ImageOverlayError(f"{label} is {opened.format}, expected {expected} for {relative}")
            if opened.width * opened.height > MAX_PIXELS or getattr(opened, "n_frames", 1) != 1:
                raise ImageOverlayError(f"{label} is too large or animated")
            opened.load()
            if opened.mode not in {"RGB", "RGBA"}:
                raise ImageOverlayError(f"{label} mode {opened.mode} is not RGB/RGBA")
            return opened.copy()
    except ImageOverlayError:
        raise
    except Exception as exc:  # noqa: BLE001 - decoder failures fail closed
        raise ImageOverlayError(f"{label} cannot be decoded: {exc}") from exc


def scan_image_references(game_root) -> dict[str, list[dict]]:
    """Inert scan of loose ``game/**/*.rpy`` for literal asset paths inside imagemap/imagebutton blocks (never evaluates code)."""
    game = _regular(Path(game_root) / "game")
    references: dict[str, list[dict]] = {}
    for script in sorted(game.rglob("*.rpy")):
        relative = script.relative_to(game).as_posix()
        if relative.casefold().startswith("tl/") or script.is_symlink() or script.stat().st_size > MAX_SCRIPT_BYTES:
            continue
        lines = script.read_text(encoding="utf-8-sig", errors="replace").splitlines()
        block = None
        for number, raw in enumerate(lines, 1):
            stripped = raw.strip()
            if not stripped or stripped.startswith("#"):
                continue
            indent = len(raw) - len(raw.lstrip())
            if block is not None and indent <= block["indent"]:
                block = None
            match = _BLOCK.match(stripped)
            if match and block is None:
                block = {"kind": match.group(1), "indent": indent, "line": number, "assets": [], "hotspots": [], "file": "game/" + relative}
                continue
            if block is None:
                continue
            ref = _REFERENCE.match(stripped)
            if ref:
                block["assets"].append((ref.group(1), ref.group(3), number))
                references.setdefault(ref.group(3), []).append(block)
            hot = _HOTSPOT.match(stripped)
            if hot:
                block["hotspots"].append([int(n) for n in hot.groups()])
    return references


def locate_baseline(game_root, relative: str) -> tuple[bytes, dict]:
    """The one original copy of ``relative`` (loose xor in exactly one top-level archive) with its identity."""
    game = _regular(Path(game_root) / "game")
    loose = _regular(game / relative)
    found: list[tuple[bytes, dict]] = []
    if loose.is_file():
        data = loose.read_bytes()
        found.append((data, {"path": "game/" + relative, "sha256": _sha256(data)}))
    for archive in sorted(game.glob("*.rpa")):
        _regular(archive)
        opened = RenPyArchive(archive)
        if relative in opened.members:
            item = opened.read_member(relative)
            found.append((item["content"], {"path": "game/" + archive.name, "sha256": item["container_sha256"], "member": relative,
                                            "member_sha256": item["member_sha256"]}))
    if not found:
        raise ImageOverlayError(f"asset not found in the game: {relative}")
    if len(found) != 1:
        raise ImageOverlayError(f"asset is present more than once (loose/archive shadowing is ambiguous): {relative}")
    return found[0]


def _region(raw, size) -> list[int]:
    if not isinstance(raw, list) or len(raw) != 4 or any(type(n) is not int for n in raw):
        raise ImageOverlayError("region needs integer x,y,width,height")
    x, y, w, h = raw
    if x < 0 or y < 0 or w <= 0 or h <= 0 or x + w > size[0] or y + h > size[1]:
        raise ImageOverlayError("region lies outside the image")
    return [x, y, w, h]


def _encode(image, relative: str) -> bytes:
    stream = io.BytesIO()
    if Path(relative).suffix.lower() == ".webp":
        image.save(stream, format="WEBP", lossless=True, quality=100)
    else:
        image.save(stream, format="PNG", compress_level=9)
    return stream.getvalue()


def _change_mask(first, second):
    """'L' image: 255 where any channel differs (Pillow only; the packaged worker ships no numpy)."""
    from PIL import ImageChops
    bands = ImageChops.difference(first, second).split()
    merged = bands[0]
    for band in bands[1:]:
        merged = ImageChops.lighter(merged, band)
    return merged.point(lambda value: 255 if value else 0)


def prepare_image_overlays(game_root, spec_path) -> tuple[dict[str, bytes], dict]:
    """Validate the user spec and rendered images; returns ``{relative target: payload bytes}`` and the evidence report."""
    spec_file = _regular(spec_path)
    if spec_file.stat().st_size > MAX_SPEC_BYTES:
        raise ImageOverlayError("image overlay spec exceeds 64 KiB")
    spec = json.loads(spec_file.read_text(encoding="utf-8-sig"))
    if not isinstance(spec, dict) or spec.get("schema") != 1 or spec.get("language", LANGUAGE) != LANGUAGE or set(spec) - {"schema", "language", "images"}:
        raise ImageOverlayError("unsupported image overlay spec")
    items = spec.get("images")
    if not isinstance(items, list) or not 0 < len(items) <= MAX_IMAGES:
        raise ImageOverlayError("image overlay spec needs 1..16 images")
    references = scan_image_references(game_root)
    payloads: dict[str, bytes] = {}
    entries = []
    from PIL import Image, ImageChops, ImageDraw
    for item in items:
        if not isinstance(item, dict) or set(item) - {"path", "rendered", "regions"}:
            raise ImageOverlayError("malformed image overlay item")
        relative = _asset_path(item.get("path"))
        target = LOCALE_ROOT + relative
        if target in payloads:
            raise ImageOverlayError(f"duplicate image overlay target: {relative}")
        blocks = references.get(relative)
        if not blocks:
            raise ImageOverlayError(f"asset is not a known imagemap/imagebutton image in the game scripts: {relative}")
        original, baseline = locate_baseline(game_root, relative)
        base_image = _decode(original, relative, "baseline")
        rendered_file = _regular(spec_file.parent / str(item.get("rendered") or ""))
        if not rendered_file.is_file():
            raise ImageOverlayError(f"rendered image missing for {relative}")
        rendered = _decode(rendered_file.read_bytes(), relative, "rendered image")
        if rendered.size != base_image.size or rendered.mode != base_image.mode:
            raise ImageOverlayError(f"rendered image must keep size/mode {base_image.size}/{base_image.mode}: {relative}")
        regions = [_region(region, base_image.size) for region in item.get("regions") or []]
        if not regions:
            raise ImageOverlayError("image overlay needs at least one region")
        hotspots = [spot for block in blocks for spot in block["hotspots"]]
        if any(x + w > base_image.width or y + h > base_image.height for x, y, w, h in hotspots):
            raise ImageOverlayError("a recorded hotspot lies outside the image; the bitmap geometry is not this screen's")
        allowed = Image.new("L", base_image.size, 0)
        draw = ImageDraw.Draw(allowed)
        for x, y, w, h in regions:
            draw.rectangle([x, y, x + w - 1, y + h - 1], fill=255)
        changed = _change_mask(base_image, rendered)
        bbox = changed.getbbox()
        if bbox is None:
            raise ImageOverlayError(f"rendered image is identical to the original: {relative}")
        if ImageChops.subtract(changed, allowed).getbbox() is not None:
            raise ImageOverlayError(f"rendered image changes pixels outside the declared regions: {relative}")
        data = _encode(rendered, relative)
        again = _decode(data, relative, "encoded payload")
        if _change_mask(again, rendered).getbbox() is not None:
            raise ImageOverlayError("encoded payload does not read back identically")
        payloads[target] = data
        entries.append({
            "path": relative, "target": target, "sha256": _sha256(data), "rendered_sha256": _sha256(rendered_file.read_bytes()),
            "width": base_image.width, "height": base_image.height, "mode": base_image.mode, "baseline": baseline,
            "regions": regions, "changed_pixels": int(changed.histogram()[255]),
            "changed_bbox": [int(v) for v in bbox],
            "references": [{"file": b["file"], "kind": b["kind"], "line": b["line"], "hotspots": b["hotspots"]} for b in blocks],
        })
    report = {"schema": 1, "language": LANGUAGE, "images": entries,
              "scope": "Known imagemap/imagebutton bitmaps only; original loose/archived assets are never edited; activation needs the Vietnamese language."}
    return payloads, report


def verify_baselines(game_root, report: dict) -> None:
    """Re-read every baseline and refuse a drifted or newly shadowed asset (used before and after publication)."""
    for entry in report["images"]:
        original, baseline = locate_baseline(game_root, entry["path"])
        if baseline != entry["baseline"]:
            raise ImageOverlayError(f"image baseline changed: {entry['path']}")
        existing = _regular(Path(game_root) / entry["target"])
        if existing.exists() and (not existing.is_file() or _sha256(existing.read_bytes()) != entry["sha256"]):
            raise ImageOverlayError(f"a different locale image already exists; uninstall the previous locale patch first: {entry['target']}")


def baseline_checks(report: dict) -> list[dict]:
    """Installer ``game_checks`` rows: the loose file or the whole container, hashed as it is on disk."""
    checks = []
    for entry in report["images"]:
        row = {"path": entry["baseline"]["path"], "sha256": entry["baseline"]["sha256"]}
        if row not in checks:
            checks.append(row)
    return checks


def validate_report_payload(report, payload_root: Path) -> set[str]:
    """Exact payload files an ``image_overlay.json`` may add; every one is hash/dimension-bound or the output is rejected."""
    if not isinstance(report, dict) or report.get("schema") != 1 or report.get("language") != LANGUAGE:
        raise ImageOverlayError("unsupported image overlay report")
    entries = report.get("images")
    if not isinstance(entries, list) or not 0 < len(entries) <= MAX_IMAGES:
        raise ImageOverlayError("image overlay report needs 1..16 images")
    accepted: set[str] = set()
    for entry in entries:
        target = str(entry.get("target") if isinstance(entry, dict) else "")
        if not _TARGET.fullmatch(target) or target in accepted or "/../" in target or not RenPyArchive._safe_name(target):
            raise ImageOverlayError("image overlay target is outside the locale image layout: " + target)
        relative = _asset_path(target[len(LOCALE_ROOT):])
        if entry.get("path") != relative or not re.fullmatch(r"[0-9a-f]{64}", str(entry.get("sha256") or "")):
            raise ImageOverlayError("image overlay report entry is malformed: " + target)
        file = payload_root / target
        if file.is_symlink() or not file.is_file():
            raise ImageOverlayError("image overlay payload missing: " + target)
        data = file.read_bytes()
        if _sha256(data) != entry["sha256"]:
            raise ImageOverlayError("image overlay payload differs from its report: " + target)
        image = _decode(data, relative, "payload")
        if [image.width, image.height] != [entry.get("width"), entry.get("height")] or image.mode != entry.get("mode"):
            raise ImageOverlayError("image overlay payload geometry differs from its report: " + target)
        accepted.add(target)
    return accepted


def inventory_image_candidates(game_root, limit: int = 256) -> dict:
    """Discovery only: every literal imagemap/imagebutton asset with its states and whether the verified locale overlay could carry it.

    No OCR and no writes.  A candidate still needs an Owner-authored spec (changed pixels inside declared regions) before anything is staged."""
    root = Path(game_root)
    references = scan_image_references(root)
    game = _regular(root / "game")
    rows = []
    for asset in sorted(references):
        blocks = references[asset]
        states = sorted({state for block in blocks for state, name, _line in block["assets"] if name == asset})
        row = {"asset": asset, "states": states, "uses": [{"file": block["file"], "line": block["line"], "kind": block["kind"]} for block in blocks[:8]],
               "sibling_assets": sorted({name for block in blocks for _state, name, _line in block["assets"] if name != asset})[:16]}
        try:
            if Path(asset).suffix.lower() not in _LOSSLESS:
                row.update(status="UNSUPPORTED_FORMAT", why="only lossless PNG/WebP can keep untouched pixels identical")
            else:
                _asset_path(asset)
                if _regular(game / "tl" / LANGUAGE / asset).is_file():
                    row["locale_copy_exists"] = True
                data, identity = locate_baseline(root, asset)
                image = _decode(data, asset, "baseline")
                row.update(status="SUPPORTED_LOSSLESS", why="single baseline, lossless, RGB/RGBA", width=image.width, height=image.height,
                           baseline=identity["path"] + ("::" + identity["member"] if "member" in identity else ""))
        except ImageOverlayError as exc:
            message = str(exc)
            row.update(status="AMBIGUOUS_SHADOW" if "more than once" in message else "MISSING" if "not found" in message else "UNSUPPORTED", why=message[:200])
        rows.append(row)
        if len(rows) >= limit:
            break
    counts = {}
    for row in rows:
        counts[row["status"]] = counts.get(row["status"], 0) + 1
    return {"schema": 1, "candidates": rows, "summary": dict(sorted(counts.items())),
            "coverage_scope": "Literal assets inside imagemap/imagebutton blocks of loose game/**/*.rpy only. Scripts inside .rpa archives, .rpyc-only games, dynamic names and images drawn by other displayables are not discovered. Discovery never edits pixels or recognises text."}
