"""0.1.42: a translated line that Ren'Py cannot parse ("String ... ends with an open format operation") must never reach the game."""
import hashlib
import itertools
import json
import random
import re
import tempfile
import unittest
from unittest import mock
from pathlib import Path

from vntext.package_io import CSV_FIELDS, write_csv_rows_file
from vntext.patch_gate import patch_skip_reason, reason_label_vi
from vntext.patch_renpy import RenPyPatchError, apply_renpy_translation_package
from vntext.renpy_markup import interpolation_error, markup_problems, overlay_problems, repair_markup

ROOT = Path(__file__).resolve().parents[2]
SDK_SUBST = ROOT / ".dev-env" / "tools" / "renpy-8.5.3" / "renpy" / "substitutions.py"


def _sdk_parse():
    text = SDK_SUBST.read_text(encoding="utf-8")
    m = re.search(r"^def parse\(s\):.*?(?=^def )", text, re.S | re.M)
    scope = {"flags": frozenset("rstiqulc!")}
    exec(m.group(0), scope)  # noqa: S102 - the pinned SDK file of the dev environment, not user data
    return scope["parse"]


def _sdk_fails(parse, s):
    try:
        list(parse(s))
        return False
    except Exception:
        return True


class MarkupChecker(unittest.TestCase):
    # Synthetic stand-in for the reported line: the machine translation turned "{i}" into "[i}" and left a stray pair of tags.
    SOURCE = '{i}You may rest here, [name].{/i}'
    BROKEN = '{i}[i}Bạn có thể nghỉ ở đây, [name]. ‘ \\"ổn\\" {b}{/b} {/i}'

    def test_the_reported_shape_is_blocked(self):
        reasons = markup_problems(self.SOURCE, self.BROKEN)
        self.assertTrue(any("[ ]" in r for r in reasons), reasons)
        self.assertTrue(any("rỗng" in r for r in reasons), reasons)

    def test_the_gate_blocks_it_with_a_plain_vietnamese_reason(self):
        entry = {"source_text": self.SOURCE, "import_method": "renpy_dialogue", "file_path": "game/x.rpy", "context": ""}
        reason = patch_skip_reason(entry, self.BROKEN, set())
        self.assertTrue(reason, "the broken line went through the patch gate")
        self.assertNotIn("renpy_markup_invalid", reason_label_vi(reason))
        self.assertTrue(reason_label_vi(reason))

    def test_a_good_translation_passes(self):
        good = '{i}Bạn có thể nghỉ ở đây, [name].{/i}'
        self.assertEqual([], markup_problems(self.SOURCE, good))
        entry = {"source_text": self.SOURCE, "import_method": "renpy_dialogue", "file_path": "game/x.rpy", "context": ""}
        self.assertEqual("", patch_skip_reason(entry, good, set()))

    def test_safe_repair_restores_the_markup_of_the_source(self):
        fixed = repair_markup(self.SOURCE, self.BROKEN)
        self.assertIsNotNone(fixed)
        self.assertEqual([], markup_problems(self.SOURCE, fixed))
        self.assertIn("Bạn có thể", fixed)
        self.assertFalse(interpolation_error(fixed))

    def test_unrepairable_line_returns_none(self):
        self.assertIsNone(repair_markup("Hello [name]", "Xin chào [nam"))

    def test_escaped_brackets_and_braces_are_fine(self):
        self.assertEqual([], markup_problems("Press [[A]] {{now}}", "Nhấn [[A]] {{ngay}}"))

    def test_lost_name_is_reported(self):
        self.assertTrue(markup_problems("Hello [name]", "Xin chào"))

    @unittest.skipUnless(SDK_SUBST.is_file(), "Ren'Py SDK of the dev environment not present")
    def test_interpolation_check_agrees_with_the_ren_py_parser(self):
        parse = _sdk_parse()
        rng = random.Random(42)
        alphabet = list("[]{}!:()'\"a b%/\\") + ["[[", "]]", "!t", "!r", ":d"]
        for _ in range(4000):
            s = "".join(rng.choice(alphabet) for _ in range(rng.randint(0, 9)))
            self.assertEqual(_sdk_fails(parse, s), bool(interpolation_error(s)), repr(s))

    def test_generated_file_check_names_the_line(self):
        payload = 'translate vietnamese strings:\n    old "a"\n    new "Xin [chào"\n\ntranslate vietnamese start_a:\n    # "x"\n    "Ổn"\n'
        found = overlay_problems(payload)
        self.assertEqual([3], [n for n, _ in found])


class PatchWritesNothingBroken(unittest.TestCase):
    def _package(self, base: Path, translation: str):
        from tests.unit.test_renpy_patch import _native_contract
        game = base / "gamecopy"
        (game / "game").mkdir(parents=True)
        (game / "game" / "script.rpy").write_text('label start:\n    "{i}You may rest here, [name].{/i}"\n', encoding="utf-8")
        sha = hashlib.sha256((game / "game/script.rpy").read_bytes()).hexdigest()
        entry = {"key": "d", "source_text": "{i}You may rest here, [name].{/i}", "file_path": "game/script.rpy", "import_method": "renpy_dialogue",
                 "locator": {"native_id": "start_a", "unit_type": "dialogue"}, "backend": "renpy_loose_source", "object_info": ""}
        entry["native_contract"] = _native_contract(entry, sha)
        manifest = base / "manifest.json"
        manifest.write_text(json.dumps({"entries": [entry]}), encoding="utf-8")
        row = {f: "" for f in CSV_FIELDS}
        row.update(entry)
        row["translation"] = translation
        csv = base / "translation.csv"
        write_csv_rows_file(csv, CSV_FIELDS, [row])
        return game, csv, manifest

    def test_repairable_broken_line_is_repaired_before_writing(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            game, csv, manifest = self._package(base, MarkupChecker.BROKEN)
            apply_renpy_translation_package(str(csv), str(manifest), str(game), str(base / "out"))
            overlay = (base / "out/COPY_TO_GAME_ROOT/game/tl/vietnamese/vntext.rpy").read_text(encoding="utf-8")
            self.assertEqual([], overlay_problems(overlay))
            self.assertNotIn("[i}", overlay)
            verification = json.loads((base / "out/patch_verification.json").read_text(encoding="utf-8"))
            self.assertEqual(["d"], verification["repaired_markup_keys"])

    def test_unrepairable_line_is_left_in_english_and_counted(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            game, csv, manifest = self._package(base, "{i}Bạn nghỉ ở đây, [nam.{/i}")
            with mock.patch("vntext.renpy_markup.repair_markup", return_value=None), self.assertRaises(RenPyPatchError):      # the only row is omitted -> nothing eligible
                apply_renpy_translation_package(str(csv), str(manifest), str(game), str(base / "out"))
            self.assertFalse((base / "out/COPY_TO_GAME_ROOT/game/tl/vietnamese/vntext.rpy").exists())


if __name__ == "__main__":
    unittest.main()
