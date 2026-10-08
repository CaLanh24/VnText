"""Synthetic subprocess checks for silent workers and retained failure evidence."""
import contextlib
import io
import subprocess
import sys
import time
import unittest

from tests.lib.worker_test_lib import WorkerReadError, read_ready, run_task, stop_worker


class WorkerTestLibTests(unittest.TestCase):
    def worker(self, script):
        proc = subprocess.Popen([sys.executable, "-u", "-c", script], stdin=subprocess.PIPE,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self.addCleanup(stop_worker, proc)
        return proc

    def test_silent_ready_obeys_deadline(self):
        proc = self.worker("import time; time.sleep(20)")
        start = time.monotonic()
        with self.assertRaises(WorkerReadError) as failure:
            read_ready(proc, timeout=0.15)
        self.assertLess(time.monotonic() - start, 2)
        self.assertEqual(failure.exception.events, [])

    def test_silent_task_retains_and_streams_error(self):
        proc = self.worker('import time; print(\'{"type":"ready"}\',flush=True); input(); '
                           'print(\'{"type":"error","error":"synthetic failure"}\',flush=True); time.sleep(20)')
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            read_ready(proc, timeout=3)
            with self.assertRaises(WorkerReadError) as failure:
                run_task(proc, "x", "translate", {}, timeout=0.15)
        self.assertEqual(failure.exception.events[-1]["error"], "synthetic failure")
        self.assertIn("WORKER_RUN", output.getvalue())
        self.assertIn("synthetic failure", output.getvalue())

    def test_failed_complete_blocks_patch_before_write(self):
        proc = self.worker('print(\'{"type":"ready"}\',flush=True); input(); '
                           'print(\'{"type":"complete","id":"x","ok":false,"error":"blocked"}\',flush=True)')
        read_ready(proc, timeout=3)
        events = run_task(proc, "x", "translate", {}, timeout=3)
        self.assertIs(events[-1]["ok"], False)
        with self.assertRaises(WorkerReadError) as failure:
            run_task(proc, "p", "patch", {}, prerequisites=(events[-1],))
        self.assertEqual(failure.exception.events[-1]["error"], "blocked")
        with self.assertRaises(WorkerReadError):
            run_task(proc, "p", "patch", {}, prerequisites=({"type": "complete", "ok": True,
                                                             "complete": False},))

    def test_flood_evidence_is_bounded_and_reader_stops(self):
        proc = self.worker('import time; print(\'{"type":"ready"}\',flush=True); input(); '
                           '[print(\'{"type":"log","message":"\'+"x"*1000+\'"}\',flush=True) for _ in range(10000)]; time.sleep(20)')
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            read_ready(proc, timeout=3)
            with self.assertRaises(WorkerReadError) as failure:
                run_task(proc, "flood", "sample", {}, timeout=0.1)
        self.assertLessEqual(len(failure.exception.events), 64)
        self.assertLess(len(output.getvalue().encode()), 70000)
        stop_worker(proc)
        self.assertFalse(proc._worker_reader.is_alive())
