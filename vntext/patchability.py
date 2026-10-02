"""Explicit extract/patch symmetry contracts for translation-flow entries.

The existing package split is a compatibility boundary and intentionally keeps
its method allow-list.  This module adds the stricter, inspectable contract
that a new extractor can use before promoting entries into the main flow.
It does not mutate entries or CSV files.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import re
from typing import Any, Iterable


SUPPORTED_AND_PATCHABLE = "SUPPORTED_AND_PATCHABLE"
EXTRACT_ONLY = "EXTRACT_ONLY"
REVIEW_REQUIRED = "REVIEW_REQUIRED"
UNSUPPORTED = "UNSUPPORTED"

_PROOF_FIELDS = ("reader", "writer", "preflight", "reopen", "semantic_verify")

# These proof markers are method-level evidence, not a claim that every
# translation fits every game's serialized layout.  The writer/preflight
# policy still decides whether a particular row can be applied; the markers
# are attached only to extractors covered by a disposable roundtrip fixture.
PLAIN_TEXT_PATCH_PROOF = {field: True for field in _PROOF_FIELDS}
UNITY_TEXTASSET_PATCH_PROOF = {field: True for field in _PROOF_FIELDS}
UNITY_TYPETREE_PATCH_PROOF = {field: True for field in _PROOF_FIELDS}
UNITY_UI_PATCH_PROOF = {field: True for field in _PROOF_FIELDS}
NANINOVEL_PATCH_PROOF = {field: True for field in _PROOF_FIELDS}
STRUCTURED_JSON_PATCH_PROOF = {field: True for field in _PROOF_FIELDS}
STRUCTURED_CSV_PATCH_PROOF = {field: True for field in _PROOF_FIELDS}
STRUCTURED_XML_PATCH_PROOF = {field: True for field in _PROOF_FIELDS}
STRUCTURED_SQLITE_PATCH_PROOF = {field: True for field in _PROOF_FIELDS}
UNITY_LOCALIZATION_PATCH_PROOF = {field: True for field in _PROOF_FIELDS}
RENPY_DIALOGUE_PATCH_PROOF = {field: True for field in _PROOF_FIELDS}
RENPY_STRING_PATCH_PROOF = {field: True for field in _PROOF_FIELDS}

RENPY_NATIVE_CONTRACT_VERSION = 1
RENPY_ENGINE = "renpy"
RENPY_DIALOGUE_UNIT = "dialogue"
RENPY_STRING_UNIT = "string"
RENPY_UNIT_TYPES = frozenset({RENPY_DIALOGUE_UNIT, RENPY_STRING_UNIT})
RENPY_GAME_OWNED = "game_owned"
RENPY_COMMON = "renpy_common"
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_RENPY_NATIVE_ID = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


@dataclass(frozen=True)
class MethodContract:
    method: str
    reader: str
    writer: str
    locator_kind: str
    required_locator_fields: tuple[str, ...]
    precondition: str
    growth_policy: str


PATCHABLE_METHOD_CONTRACTS: dict[str, MethodContract] = {
    "renpy_dialogue": MethodContract("renpy_dialogue", "vntext.renpy_extract.extract_loose_source", "vntext.patch_renpy.apply_renpy_translation_package", "renpy_native_dialogue_id", ("native_id", "unit_type"), "native_id + unit_type + exact source/template precondition", "external_translation_overlay"),
    "renpy_string": MethodContract("renpy_string", "vntext.renpy_extract.extract_loose_source", "vntext.patch_renpy.apply_renpy_translation_package", "renpy_string_source", ("source", "unit_type"), "exact source + unit_type + source/template precondition", "external_translation_overlay"),
    "plain_text_line": MethodContract(
        method="plain_text_line",
        reader="vntext.extract_text.plain_text_line",
        writer="vntext.patch_plain.plain_text_line",
        locator_kind="source_file_line",
        required_locator_fields=("line",),
        precondition="file_path + source_text + line",
        growth_policy="text_file_rewrite",
    ),
    "structured_json_value": MethodContract(
        method="structured_json_value",
        reader="vntext.structured_json.extract_structured_json",
        writer="vntext.structured_json.patch_structured_json",
        locator_kind="json_pointer",
        required_locator_fields=("json_pointer",),
        precondition="file_path + json_pointer + source_text",
        growth_policy="structured_json_rewrite",
    ),
    "structured_csv_cell": MethodContract(
        method="structured_csv_cell",
        reader="vntext.structured_csv.extract_structured_csv",
        writer="vntext.structured_csv.patch_structured_csv",
        locator_kind="csv_row_column",
        required_locator_fields=("row_index", "column_index"),
        precondition="file_path + row_index + column_index + source_text",
        growth_policy="structured_csv_rewrite",
    ),
    "structured_xml_value": MethodContract(
        method="structured_xml_value",
        reader="vntext.structured_xml.extract_structured_xml",
        writer="vntext.structured_xml.patch_structured_xml",
        locator_kind="xml_element_path",
        required_locator_fields=("xml_path", "node_kind"),
        precondition="file_path + xml_path + node_kind + source_text",
        growth_policy="structured_xml_rewrite",
    ),
    "structured_sqlite_value": MethodContract(
        method="structured_sqlite_value",
        reader="vntext.extract_sqlite.extract_sqlite_text_candidates",
        writer="vntext.extract_sqlite.patch_structured_sqlite",
        locator_kind="sqlite_table_rowid_column",
        required_locator_fields=("table", "column", "rowid", "schema_fingerprint", "file_sha256"),
        precondition="file_sha256 + schema_fingerprint + rowid + column + exact source_text",
        growth_policy="sqlite_transactional_copy_reopen",
    ),
    "unity_textasset_line": MethodContract(
        method="unity_textasset_line",
        reader="vntext.extract_unity.TextAsset.line",
        writer="vntext.patch_pipeline.TextAsset.line",
        locator_kind="unity_path_id_line",
        required_locator_fields=("path_id", "line_index"),
        precondition="path_id + source_text",
        growth_policy="TextAsset_object_policy",
    ),
    "unity_textasset_table_cell": MethodContract(
        method="unity_textasset_table_cell",
        reader="vntext.extract_text.TextAsset.table_cell",
        writer="vntext.patch_pipeline.TextAsset.table_cell",
        locator_kind="unity_path_id_table_cell",
        required_locator_fields=("path_id", "line_index", "column_index"),
        precondition="path_id + source_text + row/column",
        growth_policy="TextAsset_object_policy",
    ),
    "unity_textasset_script": MethodContract(
        method="unity_textasset_script",
        reader="vntext.extract_unity.TextAsset.script",
        writer="vntext.patch_pipeline.TextAsset.script",
        locator_kind="unity_path_id_field",
        required_locator_fields=("path_id",),
        precondition="path_id + source_text",
        growth_policy="TextAsset_object_policy",
    ),
    "unity_typetree_field": MethodContract(
        method="unity_typetree_field",
        reader="vntext.extract_unity.TypeTree.field",
        writer="vntext.patch_pipeline.TypeTree.field",
        locator_kind="unity_path_id_field_path",
        required_locator_fields=("path_id", "field_path"),
        precondition="path_id + field_path + source_text",
        growth_policy="serialized_object_policy",
    ),
    "unity_ui_text": MethodContract(
        method="unity_ui_text",
        reader="vntext.extract_unity.UI.text_field",
        writer="vntext.patch_pipeline.UI.text_field",
        locator_kind="unity_path_id_field_path",
        required_locator_fields=("path_id", "field_path"),
        precondition="path_id + field_path + source_text",
        growth_policy="serialized_object_policy",
    ),
    "unity_localization_string": MethodContract(
        method="unity_localization_string",
        reader="vntext.unity_localization.StringTable.m_Localized",
        writer="vntext.patch_pipeline.UnityLocalization.StringTable.m_Localized",
        locator_kind="unity_path_id_localization_field_path",
        required_locator_fields=("path_id", "field_path", "table_kind", "entry_index"),
        precondition="StringTable + path_id + m_TableData[*].m_Localized + source_text; m_Id identity guard when present",
        growth_policy="serialized_object_policy",
    ),
    "naninovel_script_string": MethodContract(
        method="naninovel_script_string",
        reader="vntext.extract_naninovel.script_string",
        writer="vntext.patch_naninovel.script_string",
        locator_kind="naninovel_path_id_string",
        required_locator_fields=("path_id",),
        precondition="path_id + source_text",
        growth_policy="serialized_object_policy",
    ),
    "naninovel_choice": MethodContract(
        method="naninovel_choice",
        reader="vntext.extract_naninovel.choice",
        writer="vntext.patch_naninovel.choice",
        locator_kind="naninovel_path_id_command",
        required_locator_fields=("path_id",),
        precondition="path_id + command/source text",
        growth_policy="serialized_object_policy",
    ),
    "naninovel_print": MethodContract(
        method="naninovel_print",
        reader="vntext.extract_naninovel.print",
        writer="vntext.patch_naninovel.print",
        locator_kind="naninovel_path_id_command",
        required_locator_fields=("path_id",),
        precondition="path_id + command/source text",
        growth_policy="serialized_object_policy",
    ),
}

EXTRACT_ONLY_METHODS = frozenset(
    {
        "raw_fixed_slot",
        "naninovel_blob_string",
        "naninovel_raw_candidate",
        "raw_review_only",
        "external_dump_reimport",
        "review_only",
    }
)


@dataclass(frozen=True)
class PatchabilityAssessment:
    status: str
    eligible: bool
    method: str
    reason: str
    reader: str | None
    writer: str | None
    locator_kind: str | None
    required_locator_fields: tuple[str, ...]
    missing_locator_fields: tuple[str, ...]
    precondition: str | None
    growth_policy: str | None
    proof: dict[str, bool]
    proof_complete: bool

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["required_locator_fields"] = list(self.required_locator_fields)
        value["missing_locator_fields"] = list(self.missing_locator_fields)
        return value


def _get(entry: Any, key: str, default: Any = "") -> Any:
    if isinstance(entry, dict):
        return entry.get(key, default)
    return getattr(entry, key, default)


def _locator(entry: Any) -> dict[str, Any]:
    value = _get(entry, "locator", {})
    return value if isinstance(value, dict) else {}


def _present(value: Any) -> bool:
    if value is None or value is False:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    return True


def classify_renpy_provenance(source_file: Any, *, source_available: bool) -> dict[str, Any]:
    """Classify native source ownership without guessing from translated text."""

    relative = str(source_file or "").replace("\\", "/").strip("/")
    common = relative.casefold() == "renpy/common" or relative.casefold().startswith("renpy/common/")
    if common:
        return {
            "owner": RENPY_COMMON,
            "source_available": bool(source_available),
            "auto_patchable": False,
            "disposition": "common_review_only" if source_available else "sdk_only",
            "ledger": "review_only" if source_available else "missing_source",
        }
    if source_available:
        return {
            "owner": RENPY_GAME_OWNED,
            "source_available": True,
            "auto_patchable": True,
            "disposition": "game_owned",
            "ledger": "translation_csv",
        }
    return {
        "owner": "unknown",
        "source_available": False,
        "auto_patchable": False,
        "disposition": "missing_source",
        "ledger": "missing_source",
    }


def renpy_contract_fingerprint(contract: dict[str, Any]) -> str:
    """Hash only Ren'Py identity/locator/precondition data.

    Provenance and context are intentionally excluded: they help explain an
    entry but must never become patch authority.
    """

    material = {
        field: contract.get(field)
        for field in ("version", "engine", "identity", "locator", "precondition")
    }
    payload = json.dumps(
        material,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def make_renpy_contract(
    *,
    method: str,
    backend: str,
    unit_type: str,
    source_text: str,
    file_path: str,
    source_sha256: str,
    template_sha256: str,
    native_id: str = "",
    source_line: int | None = None,
    block_order: int | None = None,
    speaker: str = "",
    source_context: str = "",
    language: str = "vietnamese",
) -> dict[str, Any]:
    """Build the additive Ren'Py contract from already-extracted metadata."""

    identity: dict[str, Any] = {
        "backend": backend,
        "import_method": method,
        "unit_type": unit_type,
        "language": language,
    }
    locator: dict[str, Any] = {"unit_type": unit_type}
    precondition: dict[str, Any] = {
        "native_source": source_text,
        "source_file": file_path,
        "source_sha256": source_sha256,
        "template_file": "<generated-renpy-template>",
        "template_sha256": template_sha256,
        "unit_type": unit_type,
        "language": language,
    }
    if unit_type == RENPY_DIALOGUE_UNIT:
        identity["native_id"] = native_id
        locator["native_id"] = native_id
        precondition["native_id"] = native_id
    elif unit_type == RENPY_STRING_UNIT:
        identity["source"] = source_text
        locator["source"] = source_text
    else:
        raise ValueError(f"unsupported Ren'Py unit_type: {unit_type}")
    contract = {
        "version": RENPY_NATIVE_CONTRACT_VERSION,
        "engine": RENPY_ENGINE,
        "identity": identity,
        "locator": locator,
        "precondition": precondition,
        "provenance": {
            "source_file": file_path,
            "source_line": source_line,
            "language": language,
            "original_source_text": source_text,
            "generated_artifact": {
                "file": "<generated-renpy-template>",
                "sha256": template_sha256,
            },
            "block_order": block_order,
        },
        "context": {"speaker": speaker, "source_context": source_context},
    }
    if unit_type == RENPY_STRING_UNIT:
        contract["provenance"].update(
            classify_renpy_provenance(file_path, source_available=bool(source_sha256))
        )
    contract["fingerprint"] = renpy_contract_fingerprint(contract)
    return contract


