import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tests.lib.work_paths import work_temp_dir
from vntext.extract_output import refresh_extract

WORK = work_temp_dir("extract-output-refresh")


class ExtractOutputRefreshTests(unittest.TestCase):
    def test_worker_preserves_verified_subset_scope_in_terminal_event(self):
        from vntext_worker.task_runners import _make_callbacks
        with patch("vntext_worker.protocol.emit") as emitted:
            _, _, done = _make_callbacks("extract", lambda: False)
            done({"ok": False, "complete": False, "extract_status": "PARTIAL", "severity": "warning", "patch_scope": "VERIFIED_MAIN_SUBSET"})
        self.assertEqual("VERIFIED_MAIN_SUBSET", emitted.call_args.args[0]["patch_scope"])

    def run_case(self, producer, setup=None):
        with tempfile.TemporaryDirectory(dir=WORK) as temp:
            base = Path(temp)
            source = base / "game"
            source.mkdir()
            out = base / "output"
            out.mkdir()
            (out / "translation.csv").write_bytes(b"old CSV")
            (out / "notes.txt").write_bytes(b"user data")
            if setup:
                setup(out)
            results = []
            producer(source, out, results)

    @staticmethod
    def generated(stage, done, log):
        (stage / "translation.csv").write_text("key,source_text,translation\na,Hello,\n", encoding="utf-8")
        (stage / "manifest.json").write_text('{"entries": []}', encoding="utf-8")
        (stage / "extract_status.json").write_text('{"complete": true, "status": "COMPLETE"}', encoding="utf-8")
        done({"ok": True, "complete": True, "summary": str(stage)})

    def test_overwrites_only_generated_outputs_without_old_backup(self):
        def run(source, out, results):
            refresh_extract(source, out, self.generated, results.append, lambda _: None)
            self.assertIn(b"Hello", (out / "translation.csv").read_bytes())
            self.assertEqual(b"user data", (out / "notes.txt").read_bytes())
            self.assertTrue(results[-1]["ok"])
            self.assertEqual(str(out), results[-1]["summary"])
            self.assertFalse(any(p.name.startswith(".vntext-") or p.suffix == ".bak" for p in out.iterdir()))
            self.assertFalse(json.loads((out / ".mt/translate_status.json").read_text())["complete"])
        self.run_case(run)

    def test_failed_generation_preserves_csv_and_never_leaves_ready_status(self):
        def run(source, out, results):
            refresh_extract(source, out, lambda s, done, log: done({"ok": False, "error": "SDK failed", "renpy_sdk_missing": True}), results.append, lambda _: None)
            self.assertEqual(b"old CSV", (out / "translation.csv").read_bytes())
            self.assertTrue(results[-1]["renpy_sdk_missing"])
            self.assertFalse(json.loads((out / "extract_status.json").read_text())["complete"])
        self.run_case(run)

    def test_directory_collision_is_preserved(self):
        def run(source, out, results):
            def generate(stage, done, log):
                self.generated(stage, done, log)
                (stage / "keep").write_bytes(b"generated")
            with self.assertRaisesRegex(ValueError, "directory"):
                refresh_extract(source, out, generate, results.append, lambda _: None)
            self.assertEqual(b"private", (out / "keep/private.txt").read_bytes())
            self.assertFalse(json.loads((out / "extract_status.json").read_text())["complete"])
        def setup(out):
            (out / "keep").mkdir()
            (out / "keep/private.txt").write_bytes(b"private")
        self.run_case(run, setup)

    def test_overlap_refused_before_writing(self):
        with tempfile.TemporaryDirectory(dir=WORK) as temp:
            root = Path(temp)
            source = root / "game"
            source.mkdir()
            with self.assertRaisesRegex(ValueError, "Thư mục xuất"):
                refresh_extract(source, root, self.generated, lambda _: None, lambda _: None)
            self.assertEqual([source], list(root.iterdir()))

    def test_external_csv_change_is_not_overwritten(self):
        import vntext.extract_output as output
        def run(source, out, results):
            original = output._write
            def write(path, data, expected):
                if path.name == "translation.csv":
                    path.write_bytes(b"external edit")
                return original(path, data, expected)
            with patch.object(output, "_write", side_effect=write), self.assertRaisesRegex(ValueError, "externally"):
                refresh_extract(source, out, self.generated, results.append, lambda _: None)
            self.assertEqual(b"external edit", (out / "translation.csv").read_bytes())
            self.assertFalse(json.loads((out / "extract_status.json").read_text())["complete"])
        self.run_case(run)

    def test_csv_changed_while_producing_is_preserved(self):
        def run(source, out, results):
            def generate(stage, done, log):
                self.generated(stage, done, log)
                (out / "translation.csv").write_bytes(b"edit during extract")
            with self.assertRaisesRegex(ValueError, "externally"):
                refresh_extract(source, out, generate, results.append, lambda _: None)
            self.assertEqual(b"edit during extract", (out / "translation.csv").read_bytes())
        self.run_case(run)

    def test_completion_is_after_releasing_package_lock(self):
        def run(source, out, results):
            def done(result):
                self.assertFalse((out / ".vntext-extract.lock").exists())
                results.append(result)
            refresh_extract(source, out, self.generated, done, lambda _: None)
        self.run_case(run)

    def test_trace_writer_refuses_an_active_extraction(self):
        from vntext.traceability import TraceStore, TraceStoreError
        def run(source, out, results):
            def generate(stage, done, log):
                with self.assertRaisesRegex(TraceStoreError, "extraction"):
                    TraceStore(out, "fixture")
                self.generated(stage, done, log)
            refresh_extract(source, out, generate, results.append, lambda _: None)
            self.assertFalse((out / ".mt/traceability.lock").exists())
        self.run_case(run)

    def test_renpy_installer_hashes_each_source_file_once(self):
        import vntext.patch_output as output
        with tempfile.TemporaryDirectory(dir=WORK) as temp:
            root = Path(temp)
            game = root / "game"
            (game / "game").mkdir(parents=True)
            source = game / "game/script.rpy"
            source.write_bytes(b"fixture")
            patch_root = root / "patch"
            payload = patch_root / "COPY_TO_GAME_ROOT/game/tl/vietnamese/vntext.rpy"
            payload.parent.mkdir(parents=True)
            payload.write_bytes(b"overlay")
            entry = {"file_path": "game/script.rpy"}
            with patch.object(output, "_sha256_file", wraps=output._sha256_file) as hashed:
                output.write_renpy_patch_manifest(patch_root, game, "test", {"entries": [entry] * 100})
            self.assertEqual(1, sum(call.args[0] == source for call in hashed.call_args_list))

    def test_stale_extract_lock_recovered_without_removing_user_files(self):
        def run(source, out, results):
            (out / ".vntext-extract.lock").write_text('{"pid": 999999999}', encoding="utf-8")
            refresh_extract(source, out, self.generated, results.append, lambda _: None)
            self.assertEqual(b"user data", (out / "notes.txt").read_bytes())
            self.assertTrue(results[-1]["ok"])
        self.run_case(run)

    def test_lock_write_failure_does_not_leak_a_lock_or_change_csv(self):
        def run(source, out, results):
            with patch("vntext.extract_output.os.write", side_effect=OSError("disk full")), self.assertRaises(OSError):
                refresh_extract(source, out, self.generated, results.append, lambda _: None)
            self.assertFalse((out / ".vntext-extract.lock").exists())
            self.assertEqual(b"old CSV", (out / "translation.csv").read_bytes())
        self.run_case(run)
