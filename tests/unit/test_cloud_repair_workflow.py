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

from work_paths import work_temp_dir  # noqa: E402
from vntext.cloud_repair_import import import_cloud_repair_result  # noqa: E402
from vntext.cloud_repair_package import (  # noqa: E402
    MANIFEST_MEMBER,
    TRANSLATION_MEMBER,
    export_cloud_repair_package,
)
from vntext.entry import Entry  # noqa: E402
from vntext.package_io import (  # noqa: E402
    CSV_FIELDS,
    read_csv_rows_file,
    write_csv_rows_file,
    write_package,
)
from vntext.patch_gate import audit_patch_package  # noqa: E402


class CloudRepairWorkflowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.root = work_temp_dir("cloud-repair-workflow") / self._testMethodName
        self.root.mkdir(parents=True, exist_ok=True)
        self.package = self.root / "package"
        self.archive = self.root / "cloud-repair.zip"
        self.output = self.root / "merged.csv"
        self._build_package_fixture()
        self.export_report = export_cloud_repair_package(self.package, self.archive)
        self.reference_rows = self._zip_rows()

    def _build_package_fixture(self) -> None:
        entries = [
            Entry(
                source_text="Hello {NAME} <b>world</b>\\n",
                file_path="fixture/dialogue.txt",
                context="scene-1",
                object_info="line 1",
                import_method="plain_text_line",
                safety="safe",
                locator={"line": 1},
                backend="text",
                patch_proof={
                    "reader": True,
                    "writer": True,
                    "preflight": True,
                    "reopen": True,
                    "semantic_verify": True,
                },
            ).finalize(),
            Entry(
                source_text="Bye",
                file_path="fixture/dialogue.txt",
                context="scene-1",
                object_info="line 2",
                import_method="plain_text_line",
                safety="safe",
                locator={"line": 2},
                backend="text",
                patch_proof={
                    "reader": True,
                    "writer": True,
                    "preflight": True,
                    "reopen": True,
                    "semantic_verify": True,
                },
            ).finalize(),
            Entry(
                source_text="Value {iWillpower*5}",
                file_path="fixture/dialogue.txt",
                context="scene-1",
                object_info="line 3",
                import_method="plain_text_line",
                safety="safe",
                locator={"line": 3},
                backend="text",
                patch_proof={
                    "reader": True,
                    "writer": True,
                    "preflight": True,
                    "reopen": True,
                    "semantic_verify": True,
                },
            ).finalize(),
        ]
        write_package(
            str(self.package),
            entries,
            [],
            {
                "mode": "synthetic_cloud_repair",
                "files_scanned": 1,
                "main_entries": len(entries),
                "review_entries": 0,
                "errors": [],
            },
            enforce_symmetry=True,
        )
        fields, rows = read_csv_rows_file(self.package / TRANSLATION_MEMBER)
        self.assertEqual(fields, CSV_FIELDS)
        drafts = {
            entries[0].key: "Bản nháp {NAME} <b>thế giới</b>\\n",
            entries[1].key: "Tạm biệt",
            entries[2].key: "Giá trị {iWillpower*5}",
        }
        for row in rows:
            row["translation"] = drafts[row["key"]]
        write_csv_rows_file(self.package / TRANSLATION_MEMBER, CSV_FIELDS, rows)

    def _zip_rows(self) -> list[dict[str, str]]:
        with zipfile.ZipFile(self.archive) as archive:
            payload = archive.read(TRANSLATION_MEMBER).decode("utf-8-sig")
        reader = csv.DictReader(io.StringIO(payload, newline=""))
        self.assertEqual(reader.fieldnames, CSV_FIELDS)
        rows = [dict(row) for row in reader]
        self.assertEqual(len(rows), 3)
        return rows

    def _synthetic_cloud_consumer(self, changes: dict[str, str], name: str) -> Path:
        """Test-only consumer: read package translation.csv and change translations only."""

        result = self.root / name
        with zipfile.ZipFile(self.archive) as archive:
            payload = archive.read(TRANSLATION_MEMBER).decode("utf-8-sig")
        reader = csv.DictReader(io.StringIO(payload, newline=""))
        self.assertEqual(reader.fieldnames, CSV_FIELDS)
        rows = [dict(row) for row in reader]
        seen = set()
        for row in rows:
            if row["key"] in changes:
                row["translation"] = changes[row["key"]]
                seen.add(row["key"])
        self.assertEqual(seen, set(changes))
        write_csv_rows_file(result, CSV_FIELDS, rows)
        return result

    def _assert_rejected_without_output(self, result: Path, output_name: str) -> dict:
        output = self.root / output_name
        report = import_cloud_repair_result(self.archive, result, output)
        self.assertEqual(report["status"], "FAIL")
        self.assertFalse(report["merge_applied"])
        self.assertFalse(output.exists())
        self.assertFalse(list(output.parent.glob(f".{output.name}.*.tmp")))
        self.assertEqual(report["patch_verification"], "NOT_RUN")
        self.assertEqual(report["verification_scope"]["patch"], "NOT_RUN")
        return report

    def test_synthetic_cloud_repair_runs_export_import_and_patch_gate(self):
        self.assertEqual(self.export_report["status"], "PASS")
        self.assertEqual(self.export_report["row_count"], len(self.reference_rows))
        with zipfile.ZipFile(self.archive) as archive:
            manifest = json.loads(archive.read(MANIFEST_MEMBER))
            reference_bytes = archive.read(TRANSLATION_MEMBER)
        self.assertEqual(
            self.export_report["package_identity_sha256"],
            manifest["identity"]["contract_sha256"],
        )
        self.assertEqual(
            self.export_report["translation_csv_sha256"],
            hashlib.sha256(reference_bytes).hexdigest(),
        )

        result = self._synthetic_cloud_consumer(
            {
                self.reference_rows[0]["key"]: "Xin chào {NAME} <b>thế giới</b>\\n",
                self.reference_rows[2]["key"]: "Giá trị {iWillpower*5}!",
            },
            "cloud-final.csv",
        )
        report = import_cloud_repair_result(self.archive, result, self.output)
        self.assertEqual(report["status"], "PASS")
        self.assertTrue(report["merge_applied"])
        self.assertEqual(report["changed_count"], 2)
        self.assertEqual(report["reference_package_identity"], self.export_report["package_identity_sha256"])
        self.assertEqual(report["structural_failures"], [])

        fields, merged_rows = read_csv_rows_file(self.output)
        self.assertEqual(fields, CSV_FIELDS)
        self.assertEqual([row["key"] for row in merged_rows], [row["key"] for row in self.reference_rows])
        self.assertEqual(
            [row["source_text"] for row in merged_rows],
            [row["source_text"] for row in self.reference_rows],
        )
        expected_translations = {
            self.reference_rows[0]["key"]: "Xin chào {NAME} <b>thế giới</b>\\n",
            self.reference_rows[1]["key"]: self.reference_rows[1]["translation"],
            self.reference_rows[2]["key"]: "Giá trị {iWillpower*5}!",
        }
        for before, after in zip(self.reference_rows, merged_rows):
            for field in CSV_FIELDS:
                if field == "translation":
                    self.assertEqual(after[field], expected_translations[before["key"]])
                else:
                    self.assertEqual(after[field], before[field])

        gate = audit_patch_package(self.output, self.package / "manifest.json")
        self.assertTrue(gate["ok"], gate)
        self.assertEqual(gate["eligible"], len(self.reference_rows))
        self.assertEqual(gate["blocked"], 0)
        self.assertEqual(gate["translated_rows"], len(self.reference_rows))

    def test_negative_e2e_cases_fail_closed_before_patch_acceptance(self):
        cases = {}

        changed_source = [dict(row) for row in self.reference_rows]
        changed_source[0]["source_text"] = "Tampered source"
        cases["changed-source"] = (changed_source, "negative-changed-source.csv")

        missing_row = [dict(row) for row in self.reference_rows[:-1]]
        cases["missing-row"] = (missing_row, "negative-missing-row.csv")

        reordered_rows = [dict(row) for row in reversed(self.reference_rows)]
        cases["reordered-row"] = (reordered_rows, "negative-reordered-row.csv")

        broken_placeholder = [dict(row) for row in self.reference_rows]
        broken_placeholder[0]["translation"] = "Xin chào <b>thế giới</b>\\n"
        cases["broken-placeholder"] = (broken_placeholder, "negative-broken-placeholder.csv")

        changed_metadata = [dict(row) for row in self.reference_rows]
        changed_metadata[0]["context"] = "tampered-context"
        cases["changed-immutable-metadata"] = (changed_metadata, "negative-changed-metadata.csv")

        for name, (rows, result_name) in cases.items():
            with self.subTest(case=name):
                result = self.root / result_name
                write_csv_rows_file(result, CSV_FIELDS, rows)
                report = self._assert_rejected_without_output(result, f"{result_name}.out.csv")
                if name == "broken-placeholder":
                    self.assertTrue(report["structural_failures"])
                else:
                    self.assertTrue(report["errors"])


if __name__ == "__main__":
    unittest.main()
