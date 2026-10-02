from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from vntext.entry import make_key
from vntext.package_io import read_csv_rows_file, write_package
from vntext.patchability import REVIEW_REQUIRED, SUPPORTED_AND_PATCHABLE, assess_entry, validate_renpy_contract
from vntext.renpy_extract import RenPyTemplateParseError, extract_native_template_entries


class RenPyNativeExtractionTests(unittest.TestCase):
    def _fixture(self, root: Path, *, conflicting_strings: bool = False) -> tuple[Path, Path]:
        game = root / "game"
        game.mkdir(parents=True)
        (game / "story.rpy").write_text(
            'label start:\n'
            '    e "Same source"\n'
            '    e "Same source"\n'
            '    $ code_literal = "Only in code"\n'
            '    $ native_only = "Native only"\n',
            encoding="utf-8",
        )
        (game / "ui.rpy").write_text('screen test:\n    text _("Open")\n', encoding="utf-8")
        templates = root / "generated" / "tl" / "vietnamese"
        templates.mkdir(parents=True)
        second_target = 'new "Different"' if conflicting_strings else 'new ""'
        (templates / "00_strings.rpy").write_text(
            "translate vietnamese strings:\n\n"
            "    # game/ui.rpy:2\n"
            '    old "Open"\n'
            '    new ""\n'
            "\n"
            "    # game/ui.rpy:2\n"
            '    old "Open"\n'
            f"    {second_target}\n",
            encoding="utf-8",
        )
        (templates / "10_dialogue.rpy").write_text(
            "# game/story.rpy:2\n"
            "translate vietnamese same_a:\n\n"
            '    # e "Same source"\n'
            '    e ""\n'
            "\n"
            "# game/story.rpy:3\n"
            "translate vietnamese same_b:\n\n"
            '    # e "Same source"\n'
            '    e ""\n'
            "\n"
            "# game/story.rpy:5\n"
            "translate vietnamese native_only:\n\n"
            '    # "Native only"\n'
            '    ""\n',
            encoding="utf-8",
        )
        return root, templates

    def test_native_units_are_canonical_and_contract_complete(self):
        with tempfile.TemporaryDirectory() as temp:
            root, templates = self._fixture(Path(temp))
            main, review, stats = extract_native_template_entries(root, templates)

        self.assertEqual(review, [])
        self.assertEqual([entry.source_text for entry in main], ["Open", "Open", "Same source", "Same source", "Native only"])
        dialogue = [entry for entry in main if entry.import_method == "renpy_dialogue"]
        self.assertEqual([entry.locator["native_id"] for entry in dialogue], ["same_a", "same_b", "native_only"])
        self.assertEqual(len({entry.key for entry in dialogue if entry.source_text == "Same source"}), 2)
        self.assertEqual([assess_entry(entry).status for entry in main], [SUPPORTED_AND_PATCHABLE] * 5)
        self.assertTrue(all(entry.native_contract["precondition"]["template_sha256"] for entry in main))
        self.assertTrue(all(entry.native_contract["precondition"]["source_sha256"] for entry in main))
        self.assertEqual(stats["native_units"], 5)
        self.assertEqual(stats["native_dialogue_units"], 3)
        self.assertEqual(stats["native_string_units"], 2)

    def test_native_route_does_not_promote_source_code_literals(self):
        with tempfile.TemporaryDirectory() as temp:
            root, templates = self._fixture(Path(temp))
            main, _review, _stats = extract_native_template_entries(root, templates)

        self.assertNotIn("Only in code", [entry.source_text for entry in main])

    def test_conflicting_same_source_native_strings_fail_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            root, templates = self._fixture(Path(temp), conflicting_strings=True)
            with self.assertRaisesRegex(RenPyTemplateParseError, "conflicting native string source"):
                extract_native_template_entries(root, templates)

    def test_source_parser_failure_does_not_remove_native_units(self):
        with tempfile.TemporaryDirectory() as temp:
            root, templates = self._fixture(Path(temp))
            with patch("vntext.renpy_extract.extract_loose_source", side_effect=AssertionError("source parser called")):
                main, review, _stats = extract_native_template_entries(root, templates)

        self.assertEqual(len(main), 5)
        self.assertEqual(review, [])

    def test_exact_source_enrichment_is_additive_and_bounded(self):
        with tempfile.TemporaryDirectory() as temp:
            root, templates = self._fixture(Path(temp))
            main, _review, _stats = extract_native_template_entries(root, templates)

        by_id = {entry.locator.get("native_id"): entry for entry in main if entry.import_method == "renpy_dialogue"}
        first = by_id["same_a"]
        first_context = first.native_contract["context"]
        self.assertEqual(first.object_info, "e")
        self.assertEqual(first_context["enrichment"], {"status": "RESOLVED", "authoritative": False})
        self.assertEqual(first_context["context_group"], "label:start")
        self.assertEqual(first_context["previous"], [])
        self.assertEqual(first_context["next"], ["Same source"])
        self.assertEqual(first.native_contract["provenance"]["source_span"], {
            "line": 2,
            "start_column": 7,
            "end_column": 19,
        })
        self.assertEqual(validate_renpy_contract(first.to_manifest()), "")
        self.assertEqual(by_id["same_b"].native_contract["context"]["previous"], ["Same source"])
        self.assertTrue(all(len(entry.native_contract["context"]["previous"]) <= 1 for entry in main))
        self.assertTrue(all(len(entry.native_contract["context"]["next"]) <= 1 for entry in main))
        self.assertTrue(all(len(value) <= 240 for entry in main for side in ("previous", "next") for value in entry.native_contract["context"][side]))

    def test_mismatched_source_provenance_keeps_native_contract_patchable_without_fuzzy_fallback(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "game").mkdir()
            (root / "game" / "story.rpy").write_text(
                'label start:\n'
                '    e "Changed at the exact line"\n'
                '    e "Expected only elsewhere"\n',
                encoding="utf-8",
            )
            templates = root / "generated"
            templates.mkdir()
            (templates / "dialogue.rpy").write_text(
                "# game/story.rpy:2\n"
                "translate vietnamese expected_id:\n\n"
                '    # e "Expected only elsewhere"\n'
                '    e ""\n',
                encoding="utf-8",
            )
            main, review, _stats = extract_native_template_entries(root, templates)

        self.assertEqual(review, [])
        entry = main[0]
        self.assertEqual(assess_entry(entry).status, SUPPORTED_AND_PATCHABLE)
        enrichment = entry.native_contract["context"]["enrichment"]
        self.assertEqual(enrichment["status"], "MISMATCH")
        self.assertFalse(enrichment["authoritative"])
        self.assertTrue(enrichment["reason"])
        self.assertNotIn("source_span", entry.native_contract["provenance"])
        self.assertEqual(entry.native_contract["context"]["previous"], [])
        self.assertEqual(entry.native_contract["context"]["next"], [])
        self.assertEqual(entry.locator, {"native_id": "expected_id", "unit_type": "dialogue"})
        self.assertEqual(entry.key, make_key(entry.file_path, entry.context, entry.source_text, entry.import_method))

    def test_ambiguous_string_line_is_retained_without_source_search(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "game").mkdir()
            (root / "game" / "ui.rpy").write_text(
                'screen test:\n    text _("Open") + text _("Open")\n',
                encoding="utf-8",
            )
            templates = root / "generated"
            templates.mkdir()
            (templates / "strings.rpy").write_text(
                "translate vietnamese strings:\n\n"
                "    # game/ui.rpy:2\n"
                '    old "Open"\n'
                '    new ""\n',
                encoding="utf-8",
            )
            main, review, _stats = extract_native_template_entries(root, templates)

        self.assertEqual(review, [])
        entry = main[0]
        self.assertEqual(entry.native_contract["context"]["enrichment"]["status"], "AMBIGUOUS")
        self.assertNotIn("source_span", entry.native_contract["provenance"])
        self.assertEqual(assess_entry(entry).status, SUPPORTED_AND_PATCHABLE)

    def test_full_string_reconciliation_keeps_common_and_sdk_only_out_of_main(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "game").mkdir()
            game_values = ["Q.Save", "Q.Load", ">", "<"] + [f"Game string {index}" for index in range(79)]
            (root / "game" / "strings.rpy").write_text(
                "\n".join(
                    f"    $ value_{index} = _({json.dumps(text, ensure_ascii=False)})"
                    for index, text in enumerate(game_values, start=1)
                )
                + "\n",
                encoding="utf-8",
            )
            common_values = ["joystick...", "60", "30"] + [f"Common string {index}" for index in range(302)]
            common_path = root / "renpy" / "common" / "common.rpy"
            common_path.parent.mkdir(parents=True)
            common_path.write_text(
                "\n".join(
                    f"    $ value_{index} = _({json.dumps(text, ensure_ascii=False)})"
                    for index, text in enumerate(common_values, start=1)
                )
                + "\n",
                encoding="utf-8",
            )
            sdk_only = [f"SDK-only {index}" for index in range(3)]
            template = root / "generated"
            template.mkdir()
            units = []
            for index, text in enumerate(game_values, start=1):
                units.extend([f"    # game/strings.rpy:{index}", f"    old {json.dumps(text, ensure_ascii=False)}", '    new ""'])
            for index, text in enumerate(common_values, start=1):
                units.extend([f"    # renpy/common/common.rpy:{index}", f"    old {json.dumps(text, ensure_ascii=False)}", '    new ""'])
            for index, text in enumerate(sdk_only, start=1):
                units.extend([f"    # renpy/common/00translation.rpy:{index}", f"    old {json.dumps(text, ensure_ascii=False)}", '    new ""'])
            (template / "strings.rpy").write_text(
                "translate vietnamese strings:\n\n" + "\n".join(units) + "\n",
                encoding="utf-8",
            )
            main, review, stats = extract_native_template_entries(root, template)
            package = root / "package"
            write_package(str(package), main, review, stats, separate_review=True, enforce_symmetry=True)
            manifest = json.loads((package / "manifest.json").read_text(encoding="utf-8"))
            translation_rows = read_csv_rows_file(package / "translation.csv")[1]
            review_rows = read_csv_rows_file(package / "review_only.csv")[1]
            technical_rows = read_csv_rows_file(package / "technical_skipped.csv")[1]

        self.assertEqual(stats["native_string_units"], 391)
        self.assertEqual(stats["native_string_unique_sources"], 391)
        self.assertEqual(stats["native_string_ownership_counts"], {"game_owned": 83, "renpy_common": 308})
        self.assertEqual(
            stats["native_string_ledger_counts"],
            {"missing_source": 3, "review_only": 302, "technical_skipped": 7, "translation_csv": 79},
        )
        reconciliation = stats["native_string_reconciliation"]
        self.assertEqual(reconciliation["common_runtime_count"], 305)
        self.assertEqual(reconciliation["sdk_only_count"], 3)
        self.assertEqual(reconciliation["auto_patchable_count"], 79)
        self.assertEqual(len(main), 86)
        self.assertEqual(len(review), 305)
        self.assertEqual(len(translation_rows), 79)
        self.assertEqual(len(review_rows), 305)
        self.assertEqual(len(technical_rows), 7)
        self.assertEqual(len(manifest["entries"]) + len(manifest["technical_skipped"]), 391)
        self.assertEqual(manifest["stats"]["native_string_reconciliation"], reconciliation)
        common_review = next(entry for entry in review if entry.source_text == "Common string 1")
        self.assertEqual(assess_entry(common_review).status, REVIEW_REQUIRED)
        self.assertEqual(common_review.native_contract["provenance"]["owner"], "renpy_common")
        common_manifest = common_review.to_manifest()
        common_manifest["review_only"] = False
        self.assertIn("not game-owned", validate_renpy_contract(common_manifest))
        sdk_entry = next(entry for entry in review if entry.source_text == "SDK-only 1")
        self.assertEqual(sdk_entry.native_contract["provenance"]["disposition"], "sdk_only")
        self.assertFalse(sdk_entry.native_contract["provenance"]["source_available"])


if __name__ == "__main__":
    unittest.main()
