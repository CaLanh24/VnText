"""Contract tests for strict local-translation completion status."""

from __future__ import annotations

import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path


def _tests_lib_on_path() -> None:
    current = Path(__file__).resolve()
    while current.name != "tests" and current.parent != current:
        current = current.parent
    value = str(current / "lib")
    if value not in sys.path:
        sys.path.insert(0, value)


_tests_lib_on_path()
from bootstrap import bootstrap  # noqa: E402

TESTS, ROOT, LIB = bootstrap(__file__)

from vntext.mt_ct2_status import (  # noqa: E402
    TranslateStatusError,
    _build_translate_result,
    snapshot_translate_status,
    write_translate_status,
)


class MtCt2StatusTests(unittest.TestCase):
    def test_final_blocked_rows_keep_completion_false(self):
        with tempfile.TemporaryDirectory(prefix="vntext-ct2-status-") as name:
            result = _build_translate_result(
                Path(name),
                [{"source_text": "Hello", "translation": "Xin chào"}],
                applied=1,
                copied_vi=0,
                skipped_technical=0,
                blocked=1,
                summary="one row remains blocked",
                pipeline_liveness=True,
            )

        self.assertTrue(result["ok"], result)
        self.assertFalse(result["complete"], result)
        self.assertEqual(result["blocked"], 1)

    def test_zero_final_blocked_rows_can_complete(self):
        with tempfile.TemporaryDirectory(prefix="vntext-ct2-status-") as name:
            result = _build_translate_result(
                Path(name),
                [{"source_text": "Hello", "translation": "Xin chào"}],
                applied=1,
                copied_vi=0,
                skipped_technical=0,
                blocked=0,
                summary="complete",
                pipeline_liveness=True,
            )

        self.assertTrue(result["ok"], result)
        self.assertTrue(result["complete"], result)
        self.assertEqual(result["blocked"], 0)

    def test_unresolved_synonym_counts_as_pending(self):
        with tempfile.TemporaryDirectory(prefix="vntext-ct2-status-") as name:
            result = _build_translate_result(
                Path(name),
                [{"source_text": "one,two", "translation": "", "file_path": "_synonyms.txt"}],
                applied=0,
                copied_vi=0,
                skipped_technical=0,
                blocked=0,
                summary="synonym remains unresolved",
                pipeline_liveness=True,
            )

        self.assertFalse(result["complete"], result)
        self.assertEqual(result["pending"], 1)

    def test_review_and_unsupported_rows_are_pending_not_complete(self):
        with tempfile.TemporaryDirectory(prefix="vntext-ct2-status-classifier-") as name:
            result = _build_translate_result(
                Path(name),
                [
                    {"source_text": "Visible review", "translation": "", "review_only": True},
                    {"source_text": "Visible raw", "translation": "", "import_method": "naninovel_raw_candidate"},
                ],
                applied=0,
                copied_vi=0,
                skipped_technical=0,
                blocked=0,
                summary="classifier boundary remains unresolved",
                pipeline_liveness=True,
            )
        self.assertFalse(result["complete"], result)
        self.assertEqual(result["pending"], 2)
        self.assertEqual(result["classifier_review"], 1)
        self.assertEqual(result["classifier_unsupported"], 1)

    def test_status_writer_cannot_promote_blocked_or_synonym_rows(self):
        with tempfile.TemporaryDirectory(prefix="vntext-ct2-status-") as name:
            package = Path(name)
            csv_path = package / "translation.csv"
            with csv_path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=["key", "source_text", "translation", "file_path", "context"],
                )
                writer.writeheader()
                writer.writerow({
                    "key": "k1",
                    "source_text": "one,two",
                    "translation": "",
                    "file_path": "_synonyms.txt",
                })

            status = write_translate_status(
                package,
                csv_path,
                complete=True,
                pending=0,
                review_only=0,
                blocked=2,
            )

            self.assertFalse(status["complete"], status)
            self.assertEqual(status["pending"], 1)
            self.assertEqual(status["blocked"], 2)
            on_disk = snapshot_translate_status(package, csv_path)
            self.assertFalse(on_disk["complete"], on_disk)
            self.assertEqual(on_disk["pending"], 1)
            self.assertEqual(on_disk["blocked"], 2)

            with csv_path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=["key", "source_text", "translation", "file_path", "context"],
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "key": "k1",
                        "source_text": "one,two",
                        "translation": "Đã dịch",
                        "file_path": "_synonyms.txt",
                    }
                )
            cleared = write_translate_status(
                package,
                csv_path,
                complete=True,
                pending=0,
                review_only=0,
                blocked=0,
                package_wide_verified=True,
            )
            self.assertTrue(cleared["complete"], cleared)
            self.assertEqual(snapshot_translate_status(package, csv_path)["blocked"], 0)

    def test_persisted_blocked_requires_package_wide_proof_to_clear(self):
        with tempfile.TemporaryDirectory(prefix="vntext-ct2-status-blocked-") as name:
            package = Path(name)
            csv_path = package / "translation.csv"
            with csv_path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=["key", "source_text", "translation", "file_path", "context"],
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "key": "k1",
                        "source_text": "Hello",
                        "translation": "Xin chào",
                        "file_path": "x.txt",
                    }
                )

            first = write_translate_status(package, csv_path, blocked=1)
            self.assertEqual(first["blocked"], 1)
            retained = write_translate_status(package, csv_path, blocked=0)
            self.assertFalse(retained["complete"], retained)
            self.assertEqual(retained["blocked"], 1)
            cleared = write_translate_status(
                package,
                csv_path,
                blocked=0,
                package_wide_verified=True,
            )
            self.assertTrue(cleared["complete"], cleared)
            self.assertEqual(cleared["blocked"], 0)

    def test_writer_revalidates_measured_status_against_canonical_package(self):
        with tempfile.TemporaryDirectory(prefix="vntext-ct2-status-measured-") as name:
            package = Path(name)
            csv_path = package / "translation.csv"
            with csv_path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=["key", "source_text", "translation", "file_path", "context"],
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "key": "pending",
                        "source_text": "one,two",
                        "translation": "",
                        "file_path": "_synonyms.txt",
                    }
                )
            fake = {
                "complete": True,
                "pending": 0,
                "review_only": 0,
                "blocked": 0,
                "translated": 1,
            }
            with self.assertRaisesRegex(TranslateStatusError, "không khớp"):
                write_translate_status(package, csv_path, measured_status=fake)

    def test_negative_or_malformed_persisted_counts_fail_closed(self):
        fields = ["key", "source_text", "translation", "file_path", "context"]
        for field, value in (("pending", -1), ("review_only", -1), ("blocked", -1)):
            with self.subTest(field=field):
                with tempfile.TemporaryDirectory(prefix="vntext-ct2-status-invalid-") as name:
                    package = Path(name)
                    csv_path = package / "translation.csv"
                    with csv_path.open("w", encoding="utf-8", newline="") as handle:
                        writer = csv.DictWriter(handle, fieldnames=fields)
                        writer.writeheader()
                        writer.writerow({"key": "k", "source_text": "Hello", "translation": "Xin chào"})
                    status_path = package / ".mt" / "translate_status.json"
                    status_path.parent.mkdir(parents=True)
                    status_path.write_text(
                        json.dumps({"pending": 0, "review_only": 0, "blocked": 0, "complete": True} | {field: value}),
                        encoding="utf-8",
                    )
                    with self.assertRaisesRegex(TranslateStatusError, rf"{field} âm"):
                        snapshot_translate_status(package, csv_path)

        with tempfile.TemporaryDirectory(prefix="vntext-ct2-status-invalid-type-") as name:
            package = Path(name)
            csv_path = package / "translation.csv"
            with csv_path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=fields)
                writer.writeheader()
                writer.writerow({"key": "k", "source_text": "Hello", "translation": "Xin chào"})
            status_path = package / ".mt" / "translate_status.json"
            status_path.parent.mkdir(parents=True)
            status_path.write_text(
                '{"pending": 0, "review_only": "bad", "blocked": 0, "complete": true}',
                encoding="utf-8",
            )
            with self.assertRaisesRegex(TranslateStatusError, "review_only không hợp lệ"):
                snapshot_translate_status(package, csv_path)

        with tempfile.TemporaryDirectory(prefix="vntext-ct2-status-missing-field-") as name:
            package = Path(name)
            csv_path = package / "translation.csv"
            with csv_path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=fields)
                writer.writeheader()
                writer.writerow({"key": "k", "source_text": "Hello", "translation": "Xin chào"})
            status_path = package / ".mt" / "translate_status.json"
            status_path.parent.mkdir(parents=True)
            status_path.write_text(
                '{"pending": 0, "blocked": 0, "complete": true}',
                encoding="utf-8",
            )
            with self.assertRaisesRegex(TranslateStatusError, "thiếu trường review_only"):
                snapshot_translate_status(package, csv_path)

    def test_malformed_persisted_status_fails_closed(self):
        with tempfile.TemporaryDirectory(prefix="vntext-ct2-status-corrupt-") as name:
            package = Path(name)
            csv_path = package / "translation.csv"
            with csv_path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=["key", "source_text", "translation", "file_path", "context"],
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "key": "k1",
                        "source_text": "Hello",
                        "translation": "Xin chào",
                        "file_path": "x.txt",
                    }
                )
            status_path = package / ".mt" / "translate_status.json"
            status_path.parent.mkdir(parents=True)
            status_path.write_text('{"blocked":', encoding="utf-8")

            with self.assertRaisesRegex(TranslateStatusError, "Không đọc được trạng thái package"):
                snapshot_translate_status(package, csv_path)

    def test_translation_result_rejects_invalid_blocked_count(self):
        with tempfile.TemporaryDirectory(prefix="vntext-ct2-result-invalid-") as name:
            package = Path(name)
            rows = [{"source_text": "Hello", "translation": "Xin chào"}]
            with self.assertRaisesRegex(TranslateStatusError, "blocked âm"):
                _build_translate_result(
                    package,
                    rows,
                    applied=1,
                    copied_vi=0,
                    skipped_technical=0,
                    blocked=-1,
                    summary="invalid",
                )
            with self.assertRaisesRegex(TranslateStatusError, "blocked không hợp lệ"):
                _build_translate_result(
                    package,
                    rows,
                    applied=1,
                    copied_vi=0,
                    skipped_technical=0,
                    blocked="bad",
                    summary="invalid",
                )


if __name__ == "__main__":
    unittest.main()
