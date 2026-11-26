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

    # ---- revision CAS (stale before MT / during MT), transactional exclusions, legacy selected completion ----

    @unittest.skipUnless((MODEL_DIR / "model.bin").is_file(), "Product OPUS-MT model absent")
    def test_selected_human_and_removed_machine_rows_have_separate_terminal_outcomes(self):
        done = self.run_selected(["s1", "s2", "s4"], self.sha())
        self.assertTrue(done["ok"] and done["complete"], done)
        self.assertEqual(done["selected_counts"], {"applied": 1, "skipped": 2, "review": 0, "failed": 0})
        outcomes = {row["key"]: row for row in done["selected_outcomes"]}
        self.assertEqual(outcomes["s2"]["reason"], "machine_technical_excluded")
        self.assertEqual(outcomes["s4"]["status"], "skipped")
        self.assertNotIn("s2", {row["key"] for row in self.rows()})
    def sha(self):
        return hashlib.sha256(self.csv.read_bytes()).hexdigest()

    def external_manual_edit(self):
        rows = self.rows()
        for row in rows:
            if row["key"] == "d1":
                row["translation"] = "Sửa tay bên ngoài ứng dụng."
        write_csv_rows_file(self.csv, CSV_FIELDS, rows)

    def run_selected(self, keys, expected, *, progress=lambda _: None):
        from vntext.app_tasks import run_translate_keys_ct2_task
        events = []
        run_translate_keys_ct2_task(self.csv, self.package, keys, model_dir=str(MODEL_DIR), selection_only=True, expected_csv_sha256=expected,
                                    progress=progress, log=lambda _: None, complete=events.append)
        return events[-1]

    def test_stale_revision_before_mt_refuses_with_no_mutation_including_machine_exclusions(self):
        opened = self.sha()
        self.external_manual_edit()                                                                 # disk changed AFTER the user's selection
        csv_before, manifest_before = self.csv.read_bytes(), (self.package / "manifest.json").read_bytes()
        done = self.run_selected(["s1", "s2", "s4"], opened)                                          # s2/s4/... would otherwise be auto-excluded
        self.assertFalse(done["ok"], done)
        self.assertIn("không thay đổi gì", done["error"])
        self.assertEqual(csv_before, self.csv.read_bytes())                                           # byte-identical: the external edit survives
        self.assertEqual(manifest_before, (self.package / "manifest.json").read_bytes())
        self.assertFalse((self.package / EXCLUSIONS_FILE).exists())                                   # no automatic exclusion recorded for a stale view
        self.assertEqual(6, len(self.rows()))
        self.assertNotIn("Traceback", json.dumps(done))

    @unittest.skipUnless((MODEL_DIR / "model.bin").is_file(), "Product OPUS-MT model absent")
    def test_external_change_during_mt_is_never_overwritten(self):
        exclude_machine_technical(self.csv)
        opened = self.sha()
        changed = []

        def edit_midway(_progress):
            if not changed:
                changed.append(True)
                self.external_manual_edit()                                                           # a second writer lands while inference runs
        done = self.run_selected(["s1"], opened, progress=edit_midway)
        self.assertTrue(changed)
        self.assertFalse(done["ok"], done)
        self.assertIn("ngoài ứng dụng", done["error"])
        rows = {r["key"]: r for r in self.rows()}
        self.assertEqual("Sửa tay bên ngoài ứng dụng.", rows["d1"]["translation"])                     # the external edit is intact
        self.assertEqual("", rows["s1"]["translation"])                                               # our draft was NOT written over a revision we did not see

    @unittest.skipUnless((MODEL_DIR / "model.bin").is_file(), "Product OPUS-MT model absent")
    def test_selected_only_legacy_draft_succeeds_and_reports_patch_omissions_without_proof(self):
        done = self.run_selected(["s1"], self.sha())
        self.assertTrue(done["ok"] and done["complete"], done)                                         # the selected draft is the whole job
        self.assertEqual(1, done["selected_done"])
        self.assertEqual("", done["error"])
        self.assertIn("Bản nháp đã lưu", done["summary"])
        self.assertIn("bỏ qua 1 dòng khác", done["summary"])
        self.assertTrue({r["key"]: r for r in self.rows()}["s1"]["translation"].strip())
        from vntext.patch_gate import audit_patch_package
        self.assertEqual(1, audit_patch_package(self.csv, self.package / "manifest.json")["eligible"])  # only the dialogue row d1; the drafted legacy row s1 is still not patch proof

    def test_failed_csv_write_rolls_the_exclusion_ledger_back_and_next_status_is_unchanged(self):
        from unittest.mock import patch
        from vntext.mt_ct2_status import _load_human_review_keys
        from vntext.user_exclusions import ExclusionConflict, exclude_rows, filter_excluded_entries
        ledger = self.package / EXCLUSIONS_FILE
        real_replace = os.replace

        def failing(src, dst, *a, **k):
            if str(dst).endswith("translation.csv"):
                raise OSError("injected: disk full")
            return real_replace(src, dst, *a, **k)
        # (a) no ledger yet: a failed operation leaves none behind
        before = self.csv.read_bytes()
        with patch("os.replace", failing), self.assertRaises(OSError):
            exclude_rows(self.csv, ["s2"], self.sha())
        self.assertEqual(before, self.csv.read_bytes())
        self.assertFalse(ledger.exists())
        self.assertEqual([], filter_excluded_entries([{"key": "s2", "source_text": "<"}], self.package)[1])   # the next extraction would NOT suppress s2
        # (b) an existing ledger survives byte-for-byte
        exclude_rows(self.csv, ["s3"], self.sha())
        ledger_before, csv_before = ledger.read_bytes(), self.csv.read_bytes()
        keys_before = _load_human_review_keys(self.package)
        with patch("os.replace", failing), self.assertRaises(OSError):
            exclude_rows(self.csv, ["s2"], self.sha())
        self.assertEqual(ledger_before, ledger.read_bytes())
        self.assertEqual(csv_before, self.csv.read_bytes())
        self.assertEqual(keys_before, _load_human_review_keys(self.package))                          # review counts unchanged by the failed attempt
        probe = [{"key": "s3", "source_text": "{#auto_page}A"}, {"key": "s2", "source_text": "<"}]
        self.assertEqual(["s3"], filter_excluded_entries(probe, self.package)[1])
        # (c) a rollback that itself fails is reported, never silent
        state = {"n": 0}

        def rollback_fails(src, dst, *a, **k):
            if str(dst).endswith("translation.csv"):
                raise OSError("injected csv")
            if str(dst).endswith(EXCLUSIONS_FILE):
                state["n"] += 1
                if state["n"] == 2:
                    raise OSError("injected rollback")
            return real_replace(src, dst, *a, **k)
        with patch("os.replace", rollback_fails), self.assertRaises(ExclusionConflict) as caught:
            exclude_rows(self.csv, ["s2"], self.sha())
        self.assertIn(EXCLUSIONS_FILE, str(caught.exception))

    def test_automatic_exclusion_failure_refuses_translation_and_persists_nothing(self):
        from unittest.mock import patch
        before = self.csv.read_bytes()
        real_replace = os.replace

        def failing(src, dst, *a, **k):
            if str(dst).endswith("translation.csv"):
                raise OSError("injected: disk full")
            return real_replace(src, dst, *a, **k)
        with patch("os.replace", failing):
            done = self.run_selected(["s1"], self.sha())
        self.assertFalse(done["ok"], done)
        self.assertEqual(before, self.csv.read_bytes())
        self.assertFalse((self.package / EXCLUSIONS_FILE).exists())
        self.assertNotIn("Traceback", json.dumps(done))

    def test_worker_forwards_the_opened_revision_to_the_selected_task(self):
        from unittest.mock import patch
        from vntext_worker.task_runners import run_translate_worker
        seen = {}
        with patch("vntext_worker.task_runners.run_translate_keys_ct2_task", lambda *a, **k: seen.update(k)):
            run_translate_worker("t1", {"csv_path": str(self.csv), "keys": ["s1"], "selection_only": True, "expected_csv_sha256": "ABC123", "model": "ct2",
                                        "model_dir": str(MODEL_DIR)}, lambda: False)
        self.assertEqual("ABC123", seen.get("expected_csv_sha256"))
        self.assertIs(True, seen.get("selection_only"))

    @unittest.skipUnless((MODEL_DIR / "model.bin").is_file(), "Product OPUS-MT model absent")
    def test_generic_screen_labels_through_the_real_route_are_translated_or_documented_keeps(self):
        # Real OPUS-MT route + the generic UI-label catalog, no title-specific rule: each row ends non-empty with no corruption.
        from vntext.mt_classify import classify_row_authoritative
        labels = ["Chapter 1", "Mute All", "Settings", "Prologue", "Epilogue", "Quit"]
        rows = [{field: "" for field in CSV_FIELDS} | {"key": f"g{i}", "source_text": s, "import_method": "renpy_screen_text", "context": "UI:screen",
                                                       "file_path": "game/screens.rpy", "backend": "renpy_loose_source"} for i, s in enumerate(labels)]
        write_csv_rows_file(self.csv, CSV_FIELDS, rows)
        entries = [{"key": r["key"], "source_text": r["source_text"], "file_path": "game/screens.rpy", "import_method": "renpy_screen_text", "safety": "safe",
                    "locator": {"line": 1}, "backend": "renpy_loose_source"} for r in rows]
        (self.package / "manifest.json").write_text(json.dumps({"format": 2, "unified_document": True, "version": "0.1.17", "entries": entries, "technical_skipped": [], "stats": {}}), encoding="utf-8")
        done = self.run_selected([r["key"] for r in rows], self.sha())
        self.assertTrue(done["ok"], done)
        got = {r["source_text"]: r["translation"] for r in self.rows()}
        self.assertEqual("Chương 1", got["Chapter 1"])
        self.assertEqual("Tắt tiếng tất cả", got["Mute All"])
        self.assertEqual("Cài đặt", got["Settings"])
        self.assertEqual("Lời mở đầu", got["Prologue"])                                                # exact standard UI labels, proven UI context only
        self.assertEqual("Lời kết", got["Epilogue"])
        self.assertEqual("Thoát", got["Quit"])
        self.assertEqual("ui_label_fixed", classify_row_authoritative(rows[3])[0])
        for text in got.values():
            self.assertTrue(text.strip())
            self.assertNotIn("�", text)

    def test_standard_labels_are_context_bounded_dialogue_and_names_are_never_rewritten(self):
        from vntext.mt_classify import classify_row_authoritative
        from vntext.ui_labels import resolve_ui_label_translation

        def row(text, context, method):
            return {field: "" for field in CSV_FIELDS} | {"key": "k", "source_text": text, "import_method": method, "context": context, "file_path": "game/script.rpy"}
        for label, expected in (("Prologue", "Lời mở đầu"), ("Epilogue", "Lời kết"), ("Quit", "Thoát"), ("PROLOGUE", "LỜI MỞ ĐẦU")):
            self.assertEqual(expected, resolve_ui_label_translation(label, "UI:screen"))
            self.assertIsNone(resolve_ui_label_translation(label, ""))                                # unknown context
            self.assertIsNone(resolve_ui_label_translation(label, "dialogue:Eileen"))                  # story dialogue
            self.assertIsNone(resolve_ui_label_translation(label, "UI:screen:choice"))                 # menu choice
        for text in ("The Prologue", "Prologue [name]", "Prologue {b}one{/b}", "Prologue\nTwo", "Prologue: Kai"):
            self.assertIsNone(resolve_ui_label_translation(text, "UI:screen"))                         # not an exact standalone label: tokens/newline/prose untouched
        self.assertEqual("copy_literal", classify_row_authoritative(row("Prologue", "dialogue:Eileen", "renpy_dialogue"))[0])   # a proper name in dialogue keeps its form
        self.assertEqual("ui_label_fixed", classify_row_authoritative(row("Prologue", "UI:screen", "renpy_screen_text"))[0])


if __name__ == "__main__":
    unittest.main()
