"""Phase 3 symmetry-contract tests; legacy package behavior stays separate."""

from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path
import tempfile


from vntext.patchability import (
    EXTRACT_ONLY,
    PATCHABLE_METHOD_CONTRACTS,
    REVIEW_REQUIRED,
    SUPPORTED_AND_PATCHABLE,
    UNSUPPORTED,
    assess_entry,
    audit_entries,
    enforce_main_flow,
    is_technical_skip_entry,
    make_renpy_contract,
    route_main_flow,
)
from vntext.entry import Entry
from vntext.package_io import read_csv_rows_file, write_csv_rows_file, write_package
from vntext.patch import apply_translation_package
from vntext.patch_safety import resolve_game_source_file


_PROOF = {
    "reader": True,
    "writer": True,
    "preflight": True,
    "reopen": True,
    "semantic_verify": True,
}


def _entry(method: str, locator: dict | None = None, **extra) -> dict:
    return {
        "key": f"key-{method}",
        "source_text": "Hello player",
        "file_path": "Demo_Data/data.assets",
        "import_method": method,
        "locator": dict(locator or {}),
        **extra,
    }


class PatchabilityContractTests(unittest.TestCase):
    def test_known_methods_have_explicit_reader_writer_locator_and_growth_policy(self):
        self.assertGreaterEqual(len(PATCHABLE_METHOD_CONTRACTS), 9)
        for method, contract in PATCHABLE_METHOD_CONTRACTS.items():
            with self.subTest(method=method):
                self.assertTrue(contract.reader)
                self.assertTrue(contract.writer)
                self.assertTrue(contract.locator_kind)
                self.assertTrue(contract.precondition)
                self.assertTrue(contract.growth_policy)

    def test_complete_locator_is_patchable_but_missing_locator_fails_closed(self):
        cases = {
            "plain_text_line": {"line": 2},
            "unity_textasset_line": {"path_id": "7", "line_index": 2},
            "unity_textasset_table_cell": {"path_id": "7", "line_index": 2, "column_index": 1},
            "unity_textasset_script": {"path_id": "7"},
            "unity_typetree_field": {"path_id": "7", "field_path": "m_Text"},
            "unity_ui_text": {"path_id": "7", "field_path": "m_Text"},
            "unity_localization_string": {
                "path_id": "7",
                "field_path": "m_TableData[0].m_Localized",
                "table_kind": "StringTable",
                "entry_index": 0,
                "entry_id": 1001,
            },
            "naninovel_script_string": {"path_id": "7"},
            "naninovel_choice": {"path_id": "7"},
            "naninovel_print": {"path_id": "7"},
            "structured_json_value": {"json_pointer": "/dialogue"},
            "structured_csv_cell": {"row_index": 1, "column_index": 2},
            "structured_xml_value": {"xml_path": [0, 1], "node_kind": "text"},
            "structured_sqlite_value": {
                "table": "dialogue",
                "column": "text",
                "rowid": 1,
                "schema_fingerprint": "schema",
                "file_sha256": "sha256",
            },
        }
        for method, locator in cases.items():
            with self.subTest(method=method):
                result = assess_entry(_entry(method, locator, patch_proof=_PROOF))
                self.assertEqual(result.status, SUPPORTED_AND_PATCHABLE)
                self.assertTrue(result.eligible)
                self.assertFalse(result.missing_locator_fields)
                self.assertEqual(result.to_dict()["required_locator_fields"], list(PATCHABLE_METHOD_CONTRACTS[method].required_locator_fields))

        dialogue = assess_entry(
            _entry("renpy_dialogue", {"native_id": "start_a", "line": 2}, patch_proof=_PROOF)
        )
        self.assertEqual(dialogue.status, SUPPORTED_AND_PATCHABLE)
        self.assertTrue(dialogue.eligible)

        legacy_string = assess_entry(
            _entry("renpy_string", {"source": "Hello player", "line": 2}, patch_proof=_PROOF)
        )
        self.assertEqual(legacy_string.status, REVIEW_REQUIRED)
        self.assertIn("native provenance", legacy_string.reason)

        native_string = _entry(
            "renpy_string",
            {"source": "Hello player", "unit_type": "string"},
            backend="renpy_loose_source",
            patch_proof=_PROOF,
        )
        native_string["native_contract"] = make_renpy_contract(
            method="renpy_string",
            backend="renpy_loose_source",
            unit_type="string",
            source_text="Hello player",
            file_path=native_string["file_path"],
            source_sha256=hashlib.sha256(b"source").hexdigest(),
            template_sha256=hashlib.sha256(b"template").hexdigest(),
        )
        result = assess_entry(native_string)
        self.assertEqual(result.status, SUPPORTED_AND_PATCHABLE)
        self.assertTrue(result.eligible)

        missing = assess_entry(_entry("unity_ui_text", {"path_id": "7"}, patch_proof=_PROOF))
        self.assertEqual(missing.status, REVIEW_REQUIRED)
        self.assertFalse(missing.eligible)
        self.assertIn("field_path", missing.missing_locator_fields)

    def test_extract_only_and_unknown_are_not_promoted(self):
        raw = assess_entry(_entry("raw_fixed_slot", {"offset": 10, "length": 8}))
        unknown = assess_entry(_entry("custom_binary_string"))
        review = assess_entry(_entry("unity_ui_text", {"path_id": "7"}, review_only=True))
        self.assertEqual(raw.status, EXTRACT_ONLY)
        self.assertFalse(raw.eligible)
        self.assertEqual(unknown.status, UNSUPPORTED)
        self.assertFalse(unknown.eligible)
        self.assertEqual(review.status, REVIEW_REQUIRED)
        self.assertFalse(review.eligible)

    def test_require_proof_is_strict_and_enforce_main_flow_does_not_mutate(self):
        entry = _entry("unity_ui_text", {"path_id": "7", "field_path": "m_Text"})
        before = dict(entry)
        pending = assess_entry(entry, require_proof=True)
        self.assertEqual(pending.status, REVIEW_REQUIRED)
        self.assertIn("semantic_verify", pending.reason)
        self.assertEqual(entry, before)
        with self.assertRaisesRegex(ValueError, "symmetry gate failed"):
            enforce_main_flow([entry])

        entry["patch_proof"] = {
            "reader": True,
            "writer": True,
            "preflight": True,
            "reopen": True,
            "semantic_verify": True,
        }
        report = enforce_main_flow([entry])
        self.assertTrue(report["main_flow_safe"])
        self.assertEqual(report["eligible"], 1)

    def test_route_main_flow_keeps_unproven_discovery_in_review(self):
        proven = _entry(
            "unity_ui_text",
            {"path_id": "7", "field_path": "m_Text"},
            patch_proof=_PROOF,
        )
        unproven = _entry(
            "unity_typetree_field",
            {"path_id": "8", "field_path": "dialogueText"},
        )
        extract_only = _entry("raw_fixed_slot", {"offset": 10, "length": 8})

        from vntext.patchability import route_main_flow

        main, review, report = route_main_flow([proven, unproven, extract_only])
        self.assertEqual(main, [proven])
        self.assertEqual(review, [unproven, extract_only])
        self.assertTrue(all(item.get("review_only") for item in review))
        self.assertTrue(report["route_complete"])
        self.assertEqual(report["promoted_main_entries"], 1)
        self.assertEqual(report["demoted_to_review_entries"], 2)
        self.assertTrue(report["main_flow_safe"])
        self.assertFalse(report["source_main_flow_safe"])

    def test_technical_row_is_skipped_before_symmetry_review(self):
        entry = Entry(
            source_text="yyyy-MM-dd HH:mm:ss",
            file_path="Sample_Data/StreamingAssets/state.bundle",
            context="dateFormat",
            object_info="MonoBehaviour:-598:GameStateSlot",
            import_method="unity_typetree_field",
            locator={"path_id": -598, "field_path": "dateFormat"},
            backend="unitypy_typetree",
        ).finalize()

        self.assertTrue(is_technical_skip_entry(entry))
        main, review, report = route_main_flow([entry])
        self.assertEqual([entry], main)
        self.assertFalse(review)
        self.assertFalse(entry.review_only)
        self.assertEqual(1, report["technical_preclassified_entries"])

        with tempfile.TemporaryDirectory(prefix="vntext-technical-skip-package-") as name:
            out = Path(name) / "package"
            write_package(str(out), main, review, {"mode": "deep"}, True, enforce_symmetry=True)
            _fields, translation_rows = read_csv_rows_file(out / "translation.csv")
            _fields, technical_rows = read_csv_rows_file(out / "technical_skipped.csv")
            self.assertFalse(translation_rows)
            self.assertEqual(1, len(technical_rows))
            self.assertFalse(
                (out / "review_only.csv").read_text(encoding="utf-8-sig").strip().splitlines()[1:]
            )

    def test_audit_reports_all_statuses_and_samples(self):
        entries = [
            _entry("plain_text_line", {"line": 1}, patch_proof=_PROOF),
            _entry("raw_review_only", {"offset": 1, "length": 4}),
            _entry("unknown_method"),
            _entry("unity_typetree_field", {"path_id": "1"}),
        ]
        before = [dict(item) for item in entries]
        report = audit_entries(entries)
        self.assertEqual(report["entry_count"], 4)
        self.assertEqual(report["status_counts"][SUPPORTED_AND_PATCHABLE], 1)
        self.assertEqual(report["status_counts"][EXTRACT_ONLY], 1)
        self.assertEqual(report["status_counts"][UNSUPPORTED], 1)
        self.assertEqual(report["status_counts"][REVIEW_REQUIRED], 1)
        self.assertFalse(report["main_flow_safe"])
        self.assertEqual(len(report["samples"]), 3)
        self.assertEqual(entries, before)

    def test_write_package_opt_in_gate_preserves_legacy_default(self):
        proof = {
            "reader": True,
            "writer": True,
            "preflight": True,
            "reopen": True,
            "semantic_verify": True,
        }
        entry = Entry(
            source_text="Hello player",
            file_path="dialogue.txt",
            context="line:1",
            import_method="plain_text_line",
            locator={"line": 1},
            patch_proof=proof,
        ).finalize()
        with tempfile.TemporaryDirectory(prefix="vntext-symmetry-package-") as name:
            out = Path(name) / "strict"
            write_package(str(out), [entry], [], {"mode": "safe"}, True, enforce_symmetry=True)
            self.assertTrue((out / "translation.csv").is_file())
            manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["entries"][0]["patch_proof"], proof)

            legacy_out = Path(name) / "legacy"
            legacy_entry = Entry(
                source_text="Hello player",
                file_path="dialogue.txt",
                context="line:1",
                import_method="plain_text_line",
            ).finalize()
            write_package(str(legacy_out), [legacy_entry], [], {"mode": "safe"}, True)
            self.assertTrue((legacy_out / "translation.csv").is_file())

    def test_plain_text_roundtrip_proves_locator_writer_and_original_safety(self):
        proof = dict(_PROOF)
        with tempfile.TemporaryDirectory(prefix="vntext-symmetry-roundtrip-") as name:
            root = Path(name) / "game"
            package = Path(name) / "package"
            output = Path(name) / "patch"
            root.mkdir()
            source = root / "dialogue.txt"
            source.write_text("Hello player\nKeep this line\n", encoding="utf-8")
            entry = Entry(
                source_text="Hello player",
                file_path="dialogue.txt",
                context="line:0",
                import_method="plain_text_line",
                locator={"line": 0},
                patch_proof=proof,
            ).finalize()
            write_package(str(package), [entry], [], {"mode": "safe"}, True, enforce_symmetry=True)
            fields, rows = read_csv_rows_file(package / "translation.csv")
            rows[0]["translation"] = "Xin chào người chơi"
            write_csv_rows_file(package / "translation.csv", fields, rows)

            original_hash = hashlib.sha256(source.read_bytes()).hexdigest()
            result = apply_translation_package(
                str(package / "translation.csv"),
                str(package / "manifest.json"),
                str(root),
                str(output),
            )
            self.assertTrue(any("TEXT dialogue.txt: 1/1" in line for line in result), result)
            patched = output / "COPY_TO_GAME_ROOT" / "dialogue.txt"
            self.assertEqual(patched.read_text(encoding="utf-8"), "Xin chào người chơi\nKeep this line\n")
            self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(), original_hash)
            self.assertTrue((output / "backup_original" / "dialogue.txt").is_file())
            self.assertFalse(any(item.suffix.casefold() == ".bat" for item in output.iterdir()))
            self.assertTrue((output / "patch_manifest.json").is_file())
            self.assertTrue((output / "import_report.txt").is_file())

    def test_plain_text_duplicate_source_uses_each_line_locator(self):
        proof = dict(_PROOF)
        with tempfile.TemporaryDirectory(prefix="vntext-plain-duplicate-roundtrip-") as name:
            root = Path(name) / "game"
            package = Path(name) / "package"
            output = Path(name) / "patch"
            root.mkdir()
            source = root / "dialogue.txt"
            source.write_text("Hello player\nKeep this line\nHello player\n", encoding="utf-8", newline="")
            entry = Entry(
                source_text="Hello player",
                file_path="dialogue.txt",
                context="line:1",
                import_method="plain_text_line",
                locator={"line": 1},
                duplicate_locations=[{"line": 3}],
                patch_proof=proof,
            ).finalize()
            write_package(str(package), [entry], [], {"mode": "safe"}, True, enforce_symmetry=True)
            fields, rows = read_csv_rows_file(package / "translation.csv")
            rows[0]["translation"] = "Xin chào người chơi"
            write_csv_rows_file(package / "translation.csv", fields, rows)

            report = apply_translation_package(
                str(package / "translation.csv"),
                str(package / "manifest.json"),
                str(root),
                str(output),
            )
            self.assertTrue(any("TEXT dialogue.txt: 2/2" in line for line in report), report)
            patched = output / "COPY_TO_GAME_ROOT" / "dialogue.txt"
            self.assertEqual(
                patched.read_text(encoding="utf-8"),
                "Xin chào người chơi\nKeep this line\nXin chào người chơi\n",
            )

    def test_route_does_not_promote_structured_text_without_field_writer(self):
        from vntext.extract_text import extract_plain_text

        with tempfile.TemporaryDirectory(prefix="vntext-structured-review-") as name:
            root = Path(name)
            text_path = root / "dialogue.txt"
            json_path = root / "dialogue.json"
            text_path.write_text("Hello player\n", encoding="utf-8")
            json_path.write_text("Hello player\n", encoding="utf-8")
            text_entry = next(extract_plain_text(text_path, root))
            json_entry = next(extract_plain_text(json_path, root))
            self.assertTrue(text_entry.patch_proof)
            self.assertFalse(json_entry.patch_proof)

    def test_strict_package_does_not_auto_promote_raw_review_candidates(self):
        with tempfile.TemporaryDirectory(prefix="vntext-strict-raw-package-") as name:
            package = Path(name)
            raw = Entry(
                source_text="A complete raw candidate sentence.",
                file_path="Demo_Data/resources.assets",
                context="raw",
                import_method="naninovel_raw_candidate",
                review_only=True,
            ).finalize()
            write_package(
                str(package),
                [],
                [raw],
                {"mode": "strict"},
                True,
                enforce_symmetry=True,
            )
            _fields, main_rows = read_csv_rows_file(package / "translation.csv")
            _raw_fields, raw_rows = read_csv_rows_file(package / "raw_unpatchable.csv")
            self.assertEqual(main_rows, [])
            self.assertEqual([row["source_text"] for row in raw_rows], [raw.source_text])
            manifest = json.loads((package / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["stats"]["auto_raw_promoted"], 0)
            self.assertEqual(manifest["stats"]["raw_candidate_entries"], 0)
            self.assertEqual(manifest["stats"]["raw_unpatchable_entries"], 1)

    def test_source_resolution_fallback_is_generic_for_any_unity_data_root(self):
        with tempfile.TemporaryDirectory(prefix="vntext-generic-data-root-") as name:
            root = Path(name)
            data = root / "SampleVN_Data"
            data.mkdir()
            resource = data / "resources.assets"
            resource.write_bytes(b"fixture")
            resolved, rel = resolve_game_source_file(root, "resources.assets")
            self.assertEqual(resolved, resource)
            self.assertEqual(rel.replace("\\", "/"), "SampleVN_Data/resources.assets")

            nested = data / "StreamingAssets" / "dialogue.txt"
            nested.parent.mkdir()
            nested.write_text("Hello\n", encoding="utf-8")
            resolved_nested, rel_nested = resolve_game_source_file(root, "StreamingAssets/dialogue.txt")
            self.assertEqual(resolved_nested, nested)
            self.assertEqual(rel_nested.replace("\\", "/"), "SampleVN_Data/StreamingAssets/dialogue.txt")

            other = root / "OtherVN_Data"
            other.mkdir()
            (other / "resources.assets").write_bytes(b"other fixture")
            ambiguous, ambiguous_rel = resolve_game_source_file(root, "resources.assets")
            self.assertEqual(ambiguous, root / "resources.assets")
            self.assertEqual(ambiguous_rel.replace("\\", "/"), "resources.assets")


if __name__ == "__main__":
    unittest.main()
