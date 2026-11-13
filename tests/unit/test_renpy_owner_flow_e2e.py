"""Owner acceptance flow on a representative Ren'Py fixture (no real game, no gameplay): extract -> translate EVERY CSV row with the product
OPUS-MT model -> build the patch -> per-key payload read-back.  Human text (dialogue, menu, screen text, tagged prose, "Mute All", "Return",
"Chapter 1", "Version [config.version!t]", the accessibility sentence) is translated and written back with placeholders/tags intact;
technical syntax (glyphs, interpolation-only, engine credit) is excluded automatically and audited, never a user review item."""
import csv
import json
import os
import re
import tempfile
import unittest
from pathlib import Path

from tests.lib.dev_environment import renpy_native_sdk
from tests.lib.work_paths import work_temp_dir

ROOT = Path(__file__).resolve().parents[2]
MODEL_DIR = Path(os.environ.get("VNTEXT_CT2_MODEL", str(ROOT / ".dev-env" / "cache" / "models" / "opus-mt-en-vi-int8")))
SDK_OK = (renpy_native_sdk() / "renpy.py").is_file()
HUMAN = ["Prologue", "Welcome to the village, traveler.", "You go north.", "Take the north road", "Mute All", "Chapter 1", "The Claiming", "Return",
         "Version [config.version!t]", "Toggles assistive {a=https://www.renpy.org/l/voicing}self-voicing{/a}."]
TECHNICAL = ["<", "{#auto_page}A", "[page]", "[config.name!t]"]
ENGINE_CREDIT = "Made with {a=https://www.renpy.org/}Ren'Py{/a} [renpy.version_only].\\n\\n[renpy.license!t]"
SCRIPT = f'''define e = Character("Eileen")
label start:
    "Prologue"
    e "Welcome to the village, traveler."
    menu:
        "Take the north road":
            "You go north."
    return
screen ui():
    text "Chapter 1"
    text "The Claiming"
    textbutton _("Mute All"):
        action NullAction()
    textbutton "Return" action NullAction()
    text "Version [config.version!t]"
    text "Toggles assistive {{a=https://www.renpy.org/l/voicing}}self-voicing{{/a}}."
    text "{ENGINE_CREDIT}"
    textbutton "<" action NullAction()
    textbutton "{{#auto_page}}A" action NullAction()
    text "[page]"
    text "[config.name!t]"
'''


def _tokens(text):
    """Placeholders and tags that must survive translation unchanged."""
    return sorted(re.findall(r"\[[^\[\]]+\]|\{[^{}]*\}", text))


@unittest.skipUnless(SDK_OK, "Official Ren'Py SDK absent")
class RenPyOwnerFlowTests(unittest.TestCase):
    def extract(self, script=SCRIPT):
        from vntext.app_tasks import run_extract_task
        tmp = tempfile.TemporaryDirectory(dir=work_temp_dir("renpy-owner-flow"))
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        game = root / "source"; (game / "game").mkdir(parents=True)
        source = game / "game" / "script.rpy"; source.write_text(script, encoding="utf-8")
        events = []
        run_extract_task(str(game), str(root / "package"), "safe", "balanced", True, renpy_sdk_path=str(renpy_native_sdk()), renpy_sdk_action="existing",
                         progress=lambda _: None, log=lambda _: None, complete=events.append)
        return root, game, source, root / "package", events[-1]

    def rows(self, package):
        with (package / "translation.csv").open(encoding="utf-8-sig", newline="") as stream:
            return list(csv.DictReader(stream))

    def test_extract_is_complete_with_human_text_only_and_a_machine_audit(self):
        _root, _game, _source, package, done = self.extract()
        self.assertEqual("COMPLETE", done["extract_status"], done)
        self.assertTrue(done["ok"]); self.assertEqual(0, done["review_only"])                      # no review rows: nothing to triage
        self.assertEqual(HUMAN, [row["source_text"] for row in self.rows(package)])
        audit = json.loads((package / "renpy_technical_excluded.json").read_text(encoding="utf-8"))
        reasons = {entry["source_text"]: entry["reason"] for entry in audit["entries"]}
        self.assertEqual(set(TECHNICAL) | {ENGINE_CREDIT.replace("\\n", "\n")} if False else set(TECHNICAL), {k for k in reasons if k in TECHNICAL})
        self.assertEqual("engine_metadata", next(v for k, v in reasons.items() if k.startswith("Made with")))
        self.assertTrue(all(reasons[k] == "no_visible_words" for k in TECHNICAL))
        status = json.loads((package / "extract_status.json").read_text(encoding="utf-8"))
        self.assertEqual(len(audit["entries"]), status["excluded_technical_ui"])                   # the counter is the audit, never invented

    def test_unproven_human_text_is_still_a_real_review_row_never_silently_patched(self):
        _root, _game, _source, package, done = self.extract(SCRIPT + '    text "Disabled label" substitute False\n')
        self.assertEqual("PARTIAL", done["extract_status"])                                         # honest: one genuine unproven human row remains
        manifest = json.loads((package / "manifest.json").read_text(encoding="utf-8"))
        disabled = next(entry for entry in manifest["entries"] if entry["source_text"] == "Disabled label")
        self.assertTrue(disabled["review_only"]); self.assertFalse(disabled.get("patch_proof"))

    @unittest.skipUnless((MODEL_DIR / "model.bin").is_file(), "Product OPUS-MT model absent")
    def test_translate_all_rows_with_the_product_model_then_patch_and_read_back_every_key(self):
        from vntext.app_tasks import run_patch_task, run_translate_ct2_task
        from vntext.package_io import read_translation_rows
        root, game, source, package, done = self.extract()
        before = source.read_bytes()
        translated = []
        run_translate_ct2_task(package / "translation.csv", package, False, model_dir=str(MODEL_DIR), progress=lambda _: None, log=lambda _: None,
                               complete=translated.append)
        self.assertTrue(translated and translated[-1].get("ok"), translated)
        rows = read_translation_rows(str(package / "translation.csv"))
        csv_rows = self.rows(package)
        self.assertEqual(len(HUMAN), len(csv_rows))
        for row in csv_rows:                                                                         # structural check of EVERY row against the real model output
            target = row["translation"]
            self.assertTrue(target.strip(), row["source_text"])
            self.assertEqual(_tokens(row["source_text"]), _tokens(target), (row["source_text"], target))   # placeholders and tags intact
            self.assertNotIn("\ufffd", target)                                                       # no encoding corruption
        completed = []
        run_patch_task(package / "translation.csv", package / "manifest.json", str(game), str(package), progress=lambda _: None, log=lambda _: None,
                       complete=completed.append, patch_out_override=package / "Patch_Viet_Hoa", include_installer=False, write_manifest_file=False)
        self.assertTrue(completed and completed[-1]["ok"], completed)
        output = package / "Patch_Viet_Hoa"
        verification = json.loads((output / "patch_verification.json").read_text(encoding="utf-8"))
        self.assertEqual(len(HUMAN), len(verification["results"]))                                  # every included key has read-back evidence
        overlay = "\n".join(path.read_text(encoding="utf-8") for path in (output / "COPY_TO_GAME_ROOT").rglob("*.rpy"))
        for row in csv_rows:
            self.assertIn(row["translation"].replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n"), overlay, row["source_text"])   # payload == CSV, per key
        for text in TECHNICAL:
            self.assertNotIn(f'old "{text}"', overlay)                                               # excluded technical syntax is never written
        self.assertEqual(before, source.read_bytes())                                                # the original game is untouched
        self.assertEqual(set(rows), {row["key"] for row in csv_rows})


if __name__ == "__main__":
    unittest.main()
