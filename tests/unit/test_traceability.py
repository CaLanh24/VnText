from __future__ import annotations

import json
import hashlib
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from vntext.entry import Entry
from vntext.package_io import _classifier_matches_package_classification, write_package
from vntext.package_io import read_csv_rows_file, write_csv_rows_file
from vntext.app_tasks import _run_traced_translation, _trace_patch_start, run_patch_task
from vntext.app_tasks import run_extract_task
from vntext.mt_classify import CLASSIFIER_POLICY_VERSION, classify_row_authoritative
from vntext.traceability import (
    CLASSIFICATION_MAIN,
    CLASSIFICATION_REVIEW,
    EVENT_ABORTED,
    EVENT_COMPLETED,
    EVENT_STARTED,
    EVENT_FAILED,
    ROOT_CAUSE_UNKNOWN,
    ROOT_CAUSE_DISCOVERY_GAP,
    ROOT_CAUSE_MISCLASSIFIED,
    ROOT_CAUSE_PATCH_VERIFY_FAILED,
    STAGE_EXTRACTED,
    STAGE_TRANSLATED,
    TRACE_SCHEMA_VERSION,
    TraceStore,
    TraceStoreError,
    compute_package_id,
    compute_target_id,
    compute_trace_id,
)


TRACE_TEST_WORK_ROOT = Path(__file__).resolve().parents[1] / "golden" / "_work"


def _manifest() -> dict:
    return {
        "format": 2,
        "version": "test",
        "entries": [
            {
                "key": "entry-a",
                "source_text": "Hello",
                "file_path": "data.assets",
                "import_method": "unity_ui_text",
                "locator": {"field_path": "m_Text", "path_id": 7},
            }
        ],
        "technical_skipped": [],
        "stats": {"generated_at": "must-not-affect-id", "entries": 1},
    }


def _entry(key: str = "entry-a") -> Entry:
    return Entry(
        key=key,
        source_text="Hello",
        file_path="data.assets",
        context="object",
        object_info="TextMeshProUGUI",
        import_method="unity_ui_text",
        backend="unity",
        locator={"path_id": 7, "field_path": "m_Text"},
        duplicate_locations=[{"path_id": 8, "field_path": "m_Text"}],
    )


class TraceIdentityTests(unittest.TestCase):
    def test_package_identity_ignores_embedded_csv_line_ending_style(self):
        lf = _manifest()
        crlf = json.loads(json.dumps(lf))
        lf["entries"][0]["source_text"] = "Hello\nworld"
        crlf["entries"][0]["source_text"] = "Hello\r\nworld"

        self.assertEqual(compute_package_id(lf), compute_package_id(crlf))

    def test_package_identity_ignores_order_stats_and_timestamps(self):
        first = _manifest()
        second = {
            "stats": {"entries": 99, "timestamp": "different"},
            "technical_skipped": [],
            "entries": [
                {
                    "locator": {"path_id": 7, "field_path": "m_Text"},
                    "import_method": "unity_ui_text",
                    "file_path": "data.assets",
                    "source_text": "Hello",
                    "key": "entry-a",
                }
            ],
            "version": "other",
        }
        self.assertEqual(compute_package_id(first), compute_package_id(second))

        changed = json.loads(json.dumps(first))
        changed["entries"][0]["source_text"] = "Goodbye"
        self.assertNotEqual(compute_package_id(first), compute_package_id(changed))
        changed_locator = json.loads(json.dumps(first))
        changed_locator["entries"][0]["locator"]["path_id"] = 8
        self.assertNotEqual(compute_package_id(first), compute_package_id(changed_locator))

    def test_package_identity_survives_technical_ledger_reclassification(self):
        before = _manifest()
        after = json.loads(json.dumps(before))
        row = after["entries"].pop()
        row["reason"] = "technical classifier decision"
        after["technical_skipped"] = [row]

        self.assertEqual(compute_package_id(before), compute_package_id(after))

    def test_trace_and_target_identity_are_stable_and_duplicates_are_distinct(self):
        package_id = compute_package_id(_manifest())
        trace_id = compute_trace_id(package_id, "entry-a")
        self.assertEqual(trace_id, compute_trace_id(package_id, "entry-a"))
        first = compute_target_id(trace_id, {"path_id": 7}, 0)
        second = compute_target_id(trace_id, {"path_id": 7}, 1)
        self.assertNotEqual(first, second)


class TraceStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        # Keep SQLite/lock fixtures in the repository's sanctioned test-work
        # area. The host temp directory is monitored and intermittently
        # interrupted lock-file operations during a long Release gate.
        TRACE_TEST_WORK_ROOT.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(
            prefix="vntext-trace-",
            dir=TRACE_TEST_WORK_ROOT,
        )
        self.root = Path(self.temp.name)
        self.package_id = compute_package_id(_manifest())

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_schema_pragmas_and_entry_key_are_preserved(self):
        store = TraceStore(self.root, self.package_id)
        try:
            self.assertEqual(store.connection.execute("PRAGMA user_version").fetchone()[0], TRACE_SCHEMA_VERSION)
            self.assertEqual(store.connection.execute("PRAGMA journal_mode").fetchone()[0].lower(), "wal")
            self.assertEqual(store.connection.execute("PRAGMA synchronous").fetchone()[0], 2)
            self.assertEqual(store.connection.execute("PRAGMA busy_timeout").fetchone()[0], 5000)
            columns = {
                row[1]
                for row in store.connection.execute("PRAGMA table_info(trace_entries)").fetchall()
            }
            self.assertTrue(
                {
                    "source_text",
                    "source_file",
                    "container",
                    "object_info",
                    "path_id",
                    "field_locator",
                    "locator_json",
                    "import_method",
                    "model_engine",
                    "model_revision",
                    "glossary_fingerprint",
                    "context_fingerprint",
                    "cache_fingerprint",
                    "memory_fingerprint",
                    "translation",
                    "translation_hash",
                    "validation_result",
                    "patch_status",
                    "write_status",
                    "readback_status",
                    "final_verification",
                    "runtime_status",
                    "root_cause",
                }.issubset(columns)
            )
            result = store.register_entry(_entry())
            self.assertEqual(result["entry_key"], "entry-a")
            row = store.connection.execute(
                "SELECT entry_key, source_text FROM trace_entries WHERE trace_id = ?",
                (result["trace_id"],),
            ).fetchone()
            self.assertEqual(row, ("entry-a", "Hello"))
            targets = store.connection.execute(
                "SELECT duplicate_ordinal, target_id FROM trace_targets WHERE trace_id = ? ORDER BY duplicate_ordinal",
                (result["trace_id"],),
            ).fetchall()
            self.assertEqual([row[0] for row in targets], [0, 1])
            self.assertNotEqual(targets[0][1], targets[1][1])
        finally:
            store.close()

    def test_lock_rejects_live_owner_and_reclaims_stale_owner(self):
        first = TraceStore(self.root, self.package_id)
        try:
            with self.assertRaises(TraceStoreError):
                TraceStore(self.root, self.package_id)
        finally:
            first.close()

        lock = self.root / ".mt" / "traceability.lock"
        lock.write_text(
            json.dumps({"owner_id": "stale", "pid": os.getpid() + 1000000}),
            encoding="utf-8",
        )
        recovered = TraceStore(self.root, self.package_id)
        recovered.close()

    def test_migration_is_additive_and_future_schema_fails_closed(self):
        store = TraceStore(self.root, self.package_id)
        store.close()
        connection = sqlite3.connect(self.root / ".mt" / "traceability.sqlite3")
        try:
            connection.execute("PRAGMA user_version = 0")
            connection.commit()
        finally:
            connection.close()
        reopened = TraceStore(self.root, self.package_id)
        reopened.close()

        connection = sqlite3.connect(self.root / ".mt" / "traceability.sqlite3")
        try:
            connection.execute("PRAGMA user_version = 99")
            connection.commit()
        finally:
            connection.close()
        with self.assertRaises(TraceStoreError):
            TraceStore(self.root, self.package_id)

    def test_v1_store_migrates_memory_fingerprint_additively(self):
        store = TraceStore(self.root, self.package_id)
        store.close()
        connection = sqlite3.connect(self.root / ".mt" / "traceability.sqlite3")
        try:
            connection.execute("PRAGMA user_version = 1")
            connection.execute("ALTER TABLE trace_entries DROP COLUMN memory_fingerprint")
            connection.commit()
        finally:
            connection.close()

        migrated = TraceStore(self.root, self.package_id)
        try:
            columns = {
                row[1]
                for row in migrated.connection.execute("PRAGMA table_info(trace_entries)").fetchall()
            }
            self.assertIn("memory_fingerprint", columns)
            self.assertEqual(
                migrated.connection.execute("PRAGMA user_version").fetchone()[0],
                TRACE_SCHEMA_VERSION,
            )
        finally:
            migrated.close()

    def test_register_entry_merges_metadata_across_pipeline_reuse(self):
        store = TraceStore(self.root, self.package_id)
        try:
            result = store.register_entry(_entry(), metadata={"source": "extract", "inventory": 1})
            store.register_entry(_entry(), metadata={"source": "manifest", "pipeline": "translate"})
            row = store.connection.execute(
                "SELECT metadata_json FROM trace_entries WHERE trace_id = ?",
                (result["trace_id"],),
            ).fetchone()
            self.assertEqual(
                json.loads(row[0]),
                {"source": "manifest", "inventory": 1, "pipeline": "translate"},
            )
        finally:
            store.close()

    def test_event_ordering_summary_and_export(self):
        store = TraceStore(self.root, self.package_id)
        try:
            result = store.register_entry(_entry())
            run_id = store.start_run(metadata={"fixture": "unit"})
            action_id = store.start_event(STAGE_EXTRACTED, trace_id=result["trace_id"])
            events = store.connection.execute(
                "SELECT event_status FROM trace_events WHERE action_id = ? ORDER BY event_id",
                (action_id,),
            ).fetchall()
            self.assertEqual([row[0] for row in events], [EVENT_STARTED])
            store.finish_event(action_id, EVENT_COMPLETED)
            store.record_event(STAGE_TRANSLATED, "PASS", trace_id=result["trace_id"])
            store.finish_run(EVENT_COMPLETED)
            summary = store.summary()
            self.assertEqual(summary["run_id"], run_id)
            self.assertEqual(summary["classification_counts"], {CLASSIFICATION_MAIN: 1})
            self.assertEqual(summary["event_status_counts"][EVENT_STARTED], 2)
            self.assertEqual(summary["event_status_counts"]["PASS"], 1)
            self.assertEqual(summary["event_status_counts"][EVENT_COMPLETED], 1)
            summary_path = store.write_summary()
            self.assertEqual(json.loads(summary_path.read_text(encoding="utf-8"))["package_id"], self.package_id)
            diagnostic_path = self.root / ".mt" / "diagnostic_summary.json"
            diagnostic = json.loads(diagnostic_path.read_text(encoding="utf-8"))
            self.assertEqual(diagnostic["total_candidates"], 1)
            self.assertEqual(diagnostic["trace_coverage"]["status"], "NOT_RECORDED")
            self.assertTrue(diagnostic["actionable_next_step"])
            export_path = store.export_jsonl()
            self.assertEqual(len(export_path.read_text(encoding="utf-8").splitlines()), 4)
        finally:
            store.close()

    def test_completed_run_rejects_inflight_action(self):
        store = TraceStore(self.root, self.package_id)
        try:
            result = store.register_entry(_entry("inflight"))
            store.start_run()
            action_id = store.start_event(STAGE_EXTRACTED, trace_id=result["trace_id"])
            with self.assertRaisesRegex(TraceStoreError, "in-flight"):
                store.finish_run(EVENT_COMPLETED)
            store.finish_event(action_id, EVENT_COMPLETED)
            store.finish_run(EVENT_COMPLETED)
        finally:
            store.close()

    def test_terminal_run_rejects_new_events_and_second_finish(self):
        store = TraceStore(self.root, self.package_id)
        try:
            store.start_run()
            store.finish_run(EVENT_COMPLETED)
            with self.assertRaisesRegex(TraceStoreError, "not RUNNING"):
                store.start_event(STAGE_EXTRACTED)
            with self.assertRaisesRegex(TraceStoreError, "not RUNNING"):
                store.finish_run(EVENT_COMPLETED)
        finally:
            store.close()

    def test_crash_recovery_aborts_inflight_and_never_marks_pass(self):
        crashed = TraceStore(self.root, self.package_id)
        result = crashed.register_entry(_entry())
        run_id = crashed.start_run()
        action_id = crashed.start_event(STAGE_EXTRACTED, trace_id=result["trace_id"])
        crashed.close()

        recovered = TraceStore(self.root, self.package_id)
        try:
            event_rows = recovered.connection.execute(
                "SELECT event_status, root_cause FROM trace_events WHERE action_id = ? ORDER BY event_id",
                (action_id,),
            ).fetchall()
            self.assertEqual(event_rows, [(EVENT_STARTED, None), (EVENT_ABORTED, ROOT_CAUSE_UNKNOWN)])
            run_status = recovered.connection.execute(
                "SELECT status, root_cause FROM trace_runs WHERE run_id = ?", (run_id,)
            ).fetchone()
            self.assertEqual(run_status, (EVENT_ABORTED, ROOT_CAUSE_UNKNOWN))
            entry_status = recovered.connection.execute(
                "SELECT status, root_cause FROM trace_entries WHERE trace_id = ?",
                (result["trace_id"],),
            ).fetchone()
            self.assertEqual(entry_status, (EVENT_ABORTED, ROOT_CAUSE_UNKNOWN))
            self.assertNotIn("PASS", {row[0] for row in event_rows})
        finally:
            recovered.close()

    def test_review_classification_is_explicit(self):
        store = TraceStore(self.root, self.package_id)
        try:
            entry = _entry("review")
            result = store.register_entry(entry, classification=CLASSIFICATION_REVIEW, classification_reason="needs proof")
            row = store.connection.execute(
                "SELECT classification, classification_reason FROM trace_entries WHERE trace_id = ?",
                (result["trace_id"],),
            ).fetchone()
            self.assertEqual(row, (CLASSIFICATION_REVIEW, "needs proof"))
        finally:
            store.close()

    def test_non_main_classification_requires_reason(self):
        store = TraceStore(self.root, self.package_id)
        try:
            with self.assertRaisesRegex(TraceStoreError, "requires an explicit reason"):
                store.register_entry(_entry("review-without-reason"), classification=CLASSIFICATION_REVIEW)
        finally:
            store.close()

    def test_traced_translation_fails_closed_on_malformed_manifest_entry(self):
        entry = _entry("manifest-malformed")
        entry.patch_proof = {
            "reader": True,
            "writer": True,
            "preflight": True,
            "reopen": True,
            "semantic_verify": True,
        }
        package = self.root / "malformed-manifest-package"
        write_package(
            str(package),
            [entry],
            [],
            {"mode": "deep"},
            separate_review=True,
            enforce_symmetry=True,
        )
        manifest = json.loads((package / "manifest.json").read_text(encoding="utf-8"))
        manifest["entries"].append({"source_text": "missing key"})
        (package / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False), encoding="utf-8"
        )
        csv_path = package / "translation.csv"
        called = []

        def operation():
            called.append(True)
            return {"ok": True}

        with self.assertRaisesRegex(RuntimeError, "missing key"):
            _run_traced_translation(csv_path, package, operation, overwrite=False)
        self.assertEqual(called, [])
        summary = json.loads((package / ".mt" / "trace_summary.json").read_text(encoding="utf-8"))
        self.assertEqual(summary["run_status_counts"], {EVENT_ABORTED: 1})

    def test_result_fields_are_updated_through_sink_api(self):
        store = TraceStore(self.root, self.package_id)
        try:
            result = store.register_entry(_entry())
            store.update_entry(
                result["trace_id"],
                stage=STAGE_TRANSLATED,
                status="PASS",
                model_engine="ct2",
                model_revision="r1",
                translation="Xin chào",
                validation_result="PASS",
                patch_status="PENDING",
            )
            store.update_target(result["target_ids"][1], write_status="PASS", readback_status="PENDING")
            row = store.connection.execute(
                "SELECT stage, status, model_engine, translation, translation_hash, validation_result FROM trace_entries WHERE trace_id = ?",
                (result["trace_id"],),
            ).fetchone()
            self.assertEqual(row[0:4], (STAGE_TRANSLATED, "PASS", "ct2", "Xin chào"))
            self.assertEqual(row[4], hashlib.sha256("Xin chào".encode()).hexdigest())
            self.assertEqual(row[5], "PASS")
            target = store.connection.execute(
                "SELECT write_status, readback_status FROM trace_targets WHERE target_id = ?",
                (result["target_ids"][1],),
            ).fetchone()
            self.assertEqual(target, ("PASS", "PENDING"))
        finally:
            store.close()

    def test_traced_package_matches_manifest_and_csv_counts(self):
        visible = _entry("visible")
        technical = _entry("technical")
        technical.source_text = "Sample.Scene_{mName}"
        review = _entry("review")
        review.review_only = True
        proof = {
            "reader": True,
            "writer": True,
            "preflight": True,
            "reopen": True,
            "semantic_verify": True,
        }
        visible.patch_proof = dict(proof)
        technical.patch_proof = dict(proof)
        before_keys = [visible.key, technical.key, review.key]
        out = self.root / "traced-package"
        write_package(
            str(out),
            [visible, technical],
            [review],
            {"mode": "deep"},
            separate_review=True,
            enforce_symmetry=True,
            enable_trace=True,
        )
        self.assertEqual([visible.key, technical.key, review.key], before_keys)
        summary = json.loads((out / ".mt" / "trace_summary.json").read_text(encoding="utf-8"))
        self.assertEqual(summary["measurements"]["candidate_emitted"], 3)
        self.assertEqual(summary["measurements"]["manifest_entries"], 2)
        self.assertEqual(summary["measurements"]["translation_csv_entries"], 1)
        self.assertEqual(summary["measurements"]["review_only_entries"], 1)
        self.assertEqual(summary["measurements"]["technical_skipped_entries"], 1)
        classifier = summary["measurements"]["classifier"]
        self.assertEqual(classifier["rows"], 3)
        self.assertTrue(classifier["no_drop"])
        self.assertEqual(classifier["decision_counts"]["TRANSLATE"], 1)
        self.assertEqual(classifier["decision_counts"]["DO_NOT_TRANSLATE"], 1)
        self.assertEqual(classifier["decision_counts"]["REVIEW"], 1)
        self.assertEqual(summary["run_status_counts"], {EVENT_COMPLETED: 1})
        self.assertTrue((out / ".mt" / "traceability.sqlite3").is_file())
        self.assertTrue((out / ".mt" / "trace_export.jsonl").is_file())
        metadata = json.loads(
            self._store_metadata(out, visible.key)
        )
        self.assertEqual(metadata["classifier_v2"]["policy_version"], CLASSIFIER_POLICY_VERSION)
        self.assertEqual(metadata["classifier_v2"]["decision"], "TRANSLATE")
        self.assertNotIn(ROOT_CAUSE_MISCLASSIFIED, summary["root_cause_counts"])

    def test_classifier_bucket_mismatch_is_detectable_without_relaxing_route(self):
        _action, _reason, decision = classify_row_authoritative(_entry("route-contract").to_csv_row())

        self.assertEqual(decision.decision, "TRANSLATE")
        self.assertTrue(_classifier_matches_package_classification(CLASSIFICATION_MAIN, decision))
        self.assertFalse(_classifier_matches_package_classification(CLASSIFICATION_REVIEW, decision))

    def test_traced_raw_unsupported_boundary_is_not_misclassified(self):
        raw = _entry("raw-unsupported-boundary")
        raw.import_method = "naninovel_raw_candidate"
        raw.source_text = "This is a normal dialogue sentence with enough words"
        out = self.root / "raw-unsupported-boundary"

        write_package(
            str(out),
            [],
            [raw],
            {"mode": "deep"},
            separate_review=True,
            enforce_symmetry=False,
            enable_trace=True,
        )

        summary = json.loads((out / ".mt" / "trace_summary.json").read_text(encoding="utf-8"))
        self.assertEqual(summary["measurements"]["classifier"]["misclassified"], 0)
        self.assertNotIn(ROOT_CAUSE_MISCLASSIFIED, summary["root_cause_counts"])

    def test_traced_review_metadata_survives_package_split(self):
        review = _entry("review-metadata")
        review.source_text = "dateFormat"
        review.file_path = (
            "SampleGame_Data\\StreamingAssets\\aa\\"
            "StandaloneWindows\\sample_assets.bundle"
        )
        review.context = "dateFormat"
        review.object_info = "MonoBehaviour:42:SampleState"
        review.import_method = "unity_typetree_field"
        review.backend = "unitypy_typetree"
        review.review_only = True
        out = self.root / "review-metadata"

        write_package(
            str(out),
            [review],
            [],
            {"mode": "deep"},
            separate_review=True,
            enforce_symmetry=False,
            enable_trace=True,
        )

        summary = json.loads((out / ".mt" / "trace_summary.json").read_text(encoding="utf-8"))
        classifier = summary["measurements"]["classifier"]
        self.assertEqual(classifier["decision_counts"]["REVIEW"], 1)
        self.assertEqual(classifier["misclassified"], 0)
        self.assertNotIn(ROOT_CAUSE_MISCLASSIFIED, summary["root_cause_counts"])
        self.assertEqual(summary["measurements"]["technical_skipped_entries"], 0)

    @staticmethod
    def _store_metadata(package: Path, entry_key: str) -> str:
        connection = sqlite3.connect(package / ".mt" / "traceability.sqlite3")
        try:
            row = connection.execute(
                "SELECT metadata_json FROM trace_entries WHERE entry_key = ?", (entry_key,)
            ).fetchone()
            if row is None:
                raise AssertionError(f"missing trace metadata for {entry_key}")
            return row[0]
        finally:
            connection.close()

    def test_traced_package_fails_closed_before_output_files_if_store_cannot_open(self):
        out = self.root / "trace-init-failure"
        entry = _entry("visible")
        entry.patch_proof = {
            "reader": True,
            "writer": True,
            "preflight": True,
            "reopen": True,
            "semantic_verify": True,
        }
        with patch("vntext.traceability.TraceStore.for_package", side_effect=TraceStoreError("open failed")):
            with self.assertRaisesRegex(TraceStoreError, "open failed"):
                write_package(
                    str(out),
                    [entry],
                    [],
                    {"mode": "deep"},
                    separate_review=True,
                    enforce_symmetry=True,
                    enable_trace=True,
                )
        self.assertFalse((out / "translation.csv").exists())
        self.assertFalse((out / "manifest.json").exists())

    def test_traced_package_marks_discovery_errors_as_failed_run(self):
        entry = _entry("discovery-error")
        entry.patch_proof = {
            "reader": True,
            "writer": True,
            "preflight": True,
            "reopen": True,
            "semantic_verify": True,
        }
        out = self.root / "discovery-error-package"
        write_package(
            str(out),
            [entry],
            [],
            {
                "mode": "deep",
                "errors": ["asset: unity_typetree TIMEOUT"],
                "file_timings": [{"file": "asset", "step": "unity_typetree", "status": "TIMEOUT"}],
            },
            separate_review=True,
            enforce_symmetry=True,
            enable_trace=True,
        )
        summary = json.loads((out / ".mt" / "trace_summary.json").read_text(encoding="utf-8"))
        self.assertEqual(summary["run_status_counts"], {EVENT_FAILED: 1})
        self.assertEqual(summary["event_root_cause_counts"], {ROOT_CAUSE_DISCOVERY_GAP: 4})
        export = (out / ".mt" / "trace_export.jsonl").read_text(encoding="utf-8")
        self.assertIn("unity_typetree", export)

    def test_extract_task_reports_partial_package_on_discovery_error(self):
        entry = _entry("extract-error")
        entry.patch_proof = {
            "reader": True,
            "writer": True,
            "preflight": True,
            "reopen": True,
            "semantic_verify": True,
        }
        completed: list[dict] = []
        with patch("vntext.app_tasks._run_unity_preflight"), patch(
            "vntext.app_tasks.extract_project",
            return_value=(
                [entry],
                [],
                {"errors": ["dialogue.txt: plain_text TIMEOUT"]},
            ),
        ), patch("vntext.app_tasks.write_package") as write_mock:
            run_extract_task(
                "game",
                "package",
                "deep",
                "balanced",
                True,
                progress=lambda _payload: None,
                log=lambda _message: None,
                complete=completed.append,
            )
        self.assertEqual(write_mock.call_count, 1)
        self.assertEqual(len(completed), 1)
        self.assertFalse(completed[0]["ok"])
        self.assertFalse(completed[0]["complete"])
        self.assertIn("TIMEOUT", completed[0]["error"])

    def test_extract_task_does_not_complete_with_review_rows(self):
        entry = _entry("extract-review")
        entry.patch_proof = {
            "reader": True,
            "writer": True,
            "preflight": True,
            "reopen": True,
            "semantic_verify": True,
        }
        completed: list[dict] = []
        with patch("vntext.app_tasks._run_unity_preflight"), patch(
            "vntext.app_tasks.extract_project",
            return_value=([entry], [entry], {"errors": []}),
        ), patch("vntext.app_tasks.write_package") as write_mock:
            run_extract_task(
                "game",
                "package",
                "deep",
                "balanced",
                True,
                progress=lambda _payload: None,
                log=lambda _message: None,
                complete=completed.append,
            )
        self.assertEqual(write_mock.call_count, 1)
        self.assertEqual(len(completed), 1)
        self.assertFalse(completed[0]["ok"])
        self.assertFalse(completed[0]["complete"])
        self.assertEqual(completed[0]["review_only"], 1)
        self.assertIn("REVIEW", completed[0]["error"])

    def test_traced_translation_persists_per_entry_cache_fingerprint(self):
        entry = _entry("translation-cache-fingerprint")
        entry.patch_proof = {
            "reader": True,
            "writer": True,
            "preflight": True,
            "reopen": True,
            "semantic_verify": True,
        }
        package = self.root / "translation-package"
        write_package(
            str(package),
            [entry],
            [],
            {"mode": "deep"},
            separate_review=True,
            enforce_symmetry=True,
        )
        csv_path = package / "translation.csv"
        fields, rows = read_csv_rows_file(csv_path)

        def operation():
            current_fields, current_rows = read_csv_rows_file(csv_path)
            current_rows[0]["translation"] = "Xin chào"
            write_csv_rows_file(csv_path, current_fields, current_rows)
            return {
                "ok": True,
                "pipeline_liveness": True,
                "cache": {"status": "enabled", "hits": 0, "misses": 1},
                "cache_fingerprints": {entry.key: "cache-key-for-entry"},
                "retry_attempts_by_key": {
                    entry.key: [
                        {
                            "attempt_id": "retry-attempt-1",
                            "strategy": "full_sentence",
                            "raw_output": "Hello there",
                            "raw_output_hash": "raw-hash",
                            "candidate": "Xin chào",
                            "candidate_hash": "candidate-hash",
                            "validation_reasons": [],
                            "passed": True,
                        }
                    ]
                },
            }

        result = _run_traced_translation(
            csv_path,
            package,
            operation,
            overwrite=False,
        )
        self.assertTrue(result["ok"])
        connection = sqlite3.connect(package / ".mt" / "traceability.sqlite3")
        try:
            row = connection.execute(
                "SELECT cache_fingerprint, translation_hash FROM trace_entries WHERE entry_key = ?",
                (entry.key,),
            ).fetchone()
            event_payload = connection.execute(
                "SELECT payload_json FROM trace_events WHERE stage = ? AND event_status = 'PASS'",
                ("TRANSLATED",),
            ).fetchone()
        finally:
            connection.close()
        self.assertEqual(
            row,
            (
                "cache-key-for-entry",
                hashlib.sha256("Xin chào".encode("utf-8")).hexdigest(),
            ),
        )
        self.assertEqual(json.loads(event_payload[0])["attempts"][0]["attempt_id"], "retry-attempt-1")
        self.assertEqual(json.loads(event_payload[0])["attempts"][0]["candidate_hash"], "candidate-hash")

    def test_traced_translation_records_policy_and_frozen_provenance(self):
        fixed = _entry("policy-fixed")
        fixed.source_text = "Pass"
        fixed.context = "UI:Text"
        kept = _entry("policy-kept")
        kept.source_text = "Ahhh"
        kept.context = "UI:Text"
        frozen = _entry("existing-frozen")
        frozen.source_text = "Already"
        frozen.context = "UI:Text"
        proof = {
            "reader": True,
            "writer": True,
            "preflight": True,
            "reopen": True,
            "semantic_verify": True,
        }
        for entry in (fixed, kept, frozen):
            entry.patch_proof = dict(proof)
        package = self.root / "policy-provenance-package"
        write_package(
            str(package),
            [fixed, kept, frozen],
            [],
            {"mode": "deep"},
            separate_review=True,
            enforce_symmetry=True,
        )
        csv_path = package / "translation.csv"
        fields, rows = read_csv_rows_file(csv_path)
        for row in rows:
            if row["key"] == frozen.key:
                row["translation"] = "Đã có"
        write_csv_rows_file(csv_path, fields, rows)

        def operation():
            current_fields, current_rows = read_csv_rows_file(csv_path)
            values = {
                fixed.key: "Đạt ",
                kept.key: kept.source_text,
                frozen.key: "Đã có",
            }
            for row in current_rows:
                row["translation"] = values[row["key"]]
            write_csv_rows_file(csv_path, current_fields, current_rows)
            return {"ok": True, "pipeline_liveness": True}

        result = _run_traced_translation(
            csv_path,
            package,
            operation,
            overwrite=False,
            model_dir="ct2-test",
        )
        self.assertTrue(result["ok"])
        summary = json.loads((package / ".mt" / "trace_summary.json").read_text(encoding="utf-8"))
        translation_metrics = summary["measurements"]["translation"]
        self.assertEqual(translation_metrics["candidate_count"], 3)
        self.assertEqual(translation_metrics["translated"], 3)
        self.assertEqual(
            translation_metrics["provenance_counts"],
            {"model": 1, "deterministic_policy": 1, "existing_translation": 1},
        )
        connection = sqlite3.connect(package / ".mt" / "traceability.sqlite3")
        try:
            rows_by_key = {
                row[0]: row[1:]
                for row in connection.execute(
                    "SELECT entry_key, translation, translation_hash, model_engine, model_revision "
                    "FROM trace_entries ORDER BY entry_key"
                )
            }
            events = [
                json.loads(row[0])
                for row in connection.execute(
                    "SELECT payload_json FROM trace_events "
                    "WHERE stage = ? AND event_status = 'PASS'",
                    (STAGE_TRANSLATED,),
                )
            ]
        finally:
            connection.close()
        self.assertEqual(rows_by_key[fixed.key][0], "Đạt ")
        self.assertEqual(rows_by_key[fixed.key][1], hashlib.sha256("Đạt ".encode("utf-8")).hexdigest())
        self.assertEqual(rows_by_key[kept.key][0], kept.source_text)
        self.assertEqual(rows_by_key[frozen.key][0], "Đã có")
        self.assertEqual(rows_by_key[fixed.key][2], "CTranslate2/OPUS-MT")
        self.assertTrue(rows_by_key[fixed.key][3])
        self.assertEqual(rows_by_key[kept.key][2], "deterministic_policy")
        self.assertEqual(rows_by_key[frozen.key][2:], ("existing_translation", "frozen"))
        self.assertEqual(
            sorted(event["provenance"] for event in events),
            ["deterministic_policy", "existing_translation", "model"],
        )

    def test_traced_patch_syncs_exact_csv_without_embedded_policy_override(self):
        entry = _entry("patch-csv-sync")
        entry.patch_proof = {
            "reader": True,
            "writer": True,
            "preflight": True,
            "reopen": True,
            "semantic_verify": True,
        }
        package = self.root / "patch-csv-sync-package"
        write_package(
            str(package),
            [entry],
            [],
            {"mode": "deep"},
            separate_review=True,
            enforce_symmetry=True,
        )
        fields, rows = read_csv_rows_file(package / "translation.csv")
        rows[0]["translation"] = "Bản dịch cuối "
        write_csv_rows_file(package / "translation.csv", fields, rows)
        manifest = json.loads((package / "manifest.json").read_text(encoding="utf-8"))
        trace = TraceStore.for_package(package, manifest)
        trace.start_run(metadata={"pipeline": "patch"})
        actions: dict[str, dict] = {}
        try:
            actions, _metadata = _trace_patch_start(
                trace,
                manifest,
                package / "translation.csv",
            )
            self.assertEqual(len(actions), 2)
        finally:
            try:
                for action in actions.values():
                    trace.finish_event(action["action_id"], EVENT_COMPLETED)
                trace.finish_run(EVENT_COMPLETED)
            finally:
                trace.close()
        connection = sqlite3.connect(package / ".mt" / "traceability.sqlite3")
        try:
            row = connection.execute(
                "SELECT translation, translation_hash, model_engine, model_revision "
                "FROM trace_entries WHERE entry_key = ?",
                (entry.key,),
            ).fetchone()
        finally:
            connection.close()
        self.assertEqual(
            row,
            (
                "Bản dịch cuối ",
                hashlib.sha256("Bản dịch cuối ".encode("utf-8")).hexdigest(),
                None,
                None,
            ),
        )

    def test_traced_patch_fails_when_per_target_readback_evidence_is_missing(self):
        entry = _entry("patch-missing-readback")
        entry.patch_proof = {
            "reader": True,
            "writer": True,
            "preflight": True,
            "reopen": True,
            "semantic_verify": True,
        }
        package = self.root / "patch-package"
        write_package(
            str(package),
            [entry],
            [],
            {"mode": "deep"},
            separate_review=True,
            enforce_symmetry=True,
        )
        fields, rows = read_csv_rows_file(package / "translation.csv")
        rows[0]["translation"] = "Xin chào"
        write_csv_rows_file(package / "translation.csv", fields, rows)
        game = self.root / "game"
        game.mkdir()
        (game / "data.assets").write_text("Hello", encoding="utf-8")
        patch_out = self.root / "patch-output"
        completed: list[dict] = []

        def fake_apply(_csv, _manifest, _game, output, _progress):
            destination = Path(output) / "COPY_TO_GAME_ROOT"
            destination.mkdir(parents=True, exist_ok=True)
            (destination / "data.assets").write_text("wrong", encoding="utf-8")
            (Path(output) / "import_report.txt").write_text("patched_lines: 1\n", encoding="utf-8")

        with patch("vntext.app_tasks.apply_translation_package", side_effect=fake_apply):
            run_patch_task(
                package / "translation.csv",
                package / "manifest.json",
                str(game),
                str(patch_out),
                progress=lambda _payload: None,
                log=lambda _message: None,
                complete=completed.append,
                patch_out_override=patch_out,
                include_installer=False,
                write_manifest_file=False,
                enable_trace=True,
            )
        self.assertTrue(completed)
        self.assertFalse(completed[-1]["ok"])
        summary = json.loads((package / ".mt" / "trace_summary.json").read_text(encoding="utf-8"))
        self.assertEqual(summary["run_status_counts"], {EVENT_ABORTED: 1})
        self.assertEqual(summary["root_cause_counts"], {ROOT_CAUSE_PATCH_VERIFY_FAILED: 1})


if __name__ == "__main__":
    unittest.main()
