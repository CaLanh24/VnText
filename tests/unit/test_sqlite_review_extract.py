"""Bounded SQLite discovery stays visible without entering the patch flow."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from vntext.extract_pipeline import extract_project
from vntext.extract_sqlite import extract_sqlite_text_candidates, patch_structured_sqlite
from vntext.package_io import read_csv_rows_file, write_csv_rows_file, write_package
from vntext.patch import apply_translation_package


class SQLiteReviewExtractionTests(unittest.TestCase):
    def _make_database(self, root: Path) -> Path:
        path = root / "Demo_Data" / "StreamingAssets" / "localization.db"
        path.parent.mkdir(parents=True)
        connection = sqlite3.connect(path)
        try:
            connection.execute(
                "CREATE TABLE dialogue (id INTEGER PRIMARY KEY, text TEXT, note VARCHAR(64), count INTEGER)"
            )
            connection.executemany(
                "INSERT INTO dialogue(id, text, note, count) VALUES (?, ?, ?, ?)",
                [
                    (1, "Hello from SQLite", "Internal note", 3),
                    (2, "Goodbye from SQLite", "", 4),
                ],
            )
            connection.execute("CREATE TABLE dynamic (key, value)")
            connection.execute(
                "INSERT INTO dynamic(key, value) VALUES (?, ?)",
                ("dialogue_key", "A value without a declared type"),
            )
            connection.commit()
        finally:
            connection.close()
        return path

    def test_scanner_is_bounded_review_only_and_does_not_mutate_database(self):
        with tempfile.TemporaryDirectory(prefix="vntext-sqlite-review-") as name:
            root = Path(name) / "game"
            database = self._make_database(root)
            before = hashlib.sha256(database.read_bytes()).hexdigest()

            entries = list(extract_sqlite_text_candidates(database, root))

            self.assertEqual(
                {entry.source_text for entry in entries},
                {
                    "Hello from SQLite",
                    "Internal note",
                    "Goodbye from SQLite",
                    "dialogue_key",
                    "A value without a declared type",
                },
            )
            main = [entry for entry in entries if not entry.review_only]
            review = [entry for entry in entries if entry.review_only]
            self.assertEqual({entry.source_text for entry in main}, {"Hello from SQLite", "Goodbye from SQLite"})
            self.assertEqual(len(review), 3)
            self.assertTrue(all(entry.import_method == "structured_sqlite_value" for entry in main))
            self.assertTrue(all(entry.backend == "structured_sqlite" for entry in main))
            self.assertTrue(all(all(entry.patch_proof.values()) for entry in main))
            self.assertTrue(all(entry.import_method == "sqlite_text_candidate" for entry in review))
            self.assertTrue(all(entry.backend == "sqlite_inventory" for entry in review))
            self.assertTrue(all(not entry.patch_proof for entry in review))
            self.assertTrue(
                all(
                    set(entry.locator) >= {"table", "column", "row_index", "declared_type"}
                    for entry in entries
                )
            )
            self.assertEqual(hashlib.sha256(database.read_bytes()).hexdigest(), before)
            self.assertFalse(list(root.rglob("localization.db-*")))

    def test_pipeline_routes_sqlite_candidates_to_review_in_safe_and_deep_modes(self):
        with tempfile.TemporaryDirectory(prefix="vntext-sqlite-pipeline-") as name:
            root = Path(name) / "game"
            self._make_database(root)
            for mode in ("safe", "deep"):
                main, review, stats = extract_project(str(root), mode)

                self.assertEqual(len(main), 2)
                self.assertEqual(stats["files_scanned"], 1)
                self.assertEqual(stats["sqlite_inventory_files"], 1)
                self.assertEqual(stats["sqlite_review_entries"], 5)
                self.assertEqual(len(review), 3)
                self.assertEqual(
                    stats["method_counts"],
                    {"structured_sqlite_value": 2, "sqlite_text_candidate": 3},
                )
                self.assertTrue(
                    all(item["step"] != "raw_scan" for item in stats["file_timings"])
                )

    def test_pipeline_error_is_explicit_and_never_falls_back_to_raw_scan(self):
        with tempfile.TemporaryDirectory(prefix="vntext-sqlite-invalid-") as name:
            root = Path(name) / "game"
            database = root / "Demo_Data" / "broken.db"
            database.parent.mkdir(parents=True)
            database.write_bytes(b"SQLite format 3\x00not a complete database")

            main, review, stats = extract_project(str(root), "deep")

            self.assertFalse(main)
            self.assertFalse(review)
            self.assertEqual(stats["files_scanned"], 1)
            self.assertEqual(stats["sqlite_inventory_files"], 1)
            self.assertEqual(stats["sqlite_review_entries"], 0)
            self.assertTrue(any("sqlite_inventory" in error for error in stats["errors"]))
            self.assertTrue(all(item["step"] != "raw_scan" for item in stats["file_timings"]))

    def test_package_keeps_sqlite_candidates_in_review_only_csv(self):
        with tempfile.TemporaryDirectory(prefix="vntext-sqlite-package-") as name:
            root = Path(name) / "game"
            package = Path(name) / "package"
            self._make_database(root)

            main, review, stats = extract_project(str(root), "safe")
            write_package(str(package), main, review, stats, True, enforce_symmetry=True)

            _fields, translation_rows = read_csv_rows_file(package / "translation.csv")
            _review_fields, review_rows = read_csv_rows_file(package / "review_only.csv")
            self.assertEqual(len(translation_rows), 2)
            # Technical key-like values remain observable in the package's
            # dedicated technical ledger; only player-copy candidates stay in
            # review_only.csv.
            self.assertEqual(len(review_rows), 2)
            self.assertTrue((package / "technical_skipped.csv").is_file())
            self.assertEqual(json.loads((package / "manifest.json").read_text(encoding="utf-8"))["stats"]["technical_skipped_entries"], 1)
            self.assertTrue(all(row["import_method"] == "sqlite_text_candidate" for row in review_rows))
            self.assertTrue(all(row["translation"] == "" for row in review_rows))

    def test_safe_sqlite_writer_roundtrips_and_preserves_source(self):
        with tempfile.TemporaryDirectory(prefix="vntext-sqlite-roundtrip-") as name:
            root = Path(name) / "game"
            database = self._make_database(root)
            target = Path(name) / "patch" / "localization.db"
            before = hashlib.sha256(database.read_bytes()).hexdigest()
            entries = [entry for entry in extract_sqlite_text_candidates(database, root) if not entry.review_only]

            changed, skipped = patch_structured_sqlite(
                database,
                target,
                [
                    (entries[0].to_manifest(), "Xin chào từ SQLite"),
                    (entries[1].to_manifest(), "Tạm biệt từ SQLite"),
                ],
            )

            self.assertEqual((changed, skipped), (2, 0))
            self.assertEqual(hashlib.sha256(database.read_bytes()).hexdigest(), before)
            connection = sqlite3.connect(target)
            try:
                self.assertEqual(
                    connection.execute("SELECT id, text, note FROM dialogue ORDER BY id").fetchall(),
                    [
                        (1, "Xin chào từ SQLite", "Internal note"),
                        (2, "Tạm biệt từ SQLite", ""),
                    ],
                )
            finally:
                connection.close()

    def test_safe_sqlite_writer_fails_closed_on_source_and_schema_drift(self):
        with tempfile.TemporaryDirectory(prefix="vntext-sqlite-drift-") as name:
            root = Path(name) / "game"
            database = self._make_database(root)
            target = Path(name) / "patch" / "localization.db"
            entry = next(entry for entry in extract_sqlite_text_candidates(database, root) if not entry.review_only)

            source_drift = entry.to_manifest()
            source_drift["source_text"] = "Changed outside package"
            changed, skipped = patch_structured_sqlite(
                database,
                target,
                [(source_drift, "Xin chào")],
            )
            self.assertEqual((changed, skipped), (0, 1))
            self.assertEqual(target.read_bytes(), database.read_bytes())

            schema_drift = entry.to_manifest()
            schema_drift["locator"] = dict(schema_drift["locator"], schema_fingerprint="drift")
            changed, skipped = patch_structured_sqlite(
                database,
                target,
                [(schema_drift, "Xin chào")],
            )
            self.assertEqual((changed, skipped), (0, 1))
            self.assertEqual(target.read_bytes(), database.read_bytes())

    def test_package_and_patch_pipeline_use_safe_sqlite_route(self):
        with tempfile.TemporaryDirectory(prefix="vntext-sqlite-e2e-") as name:
            root = Path(name) / "game"
            package = Path(name) / "package"
            output = Path(name) / "patch"
            self._make_database(root)

            main, review, stats = extract_project(str(root), "safe")
            write_package(str(package), main, review, stats, True, enforce_symmetry=True)
            fields, rows = read_csv_rows_file(package / "translation.csv")
            translations = {
                "Hello from SQLite": "Xin chào từ SQLite",
                "Goodbye from SQLite": "Tạm biệt từ SQLite",
            }
            for row in rows:
                row["translation"] = translations[row["source_text"]]
            write_csv_rows_file(package / "translation.csv", fields, rows)

            report = apply_translation_package(
                str(package / "translation.csv"),
                str(package / "manifest.json"),
                str(root),
                str(output),
            )

            self.assertTrue(any(line.startswith("SQLite ") and "2/2" in line for line in report))
            target = output / "COPY_TO_GAME_ROOT" / "Demo_Data" / "StreamingAssets" / "localization.db"
            connection = sqlite3.connect(target)
            try:
                self.assertEqual(
                    connection.execute("SELECT text FROM dialogue ORDER BY id").fetchall(),
                    [("Xin chào từ SQLite",), ("Tạm biệt từ SQLite",)],
                )
            finally:
                connection.close()


if __name__ == "__main__":
    unittest.main()