def validate_renpy_contract(entry: Any) -> str:
    """Return a fail-closed reason for one canonical Ren'Py entry.

    Identity, locator and precondition data authorize the target; string units
    additionally require explicit game-owned source provenance.
    """

    method = str(_get(entry, "import_method", "") or "")
    if method not in {"renpy_dialogue", "renpy_string"}:
        return "not a Ren'Py native entry"
    contract = _get(entry, "native_contract", {})
    if not isinstance(contract, dict):
        return "missing Ren'Py native contract"
    if contract.get("version") != RENPY_NATIVE_CONTRACT_VERSION:
        return "unsupported or missing Ren'Py native contract version"
    if contract.get("engine") != RENPY_ENGINE:
        return "Ren'Py native contract engine mismatch"

    locator = _locator(entry)
    identity = contract.get("identity")
    contract_locator = contract.get("locator")
    precondition = contract.get("precondition")
    provenance = contract.get("provenance")
    context = contract.get("context")
    if not all(isinstance(value, dict) for value in (identity, contract_locator, precondition)):
        return "Ren'Py native contract identity/locator/precondition is malformed"
    if not isinstance(provenance, dict) or not isinstance(context, dict):
        return "Ren'Py native contract provenance/context is malformed"

    source_text = str(_get(entry, "source_text", "") or "")
    file_path = str(_get(entry, "file_path", "") or "")
    backend = str(_get(entry, "backend", "") or "")
    unit_type = str(locator.get("unit_type") or "")
    if unit_type not in RENPY_UNIT_TYPES:
        return "Ren'Py native locator has an invalid unit_type"
    if identity.get("unit_type") != unit_type or contract_locator.get("unit_type") != unit_type:
        return "Ren'Py native unit_type drift"
    if identity.get("backend") != backend:
        return "Ren'Py native backend drift"
    if identity.get("import_method") != method:
        return "Ren'Py native import_method drift"
    if contract_locator != {
        key: locator.get(key)
        for key in ("native_id", "source", "unit_type")
        if key in locator
    }:
        return "Ren'Py native locator drift"

    contract_language = identity.get("language")
    if contract_language is not None and precondition.get("language") != contract_language:
        return "Ren'Py native language precondition drift"
    if precondition.get("unit_type") != unit_type:
        return "Ren'Py native source unit_type precondition drift"
    if precondition.get("native_source") != source_text:
        return "Ren'Py native source precondition drift"
    if precondition.get("source_file") != file_path:
        return "Ren'Py native source file precondition drift"
    source_sha256 = str(precondition.get("source_sha256") or "")
    template_file = str(precondition.get("template_file") or "")
    template_sha256 = str(precondition.get("template_sha256") or "")
    if not _SHA256.fullmatch(source_sha256):
        return "Ren'Py native source precondition hash is malformed"
    if not template_file or not _SHA256.fullmatch(template_sha256):
        return "Ren'Py native template precondition is malformed"

    if method == "renpy_dialogue":
        native_id = str(locator.get("native_id") or "")
        if not native_id:
            return "missing native Ren'Py dialogue identifier"
        if not _RENPY_NATIVE_ID.fullmatch(native_id):
            return "malformed native Ren'Py dialogue identifier"
        if set(locator) - {"native_id", "unit_type"}:
            return "Ren'Py dialogue locator has unsupported fields"
        if identity.get("native_id") != native_id or contract_locator.get("native_id") != native_id:
            return "Ren'Py native dialogue identifier drift"
        if "source" in identity or "source" in contract_locator:
            return "Ren'Py dialogue locator mixes string identity"
        if precondition.get("native_id") != native_id:
            return "Ren'Py native dialogue identifier precondition drift"
    else:
        source = locator.get("source")
        if not isinstance(source, str) or source != source_text:
            return "Ren'Py string locator must equal exact source text"
        if set(locator) - {"source", "unit_type"}:
            return "Ren'Py string locator has unsupported fields"
        if identity.get("source") != source_text or contract_locator.get("source") != source_text:
            return "Ren'Py string identity drift"
        if "native_id" in identity or "native_id" in contract_locator or "native_id" in precondition:
            return "Ren'Py string identity must not use a dialogue native ID"
        if not isinstance(contract_language, str) or not contract_language.strip():
            return "Ren'Py string identity is missing language"
        expected_provenance = classify_renpy_provenance(
            file_path,
            source_available=bool(source_sha256),
        )
        if expected_provenance["owner"] != RENPY_GAME_OWNED:
            return "Ren'Py string provenance is not game-owned"
        if provenance.get("source_file") != file_path:
            return "Ren'Py string provenance source drift"
        if provenance.get("owner") != RENPY_GAME_OWNED:
            return "Ren'Py string provenance is not game-owned"
        if provenance.get("source_available") is not True or provenance.get("auto_patchable") is not True:
            return "Ren'Py string source provenance is not patchable"

    if contract.get("fingerprint") != renpy_contract_fingerprint(contract):
        return "Ren'Py native contract fingerprint mismatch"
    return ""


