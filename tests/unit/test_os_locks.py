"""The trace-store and translation-cache locks are operating-system locks: held by a live process, gone the moment it dies, never decided by a pid."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tests.lib.work_paths import work_temp_dir
from vntext.translation_cache import TranslationCache, TranslationCacheError
from vntext.traceability import TraceStore, TraceStoreError

WORK = work_temp_dir("os-locks")
ROOT = Path(__file__).resolve().parents[2]

HOLDERS = {
    "trace": "from vntext.traceability import TraceStore; keep = TraceStore(sys.argv[2], 'fixture')",
    "cache": "from vntext.translation_cache import TranslationCache; keep = TranslationCache(sys.argv[2])",
}


def _hold(kind: str, package: Path) -> subprocess.Popen:
    code = ";".join(["import sys, time", "sys.path.insert(0, sys.argv[1])", HOLDERS[kind], "print('held', flush=True)", "time.sleep(120)"])
    proc = subprocess.Popen([sys.executable, "-c", code, str(ROOT), str(package)], stdout=subprocess.PIPE, text=True)
    assert proc.stdout.readline().strip() == "held"
    return proc


class OsLockTests(unittest.TestCase):
    def _check(self, kind, opener, error, lock_relative):
        with tempfile.TemporaryDirectory(dir=WORK) as temp:
            package = Path(temp)
            holder = _hold(kind, package)
            try:
                with self.assertRaises(error) as caught:
                    opener(package)
                self.assertIn("another process", str(caught.exception))
                self.assertNotIn(str(package), str(caught.exception).split("(", 1)[-1])
            finally:
                holder.kill()
                holder.wait()
                holder.stdout.close()
            lock = package / lock_relative
            self.assertTrue(lock.exists())                                    # the dead holder's record is still there ...
            self.assertIn("pid", lock.read_text(encoding="utf-8"))            # ... naming a pid that must not matter
            opener(package).close()                                           # ... and the very next opener gets the lock
            self.assertFalse(lock.exists())

    def test_trace_store_lock_follows_the_process_not_a_pid(self):
        self._check("trace", lambda p: TraceStore(p, "fixture"), TraceStoreError, Path(".mt") / "traceability.lock")

    def test_translation_cache_lock_follows_the_process_not_a_pid(self):
        from vntext.translation_cache import CACHE_DIR_NAME, CACHE_LOCK_NAME
        self._check("cache", lambda p: TranslationCache(p), TranslationCacheError, Path(".mt") / CACHE_DIR_NAME / CACHE_LOCK_NAME)

    def test_a_leftover_lock_file_with_a_live_looking_pid_never_blocks(self):
        for kind, opener, rel in (("trace", lambda p: TraceStore(p, "fixture"), Path(".mt") / "traceability.lock"),):
            with tempfile.TemporaryDirectory(dir=WORK) as temp:
                package = Path(temp)
                (package / ".mt").mkdir()
                for text in ('{"pid": %d}' % os.getpid(), '{"pid": 4, "start": "1"}', "garbage", ""):
                    (package / rel).write_text(text, encoding="utf-8")
                    opener(package).close()

    def test_two_stores_in_one_process_still_exclude_each_other(self):
        with tempfile.TemporaryDirectory(dir=WORK) as temp:
            first = TraceStore(temp, "fixture")
            try:
                with self.assertRaises(TraceStoreError):
                    TraceStore(temp, "fixture")
            finally:
                first.close()
            TraceStore(temp, "fixture").close()

    def test_the_owner_description_is_rewritten_in_place_while_the_lock_is_kept(self):
        with tempfile.TemporaryDirectory(dir=WORK) as temp:
            store = TraceStore(temp, "fixture")
            try:
                store.start_run(metadata={"fixture": "unit"})
                record = json.loads((Path(temp) / ".mt" / "traceability.lock").read_text(encoding="utf-8"))
                self.assertEqual(os.getpid(), record["pid"])
                with self.assertRaises(TraceStoreError):
                    TraceStore(temp, "fixture")
            finally:
                store.close()


if __name__ == "__main__":
    unittest.main()
