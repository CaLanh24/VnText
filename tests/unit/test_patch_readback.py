from __future__ import annotations

import json
import os
import sqlite3
import struct
import sys
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import vntext.patch_readback as patch_readback
from vntext.patch_readback import FAIL, NOT_TESTABLE, PASS, TIMEOUT, verify_patch_targets, write_patch_verification_report
from vntext.structured_csv import patch_structured_csv
from vntext.structured_json import patch_structured_json
from vntext.structured_xml import patch_structured_xml


def _slow_readback(_patched_root, _game_root, _grouped_items):
    """Spawn-safe deterministic reader used to exercise the hard deadline."""

    time.sleep(2.0)
    return {"schema_version": 1, "counts": {"PASS": 1}, "results": [{"status": PASS}]}


class PatchReadbackTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="vntext-readback-")
        self.root = Path(self.temp.name)
        self.patch_root = self.root / "COPY_TO_GAME_ROOT"

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _verify(self, rel: str, entry: dict, translation: str) -> dict:
        return verify_patch_targets(
            self.patch_root,
            self.root,
            {rel: [(entry, translation)]},
        )["results"][0]

    def test_windows_readback_child_is_console_isolated(self):
        if os.name != "nt":
            self.skipTest("Windows subprocess creation policy")
        launch = patch_readback._readback_subprocess_launch()
        expected = int(getattr(patch_readback.subprocess, "CREATE_NO_WINDOW", 0)) | int(
            getattr(patch_readback.subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        )
        self.assertEqual(launch["creationflags"], expected)
        self.assertTrue(Path(launch["executable"]).name.lower() in {"python.exe", "pythonw.exe"})
        if Path(sys.executable).with_name("pythonw.exe").is_file():
            self.assertEqual(Path(launch["executable"]).name.lower(), "pythonw.exe")

    def test_plain_text_reopens_exact_line_and_detects_wrong_output(self):
        source = self.root / "dialogue.txt"
        target = self.patch_root / "dialogue.txt"
        source.write_text("NPC: Hello\n", encoding="utf-8")
        target.parent.mkdir(parents=True)
        target.write_text("NPC: Xin chào\n", encoding="utf-8")
        entry = {
            "key": "plain",
            "source_text": "Hello",
            "file_path": "dialogue.txt",
            "import_method": "plain_text_line",
            "locator": {"line": 1},
        }
        self.assertEqual(self._verify("dialogue.txt", entry, "Xin chào")["status"], PASS)
        target.write_text("NPC: Sai\n", encoding="utf-8")
        self.assertEqual(self._verify("dialogue.txt", entry, "Xin chào")["status"], FAIL)

    def test_structured_json_csv_xml_reopen_values(self):
        json_source = self.root / "data.json"
        json_target = self.patch_root / "data.json"
        json_source.write_text(json.dumps({"dialogue": "Hello"}), encoding="utf-8")
        json_target.parent.mkdir(parents=True, exist_ok=True)
        patch_structured_json(
            json_source,
            json_target,
            [({"source_text": "Hello", "locator": {"json_pointer": "/dialogue"}}, "Xin chào")],
        )
        self.assertEqual(
            self._verify(
                "data.json",
                {
                    "key": "json",
                    "source_text": "Hello",
                    "file_path": "data.json",
                    "import_method": "structured_json_value",
                    "locator": {"json_pointer": "/dialogue"},
                },
                "Xin chào",
            )["status"],
            PASS,
        )

        csv_source = self.root / "data.csv"
        csv_target = self.patch_root / "data.csv"
        csv_source.write_text("id,text\n1,Hello\n", encoding="utf-8")
        patch_structured_csv(
            csv_source,
            csv_target,
            [({"source_text": "Hello", "locator": {"row_index": 1, "column_index": 1}}, "Xin chào")],
        )
        self.assertEqual(
            self._verify(
                "data.csv",
                {
                    "key": "csv",
                    "source_text": "Hello",
                    "file_path": "data.csv",
                    "import_method": "structured_csv_cell",
                    "locator": {"row_index": 1, "column_index": 1},
                },
                "Xin chào",
            )["status"],
            PASS,
        )

        xml_source = self.root / "data.xml"
        xml_target = self.patch_root / "data.xml"
        xml_source.write_text("<root><line text=\"Hello\" /></root>\n", encoding="utf-8")
        patch_structured_xml(
            xml_source,
            xml_target,
            [(
                {"source_text": "Hello", "locator": {"xml_path": [0], "node_kind": "attribute", "attribute": "text"}},
                "Xin chào",
            )],
        )
        self.assertEqual(
            self._verify(
                "data.xml",
                {
                    "key": "xml",
                    "source_text": "Hello",
                    "file_path": "data.xml",
                    "import_method": "structured_xml_value",
                    "locator": {"xml_path": [0], "node_kind": "attribute", "attribute": "text"},
                },
                "Xin chào",
            )["status"],
            PASS,
        )

    def test_sqlite_reopen_and_unknown_route_are_fail_closed(self):
        source = self.root / "data.sqlite3"
        target = self.patch_root / "data.sqlite3"
        connection = sqlite3.connect(source)
        try:
            connection.execute("CREATE TABLE dialogue (text TEXT)")
            connection.execute("INSERT INTO dialogue(text) VALUES (?)", ("Hello",))
            connection.commit()
        finally:
            connection.close()
        target.parent.mkdir(parents=True, exist_ok=True)
        copy = sqlite3.connect(target)
        try:
            copy.execute("CREATE TABLE dialogue (text TEXT)")
            copy.execute("INSERT INTO dialogue(text) VALUES (?)", ("Xin chào",))
            copy.commit()
        finally:
            copy.close()
        entry = {
            "key": "sqlite",
            "source_text": "Hello",
            "file_path": "data.sqlite3",
            "import_method": "structured_sqlite_value",
            "locator": {"table": "dialogue", "column": "text", "rowid": 1},
        }
        self.assertEqual(self._verify("data.sqlite3", entry, "Xin chào")["status"], PASS)
        entry["import_method"] = "naninovel_raw_candidate"
        self.assertEqual(self._verify("data.sqlite3", entry, "Xin chào")["status"], NOT_TESTABLE)

    def test_unity_ui_nested_field_reopens_by_full_typetree_locator(self):
        source = self.root / "Demo_Data" / "ui.bundle"
        target = self.patch_root / "Demo_Data" / "ui.bundle"
        source.parent.mkdir(parents=True)
        target.parent.mkdir(parents=True)
        source.write_bytes(b"source unity fixture")
        target.write_bytes(b"patched unity fixture")

        class FakeObject:
            def __init__(self, tree):
                self.path_id = 77
                self._tree = tree

            def read(self):
                return SimpleNamespace()

            def read_typetree(self):
                return self._tree

        source_env = SimpleNamespace(objects=[FakeObject({"m_Options": {"m_Options": [{"m_Text": "MAX"}]}})])
        target_env = SimpleNamespace(objects=[FakeObject({"m_Options": {"m_Options": [{"m_Text": "TỐI ĐA"}]}})])
        fake_unitypy = SimpleNamespace(
            load=lambda path: source_env if Path(path) == source else target_env,
        )
        entry = {
            "key": "nested-ui",
            "source_text": "MAX",
            "file_path": "Demo_Data/ui.bundle",
            "import_method": "unity_ui_text",
            "locator": {
                "path_id": "77",
                "field_path": "m_Options.m_Options[0].m_Text",
            },
        }
        with patch.dict(sys.modules, {"UnityPy": fake_unitypy}):
            result = self._verify("Demo_Data/ui.bundle", entry, "TỐI ĐA")
        self.assertEqual(result["status"], PASS, result)

    def test_unity_reopen_keeps_writer_first_match_for_duplicate_path_id(self):
        source = self.root / "Demo_Data" / "ui.bundle"
        target = self.patch_root / "Demo_Data" / "ui.bundle"
        source.parent.mkdir(parents=True)
        target.parent.mkdir(parents=True)
        source.write_bytes(b"source unity fixture")
        target.write_bytes(b"patched unity fixture")

        class FakeObject:
            def __init__(self, value):
                self.path_id = 79
                self._value = value

            def read(self):
                return SimpleNamespace(m_Text=self._value)

        source_env = SimpleNamespace(objects=[FakeObject("MAX"), FakeObject("stale")])
        target_env = SimpleNamespace(objects=[FakeObject("TỐI ĐA"), FakeObject("wrong")])
        fake_unitypy = SimpleNamespace(
            load=lambda path: source_env if Path(path) == source else target_env,
        )
        entry = {
            "key": "duplicate-path-id-ui",
            "source_text": "MAX",
            "file_path": "Demo_Data/ui.bundle",
            "import_method": "unity_ui_text",
            "locator": {"path_id": "79", "field_path": "m_Text"},
        }
        with patch.dict(sys.modules, {"UnityPy": fake_unitypy}):
            result = self._verify("Demo_Data/ui.bundle", entry, "TỐI ĐA")
        self.assertEqual(result["status"], PASS, result)

    def test_unity_ui_mtext_locator_reads_tmp_mtext_alias(self):
        source = self.root / "Demo_Data" / "ui.bundle"
        target = self.patch_root / "Demo_Data" / "ui.bundle"
        source.parent.mkdir(parents=True)
        target.parent.mkdir(parents=True)
        source.write_bytes(b"source unity fixture")
        target.write_bytes(b"patched unity fixture")

        class FakeObject:
            def __init__(self, value):
                self.path_id = 78
                self._value = value

            def read(self):
                return SimpleNamespace(m_text=self._value)

            def read_typetree(self):
                return {"m_text": self._value}

        source_env = SimpleNamespace(objects=[FakeObject("Author Name")])
        target_env = SimpleNamespace(objects=[FakeObject("Tên tác giả")])
        fake_unitypy = SimpleNamespace(
            load=lambda path: source_env if Path(path) == source else target_env,
        )
        entry = {
            "key": "tmp-ui",
            "source_text": "Author Name",
            "file_path": "Demo_Data/ui.bundle",
            "import_method": "unity_ui_text",
            "locator": {
                "path_id": "78",
                "field_path": "m_Text",
                "class_name": "TextMeshProUGUI",
            },
        }
        with patch.dict(sys.modules, {"UnityPy": fake_unitypy}):
            result = self._verify("Demo_Data/ui.bundle", entry, "Tên tác giả")
        self.assertEqual(result["status"], PASS, result)

    def test_unity_ui_fixed_slot_padding_is_semantically_verified(self):
        source = self.root / "Demo_Data" / "ui.bundle"
        target = self.patch_root / "Demo_Data" / "ui.bundle"
        source.parent.mkdir(parents=True)
        target.parent.mkdir(parents=True)
        source.write_bytes(b"source unity fixture")
        target.write_bytes(b"patched unity fixture")

        def aligned(value: str) -> bytes:
            raw = value.encode("utf-8")
            return struct.pack("<i", len(raw)) + raw + (b"\x00" * ((4 - len(raw) % 4) % 4))

        class FakeObject:
            def __init__(self, raw: bytes, value: str):
                self.path_id = 80
                self.data = raw
                self._value = value

            def read(self):
                return SimpleNamespace(m_Text=self._value)

        source_env = SimpleNamespace(objects=[FakeObject(aligned("Open Menu"), "Open Menu")])
        target_env = SimpleNamespace(objects=[FakeObject(aligned("Mo menu  "), "Mo menu  ")])
        fake_unitypy = SimpleNamespace(
            load=lambda path: source_env if Path(path) == source else target_env,
        )
        entry = {
            "key": "fixed-slot-ui",
            "source_text": "Open Menu",
            "file_path": "Demo_Data/ui.bundle",
            "import_method": "unity_ui_text",
            "locator": {"path_id": "80", "field_path": "m_Text"},
        }
        with patch.dict(sys.modules, {"UnityPy": fake_unitypy}):
            result = self._verify("Demo_Data/ui.bundle", entry, "Mo menu")
        self.assertEqual(result["status"], PASS, result)

    def test_unity_ui_source_padding_is_not_compared_as_display_text(self):
        source = self.root / "Demo_Data" / "ui.bundle"
        target = self.patch_root / "Demo_Data" / "ui.bundle"
        source.parent.mkdir(parents=True)
        target.parent.mkdir(parents=True)
        source.write_bytes(b"source unity fixture")
        target.write_bytes(b"patched unity fixture")

        def aligned(value: str) -> bytes:
            raw = value.encode("utf-8")
            return struct.pack("<i", len(raw)) + raw + (b"\x00" * ((4 - len(raw) % 4) % 4))

        class FakeObject:
            def __init__(self, raw: bytes, value: str):
                self.path_id = 81
                self.data = raw
                self._value = value

            def read(self):
                return SimpleNamespace(m_Text=self._value)

        source_value = "40%\n60%    "
        target_value = "40%\n60%        "
        source_env = SimpleNamespace(objects=[FakeObject(aligned(source_value), source_value)])
        target_env = SimpleNamespace(objects=[FakeObject(aligned(target_value), target_value)])
        fake_unitypy = SimpleNamespace(
            load=lambda path: source_env if Path(path) == source else target_env,
        )
        entry = {
            "key": "fixed-slot-ui-source-padding",
            "source_text": "40%\n60%",
            "file_path": "Demo_Data/ui.bundle",
            "import_method": "unity_ui_text",
            "locator": {"path_id": "81", "field_path": "m_Text"},
        }
        with patch.dict(sys.modules, {"UnityPy": fake_unitypy}):
            result = self._verify("Demo_Data/ui.bundle", entry, "40%\n60%")
        self.assertEqual(result["status"], PASS, result)

    def test_unity_textasset_line_with_prefix_compares_value_not_full_line(self):
        source = self.root / "Demo_Data" / "dialogue.assets"
        target = self.patch_root / "Demo_Data" / "dialogue.assets"
        source.parent.mkdir(parents=True)
        target.parent.mkdir(parents=True)
        source.write_bytes(b"source unity fixture")
        target.write_bytes(b"patched unity fixture")

        class FakeObject:
            def __init__(self, script):
                self.path_id = 88
                self._data = SimpleNamespace(m_Script=script)

            def read(self):
                return self._data

        source_env = SimpleNamespace(objects=[FakeObject("Default.Key: Default\n")])
        target_env = SimpleNamespace(objects=[FakeObject("Default.Key: Xin chào\n")])
        fake_unitypy = SimpleNamespace(
            load=lambda path: source_env if Path(path) == source else target_env,
        )
        entry = {
            "key": "prefixed-textasset",
                "source_text": "Default",
            "file_path": "Demo_Data/dialogue.assets",
            "import_method": "unity_textasset_line",
            "locator": {
                "path_id": "88",
                "field": "m_Script",
                "line_index": 0,
                "prefix": "Default.Key:",
            },
        }
        with patch.dict(sys.modules, {"UnityPy": fake_unitypy}):
            result = self._verify("Demo_Data/dialogue.assets", entry, "Xin chào")
        self.assertEqual(result["status"], PASS, result)

    def test_naninovel_indexed_readback_caches_one_scan_per_script_object(self):
        source = self.root / "Demo_Data" / "data.unity3d"
        target = self.patch_root / "Demo_Data" / "data.unity3d"
        source.parent.mkdir(parents=True)
        target.parent.mkdir(parents=True)
        source.write_bytes(b"source unity fixture")
        target.write_bytes(b"patched unity fixture")

        class FakeObject:
            def __init__(self, label):
                self.path_id = 91
                self.label = label

        source_env = SimpleNamespace(objects=[FakeObject("source")])
        target_env = SimpleNamespace(objects=[FakeObject("target")])
        fake_unitypy = SimpleNamespace(
            load=lambda path: source_env if Path(path) == source else target_env,
        )
        entries = [
            {
                "key": f"nano-{index}",
                "source_text": f"Line {index}",
                "file_path": "Demo_Data/data.unity3d",
                "import_method": "naninovel_script_string",
                "locator": {"path_id": "91", "scan_index": index, "display_index": 0},
            }
            for index in range(3)
        ]
        source_items = [{"text": "Line 0"}, {"text": "Line 1"}, {"text": "Line 2"}]
        target_items = [{"text": "Dòng 0"}, {"text": "Dòng 1"}, {"text": "Dòng 2"}]

        def raw_bytes(obj):
            return obj.label.encode()

        def scanned(raw, **_kwargs):
            return source_items if raw == b"source" else target_items

        with (
            patch.dict(sys.modules, {"UnityPy": fake_unitypy}),
            patch("vntext.extract_naninovel._object_raw_bytes", side_effect=raw_bytes) as raw_mock,
            patch("vntext.extract_naninovel._scan_script_object_strings", side_effect=scanned) as scan_mock,
        ):
            report = verify_patch_targets(
                self.patch_root,
                self.root,
                {"Demo_Data/data.unity3d": [(entry, f"Dòng {index}") for index, entry in enumerate(entries)]},
            )

        self.assertEqual(report["counts"], {PASS: 3})
        self.assertEqual(raw_mock.call_count, 2)
        self.assertEqual(scan_mock.call_count, 2)

    def test_missing_plain_locator_is_not_testable(self):
        source = self.root / "dialogue.txt"
        target = self.patch_root / "dialogue.txt"
        source.write_text("Hello\n", encoding="utf-8")
        target.parent.mkdir(parents=True)
        target.write_text("Xin chào\n", encoding="utf-8")
        entry = {
            "key": "old",
            "source_text": "Hello",
            "file_path": "dialogue.txt",
            "import_method": "plain_text_line",
            "locator": {},
        }
        self.assertEqual(self._verify("dialogue.txt", entry, "Xin chào")["status"], NOT_TESTABLE)

    def test_slow_reader_times_out_and_writes_failure_contract(self):
        entry = {
            "key": "slow",
            "source_text": "Hello",
            "file_path": "dialogue.txt",
            "import_method": "plain_text_line",
            "locator": {"line": 1},
        }
        report = verify_patch_targets(
            self.patch_root,
            self.root,
            {"dialogue.txt": [(entry, "Xin chào")]},
            timeout_seconds=1.0,
            _runner=_slow_readback,
        )
        self.assertEqual(report["status"], TIMEOUT)
        self.assertEqual(report["counts"], {TIMEOUT: 1})
        self.assertEqual(report["results"][0]["status"], TIMEOUT)
        output = self.root / "patch-out"
        output.mkdir()
        report_path = write_patch_verification_report(output, report)
        payload = json.loads(report_path.read_text(encoding="utf-8"))
        self.assertEqual(payload["status"], TIMEOUT)
        self.assertNotEqual(payload["results"][0]["status"], PASS)

    def test_aggregate_deadline_covers_multiple_target_groups(self):
        def entry(key: str, rel: str) -> dict:
            return {
                "key": key,
                "source_text": "Hello",
                "file_path": rel,
                "import_method": "plain_text_line",
                "locator": {"line": 1},
            }

        report = verify_patch_targets(
            self.patch_root,
            self.root,
            {
                "one.txt": [(entry("one", "one.txt"), "Xin")],
                "two.txt": [(entry("two", "two.txt"), "Xin")],
            },
            timeout_seconds=1.0,
            _runner=_slow_readback,
        )
        self.assertEqual(report["status"], TIMEOUT)
        self.assertEqual(report["counts"], {TIMEOUT: 2})
        self.assertEqual(len(report["results"]), 2)


if __name__ == "__main__":
    unittest.main()
