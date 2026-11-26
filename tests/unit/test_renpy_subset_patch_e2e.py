"""One CSV -> Patch on a REAL official-SDK Ren'Py source fixture (no game, no execution): a valid translated SUBSET packages despite unrelated
untranslated/unsafe/review rows and a stale translate status, omissions are explicit, every included key's payload equals the CSV value,
and the guards (zero rows, changed source hash, no explicit subset on a partial extraction) still refuse with actionable text."""
import csv
import json
import re
import tempfile
import unittest
from pathlib import Path

from tests.lib.dev_environment import renpy_native_sdk
from tests.lib.work_paths import work_temp_dir

SDK_OK = (renpy_native_sdk() / "renpy.py").is_file()
SCRIPT = '''define e = Character("Eileen")
label start:
    "Welcome to the village, traveler."
    e "Good morning!"
    menu:
        "Take the north road":
            "You go north."
    return
screen ui():
    text "Chapter 1"
    textbutton _("Mute All"):
        action NullAction()
    text "Version [config.version!t]"
    text "Disabled label" substitute False
'''
# human translations written by the user / drafted earlier; "Version" drops its placeholder (unsafe) and the rest stay untranslated
TRANSLATIONS = {"Welcome to the village, traveler.": "Chào mừng đến ngôi làng, lữ khách.", "Chapter 1": "Chương 1", "Mute All": "Tắt tiếng tất cả",
                "Version [config.version!t]": "Phiên bản"}


