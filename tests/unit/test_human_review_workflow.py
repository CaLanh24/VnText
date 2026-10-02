"""Regression coverage for the explicit human-review translation route."""

from __future__ import annotations

import json
import sqlite3
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


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

from work_paths import work_temp_dir  # noqa: E402
from vntext.csv_editor_api import save_document  # noqa: E402
from vntext.mt_ct2_pipeline import run_ct2_translate, run_ct2_translate_keys  # noqa: E402
from vntext.mt_ct2_status import snapshot_translate_status  # noqa: E402
from vntext.package_io import CSV_FIELDS, read_csv_rows_file, write_csv_rows_file  # noqa: E402
from vntext.app_tasks import run_translate_ct2_task  # noqa: E402
from vntext_worker.task_runners import run_translate_worker  # noqa: E402


class FakeReviewAdapter:
    config = {"batch_size": 4, "inter_threads": 1, "max_src_tokens": 512}
    model_path = "fixture-review-model"
    revision = "fixture-review-v1"

    def metadata(self) -> dict:
        return {
            "adapter_id": "fake-review-adapter",
            "model_engine": "Fake/Review",
            "model_revision": self.revision,
        }

    def translate_many(self, texts: list[str]) -> list[str]:
        outputs: list[str] = []
        for text in texts:
            stripped = text.strip()
            if stripped == "Hello":
                outputs.append("Xin chào")
            elif stripped == "world":
                outputs.append("thế giới")
            else:
                outputs.append("Xin chào")
        return outputs


def _row(key: str, source: str, *, context: str = "UI:Dialogue", file_path: str = "dialogue.txt") -> dict:
    return {
        "key": key,
        "source_text": source,
        "translation": "",
        "context": context,
        "file_path": file_path,
        "object_info": "",
        "import_method": "plain_text_line",
        "safety": "safe",
        "backend": "plain_text",
        "byte_limit": "",
        "patch_note": "",
    }


def _write_package(name: str, rows: list[dict]) -> tuple[Path, Path]:
    package = work_temp_dir(name)
    csv_path = package / "translation.csv"
    write_csv_rows_file(csv_path, CSV_FIELDS, rows)
    return package, csv_path


def _write_manifest(package: Path, rows: list[dict]) -> None:
    package.joinpath("manifest.json").write_text(
        json.dumps(
            {
                "entries": [
                    {
                        "key": row["key"],
                        "source_text": row["source_text"],
                        "translation": "",
                        "context": row["context"],
                        "file_path": row["file_path"],
                        "import_method": row["import_method"],
                        "locator": {"line": index + 1},
                    }
                    for index, row in enumerate(rows)
                ],
                "technical_skipped": [],
            }
        ),
        encoding="utf-8",
    )


