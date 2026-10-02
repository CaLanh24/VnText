from __future__ import annotations

import base64
import json
import re
import struct
from pathlib import Path

_ADDRESSABLE_BUNDLE_HASH_RE = re.compile(r"_([0-9a-fA-F]{32})\.bundle$", re.I)


def is_addressables_bundle_rel(source_file: str) -> bool:
    rel = str(source_file or "").replace("\\", "/").lower()
    return "/streamingassets/aa/" in ("/" + rel) or rel.startswith("streamingassets/aa/")


def addressables_catalog_rel(bundle_rel: str) -> Path | None:
    parts = Path(str(bundle_rel).replace("/", "\\")).parts
    if not parts:
        parts = Path(str(bundle_rel).replace("\\", "/")).parts
    for index, part in enumerate(parts):
        if part.lower() == "aa":
            return Path(*parts[: index + 1]) / "catalog.json"
    return None


def _write_7bit_uint(value: int) -> bytes:
    value = int(value)
    if value < 0:
        raise ValueError("7-bit integer must be non-negative")
    out = bytearray()
    while value >= 0x80:
        out.append((value & 0x7F) | 0x80)
        value >>= 7
    out.append(value)
    return bytes(out)


def _read_7bit_uint(data: bytes, pos: int):
    value = 0
    shift = 0
    while True:
        if pos >= len(data) or shift > 35:
            raise ValueError("Invalid Addressables 7-bit integer")
        current = data[pos]
        pos += 1
        value |= (current & 0x7F) << shift
        if not (current & 0x80):
            return value, pos
        shift += 7


def _read_addressables_string(data: bytes, pos: int):
    size, pos = _read_7bit_uint(data, pos)
    end = pos + size
    if end > len(data):
        raise ValueError("Addressables string exceeds extra-data payload")
    return data[pos:end].decode("utf-8"), end


def _encode_addressables_string(value: str) -> bytes:
    raw = str(value).encode("utf-8")
    return _write_7bit_uint(len(raw)) + raw


def parse_addressables_extra_data(raw: bytes):
    data = bytes(raw)
    pos = 0
    records = []
    while pos < len(data):
        marker = data[pos]
        pos += 1
        assembly_name, pos = _read_addressables_string(data, pos)
        class_name, pos = _read_addressables_string(data, pos)
        if pos + 4 > len(data):
            raise ValueError("Addressables record is missing JSON size")
        json_size = struct.unpack_from("<i", data, pos)[0]
        pos += 4
        if json_size < 0 or pos + json_size > len(data):
            raise ValueError("Invalid Addressables JSON size")
        json_raw = data[pos:pos + json_size]
        pos += json_size
        records.append({
            "marker": marker,
            "assembly_name": assembly_name,
            "class_name": class_name,
            "value": json.loads(json_raw.decode("utf-16le")),
        })
    return records


def encode_addressables_extra_data(records) -> bytes:
    out = bytearray()
    for record in records:
        json_raw = json.dumps(
            record["value"], ensure_ascii=False, separators=(",", ":")
        ).encode("utf-16le")
        out.append(int(record["marker"]) & 0xFF)
        out.extend(_encode_addressables_string(record["assembly_name"]))
        out.extend(_encode_addressables_string(record["class_name"]))
        out.extend(struct.pack("<i", len(json_raw)))
        out.extend(json_raw)
    return bytes(out)


def patch_addressables_catalog(source_catalog, target_catalog, patched_bundles) -> int:
    """Disable CRC and update size for rewritten Addressables bundles."""
    source_catalog = Path(source_catalog)
    doc = json.loads(source_catalog.read_text(encoding="utf-8-sig"))
    encoded = str(doc.get("m_ExtraDataString", "") or "")
    if not encoded:
        raise ValueError(f"Addressables catalog has no m_ExtraDataString: {source_catalog}")
    records = parse_addressables_extra_data(base64.b64decode(encoded))
    wanted = {}
    for bundle_rel, bundle_path in patched_bundles:
        match = _ADDRESSABLE_BUNDLE_HASH_RE.search(Path(bundle_rel).name)
        if not match:
            raise ValueError(f"Cannot identify Addressables bundle hash: {bundle_rel}")
        wanted[match.group(1).lower()] = (str(bundle_rel), Path(bundle_path).stat().st_size)

    updated = set()
    for record in records:
        value = record.get("value") or {}
        bundle_hash = str(value.get("m_Hash", "") or "").lower()
        if bundle_hash not in wanted:
            continue
        _bundle_rel, bundle_size = wanted[bundle_hash]
        value["m_Crc"] = 0
        value["m_BundleSize"] = int(bundle_size)
        if "m_UseCrcForCachedBundles" in value:
            value["m_UseCrcForCachedBundles"] = False
        updated.add(bundle_hash)

    missing = set(wanted) - updated
    if missing:
        names = ", ".join(wanted[item][0] for item in sorted(missing))
        raise ValueError(f"Addressables catalog has no matching bundle record: {names}")

    doc["m_ExtraDataString"] = base64.b64encode(
        encode_addressables_extra_data(records)
    ).decode("ascii")
    target_catalog = Path(target_catalog)
    target_catalog.parent.mkdir(parents=True, exist_ok=True)
    target_catalog.write_text(
        json.dumps(doc, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    return len(updated)


def patch_catalogs_for_bundles(game_base: Path, patched_root: Path, patched_bundles, report: list[str]) -> None:
    grouped: dict[str, list[tuple[str, Path]]] = {}
    for rel, target in patched_bundles:
        catalog_rel = addressables_catalog_rel(rel)
        if catalog_rel is None:
            report.append(f"SKIP Addressables catalog: khong tim thay catalog.json cho {rel}")
            continue
        grouped.setdefault(str(catalog_rel), []).append((rel, Path(target)))
    for catalog_rel, bundles in grouped.items():
        source_catalog = game_base / catalog_rel
        target_catalog = patched_root / catalog_rel
        if not source_catalog.exists():
            report.append(f"MISS Addressables catalog: {catalog_rel}")
            continue
        try:
            count = patch_addressables_catalog(source_catalog, target_catalog, bundles)
            report.append(f"ADDRESSABLES catalog {catalog_rel}: updated {count} bundle CRC/size")
        except Exception as exc:
            report.append(f"ERROR Addressables catalog {catalog_rel}: {exc}")
