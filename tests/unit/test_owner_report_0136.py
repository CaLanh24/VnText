"""Owner report on 0.1.35 (real Ren'Py game, Sửa bản dịch 977 rows + Tạo bản Việt hóa), reproduced on a SYNTHETIC Ren'Py layout (no game data):

1. no one-click way to check every untranslated / needs-review row            -> WPF harness (Program.Owner0136.cs) + filters here
2. a hand-translated row kept "Đã dịch · Chưa có đường ghi bản Việt hóa được chứng minh…" (unexplained, no way out)
3. "Dịch đã chọn" changed nothing and said nothing (rows waiting for review were skipped forever)
4. "Cần xem lại 5" with no reason or action per row
5. Tạo bản Việt hóa said 22 ineligible while Sửa bản dịch said 5 (deleted rows and review evidence outside the CSV were counted)
6. Tạo bản Việt hóa failed with "Ren'Py dialogue mapping conflict: <id>" (the game already had a different Vietnamese translation for that line)

Each test is named after the issue it pins.  The SDK/model gated tests skip (never pass) when the official SDK or the product model is absent."""
import csv
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from tests.lib.dev_environment import renpy_native_sdk
from tests.lib.work_paths import work_temp_dir

ROOT = Path(__file__).resolve().parents[2]
MODEL_DIR = Path(os.environ.get("VNTEXT_CT2_MODEL", str(ROOT / ".dev-env" / "cache" / "models" / "opus-mt-en-vi-int8")))
SDK_OK = (renpy_native_sdk() / "renpy.py").is_file()
MODEL_OK = (MODEL_DIR / "model.bin").is_file()
WORK = work_temp_dir("owner-report-0136")
SCRIPT = '''define e = Character("Eileen")
label start:
    "Prologue"
    e "Welcome to the village, traveler."
    e "The river is quiet tonight."
    menu:
        "Take the north road":
            "You go north."
    return
label scene_two:
    e "Hold on tight!"
    e "The lantern is out."
    return
screen ui():
    text "Chapter 1"
    text "Disabled label" substitute False
    textbutton "Return" action NullAction()
'''
OLD_PHRASE = "Chưa có đường ghi bản Việt hóa được chứng minh"
_TEMPLATE: dict = {}