class HumanReviewWorkflowTests(unittest.TestCase):
    def test_off_keeps_existing_promotion_behavior(self):
        _package, csv_path = _write_package("human_review_off", [_row("model", "Hello")])

        result = run_ct2_translate(csv_path, model_adapter=FakeReviewAdapter())

        self.assertTrue(result["ok"], result)
        self.assertTrue(result["complete"], result)
        self.assertEqual(result.get("human_review_required_count"), 0)
        _fields, rows = read_csv_rows_file(csv_path)
        self.assertEqual(rows[0]["translation"], "Xin chào")
        self.assertFalse((csv_path.parent / "review_only.csv").exists())

    def test_on_keeps_candidate_only_in_review_with_trace_evidence(self):
        source = "Hello {NAME} <color=red>world</color>\\n"
        _package, csv_path = _write_package("human_review_candidate", [_row("model", source)])

        result = run_ct2_translate(
            csv_path,
            model_adapter=FakeReviewAdapter(),
            human_review_required=True,
        )

        self.assertFalse(result["ok"], result)
        self.assertFalse(result["complete"], result)
        self.assertEqual(result["review_only"], 1)
        self.assertEqual(result["human_review_required_count"], 1)
        fields, rows = read_csv_rows_file(csv_path)
        self.assertEqual(rows[0]["translation"], "")
        review_fields, review_rows = read_csv_rows_file(csv_path.parent / "review_only.csv")
        self.assertEqual(review_fields, fields)
        self.assertEqual(review_rows[0]["key"], "model")
        self.assertEqual(review_rows[0]["source_text"], source)
        self.assertEqual(review_rows[0]["context"], "UI:Dialogue")
        self.assertEqual(review_rows[0]["file_path"], "dialogue.txt")
        self.assertEqual(review_rows[0]["translation"], "")
        self.assertIn("HUMAN_REVIEW_REQUIRED", review_rows[0]["patch_note"])
        self.assertIn("candidate=", review_rows[0]["patch_note"])
        self.assertIn("not auto-promoted", review_rows[0]["patch_note"])

        inventory = json.loads((csv_path.parent / ".mt" / "blocker_inventory.json").read_text(encoding="utf-8"))
        blocker = inventory["rows"][0]
        self.assertEqual(blocker["route"], "human_review_required")
        self.assertEqual(blocker["candidate"], "Xin chào {NAME} <color=red>thế giới</color>\\n")
        self.assertIn("HUMAN_REVIEW_REQUIRED", blocker["final_reasons"])
        self.assertIn("human_review_required", blocker["groups"])
        self.assertEqual(blocker["source_features"]["placeholder_count"], 1)
        self.assertEqual(blocker["source_features"]["newline_count"], 1)

    def test_human_review_toggle_off_does_not_promote_pending_key(self):
        package, csv_path = _write_package("human_review_toggle_rerun", [_row("model", "Hello")])

        first = run_ct2_translate(
            csv_path,
            model_adapter=FakeReviewAdapter(),
            human_review_required=True,
        )
        self.assertEqual(first["human_review_required_count"], 1, first)

        second = run_ct2_translate(
            csv_path,
            model_adapter=FakeReviewAdapter(),
            human_review_required=False,
        )

        self.assertFalse(second["ok"], second)
        self.assertFalse(second["complete"], second)
        self.assertEqual(second["human_review_required_count"], 1, second)
        _fields, current = read_csv_rows_file(csv_path)
        self.assertEqual(current[0]["translation"], "")
        _review_fields, review_rows = read_csv_rows_file(package / "review_only.csv")
        self.assertEqual({row["key"] for row in review_rows}, {"model"})

    def test_human_review_toggle_off_does_not_promote_key_scoped_retry(self):
        package, csv_path = _write_package("human_review_retry_rerun", [_row("model", "Hello")])

        first = run_ct2_translate(
            csv_path,
            model_adapter=FakeReviewAdapter(),
            human_review_required=True,
        )
        self.assertEqual(first["human_review_required_count"], 1, first)

        retry = run_ct2_translate_keys(
            csv_path,
            ["model"],
            model_adapter=FakeReviewAdapter(),
            human_review_required=False,
            backup=False,
        )

        self.assertFalse(retry["ok"], retry)
        self.assertEqual(retry["human_review_required_count"], 1, retry)
        _fields, current = read_csv_rows_file(csv_path)
        self.assertEqual(current[0]["translation"], "")
        _review_fields, review_rows = read_csv_rows_file(package / "review_only.csv")
        self.assertEqual({row["key"] for row in review_rows}, {"model"})

    def test_copy_and_technical_routes_are_not_human_reviewed(self):
        rows = [
            _row("model", "Hello"),
            _row("copy", "Xin chào"),
            _row("keep", "*GLRK*"),
            _row("technical", "Assets/Scenes/Main.unity", file_path="Assets/Scenes/Main.unity"),
        ]
        package, csv_path = _write_package("human_review_routes", rows)

        result = run_ct2_translate(
            csv_path,
            model_adapter=FakeReviewAdapter(),
            human_review_required=True,
        )

        self.assertEqual(result["human_review_required_count"], 1, result)
        _fields, translated = read_csv_rows_file(csv_path)
        by_key = {row["key"]: row for row in translated}
        self.assertEqual(by_key["copy"]["translation"], "Xin chào")
        self.assertEqual(by_key["keep"]["translation"], "*GLRK*")
        _review_fields, review_rows = read_csv_rows_file(package / "review_only.csv")
        self.assertEqual({row["key"] for row in review_rows}, {"model"})
        _technical_fields, technical_rows = read_csv_rows_file(package / "technical_skipped.csv")
        self.assertEqual({row["key"] for row in technical_rows}, {"technical"})

    def test_manual_save_reconciles_only_gate_valid_review_rows(self):
        rows = [_row("model", "Hello")]
        package, csv_path = _write_package("human_review_reconcile", rows)
        run_ct2_translate(
            csv_path,
            model_adapter=FakeReviewAdapter(),
            human_review_required=True,
        )
        review_path = package / "review_only.csv"
        review_fields, review_rows = read_csv_rows_file(review_path)
        fields, current = read_csv_rows_file(csv_path)
        current[0]["translation"] = "Xin chào"
        result = save_document(csv_path, fields, current)

        self.assertTrue(result["ok"], result)
        self.assertEqual(result["review_pruned"], 1)
        _fields, remaining = read_csv_rows_file(review_path)
        self.assertEqual(remaining, [])
        self.assertTrue(snapshot_translate_status(package, csv_path)["complete"])

        # An invalid manual value must not resolve the review ledger.
        write_csv_rows_file(
            review_path,
            review_fields,
            [{**_row("model", "Hello"), "patch_note": "HUMAN_REVIEW_REQUIRED"}],
        )
        current[0]["translation"] = "Xin chào {UNRESOLVED}"
        invalid = save_document(csv_path, fields, current)
        self.assertTrue(invalid["ok"], invalid)
        _fields, still_remaining = read_csv_rows_file(review_path)
        self.assertEqual({row["key"] for row in still_remaining}, {"model"})

        current[0]["translation"] = "Xin chào"
        final = save_document(csv_path, fields, current)
        self.assertEqual(final["review_pruned"], 1)
        self.assertTrue(snapshot_translate_status(package, csv_path)["complete"])

    def test_existing_human_review_remains_incomplete_when_no_new_target_exists(self):
        translated = _row("translated", "Hello")
        translated["translation"] = "Xin chào"
        package, csv_path = _write_package("human_review_existing", [translated])
        write_csv_rows_file(
            package / "review_only.csv",
            CSV_FIELDS,
            [{**_row("model", "Hello"), "patch_note": "HUMAN_REVIEW_REQUIRED: candidate=X"}],
        )
        package.joinpath(".mt").mkdir(parents=True, exist_ok=True)
        package.joinpath(".mt", "blocker_inventory.json").write_text(
            json.dumps({"rows": [{"key": "model", "route": "human_review_required"}]}),
            encoding="utf-8",
        )

        result = run_ct2_translate(
            csv_path,
            model_adapter=FakeReviewAdapter(),
            human_review_required=False,
        )

        self.assertFalse(result["ok"], result)
        self.assertFalse(result["complete"], result)
        self.assertEqual(result["human_review_required_count"], 1)
        self.assertIn("Cần duyệt thủ công 1 dòng trước khi Patch", result["summary"])
        inventory = json.loads((package / ".mt" / "blocker_inventory.json").read_text(encoding="utf-8"))
        self.assertEqual(inventory["rows"][0]["route"], "human_review_required")

    def test_key_scoped_retry_preserves_unrelated_review_rows(self):
        selected = _row("selected", "Hello")
        selected["translation"] = "Bản cũ"
        rows = [selected, _row("unrelated", "World")]
        package, csv_path = _write_package("human_review_key_retry", rows)
        review_path = package / "review_only.csv"
        write_csv_rows_file(
            review_path,
            CSV_FIELDS,
            [{**rows[1], "patch_note": "existing review"}],
        )

        result = run_ct2_translate_keys(
            csv_path,
            ["selected"],
            model_adapter=FakeReviewAdapter(),
            human_review_required=True,
            backup=False,
        )

        self.assertFalse(result["ok"], result)
        self.assertEqual(result["human_review_required_count"], 1)
        _fields, translated_rows = read_csv_rows_file(csv_path)
        self.assertEqual(translated_rows[0]["translation"], "")
        _fields, review_rows = read_csv_rows_file(review_path)
        self.assertEqual({row["key"] for row in review_rows}, {"selected", "unrelated"})
        inventory = json.loads((package / ".mt" / "blocker_inventory.json").read_text(encoding="utf-8"))
        self.assertEqual({row["key"] for row in inventory["rows"]}, {"selected"})

    def test_worker_forwards_human_review_flag(self):
        _package, csv_path = _write_package("human_review_worker", [_row("model", "Hello")])
        captured: list[dict] = []

        with patch(
            "vntext_worker.task_runners.run_translate_ct2_task",
            side_effect=lambda *_args, **kwargs: captured.append(kwargs),
        ):
            run_translate_worker(
                "human-review-task",
                {
                    "csv_path": str(csv_path),
                    "model": "ct2",
                    "human_review_required": True,
                },
                lambda: False,
            )

        self.assertEqual(len(captured), 1)
        self.assertTrue(captured[0]["human_review_required"])

    def test_app_task_completion_and_trace_show_review_required(self):
        rows = [_row("model", "Hello")]
        package, csv_path = _write_package("human_review_trace", rows)
        _write_manifest(package, rows)
        events: list[dict] = []

        with patch(
            "vntext.app_tasks.run_ct2_translate",
            side_effect=lambda path, **kwargs: run_ct2_translate(
                path,
                model_adapter=FakeReviewAdapter(),
                **kwargs,
            ),
        ):
            run_translate_ct2_task(
                csv_path,
                package,
                False,
                human_review_required=True,
                progress=lambda _info: None,
                log=lambda _line: None,
                complete=events.append,
            )

        self.assertEqual(len(events), 1)
        event = events[0]
        self.assertFalse(event["ok"], event)
        self.assertFalse(event["complete"], event)
        self.assertEqual(event["review_only"], 1)
        self.assertEqual(event["human_review_required_count"], 1)
        self.assertEqual(event["diagnostic_root_cause"], "HUMAN_REVIEW_REQUIRED")
        self.assertIn("Cần duyệt thủ công 1 dòng trước khi Patch", event["error"])
        status = json.loads((package / ".mt" / "translate_status.json").read_text(encoding="utf-8"))
        self.assertEqual(status["human_review_required_count"], 1)

        connection = sqlite3.connect(package / ".mt" / "traceability.sqlite3")
        try:
            payloads = [
                json.loads(row[0])
                for row in connection.execute(
                    "SELECT payload_json FROM trace_events WHERE stage = ?",
                    ("TRANSLATED",),
                ).fetchall()
            ]
        finally:
            connection.close()
        failed = [payload for payload in payloads if payload.get("failure") == "human_review_required"]
        self.assertEqual(len(failed), 1, payloads)
        self.assertEqual(failed[0]["blocker"]["route"], "human_review_required")
        self.assertEqual(failed[0]["blocker"]["candidate"], "Xin chào")


if __name__ == "__main__":
    unittest.main()
