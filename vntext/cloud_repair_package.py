"""Provider-neutral export of a bounded cloud repair package.

This module owns only the export contract.  It deliberately does not know a
provider, model, API, or import/merge workflow.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import os
import re
import zipfile
from collections import Counter
from pathlib import Path
from typing import Any, Mapping

from vntext.context_builder import build_context_records
from vntext.glossary_v2 import load_glossary_v2
from vntext.mt_check import BRACKET_TOKEN, HASHTAG, HEART, PH, TAG, lexical_placeholders
from vntext.mt_memory import MEMORY_VERSION
from vntext.package_io import CSV_FIELDS


SCHEMA = "vntext.cloud_repair_manifest"
SCHEMA_VERSION = 1
KIND = "cloud_repair_package"
MANIFEST_MEMBER = "cloud_repair_manifest.json"
TRANSLATION_MEMBER = "translation.csv"
CONTEXT_MEMBER = ".mt/v2/context.jsonl"
CONSTRAINTS_MEMBER = "cloud_repair/constraints.jsonl"
_OPTIONAL_MEMBERS = {
    ".mt/glossary.json": ".mt/glossary.json",
    ".mt/v2/glossary.json": ".mt/v2/glossary.json",
    ".mt/translation_memory.json": ".mt/translation_memory.json",
}
_MAX_CONTEXT_TEXT = 1200
_MAX_INVENTORY_ITEMS = 32
_MAX_INVENTORY_ITEM_CHARS = 128
_SAFE_NAME_RE = re.compile(r"^[^\x00-\x1f\x7f]+$")


class CloudRepairPackageError(ValueError):
    """Raised when a local package cannot be exported safely."""


CloudRepairExportError = CloudRepairPackageError


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8", "surrogatepass")


def _pretty_json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n").encode(
        "utf-8", "surrogatepass"
    )


def _jsonl_bytes(records: list[Mapping[str, Any]]) -> bytes:
    return b"".join(_canonical_bytes(dict(record)) + b"\n" for record in records)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_json(value: Any) -> str:
    return _sha256(_canonical_bytes(value))


def validate_member_name(name: str) -> str:
    """Validate one relative POSIX ZIP member name."""

    if not isinstance(name, str) or not name or "\x00" in name or "\\" in name:
        raise CloudRepairPackageError(f"unsafe ZIP member name: {name!r}")
    if name.startswith("/") or ":" in name or not _SAFE_NAME_RE.fullmatch(name):
        raise CloudRepairPackageError(f"unsafe ZIP member name: {name!r}")
    parts = name.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        raise CloudRepairPackageError(f"unsafe ZIP member name: {name!r}")
    return name


def _read_translation_csv(path: Path) -> tuple[bytes, list[dict[str, str]]]:
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise CloudRepairPackageError(f"cannot read required translation.csv: {path}") from exc
    if not raw:
        raise CloudRepairPackageError("translation.csv is empty")
    try:
        text = raw.decode("utf-8-sig")
        reader = csv.reader(io.StringIO(text, newline=""), strict=True)
        table = list(reader)
    except (UnicodeError, csv.Error) as exc:
        raise CloudRepairPackageError("translation.csv is not valid strict UTF-8 CSV") from exc
    if not table or table[0] != CSV_FIELDS:
        raise CloudRepairPackageError("translation.csv schema/order does not match CSV_FIELDS")

    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for row_number, values in enumerate(table[1:], start=2):
        if not values or len(values) != len(CSV_FIELDS):
            raise CloudRepairPackageError(f"translation.csv row {row_number} has the wrong field count")
        row = dict(zip(CSV_FIELDS, values))
        key = row["key"]
        if not key.strip() or not row["source_text"].strip():
            raise CloudRepairPackageError(f"translation.csv row {row_number} has an empty key/source_text")
        if key in seen:
            raise CloudRepairPackageError(f"translation.csv contains duplicate key: {key}")
        seen.add(key)
        rows.append(row)
    if not rows:
        raise CloudRepairPackageError("translation.csv has no data rows")
    return raw, rows


def _source_identity(rows: list[dict[str, str]], csv_sha256: str) -> dict[str, Any]:
    ordered = [{"key": row["key"], "source_text": row["source_text"]} for row in rows]
    ordered_hash = _sha256_json(ordered)
    material = {
        "csv_fields": CSV_FIELDS,
        "row_count": len(rows),
        "ordered_key_source_sha256": ordered_hash,
    }
    return {
        "algorithm": "SHA-256",
        **material,
        "translation_csv_sha256": csv_sha256,
        "ordered_key_source_identity_sha256": ordered_hash,
        "sha256": _sha256_json(material),
    }


def _bounded_inventory(pattern, text: str) -> dict[str, Any]:
    values = sorted(str(value) for value in pattern.findall(text))
    clipped = [value[:_MAX_INVENTORY_ITEM_CHARS] for value in values[:_MAX_INVENTORY_ITEMS]]
    return {
        "count": len(values),
        "items": clipped,
        "truncated": len(values) > len(clipped) or any(len(value) > _MAX_INVENTORY_ITEM_CHARS for value in values),
        "sha256": _sha256_json(values),
    }


def _structural_constraints(row: Mapping[str, str]) -> dict[str, Any]:
    source = str(row.get("source_text") or "")
    escape_counts = Counter(
        token
        for token in ("\\n", "\\r", "\\t")
        if (count := source.count(token))
        for _ in range(count)
    )
    lexical = sorted("{" + name + "}" for name in lexical_placeholders(source))
    return {
        "key": str(row.get("key") or ""),
        "source_sha256": _sha256(source.encode("utf-8", "surrogatepass")),
        "placeholders": _bounded_inventory(PH, source),
        "tags": _bounded_inventory(TAG, source),
        "bracket_tokens": _bounded_inventory(BRACKET_TOKEN, source),
        "hashtags": _bounded_inventory(HASHTAG, source),
        "lexical_placeholders": {
            "count": len(lexical),
            "items": lexical[:_MAX_INVENTORY_ITEMS],
            "truncated": len(lexical) > _MAX_INVENTORY_ITEMS,
            "sha256": _sha256_json(lexical),
        },
        "literal_newline_count": source.count("\\n"),
        "heart_count": source.count(HEART),
        "escape_sequence_counts": dict(sorted(escape_counts.items())),
    }


def _build_context(rows: list[dict[str, str]]) -> tuple[bytes, list[dict[str, Any]]]:
    records = build_context_records(rows)
    if len(records) != len(rows):
        raise CloudRepairPackageError("context builder did not return one record per CSV row")
    enriched: list[dict[str, Any]] = []
    for row, record in zip(rows, records):
        if str(record.get("key") or "") != row["key"]:
            raise CloudRepairPackageError("context builder key mapping does not match translation.csv order")
        draft = row["translation"]
        enriched.append(
            {
                **record,
                "source_sha256": _sha256(row["source_text"].encode("utf-8", "surrogatepass")),
                "draft": draft[:_MAX_CONTEXT_TEXT],
                "draft_sha256": _sha256(draft.encode("utf-8", "surrogatepass")),
                "draft_truncated": len(draft) > _MAX_CONTEXT_TEXT,
            }
        )
    return _jsonl_bytes(enriched), enriched


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError, TypeError) as exc:
        raise CloudRepairPackageError(f"invalid optional artifact: {path}") from exc


def _optional_artifact(path: Path, member: str) -> bytes | None:
    if not path.exists() and not path.is_symlink():
        return None
    if path.is_symlink() or not path.is_file():
        raise CloudRepairPackageError(f"optional artifact is not a regular file: {path}")

    payload = _read_json(path)
    if member == ".mt/v2/glossary.json":
        loaded = load_glossary_v2(path.parents[2])
        if loaded.get("warnings"):
            raise CloudRepairPackageError(f"invalid V2 glossary: {path}")
        entries = loaded.get("entries") or []
        if not entries:
            return None
        canonical = {"schema_version": 1, "entries": entries}
        return _pretty_json_bytes(canonical)

    if member == ".mt/glossary.json":
        if not isinstance(payload, dict):
            raise CloudRepairPackageError(f"flat glossary must be an object: {path}")
        canonical: dict[str, str] = {}
        for key, value in payload.items():
            if not isinstance(key, str) or not isinstance(value, str) or not key.strip() or not value.strip():
                raise CloudRepairPackageError(f"flat glossary contains an invalid entry: {path}")
            canonical[key] = value.strip()
        return _pretty_json_bytes(dict(sorted(canonical.items()))) if canonical else None

    if member == ".mt/translation_memory.json":
        if not isinstance(payload, dict) or payload.get("version") != MEMORY_VERSION:
            raise CloudRepairPackageError(f"unsupported translation memory: {path}")
        entries = payload.get("entries")
        if not isinstance(entries, list):
            raise CloudRepairPackageError(f"translation memory entries are not a list: {path}")
        normalized: list[dict[str, str]] = []
        seen: set[tuple[str, str, str]] = set()
        for entry in entries:
            if not isinstance(entry, dict):
                raise CloudRepairPackageError(f"translation memory contains a non-object entry: {path}")
            value = {
                name: str(entry.get(name) or "").strip()
                for name in ("source", "import_method", "context_family", "translation")
            }
            if not all(value.values()):
                raise CloudRepairPackageError(f"translation memory contains an incomplete entry: {path}")
            identity = (value["source"], value["import_method"], value["context_family"])
            if identity in seen:
                raise CloudRepairPackageError(f"translation memory contains duplicate identity: {path}")
            seen.add(identity)
            normalized.append(value)
        if not normalized:
            return None
        normalized.sort(key=lambda item: tuple(item[name] for name in ("source", "import_method", "context_family", "translation")))
        return _pretty_json_bytes({"version": MEMORY_VERSION, "entries": normalized})

    raise CloudRepairPackageError(f"unsupported optional artifact: {path}")


def _write_deterministic_zip(output_path: Path, members: Mapping[str, bytes]) -> None:
    names = list(members)
    if names != sorted(names) or len(names) != len(set(names)):
        raise CloudRepairPackageError("ZIP member names are not unique and sorted")
    for name in names:
        validate_member_name(name)
    temp_path = output_path.with_name(f".{output_path.name}.tmp")
    try:
        with zipfile.ZipFile(temp_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
            for name in names:
                info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                info.create_system = 0
                info.external_attr = 0
                info.extra = b""
                info.comment = b""
                archive.writestr(info, members[name], compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
        with zipfile.ZipFile(temp_path, "r") as archive:
            names_read = archive.namelist()
            if names_read != names or len(names_read) != len(set(names_read)) or archive.testzip() is not None:
                raise CloudRepairPackageError("written ZIP failed safe-member verification")
        os.replace(temp_path, output_path)
    finally:
        try:
            temp_path.unlink()
        except FileNotFoundError:
            pass


def export_cloud_repair_package(package_dir: str | Path, output_zip: str | Path) -> dict[str, Any]:
    """Export one deterministic, provider-neutral cloud repair ZIP package."""

    package_input = Path(package_dir).expanduser()
    output_input = Path(output_zip).expanduser()
    if package_input.is_symlink():
        raise CloudRepairPackageError(f"package directory is a symlink: {package_input}")
    if output_input.is_symlink():
        raise CloudRepairPackageError(f"output path is a symlink: {output_input}")
    package = package_input.resolve()
    output = output_input.resolve()
    if not package.is_dir():
        raise CloudRepairPackageError(f"package directory is not a regular directory: {package}")
    if output.suffix.lower() != ".zip":
        raise CloudRepairPackageError("output path must have a .zip suffix")
    if output.exists() and (output.is_symlink() or output.is_dir()):
        raise CloudRepairPackageError(f"output path is not a regular file path: {output}")

    csv_path = package / TRANSLATION_MEMBER
    csv_bytes, rows = _read_translation_csv(csv_path)
    csv_sha256 = _sha256(csv_bytes)
    source_identity = _source_identity(rows, csv_sha256)
    context_bytes, context_records = _build_context(rows)
    constraints = [_structural_constraints(row) for row in rows]
    constraints_bytes = _jsonl_bytes(constraints)

    members: dict[str, bytes] = {
        TRANSLATION_MEMBER: csv_bytes,
        CONTEXT_MEMBER: context_bytes,
        CONSTRAINTS_MEMBER: constraints_bytes,
    }
    for relative, member in _OPTIONAL_MEMBERS.items():
        optional = _optional_artifact(package / relative, member)
        if optional is not None:
            members[member] = optional

    ordered_members = {name: members[name] for name in sorted(members)}
    inventory = [
        {"path": name, "size": len(data), "sha256": _sha256(data)}
        for name, data in ordered_members.items()
    ]
    draft_count = sum(bool(row["translation"].strip()) for row in rows)
    draft = {
        "draft_present": draft_count > 0,
        "draft_row_count": draft_count,
        "draft_engine": None,
    }
    immutable_fields = [field for field in CSV_FIELDS if field != "translation"]
    identity_material = {
        "schema": SCHEMA,
        "version": SCHEMA_VERSION,
        "kind": KIND,
        "source_identity": source_identity,
        "file_inventory": inventory,
        "allowed_mutations": ["translation"],
        "immutable_fields": immutable_fields,
        "draft": draft,
    }
    contract_identity = _sha256_json(identity_material)
    manifest = {
        "schema": SCHEMA,
        "schema_version": SCHEMA_VERSION,
        "version": SCHEMA_VERSION,
        "kind": KIND,
        "source_identity": source_identity,
        "translation_csv": {
            "member": TRANSLATION_MEMBER,
            "sha256": csv_sha256,
            "row_count": len(rows),
            "fields": CSV_FIELDS,
        },
        "draft": draft,
        "allowed_mutations": ["translation"],
        "immutable_fields": immutable_fields,
        "final_output_contract": {
            "csv_member": TRANSLATION_MEMBER,
            "fields": CSV_FIELDS,
            "row_count": len(rows),
            "ordered_keys_sha256": _sha256_json([row["key"] for row in rows]),
            "ordered_key_source_sha256": source_identity["ordered_key_source_sha256"],
            "mutable_fields": ["translation"],
            "immutable_fields": immutable_fields,
            "source_text_exact": True,
        },
        "validation_contract": {
            "csv_schema_exact": True,
            "keys_unique_and_ordered": True,
            "source_text_immutable": True,
            "translation_only_mutable": True,
            "structural_constraints_member": CONSTRAINTS_MEMBER,
            "context_member": CONTEXT_MEMBER,
            "zip_member_names": "relative-posix-unique-sorted",
            "import_scope": "Wave B only; export does not import or merge drafts",
        },
        "file_inventory": inventory,
        "inventory_excludes": [
            {"path": MANIFEST_MEMBER, "reason": "self-hash would be recursive"},
        ],
        "identity": {
            "algorithm": "SHA-256",
            "contract_sha256": contract_identity,
        },
    }
    manifest_bytes = _pretty_json_bytes(manifest)
    package_members = {**ordered_members, MANIFEST_MEMBER: manifest_bytes}
    package_members = {name: package_members[name] for name in sorted(package_members)}

    output.parent.mkdir(parents=True, exist_ok=True)
    _write_deterministic_zip(output, package_members)
    zip_sha256 = _sha256(output.read_bytes())
    return {
        "status": "PASS",
        "output_zip": str(output),
        "manifest_member": MANIFEST_MEMBER,
        "package_identity_sha256": contract_identity,
        "source_identity_sha256": source_identity["sha256"],
        "translation_csv_sha256": csv_sha256,
        "manifest_sha256": _sha256(manifest_bytes),
        "zip_sha256": zip_sha256,
        "members": list(package_members),
        "file_inventory": inventory,
        "row_count": len(rows),
        "context_records": len(context_records),
        "draft_present": draft["draft_present"],
        "deterministic_guarantee": "byte-reproducible for identical validated input bytes and optional artifacts",
    }


__all__ = [
    "CloudRepairPackageError",
    "CloudRepairExportError",
    "CONSTRAINTS_MEMBER",
    "CONTEXT_MEMBER",
    "KIND",
    "MANIFEST_MEMBER",
    "SCHEMA",
    "SCHEMA_VERSION",
    "TRANSLATION_MEMBER",
    "export_cloud_repair_package",
    "validate_member_name",
]
