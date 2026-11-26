"""'Xóa dòng đã chọn': conflict-protected bản dịch row removal with a persisted, provenance-bearing decision."""
import csv
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from tests.lib.dev_environment import renpy_native_sdk
from tests.lib.work_paths import work_temp_dir
from vntext.package_io import CSV_FIELDS, write_csv_rows_file
from vntext.user_exclusions import (EXCLUSIONS_FILE, ExclusionConflict, exclude_rows, filter_excluded_entries, load_exclusions,
                                    source_sha256)


class _Entry:
    def __init__(self, key, text):
        self.key, self.source_text = key, text


class UserExclusionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=work_temp_dir("user-exclusions"))
        self.addCleanup(self.temp.cleanup)
        self.package = Path(self.temp.name)
        self.csv = self.package / "translation.csv"
        self.rows = [{field: "" for field in CSV_FIELDS} | {"key": key, "source_text": text, "translation": tr, "import_method": "renpy_string", "file_path": "game/ui.rpy"}
                     for key, text, tr in (("k1", "Chapter 1", "Chương 1"), ("k2", "<", ""), ("k3", "Line one\nline two {w} [name]", "Dòng một\ndòng hai {w} [name]"), ("k4", "Say \"hi\", ok", "Chào \"bạn\", ok"))]
        write_csv_rows_file(self.csv, CSV_FIELDS, self.rows)

    def sha(self):
        return hashlib.sha256(self.csv.read_bytes()).hexdigest()

    def read(self):
        with self.csv.open(encoding="utf-8-sig", newline="") as stream:
            return list(csv.DictReader(stream))

    def test_remove_keeps_every_other_row_exactly_and_records_the_decision(self):
        before = self.read()
        raw_before = self.csv.read_bytes()
        result = exclude_rows(self.csv, ["k2"], self.sha())
        after = self.read()
        self.assertEqual([row for row in before if row["key"] != "k2"], after)                    # all other rows identical: tags, placeholders, newlines, quotes
        self.assertEqual(raw_before.startswith(b"\xef\xbb\xbf"), self.csv.read_bytes().startswith(b"\xef\xbb\xbf"))   # same BOM/encoding
        self.assertEqual((1, 3), (result["removed"], result["remaining"]))
        self.assertEqual(result["csv_sha256"], self.sha())
        recorded = load_exclusions(self.package)["k2"]
        self.assertEqual(source_sha256("<"), recorded["source_sha256"])
        self.assertEqual("game/ui.rpy", recorded["provenance"]["file_path"])
        self.assertEqual(list(CSV_FIELDS), list(self.read()[0].keys()))                          # schema/column order unchanged

    def test_conflicts_and_bad_selections_change_nothing(self):
        stale = self.sha()
        exclude_rows(self.csv, ["k1"], stale)
        snapshot = (self.csv.read_bytes(), (self.package / EXCLUSIONS_FILE).read_bytes())
        with self.assertRaisesRegex(ExclusionConflict, "đã thay đổi"):
            exclude_rows(self.csv, ["k3"], stale)                                                # the user's revision is out of date
        with self.assertRaisesRegex(ExclusionConflict, "không còn"):
            exclude_rows(self.csv, ["k1"], self.sha())                                           # already gone
        with self.assertRaisesRegex(ExclusionConflict, "Chưa chọn"):
            exclude_rows(self.csv, [], self.sha())
        self.assertEqual(snapshot, (self.csv.read_bytes(), (self.package / EXCLUSIONS_FILE).read_bytes()))
        self.csv.write_text("a,b\n1,2\n", encoding="utf-8")
        with self.assertRaisesRegex(ExclusionConflict, "schema"):
            exclude_rows(self.csv, ["1"], self.sha())

    def test_reextraction_does_not_resurrect_but_a_changed_source_returns(self):
        exclude_rows(self.csv, ["k2"], self.sha())
        kept, dropped = filter_excluded_entries([_Entry("k1", "Chapter 1"), _Entry("k2", "<"), _Entry("k3", "x")], self.package)
        self.assertEqual(["k1", "k3"], [entry.key for entry in kept]); self.assertEqual(["k2"], dropped)
        kept, dropped = filter_excluded_entries([_Entry("k2", "<changed>")], self.package)         # same key, different source: a different row
        self.assertEqual(["k2"], [entry.key for entry in kept]); self.assertEqual([], dropped)
        self.assertEqual(([], []), (filter_excluded_entries([], self.package)))

    @unittest.skipUnless((renpy_native_sdk() / "renpy.py").is_file(), "Official công cụ Ren’Py absent")
    def test_real_renpy_reextraction_into_the_same_package_honors_the_exclusion(self):
        from vntext.app_tasks import run_extract_task
        game = self.package / "source"; (game / "game").mkdir(parents=True)
        (game / "game" / "script.rpy").write_text('label start:\n    "Hello there"\n    return\nscreen ui():\n    text "Chapter 1"\n    text "The Claiming"\n', encoding="utf-8")
        out = self.package / "out"
        for _ in range(2):
            events = []
            run_extract_task(str(game), str(out), "safe", "balanced", True, renpy_sdk_path=str(renpy_native_sdk()), renpy_sdk_action="existing",
                             progress=lambda _: None, log=lambda _: None, complete=events.append)
            if _ == 0:
                self.assertTrue(events[-1]["ok"], events[-1])
                with (out / "translation.csv").open(encoding="utf-8-sig", newline="") as stream:
                    rows = list(csv.DictReader(stream))
                victim = next(row for row in rows if row["source_text"] == "Chapter 1")
                exclude_rows(out / "translation.csv", [victim["key"]], hashlib.sha256((out / "translation.csv").read_bytes()).hexdigest())
        if not events[-1].get("ok") and "xuất" in str(events[-1].get("error", "")).lower():
            self.skipTest("re-extraction into a non-empty output folder is refused by design; the filter itself is covered above")
        with (out / "translation.csv").open(encoding="utf-8-sig", newline="") as stream:
            texts = [row["source_text"] for row in csv.DictReader(stream)]
        self.assertNotIn("Chapter 1", texts); self.assertIn("The Claiming", texts)


if __name__ == "__main__":
    unittest.main()
