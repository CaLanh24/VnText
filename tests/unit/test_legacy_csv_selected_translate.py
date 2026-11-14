"""A CSV written by an OLDER VNText (static screen candidates listed as review rows) must not force the user to triage syntax:
selected translate (real OPUS-MT route) drafts the human row, machine syntax rows are excluded automatically and audited, nothing else changes."""
import csv
import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path

from tests.lib.work_paths import work_temp_dir
from vntext.package_io import CSV_FIELDS, write_csv_rows_file
from vntext.user_exclusions import EXCLUSIONS_FILE, exclude_machine_technical, load_exclusions

ROOT = Path(__file__).resolve().parents[2]
MODEL_DIR = Path(os.environ.get("VNTEXT_CT2_MODEL", str(ROOT / ".dev-env" / "cache" / "models" / "opus-mt-en-vi-int8")))

DIALOGUE = "The innkeeper waved from behind the counter.\nPlease take a seat, traveler."
ROWS = [  # key, source, translation, method, review_only
    ("d1", DIALOGUE, "Chủ quán vẫy tay từ sau quầy.\nXin mời ngồi, lữ khách.", "renpy_dialogue", False),
    ("s1", "Mute All", "", "renpy_screen_candidate", True),
    ("s2", "<", "", "renpy_screen_candidate", True),
    ("s3", "{#auto_page}A", "", "renpy_screen_candidate", True),
    ("s4", "[page]", "", "renpy_screen_candidate", True),
    ("s5", "[config.name!t]", "", "renpy_screen_candidate", True),
]


class LegacyCsvSelectedTranslateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=work_temp_dir("legacy-csv"))
        self.addCleanup(self.temp.cleanup)
        self.package = Path(self.temp.name)
        self.csv = self.package / "translation.csv"
        rows = [{field: "" for field in CSV_FIELDS} | {"key": k, "source_text": s, "translation": t, "import_method": m, "file_path": "game/screens.rpy",
                    "backend": "renpy_static_ui_inventory" if _r else "renpy_loose_source"} for k, s, t, m, _r in ROWS]
        write_csv_rows_file(self.csv, CSV_FIELDS, rows)
        entries = [{"key": k, "source_text": s, "file_path": "game/screens.rpy", "import_method": m, "review_only": r, "safety": "review" if r else "safe",
                    "locator": {"line": 1}, "backend": "renpy_static_ui_inventory" if r else "renpy_loose_source"} for k, s, _t, m, r in ROWS]
        (self.package / "manifest.json").write_text(json.dumps({"format": 2, "unified_document": True, "version": "0.1.17", "entries": entries, "technical_skipped": [], "stats": {}}), encoding="utf-8")

    def rows(self):
        with self.csv.open(encoding="utf-8-sig", newline="") as stream:
            return list(csv.DictReader(stream))

    def test_machine_syntax_is_excluded_and_only_human_candidates_remain(self):
        before = {r["key"]: r for r in self.rows()}
        self.assertEqual(4, exclude_machine_technical(self.csv))                                  # "<", "{#auto_page}A", "[page]", "[config.name!t]"
        after = {r["key"]: r for r in self.rows()}
        self.assertEqual({"d1", "s1"}, set(after))                                                  # the human candidate and the dialogue stay
        self.assertEqual(before["d1"], after["d1"]); self.assertEqual(before["s1"], after["s1"])   # untouched content (multiline kept)
        recorded = load_exclusions(self.package)
        self.assertEqual({"s2", "s3", "s4", "s5"}, set(recorded)); self.assertTrue(all(v["reason"] == "machine_technical" for v in recorded.values()))
        self.assertEqual(0, exclude_machine_technical(self.csv))                                    # idempotent

    @unittest.skipUnless((MODEL_DIR / "model.bin").is_file(), "Product OPUS-MT model absent")
    def test_selected_translate_drafts_the_human_row_with_no_triage_and_no_false_review(self):
        from vntext.app_tasks import run_translate_keys_ct2_task
        before = {r["key"]: r for r in self.rows()}
        events = []
        run_translate_keys_ct2_task(self.csv, self.package, ["s1", "s2", "s4"], model_dir=str(MODEL_DIR), progress=lambda _: None, log=lambda _: None, complete=events.append)
        done = events[-1]
        self.assertEqual(0, done["pending"])                                                        # syntax rows are no longer pending work
        self.assertFalse(done["complete"])                                                          # honest: the drafted legacy row has no proven writeback path yet
        self.assertIn("Chạy lại Extract", done["error"]); self.assertIn("không cần duyệt thủ công", done["error"])   # says what fixes it, no triage asked
        self.assertNotIn("Traceback", json.dumps(done))
        after = {r["key"]: r for r in self.rows()}
        self.assertEqual({"d1", "s1"}, set(after))
        self.assertTrue(after["s1"]["translation"].strip())                                         # "Mute All" drafted without any manual step
        self.assertNotIn("�", after["s1"]["translation"])
        self.assertEqual(before["d1"], after["d1"])                                                 # the unselected manual multiline row is byte-for-byte the same
        self.assertTrue((self.package / EXCLUSIONS_FILE).is_file())

    @unittest.skipUnless((MODEL_DIR / "model.bin").is_file(), "Product OPUS-MT model absent")
    def test_a_failed_write_leaves_the_csv_byte_identical_and_reports_a_plain_error(self):
        from unittest.mock import patch
        from vntext.app_tasks import run_translate_keys_ct2_task
        exclude_machine_technical(self.csv)                                                         # the legacy cleanup is its own committed step
        before = self.csv.read_bytes()
        events = []
        real_replace = os.replace
        def failing_replace(src, dst, *a, **k):
            if str(dst).endswith("translation.csv"):
                raise OSError("injected: disk full")
            return real_replace(src, dst, *a, **k)
        with patch("os.replace", failing_replace):
            run_translate_keys_ct2_task(self.csv, self.package, ["s1"], model_dir=str(MODEL_DIR), progress=lambda _: None, log=lambda _: None, complete=events.append)
        self.assertEqual(before, self.csv.read_bytes())                                              # atomic write: nothing half-written, nothing lost
        self.assertFalse(events[-1]["ok"], events[-1])
        self.assertNotIn("Traceback", json.dumps(events[-1]))

    def test_the_draft_is_never_patchable_without_proof(self):
        # The draft row keeps its review/no-proof status: the patch gate still refuses it (guards unchanged); only the translation workflow stopped blocking.
        from vntext.patch_gate import audit_patch_package
        write_csv_rows_file(self.csv, CSV_FIELDS, [{field: "" for field in CSV_FIELDS} | {"key": "s1", "source_text": "Mute All", "translation": "Tắt tiếng tất cả",
                            "import_method": "renpy_screen_candidate", "file_path": "game/screens.rpy", "backend": "renpy_static_ui_inventory"}])
        audit = audit_patch_package(self.csv, self.package / "manifest.json")
        self.assertEqual(0, audit["eligible"])


if __name__ == "__main__":
    unittest.main()
