"""Ren'Py native accounting: every native unit lands in exactly one bucket (package row, engine-common exclusion, row removed by the user or by
the machine-syntax cleanup), an unexplained gap never fails the extraction, and the gap is named - masked - for a bug report.

Owner report 2026-11-26 (v0.1.33): "Ren'Py native accounting mismatch: native=1564, package=1525" after re-extracting into an output whose
user_exclusions.json held rows removed earlier; those recorded decisions were dropped from the package but counted in no bucket."""
import csv
import hashlib
import json
import random
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tests.lib.work_paths import work_temp_dir
from vntext.native_accounting import mask_file, reconcile_native_units

ROOT = Path(__file__).resolve().parents[2]
SDK = ROOT / ".dev-env" / "tools" / "renpy-8.5.3"
WORK = work_temp_dir("native-accounting")


class ReconcileTests(unittest.TestCase):
    def test_every_unit_lands_in_one_bucket_and_a_missing_one_is_named_masked(self):
        index = [{"context": "a", "kind": "dialogue", "file": "game/secret name.rpy", "line": 3},
                 {"context": "b", "kind": "string", "file": "game/secret name.rpy", "line": 9},
                 {"context": "c", "kind": "static_display", "file": "game/screens.rpy", "line": 40},
                 {"context": "d", "kind": "dialogue", "file": "game/other.rpy", "line": 1}]
        result = reconcile_native_units(index, package_contexts={"a"}, engine_common_contexts={"c"}, user_excluded_contexts={"b"},
                                        counts={"main": 1}, native_units=4)
        self.assertEqual({"engine_common_excluded": 1, "package_row": 1, "user_excluded": 1}, result["buckets"])
        self.assertEqual(1, result["unaccounted_count"])
        self.assertEqual({"dialogue": 1}, result["unaccounted_by_kind"])
        self.assertEqual([{"kind": "dialogue", "file": mask_file("game/other.rpy"), "line": 1}], result["unaccounted"])
        text = json.dumps(result)
        self.assertNotIn("secret", text)
        self.assertNotIn("other", text)
        self.assertTrue(result["index_complete"])

    def test_samples_are_capped(self):
        index = [{"context": str(i), "kind": "dialogue", "file": "game/a.rpy", "line": i} for i in range(120)]
        result = reconcile_native_units(index, package_contexts=set(), engine_common_contexts=set(), user_excluded_contexts=set(),
                                        counts={}, native_units=120, sample_cap=50)
        self.assertEqual(120, result["unaccounted_count"])
        self.assertEqual(50, len(result["unaccounted"]))
        self.assertTrue(result["unaccounted_truncated"])


def _extract(game: Path, out: Path) -> dict:
    from vntext.app_tasks import run_extract_task
    events = []
    run_extract_task(str(game), str(out), "deep", "balanced", False, renpy_sdk_path=str(SDK), renpy_sdk_action="existing",
                     progress=lambda *_: None, log=lambda *_: None, complete=events.append)
    return events[-1]


def _status(out: Path) -> dict:
    return json.loads((out / "extract_status.json").read_text(encoding="utf-8"))


def _accounting(out: Path) -> dict:
    return json.loads((out / "native_accounting.json").read_text(encoding="utf-8"))


def _random_game(game: Path, rng: random.Random) -> None:
    """A loose Ren'Py layout mixing the native shapes the accounting must cover: dialogue (narration, speakers, nvl, menus), _() strings, screen
    text, duplicate strings across files, engine-common words, translate python/style blocks and several files/sub-folders."""
    import tests.unit.test_scan_layout_matrix as layouts
    layouts.LAYOUTS["loose_rpy"][0](game)
    (game / "game" / "script.rpy").write_text("label start:\n    return\n", encoding="utf-8")
    words = ["river", "lantern", "quiet", "morning", "letter", "garden", "window", "promise"]
    for index in range(rng.randint(1, 4)):
        folder = game / "game" / ("chapters" if index % 2 else "")
        folder.mkdir(parents=True, exist_ok=True)
        lines = [f'define c{index} = Character("Speaker {index}")', f"define n{index} = Character(None, kind=nvl)", f"label part_{index}:"]
        for n in range(rng.randint(2, 12)):
            sentence = f"{rng.choice(words).title()} {rng.choice(words)} number {index}-{n}."
            shape = rng.choice(["say", "narration", "menu", "string", "nvl"])
            if shape == "say":
                lines.append(f'    c{index} "{sentence}"')
            elif shape == "narration":
                lines.append(f'    "{sentence}"')
            elif shape == "menu":
                lines += ["    menu:", f'        "{sentence}":', "            pass", f'        "Other {n} choice.":', "            pass"]
            elif shape == "string":
                lines.append(f'    $ note_{index}_{n} = _("{sentence}")')
                lines.append('    $ shared = _("Shared words across files.")')
            else:
                lines.append(f'    n{index} "{sentence}"')
        lines.append("    return")
        (folder / f"part_{index}.rpy").write_text("\n".join(lines) + "\n", encoding="utf-8")
    screen = ["screen extra_menu():", "    vbox:", '        text "Return"', '        textbutton "Gallery of moments" action Return()', '        text "[score]"']
    (game / "game" / "extra_screens.rpy").write_text("\n".join(screen) + "\n", encoding="utf-8")


