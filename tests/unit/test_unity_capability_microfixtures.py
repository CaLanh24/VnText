"""Capability roundtrips on tiny Unity-shaped fixtures.

These fixtures deliberately exercise the reader/writer seams without copying or
patching a real game. The outer UnityFS marker and fake loader are only a small
container harness; serialized TextAsset, aligned-string and TypeTree payloads
pass through the production extract/patch code.
"""

from __future__ import annotations

import copy
import hashlib
import json
import struct
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


from vntext.entry import Entry
from vntext.extract_naninovel import collect_naninovel_choice_displays_from_path, iter_naninovel_script_entries
from vntext.extract_unity import extract_unity_typetree
from vntext.package_io import read_csv_rows_file, write_csv_rows_file, write_package
from vntext.patch import apply_translation_package
from vntext.patch_unity import (
    _pop_patched_ui_sources,
    patch_font_replacements_in_env,
    patch_object_length_prefixed_strings,
)
from vntext.patchability import (
    NANINOVEL_PATCH_PROOF,
    UNITY_TEXTASSET_PATCH_PROOF,
    UNITY_TYPETREE_PATCH_PROOF,
    UNITY_UI_PATCH_PROOF,
    UNITY_LOCALIZATION_PATCH_PROOF,
)


HEADER = b"UnityFS\x00"
TAIL = b"\x91\x92\x93\x94"
PROOFS = {
    "unity_textasset_line": UNITY_TEXTASSET_PATCH_PROOF,
    "unity_typetree_field": UNITY_TYPETREE_PATCH_PROOF,
    "unity_ui_text": UNITY_UI_PATCH_PROOF,
    "unity_localization_string": UNITY_LOCALIZATION_PATCH_PROOF,
    "naninovel_script_string": NANINOVEL_PATCH_PROOF,
    "naninovel_choice": NANINOVEL_PATCH_PROOF,
    "naninovel_print": NANINOVEL_PATCH_PROOF,
}


def _aligned_bytes(value: bytes) -> bytes:
    padding = (4 - (len(value) % 4)) % 4
    return struct.pack("<i", len(value)) + value + (b"\x00" * padding)


def _aligned_text(value: str) -> bytes:
    return _aligned_bytes(value.encode("utf-8"))


def _read_aligned_text(raw: bytes) -> str:
    if len(raw) < 4:
        return ""
    length = struct.unpack_from("<i", raw, 0)[0]
    if length < 0 or 4 + length > len(raw):
        return ""
    return raw[4 : 4 + length].decode("utf-8")


def _textasset_payload(name: str, script: str, tail: bytes = TAIL) -> bytes:
    return _aligned_text(name) + _aligned_bytes(script.encode("utf-8")) + bytes(tail)


def _read_textasset_payload(raw: bytes) -> tuple[str, str, bytes]:
    if len(raw) < 8:
        raise ValueError("short TextAsset payload")
    name_len = struct.unpack_from("<i", raw, 0)[0]
    name_end = 4 + name_len
    name_pad_end = name_end + ((4 - (name_len % 4)) % 4)
    script_len = struct.unpack_from("<i", raw, name_pad_end)[0]
    script_start = name_pad_end + 4
    script_end = script_start + script_len
    script_pad_end = script_end + ((4 - (script_len % 4)) % 4)
    return (
        raw[4:name_end].decode("utf-8"),
        raw[script_start:script_end].decode("utf-8"),
        raw[script_pad_end:],
    )


class _FakeAssetFile:
    def __init__(self, enable_type_tree: bool):
        self._enable_type_tree = enable_type_tree


class _FakeType:
    def __init__(self, name: str):
        self.name = name


class _FakeScriptPointer:
    def __init__(self, path_id: int, class_name: str):
        self.path_id = path_id
        self._class_name = class_name

    def deref_parse_as_object(self):
        return SimpleNamespace(m_ClassName=self._class_name)


