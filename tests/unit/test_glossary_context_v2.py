from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from vntext.context_builder import (
    CONTEXT_BUILDER_VERSION,
    build_context_records,
    build_context_sidecar,
)
from vntext.glossary_v2 import (
    load_compatible_entries,
    load_glossary_v2,
    mask_terms,
    resolve_exact,
    restore_terms,
)
from vntext.mt_ct2_io import _batch_translate_chunk


class _FakeTranslator:
    def translate_many(self, texts):
        return [f"VI:{text}" for text in texts]


class GlossaryContextV2Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="vntext-glossary-context-")
        self.root = Path(self.temp.name)
        (self.root / ".mt" / "v2").mkdir(parents=True)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _write_glossary(self, entries):
        (self.root / ".mt" / "v2" / "glossary.json").write_text(
            json.dumps({"schema_version": 1, "entries": entries}, ensure_ascii=False),
            encoding="utf-8",
        )

    def test_v2_glossary_exact_scope_and_conflict_fail_closed(self):
        self._write_glossary([
            {"source": "CharacterName", "target": "CharacterName", "kind": "proper_noun", "priority": 10, "scope": "NaninovelScript"},
            {"source": "Start game", "target": "Bắt đầu game", "kind": "fixed_phrase", "priority": 20},
            {"source": "Conflict", "target": "Một", "kind": "fixed_phrase", "priority": 5},
            {"source": "Conflict", "target": "Hai", "kind": "fixed_phrase", "priority": 5},
        ])
        glossary = load_glossary_v2(self.root)
        self.assertEqual(resolve_exact("CharacterName", {"context": "NaninovelScript:Main"}, glossary)["status"], "match")
        self.assertEqual(resolve_exact("CharacterName", {"context": "TextAsset:Main"}, glossary)["status"], "miss")
        self.assertEqual(resolve_exact("Conflict", {}, glossary)["status"], "conflict")
        self.assertTrue(glossary["fingerprint"])

    def test_v2_masks_terms_outside_protected_spans_and_restores(self):
        self._write_glossary([
            {"source": "CharacterName", "target": "CharacterName", "kind": "proper_noun", "priority": 10},
            {"source": "special mode", "target": "chế độ đặc biệt", "kind": "fixed_phrase", "priority": 1},
        ])
        glossary = load_glossary_v2(self.root)
        source = "CharacterName enters special mode <color=CharacterName> {CharacterName}"
        masked, restores, conflicts = mask_terms(source, {}, glossary)
        self.assertEqual(conflicts, [])
        self.assertNotIn("special mode", masked)
        self.assertIn("<color=CharacterName>", masked)
        self.assertIn("{CharacterName}", masked)
        self.assertEqual(
            restore_terms(masked.replace("enters", "đi vào"), restores),
            "CharacterName đi vào chế độ đặc biệt <color=CharacterName> {CharacterName}",
        )

    def test_v2_compatible_loader_keeps_flat_glossary(self):
        (self.root / ".mt" / "glossary.json").write_text(
            json.dumps({"Hello": "Xin chào"}), encoding="utf-8"
        )
        self._write_glossary([
            {"source": "CharacterName", "target": "CharacterName", "kind": "proper_noun"},
        ])
        compatible = load_compatible_entries(self.root)
        sources = {entry["source"] for entry in compatible["entries"]}
        self.assertEqual(sources, {"hello", "CharacterName"})
        self.assertTrue(compatible["fingerprint"])

    def test_batch_translation_applies_v2_exact_and_masked_terms(self):
        glossary = {
            "schema_version": 1,
            "entries": [
                {"source": "Start game", "target": "Bắt đầu game", "kind": "fixed_phrase", "priority": 10},
                {"source": "CharacterName", "target": "CharacterName", "kind": "proper_noun", "priority": 10},
            ],
        }
        rows = [
            {"key": "exact", "source_text": "Start game", "context": "UI:Text"},
            {"key": "masked", "source_text": "CharacterName enters.", "context": "NaninovelScript:Main"},
        ]
        result = _batch_translate_chunk(
            _FakeTranslator(), rows, {}, {}, v2_glossary=glossary, glossary_conflicts=set()
        )
        self.assertEqual(result["exact"], "Bắt đầu game")
        self.assertIn("CharacterName", result["masked"])
        self.assertNotIn("ZZG900000ZZG", result["masked"])

    def test_conflicting_term_is_reported_without_model_output(self):
        glossary = {
            "schema_version": 1,
            "entries": [
                {"source": "Conflict", "target": "Một", "kind": "fixed_phrase", "priority": 1},
                {"source": "Conflict", "target": "Hai", "kind": "fixed_phrase", "priority": 1},
            ],
        }
        conflicts = set()
        result = _batch_translate_chunk(
            _FakeTranslator(),
            [{"key": "k", "source_text": "Conflict", "context": "UI:Text"}],
            {},
            {},
            v2_glossary=glossary,
            glossary_conflicts=conflicts,
        )
        self.assertEqual(result["k"], "")
        self.assertEqual(conflicts, {"k"})

    def test_context_does_not_guess_cross_file_or_missing_boundaries(self):
        rows = [
            {"key": "a", "source_text": "A", "file_path": "one", "context_group": "scene-1", "import_method": "plain_text_line"},
            {"key": "b", "source_text": "B", "file_path": "one", "context_group": "scene-1", "import_method": "plain_text_line"},
            {"key": "c", "source_text": "C", "file_path": "two", "context_group": "scene-1", "import_method": "plain_text_line"},
            {"key": "d", "source_text": "D", "file_path": "one", "import_method": "plain_text_line"},
        ]
        records = build_context_records(rows, max_chars=100, max_items=1)
        self.assertEqual(records[0]["status"], "bounded")
        self.assertEqual(records[0]["next"], ["B"])
        self.assertEqual(records[1]["previous"], ["A"])
        self.assertEqual(records[1]["next"], [])
        self.assertEqual(records[2]["previous"], [])
        self.assertEqual(records[3]["status"], "insufficient_metadata")

    def test_context_sidecar_is_bounded_and_versioned(self):
        result = build_context_sidecar(
            self.root,
            [{"key": "k", "source_text": "Hello", "file_path": "a", "import_method": "plain_text_line"}],
        )
        self.assertEqual(result["builder_version"], CONTEXT_BUILDER_VERSION)
        self.assertEqual(result["status"], "METADATA_ONLY")
        self.assertFalse(result["model_injection"])
        self.assertEqual(result["insufficient_metadata"], 1)
        line = (self.root / ".mt" / "v2" / "context.jsonl").read_text(encoding="utf-8").strip()
        self.assertEqual(json.loads(line)["schema_version"], 1)


if __name__ == "__main__":
    unittest.main()