@unittest.skipUnless((SDK / "renpy.exe").is_file(), "needs the local Ren'Py SDK")
class NativeAccountingExtractTests(unittest.TestCase):
    def test_rows_removed_earlier_are_their_own_bucket_on_re_extraction(self):
        from vntext.user_exclusions import exclude_rows
        with tempfile.TemporaryDirectory(dir=WORK) as temp:
            base = Path(temp); game = base / "game copy"; game.mkdir(); out = base / "out"
            _random_game(game, random.Random(7))
            self.assertEqual("COMPLETE", _extract(game, out).get("extract_status"))
            with open(out / "translation.csv", encoding="utf-8-sig", newline="") as stream:
                rows = list(csv.DictReader(stream))
            keys = [row["key"] for row in rows[:3]]
            exclude_rows(out / "translation.csv", keys, hashlib.sha256((out / "translation.csv").read_bytes()).hexdigest())
            result = _extract(game, out)
            status = _status(out)
            self.assertEqual("COMPLETE", result.get("extract_status"), result)
            self.assertEqual((status["native_units"], 3, True), (status["native_accounted"], status["user_excluded"], status["native_accounting_complete"]))
            accounting = _accounting(out)
            self.assertEqual(0, accounting["unaccounted_count"])
            self.assertEqual(3, accounting["buckets"]["user_excluded"])
            self.assertEqual(status["native_units"], sum(accounting["buckets"].values()))

    def test_an_unexplained_gap_is_a_partial_warning_with_masked_units_never_a_failure(self):
        import vntext.user_exclusions as exclusions
        original = exclusions.filter_excluded_entries

        def lose_one_silently(entries, package_dir):          # a future, unknown loss: one native row vanishes without being recorded anywhere
            kept, dropped = original(entries, package_dir)
            native = [entry for entry in kept if entry.import_method == "renpy_dialogue"]
            return ([entry for entry in kept if entry is not native[0]] if native else kept), dropped

        with tempfile.TemporaryDirectory(dir=WORK) as temp:
            base = Path(temp); game = base / "game copy"; game.mkdir(); out = base / "out"
            _random_game(game, random.Random(11))
            with mock.patch.object(exclusions, "filter_excluded_entries", lose_one_silently):
                result = _extract(game, out)
            status = _status(out)
            self.assertEqual("PARTIAL", result.get("extract_status"), result)
            self.assertEqual(("warning", 0), (status["severity"], status["errors"]))
            self.assertNotIn("accounting mismatch", json.dumps(result, ensure_ascii=False))
            self.assertIn("NATIVE_ACCOUNTING_GAP", json.dumps(status.get("limitations") or result, ensure_ascii=False) + json.dumps(result, ensure_ascii=False)
                          + (out / "manifest.json").read_text(encoding="utf-8"))
            self.assertIn("Tạo gói báo lỗi", status["action"])
            accounting = _accounting(out)
            self.assertEqual((1, {"dialogue": 1}), (accounting["unaccounted_count"], accounting["unaccounted_by_kind"]))
            from vntext.bug_report import collect_structure
            structure = collect_structure(out)["native_accounting"]
            self.assertEqual(1, structure["unaccounted_count"])
            self.assertRegex(structure["unaccounted"][0]["file"], r"^u\d+\.rpy$")
            self.assertNotIn("part_", json.dumps(structure))

    def test_property_buckets_always_sum_to_native_units_on_random_layouts(self):
        from vntext.user_exclusions import exclude_rows
        for seed in range(6):
            with self.subTest(seed=seed), tempfile.TemporaryDirectory(dir=WORK) as temp:
                rng = random.Random(1000 + seed)
                base = Path(temp); game = base / "game copy"; game.mkdir(); out = base / "out"
                _random_game(game, rng)
                result = _extract(game, out)
                self.assertIn(result.get("extract_status"), {"COMPLETE", "PARTIAL"}, result)
                if rng.random() < 0.7:
                    with open(out / "translation.csv", encoding="utf-8-sig", newline="") as stream:
                        rows = list(csv.DictReader(stream))
                    if rows:
                        picked = rng.sample([row["key"] for row in rows], k=rng.randint(1, max(1, len(rows) // 2)))
                        exclude_rows(out / "translation.csv", picked, hashlib.sha256((out / "translation.csv").read_bytes()).hexdigest())
                        result = _extract(game, out)
                status = _status(out)
                accounting = _accounting(out)
                self.assertEqual(status["native_units"], status["native_accounted"], (seed, status))
                self.assertTrue(status["native_accounting_complete"], (seed, status))
                self.assertEqual(0, accounting["unaccounted_count"], (seed, accounting))
                self.assertEqual(status["native_units"], sum(accounting["buckets"].values()), (seed, accounting))
                self.assertEqual(0, status["errors"], (seed, status))


if __name__ == "__main__":
    unittest.main()
