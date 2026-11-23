import json
import os
from pathlib import Path
import tempfile
import threading
import time
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
            from vntext.mt_ct2_status import snapshot_translate_status
            self.assertEqual(1, snapshot_translate_status(out)["pending"])
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

    def test_killed_extraction_leftovers_are_swept_and_user_data_is_untouched(self):
        # A forced stop mid-extraction leaves a dead lock, a private staging folder and a half-written temp file.  The next run must recover
        # without touching the previous CSV, user files, or anything it does not own.
        def setup(out):
            (out / ".vntext-extract.lock").write_text(json.dumps({"pid": 2 ** 30}), encoding="utf-8")
            torn = out / ".vntext-extract-deadbeef"
            torn.mkdir()
            (torn / "translation.csv").write_bytes(b"half a CSV")
            (out / ".vntext-new-0123abcd").write_bytes(b"half a write")
            (out / "extract_status.json").write_text('{"status": "RUNNING", "complete": false}', encoding="utf-8")
            (out / ".vntext-mine-not-ours.txt").write_bytes(b"user file with a similar prefix")

        def run(source, out, results):
            refresh_extract(source, out, self.generated, results.append, lambda _: None)
            self.assertTrue(results[-1]["ok"])
            self.assertIn(b"Hello", (out / "translation.csv").read_bytes())
            self.assertEqual(b"user data", (out / "notes.txt").read_bytes())
            self.assertEqual(b"user file with a similar prefix", (out / ".vntext-mine-not-ours.txt").read_bytes())
            self.assertFalse((out / ".vntext-extract-deadbeef").exists())
            self.assertFalse((out / ".vntext-new-0123abcd").exists())
            self.assertFalse((out / ".vntext-extract.lock").exists())
            self.assertTrue(json.loads((out / "extract_status.json").read_text())["complete"])
        self.run_case(run, setup)

    def test_user_cancel_restores_the_previous_status_instead_of_failed(self):
        previous = '{"status": "COMPLETE", "complete": true, "patch_scope": "FULL", "errors": 0}'

        def cancelled(stage, done, log):
            done({"ok": False, "error": "cancelled"})

        def run(source, out, results):
            with self.assertRaises(ValueError):
                refresh_extract(source, out, cancelled, results.append, lambda _: None)
            self.assertEqual(b"old CSV", (out / "translation.csv").read_bytes())
            self.assertEqual(previous, (out / "extract_status.json").read_text())      # the untouched package keeps its own verdict
            self.assertFalse(any(p.name.startswith(".vntext-extract") for p in out.iterdir()))
        self.run_case(run, setup=lambda out: (out / "extract_status.json").write_text(previous))

    def test_user_cancel_on_a_first_extraction_leaves_no_running_marker(self):
        def cancelled(stage, done, log):
            done({"ok": False, "error": "cancelled"})

        def run(source, out, results):
            with self.assertRaises(ValueError):
                refresh_extract(source, out, cancelled, results.append, lambda _: None)
            self.assertFalse((out / "extract_status.json").exists())
        self.run_case(run)

    def test_interrupted_extraction_keeps_the_previous_csv_and_never_reads_as_ready(self):
        def broken(stage, done, log):
            (stage / "translation.csv").write_text("half", encoding="utf-8")
            raise KeyboardInterrupt  # what a stop request looks like to the publisher: the stage is never published

        def run(source, out, results):
            with self.assertRaises(BaseException):
                refresh_extract(source, out, broken, results.append, lambda _: None)
            self.assertEqual(b"old CSV", (out / "translation.csv").read_bytes())
            self.assertFalse(json.loads((out / "extract_status.json").read_text()).get("complete", False))
            self.assertFalse(any(p.name.startswith(".vntext-extract-") for p in out.iterdir()))
        self.run_case(run)

    def test_stale_extract_lock_recovered_without_removing_user_files(self):
        def run(source, out, results):
            (out / ".vntext-extract.lock").write_text('{"pid": 999999999}', encoding="utf-8")
            refresh_extract(source, out, self.generated, results.append, lambda _: None)
            self.assertEqual(b"user data", (out / "notes.txt").read_bytes())
            self.assertTrue(results[-1]["ok"])
        self.run_case(run)

    def _locked_run(self, lock_text, *, age=0, expect_ok=True):
        def run(source, out, results):
            lock = out / ".vntext-extract.lock"
            lock.write_text(lock_text, encoding="utf-8")
            if age:
                import os
                import time
                os.utime(lock, (time.time() - age, time.time() - age))
            if expect_ok:
                refresh_extract(source, out, self.generated, results.append, lambda _: None)
                self.assertTrue(results[-1]["ok"])
                self.assertFalse(lock.exists())
            else:
                with self.assertRaises(ValueError) as caught:
                    refresh_extract(source, out, self.generated, results.append, lambda _: None)
                self.assertIn("Thư mục xuất", str(caught.exception))
                self.assertTrue(lock.exists())
            self.assertEqual(b"user data", (out / "notes.txt").read_bytes())
        self.run_case(run)

    def test_lock_of_recycled_pid_with_other_start_time_is_reclaimed(self):
        import os
        self._locked_run(json.dumps({"pid": os.getpid(), "start": "1"}))

    def test_legacy_lock_whose_pid_now_runs_another_program_is_reclaimed(self):
        import subprocess
        import sys
        import os
        # A live process that is not VNText (cmd/ping style): recycled pid in an old-format lock.
        other = subprocess.Popen(["cmd", "/c", "ping -n 20 127.0.0.1 >nul"] if os.name == "nt" else ["sleep", "20"],
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            self._locked_run(json.dumps({"pid": other.pid}))
        finally:
            other.kill()
            other.wait()

    def test_lock_of_dead_pid_with_start_time_is_reclaimed(self):
        self._locked_run(json.dumps({"pid": 2 ** 30, "start": "123"}))

    @staticmethod
    def _live_python():
        import subprocess
        import sys
        proc = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(0.5)
        return proc

    def test_legacy_lock_is_never_kept_whatever_the_live_pid_is(self):
        # Owner machine 2026-11-23: {"pid": N} (no creation time) kept blocking although nothing ran.  Only 0.1.27 or older wrote that form.
        proc = self._live_python()
        try:
            self._locked_run(json.dumps({"pid": proc.pid}))                  # a live python
            self._locked_run(json.dumps({"pid": proc.pid}), age=3600)        # a live python that started after the lock
        finally:
            proc.kill()
            proc.wait()
        self._locked_run(json.dumps({"pid": os.getpid()}))                   # this very process

    @unittest.skipUnless(os.name == "nt", "needs a Windows system process and exe")
    def test_legacy_lock_of_a_live_process_named_vntext_or_unreadable_is_reclaimed(self):
        import shutil
        import subprocess
        with tempfile.TemporaryDirectory(dir=WORK) as temp:
            exe = Path(temp) / "VNText Studio.exe"
            shutil.copy(Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "ping.exe", exe)
            proc = subprocess.Popen([str(exe), "-n", "30", "127.0.0.1"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            try:
                time.sleep(0.5)
                self._locked_run(json.dumps({"pid": proc.pid}))
            finally:
                proc.kill()
                proc.wait()
        self._locked_run(json.dumps({"pid": 4}))                             # the System process: alive, name and times unreadable

    @staticmethod
    def _hold_lock_in_another_process(out):
        import subprocess
        import sys
        code = ";".join(["import sys, time", "sys.path.insert(0, sys.argv[1])", "from pathlib import Path",
                         "from vntext.extract_output import _take_lock",
                         "_take_lock(Path(sys.argv[2]) / '.vntext-extract.lock')", "print('held', flush=True)", "time.sleep(120)"])
        root = Path(__file__).resolve().parents[2]
        holder = subprocess.Popen([sys.executable, "-c", code, str(root), str(out)], stdout=subprocess.PIPE, text=True)
        assert holder.stdout.readline().strip() == "held"
        return holder

    def test_lock_held_by_another_live_process_is_refused_and_taken_the_moment_it_dies(self):
        # The system lock, not a pid, decides: the holder's record stays in the file after it is killed and still must not block anything.
        def run(source, out, results):
            holder = self._hold_lock_in_another_process(out)
            try:
                with self.assertRaises(ValueError) as caught:
                    refresh_extract(source, out, self.generated, results.append, lambda _: None)
                message = str(caught.exception)
                recorded = json.loads((out / ".vntext-extract.lock").read_text())["pid"]
                self.assertIn(f"PID {recorded}", message)
                self.assertIn("giây tuổi", message)
                self.assertNotIn(str(out), message)
                self.assertTrue((out / ".vntext-extract.lock").exists())
                from vntext.extract_output import extract_lock_held
                self.assertTrue(extract_lock_held(out / ".vntext-extract.lock"))
            finally:
                holder.kill()
                holder.wait()
            self.assertIn(str(recorded), (out / ".vntext-extract.lock").read_text())
            refresh_extract(source, out, self.generated, results.append, lambda _: None)
            self.assertTrue(results[-1]["ok"])
            self.assertFalse((out / ".vntext-extract.lock").exists())
        self.run_case(run)

    def test_lock_file_content_never_decides_ownership(self):
        from vntext.process_identity import owner_record
        proc = self._live_python()
        try:
            for text in ("not json", "", '{"pid": "x"}', '{"pid": 4}', json.dumps({"pid": proc.pid}), json.dumps({"pid": os.getpid()}),
                         json.dumps(owner_record()), json.dumps({"pid": proc.pid, "start": "1"})):
                with self.subTest(content=text[:30]):
                    self._locked_run(text)
        finally:
            proc.kill()
            proc.wait()

    def test_a_leftover_lock_file_nobody_holds_does_not_block_the_trace_writer(self):
        from vntext.traceability import TraceStore
        def run(source, out, results):
            (out / ".vntext-extract.lock").write_text('{"pid": 4}', encoding="utf-8")
            TraceStore(out, "fixture").close()
        self.run_case(run)

    def test_lock_write_failure_does_not_leak_a_lock_or_change_csv(self):
        from vntext.extract_output import extract_lock_held
        def run(source, out, results):
            with patch("vntext.extract_output.os.write", side_effect=OSError("disk full")), self.assertRaises(OSError):
                refresh_extract(source, out, self.generated, results.append, lambda _: None)
            self.assertFalse(extract_lock_held(out / ".vntext-extract.lock"))
            self.assertEqual(b"old CSV", (out / "translation.csv").read_bytes())
        self.run_case(run)

    def test_trace_files_left_by_a_killed_process_do_not_block_a_new_extraction(self):
        # Found by the installed-app smoke: a translation killed or cancelled mid-run leaves .mt/traceability.lock and the SQLite -wal/-shm files; an
        # extraction must still run (they only count while a process really holds the trace lock).
        def run(source, out, results):
            meta = out / ".mt"
            meta.mkdir(exist_ok=True)
            (meta / "traceability.lock").write_text('{"pid": 4, "start": "1"}', encoding="utf-8")
            (meta / "traceability.sqlite3-wal").write_bytes(b"x" * 100)
            (meta / "traceability.sqlite3-shm").write_bytes(b"x" * 100)
            refresh_extract(source, out, self.generated, results.append, lambda _: None)
            self.assertTrue(results[-1]["ok"])
        self.run_case(run)

    def test_a_process_holding_the_trace_lock_still_blocks_the_extraction(self):
        from vntext.traceability import TraceStore

        def run(source, out, results):
            store = TraceStore(out, "fixture")
            try:
                with self.assertRaisesRegex(ValueError, "Gói dịch đang được sử dụng"):
                    refresh_extract(source, out, self.generated, results.append, lambda _: None)
            finally:
                store.close()
        self.run_case(run)

    def test_second_extraction_in_this_process_is_refused_while_the_first_runs_and_the_counter_clears(self):
        import threading
        from vntext import extract_output
        started, release = threading.Event(), threading.Event()

        def slow(stage, done, log):
            started.set()
            release.wait(10)
            self.generated(stage, done, log)

        def run(source, out, results):
            first = threading.Thread(target=lambda: refresh_extract(source, out, slow, results.append, lambda _: None))
            first.start()
            self.assertTrue(started.wait(10))
            try:
                with self.assertRaises(ValueError) as caught:
                    refresh_extract(source, out, self.generated, results.append, lambda _: None)
                self.assertIn("chính tiến trình này", str(caught.exception))
            finally:
                release.set()
                first.join(20)
            self.assertTrue(results[-1]["ok"])
            self.assertFalse((out / ".vntext-extract.lock").exists())
            self.assertEqual(set(), extract_output._HELD_LOCKS)
            refresh_extract(source, out, self.generated, results.append, lambda _: None)      # and the folder is usable again
            self.assertTrue(results[-1]["ok"])
        self.run_case(run)

    def test_failed_extraction_releases_the_in_process_counter(self):
        from vntext import extract_output

        def boom(stage, done, log):
            raise RuntimeError("boom")

        def run(source, out, results):
            with self.assertRaises(RuntimeError):
                refresh_extract(source, out, boom, results.append, lambda _: None)
            self.assertEqual(set(), extract_output._HELD_LOCKS)
            self.assertFalse((out / ".vntext-extract.lock").exists())
        self.run_case(run)

    def test_worker_watchdog_fires_when_its_parent_is_gone(self):
        import subprocess
        import sys
        from vntext.process_identity import watch_parent
        parent = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(0.5)
        fired = threading.Event()
        thread = watch_parent(fired.set, interval=0.1, parent_pid=parent.pid)
        self.assertIsNotNone(thread)
        self.assertFalse(fired.wait(0.5))
        parent.kill()
        parent.wait()
        self.assertTrue(fired.wait(5))

