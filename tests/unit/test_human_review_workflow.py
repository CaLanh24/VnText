"""Regression coverage for the explicit human-review translation route."""

from __future__ import annotations

import json
import sqlite3
import sys
import threading
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
from vntext.external_translation_import import import_existing_translations  # noqa: E402
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
    def test_cancel_after_blocking_batch_emits_terminal_without_starting_next_chunk(self):
        rows = [_row("one", "A longer dialogue line"), _row("two", "Another dialogue line")]
        package, csv_path = _write_package("cancel_after_blocking_batch", rows)
        _write_manifest(package, rows)
        cancelled = threading.Event()
        batch_entered = threading.Event()
        release_batch = threading.Event()

        class BlockingAdapter:
            config = {"batch_size": 1, "inter_threads": 1, "max_src_tokens": 512}
            calls = 0

            def metadata(self) -> dict:
                return {"adapter_id": "blocking-test", "model_engine": "Fake/Blocking"}

            def translate_many(self, texts: list[str]) -> list[str]:
                self.calls += 1
                batch_entered.set()
                if not release_batch.wait(5):
                    raise TimeoutError("test batch was not released")
                return ["Bản dịch an toàn" for _ in texts]

            def translate(self, text: str) -> str:
                return self.translate_many([text])[0]

        adapter = BlockingAdapter()
        terminal_events: list[tuple] = []
        errors: list[BaseException] = []

        def run_worker() -> None:
            try:
                run_translate_worker(
                    "cancel-after-batch",
                    {"csv_path": str(csv_path)},
                    cancelled.is_set,
                )
            except BaseException as exc:  # surfaced to the test thread
                errors.append(exc)

        with (
            patch("vntext.mt_ct2_model.get_translator", return_value=adapter),
            patch(
                "vntext_worker.task_runners.emit_complete",
                side_effect=lambda *args, **kwargs: terminal_events.append((args, kwargs)),
            ),
            patch("vntext_worker.task_runners.emit_progress"),
            patch("vntext_worker.task_runners.emit_log"),
        ):
            thread = threading.Thread(target=run_worker)
            thread.start()
            self.assertTrue(
                batch_entered.wait(5),
                f"blocking translator was not entered; terminal={terminal_events!r}, errors={errors!r}",
            )
            cancelled.set()
            self.assertTrue(thread.is_alive(), "cancel must wait for the active synchronous call")
            release_batch.set()
            thread.join(10)

        self.assertFalse(thread.is_alive(), "cancel did not reach a terminal result after batch return")
        self.assertEqual(errors, [])
        self.assertEqual(adapter.calls, 1, "cancellation must prevent starting the next chunk")
        self.assertEqual(len(terminal_events), 1, terminal_events)
        _args, payload = terminal_events[0]
        self.assertFalse(payload.get("ok", True), payload)
        self.assertEqual(payload.get("error"), "cancelled", payload)
        self.assertFalse(payload.get("complete", True), payload)
        _fields, persisted_rows = read_csv_rows_file(csv_path)
        self.assertTrue(all(not row["translation"] for row in persisted_rows), persisted_rows)

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

    def test_editing_review_only_csv_preserves_rows_until_explicit_import(self):
        rows = [_row("model", "Hello")]
        package, csv_path = _write_package("human_review_editor_import", rows)
        _write_manifest(package, rows)
        run_ct2_translate(
            csv_path,
            model_adapter=FakeReviewAdapter(),
            human_review_required=True,
        )

        review_path = package / "review_only.csv"
        review_fields, review_rows = read_csv_rows_file(review_path)
        self.assertEqual({row["key"] for row in review_rows}, {"model"})
        review_rows[0]["translation"] = "Xin chào"
        saved = save_document(review_path, review_fields, review_rows)
        self.assertTrue(saved["ok"], saved)
        self.assertEqual(saved["review_pruned"], 0)
        _fields, saved_review_rows = read_csv_rows_file(review_path)
        self.assertEqual(saved_review_rows[0]["translation"], "Xin chào")

        imported = import_existing_translations(csv_path, review_path)
        self.assertEqual(imported["applied"], 1, imported)
        self.assertTrue(imported["complete"], imported)
        _fields, translated_rows = read_csv_rows_file(csv_path)
        self.assertEqual(translated_rows[0]["translation"], "Xin chào")
        _fields, remaining_review_rows = read_csv_rows_file(review_path)
        self.assertEqual(remaining_review_rows, [])
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


