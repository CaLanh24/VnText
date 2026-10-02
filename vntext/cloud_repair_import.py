"""Fail-closed import of a final CSV returned for a cloud repair package."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import os
import stat
import tempfile
import zipfile
from pathlib import Path
from typing import Any

from vntext import cloud_repair_package as package_contract
from vntext import mt_check
from vntext.package_io import CSV_FIELDS, read_csv_rows_file, write_csv_rows_file


OPTIONAL_MEMBERS = frozenset(
    {
        ".mt/glossary.json",
        ".mt/v2/glossary.json",
        ".mt/translation_memory.json",
    }
)
REQUIRED_MEMBERS = frozenset(
    {
        package_contract.MANIFEST_MEMBER,
        package_contract.TRANSLATION_MEMBER,
        package_contract.CONTEXT_MEMBER,
        package_contract.CONSTRAINTS_MEMBER,
    }
)
KNOWN_MEMBERS = REQUIRED_MEMBERS | OPTIONAL_MEMBERS

_MANIFEST_KEYS = frozenset(
    {
        "schema",
        "schema_version",
        "version",
        "kind",
        "source_identity",
        "translation_csv",
        "draft",
        "allowed_mutations",
        "immutable_fields",
        "final_output_contract",
        "validation_contract",
        "file_inventory",
        "inventory_excludes",
        "identity",
    }
)
_IMMUTABLE_FIELDS = [field for field in CSV_FIELDS if field != "translation"]


class CloudRepairImportError(ValueError):
    """Raised internally for a package or result that cannot be imported."""


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _safe_key(value: object) -> str:
    return str(value).replace("\r", " ").replace("\n", " ")[:128]


def _error(message: str, *, row: int | None = None, key: object | None = None) -> str:
    prefix = []
    if row is not None:
        prefix.append(f"row={row}")
    if key is not None:
        prefix.append(f"key={_safe_key(key)}")
    return f"{' '.join(prefix)}: {message}" if prefix else message


def _reject_json_constant(value: str) -> None:
    raise ValueError(f"invalid JSON constant: {value}")


def _load_json(data: bytes, label: str) -> Any:
    try:
        return json.loads(
            data.decode("utf-8"),
            object_pairs_hook=_unique_object,
            parse_constant=_reject_json_constant,
        )
    except (UnicodeError, ValueError, json.JSONDecodeError) as exc:
        raise CloudRepairImportError(f"{label} is not valid UTF-8 JSON") from exc


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _parse_csv_bytes(data: bytes, label: str) -> list[dict[str, str]]:
    try:
        text = data.decode("utf-8-sig")
        table = list(csv.reader(io.StringIO(text, newline=""), strict=True))
    except (UnicodeError, csv.Error) as exc:
        raise CloudRepairImportError(f"{label} is not valid strict UTF-8 CSV") from exc
    if not table:
        raise CloudRepairImportError(f"{label} is empty")
    if table[0] != CSV_FIELDS:
        raise CloudRepairImportError(f"{label} header does not exactly match CSV_FIELDS")

    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for row_number, values in enumerate(table[1:], start=2):
        if len(values) != len(CSV_FIELDS):
            raise CloudRepairImportError(f"{label} row {row_number} has the wrong field count")
        row = dict(zip(CSV_FIELDS, values))
        key = row["key"]
        if not key.strip() or not row["source_text"].strip():
            raise CloudRepairImportError(f"{label} row {row_number} has an empty key/source_text")
        if key in seen:
            raise CloudRepairImportError(f"{label} row {row_number} duplicates key {_safe_key(key)}")
        seen.add(key)
        rows.append(row)
    if not rows:
        raise CloudRepairImportError(f"{label} has no data rows")
    return rows


def _read_result_csv(path: Path) -> tuple[bytes, list[dict[str, str]]]:
    try:
        raw = path.read_bytes()
        strict_rows = _parse_csv_bytes(raw, "cloud result CSV")
        helper_fields, helper_rows = read_csv_rows_file(path)
    except CloudRepairImportError:
        raise
    except (OSError, UnicodeError, csv.Error, ValueError) as exc:
        raise CloudRepairImportError(f"cannot read cloud result CSV: {path}") from exc
    if helper_fields != CSV_FIELDS or helper_rows != strict_rows:
        raise CloudRepairImportError("package_io CSV reader disagrees with strict cloud result CSV validation")
    return raw, strict_rows


def _zip_members(path: Path) -> tuple[dict[str, bytes], str]:
    try:
        zip_bytes = path.read_bytes()
        zip_sha256 = _sha256(zip_bytes)
        with zipfile.ZipFile(io.BytesIO(zip_bytes), "r") as archive:
            infos = archive.infolist()
            names = [info.filename for info in infos]
            if names != sorted(names) or len(names) != len(set(names)):
                raise CloudRepairImportError("ZIP members must be unique and sorted")
            members: dict[str, bytes] = {}
            for info in infos:
                try:
                    package_contract.validate_member_name(info.filename)
                except package_contract.CloudRepairPackageError as exc:
                    raise CloudRepairImportError(str(exc)) from exc
                if info.is_dir() or ((info.external_attr >> 16) & 0o170000) == stat.S_IFLNK:
                    raise CloudRepairImportError(f"ZIP member is not a regular file: {info.filename}")
                if info.flag_bits & 0x1:
                    raise CloudRepairImportError(f"encrypted ZIP member is not allowed: {info.filename}")
                try:
                    data = archive.read(info)
                except (KeyError, RuntimeError, OSError, zipfile.BadZipFile) as exc:
                    raise CloudRepairImportError(f"cannot read ZIP member: {info.filename}") from exc
                if len(data) != info.file_size:
                    raise CloudRepairImportError(f"ZIP member size mismatch: {info.filename}")
                members[info.filename] = data
            if archive.testzip() is not None:
                raise CloudRepairImportError("ZIP CRC verification failed")
    except CloudRepairImportError:
        raise
    except (OSError, zipfile.BadZipFile, ValueError) as exc:
        raise CloudRepairImportError("cloud repair ZIP is not readable") from exc
    return members, zip_sha256


def _expected_inventory(members: dict[str, bytes]) -> list[dict[str, Any]]:
    return [
        {"path": name, "size": len(members[name]), "sha256": _sha256(members[name])}
        for name in sorted(members)
        if name != package_contract.MANIFEST_MEMBER
    ]


def _validate_manifest(
    manifest: Any,
    members: dict[str, bytes],
    reference_bytes: bytes,
    reference_rows: list[dict[str, str]],
) -> None:
    if not isinstance(manifest, dict):
        raise CloudRepairImportError("cloud repair manifest must be a JSON object")
    if set(manifest) != _MANIFEST_KEYS:
        raise CloudRepairImportError("cloud repair manifest schema keys are invalid")
    if manifest["schema"] != package_contract.SCHEMA:
        raise CloudRepairImportError("cloud repair manifest schema is invalid")
    if manifest["schema_version"] != package_contract.SCHEMA_VERSION or manifest["version"] != package_contract.SCHEMA_VERSION:
        raise CloudRepairImportError("cloud repair manifest version is invalid")
    if manifest["kind"] != package_contract.KIND:
        raise CloudRepairImportError("cloud repair manifest kind is invalid")

    names = set(members)
    if names - KNOWN_MEMBERS:
        raise CloudRepairImportError("ZIP contains a member outside the cloud repair allowlist")
    missing = REQUIRED_MEMBERS - names
    if missing:
        raise CloudRepairImportError("ZIP is missing required member(s): " + ", ".join(sorted(missing)))

    actual_inventory = _expected_inventory(members)
    if manifest["file_inventory"] != actual_inventory:
        raise CloudRepairImportError("cloud repair ZIP file inventory does not match its members")
    if manifest["inventory_excludes"] != [{"path": package_contract.MANIFEST_MEMBER, "reason": "self-hash would be recursive"}]:
        raise CloudRepairImportError("cloud repair manifest inventory exclusion is invalid")

    csv_sha256 = _sha256(reference_bytes)
    expected_source = package_contract._source_identity(reference_rows, csv_sha256)
    if manifest["source_identity"] != expected_source:
        raise CloudRepairImportError("cloud repair source identity does not match reference translation.csv")
    expected_constraints = package_contract._jsonl_bytes(
        [package_contract._structural_constraints(row) for row in reference_rows]
    )
    if members[package_contract.CONSTRAINTS_MEMBER] != expected_constraints:
        raise CloudRepairImportError("cloud repair structural constraints do not match reference translation.csv")

    expected_draft = {
        "draft_present": any(row["translation"].strip() for row in reference_rows),
        "draft_row_count": sum(bool(row["translation"].strip()) for row in reference_rows),
        "draft_engine": None,
    }
    if manifest["draft"] != expected_draft:
        raise CloudRepairImportError("cloud repair draft metadata does not match reference translation.csv")

    expected_immutable = _IMMUTABLE_FIELDS
    if manifest["allowed_mutations"] != ["translation"] or manifest["immutable_fields"] != expected_immutable:
        raise CloudRepairImportError("cloud repair mutable/immutable field contract is invalid")

    expected_translation = {
        "member": package_contract.TRANSLATION_MEMBER,
        "sha256": csv_sha256,
        "row_count": len(reference_rows),
        "fields": CSV_FIELDS,
    }
    if manifest["translation_csv"] != expected_translation:
        raise CloudRepairImportError("cloud repair translation.csv contract is invalid")

    expected_final = {
        "csv_member": package_contract.TRANSLATION_MEMBER,
        "fields": CSV_FIELDS,
        "row_count": len(reference_rows),
        "ordered_keys_sha256": package_contract._sha256_json([row["key"] for row in reference_rows]),
        "ordered_key_source_sha256": expected_source["ordered_key_source_sha256"],
        "mutable_fields": ["translation"],
        "immutable_fields": expected_immutable,
        "source_text_exact": True,
    }
    if manifest["final_output_contract"] != expected_final:
        raise CloudRepairImportError("cloud repair final-output contract is invalid")

    expected_validation = {
        "csv_schema_exact": True,
        "keys_unique_and_ordered": True,
        "source_text_immutable": True,
        "translation_only_mutable": True,
        "structural_constraints_member": package_contract.CONSTRAINTS_MEMBER,
        "context_member": package_contract.CONTEXT_MEMBER,
        "zip_member_names": "relative-posix-unique-sorted",
        "import_scope": "Wave B only; export does not import or merge drafts",
    }
    if manifest["validation_contract"] != expected_validation:
        raise CloudRepairImportError("cloud repair validation contract is invalid")

    expected_identity_material = {
        "schema": package_contract.SCHEMA,
        "version": package_contract.SCHEMA_VERSION,
        "kind": package_contract.KIND,
        "source_identity": expected_source,
        "file_inventory": actual_inventory,
        "allowed_mutations": ["translation"],
        "immutable_fields": expected_immutable,
        "draft": expected_draft,
    }
    expected_identity = {
        "algorithm": "SHA-256",
        "contract_sha256": package_contract._sha256_json(expected_identity_material),
    }
    if manifest["identity"] != expected_identity:
        raise CloudRepairImportError("cloud repair contract identity is invalid")


def _load_reference_package(path: Path) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise CloudRepairImportError("reference package path is not a regular file")
    members, zip_sha256 = _zip_members(path)
    manifest_name = package_contract.MANIFEST_MEMBER
    if manifest_name not in members:
        raise CloudRepairImportError("ZIP is missing the cloud repair manifest")
    manifest = _load_json(members[manifest_name], manifest_name)
    reference_bytes = members.get(package_contract.TRANSLATION_MEMBER)
    if reference_bytes is None:
        raise CloudRepairImportError("ZIP is missing translation.csv")
    reference_rows = _parse_csv_bytes(reference_bytes, "reference translation.csv")
    _validate_manifest(manifest, members, reference_bytes, reference_rows)
    return {
        "members": members,
        "manifest": manifest,
        "reference_bytes": reference_bytes,
        "reference_rows": reference_rows,
        "zip_sha256": zip_sha256,
        "manifest_sha256": _sha256(members[manifest_name]),
    }


def _new_report(package_zip: Path, result_csv: Path, output_csv: Path) -> dict[str, Any]:
    verification = {"semantic": "NOT_RUN", "e2e": "NOT_RUN", "patch": "NOT_RUN"}
    return {
        "status": "FAIL",
        "reference_package": {"path": str(package_zip), "zip_sha256": None, "manifest_sha256": None},
        "reference_package_identity": None,
        "result_input": {"path": str(result_csv), "sha256": None},
        "result_csv_identity": None,
        "output_path": str(output_csv),
        "expected_row_count": None,
        "actual_row_count": None,
        "changed_count": 0,
        "unchanged_count": 0,
        "errors": [],
        "structural_failures": [],
        "merge_applied": False,
        "verification_scope": verification,
        "semantic_verification": verification["semantic"],
        "e2e_verification": verification["e2e"],
        "patch_verification": verification["patch"],
    }


def _reject_output_collision(package_zip: Path, result_csv: Path, output_csv: Path) -> None:
    if output_csv.is_symlink() or output_csv.is_dir():
        raise CloudRepairImportError("output path is not a regular file path")
    resolved_output = output_csv.resolve()
    if resolved_output in {package_zip.resolve(), result_csv.resolve()}:
        raise CloudRepairImportError("output path collides with an input path")
    if output_csv.exists():
        try:
            if os.path.samefile(output_csv, package_zip) or os.path.samefile(output_csv, result_csv):
                raise CloudRepairImportError("output path collides with an input file")
        except FileNotFoundError:
            pass


def _compare_result_rows(
    reference_rows: list[dict[str, str]],
    result_rows: list[dict[str, str]],
    report: dict[str, Any],
) -> None:
    report["expected_row_count"] = len(reference_rows)
    report["actual_row_count"] = len(result_rows)
    seen: set[str] = set()
    for row_number, row in enumerate(result_rows, start=2):
        key = row["key"]
        if key in seen:
            report["errors"].append(_error("duplicate result key", row=row_number, key=key))
        seen.add(key)
    for index, (reference, result) in enumerate(zip(reference_rows, result_rows), start=2):
        if reference["key"] != result["key"]:
            report["errors"].append(
                _error(
                    f"row order/key mismatch; expected key {_safe_key(reference['key'])}",
                    row=index,
                    key=result["key"],
                )
            )
        for field in _IMMUTABLE_FIELDS:
            if reference[field] != result[field]:
                report["errors"].append(_error(f"immutable field changed: {field}", row=index, key=result["key"]))
    if len(result_rows) != len(reference_rows):
        report["errors"].append(
            _error(f"row count mismatch; expected {len(reference_rows)}, got {len(result_rows)}")
        )


def _validate_translations(
    reference_rows: list[dict[str, str]],
    result_rows: list[dict[str, str]],
    report: dict[str, Any],
) -> None:
    for index, (reference, result) in enumerate(zip(reference_rows, result_rows), start=2):
        problems = list(mt_check.structural_problems(reference, result["translation"]))
        if not result["translation"].strip():
            problems.insert(0, "empty translation")
        if not problems:
            continue
        failure = {"row": index, "key": _safe_key(reference["key"]), "problems": problems}
        report["structural_failures"].append(failure)
        report["errors"].append(_error("structural validation failed: " + "; ".join(problems), row=index, key=reference["key"]))


def _atomic_write_result(path: Path, rows: list[dict[str, str]]) -> bytes:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
    os.close(fd)
    temp_path = Path(temp_name)
    try:
        write_csv_rows_file(temp_path, CSV_FIELDS, rows)
        rendered = temp_path.read_bytes()
        if _parse_csv_bytes(rendered, "merged result CSV") != rows:
            raise CloudRepairImportError("atomic result CSV verification failed")
        with temp_path.open("r+b") as handle:
            os.fsync(handle.fileno())
        os.replace(temp_path, path)
        return rendered
    finally:
        try:
            temp_path.unlink()
        except FileNotFoundError:
            pass


def _reconcile_review_only(output_path: Path, rows: list[dict[str, str]]) -> int:
    """Resolve only gate-valid review rows in the package receiving cloud output."""

    package_dir = output_path.parent
    if not (package_dir / "manifest.json").is_file() or not (package_dir / "review_only.csv").is_file():
        return 0

    from vntext.mt_ct2_status import _prune_resolved_review_only

    return _prune_resolved_review_only(
        package_dir,
        rows,
        allow_human_review_resolution=True,
        allow_ct2_junk=True,
    )


def import_cloud_repair_result(
    package_zip: str | Path,
    result_csv: str | Path,
    output_csv: str | Path,
) -> dict[str, Any]:
    """Validate a Wave A ZIP and merge a cloud CSV into a separate output CSV.

    The return value is a structured PASS/FAIL report.  Validation failures do
    not raise and never create or modify ``output_csv``.
    """

    package_path = Path(package_zip).expanduser()
    result_path = Path(result_csv).expanduser()
    output_path = Path(output_csv).expanduser()
    report = _new_report(package_path, result_path, output_path)
    try:
        _reject_output_collision(package_path, result_path, output_path)
        if result_path.is_symlink() or not result_path.is_file():
            raise CloudRepairImportError("cloud result CSV path is not a regular file")
        reference = _load_reference_package(package_path)
        report["reference_package"].update(
            {
                "zip_sha256": reference["zip_sha256"],
                "manifest_sha256": reference["manifest_sha256"],
                "package_identity_sha256": reference["manifest"]["identity"]["contract_sha256"],
                "source_identity_sha256": reference["manifest"]["source_identity"]["sha256"],
                "row_count": len(reference["reference_rows"]),
            }
        )
        report["reference_package_identity"] = reference["manifest"]["identity"]["contract_sha256"]

        result_bytes, result_rows = _read_result_csv(result_path)
        report["result_input"].update({"sha256": _sha256(result_bytes), "row_count": len(result_rows)})
        _compare_result_rows(reference["reference_rows"], result_rows, report)
        _validate_translations(reference["reference_rows"], result_rows, report)
        if report["errors"]:
            return report

        merged_rows = [
            {**reference_row, "translation": result_row["translation"]}
            for reference_row, result_row in zip(reference["reference_rows"], result_rows)
        ]
        changed_count = sum(
            reference_row["translation"] != result_row["translation"]
            for reference_row, result_row in zip(reference["reference_rows"], result_rows)
        )
        rendered = _atomic_write_result(output_path.resolve(), merged_rows)
        review_pruned = _reconcile_review_only(output_path.resolve(), merged_rows)
        result_identity = {
            "algorithm": "SHA-256",
            "sha256": _sha256(rendered),
            "row_count": len(merged_rows),
            "fields": CSV_FIELDS,
        }
        report.update(
            {
                "status": "PASS",
                "changed_count": changed_count,
                "unchanged_count": len(merged_rows) - changed_count,
                "review_pruned": review_pruned,
                "merge_applied": True,
                "result_csv_identity": result_identity,
                "output_sha256": result_identity["sha256"],
            }
        )
        return report
    except Exception as exc:  # noqa: BLE001 - public import is fail-closed and report-based.
        report["errors"].append(str(exc) or type(exc).__name__)
        return report


__all__ = ["CloudRepairImportError", "import_cloud_repair_result"]
