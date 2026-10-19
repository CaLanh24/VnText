"""Boundary gates for the test-only contextual prompt experiment."""
import copy
import unittest

from tests.tools.translation_quality_prompt_trial import context_for, prompt_for, output_from, completion_output


class PromptBoundaryTests(unittest.TestCase):
    def row(self, turn=3, **changes):
        value = {"id": str(turn), "split": "development", "source_en": "line " + str(turn),
                 "group": "dialogue", "scenario_boundary": {"file_id": "f", "group_id": "g",
                 "engine": "synthetic", "kind": "same_file_scene", "turn": turn}}
        value.update(changes)
        return value

    def test_context_excludes_future_other_file_group_engine_and_split(self):
        target = self.row()
        rows = [self.row(1), self.row(2), self.row(4)]
        for field in ("file_id", "group_id", "engine"):
            other = self.row(1)
            other["id"] = "wrong-" + field
            other["scenario_boundary"][field] = "other"
            rows.append(other)
        rows.append(self.row(1, id="held-out", split="held_out"))
        context, ids = context_for(target, rows)
        self.assertEqual(ids, ["1", "2"])
        self.assertEqual(context, "line 1\nline 2")

    def test_context_window_and_standalone_exclusion(self):
        target = self.row(5)
        self.assertEqual(context_for(target, [self.row(n) for n in range(1, 5)])[1], ["3", "4"])
        target["scenario_boundary"]["kind"] = "standalone_line"
        self.assertEqual(context_for(target, [self.row(4)]), ("", []))

    def test_source_is_final_and_only_repair_contains_draft(self):
        target = self.row(source_en="Keep {PLAYER} and <b>text</b> \\n", address_context="Clerk to supervisor")
        original = copy.deepcopy(target)
        for variant in ("source", "context", "repair"):
            prompt, ids = prompt_for(target, [self.row(2)], variant, "DRAFT_ERROR")
            self.assertTrue(prompt.endswith("[Source Text]\n" + target["source_en"]))
            self.assertEqual("DRAFT_ERROR" in prompt, variant == "repair")
            self.assertEqual("Clerk to supervisor" in prompt, variant != "source")
            self.assertEqual(ids, [] if variant == "source" else ["2"])
        self.assertEqual(target, original)

    def test_term_matching_uses_source_whole_words_only(self):
        target = self.row(source_en="The cachet is missing.")
        prompt, _ = prompt_for(target, [self.row(2, source_en="cache manifest")], "context", "")
        self.assertNotIn("Reference terminology:", prompt)
        target["source_en"] = "The CACHE manifest."
        prompt, _ = prompt_for(target, [], "source", "")
        self.assertIn("cache translates to bộ nhớ đệm", prompt)
        self.assertIn("manifest translates to bản kê khai", prompt)

    def test_output_parser_rejects_missing_ambiguous_or_unfinished_boundary(self):
        self.assertEqual(output_from({"prompt": "source", "stdout": "banner\n> source\nresult\n[ Prompt: 5 ]\nExiting"}), "result")
        for text in ("result", "> source\nresult", "> source\n> source\nresult\n[ Prompt:"):
            with self.assertRaises(ValueError):
                output_from({"prompt": "source", "stdout": text})

    def test_completion_removes_only_terminal_transport_marker(self):
        self.assertEqual(completion_output("\nHello {PLAYER}\\n [end of text]\n"), "Hello {PLAYER}\\n")
        self.assertEqual(completion_output("[end of text] remains inside translation"), "[end of text] remains inside translation")

    def test_concise_prompt_source_last_no_cross_row_hints(self):
        target = self.row(source_en="{PLAYER}, go back.")
        prompt, ids = prompt_for(target, [self.row(2)], "context", "WRONG_DRAFT", "concise")
        self.assertTrue(prompt.endswith("\n\n" + target["source_en"]))
        self.assertIn("Preserve placeholders", prompt)
        self.assertNotIn("WRONG_DRAFT", prompt)
        self.assertEqual(ids, ["2"])


if __name__ == "__main__":
    unittest.main()
