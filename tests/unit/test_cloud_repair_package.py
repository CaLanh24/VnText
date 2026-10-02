from __future__ import annotations

import csv
import hashlib
import io
import json
import sys
import unittest
import zipfile
from pathlib import Path


def _bootstrap() -> tuple[Path, Path, Path]:
    cur = Path(__file__).resolve().parent
    while cur.name != "tests" and cur.parent != cur:
        cur = cur.parent
    root = cur.parent
    lib = cur / "lib"
    for item in (root, lib):
        if str(item) not in sys.path:
            sys.path.insert(0, str(item))
    return cur, root, lib


TESTS, ROOT, LIB = _bootstrap()

from work_paths import WORK_ROOT, work_temp_dir  # noqa: E402
from vntext.cloud_repair_package import (  # noqa: E402
    CONSTRAINTS_MEMBER,
    CONTEXT_MEMBER,
    MANIFEST_MEMBER,
    TRANSLATION_MEMBER,
    CloudRepairPackageError,
    export_cloud_repair_package,
    validate_member_name,
)
from vntext.package_io import CSV_FIELDS  # noqa: E402


class CloudRepairPackageTests(unittest.TestCase):
    def setUp(self) -> None:
        self.root = work_temp_dir(f"cloud-repair-package-{self._testMethodName}")

    def _row(
        self,
        key: str,
        source: str,
        translation: str = "",
        *,
        file_path: str = "dialogue.txt",
        context: str = "scene-1",
        import_method: str = "plain_text_line",
    ) -> dict[str, str]:
        return {
            "key": key,
            "source_text": source,
            "translation": translation,
            "context": context,
            "file_path": file_path,
            "object_info": "line",
            "import_method": import_method,
            "safety": "safe",
            "backend": "text",
            "byte_limit": "",
            "patch_note": "Patch tự động",
        }

    def _write_csv(self, package: Path, rows: list[dict[str, str]], *, fields: list[str] | None = None) -> bytes:
        package.mkdir(parents=True, exist_ok=True)
        path = package / TRANSLATION_MEMBER
        with path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields or CSV_FIELDS)
            writer.writeheader()
            writer.writerows(rows)
        return path.read_bytes()

    def _export(self, rows: list[dict[str, str]]) -> tuple[Path, Path, dict]:
        package = self.root / "package"
        output = self.root / "cloud.zip"
        csv_bytes = self._write_csv(package, rows)
        report = export_cloud_repair_package(package, output)
        return package, output, {"csv_bytes": csv_bytes, "report": report}

    def test_happy_export_preserves_csv_schema_rows_keys_and_sources(self):
        rows = [
            self._row("a", "Hello <b>{NAME}</b>", "Xin chào <b>{NAME}</b>"),
            self._row("b", "Next line\\n", ""),
        ]
        package, output, state = self._export(rows)
        self.assertEqual(output.read_bytes()[:2], b"PK")
        with zipfile.ZipFile(output) as archive:
            exported = archive.read(TRANSLATION_MEMBER)
            manifest = json.loads(archive.read(MANIFEST_MEMBER))
        self.assertEqual(exported, state["csv_bytes"])
        parsed = list(csv.reader(io.StringIO(exported.decode("utf-8-sig"), newline="")))
        self.assertEqual(parsed[0], CSV_FIELDS)
        self.assertEqual([line[0] for line in parsed[1:]], ["a", "b"])
        self.assertEqual([line[1] for line in parsed[1:]], [row["source_text"] for row in rows])
        self.assertEqual(manifest["source_identity"]["row_count"], 2)
        self.assertEqual(manifest["allowed_mutations"], ["translation"])
        self.assertEqual(manifest["final_output_contract"]["fields"], CSV_FIELDS)
        self.assertEqual(manifest["final_output_contract"]["mutable_fields"], ["translation"])
        self.assertTrue(package.joinpath(TRANSLATION_MEMBER).is_file())

    def test_manifest_inventory_hashes_are_correct_and_sorted(self):
        _package, output, _state = self._export(
            [self._row("a", "Hello", "Xin chào"), self._row("b", "Bye", "Tạm biệt")]
        )
        with zipfile.ZipFile(output) as archive:
            names = archive.namelist()
            manifest = json.loads(archive.read(MANIFEST_MEMBER))
            inventory = manifest["file_inventory"]
            self.assertEqual(names, sorted(names))
            self.assertEqual(len(names), len(set(names)))
            self.assertNotIn("manifest.json", names)
            self.assertEqual([item["path"] for item in inventory], sorted(item["path"] for item in inventory))
            self.assertEqual(set(item["path"] for item in inventory), set(names) - {MANIFEST_MEMBER})
            for item in inventory:
                data = archive.read(item["path"])
                self.assertEqual(item["size"], len(data))
                self.assertEqual(item["sha256"], hashlib.sha256(data).hexdigest())
        self.assertEqual(manifest["identity"]["algorithm"], "SHA-256")
        self.assertEqual(manifest["identity"]["contract_sha256"], _identity_from_manifest(manifest))

    def test_repeated_exports_are_byte_deterministic(self):
        rows = [self._row("a", "Hello", "Xin chào"), self._row("b", "Bye")]
        package = self.root / "package"
        self._write_csv(package, rows)
        first = self.root / "first.zip"
        second = self.root / "second.zip"
        one = export_cloud_repair_package(package, first)
        two = export_cloud_repair_package(package, second)
        self.assertEqual(first.read_bytes(), second.read_bytes())
        self.assertEqual(one["package_identity_sha256"], two["package_identity_sha256"])
        self.assertEqual(one["zip_sha256"], two["zip_sha256"])
        self.assertIn("byte-reproducible", one["deterministic_guarantee"])

    def test_source_identity_excludes_mutable_translation_draft(self):
        package = self.root / "package"
        self._write_csv(package, [self._row("a", "Hello", "Draft one")])
        first = self.root / "first.zip"
        export_cloud_repair_package(package, first)
        with zipfile.ZipFile(first) as archive:
            first_manifest = json.loads(archive.read(MANIFEST_MEMBER))

        self._write_csv(package, [self._row("a", "Hello", "Draft two")])
        second = self.root / "second.zip"
        export_cloud_repair_package(package, second)
        with zipfile.ZipFile(second) as archive:
            second_manifest = json.loads(archive.read(MANIFEST_MEMBER))

        self.assertEqual(first_manifest["source_identity"]["sha256"], second_manifest["source_identity"]["sha256"])
        self.assertNotEqual(
            first_manifest["translation_csv"]["sha256"], second_manifest["translation_csv"]["sha256"]
        )
        self.assertNotEqual(
            first_manifest["identity"]["contract_sha256"], second_manifest["identity"]["contract_sha256"]
        )

    def test_context_is_bounded_mapped_to_rows_and_does_not_cross_boundaries(self):
        rows = [
            self._row("a", "A", "Draft A", file_path="one", context="scene-1"),
            self._row("b", "B", "", file_path="one", context="scene-1"),
            self._row("c", "C", "Draft C", file_path="two", context="scene-1"),
            self._row("d", "D", "", file_path="one", context="none"),
        ]
        _package, output, _state = self._export(rows)
        with zipfile.ZipFile(output) as archive:
            context = [json.loads(line) for line in archive.read(CONTEXT_MEMBER).decode("utf-8").splitlines()]
            constraints = [json.loads(line) for line in archive.read(CONSTRAINTS_MEMBER).decode("utf-8").splitlines()]
        by_key = {item["key"]: item for item in context}
        self.assertEqual(set(by_key), {"a", "b", "c", "d"})
        self.assertEqual(by_key["a"]["next"], [])
        self.assertEqual(by_key["a"]["draft"], "Draft A")
        self.assertEqual(by_key["c"]["previous"], [])
        self.assertEqual(by_key["d"]["status"], "insufficient_metadata")
        self.assertEqual({item["key"] for item in constraints}, {"a", "b", "c", "d"})
        a_constraints = next(item for item in constraints if item["key"] == "a")
        self.assertEqual(a_constraints["placeholders"]["count"], 0)
        self.assertEqual(a_constraints["literal_newline_count"], 0)

    def test_valid_optional_glossary_and_memory_are_included_and_missing_are_absent(self):
        package = self.root / "package"
        self._write_csv(package, [self._row("a", "Hello", "Xin chào")])
        (package / ".mt" / "v2").mkdir(parents=True)
        (package / ".mt" / "v2" / "glossary.json").write_text(
            json.dumps(
                {"schema_version": 1, "entries": [{"source": "Hello", "target": "Xin chào", "kind": "fixed_phrase"}]},
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        (package / ".mt" / "translation_memory.json").write_text(
            json.dumps(
                {
                    "version": "1.0.0",
                    "entries": [
                        {"source": "hello", "import_method": "plain_text_line", "context_family": "scene", "translation": "xin chào"}
                    ],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        (package / "manifest.json").write_text("{}", encoding="utf-8")
        output = self.root / "with-optional.zip"
        export_cloud_repair_package(package, output)
        with zipfile.ZipFile(output) as archive:
            names = set(archive.namelist())
            self.assertIn(".mt/v2/glossary.json", names)
            self.assertIn(".mt/translation_memory.json", names)
            self.assertNotIn("manifest.json", names)

        missing_package = self.root / "missing-optional"
        self._write_csv(missing_package, [self._row("a", "Hello")])
        missing_output = self.root / "without-optional.zip"
        export_cloud_repair_package(missing_package, missing_output)
        with zipfile.ZipFile(missing_output) as archive:
            names = set(archive.namelist())
            self.assertNotIn(".mt/glossary.json", names)
            self.assertNotIn(".mt/v2/glossary.json", names)
            self.assertNotIn(".mt/translation_memory.json", names)

    def test_blank_draft_is_supported(self):
        _package, output, _state = self._export([self._row("a", "Only source")])
        with zipfile.ZipFile(output) as archive:
            manifest = json.loads(archive.read(MANIFEST_MEMBER))
            context = json.loads(archive.read(CONTEXT_MEMBER).decode("utf-8"))
        self.assertFalse(manifest["draft"]["draft_present"])
        self.assertIsNone(manifest["draft"]["draft_engine"])
        self.assertEqual(context["draft"], "")

    def test_malformed_missing_and_invalid_optional_inputs_fail_closed(self):
        missing = self.root / "missing"
        with self.assertRaises(CloudRepairPackageError):
            export_cloud_repair_package(missing, self.root / "missing.zip")

        package = self.root / "package"
        package.mkdir()
        with self.assertRaises(CloudRepairPackageError):
            export_cloud_repair_package(package, self.root / "no-csv.zip")

        (package / TRANSLATION_MEMBER).write_text("key,source_text\na,b\n", encoding="utf-8")
        with self.assertRaises(CloudRepairPackageError):
            export_cloud_repair_package(package, self.root / "bad-schema.zip")

        (package / TRANSLATION_MEMBER).write_text(
            "\ufeff" + ",".join(CSV_FIELDS) + "\n", encoding="utf-8"
        )
        with self.assertRaises(CloudRepairPackageError):
            export_cloud_repair_package(package, self.root / "empty.zip")

        self._write_csv(package, [self._row("same", "A"), self._row("same", "B")])
        with self.assertRaises(CloudRepairPackageError):
            export_cloud_repair_package(package, self.root / "duplicate.zip")

        self._write_csv(package, [self._row("a", "A")])
        (package / ".mt" / "v2").mkdir(parents=True)
        (package / ".mt" / "v2" / "glossary.json").write_text("not-json", encoding="utf-8")
        with self.assertRaises(CloudRepairPackageError):
            export_cloud_repair_package(package, self.root / "bad-optional.zip")

    def test_zip_has_only_safe_allowlisted_unique_members(self):
        _package, output, _state = self._export([self._row("a", "Hello")])
        with zipfile.ZipFile(output) as archive:
            names = archive.namelist()
        allowed = {TRANSLATION_MEMBER, MANIFEST_MEMBER, CONTEXT_MEMBER, CONSTRAINTS_MEMBER}
        self.assertEqual(set(names), allowed)
        self.assertEqual(len(names), len(set(names)))
        for name in names:
            self.assertEqual(validate_member_name(name), name)
        for unsafe in ("../escape", "/absolute", "a\\b", "C:drive", "a//b", "a/../b"):
            with self.subTest(unsafe=unsafe), self.assertRaises(CloudRepairPackageError):
                validate_member_name(unsafe)

    def test_generated_artifacts_are_registered_under_work_scope(self):
        package, output, state = self._export([self._row("a", "Hello")])
        self.assertTrue(output.is_file())
        self.assertTrue(str(output.resolve()).startswith(str(WORK_ROOT.resolve())))
        self.assertTrue(str(package.resolve()).startswith(str(WORK_ROOT.resolve())))
        self.assertEqual(state["report"]["status"], "PASS")


def _identity_from_manifest(manifest: dict) -> str:
    material = {
        "schema": manifest["schema"],
        "version": manifest["version"],
        "kind": manifest["kind"],
        "source_identity": manifest["source_identity"],
        "file_inventory": manifest["file_inventory"],
        "allowed_mutations": manifest["allowed_mutations"],
        "immutable_fields": manifest["immutable_fields"],
        "draft": manifest["draft"],
    }
    return hashlib.sha256(
        json.dumps(material, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8", "surrogatepass")
    ).hexdigest()


if __name__ == "__main__":
    unittest.main()
