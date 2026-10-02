"""Micro-fixture coverage for the read-only Unity capability analyzer."""

from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


def _tests_lib_on_path() -> None:
    cur = Path(__file__).resolve().parent
    while cur.name != "tests" and cur.parent != cur:
        cur = cur.parent
    lib = cur / "lib"
    value = str(lib)
    if value not in sys.path:
        sys.path.insert(0, value)


_tests_lib_on_path()
from bootstrap import bootstrap

TESTS, ROOT, LIB = bootstrap(__file__)
from work_paths import work_temp_dir

WORK = work_temp_dir("unity_analyzer")

from vntext.unity_analyzer import (
    AnalyzerOptions,
    EXTRACT_ONLY,
    REVIEW_REQUIRED,
    SUPPORTED_AND_PATCHABLE,
    UNSUPPORTED,
    analyze_unity_game,
)


def _snapshot(root: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    for path in sorted(root.rglob("*"), key=lambda item: item.as_posix().lower()):
        if path.is_file():
            result[path.relative_to(root).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result


class UnityAnalyzerFixtureTests(unittest.TestCase):
    def _make_game(self) -> tuple[tempfile.TemporaryDirectory[str], Path]:
        holder = tempfile.TemporaryDirectory(prefix="vntext-unity-analyzer-")
        root = Path(holder.name)
        data = root / "Demo_Data"
        (data / "StreamingAssets" / "aa").mkdir(parents=True)
        (data / "StreamingAssets" / "Localization").mkdir(parents=True)
        (data / "Managed").mkdir()
        (data / "globalgamemanagers").write_bytes(b"\x00\x01unity marker\x00")
        (data / "resources.assets").write_bytes(b"\x00\xffserialized asset bytes\x00")
        (data / "extensionless.bundle").write_bytes(b"UnityFS\x00fake fixture\x00")
        (data / "StreamingAssets" / "dialogue").write_text("Hello from StreamingAssets\n", encoding="utf-8")
        (data / "StreamingAssets" / "Localization" / "en.json").write_text(
            json.dumps({"hello": "Hello"}), encoding="utf-8"
        )
        (data / "StreamingAssets" / "Localization" / "dialogue.csv").write_text(
            "id,text\nline_1,Hello from CSV\n", encoding="utf-8"
        )
        (data / "StreamingAssets" / "Localization" / "dialogue.xml").write_text(
            '<localization><entry id="line_1" text="Hello from XML">Welcome from XML</entry></localization>',
            encoding="utf-8",
        )
        (data / "StreamingAssets" / "Localization" / "ids.csv").write_text(
            "id,name\nline_1,internal_identifier\n", encoding="utf-8"
        )
        (data / "StreamingAssets" / "aa" / "catalog.json").write_text(
            json.dumps({"m_ResourceManagerRuntimeData": "fixture"}), encoding="utf-8"
        )
        (data / "StreamingAssets" / "aa" / "asset_0123456789abcdef0123456789abcdef.bundle").write_bytes(
            b"UnityFS\x00addressable bundle fixture"
        )
        (data / "StreamingAssets" / "packed" / "catalog.json").parent.mkdir(parents=True, exist_ok=True)
        (data / "StreamingAssets" / "packed" / "catalog.json").write_text(
            json.dumps({"m_ResourceManagerRuntimeData": "custom-layout"}), encoding="utf-8"
        )
        (data / "StreamingAssets" / "packed" / "locale_content.bundle").write_bytes(
            b"UnityFS\x00custom-layout bundle fixture"
        )
        (data / "bad.json").write_text('{"hello":', encoding="utf-8")
        (data / "bad.xml").write_text("<root>", encoding="utf-8")
        (data / "save.db").write_bytes(b"SQLite format 3\x00fixture")
        (data / "archive.bin").write_bytes(b"PK\x03\x04archive fixture")
        (data / "compressed.bin").write_bytes(b"\x1f\x8bcompressed fixture")
        (data / "unknown_strings.bin").write_bytes(b"\x89\x88\xff\x00Hello from an unknown binary\x00")
        (data / "opaque.bin").write_bytes(b"\x00\x01\x02\x03\xff\xfe\xfd")
        (root / "Demo.exe").write_bytes(b"MZ\x00\x01Demo executable")
        (root / "UnityPlayer.dll").write_bytes(b"MZ\x00\x01UnityPlayer")
        return holder, root

    def test_executable_resolves_unity_data_and_inventories_all_files(self):
        holder, root = self._make_game()
        try:
            before = _snapshot(root)
            report = analyze_unity_game(root / "Demo.exe", options=AnalyzerOptions(probe_unity_objects=False))
            after = _snapshot(root)

            self.assertTrue(report["unity"]["detected"])
            self.assertEqual(Path(report["unity"]["selected_data_root"]).name, "Demo_Data")
            self.assertEqual(report["unity"]["executable"], str((root / "Demo.exe").resolve()))
            self.assertTrue(report["inventory_complete"])
            self.assertEqual(report["summary"]["resource_count"], len(before))
            self.assertEqual(before, after)
            self.assertEqual(report["coverage"]["resources_detected"], len(before))
            self.assertEqual(report["coverage"]["resources_classified"], len(before))
            self.assertEqual(report["coverage"]["unknown_resources"], report["summary"]["unknown_resources"])
            self.assertEqual(report["coverage"]["writer_coverage"]["status"], "NOT_RUN")
            self.assertEqual(report["coverage"]["locator_precondition_coverage"]["status"], "NOT_RUN")
            self.assertEqual(report["coverage"]["patch_verification"]["status"], "NOT_RUN")
            self.assertEqual(report["coverage"]["writer_coverage"]["resource_writer_invocations"], 0)
            self.assertGreaterEqual(report["coverage"]["writer_coverage"]["contract_backed_observations"], 3)
            self.assertEqual(report["coverage"]["patch_verification"]["resource_verified"], 0)
            self.assertGreaterEqual(report["coverage"]["patch_verification"]["method_fixture_verified"], 3)
            self.assertTrue(
                all(item["proof_complete"] for item in report["coverage"]["writer_coverage"]["method_contracts"])
            )

            resources = {item["path"]: item for item in report["resources"]}
            self.assertIn("Demo_Data/extensionless.bundle", resources)
            self.assertEqual(resources["Demo_Data/extensionless.bundle"]["signature"], "unityfs")
            self.assertIn("STREAMING_ASSETS", resources["Demo_Data/StreamingAssets/dialogue"]["categories"])
            self.assertEqual(resources["Demo_Data/StreamingAssets/dialogue"]["status"], EXTRACT_ONLY)
            self.assertIn("ADDRESSABLES_CATALOG", resources["Demo_Data/StreamingAssets/aa/catalog.json"]["categories"])
            self.assertEqual(resources["Demo_Data/unknown_strings.bin"]["status"], REVIEW_REQUIRED)
            self.assertEqual(resources["Demo_Data/opaque.bin"]["status"], UNSUPPORTED)
            self.assertEqual(resources["Demo_Data/bad.json"]["signature"], "json_invalid")
            self.assertEqual(resources["Demo_Data/bad.json"]["status"], REVIEW_REQUIRED)
            self.assertEqual(resources["Demo_Data/bad.xml"]["signature"], "xml_invalid")
            self.assertEqual(resources["Demo_Data/bad.xml"]["status"], REVIEW_REQUIRED)
            self.assertEqual(resources["Demo_Data/save.db"]["signature"], "sqlite")
            self.assertEqual(resources["Demo_Data/save.db"]["status"], REVIEW_REQUIRED)
            self.assertIn(
                "structured_sqlite",
                {item["name"] for item in resources["Demo_Data/save.db"]["capabilities"]},
            )
            self.assertTrue(
                any(
                    item["method"] == "structured_sqlite_value" and item["proof_complete"]
                    for item in report["coverage"]["writer_coverage"]["method_contracts"]
                )
            )
            self.assertEqual(resources["Demo_Data/archive.bin"]["signature"], "zip")
            self.assertEqual(resources["Demo_Data/archive.bin"]["status"], REVIEW_REQUIRED)
            self.assertEqual(resources["Demo_Data/compressed.bin"]["signature"], "gzip")
            self.assertEqual(resources["Demo_Data/compressed.bin"]["status"], REVIEW_REQUIRED)
            self.assertIn(
                "ASSET_BUNDLE",
                resources["Demo_Data/StreamingAssets/aa/asset_0123456789abcdef0123456789abcdef.bundle"]["categories"],
            )
            custom_bundle = resources["Demo_Data/StreamingAssets/packed/locale_content.bundle"]
            self.assertIn("ADDRESSABLES_BUNDLE_CANDIDATE", custom_bundle["categories"])
            self.assertEqual(custom_bundle["capabilities"][-1]["name"], "addressables_bundle")
            self.assertEqual(custom_bundle["capabilities"][-1]["status"], REVIEW_REQUIRED)
        finally:
            holder.cleanup()

    def test_unknown_and_structured_resources_are_not_silently_dropped(self):
        holder, root = self._make_game()
        try:
            report = analyze_unity_game(root, options=AnalyzerOptions(probe_unity_objects=False))
            paths = {item["path"] for item in report["resources"]}
            self.assertIn("Demo.exe", paths)
            self.assertIn("UnityPlayer.dll", paths)
            self.assertIn("Demo_Data/unknown_strings.bin", paths)
            self.assertIn("Demo_Data/opaque.bin", paths)
            self.assertIn("Demo_Data/resources.assets", paths)
            self.assertIn("Demo_Data/StreamingAssets/Localization/en.json", paths)

            by_path = {item["path"]: item for item in report["resources"]}
            self.assertEqual(by_path["Demo_Data/StreamingAssets/Localization/en.json"]["signature"], "json")
            self.assertEqual(by_path["Demo_Data/StreamingAssets/Localization/en.json"]["status"], REVIEW_REQUIRED)
            self.assertIn(
                "structured_json",
                {item["name"] for item in by_path["Demo_Data/StreamingAssets/Localization/en.json"]["capabilities"]},
            )
            csv_resource = by_path["Demo_Data/StreamingAssets/Localization/dialogue.csv"]
            self.assertEqual(csv_resource["status"], REVIEW_REQUIRED)
            self.assertIn(
                "structured_csv",
                {item["name"] for item in csv_resource["capabilities"]},
            )
            xml_resource = by_path["Demo_Data/StreamingAssets/Localization/dialogue.xml"]
            self.assertEqual(xml_resource["status"], REVIEW_REQUIRED)
            self.assertIn(
                "structured_xml",
                {item["name"] for item in xml_resource["capabilities"]},
            )
            self.assertEqual(
                by_path["Demo_Data/StreamingAssets/Localization/ids.csv"]["status"],
                REVIEW_REQUIRED,
            )
            self.assertGreaterEqual(report["summary"]["unknown_resources"], 2)
            self.assertGreaterEqual(report["summary"]["text_candidate_resources"], 1)
            self.assertFalse(report["scan_errors"])
        finally:
            holder.cleanup()

    def test_resource_status_is_reduced_from_unproven_capabilities(self):
        holder, root = self._make_game()
        try:
            plain = root / "plain.json"
            plain.write_text(json.dumps({"hello": "Hello"}), encoding="utf-8")
            report = analyze_unity_game(root, options=AnalyzerOptions(probe_unity_objects=False))
            by_path = {item["path"]: item for item in report["resources"]}

            # A generic structured file without a high-risk marker remains
            # supported by its independently proven JSON route.
            self.assertEqual(by_path["plain.json"]["status"], SUPPORTED_AND_PATCHABLE)

            # A path marker is only a candidate, not proof of Unity
            # Localization/Addressables semantics; the resource must not be
            # advertised as fully patchable while that capability is review.
            for path in (
                "Demo_Data/StreamingAssets/Localization/en.json",
                "Demo_Data/StreamingAssets/Localization/dialogue.csv",
                "Demo_Data/StreamingAssets/Localization/dialogue.xml",
                "Demo_Data/StreamingAssets/aa/catalog.json",
            ):
                self.assertEqual(by_path[path]["status"], REVIEW_REQUIRED, path)
        finally:
            holder.cleanup()

    def test_report_is_deterministic_and_data_root_input_is_supported(self):
        holder, root = self._make_game()
        try:
            options = AnalyzerOptions(probe_unity_objects=False)
            first = analyze_unity_game(root, options=options)
            second = analyze_unity_game(root, options=options)
            self.assertEqual(json.dumps(first, sort_keys=True), json.dumps(second, sort_keys=True))

            data_report = analyze_unity_game(root / "Demo_Data", options=options)
            self.assertTrue(data_report["unity"]["detected"])
            self.assertEqual(Path(data_report["scan_root"]), root.resolve())
            self.assertEqual(data_report["summary"]["resource_count"], first["summary"]["resource_count"])
        finally:
            holder.cleanup()

    def test_invalid_input_is_explicitly_incomplete(self):
        with tempfile.TemporaryDirectory(prefix="vntext-unity-analyzer-invalid-") as name:
            report = analyze_unity_game(Path(name) / "missing.exe")
            self.assertFalse(report["inventory_complete"])
            self.assertFalse(report["unity"]["detected"])
            self.assertTrue(report["scan_errors"])

    def test_unity_object_probe_reports_textasset_ui_and_scriptable_capabilities(self):
        holder, root = self._make_game()
        try:
            asset = root / "Demo_Data" / "sample.assets"
            asset.write_bytes(b"\x00\xffUnity serialized fixture\x00")

            class FakeType:
                def __init__(self, name: str):
                    self.name = name

            fake_objects = [
                SimpleNamespace(type=FakeType("TextAsset")),
                SimpleNamespace(type=FakeType("MonoBehaviour")),
                SimpleNamespace(type=FakeType("ScriptableObject")),
                SimpleNamespace(type=FakeType("TextMeshProUGUI")),
            ]
            fake_unitypy = SimpleNamespace(load=lambda _path: SimpleNamespace(objects=fake_objects))
            with patch.dict(sys.modules, {"UnityPy": fake_unitypy}):
                report = analyze_unity_game(
                    asset,
                    options=AnalyzerOptions(include_sha256=False, probe_unity_objects=True),
                )

            resource = next(item for item in report["resources"] if item["path"] == "sample.assets")
            self.assertEqual(resource["probe"]["status"], "OPENED")
            self.assertEqual(resource["probe"]["object_count"], 4)
            self.assertEqual(resource["probe"]["type_counts"]["TextAsset"], 1)
            self.assertIn("TEXT_ASSET", resource["categories"])
            self.assertIn("MONOBEHAVIOUR", resource["categories"])
            self.assertIn("SCRIPTABLE_OBJECT", resource["categories"])
            self.assertIn("UNITY_UI_TMP", resource["categories"])
            capability_names = {item["name"] for item in resource["capabilities"]}
            self.assertTrue({"TextAsset", "MonoBehaviour", "ScriptableObject", "Unity_UI_TMP"}.issubset(capability_names))
            self.assertEqual(resource["status"], REVIEW_REQUIRED)
        finally:
            holder.cleanup()

    def test_unity_object_probe_detects_localization_script_identity_as_review(self):
        holder, root = self._make_game()
        try:
            asset = root / "Demo_Data" / "localization.assets"
            asset.write_bytes(b"\x00\xffserialized localization fixture\x00")

            class FakeType:
                def __init__(self, name: str):
                    self.name = name

            script = SimpleNamespace(
                m_ClassName="StringTable",
                m_Namespace="UnityEngine.Localization.Tables",
            )
            pointer = SimpleNamespace(deref_parse_as_object=lambda: script)
            fake_object = SimpleNamespace(
                type=FakeType("ScriptableObject"),
                read=lambda: SimpleNamespace(m_Script=pointer),
            )
            fake_unitypy = SimpleNamespace(
                load=lambda _path: SimpleNamespace(objects=[fake_object]),
            )
            with patch.dict(sys.modules, {"UnityPy": fake_unitypy}):
                report = analyze_unity_game(
                    asset,
                    options=AnalyzerOptions(include_sha256=False, probe_unity_objects=True),
                )

            resource = next(item for item in report["resources"] if item["path"] == "localization.assets")
            self.assertEqual(
                resource["probe"]["script_class_counts"][
                    "UnityEngine.Localization.Tables.StringTable"
                ],
                1,
            )
            self.assertIn("UNITY_LOCALIZATION_CANDIDATE", resource["categories"])
            capability = next(
                item for item in resource["capabilities"] if item["name"] == "unity_localization"
            )
            self.assertEqual(capability["status"], REVIEW_REQUIRED)
            self.assertTrue(
                any("StringTable" in item for item in capability["evidence"])
            )
            localization_contract = next(
                item
                for item in report["coverage"]["writer_coverage"]["method_contracts"]
                if item["method"] == "unity_localization_string"
            )
            self.assertEqual(localization_contract["capability"], "unity_localization")
            self.assertTrue(localization_contract["proof_complete"])
            self.assertEqual(resource["status"], REVIEW_REQUIRED)
        finally:
            holder.cleanup()


class UnityAnalyzerProgressTests(unittest.TestCase):
    def test_multifile_analysis_reports_progress_and_keeps_default_hashes(self):
        with tempfile.TemporaryDirectory(dir=str(WORK), prefix="progress-") as name:
            root = Path(name)
            (root / "dialogue.txt").write_text("Hello from a synthetic fixture\n", encoding="utf-8")
            (root / "strings.json").write_text('{"hello":"Hello"}', encoding="utf-8")
            (root / "opaque.bin").write_bytes(b"\x00\x01\x02synthetic")
            events: list[dict] = []

            report = analyze_unity_game(
                root,
                options=AnalyzerOptions(probe_unity_objects=False),
                progress_callback=events.append,
            )

            self.assertTrue(report["inventory_complete"])
            self.assertEqual(report["summary"]["resource_count"], 3)
            self.assertTrue(report["summary"]["sha256_enabled"])
            self.assertTrue(all(item["sha256"] for item in report["resources"]))
            steps = {event.get("step") for event in events}
            self.assertTrue({"unity_enumerate", "unity_classify", "unity_hash"}.issubset(steps), events)

    def test_cancel_during_enumeration_or_classification_stops_before_inventory(self):
        with tempfile.TemporaryDirectory(dir=str(WORK), prefix="cancel-stage-") as name:
            root = Path(name)
            for index in range(40):
                (root / f"dialogue-{index:02d}.txt").write_text(f"Hello {index}\n", encoding="utf-8")

            for cancel_step in ("unity_enumerate", "unity_classify"):
                with self.subTest(cancel_step=cancel_step):
                    cancelled = False
                    events: list[dict] = []

                    def progress(info: dict) -> None:
                        nonlocal cancelled
                        events.append(info)
                        if info.get("step") == cancel_step:
                            cancelled = True

                    with self.assertRaisesRegex(RuntimeError, "cancelled"):
                        analyze_unity_game(
                            root,
                            options=AnalyzerOptions(probe_unity_objects=False),
                            progress_callback=progress,
                            is_cancelled=lambda: cancelled,
                        )

                    self.assertTrue(any(event.get("step") == cancel_step for event in events), events)
                    if cancel_step == "unity_enumerate":
                        self.assertFalse(any(event.get("step") == "unity_classify" for event in events), events)
                    else:
                        self.assertFalse(any(event.get("step") == "unity_hash" for event in events), events)

    def test_cancel_during_large_file_hash_aborts_inventory(self):
        with tempfile.TemporaryDirectory(dir=str(WORK), prefix="cancel-hash-") as name:
            root = Path(name)
            (root / "first.txt").write_text("Hello\n", encoding="utf-8")
            large = root / "large.bin"
            large.write_bytes(b"x" * (12 * 1024 * 1024))
            (root / "last.txt").write_text("Goodbye\n", encoding="utf-8")
            cancelled = False
            hash_done: list[int] = []

            def progress(info: dict) -> None:
                nonlocal cancelled
                if info.get("step") == "unity_hash":
                    done = int(info.get("done") or 0)
                    hash_done.append(done)
                    if done >= 1024 * 1024:
                        cancelled = True

            with self.assertRaisesRegex(RuntimeError, "cancelled"):
                analyze_unity_game(
                    root,
                    options=AnalyzerOptions(probe_unity_objects=False),
                    progress_callback=progress,
                    is_cancelled=lambda: cancelled,
                )

            self.assertTrue(hash_done and max(hash_done) < large.stat().st_size, hash_done)


if __name__ == "__main__":
    unittest.main()