def is_technical_skip_entry(entry: Any) -> bool:
    """Identify technical rows before symmetry routing marks them REVIEW."""
    if bool(_get(entry, "review_only", False)):
        return False
    from vntext.mt_classify import classify_row_authoritative

    row_factory = _get(entry, "to_csv_row", None)
    row = row_factory() if callable(row_factory) else dict(entry or {})
    if not isinstance(row, dict):
        row = {}
    row.update(
        {
            "review_only": False,
            "locator": _locator(entry),
            "patch_proof": _get(entry, "patch_proof", {}),
        }
    )
    action, _reason, _decision = classify_row_authoritative(row)
    return action == "skip_technical"


def _proof(entry: Any) -> dict[str, bool]:
    value = _get(entry, "patch_proof", None)
    if not isinstance(value, dict):
        value = _get(entry, "symmetry_proof", {})
    value = value if isinstance(value, dict) else {}
    return {field: bool(value.get(field, False)) for field in _PROOF_FIELDS}


def assess_entry(entry: Any, *, require_proof: bool = True) -> PatchabilityAssessment:
    """Assess one entry without changing it.

    ``require_proof=True`` is the default fail-closed policy: a row cannot
    enter the main flow until its reader, writer, preflight, reopen and
    semantic verification evidence are all present. Callers may pass
    ``require_proof=False`` only for a compatibility inventory of method and
    locator coverage; that report must not be promoted to a Patch decision.
    """

    method = str(_get(entry, "import_method", "") or "")
    proof = _proof(entry)
    proof_complete = all(proof.values())
    locator = _locator(entry)
    contract = PATCHABLE_METHOD_CONTRACTS.get(method)
    if bool(_get(entry, "review_only", False)):
        return PatchabilityAssessment(
            REVIEW_REQUIRED,
            False,
            method,
            "entry is explicitly review_only",
            contract.reader if contract else None,
            contract.writer if contract else None,
            contract.locator_kind if contract else None,
            contract.required_locator_fields if contract else (),
            (),
            contract.precondition if contract else None,
            contract.growth_policy if contract else None,
            proof,
            proof_complete,
        )
    if method in EXTRACT_ONLY_METHODS:
        return PatchabilityAssessment(
            EXTRACT_ONLY,
            False,
            method,
            "method has no safe direct writer in the main translation flow",
            None,
            None,
            None,
            (),
            (),
            None,
            "fixed_slot_or_external_reimport",
            proof,
            proof_complete,
        )
    if contract is None:
        return PatchabilityAssessment(
            UNSUPPORTED,
            False,
            method,
            "no reader/writer contract is registered for import_method",
            None,
            None,
            None,
            (),
            (),
            None,
            None,
            proof,
            proof_complete,
        )

    native_contract = _get(entry, "native_contract", {})
    has_native_contract = bool(native_contract) or (
        method in {"renpy_dialogue", "renpy_string"} and "unit_type" in locator
    )
    locator_fields = contract.required_locator_fields
    if method == "renpy_string" and not has_native_contract:
        return PatchabilityAssessment(
            REVIEW_REQUIRED,
            False,
            method,
            "Ren'Py string requires exact game-owned native provenance",
            contract.reader,
            contract.writer,
            contract.locator_kind,
            contract.required_locator_fields,
            ("native_contract",),
            contract.precondition,
            contract.growth_policy,
            proof,
            proof_complete,
        )
    if method == "renpy_dialogue" and not has_native_contract:
        locator_fields = ("native_id", "line")
    missing = tuple(
        field
        for field in locator_fields
        if not _present(locator.get(field))
    )
    if not _present(_get(entry, "source_text", "")):
        missing = (*missing, "source_text")
    if not _present(_get(entry, "file_path", "")):
        missing = (*missing, "file_path")
    if missing:
        return PatchabilityAssessment(
            REVIEW_REQUIRED,
            False,
            method,
            "main-flow method is missing stable locator/precondition fields: " + ", ".join(missing),
            contract.reader,
            contract.writer,
            contract.locator_kind,
            contract.required_locator_fields,
            missing,
            contract.precondition,
            contract.growth_policy,
            proof,
            proof_complete,
        )
    if method in {"renpy_dialogue", "renpy_string"} and has_native_contract:
        contract_reason = validate_renpy_contract(entry)
        if contract_reason:
            return PatchabilityAssessment(
                REVIEW_REQUIRED,
                False,
                method,
                contract_reason,
                contract.reader,
                contract.writer,
                contract.locator_kind,
                contract.required_locator_fields,
                ("native_contract",),
                contract.precondition,
                contract.growth_policy,
                proof,
                proof_complete,
            )
    if require_proof and not proof_complete:
        missing_proof = [field for field, present in proof.items() if not present]
        return PatchabilityAssessment(
            REVIEW_REQUIRED,
            False,
            method,
            "reader/locator/writer contract exists but roundtrip proof is incomplete: " + ", ".join(missing_proof),
            contract.reader,
            contract.writer,
            contract.locator_kind,
            contract.required_locator_fields,
            (),
            contract.precondition,
            contract.growth_policy,
            proof,
            proof_complete,
        )
    return PatchabilityAssessment(
        SUPPORTED_AND_PATCHABLE,
        True,
        method,
        "reader, stable locator, writer and precondition contract are complete",
        contract.reader,
        contract.writer,
        contract.locator_kind,
        contract.required_locator_fields,
        (),
        contract.precondition,
        contract.growth_policy,
        proof,
        proof_complete,
    )