class TranslateTerminalClassificationTests(unittest.TestCase):
    """Ordinary failures and cancellation must reach distinct, truthful terminals."""

    def _run_worker(self, task_id: str, csv_path: Path, is_cancelled) -> list[tuple]:
        terminal_events: list[tuple] = []
        with (
            patch("vntext.mt_ct2_model.get_translator", return_value=FakeReviewAdapter()),
            patch(
                "vntext_worker.task_runners.emit_complete",
                side_effect=lambda *args, **kwargs: terminal_events.append((args, kwargs)),
            ),
            patch("vntext_worker.task_runners.emit_progress"),
            patch("vntext_worker.task_runners.emit_log"),
        ):
            run_translate_worker(task_id, {"csv_path": str(csv_path)}, is_cancelled)
        return terminal_events

    def _assert_identity_preserved(self, csv_path: Path, rows: list[dict], allowed: set[str]) -> None:
        _fields, persisted = read_csv_rows_file(csv_path)
        self.assertEqual(
            [(row["key"], row["source_text"]) for row in persisted],
            [(row["key"], row["source_text"]) for row in rows],
        )
        for row in persisted:
            self.assertIn(row["translation"], allowed, persisted)
        self.assertEqual(sorted(csv_path.parent.glob("*.tmp")), [])

    def _run_status_counts(self, package: Path) -> dict:
        summary = json.loads((package / ".mt" / "trace_summary.json").read_text(encoding="utf-8"))
        return summary["run_status_counts"]

    def test_ordinary_failure_is_reported_as_failure_not_cancellation(self):
        rows = [_row("one", "Hello"), _row("two", "Hello again")]
        package, csv_path = _write_package("translate_ordinary_failure", rows)
        _write_manifest(package, rows)
        failure = TypeError("unsupported operand type(s) for /: 'str' and 'str'")

        with patch("vntext.mt_ct2_pipeline._cache_validated_candidate", side_effect=failure):
            events = self._run_worker("ordinary-failure", csv_path, lambda: False)

        self.assertEqual(len(events), 1, events)
        _args, payload = events[0]
        self.assertFalse(payload.get("ok", True), payload)
        self.assertIn("unsupported operand", payload.get("error") or "", payload)
        action = str(payload.get("diagnostic_action") or "").lower()
        self.assertNotIn("cancel", action, payload)
        self.assertNotIn("interrupt", action, payload)
        self.assertEqual(self._run_status_counts(package), {"FAILED": 1})
        self._assert_identity_preserved(csv_path, rows, {""})

    def test_cancel_seen_by_progress_callback_flushes_closes_cache_and_allows_retry(self):
        from vntext import mt_ct2_pipeline
        from vntext.translation_cache import TranslationCache

        rows = [_row("one", "Hello"), _row("two", "Hello again")]
        package, csv_path = _write_package("translate_cancel_at_progress", rows)
        _write_manifest(package, rows)
        cancelled = threading.Event()
        original = mt_ct2_pipeline._cache_validated_candidate

        def cancel_after_validation(*args, **kwargs):
            # The host cancel lands after the model call's own checkpoint has
            # returned, so the next observer is the worker progress callback.
            cancelled.set()
            return original(*args, **kwargs)

        with (
            patch.object(FakeReviewAdapter, "config", {"batch_size": 1, "inter_threads": 1, "max_src_tokens": 512}),
            patch("vntext.mt_ct2_pipeline._cache_validated_candidate", side_effect=cancel_after_validation),
        ):
            events = self._run_worker("cancel-at-progress", csv_path, cancelled.is_set)

        self.assertEqual(len(events), 1, events)
        _args, payload = events[0]
        self.assertFalse(payload.get("ok", True), payload)
        self.assertEqual(payload.get("error"), "cancelled", payload)
        self.assertFalse(payload.get("complete", True), payload)
        self.assertEqual(self._run_status_counts(package), {"ABORTED": 1})
        self._assert_identity_preserved(csv_path, rows, {"", "Xin chào"})
        # A cancelled run must release the package-local cache lock for retry.
        TranslationCache(package).close()

        retry = self._run_worker("retry-after-cancel", csv_path, lambda: False)
        self.assertEqual(len(retry), 1, retry)
        _args, retry_payload = retry[0]
        self.assertNotEqual(retry_payload.get("error"), "cancelled", retry_payload)
        self._assert_identity_preserved(csv_path, rows, {"", "Xin chào"})
        _fields, persisted = read_csv_rows_file(csv_path)
        self.assertEqual(persisted[0]["translation"], "Xin chào", persisted)


if __name__ == "__main__":
    unittest.main()