def _rows(path: Path) -> tuple[list[str], list[dict]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        return list(reader.fieldnames or []), list(reader)


def _write_rows(path: Path, fields: list[str], rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\r\n")
        writer.writeheader(); writer.writerows(rows)


@unittest.skipUnless(SDK_OK, "Official công cụ Ren’Py absent")
class OwnerReport0136(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from vntext.app_tasks import run_extract_task
        cls._tmp = tempfile.TemporaryDirectory(dir=WORK)
        base = Path(cls._tmp.name)
        game = base / "game_root"; (game / "game").mkdir(parents=True)
        (game / "game" / "script.rpy").write_text(SCRIPT, encoding="utf-8")
        events = []
        run_extract_task(str(game), str(base / "package"), "safe", "balanced", True, renpy_sdk_path=str(renpy_native_sdk()), renpy_sdk_action="existing",
                         progress=lambda *_: None, log=lambda *_: None, complete=events.append)
        assert (base / "package" / "translation.csv").is_file(), events[-1]
        cls.template = base

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def setUp(self):
        tmp = tempfile.TemporaryDirectory(dir=WORK); self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        shutil.copytree(self.template / "game_root", self.root / "game_root")
        shutil.copytree(self.template / "package", self.root / "package")
        self.game = self.root / "game_root"; self.package = self.root / "package"; self.csv = self.package / "translation.csv"
        self.manifest = json.loads((self.package / "manifest.json").read_text(encoding="utf-8"))
        self.fields, self.rows = _rows(self.csv)
        self.key = {row["source_text"]: row["key"] for row in self.rows}

    # --- helpers -------------------------------------------------------------------------------------------------------------------------
    def translate_by_hand(self, mapping: dict[str, str]):
        for row in self.rows:
            if row["source_text"] in mapping:
                row["translation"] = mapping[row["source_text"]]
        _write_rows(self.csv, self.fields, self.rows)

    def add_review_rows(self, notes: dict[str, str]):
        """Put CSV rows in the review ledger exactly as the CT2 review sink does (row copy + patch_note)."""
        from vntext.mt_ct2_status import _append_review_rows
        _append_review_rows(self.package, [{**row, "translation": "", "patch_note": notes[row["source_text"]]} for row in self.rows if row["source_text"] in notes])

    def native_id(self, text):
        return next(e["locator"]["native_id"] for e in self.manifest["entries"] if e["source_text"] == text)

    def patch(self):
        from vntext.app_tasks import run_patch_task
        done = []
        run_patch_task(self.csv, self.package / "manifest.json", str(self.game), str(self.package), progress=lambda *_: None, log=lambda *_: None,
                       complete=done.append, patch_out_override=self.package / "Patch_Viet_Hoa", include_installer=False, write_manifest_file=False)
        return done[-1]

    # --- 1 -------------------------------------------------------------------------------------------------------------------------------
    def test_issue1_untranslated_and_review_rows_are_distinguishable_for_bulk_selection(self):
        from vntext.csv_editor_api import validate_document
        self.translate_by_hand({"Prologue": "Mở đầu"})
        self.add_review_rows({"The lantern is out.": "MT blocked: content loss; attempt=x"})
        result = validate_document(self.csv)
        untranslated = [r["key"] for r in self.rows if not r["translation"].strip()]
        self.assertEqual("mt_blocked", result["issues_by_key"][self.key["The lantern is out."]])
        self.assertNotIn(self.key["Prologue"], result["issues_by_key"])
        self.assertEqual(len(self.rows) - 1, len(untranslated))

    # --- 2 -------------------------------------------------------------------------------------------------------------------------------
    def test_issue2_hand_translated_review_row_says_save_then_leaves_review_on_save(self):
        from vntext.csv_editor_api import load_document, save_document, validate_document
        from vntext.patch_gate import load_review_only_keys
        key = self.key["The lantern is out."]
        self.add_review_rows({"The lantern is out.": "MT blocked: content loss; attempt=x"})
        rows = [dict(row) for row in self.rows]
        for row in rows:
            if row["key"] == key:
                row["translation"] = "Đèn lồng đã tắt."
        unsaved = validate_document(self.csv, rows)
        self.assertEqual("review_resolved_unsaved", unsaved["issues_by_key"][key])
        self.assertNotIn(OLD_PHRASE, unsaved["issues_display"][key])
        self.assertIn("Lưu", unsaved["issues_display"][key])
        doc = load_document(self.csv)
        saved = save_document(self.csv, self.fields, rows, doc.get("source_sha256"))
        self.assertTrue(saved["ok"], saved)
        self.assertNotIn(key, load_review_only_keys(self.package))                       # the row left the review ledger
        self.assertNotIn(key, validate_document(self.csv)["issues_by_key"])                # and now has no status at all
        from vntext.patch_gate import audit_patch_package
        audit = audit_patch_package(self.csv, self.package / "manifest.json")
        self.assertNotIn(key, {item["key"] for item in audit["items"]})                    # Tạo bản Việt hóa includes it

    def test_issue2_row_without_a_write_route_explains_itself_in_plain_vietnamese(self):
        from vntext.patch_gate import REASON_LABELS_VI, reason_action_vi
        self.assertNotIn(OLD_PHRASE, REASON_LABELS_VI["review_only"])
        self.assertIn("Không ghi được vào game", REASON_LABELS_VI["review_only"])
        self.assertIn("Bỏ qua dòng này", reason_action_vi("review_only"))

    # --- 3 -------------------------------------------------------------------------------------------------------------------------------
    @unittest.skipUnless(MODEL_OK, "Product OPUS-MT model absent")
    def test_issue3_translate_selected_translates_rows_left_waiting_for_review_and_explains_each_row(self):
        from vntext.app_tasks import run_translate_keys_ct2_task
        keys = [self.key["Welcome to the village, traveler."], self.key["The river is quiet tonight."]]
        for human_review, expect_saved in ((True, False), (False, True)):
            events = []
            run_translate_keys_ct2_task(self.csv, self.package, keys, model_dir=str(MODEL_DIR), selection_only=True, human_review_required=human_review,
                                        progress=lambda *_: None, log=lambda *_: None, complete=events.append)
            done = events[-1]
            self.assertTrue(done["ok"], done)
            translated = {row["key"]: row["translation"] for row in _rows(self.csv)[1]}
            self.assertEqual(expect_saved, all(translated[key].strip() for key in keys), (human_review, done))
            self.assertTrue(all(outcome.get("message") for outcome in done["selected_outcomes"]))       # every row says why, in words
            if human_review:
                self.assertIn("duyệt", done["selected_outcomes"][0]["message"])
        from vntext.patch_gate import load_review_only_keys
        self.assertFalse(set(keys) & load_review_only_keys(self.package))                                 # resolved rows left the ledger

    # --- 4 -------------------------------------------------------------------------------------------------------------------------------
    def test_issue4_each_review_row_has_reason_action_and_candidate_and_accepting_it_lowers_the_count(self):
        from vntext.csv_editor_api import load_document, save_document, validate_document
        key = self.key["Hold on tight!"]
        self.add_review_rows({"Hold on tight!": "HUMAN_REVIEW_REQUIRED: candidate=Bám chặt vào!; not auto-promoted",
                              "The lantern is out.": "MT blocked: content loss; attempt=x"})
        inventory = self.package / ".mt" / "blocker_inventory.json"; inventory.parent.mkdir(exist_ok=True)
        inventory.write_text(json.dumps({"rows": [{"key": key, "route": "human_review_required", "candidate": "Bám chặt vào!"}]}), encoding="utf-8")
        before = validate_document(self.csv)
        self.assertEqual("human_review", before["issues_by_key"][key])
        self.assertEqual("Bám chặt vào!", before["review_candidates"][key])
        self.assertIn("Chấp nhận đề xuất", before["issues_action"][key])
        self.assertIn("tự gõ", before["issues_action"][self.key["The lantern is out."]].lower())
        review_before = sum(1 for reason in before["issues_by_key"].values() if reason in {"human_review", "mt_blocked", "review_only"})
        rows = [dict(row) for row in self.rows]
        for row in rows:
            if row["key"] == key:
                row["translation"] = before["review_candidates"][key]                                     # "Chấp nhận đề xuất"
        self.assertTrue(save_document(self.csv, self.fields, rows, load_document(self.csv).get("source_sha256"))["ok"])
        after = validate_document(self.csv)
        review_after = sum(1 for reason in after["issues_by_key"].values() if reason in {"human_review", "mt_blocked", "review_only"})
        self.assertEqual(review_before - 1, review_after)
        self.assertNotIn(key, after["issues_by_key"])

    # --- 5 -------------------------------------------------------------------------------------------------------------------------------
    def test_issue5_patch_count_equals_the_editor_count_and_lists_every_skipped_row_with_a_fix(self):
        from vntext.csv_editor_api import validate_document
        from vntext.patch_gate import audit_patch_package
        from vntext.user_exclusions import exclude_rows
        import hashlib
        self.translate_by_hand({"Prologue": "Mở đầu", "Welcome to the village, traveler.": "Chào mừng đến làng.", "Chapter 1": "Chương 1"})
        self.add_review_rows({"The lantern is out.": "MT blocked: content loss; attempt=x"})
        # the person deletes two untranslated rows
        gone = [self.key["You go north."], self.key["Return"]]
        exclude_rows(self.csv, gone, hashlib.sha256(self.csv.read_bytes()).hexdigest())
        editor = validate_document(self.csv)
        audit = audit_patch_package(self.csv, self.package / "manifest.json")
        fields, rows = _rows(self.csv)
        editor_skipped = sum(1 for row in rows if not row["translation"].strip() or row["key"] in editor["issues_by_key"])
        self.assertEqual(editor_skipped, audit["blocked"])                                   # one number on both screens
        self.assertEqual(editor["patch_eligible"], audit["eligible"])
        self.assertEqual(2, audit["user_excluded"])                                          # deleted rows are not "ineligible"
        self.assertGreaterEqual(audit["outside_csv_review"], 1)                              # the extraction-only review row (not in the CSV)
        self.assertEqual(audit["blocked"], len(audit["items"]))
        self.assertFalse({item["key"] for item in audit["items"]} & set(gone))
        for item in audit["items"]:
            self.assertTrue(item["label"] and item["action"], item)
        self.assertEqual({"mt_blocked", "no_translation"}, {item["reason"] for item in audit["items"]})

    # --- 6 -------------------------------------------------------------------------------------------------------------------------------
    def test_issue6_existing_foreign_translation_is_kept_and_only_that_line_is_skipped(self):
        self.translate_by_hand({"Hold on tight!": "Bám chặt vào!", "The lantern is out.": "Đèn lồng đã tắt.", "Chapter 1": "Chương 1"})
        nid = self.native_id("Hold on tight!")
        tl = self.game / "game" / "tl" / "vietnamese"; tl.mkdir(parents=True)
        foreign = tl / "existing.rpy"
        foreign.write_text(f'translate vietnamese {nid}:\n\n    e "Giữ chặt nhé!"\n', encoding="utf-8")
        before = foreign.read_bytes()
        done = self.patch()
        self.assertTrue(done["ok"], done)                                                    # was: "Ren'Py dialogue mapping conflict: <id>"
        self.assertNotIn("mapping conflict", done.get("error", ""))
        self.assertIn("bản dịch tiếng Việt KHÁC sẵn trong game", done["summary"])
        verification = json.loads((self.package / "Patch_Viet_Hoa" / "patch_verification.json").read_text(encoding="utf-8"))
        self.assertEqual([self.key["Hold on tight!"]], verification["omitted_conflict_keys"])
        self.assertEqual(1, verification["omitted_by_reason"]["existing_translation_conflict"])
        overlay = "\n".join(p.read_text(encoding="utf-8") for p in (self.package / "Patch_Viet_Hoa" / "COPY_TO_GAME_ROOT").rglob("*.rpy"))
        self.assertNotIn(f"translate vietnamese {nid}:", overlay)                            # never a second, competing block
        self.assertIn("Đèn lồng đã tắt.", overlay)                                           # the rest of the patch stands
        self.assertEqual(before, foreign.read_bytes())                                       # the game's own file is untouched

    def test_issue6_line_in_vntexts_own_overlay_is_rewritten_with_the_newer_translation(self):
        self.translate_by_hand({"Hold on tight!": "Bám chặt vào!", "Chapter 1": "Chương 1"})
        first = self.patch()
        self.assertTrue(first["ok"], first)
        # an earlier patch copied into the game by hand (no install receipt), then the person changes one translation
        shutil.copytree(self.package / "Patch_Viet_Hoa" / "COPY_TO_GAME_ROOT", self.game, dirs_exist_ok=True)
        shutil.rmtree(self.package / "Patch_Viet_Hoa")
        self.translate_by_hand({"Hold on tight!": "Giữ thật chặt!", "Chapter 1": "Chương một"})
        second = self.patch()
        self.assertTrue(second["ok"], second)
        overlay = (self.package / "Patch_Viet_Hoa" / "COPY_TO_GAME_ROOT" / "game" / "tl" / "vietnamese" / "vntext.rpy").read_text(encoding="utf-8")
        nid = self.native_id("Hold on tight!")
        self.assertEqual(1, overlay.count(f"translate vietnamese {nid}:"))
        self.assertIn('"Giữ thật chặt!"', overlay)
        self.assertNotIn('"Bám chặt vào!"', overlay)
        self.assertIn('new "Chương một"', overlay)
        self.assertNotIn('new "Chương 1"', overlay)
        verification = json.loads((self.package / "Patch_Viet_Hoa" / "patch_verification.json").read_text(encoding="utf-8"))
        self.assertEqual([], verification["omitted_conflict_keys"])
        self.assertGreaterEqual(verification["prior_overlay_rewritten"], 2)

    def test_issue6_send_preview_no_longer_says_the_bundle_was_not_sent(self):
        from vntext.bug_report_cli import run
        out = self.root / "bug-reports"
        manual = run({"src": str(self.game), "out": str(out)})
        for_send = run({"src": str(self.game), "out": str(out), "for_send": True})
        self.assertTrue(manual["ok"] and for_send["ok"], (manual, for_send))
        self.assertIn("CHƯA được gửi", manual["summary"])
        self.assertNotIn("CHƯA được gửi", for_send["summary"])
        self.assertIn("chỉ được gửi khi bạn bấm Có", for_send["summary"])
        self.assertNotIn(str(self.root), for_send["summary"])


if __name__ == "__main__":
    unittest.main()
