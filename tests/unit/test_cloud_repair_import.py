from __future__ import annotations

import csv
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
from vntext.package_io import CSV_FIELDS  # noqa: E402
from vntext.patch_gate import audit_patch_package  # noqa: E402


class CloudRepairImportTests(unittest.TestCase):
    def setUp(self) -> None:
        self.root = work_temp_dir("cloud-repair-import") / self._testMethodName
        self.root.mkdir(parents=True, exist_ok=True)
        self.rows = [
            self._row("a", "Hello {NAME} <b>world</b>\\n", "Xin chào {NAME} <b>thế giới</b>\\n"),
            self._row("b", "Bye", "Tạm biệt"),
            self._row("c", "Value {iWillpower*5}", "Giá trị {iWillpower*5}"),
        ]
        self.package, self.archive = self._export()

    def _row(self, key: str, source: str, translation: str) -> dict[str, str]:
        return {
            "key": key,
            "source_text": source,
            "translation": translation,
            "context": "scene-1",
            "file_path": "dialogue.txt",
            "object_info": "line",
            "import_method": "plain_text_line",
            "safety": "safe",
            "backend": "text",
            "byte_limit": "",
            "patch_note": "Patch tự động",
        }

    def _write_csv(self, path: Path, rows: list[dict[str, str]], fields: list[str] | None = None) -> bytes:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields or CSV_FIELDS, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)
        return path.read_bytes()

    def _export(self) -> tuple[Path, Path]:
        package = self.root / "package"
        archive = self.root / "repair.zip"
        self._write_csv(package / TRANSLATION_MEMBER, self.rows)
        export_cloud_repair_package(package, archive)
        return package, archive

    def _result(self, name: str, rows: list[dict[str, str]] | None = None) -> Path:
        path = self.root / name
        self._write_csv(path, rows or self.rows)
        return path

    def _run(self, name: str, rows: list[dict[str, str]] | None = None, output_name: str = "merged.csv") -> dict:
        result_path = self._result(name, rows)
        return import_cloud_repair_result(self.archive, result_path, self.root / output_name)

    def _read_rows(self, path: Path) -> list[dict[str, str]]:
        with path.open(encoding="utf-8-sig", newline="") as handle:
            return list(csv.DictReader(handle))

    def _rewrite_zip(self, name: str, replacements: dict[str, bytes]) -> Path:
        target = self.root / name
        with zipfile.ZipFile(self.archive, "r") as source:
            members = {member: source.read(member) for member in source.namelist()}
        members.update(replacements)
        with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for member in sorted(members):
                archive.writestr(member, members[member])
        return target

    def _manifest_bytes(self, mutate) -> bytes:
        with zipfile.ZipFile(self.archive, "r") as archive:
            manifest = json.loads(archive.read(MANIFEST_MEMBER))
        mutate(manifest)
        return (json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")

    def test_changed_and_unchanged_results_merge_only_translation(self):
        changed = [dict(row) for row in self.rows]
        changed[0]["translation"] = "Xin {NAME} <b>thế giới</b>\\n"
        report = self._run("changed.csv", changed)
        self.assertEqual(report["status"], "PASS")
        self.assertTrue(report["merge_applied"])
        self.assertEqual(report["changed_count"], 1)
        merged = self._read_rows(self.root / "merged.csv")
        for before, after, cloud in zip(self.rows, merged, changed):
            for field in CSV_FIELDS:
                self.assertEqual(after[field], cloud[field] if field == "translation" else before[field])

        unchanged_report = self._run("unchanged.csv", self.rows, "unchanged.csv.out")
        self.assertEqual(unchanged_report["status"], "PASS")
        self.assertEqual(unchanged_report["changed_count"], 0)

    def test_valid_cloud_result_resolves_only_gate_valid_review_rows(self):
        review_row = dict(self.rows[0])
        review_row["translation"] = ""
        self._write_csv(self.package / TRANSLATION_MEMBER, [review_row])
        export_cloud_repair_package(self.package, self.archive)
        self._write_csv(self.package / "review_only.csv", [review_row])
        (self.package / "manifest.json").write_text(
            json.dumps({"entries": [{"key": review_row["key"], **review_row}]}),
            encoding="utf-8",
        )

        repaired = dict(review_row)
        repaired["translation"] = "Xin chào {NAME} <b>thế giới</b>\\n"
        result = self._result("review-repaired.csv", [repaired])
        output = self.package / "translation.cloud_repair.csv"
        report = import_cloud_repair_result(self.archive, result, output)

        self.assertEqual(report["status"], "PASS")
        self.assertEqual(report["review_pruned"], 1)
        self.assertEqual(self._read_rows(self.package / "review_only.csv"), [])
        gate = audit_patch_package(output, self.package / "manifest.json")
        self.assertEqual(gate["blocked"], 0, gate)

    def test_cloud_result_that_fails_patch_quality_keeps_review_row(self):
        review_row = dict(self.rows[0])
        review_row["translation"] = ""
        self._write_csv(self.package / TRANSLATION_MEMBER, [review_row])
        export_cloud_repair_package(self.package, self.archive)
        self._write_csv(self.package / "review_only.csv", [review_row])
        (self.package / "manifest.json").write_text(
            json.dumps({"entries": [{"key": review_row["key"], **review_row}]}),
            encoding="utf-8",
        )

        weak = dict(review_row)
        weak["translation"] = "bởi bởi bởi bởi bởi {NAME} <b>thế giới</b>\\n"
        result = self._result("review-weak.csv", [weak])
        report = import_cloud_repair_result(self.archive, result, self.package / "translation.cloud_repair.csv")

        self.assertEqual(report["status"], "PASS")
        self.assertEqual(report["review_pruned"], 0)
        self.assertEqual({row["key"] for row in self._read_rows(self.package / "review_only.csv")}, {"a"})

    def test_cloud_result_can_resolve_ct2_specific_false_positive(self):
        review_row = self._row("money", "But money is money!", "")
        self._write_csv(self.package / TRANSLATION_MEMBER, [review_row])
        export_cloud_repair_package(self.package, self.archive)
        self._write_csv(self.package / "review_only.csv", [review_row])
        (self.package / "manifest.json").write_text(
            json.dumps({"entries": [{"key": review_row["key"], **review_row}]}),
            encoding="utf-8",
        )

        repaired = dict(review_row)
        repaired["translation"] = "Nhưng tiền vẫn là tiền!"
        report = import_cloud_repair_result(
            self.archive,
            self._result("review-money.csv", [repaired]),
            self.package / "translation.cloud_repair.csv",
        )

        self.assertEqual(report["status"], "PASS")
        self.assertEqual(report["review_pruned"], 1)
        self.assertEqual(self._read_rows(self.package / "review_only.csv"), [])

    def test_manifest_hash_inventory_and_reference_identity_fail_closed(self):
        mutations = {
            "manifest": lambda doc: doc["source_identity"].update({"row_count": 99}),
            "inventory": lambda doc: doc["file_inventory"][0].update({"sha256": "0" * 64}),
            "identity": lambda doc: doc["source_identity"].update({"ordered_key_source_sha256": "0" * 64}),
        }
        for name, mutate in mutations.items():
            with self.subTest(name=name):
                archive = self._rewrite_zip(
                    f"bad-{name}.zip",
                    {MANIFEST_MEMBER: self._manifest_bytes(mutate)},
                )
                result = self._result(f"{name}.csv")
                output = self.root / f"{name}-merged.csv"
                report = import_cloud_repair_result(archive, result, output)
                self.assertEqual(report["status"], "FAIL")
                self.assertFalse(report["merge_applied"])
                self.assertFalse(output.exists())

    def test_schema_malformed_and_row_shape_fail_closed(self):
        schema_cases = {
            "removed": CSV_FIELDS[:-1],
            "added": CSV_FIELDS + ["extra"],
            "renamed": ["renamed" if field == "key" else field for field in CSV_FIELDS],
            "reordered": [CSV_FIELDS[1], CSV_FIELDS[0], *CSV_FIELDS[2:]],
        }
        for name, fields in schema_cases.items():
            with self.subTest(schema=name):
                result = self.root / f"schema-{name}.csv"
                self._write_csv(result, self.rows, fields)
                report = import_cloud_repair_result(self.archive, result, self.root / f"schema-{name}.out.csv")
                self.assertEqual(report["status"], "FAIL")
                self.assertFalse(report["merge_applied"])

        malformed = self.root / "malformed.csv"
        malformed.write_bytes(b"\xef\xbb\xbf" + (",".join(CSV_FIELDS) + "\n\"unterminated").encode("utf-8"))
        report = import_cloud_repair_result(self.archive, malformed, self.root / "malformed.out.csv")
        self.assertEqual(report["status"], "FAIL")

        row_cases = {
            "missing": self.rows[:-1],
            "extra": self.rows + [self._row("extra", "Extra", "Thêm")],
            "reordered": list(reversed(self.rows)),
            "duplicate": self.rows[:2] + [dict(self.rows[0])],
        }
        for name, rows in row_cases.items():
            with self.subTest(rows=name):
                report = self._run(f"rows-{name}.csv", rows, f"rows-{name}.out.csv")
                self.assertEqual(report["status"], "FAIL")
                self.assertFalse(report["merge_applied"])

    def test_key_source_and_every_immutable_field_are_rejected(self):
        for field in [field for field in CSV_FIELDS if field != "translation"]:
            with self.subTest(field=field):
                rows = [dict(row) for row in self.rows]
                rows[0][field] = f"changed-{field}"
                report = self._run(f"immutable-{field}.csv", rows, f"immutable-{field}.out.csv")
                self.assertEqual(report["status"], "FAIL")
                self.assertFalse(report["merge_applied"])
                self.assertTrue(any(field in error for error in report["errors"]))

    def test_structural_corruption_and_blank_translation_fail_via_canonical_gate(self):
        bad_translations = {
            "placeholder": "Xin NAME <b>thế giới</b>\\n",
            "tag": "Xin chào {NAME} thế giới\\n",
            "code": "Giá trị iWillpower",
            "literal-newline": "Xin chào {NAME} <b>thế giới</b>\n",
            "blank": "",
        }
        for name, translation in bad_translations.items():
            with self.subTest(kind=name):
                rows = [dict(row) for row in self.rows]
                rows[2 if name == "code" else 0]["translation"] = translation
                report = self._run(f"structural-{name}.csv", rows, f"structural-{name}.out.csv")
                self.assertEqual(report["status"], "FAIL")
                self.assertFalse(report["merge_applied"])
                self.assertTrue(report["structural_failures"])

    def test_one_bad_row_does_not_mutate_existing_output(self):
        output = self.root / "existing-output.csv"
        output.write_bytes(b"keep this file unchanged")
        rows = [dict(row) for row in self.rows]
        rows[1]["translation"] = ""
        before = output.read_bytes()
        report = self._run("one-bad-row.csv", rows, output.name)
        self.assertEqual(report["status"], "FAIL")
        self.assertFalse(report["merge_applied"])
        self.assertEqual(output.read_bytes(), before)

    def test_output_collision_is_rejected_and_scope_stays_nonsemantic(self):
        result = self._result("collision-result.csv")
        before_result = result.read_bytes()
        report = import_cloud_repair_result(self.archive, result, result)
        self.assertEqual(report["status"], "FAIL")
        self.assertFalse(report["merge_applied"])
        self.assertEqual(result.read_bytes(), before_result)

        report = import_cloud_repair_result(self.archive, result, self.archive)
        self.assertEqual(report["status"], "FAIL")
        self.assertFalse(report["merge_applied"])

        valid = self._run("scope.csv", self.rows, "scope-output.csv")
        self.assertEqual(valid["verification_scope"], {"semantic": "NOT_RUN", "e2e": "NOT_RUN", "patch": "NOT_RUN"})
        self.assertEqual(valid["semantic_verification"], "NOT_RUN")
        self.assertEqual(valid["e2e_verification"], "NOT_RUN")
        self.assertEqual(valid["patch_verification"], "NOT_RUN")
        self.assertNotIn("semantic PASS", str(valid).lower())
        self.assertNotIn("patch PASS", str(valid).lower())


if __name__ == "__main__":
    unittest.main()
