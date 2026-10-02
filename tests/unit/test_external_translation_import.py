from __future__ import annotations

import csv
import sys
import unittest
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
from vntext.entry import Entry  # noqa: E402
from vntext.external_translation_import import import_existing_translations  # noqa: E402
from vntext.package_io import CSV_FIELDS, read_csv_rows_file, write_csv_rows_file, write_package  # noqa: E402


def _entry(source_text: str, context: str) -> Entry:
    return Entry(
        source_text=source_text,
        file_path="fixture/dialogue.txt",
        context=context,
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
    ).finalize()


class ExternalTranslationImportTests(unittest.TestCase):
    def setUp(self) -> None:
        self.root = work_temp_dir("external-translation-import") / self._testMethodName
        self.root.mkdir(parents=True, exist_ok=True)
        self.package = self.root / "current"
        self.entries = [
            _entry("Hello {NAME}", "valid"),
            _entry("Already translated", "existing"),
            _entry("Broken {NAME}", "broken"),
            _entry("Changed source", "mismatch"),
            _entry("Source-only must not match", "source-only"),
        ]
        write_package(
            str(self.package),
            self.entries,
            [],
            {"mode": "synthetic", "files_scanned": 1, "main_entries": 5, "review_entries": 0, "errors": []},
            enforce_symmetry=True,
        )
        self.target = self.package / "translation.csv"
        self.source = self.root / "older-translation.csv"
        _, rows = read_csv_rows_file(self.target)
        self.rows_by_context = {row["context"]: row for row in rows}
        self.rows_by_context["existing"]["translation"] = "Bản dịch đang dùng"
        write_csv_rows_file(self.target, CSV_FIELDS, rows)
        review_rows = [
            dict(self.rows_by_context[name])
            for name in ("valid", "broken", "mismatch", "source-only")
        ]
        for row in review_rows:
            row["translation"] = ""
        write_csv_rows_file(self.package / "review_only.csv", CSV_FIELDS, review_rows)

    def _write_older_rows(self) -> None:
        donor_rows = [dict(row) for row in self.rows_by_context.values()]
        by_context = {row["context"]: row for row in donor_rows}
        by_context["valid"]["translation"] = "Xin chào {NAME}"
        by_context["existing"]["translation"] = "Không được ghi đè"
        by_context["broken"]["translation"] = "Xin chào"
        by_context["mismatch"]["source_text"] = "Nguồn đã đổi"
        donor_rows = [row for row in donor_rows if row["context"] != "source-only"]
        source_only = dict(self.rows_by_context["source-only"])
        source_only["key"] = "other-key-with-same-source"
        source_only["translation"] = "Không được ghép theo source_text"
        donor_rows.append(source_only)
        write_csv_rows_file(self.source, CSV_FIELDS, donor_rows)

    def test_imports_only_exact_safe_rows_and_keeps_unresolved_rows(self) -> None:
        self._write_older_rows()
        donor_before = self.source.read_bytes()

        report = import_existing_translations(self.target, self.source)

        self.assertEqual(report["status"], "PASS", report)
        self.assertEqual(report["applied"], 1)
        self.assertEqual(report["review_pruned"], 1)
        self.assertEqual(report["review_only_remaining"], 3)
        self.assertEqual(report["untranslated_remaining"], 3)
        self.assertFalse(report["complete"])
        self.assertEqual(report["source_mismatch"], 1)
        self.assertEqual(report["source_missing"], 1)
        self.assertTrue(report["rejected"])
        self.assertEqual(donor_before, self.source.read_bytes())

        _, current_rows = read_csv_rows_file(self.target)
        current = {row["context"]: row for row in current_rows}
        self.assertEqual(current["valid"]["translation"], "Xin chào {NAME}")
        self.assertEqual(current["existing"]["translation"], "Bản dịch đang dùng")
        self.assertEqual(current["broken"]["translation"], "")
        self.assertEqual(current["mismatch"]["translation"], "")
        self.assertEqual(current["source-only"]["translation"], "")
        self.assertEqual(current["valid"]["source_text"], "Hello {NAME}")

    def test_duplicate_donor_key_fails_without_changing_current_package(self) -> None:
        row = dict(self.rows_by_context["valid"])
        row["translation"] = "Xin chào {NAME}"
        with self.source.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
            writer.writeheader()
            writer.writerow(row)
            writer.writerow(row)

        target_before = self.target.read_bytes()
        review_before = (self.package / "review_only.csv").read_bytes()
        report = import_existing_translations(self.target, self.source)

        self.assertEqual(report["status"], "FAIL")
        self.assertIn("trùng lặp", report["errors"][0])
        self.assertEqual(target_before, self.target.read_bytes())
        self.assertEqual(review_before, (self.package / "review_only.csv").read_bytes())

    def test_untranslated_rows_prevent_false_completion_without_review_ledger(self) -> None:
        (self.package / "review_only.csv").unlink()
        self._write_older_rows()

        report = import_existing_translations(self.target, self.source)

        self.assertEqual(report["status"], "PASS", report)
        self.assertEqual(report["review_only_remaining"], 0)
        self.assertEqual(report["untranslated_remaining"], 3)
        self.assertFalse(report["complete"])