class _FakeObject:
    def __init__(self, definition: dict):
        self.path_id = int(definition["path_id"])
        self.type = _FakeType(str(definition["type"]))
        self.assets_file = _FakeAssetFile(bool(definition.get("type_tree_enabled")))
        self._class_name = str(definition.get("class_name") or "")
        self._script_path_id = int(definition.get("script_path_id") or 0)
        self._tree = copy.deepcopy(definition.get("tree") or {})
        self._tail = bytes.fromhex(str(definition.get("tail_hex") or ""))

        if self.type.name == "TextAsset":
            self._data = SimpleNamespace(
                m_Name=str(definition.get("name") or ""),
                name=str(definition.get("name") or ""),
                m_Script=str(definition.get("script") or ""),
                script=str(definition.get("script") or ""),
            )
            raw = _textasset_payload(self._data.m_Name, self._data.m_Script, self._tail)
        elif self.type.name == "MonoScript":
            self._data = SimpleNamespace(m_ClassName=self._class_name)
            raw = b""
        elif self.type.name == "MonoBehaviour" and self._class_name in {
            "Text",
            "TextMeshPro",
            "TextMeshProUGUI",
            "TMP_Text",
        }:
            raw = bytes.fromhex(str(definition.get("raw_hex") or ""))
            self._data = SimpleNamespace(
                m_Text=str(definition.get("text") or _read_aligned_text(raw)),
                m_text=str(definition.get("text") or _read_aligned_text(raw)),
                text=str(definition.get("text") or _read_aligned_text(raw)),
            )
        else:
            raw = bytes.fromhex(str(definition.get("raw_hex") or ""))
            if not raw:
                raw = json.dumps(self._tree, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
            self._data = SimpleNamespace()
        if self.type.name == "TextAsset":
            self._data.save = self._save_textasset
        self.data = bytearray(raw)
        self.byte_size = len(self.data)

    def _save_textasset(self):
        self.data = bytearray(
            _textasset_payload(
                self._data.m_Name,
                self._data.m_Script,
                self._tail,
            )
        )

    def read(self):
        if self.type.name == "TextAsset":
            name, script, _tail = _read_textasset_payload(bytes(self.data))
            self._data.m_Name = name
            self._data.name = name
            self._data.m_Script = script
            self._data.script = script
        elif self.type.name == "MonoBehaviour" and self._class_name in {
            "Text",
            "TextMeshPro",
            "TextMeshProUGUI",
            "TMP_Text",
        }:
            value = _read_aligned_text(bytes(self.data))
            self._data.m_Text = value
            self._data.m_text = value
            self._data.text = value
        return self._data

    def set_raw_data(self, raw: bytes):
        self.data = bytearray(raw)
        self.read()

    def get_raw_data(self):
        return bytes(self.data)

    def parse_monobehaviour_head(self):
        return SimpleNamespace(
            m_Script=_FakeScriptPointer(self._script_path_id, self._class_name)
        )

    def read_typetree(self):
        return self._tree

    def save_typetree(self, tree):
        self._tree = copy.deepcopy(tree)
        raw = json.dumps(self._tree, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        if len(raw) <= self.byte_size:
            raw += b"\x00" * (self.byte_size - len(raw))
        self.data = bytearray(raw)

    def export_definition(self) -> dict:
        result = {
            "path_id": self.path_id,
            "type": self.type.name,
            "class_name": self._class_name,
            "script_path_id": self._script_path_id,
            "type_tree_enabled": self.assets_file._enable_type_tree,
        }
        if self.type.name == "TextAsset":
            name, script, tail = _read_textasset_payload(bytes(self.data))
            result.update(name=name, script=script, tail_hex=tail.hex())
        elif self.type.name == "MonoBehaviour" and self._class_name in {
            "Text",
            "TextMeshPro",
            "TextMeshProUGUI",
            "TMP_Text",
        }:
            result.update(raw_hex=bytes(self.data).hex(), text=_read_aligned_text(bytes(self.data)))
        else:
            result.update(tree=self._tree, raw_hex=bytes(self.data).hex())
        return result


class _FakeEnvironment:
    def __init__(self, definitions: list[dict]):
        self.objects = [_FakeObject(item) for item in definitions]
        self.file = SimpleNamespace(signature="UnityFS")


class _FakeUnityPy:
    @staticmethod
    def load(path: str):
        raw = Path(path).read_bytes()
        if not raw.startswith(HEADER):
            raise ValueError("not a UnityFS micro-fixture")
        payload = raw[len(HEADER) :].rstrip(b"\x00")
        document = json.loads(payload.decode("utf-8"))
        return _FakeEnvironment(document["objects"])


def _save_fake_environment(env, target_path, _progress_callback=None):
    target = Path(target_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(
        {"objects": [obj.export_definition() for obj in env.objects]},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    target.write_bytes(HEADER + payload)


def _write_game(root: Path, definitions: list[dict], relative: str = "Demo_Data/microfixture") -> Path:
    asset = root / relative
    asset.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(
        {"objects": definitions},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    asset.write_bytes(HEADER + payload)
    return asset


def _write_package_translation(package: Path, entry_rows: list[Entry], translations: dict[str, str]) -> None:
    write_package(
        str(package),
        entry_rows,
        [],
        {"fixture": "unity-capability-microfixture"},
        True,
        enforce_symmetry=True,
    )
    csv_path = package / "translation.csv"
    fields, rows = read_csv_rows_file(csv_path)
    for row in rows:
        if row["source_text"] in translations:
            row["translation"] = translations[row["source_text"]]
    write_csv_rows_file(csv_path, fields, rows)


class UnityCapabilityMicrofixtureTests(unittest.TestCase):
    def test_explicit_font_replacement_copies_payload_and_fails_closed(self):
        class FontObject:
            def __init__(self, name, payload):
                self.type = SimpleNamespace(name="Font")
                self._data = SimpleNamespace(m_Name=name, m_FontData=list(payload))
                self.saved = False

                def save():
                    self.saved = True

                self._data.save = save

            def read(self):
                return self._data

        source = FontObject("BerkshireSwash-Regular", b"old-font")
        target = FontObject("Candara", b"font-with-vietnamese-glyphs")
        result = patch_font_replacements_in_env(
            SimpleNamespace(objects=[source, target]),
            (("BerkshireSwash-Regular", "Candara"),),
        )
        self.assertEqual(result["changed"], 1)
        self.assertEqual(result["errors"], [])
        self.assertTrue(source.saved)
        self.assertEqual(bytes(source.read().m_FontData), b"font-with-vietnamese-glyphs")

        missing = patch_font_replacements_in_env(
            SimpleNamespace(objects=[FontObject("BerkshireSwash-Regular", b"old")]),
            (("BerkshireSwash-Regular", "Candara"),),
        )
        self.assertEqual(missing["changed"], 0)
        self.assertTrue(any("target_not_present" in error for error in missing["errors"]))

    def test_large_file_choice_hint_uses_mapped_read_not_read_bytes(self):
        with tempfile.TemporaryDirectory(prefix="vntext-choice-map-micro-") as name:
            path = Path(name) / "large-data.unity3d"
            path.write_bytes(b'prefix @choice "Mapped choice" suffix')
            with patch.object(Path, "read_bytes", side_effect=AssertionError("whole-file read forbidden")):
                self.assertEqual(
                    collect_naninovel_choice_displays_from_path(path),
                    {"Mapped choice"},
                )

    def test_textasset_line_roundtrip_preserves_tail_and_original(self):
        with tempfile.TemporaryDirectory(prefix="vntext-textasset-micro-") as name:
            root = Path(name) / "game"
            package = Path(name) / "package"
            patch_out = Path(name) / "patch"
            source = _write_game(
                root,
                [
                    {
                        "path_id": 7,
                        "type": "TextAsset",
                        "name": "Dialogue",
                        "script": "Hello from TextAsset.\nKeep this line.\n",
                        "type_tree_enabled": False,
                        "tail_hex": TAIL.hex(),
                    }
                ],
            )
            original_hash = hashlib.sha256(source.read_bytes()).hexdigest()
            fake_unitypy = SimpleNamespace(load=_FakeUnityPy.load)
            with patch.dict(sys.modules, {"UnityPy": fake_unitypy}):
                entries = list(extract_unity_typetree(source, root))
                entry = next(item for item in entries if item.source_text == "Hello from TextAsset.")
                self.assertEqual(entry.import_method, "unity_textasset_line")
                self.assertEqual(entry.locator["path_id"], "7")
                self.assertEqual(entry.patch_proof, PROOFS[entry.import_method])

                _write_package_translation(
                    package,
                    [entry],
                    {"Hello from TextAsset.": "Xin chao TextAsset."},
                )
                with patch("vntext.patch_output.save_unity_env", side_effect=_save_fake_environment):
                    report = apply_translation_package(
                        str(package / "translation.csv"),
                        str(package / "manifest.json"),
                        str(root),
                        str(patch_out),
                    )
                self.assertTrue(any("UNITY Demo_Data\\microfixture: 1/1" in line for line in report), report)
                target = patch_out / "COPY_TO_GAME_ROOT" / "Demo_Data" / "microfixture"
                reopened = _FakeUnityPy.load(str(target))
                data = reopened.objects[0].read()
                self.assertIn("Xin chao TextAsset.", data.m_Script)
                self.assertTrue(bytes(reopened.objects[0].data).endswith(TAIL))
            self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(), original_hash)

    def test_generic_naninovel_script_roundtrip_has_no_profile_dependency(self):
        with tempfile.TemporaryDirectory(prefix="vntext-generic-naninovel-micro-") as name:
            root = Path(name) / "game"
            package = Path(name) / "package"
            patch_out = Path(name) / "patch"
            source = _write_game(
                root,
                [
                    {
                        "path_id": 700,
                        "type": "MonoScript",
                        "class_name": "Script",
                    },
                    {
                        "path_id": 701,
                        "type": "MonoBehaviour",
                        "class_name": "Script",
                        "script_path_id": 700,
                        "type_tree_enabled": False,
                        "raw_hex": (
                            _aligned_text('@print "Hello from generic VN."')
                            + _aligned_text('@choice "Open the gate"')
                        ).hex(),
                    },
                ],
                relative="GenericVN_Data/resources.assets",
            )
            original_hash = hashlib.sha256(source.read_bytes()).hexdigest()
            fake_unitypy = SimpleNamespace(load=_FakeUnityPy.load)
            with patch.dict(sys.modules, {"UnityPy": fake_unitypy}):
                entries = list(extract_unity_typetree(source, root))
                selected = [
                    item
                    for item in entries
                    if item.import_method in {"naninovel_print", "naninovel_choice", "naninovel_script_string"}
                ]
                self.assertEqual(
                    {item.source_text for item in selected},
                    {"Hello from generic VN.", "Open the gate"},
                )
                self.assertTrue(selected)
                self.assertTrue(all(item.backend == "naninovel_script_object" for item in selected))
                self.assertTrue(all(item.locator["path_id"] == "701" for item in selected))
                self.assertTrue(all(item.patch_proof == PROOFS[item.import_method] for item in selected))

                _write_package_translation(
                    package,
                    selected,
                    {
                        "Hello from generic VN.": "Xin chao VN generic.",
                        "Open the gate": "Mo cong vao",
                    },
                )
                with patch("vntext.patch_output.save_unity_env", side_effect=_save_fake_environment):
                    report = apply_translation_package(
                        str(package / "translation.csv"),
                        str(package / "manifest.json"),
                        str(root),
                        str(patch_out),
                    )
                self.assertTrue(any("NANINOVEL GenericVN_Data\\resources.assets" in line for line in report), report)
                self.assertTrue(any("patched 2 string slots" in line for line in report), report)
                target = patch_out / "COPY_TO_GAME_ROOT" / "GenericVN_Data" / "resources.assets"
                reopened = _FakeUnityPy.load(str(target))
                script = reopened.objects[1]
                reopened_entries = list(
                    iter_naninovel_script_entries(
                        script,
                        "GenericVN_Data/resources.assets",
                        "701",
                        "MonoBehaviour:701",
                    )
                )
                values = {item.source_text for item in reopened_entries}
                self.assertIn("Xin chao VN generic.", values)
                self.assertIn("Mo cong vao", values)
                self.assertNotIn("Hello from generic VN.", values)
                self.assertNotIn("Open the gate", values)
            self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(), original_hash)

    def test_generic_data_unity3d_textasset_roundtrip_has_no_profile_scanner(self):
        with tempfile.TemporaryDirectory(prefix="vntext-generic-data-unity3d-micro-") as name:
            root = Path(name) / "game"
            source = _write_game(
                root,
                [
                    {
                        "path_id": 17,
                        "type": "TextAsset",
                        "name": "GenericDialogue",
                        "script": "A generic data.unity3d line.\n",
                        "type_tree_enabled": False,
                    }
                ],
                relative="GenericVN_Data/data.unity3d",
            )
            fake_unitypy = SimpleNamespace(load=_FakeUnityPy.load)
            with patch.dict(sys.modules, {"UnityPy": fake_unitypy}):
                entries = list(extract_unity_typetree(source, root))
            self.assertEqual([item.source_text for item in entries], ["A generic data.unity3d line."])

    def test_typetree_and_scriptableobject_roundtrip_use_field_locator(self):
        with tempfile.TemporaryDirectory(prefix="vntext-typetree-micro-") as name:
            root = Path(name) / "game"
            package = Path(name) / "package"
            patch_out = Path(name) / "patch"
            source = _write_game(
                root,
                [
                    {
                        "path_id": 11,
                        "type": "MonoBehaviour",
                        "class_name": "DialogueComponent",
                        "script_path_id": 901,
                        "type_tree_enabled": True,
                        "tree": {"scriptText": "Hello from component."},
                    },
                    {
                        "path_id": 12,
                        "type": "ScriptableObject",
                        "type_tree_enabled": True,
                        "tree": {"displayName": "Asset label appears."},
                    },
                ],
            )
            original_hash = hashlib.sha256(source.read_bytes()).hexdigest()
            fake_unitypy = SimpleNamespace(load=_FakeUnityPy.load)
            with patch.dict(sys.modules, {"UnityPy": fake_unitypy}):
                entries = list(extract_unity_typetree(source, root))
                selected = [
                    item
                    for item in entries
                    if item.import_method == "unity_typetree_field"
                ]
                self.assertEqual({item.source_text for item in selected}, {
                    "Hello from component.",
                    "Asset label appears.",
                })
                for item in selected:
                    self.assertIn(item.locator["field_path"], {"scriptText", "displayName"})
                    self.assertEqual(item.patch_proof, PROOFS["unity_typetree_field"])

                _write_package_translation(
                    package,
                    selected,
                    {
                        "Hello from component.": "Xin chao component.",
                        "Asset label appears.": "Nhan asset.",
                    },
                )
                with patch("vntext.patch_output.save_unity_env", side_effect=_save_fake_environment):
                    report = apply_translation_package(
                        str(package / "translation.csv"),
                        str(package / "manifest.json"),
                        str(root),
                        str(patch_out),
                    )
                self.assertTrue(any("UNITY Demo_Data\\microfixture: 2/2" in line for line in report), report)
                target = patch_out / "COPY_TO_GAME_ROOT" / "Demo_Data" / "microfixture"
                reopened = _FakeUnityPy.load(str(target))
                trees = {obj.path_id: obj.read_typetree() for obj in reopened.objects}
                self.assertEqual(trees[11]["scriptText"], "Xin chao component.")
                self.assertEqual(trees[12]["displayName"], "Nhan asset.")
            self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(), original_hash)

    def test_textasset_line_rerun_preserves_key_value_delimiter(self):
        with tempfile.TemporaryDirectory(prefix="vntext-textasset-rerun-micro-") as name:
            root = Path(name) / "game"
            package = Path(name) / "package"
            patch_out = Path(name) / "patch"
            source = _write_game(
                root,
                [
                    {
                        "path_id": 8,
                        "type": "TextAsset",
                        "name": "DefaultUI",
                        "script": "Default.Key: Xin chao\n",
                        "type_tree_enabled": False,
                        "tail_hex": TAIL.hex(),
                    }
                ],
            )
            entry = Entry(
                source_text="Default",
                file_path="Demo_Data/microfixture",
                context="TextAsset:DefaultUI:line:1",
                object_info="TextAsset:8:DefaultUI",
                import_method="unity_textasset_line",
                safety="safe",
                locator={
                    "path_id": "8",
                    "field": "m_Script",
                    "encoding": "utf-8",
                    "line_index": 0,
                    "line_mode": "key_value",
                    "prefix": "Default.Key:",
                },
                backend="unitypy_textasset",
                patch_proof=UNITY_TEXTASSET_PATCH_PROOF,
            ).finalize()
            _write_package_translation(package, [entry], {"Default": "Xin chao"})

            fake_unitypy = SimpleNamespace(load=_FakeUnityPy.load)
            with patch.dict(sys.modules, {"UnityPy": fake_unitypy}), patch(
                "vntext.patch_output.save_unity_env", side_effect=_save_fake_environment
            ):
                apply_translation_package(
                    str(package / "translation.csv"),
                    str(package / "manifest.json"),
                    str(root),
                    str(patch_out),
                )

            target = patch_out / "COPY_TO_GAME_ROOT" / "Demo_Data" / "microfixture"
            reopened = _FakeUnityPy.load(str(target))
            data = reopened.objects[0].read()
            self.assertEqual(data.m_Script, "Default.Key: Xin chao\n")

    def test_unityfs_textasset_growth_is_retained_for_repack(self):
        with tempfile.TemporaryDirectory(prefix="vntext-textasset-grow-micro-") as name:
            root = Path(name) / "game"
            package = Path(name) / "package"
            patch_out = Path(name) / "patch"
            source = _write_game(
                root,
                [
                    {
                        "path_id": 8,
                        "type": "TextAsset",
                        "name": "Dialogue",
                        "script": "Short line.\n",
                        "type_tree_enabled": False,
                    }
                ],
            )
            fake_unitypy = SimpleNamespace(load=_FakeUnityPy.load)
            with patch.dict(sys.modules, {"UnityPy": fake_unitypy}):
                entry = next(
                    item
                    for item in extract_unity_typetree(source, root)
                    if item.source_text == "Short line."
                )
                _write_package_translation(
                    package,
                    [entry],
                    {"Short line.": "Bản dịch dài hơn rất nhiều."},
                )
                with patch("vntext.patch_output.save_unity_env", side_effect=_save_fake_environment):
                    report = apply_translation_package(
                        str(package / "translation.csv"),
                        str(package / "manifest.json"),
                        str(root),
                        str(patch_out),
                    )
                self.assertTrue(any("UNITY Demo_Data\\microfixture: 1/1" in line for line in report), report)
                self.assertFalse(any("kept original" in line for line in report), report)
                target = patch_out / "COPY_TO_GAME_ROOT" / "Demo_Data" / "microfixture"
                reopened = _FakeUnityPy.load(str(target))
                self.assertEqual(reopened.objects[0].read().m_Script.rstrip(), "Bản dịch dài hơn rất nhiều.")

    def test_typetree_ui_text_receives_ui_patch_proof_and_enters_main(self):
        with tempfile.TemporaryDirectory(prefix="vntext-typetree-ui-proof-micro-") as name:
            root = Path(name) / "game"
            source = _write_game(
                root,
                [
                    {
                        "path_id": 13,
                        "type": "MonoBehaviour",
                        "class_name": "DialogueComponent",
                        "script_path_id": 902,
                        "type_tree_enabled": True,
                        "tree": {"m_Text": "Settings label."},
                    },
                ],
            )
            original_hash = hashlib.sha256(source.read_bytes()).hexdigest()
            fake_unitypy = SimpleNamespace(load=_FakeUnityPy.load)
            with patch.dict(sys.modules, {"UnityPy": fake_unitypy}):
                entries = list(extract_unity_typetree(source, root))
                selected = next(item for item in entries if item.source_text == "Settings label.")
                self.assertEqual(selected.import_method, "unity_ui_text")
                self.assertEqual(selected.patch_proof, PROOFS["unity_ui_text"])
                from vntext.patchability import route_main_flow

                main, review, _report = route_main_flow([selected])
                self.assertEqual(main, [selected])
                self.assertEqual(review, [])
            self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(), original_hash)

    def test_nested_ui_typetree_roundtrip_writes_exact_field_locator(self):
        with tempfile.TemporaryDirectory(prefix="vntext-nested-ui-micro-") as name:
            root = Path(name) / "game"
            package = Path(name) / "package"
            patch_out = Path(name) / "patch"
            source = _write_game(
                root,
                [
                    {
                        "path_id": 13,
                        "type": "MonoBehaviour",
                        "class_name": "Dropdown",
                        "type_tree_enabled": True,
                        "tree": {
                            "m_Options": {
                                "m_Options": [{"m_Text": "Option A"}]
                            }
                        },
                    }
                ],
            )
            original_hash = hashlib.sha256(source.read_bytes()).hexdigest()
            entry = Entry(
                source_text="Option A",
                file_path="Demo_Data/microfixture",
                context="m_Options.m_Options[0].m_Text",
                object_info="MonoBehaviour:13:Dropdown",
                import_method="unity_ui_text",
                safety="safe",
                locator={
                    "path_id": "13",
                    "field_path": "m_Options.m_Options[0].m_Text",
                    "type": "MonoBehaviour",
                    "class_name": "Dropdown",
                },
                backend="unity_ui_object",
                patch_proof=PROOFS["unity_ui_text"],
            ).finalize()
            fake_unitypy = SimpleNamespace(load=_FakeUnityPy.load)
            with patch.dict(sys.modules, {"UnityPy": fake_unitypy}):
                _write_package_translation(package, [entry], {"Option A": "Tùy chọn A"})
                with patch("vntext.patch_output.save_unity_env", side_effect=_save_fake_environment):
                    report = apply_translation_package(
                        str(package / "translation.csv"),
                        str(package / "manifest.json"),
                        str(root),
                        str(patch_out),
                    )
            self.assertTrue(any("UI TypeTree Demo_Data\\microfixture: 1/1" in line for line in report), report)
            target = patch_out / "COPY_TO_GAME_ROOT" / "Demo_Data" / "microfixture"
            reopened = _FakeUnityPy.load(str(target))
            self.assertEqual(
                reopened.objects[0].read_typetree()["m_Options"]["m_Options"][0]["m_Text"],
                "Tùy chọn A",
            )
            self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(), original_hash)

    def test_typetree_runtime_id_prefix_is_not_promoted(self):
        with tempfile.TemporaryDirectory(prefix="vntext-typetree-runtime-id-micro-") as name:
            root = Path(name) / "game"
            source = _write_game(
                root,
                [
                    {
                        "path_id": 14,
                        "type": "MonoBehaviour",
                        "class_name": "TipsPanel",
                        "script_path_id": 903,
                        "type_tree_enabled": True,
                        "tree": {
                            "unlockableIdPrefix": "Tips",
                            "managedTextCategory": "Tips",
                            "description": "Visible tips text.",
                        },
                    },
                ],
            )
            fake_unitypy = SimpleNamespace(load=_FakeUnityPy.load)
            with patch.dict(sys.modules, {"UnityPy": fake_unitypy}):
                entries = list(extract_unity_typetree(source, root))
            self.assertNotIn("Tips", {item.source_text for item in entries})
            self.assertIn("Visible tips text.", {item.source_text for item in entries})

    def test_unity_localization_stringtable_roundtrip_has_exact_locator_and_precondition(self):
        with tempfile.TemporaryDirectory(prefix="vntext-unity-localization-micro-") as name:
            root = Path(name) / "game"
            package = Path(name) / "package"
            patch_out = Path(name) / "patch"
            source = _write_game(
                root,
                [
                    {
                        "path_id": 61,
                        "type": "ScriptableObject",
                        "class_name": "StringTable",
                        "type_tree_enabled": True,
                        "tree": {
                            "m_TableData": [
                                {"m_Id": 1001, "m_Localized": "Welcome, player."},
                                {"m_Id": 1002, "m_Localized": "Open settings"},
                            ],
                            "m_Comment": "schema metadata is not a localized value",
                        },
                    },
                    {
                        "path_id": 62,
                        "type": "ScriptableObject",
                        "class_name": "SharedTableData",
                        "type_tree_enabled": True,
                        "tree": {"m_Entries": [{"m_Id": 1001, "m_Key": "welcome"}]},
                    },
                ],
            )
            original_hash = hashlib.sha256(source.read_bytes()).hexdigest()
            fake_unitypy = SimpleNamespace(load=_FakeUnityPy.load)
            with patch.dict(sys.modules, {"UnityPy": fake_unitypy}):
                entries = list(extract_unity_typetree(source, root))
                selected = [
                    item
                    for item in entries
                    if item.import_method == "unity_localization_string"
                ]
                self.assertEqual(
                    [item.source_text for item in selected],
                    ["Welcome, player.", "Open settings"],
                )
                self.assertEqual(
                    [item.locator["field_path"] for item in selected],
                    ["m_TableData[0].m_Localized", "m_TableData[1].m_Localized"],
                )
                self.assertEqual(
                    [item.locator["entry_id"] for item in selected],
                    [1001, 1002],
                )
                self.assertEqual(
                    [item.locator["entry_id_field_path"] for item in selected],
                    ["m_TableData[0].m_Id", "m_TableData[1].m_Id"],
                )
                self.assertTrue(all(item.patch_proof == PROOFS["unity_localization_string"] for item in selected))
                self.assertTrue(all(item.locator["table_kind"] == "StringTable" for item in selected))

                _write_package_translation(
                    package,
                    selected,
                    {
                        "Welcome, player.": "Chào bạn.",
                        "Open settings": "Mở cài đặt",
                    },
                )
                with patch("vntext.patch_output.save_unity_env", side_effect=_save_fake_environment):
                    report = apply_translation_package(
                        str(package / "translation.csv"),
                        str(package / "manifest.json"),
                        str(root),
                        str(patch_out),
                    )
                self.assertTrue(any("UNITY Demo_Data\\microfixture: 2/2" in line for line in report), report)
                target = patch_out / "COPY_TO_GAME_ROOT" / "Demo_Data" / "microfixture"
                reopened = _FakeUnityPy.load(str(target))
                tree = reopened.objects[0].read_typetree()
                self.assertEqual(tree["m_TableData"][0]["m_Localized"], "Chào bạn.")
                self.assertEqual(tree["m_TableData"][1]["m_Localized"], "Mở cài đặt")
                self.assertEqual(tree["m_Comment"], "schema metadata is not a localized value")
            self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(), original_hash)

    def test_unity_localization_writer_fails_closed_on_source_drift(self):
        from vntext.unity_localization import set_unity_localization_field

        tree = {"m_TableData": [{"m_Localized": "Current source"}]}
        before = copy.deepcopy(tree)
        self.assertFalse(
            set_unity_localization_field(
                tree,
                "m_TableData[0].m_Localized",
                "Stale source",
                "Không được ghi",
            )
        )
        self.assertEqual(tree, before)

    def test_unity_localization_writer_fails_closed_on_entry_identity_drift(self):
        with tempfile.TemporaryDirectory(prefix="vntext-unity-localization-id-drift-") as name:
            root = Path(name) / "game"
            package = Path(name) / "package"
            patch_out = Path(name) / "patch"
            source = _write_game(
                root,
                [
                    {
                        "path_id": 61,
                        "type": "ScriptableObject",
                        "class_name": "StringTable",
                        "type_tree_enabled": True,
                        "tree": {
                            "m_TableData": [
                                {"m_Id": 1001, "m_Localized": "Stable source."},
                            ],
                        },
                    },
                ],
            )
            entry = Entry(
                source_text="Stable source.",
                file_path="Demo_Data/microfixture",
                context="UnityLocalization:StringTable:id:9999:entry:0",
                object_info="ScriptableObject:61:StringTable",
                import_method="unity_localization_string",
                safety="safe",
                locator={
                    "path_id": "61",
                    "field_path": "m_TableData[0].m_Localized",
                    "class_name": "StringTable",
                    "table_kind": "StringTable",
                    "entry_index": 0,
                    "entry_id": 9999,
                },
                backend="unity_localization_string_table",
                patch_proof=dict(UNITY_LOCALIZATION_PATCH_PROOF),
            ).finalize()
            _write_package_translation(package, [entry], {"Stable source.": "Không được ghi."})
            original_hash = hashlib.sha256(source.read_bytes()).hexdigest()
            fake_unitypy = SimpleNamespace(load=_FakeUnityPy.load)
            with patch.dict(sys.modules, {"UnityPy": fake_unitypy}), patch(
                "vntext.patch_output.save_unity_env", side_effect=_save_fake_environment
            ):
                report = apply_translation_package(
                    str(package / "translation.csv"),
                    str(package / "manifest.json"),
                    str(root),
                    str(patch_out),
                )
            self.assertTrue(any("entry identity drift" in line for line in report), report)
            target = patch_out / "COPY_TO_GAME_ROOT" / "Demo_Data" / "microfixture"
            self.assertFalse(target.exists())
            self.assertTrue((patch_out / "COPY_TO_GAME_ROOT").is_dir())
            self.assertTrue((patch_out / "patch_manifest.json").is_file())
            self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(), original_hash)

    def test_unity_localization_without_entry_identity_stays_out_of_main(self):
        from vntext.unity_localization import iter_unity_localization_entries

        entries = list(
            iter_unity_localization_entries(
                {"m_TableData": [{"m_Localized": "No stable table identity."}]},
                "Demo_Data/localization.assets",
                "61",
                "ScriptableObject:61",
                "StringTable",
            )
        )
        self.assertEqual(entries, [])

    def test_tmp_ui_roundtrip_and_duplicate_aligned_slots(self):
        with tempfile.TemporaryDirectory(prefix="vntext-ui-micro-") as name:
            root = Path(name) / "game"
            package = Path(name) / "package"
            patch_out = Path(name) / "patch"
            raw = _aligned_text("Open Menu") + _aligned_text("Open Menu")
            source = _write_game(
                root,
                [
                    {"path_id": 501, "type": "MonoScript", "class_name": "TextMeshProUGUI"},
                    {
                        "path_id": 21,
                        "type": "MonoBehaviour",
                        "class_name": "TextMeshProUGUI",
                        "script_path_id": 501,
                        "type_tree_enabled": False,
                        "raw_hex": raw.hex(),
                        "text": "Open Menu",
                    },
                ],
            )
            original_hash = hashlib.sha256(source.read_bytes()).hexdigest()
            fake_unitypy = SimpleNamespace(load=_FakeUnityPy.load)
            with patch.dict(sys.modules, {"UnityPy": fake_unitypy}):
                entries = list(extract_unity_typetree(source, root))
                entry = next(item for item in entries if item.source_text == "Open Menu")
                self.assertEqual(entry.import_method, "unity_ui_text")
                self.assertEqual(entry.locator["field_path"], "m_Text")
                self.assertEqual(entry.patch_proof, PROOFS[entry.import_method])
                _write_package_translation(package, [entry], {"Open Menu": "Mo menu"})
                with patch("vntext.patch_output.save_unity_env", side_effect=_save_fake_environment):
                    report = apply_translation_package(
                        str(package / "translation.csv"),
                        str(package / "manifest.json"),
                        str(root),
                        str(patch_out),
                    )
                self.assertTrue(any("UNITY Demo_Data\\microfixture: 2/1" in line for line in report), report)
                target = patch_out / "COPY_TO_GAME_ROOT" / "Demo_Data" / "microfixture"
                reopened = _FakeUnityPy.load(str(target))
                self.assertEqual(reopened.objects[1].read().m_Text.rstrip(), "Mo menu")
                self.assertEqual(bytes(reopened.objects[1].data).count(b"Mo menu"), 2)

                duplicate_obj = _FakeObject(
                    {
                        "path_id": 99,
                        "type": "MonoBehaviour",
                        "class_name": "TextMeshProUGUI",
                        "script_path_id": 501,
                        "type_tree_enabled": False,
                        "raw_hex": raw.hex(),
                        "text": "Open Menu",
                    }
                )
                changed = patch_object_length_prefixed_strings(
                    duplicate_obj,
                    {"Open Menu": "Mo menu"},
                    preserve_slot_size=True,
                )
                self.assertEqual(changed, 2)
                self.assertEqual(bytes(duplicate_obj.data).count(b"Mo menu"), 2)
            self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(), original_hash)

    def test_ui_raw_overflow_uses_metadata_preserving_growth_without_data_save(self):
        with tempfile.TemporaryDirectory(prefix="vntext-ui-overflow-micro-") as name:
            root = Path(name) / "game"
            package = Path(name) / "package"
            patch_out = Path(name) / "patch"
            source = _write_game(
                root,
                [
                    {"path_id": 501, "type": "MonoScript", "class_name": "TextMeshProUGUI"},
                    {
                        "path_id": 21,
                        "type": "MonoBehaviour",
                        "class_name": "TextMeshProUGUI",
                        "script_path_id": 501,
                        "type_tree_enabled": False,
                        "raw_hex": _aligned_text("Open Menu").hex(),
                        "text": "Open Menu",
                    },
                ],
            )
            original_hash = hashlib.sha256(source.read_bytes()).hexdigest()
            fake_unitypy = SimpleNamespace(load=_FakeUnityPy.load)
            with patch.dict(sys.modules, {"UnityPy": fake_unitypy}):
                entry = next(
                    item
                    for item in extract_unity_typetree(source, root)
                    if item.source_text == "Open Menu"
                )
                _write_package_translation(
                    package,
                    [entry],
                    {"Open Menu": "Bản dịch dài hơn rất nhiều."},
                )
                with patch(
                    "vntext.patch_unity.patch_ui_text_fields_via_read",
                    side_effect=AssertionError("unsafe UI read fallback called"),
                ), patch(
                    "vntext.patch_output.save_unity_env",
                    side_effect=_save_fake_environment,
                ):
                    report = apply_translation_package(
                        str(package / "translation.csv"),
                        str(package / "manifest.json"),
                        str(root),
                        str(patch_out),
                    )
            self.assertTrue(
                any("UI Demo_Data\\microfixture: patched 1 m_text/TMP string slots" in line for line in report),
                report,
            )
            target = patch_out / "COPY_TO_GAME_ROOT" / "Demo_Data" / "microfixture"
            reopened = _FakeUnityPy.load(str(target))
            self.assertEqual(
                reopened.objects[1].read().m_Text,
                "Bản dịch dài hơn rất nhiều.",
            )
            self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(), original_hash)

    def test_ui_raw_patch_does_not_reenter_stale_read_cache(self):
        class StaleReadObject:
            def __init__(self):
                self.data = bytearray(_aligned_text("TEXT\n"))

            def set_raw_data(self, raw):
                self.data = bytearray(raw)

            def read(self):
                # UnityPy may return a cached pre-patch view here.
                return SimpleNamespace(m_Text="TEXT\n")

        obj = StaleReadObject()
        replacements = {"TEXT": "Chữ"}
        self.assertEqual(
            patch_object_length_prefixed_strings(
                obj,
                replacements,
                preserve_slot_size=False,
            ),
            1,
        )
        _pop_patched_ui_sources(replacements, obj)
        self.assertEqual(replacements, {})
        self.assertIn("Chữ\n".encode("utf-8"), bytes(obj.data))

    def test_no_typetree_custom_object_is_not_promoted(self):
        with tempfile.TemporaryDirectory(prefix="vntext-notypetree-micro-") as name:
            root = Path(name) / "game"
            raw = _aligned_text("Unknown custom text")
            source = _write_game(
                root,
                [
                    {
                        "path_id": 31,
                        "type": "MonoBehaviour",
                        "class_name": "CustomRuntimeComponent",
                        "script_path_id": 999,
                        "type_tree_enabled": False,
                        "raw_hex": raw.hex(),
                    }
                ],
            )
            fake_unitypy = SimpleNamespace(load=_FakeUnityPy.load)
            with patch.dict(sys.modules, {"UnityPy": fake_unitypy}):
                entries = list(extract_unity_typetree(source, root))
            self.assertEqual(entries, [])

    def test_proofless_typetree_manifest_row_is_fail_closed(self):
        with tempfile.TemporaryDirectory(prefix="vntext-typetree-proof-gate-") as name:
            root = Path(name) / "game"
            package = Path(name) / "package"
            patch_out = Path(name) / "patch"
            source = _write_game(
                root,
                [
                    {
                        "path_id": 41,
                        "type": "MonoBehaviour",
                        "class_name": "DialogueComponent",
                        "script_path_id": 901,
                        "type_tree_enabled": True,
                        "tree": {"scriptText": "Legacy source."},
                    },
                ],
            )
            fake_unitypy = SimpleNamespace(load=_FakeUnityPy.load)
            with patch.dict(sys.modules, {"UnityPy": fake_unitypy}):
                entry = next(
                    item
                    for item in extract_unity_typetree(source, root)
                    if item.import_method == "unity_typetree_field"
                )
                _write_package_translation(package, [entry], {"Legacy source.": "Should not write."})
                manifest_path = package / "manifest.json"
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                for row in manifest["entries"]:
                    row.pop("patch_proof", None)
                    row.pop("symmetry_proof", None)
                manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
                (patch_out / "COPY_TO_GAME_ROOT").mkdir(parents=True)
                with patch("vntext.patch_output.save_unity_env", side_effect=_save_fake_environment):
                    report = apply_translation_package(
                        str(package / "translation.csv"),
                        str(manifest_path),
                        str(root),
                        str(patch_out),
                    )
                self.assertTrue(
                    any("symmetry gate" in line and "proof" in line for line in report),
                    report,
                )
                self.assertFalse((patch_out / "COPY_TO_GAME_ROOT" / "Demo_Data" / "microfixture").exists())


if __name__ == "__main__":
    unittest.main()
