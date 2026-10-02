from __future__ import annotations

import hashlib
from copy import deepcopy
from dataclasses import dataclass, field


def make_key(file_path: str, context: str, text: str, method: str) -> str:
    raw = "\n".join([file_path, context, method, text]).encode("utf-8", "surrogatepass")
    return hashlib.sha1(raw).hexdigest()[:16]


@dataclass
class Entry:
    source_text: str
    file_path: str
    context: str
    object_info: str = ""
    import_method: str = "review_only"
    safety: str = "unsafe"
    locator: dict = field(default_factory=dict)
    backend: str = ""
    review_only: bool = False
    key: str = ""
    duplicate_locations: list = field(default_factory=list)
    patch_proof: dict = field(default_factory=dict)
    native_contract: dict = field(default_factory=dict)

    def finalize(self) -> "Entry":
        if not self.key:
            self.key = make_key(self.file_path, self.context, self.source_text, self.import_method)
        return self

    def to_csv_row(self) -> dict:
        byte_limit = ""
        patch_note = ""
        length = self.locator.get("length") if isinstance(self.locator, dict) else None
        if self.import_method in {"raw_fixed_slot", "naninovel_blob_string", "naninovel_raw_candidate"} and length:
            byte_limit = str(length)
            patch_note = "RAW DEBUG: không nằm luồng chính; cần importer object/UABEA, không bắt dịch ngắn"
        elif self.import_method in {
            "unity_textasset_line",
            "unity_textasset_table_cell",
            "unity_textasset_script",
            "unity_typetree_field",
            "unity_ui_text",
            "unity_localization_string",
            "naninovel_script_string",
            "naninovel_choice",
            "naninovel_print",
            "plain_text_line",
            "structured_json_value",
            "structured_csv_cell",
            "structured_xml_value",
            "structured_sqlite_value",
            "renpy_dialogue",
            "renpy_string",
        }:
            if self.import_method == "unity_textasset_table_cell":
                patch_note = "Patch bảng language tự động kiểu UABEA; không giới hạn độ dài"
            else:
                patch_note = "Patch tự động"
        else:
            patch_note = "Có thể chỉ extract, xem import_report"
        return {
            "key": self.key,
            "source_text": self.source_text,
            "translation": "",
            "context": self.context,
            "file_path": self.file_path,
            "object_info": self.object_info,
            "import_method": self.import_method,
            "safety": self.safety,
            "backend": self.backend,
            "byte_limit": byte_limit,
            "patch_note": patch_note,
        }

    def to_manifest(self) -> dict:
        manifest = {
            "key": self.key,
            "source_text": self.source_text,
            "file_path": self.file_path,
            "context": self.context,
            "object_info": self.object_info,
            "import_method": self.import_method,
            "safety": self.safety,
            "locator": self.locator,
            "backend": self.backend,
            "review_only": self.review_only,
            "duplicate_locations": self.duplicate_locations,
        }
        # Additive metadata: legacy entries keep the exact manifest shape;
        # strict generic extractors may attach proof consumed by the symmetry
        # gate before promotion to the main translation flow.
        if self.patch_proof:
            manifest["patch_proof"] = dict(self.patch_proof)
        if self.native_contract:
            manifest["native_contract"] = deepcopy(self.native_contract)
        return manifest
