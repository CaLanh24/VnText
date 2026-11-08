import argparse
import csv
import hashlib
import json
from pathlib import Path
import shutil
import unittest
import zipfile

from tests.lib.work_paths import work_temp_dir
from tests.tools import whole_game_acceptance as wga
from vntext.patch_renpy import _render_overlay

SUPPORT = "# support block (not generated)\ninit 999 python:\n    pass\n\n"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def dialogue(key, native_id, text):
    return {"key": key, "source_text": text, "file_path": "game/script.rpy", "context": "RenPy:game/script.rpy:1:" + native_id, "object_info": "", "import_method": "renpy_dialogue",
            "safety": "safe", "review_only": False, "locator": {"native_id": native_id, "unit_type": "dialogue", "speaker": "av"}, "native_contract": {"precondition": {"say_prefix": "av"}}}


def string(key, text):
    return {"key": key, "source_text": text, "file_path": "game/screens.rpy", "context": "RenPy:game/screens.rpy:2:string", "object_info": "", "import_method": "renpy_string",
            "safety": "safe", "review_only": False, "locator": {"source": text, "unit_type": "string"}}


ENTRIES = [dialogue("d1", "start_a", "Hello there my dear friend, how are you today?"), dialogue("d2", "start_b", "Fine."), string("s1", "Start game")]
TRANSLATION = {"d1": "Xin chào người bạn thân mến, hôm nay bạn thế nào?", "d2": "Khỏe.", "s1": "Bắt đầu trò chơi"}
COVERS = ["story.route", "story.ending", "ui.save_load", "ui.menus", "font.glyph", "representative.longest_dialogue", "representative.shortest_dialogue"]


class Fixture:
    """A tiny but complete evidence set: package, patch, game, owner data, candidate, basis, investigation, censuses."""

    def __init__(self, root):
        self.root = Path(root)
        r = self.root
        (r / "package").mkdir(); (r / "patch/COPY_TO_GAME_ROOT/game/tl/vietnamese").mkdir(parents=True); (r / "game/game").mkdir(parents=True); (r / "owner").mkdir()
        self.manifest = {"entries": ENTRIES, "technical_skipped": [], "stats": {"native_units": 3}}
        (r / "package/manifest.json").write_text(json.dumps(self.manifest), encoding="utf-8")
        self.write_csv(TRANSLATION)
        self.write_overlay(TRANSLATION)
        (r / "patch/patch_verification.json").write_text(json.dumps({"status": "PASS", "counts": {"PASS": 3, "FAIL": 0}, "results": [{"key": k, "status": "PASS", "method": "m"} for k in TRANSLATION]}), encoding="utf-8")
        (r / "patch/patch_coverage.json").write_text(json.dumps({"excluded_coverage": [{"code": "TECH", "count": 1, "message": "numbers"}]}), encoding="utf-8")
        (r / "game/game/archive.bin").write_bytes(b"original game bytes")
        (r / "owner/prefs").write_bytes(b"owner data")
        before = {"game_root": str(r / "game"), "game": {"files": {"game/archive.bin": sha(r / "game/game/archive.bin")}}, "appdata": {"files": {"prefs": sha(r / "owner/prefs")}}}
        (r / "before.json").write_text(json.dumps(before), encoding="utf-8")
        (r / "setup.exe").write_bytes(b"setup bytes")
        self.write_candidate("0123456789abcdef")
        (r / "flow.json").write_text(json.dumps({"say_lines": 2, "end_line": 9, "branching": "none"}), encoding="utf-8")
        (r / "audit.json").write_text(json.dumps({"totals": {"menu_choice": 0}, "menu_choices": [], "entry_labels": ["start"], "reachable": 1, "unreachable_labels": [], "say_in_unreachable": []}), encoding="utf-8")
        self.write_basis(sha(r / "package/translation.csv"), "receipt")
        self.write_investigation([{"id": "t1", "file": "game/screens.rpy", "line": 3, "classification": "EXCLUDED_TECHNICAL", "text": "[a]/[b]"}])

    def write_csv(self, translation):
        with (self.root / "package/translation.csv").open("w", encoding="utf-8-sig", newline="") as f:
            w = csv.writer(f)
            w.writerow(["key", "source_text", "translation"])
            for e in ENTRIES:
                if e["key"] in translation:
                    w.writerow([e["key"], e["source_text"], translation[e["key"]]])

    def write_overlay(self, translation, extra=""):
        dialogues = [(e, translation[e["key"]]) for e in ENTRIES if e["import_method"] == "renpy_dialogue"]
        strings = {("vietnamese", e["source_text"]): translation[e["key"]] for e in ENTRIES if e["import_method"] == "renpy_string"}
        (self.root / "patch/COPY_TO_GAME_ROOT/game/tl/vietnamese/vntext.rpy").write_text(SUPPORT + _render_overlay(dialogues, strings) + extra, encoding="utf-8")

    def write_candidate(self, source, tamper=False):
        r = self.root
        with zipfile.ZipFile(r / "route.zip", "w") as z:
            z.writestr("VNText Studio.exe", b"app exe")
            z.writestr("app/worker/vntext/tools/VNTextPatchInstaller.exe", b"installer")
        feed = {"package_file": "route.zip", "package_sha256": "0" * 64 if tamper else sha(r / "route.zip"), "manifest": {"source_sha": source, "version": "0.1.17"}}
        (r / "feed.json").write_text(json.dumps(feed), encoding="utf-8")

    def write_basis(self, csv_sha, attestation):
        r = self.root
        ev = r / "native_receipt.json"
        ev.write_text(json.dumps({"native": "route traversed"}), encoding="utf-8")
        bind = {"csv_sha256": csv_sha, "overlay_sha256": sha(r / "patch/COPY_TO_GAME_ROOT/game/tl/vietnamese/vntext.rpy")}
        item = {"id": "n1", "kind": "native", "attestation": attestation, "bind": bind, "evidence": [{"path": str(ev), "sha256": sha(ev)}], "covers": COVERS, "statement": "s", "limits": "l"}
        (r / "basis.json").write_text(json.dumps({"items": [item]}), encoding="utf-8")

    def write_investigation(self, items):
        (self.root / "investigation.json").write_text(json.dumps({"groups": [{"code": "TECH", "items": items}], "cache_evidence": []}), encoding="utf-8")

    def args(self, **over):
        r = self.root
        base = dict(package=r / "package", patch=r / "patch", game_before=r / "before.json", game_root=r / "game", owner_root=r / "owner", candidate_setup=r / "setup.exe",
                    route_zip=r / "route.zip", route_feed=r / "feed.json", candidate_source="0123456", basis=r / "basis.json", investigation=r / "investigation.json",
                    story_flow=r / "flow.json", script_audit=r / "audit.json", output=r / "out.json")
        base.update(over)
        return argparse.Namespace(**{k: str(v) for k, v in base.items()})


class WholeGameAcceptanceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = work_temp_dir("whole-game-acceptance") / self._testMethodName
        shutil.rmtree(self.tmp, ignore_errors=True)
        self.tmp.mkdir(parents=True)
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.fx = Fixture(self.tmp)

    def blocked(self, receipt, prefix):
        return [b for b in receipt["blocking"] if b["id"].startswith(prefix)]

    def test_complete_consistent_evidence_is_the_only_accept_path(self):
        receipt = wga.build(self.fx.args())
        self.assertEqual("ACCEPT_ELIGIBLE", receipt["verdict"], receipt["blocking"])
        self.assertEqual(3, receipt["counts"]["achieved"])
        self.assertTrue(receipt["chain"]["overlay_regenerated_with_product_renderer"])

    def test_row_invariants_reject_real_corruption_but_not_decomposed_vietnamese(self):
        self.assertEqual([], wga.row_invariants("Hi [name]! {b}x{/b}\nok", "Chào [name]! {b}x{/b}\nđược"))
        self.assertEqual(["placeholder"], wga.row_invariants("Hi [name]", "Chào"))
        self.assertEqual(["tags"], wga.row_invariants("{b}x{/b}", "x"))
        self.assertEqual(["newline"], wga.row_invariants("a\nb", "a b"))
        self.assertEqual(["encoding"], wga.row_invariants("x", "x" + chr(0xFFFD)))
        self.assertEqual([], wga.row_invariants("dung", "du" + chr(0x300) + "ng"))            # valid canonically equivalent Vietnamese is not corruption
        self.assertEqual([], wga.row_invariants("dung", "d" + chr(0x1EEB) + "ng"))

    def test_swapped_translations_between_csv_and_overlay_fail_the_chain(self):
        swapped = dict(TRANSLATION, d1=TRANSLATION["d2"], d2=TRANSLATION["d1"])
        self.fx.write_csv(swapped)                                                       # overlay still carries the original pairing
        receipt = wga.build(self.fx.args())
        self.assertFalse(receipt["chain"]["pass"])
        self.assertFalse(receipt["chain"]["overlay_regenerated_with_product_renderer"])
        self.assertEqual("NOT_ACCEPTED", receipt["verdict"])

    def test_missing_extra_and_duplicate_sets_are_exact(self):
        self.fx.write_csv({k: v for k, v in TRANSLATION.items() if k != "d2"})
        receipt = wga.build(self.fx.args())
        self.assertEqual(["d2"], receipt["chain"]["missing_csv"])
        self.assertEqual(["d2"], receipt["chain"]["extra_readback"])
        self.fx.write_csv(TRANSLATION)
        rb = json.loads((self.tmp / "patch/patch_verification.json").read_text(encoding="utf-8"))
        rb["results"].append(dict(rb["results"][0]))
        rb["counts"]["PASS"] = 4
        (self.tmp / "patch/patch_verification.json").write_text(json.dumps(rb), encoding="utf-8")
        receipt = wga.build(self.fx.args())
        self.assertEqual(["d1"], receipt["chain"]["dup_readback"])
        self.assertEqual("NOT_ACCEPTED", receipt["verdict"])

    def test_extra_overlay_translation_is_rejected(self):
        self.fx.write_overlay(TRANSLATION, extra='translate vietnamese strings:\n    old "Injected"\n    new "Chèn"\n')
        receipt = wga.build(self.fx.args())
        self.assertGreater(receipt["chain"]["overlay_extra_string_pairs"], 0)
        self.assertEqual("NOT_ACCEPTED", receipt["verdict"])

    def test_wrong_candidate_artifact_or_source_blocks(self):
        self.fx.write_candidate("0123456789abcdef", tamper=True)
        self.assertTrue(self.blocked(wga.build(self.fx.args()), "gate.candidate"))
        self.fx.write_candidate("fedcba9876543210")
        self.assertTrue(self.blocked(wga.build(self.fx.args()), "gate.candidate"))

    def test_native_basis_is_bound_to_component_hashes_and_receipts(self):
        self.fx.write_basis("f" * 64, "receipt")                                         # basis claims a different CSV than the accepted one
        receipt = wga.build(self.fx.args())
        self.assertEqual("NOT_ACCEPTED", receipt["verdict"])
        self.assertTrue(any("MISMATCH" in b["why"] for b in receipt["blocking"] if b["id"].startswith("basis.")))
        self.assertEqual("MISMATCH", receipt["matrix"][0]["native"])
        self.fx.write_basis(sha(self.tmp / "package/translation.csv"), "reported")      # a statement without a machine receipt is not proof
        receipt = wga.build(self.fx.args())
        self.assertEqual("REPORTED_ONLY", receipt["matrix"][0]["native"])
        self.assertEqual("NOT_ACCEPTED", receipt["verdict"])
        (self.tmp / "native_receipt.json").write_text("tampered", encoding="utf-8")      # evidence file hash changed after the claim
        self.fx.write_basis(sha(self.tmp / "package/translation.csv"), "receipt")
        (self.tmp / "native_receipt.json").write_text("different", encoding="utf-8")
        receipt = wga.build(self.fx.args())
        self.assertEqual("EVIDENCE_MISMATCH", receipt["matrix"][0]["native"])

    def test_missing_required_coverage_stays_blocking(self):
        basis = json.loads((self.tmp / "basis.json").read_text(encoding="utf-8"))
        basis["items"][0]["covers"].remove("representative.longest_dialogue")
        (self.tmp / "basis.json").write_text(json.dumps(basis), encoding="utf-8")
        receipt = wga.build(self.fx.args())
        self.assertEqual("NOT_ACCEPTED", receipt["verdict"])
        self.assertTrue(self.blocked(receipt, "representative.longest_dialogue"))
        self.fx.write_basis(sha(self.tmp / "package/translation.csv"), "receipt")
        self.fx.write_investigation([])                                                  # excluded group count is 1 but nothing was inspected
        receipt = wga.build(self.fx.args())
        self.assertTrue(self.blocked(receipt, "gate.investigation"))
        self.fx.write_investigation([{"id": "t1", "file": "game/screens.rpy", "line": 3, "classification": "EXCLUDED_TECHNICAL", "text": "Mute All"}])
        receipt = wga.build(self.fx.args())                                              # a classification that is not mechanically true is a failure, not a waiver
        self.assertEqual("FAIL", receipt["matrix"][-1]["static"])
        self.assertEqual("NOT_ACCEPTED", receipt["verdict"])

    def test_missing_input_fails_closed_and_changed_protected_data_blocks(self):
        (self.tmp / "basis.json").unlink()
        with self.assertRaises(wga.InputError):
            wga.build(self.fx.args())
        self.fx.write_basis(sha(self.tmp / "package/translation.csv"), "receipt")
        (self.tmp / "game/game/archive.bin").write_bytes(b"modified")
        receipt = wga.build(self.fx.args())
        self.assertTrue(self.blocked(receipt, "gate.game_hashes"))
        self.assertEqual(["game/archive.bin"], receipt["game"]["current"]["changed"])


if __name__ == "__main__":
    unittest.main()