def audit_entries(entries: Iterable[Any], *, require_proof: bool = True, sample_limit: int = 20) -> dict[str, Any]:
    """Return measurable symmetry coverage for a sequence of entries."""

    materialised = list(entries)
    assessments: list[PatchabilityAssessment] = [
        assess_entry(entry, require_proof=require_proof) for entry in materialised
    ]
    counts: dict[str, int] = {}
    method_counts: dict[str, int] = {}
    samples: list[dict[str, Any]] = []
    for entry, assessment in zip(materialised, assessments):
        counts[assessment.status] = counts.get(assessment.status, 0) + 1
        method_counts[assessment.method] = method_counts.get(assessment.method, 0) + 1
        if not assessment.eligible and len(samples) < sample_limit:
            samples.append(
                {
                    "key": str(_get(entry, "key", "") or ""),
                    "file_path": str(_get(entry, "file_path", "") or ""),
                    "method": assessment.method,
                    "status": assessment.status,
                    "reason": assessment.reason,
                }
            )

    return {
        "require_proof": require_proof,
        "entry_count": len(assessments),
        "status_counts": dict(sorted(counts.items())),
        "method_counts": dict(sorted(method_counts.items())),
        "eligible": sum(assessment.eligible for assessment in assessments),
        # The invariant is universal over MAIN rows: an empty MAIN is safe and
        # must still allow a review-only package for games with no proven writer.
        "main_flow_safe": all(assessment.eligible for assessment in assessments),
        "samples": samples,
        "assessments": [assessment.to_dict() for assessment in assessments],
    }