@unittest.skipUnless(SDK_OK, "Official công cụ Ren’Py absent")
class SubsetPatchE2ETests(unittest.TestCase):
    def setUp(self):
        from vntext.app_tasks import run_extract_task
        tmp = tempfile.TemporaryDirectory(dir=work_temp_dir("renpy-subset-patch"))
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.game = self.root / "source"; (self.game / "game").mkdir(parents=True)
        self.source = self.game / "game" / "script.rpy"; self.source.write_text(SCRIPT, encoding="utf-8")
        events = []
        run_extract_task(str(self.game), str(self.root / "package"), "safe", "balanced", True, renpy_sdk_path=str(renpy_native_sdk()), renpy_sdk_action="existing",
                         progress=lambda _: None, log=lambda _: None, complete=events.append)
        self.extract = events[-1]
        self.package = self.root / "package"; self.csv = self.package / "translation.csv"
        with self.csv.open(encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream); self.fields = reader.fieldnames; rows = list(reader)
        for row in rows:
            row["translation"] = TRANSLATIONS.get(row["source_text"], "")
        with self.csv.open("w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=self.fields, lineterminator="\r\n"); writer.writeheader(); writer.writerows(rows)
        self.status = self.package / "extract_status.json"
        self.scoped_status = self.status.read_text(encoding="utf-8")
        # an UNSCOPED PARTIAL (what blanket-blocked before): errors/review beyond the expected limitations
        self.unscoped = json.dumps({"status": "PARTIAL", "complete": False, "main": 5, "review": 3, "errors": 1, "severity": "error", "limitations": []})
        (self.package / ".mt").mkdir(exist_ok=True)                                                  # a stale, pessimistic translate status must not veto the patch
        (self.package / ".mt" / "translate_status.json").write_text(json.dumps({"complete": False, "pending": 9, "review_only": 3, "blocked": 2, "translated": 0}), encoding="utf-8")

    def patch(self, **kwargs):
        from vntext.app_tasks import run_patch_task
        done = []
        run_patch_task(self.csv, self.package / "manifest.json", str(self.game), str(self.package), progress=lambda _: None, log=lambda _: None, complete=done.append,
                       patch_out_override=self.package / "Patch_Viet_Hoa", include_installer=False, write_manifest_file=False, **kwargs)
        return done[-1]

    def rows(self):
        with self.csv.open(encoding="utf-8-sig", newline="") as stream:
            return list(csv.DictReader(stream))

    def test_partial_extraction_is_the_precondition_of_this_scenario(self):
        self.assertEqual("PARTIAL", self.extract["extract_status"])                                   # the "Disabled label" row is a genuine unproven human row

    def test_scoped_partial_patches_without_any_override_and_never_claims_full_coverage(self):
        done = self.patch()
        self.assertTrue(done["ok"], done)
        coverage = json.loads((self.package / "Patch_Viet_Hoa" / "patch_coverage.json").read_text(encoding="utf-8"))
        self.assertEqual("VERIFIED_MAIN_SUBSET", coverage["scope"]); self.assertIn("NOT a full-game PASS", coverage["statement"])

    def test_valid_subset_packages_with_explicit_omissions_and_exact_payload(self):
        self.status.write_text(self.unscoped, encoding="utf-8")
        before = (self.source.read_bytes(), self.csv.read_bytes(), (self.package / "manifest.json").read_bytes())
        done = self.patch(partial_override=True)
        self.assertTrue(done["ok"], done)
        output = self.package / "Patch_Viet_Hoa"
        verification = json.loads((output / "patch_verification.json").read_text(encoding="utf-8"))
        csv_rows = {row["source_text"]: row["translation"] for row in self.rows() if row["translation"].strip()}
        overlay = "\n".join(p.read_text(encoding="utf-8") for p in (output / "COPY_TO_GAME_ROOT").rglob("*.rpy"))
        written = dict(re.findall(r'old "(.*?)"\s*\n\s*new "(.*?)"', overlay))
        dialogue = [t for t in re.findall(r'"([^"]*)"', overlay)]
        self.assertEqual(2 + 0, len([k for k in ("Chapter 1", "Mute All") if k in written]))          # screen strings written as string translations
        for source in ("Chapter 1", "Mute All"):
            self.assertEqual(csv_rows[source], written[source])                                       # payload == CSV value per key
        self.assertIn(csv_rows["Welcome to the village, traveler."], dialogue)                         # dialogue written back as well
        self.assertNotIn("Phiên bản", overlay)                                                         # the unsafe (placeholder-dropping) row was OMITTED, not patched
        self.assertNotIn("Disabled label", written)                                                    # unproven/untranslated rows are never invented
        omitted = verification.get("omitted_by_reason") or {}
        self.assertGreaterEqual(sum(omitted.values()), 2)                                              # untranslated + unsafe omissions are counted, not hidden
        coverage = json.loads((output / "patch_coverage.json").read_text(encoding="utf-8"))
        self.assertTrue(coverage["owner_override"]); self.assertIn("NOT a full-game PASS", coverage["statement"])
        self.assertEqual(len(verification["results"]), coverage["included_rows"])
        self.assertEqual(before, (self.source.read_bytes(), self.csv.read_bytes(), (self.package / "manifest.json").read_bytes()))

    def test_without_the_explicit_subset_an_unscoped_partial_extraction_is_refused_with_actionable_text(self):
        self.status.write_text(self.unscoped, encoding="utf-8")
        done = self.patch()
        self.assertFalse(done["ok"], done)
        self.assertIn("safe-subset", done.get("error", "") + done.get("summary", ""))                  # tells the user the supported action, no traceback wall
        self.assertNotIn("Traceback", json.dumps(done))
        self.assertFalse((self.package / "Patch_Viet_Hoa" / "COPY_TO_GAME_ROOT").exists())

    def test_changed_source_hash_and_zero_translated_rows_still_refuse(self):
        self.status.write_text(self.unscoped, encoding="utf-8")
        self.source.write_text(SCRIPT + "# edited after extraction\n", encoding="utf-8")
        done = self.patch(partial_override=True)
        self.assertFalse(done["ok"], done)
        self.assertFalse((self.package / "Patch_Viet_Hoa" / "COPY_TO_GAME_ROOT").exists())
        self.source.write_text(SCRIPT, encoding="utf-8")
        rows = self.rows()
        for row in rows:
            row["translation"] = ""
        with self.csv.open("w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=self.fields, lineterminator="\r\n"); writer.writeheader(); writer.writerows(rows)
        done = self.patch(partial_override=True)
        self.assertFalse(done["ok"], done)
        self.assertIn("đủ điều kiện", done.get("error", "") + done.get("summary", ""))                 # "no eligible row", never an empty patch
        self.assertFalse((self.package / "Patch_Viet_Hoa" / "COPY_TO_GAME_ROOT").exists())

    def test_failed_exclusion_write_does_not_suppress_the_row_on_the_next_real_extraction(self):
        from unittest.mock import patch
        from vntext.app_tasks import run_extract_task
        from vntext.user_exclusions import EXCLUSIONS_FILE, exclude_rows
        import hashlib, os
        key = next(row["key"] for row in self.rows() if row["source_text"] == "Chapter 1")
        csv_before = self.csv.read_bytes()
        real_replace = os.replace

        def failing(src, dst, *a, **k):
            if str(dst).endswith("translation.csv"):
                raise OSError("injected: disk full")
            return real_replace(src, dst, *a, **k)
        with patch("os.replace", failing), self.assertRaises(OSError):
            exclude_rows(self.csv, [key], hashlib.sha256(csv_before).hexdigest())
        self.assertEqual(csv_before, self.csv.read_bytes())
        self.assertFalse((self.package / EXCLUSIONS_FILE).exists())                                     # nothing left behind to suppress the next extract
        events = []
        run_extract_task(str(self.game), str(self.package), "safe", "balanced", True, renpy_sdk_path=str(renpy_native_sdk()), renpy_sdk_action="existing",
                         progress=lambda _: None, log=lambda _: None, complete=events.append)
        self.assertIn("Chapter 1", [row["source_text"] for row in self.rows()])                         # re-extraction still lists the row
        self.assertNotEqual("", events[-1].get("extract_status", ""))


if __name__ == "__main__":
    unittest.main()
