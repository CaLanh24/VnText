import json
from pathlib import Path
import shutil
import tracemalloc
import unittest

from tests.lib.work_paths import work_temp_dir
from tests.tools import cleanup_work_artifacts as cleanup


def registry(extra_records, epoch_ids=("a", "b")):
    artifacts = [{"id": "run:%d" % i, "path": "C:\\x\\%d" % i, "lifecycle": "MISSING", "purpose": "p" * 60} for i in range(extra_records)]
    artifacts += [{"id": cleanup.EPOCH_RECORD_PREFIX + e, "path": "C:\\epochs\\" + e, "lifecycle": "RETAINED"} for e in epoch_ids]
    return {"version": 2, "schema_version": 2, "artifacts": artifacts, "archive": [], "prospective_epoch": {"epoch_id": "e1", "source_sha": "0" * 40}}


class EpochChainMemoryTests(unittest.TestCase):
    def setUp(self):
        self.root = work_temp_dir("cleanup-verify-memory") / self._testMethodName
        shutil.rmtree(self.root, ignore_errors=True)
        self.root.mkdir(parents=True)
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        self.saved = (cleanup._TXN_DEPTH, cleanup._memo_allowed)
        cleanup._TXN_DEPTH = 1
        cleanup._memo_allowed = lambda path: True            # the epoch snapshot directory rule is covered elsewhere; here the memo itself is under test
        cleanup._clear_integrity_cache()
        self.addCleanup(self.restore)

    def restore(self):
        cleanup._TXN_DEPTH, cleanup._memo_allowed = self.saved
        cleanup._clear_integrity_cache()

    def write(self, name, document):
        path = self.root / name
        path.write_text(json.dumps(document), encoding="utf-8")
        return path

    def test_projection_keeps_exactly_what_the_chain_verifies(self):
        document = registry(500)
        projected = cleanup._project_epoch_chain_manifest(document)
        self.assertEqual({k: v for k, v in document.items() if k != "artifacts"}, {k: v for k, v in projected.items() if k != "artifacts"})
        self.assertEqual([r for r in document["artifacts"] if r["id"].startswith(cleanup.EPOCH_RECORD_PREFIX)], projected["artifacts"])
        self.assertEqual(502, len(document["artifacts"]))                                   # the input is not mutated
        self.assertEqual([], cleanup._epoch_manifest_shape(projected))                      # shape check still passes
        tampered = json.loads(json.dumps(document))
        tampered["artifacts"][-1]["lifecycle"] = "DISPOSABLE"
        self.assertNotEqual(projected["artifacts"], cleanup._project_epoch_chain_manifest(tampered)["artifacts"])      # a changed epoch record is still visible
        for odd in ({"artifacts": "not a list"}, {"artifacts": None}, ["x"], 7):
            self.assertEqual(odd, cleanup._project_epoch_chain_manifest(odd))               # malformed shapes pass through so the existing checks fail closed
        self.assertIn("manifest_artifacts_and_archive_must_be_lists", cleanup._epoch_manifest_shape(cleanup._project_epoch_chain_manifest({"version": 2, "schema_version": 2, "artifacts": "x"})))

    def test_invalid_json_still_raises_like_before(self):
        bad = self.root / "bad.json"
        bad.write_text("{not json", encoding="utf-8")
        with self.assertRaises(json.JSONDecodeError):
            cleanup._read_json_cached(bad, project=cleanup._project_epoch_chain_manifest)

    def test_many_large_previous_registries_do_not_accumulate_in_memory(self):
        paths = [self.write("r%d.json" % i, registry(20000, epoch_ids=("e%d" % i,))) for i in range(30)]       # ~30 x 3 MB of registry text
        self.assertGreater(paths[0].stat().st_size, 2_000_000)
        tracemalloc.start()
        try:
            before, _ = tracemalloc.get_traced_memory()
            for p in paths:
                projected = cleanup._read_json_cached(p, project=cleanup._project_epoch_chain_manifest)
                self.assertEqual(1, len(projected["artifacts"]))
            retained, peak = tracemalloc.get_traced_memory()
        finally:
            tracemalloc.stop()
        self.assertLess(retained - before, 6 * 1024 * 1024, "retained memo growth over 30 large registries")           # unbounded caching kept every parsed registry (~10x the file size each)
        self.assertLess(peak - before, 120 * 1024 * 1024, "transient peak for one parse")
        self.assertLessEqual(cleanup._JSON_MEMO_BYTES, cleanup.JSON_MEMO_MAX_TOTAL_BYTES)
        again = cleanup._read_json_cached(paths[0], project=cleanup._project_epoch_chain_manifest)                       # a repeat is served from the small projection memo
        self.assertEqual([cleanup.EPOCH_RECORD_PREFIX + "e0"], [r["id"] for r in again["artifacts"]])

    def test_unprojected_large_documents_are_parsed_on_demand_and_never_cached(self):
        big = self.write("big.json", registry(30000))
        self.assertGreater(big.stat().st_size, cleanup.JSON_MEMO_MAX_SOURCE_BYTES)
        misses = cleanup.INTEGRITY_STATS["json_misses"]
        for _ in range(2):
            self.assertEqual(30002, len(cleanup._read_json_cached(big)["artifacts"]))
        self.assertEqual(misses + 2, cleanup.INTEGRITY_STATS["json_misses"])              # no hit: it was not retained
        small = self.write("small.json", {"a": 1})
        cleanup._read_json_cached(small); cleanup._read_json_cached(small)
        self.assertEqual(misses + 3, cleanup.INTEGRITY_STATS["json_misses"])              # small documents are still memoised
        cleanup._clear_integrity_cache()
        self.assertEqual(0, cleanup._JSON_MEMO_BYTES)


if __name__ == "__main__":
    unittest.main()