def enforce_main_flow(entries: Iterable[Any], *, require_proof: bool = True) -> dict[str, Any]:
    """Fail closed for a new extractor before main CSV promotion."""

    materialised = list(entries)
    report = audit_entries(materialised, require_proof=require_proof)
    if not report["main_flow_safe"]:
        failed = [item for item in report["assessments"] if not item["eligible"]]
        preview = "; ".join(f"{item['method']}: {item['reason']}" for item in failed[:5])
        raise ValueError(f"extract/patch symmetry gate failed for {len(failed)} entries: {preview}")
    return report


def route_main_flow(entries: Iterable[Any], *, require_proof: bool = True) -> tuple[list[Any], list[Any], dict[str, Any]]:
    """Promote only symmetry-proven entries and route the rest to review.

    Extraction is intentionally allowed to discover text that the current
    writer cannot safely re-import.  The important boundary is the package's
    main translation flow: every item returned in ``main`` must pass the same
    fail-closed assessment used by the patcher.  Entries that do not pass are
    retained, marked ``review_only`` and returned in ``review`` so discovery
    remains observable instead of silently dropping text.
    """

    materialised = list(entries)
    report = audit_entries(materialised, require_proof=require_proof)
    main: list[Any] = []
    review: list[Any] = []
    assessments = report.pop("assessments")
    technical: list[Any] = []
    for entry, assessment in zip(materialised, assessments):
        if is_technical_skip_entry(entry):
            technical.append(entry)
            main.append(entry)
            continue
        if assessment["eligible"] and not bool(_get(entry, "review_only", False)):
            main.append(entry)
            continue
        if isinstance(entry, dict):
            entry["review_only"] = True
        else:
            setattr(entry, "review_only", True)
        review.append(entry)

    source_main_flow_safe = bool(report["main_flow_safe"])
    report["source_main_flow_safe"] = source_main_flow_safe
    report["technical_preclassified_entries"] = len(technical)
    report["promoted_main_entries"] = len(main) - len(technical)
    report["demoted_to_review_entries"] = len(review)
    technical_ids = {id(entry) for entry in technical}
    report["main_flow_safe"] = bool(main) and all(
        assess_entry(entry, require_proof=require_proof).eligible
        for entry in main
        if id(entry) not in technical_ids
    )
    report["route_complete"] = len(main) + len(review) == len(materialised)
    # Keep per-entry diagnostics available from audit_entries(), but do not
    # embed a duplicated assessment object for every row in manifest.stats.
    report["assessment_count"] = len(assessments)
    return main, review, report


__all__ = [
    "EXTRACT_ONLY",
    "EXTRACT_ONLY_METHODS",
    "MethodContract",
    "PATCHABLE_METHOD_CONTRACTS",
    "PatchabilityAssessment",
    "PLAIN_TEXT_PATCH_PROOF",
    "NANINOVEL_PATCH_PROOF",
    "UNITY_TEXTASSET_PATCH_PROOF",
    "UNITY_TYPETREE_PATCH_PROOF",
    "UNITY_UI_PATCH_PROOF",
    "REVIEW_REQUIRED",
    "SUPPORTED_AND_PATCHABLE",
    "UNSUPPORTED",
    "RENPY_DIALOGUE_UNIT",
    "RENPY_ENGINE",
    "RENPY_GAME_OWNED",
    "RENPY_COMMON",
    "RENPY_NATIVE_CONTRACT_VERSION",
    "RENPY_STRING_UNIT",
    "RENPY_UNIT_TYPES",
    "is_technical_skip_entry",
    "renpy_contract_fingerprint",
    "make_renpy_contract",
    "classify_renpy_provenance",
    "validate_renpy_contract",
    "assess_entry",
    "audit_entries",
    "enforce_main_flow",
    "route_main_flow",
]
