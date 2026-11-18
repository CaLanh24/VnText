"""Job accounting and font evidence without a game, model download or runtime."""
import struct
import hashlib
from pathlib import Path
from unittest.mock import patch
import unittest
from vntext.selected_translation import selected_outcomes
from vntext.patch_font_preflight import required_characters, font_report
from vntext.font_coverage import cmap_glyphs


class SelectedRowsTests(unittest.TestCase):
    def test_csv_preflight_separates_technical_from_human_review_and_is_revision_bound(self):
        from vntext.csv_editor_api import translation_eligibility
        raw = b'key,source_text,translation,import_method\r\na,Hello there.,,renpy_dialogue\r\nb,gui/button/idle.png,,\r\nc,[page],,renpy_screen_candidate\r\nd,Please wait.,,renpy_dialogue\r\n'
        digest = hashlib.sha256(raw).hexdigest()
        with patch.object(Path, "read_bytes", return_value=raw), patch("vntext.mt_ct2_status._load_human_review_keys", return_value={"d"}):
            result = translation_eligibility(Path("fixture.csv"), digest.upper())["rows"]
            self.assertTrue(result["a"]["eligible"])
            self.assertTrue(result["b"]["technical"])
            self.assertTrue(result["c"]["technical"])
            self.assertFalse(result["c"]["eligible"])
            self.assertFalse(result["d"]["eligible"])
            self.assertFalse(result["d"]["technical"])
            with self.assertRaisesRegex(ValueError, "CSV changed"):
                translation_eligibility(Path("fixture.csv"), "0" * 64)

    def test_preexisting_translation_is_not_counted_as_applied_when_this_job_did_not_apply_it(self):
        _, counts = selected_outcomes([{"key": "a", "source_text": "Hello there.", "translation": "Xin chào."}], ["a"], applied_keys=[])
        self.assertEqual(counts["failed"], 1)
        self.assertEqual(counts["applied"], 0)

    def test_audited_machine_exclusion_is_skipped_not_a_missing_key_failure(self):
        outcomes, counts = selected_outcomes([], ["old", "missing"], excluded_keys={"old"})
        self.assertEqual(counts["skipped"], 1)
        self.assertEqual(counts["failed"], 1)
        self.assertEqual(outcomes[0]["reason"], "machine_technical_excluded")
    def test_mixed_selection_accounts_each_key_without_filling_technical_rows(self):
        rows = [{"key": "text", "source_text": "Hello, [name]!", "translation": "Chào, [name]!"},
                {"key": "path", "source_text": "gui/button/idle.png", "translation": ""},
                {"key": "placeholder", "source_text": "[name]", "translation": ""},
                {"key": "unselected", "source_text": "Keep me.", "translation": "MANUAL"}]
        outcomes, counts = selected_outcomes(rows, ["text", "path", "placeholder"])
        self.assertEqual(counts, {"applied": 1, "skipped": 2, "review": 0, "failed": 0})
        self.assertEqual([r["key"] for r in outcomes], ["text", "path", "placeholder"])
        self.assertTrue(all(r["reason"] for r in outcomes))
        self.assertEqual(rows[-1]["translation"], "MANUAL")
        self.assertEqual(rows[1]["translation"], "")

    def test_missing_and_unsaved_text_are_real_failures_protected_row_is_review(self):
        rows = [{"key": "a", "source_text": "Hello there.", "translation": ""},
                {"key": "b", "source_text": "Another sentence.", "translation": ""}]
        outcomes, counts = selected_outcomes(rows, ["a", "b", "missing", "a"], protected_keys={"b"})
        self.assertEqual(counts, {"applied": 0, "skipped": 0, "review": 1, "failed": 2})
        self.assertEqual(len(outcomes), 3)


class FontPreflightTests(unittest.TestCase):
    def test_actual_nfc_nfd_and_vietnamese_case_are_checked_syntax_is_excluded(self):
        chars = required_characters(["Đặng đợi {b}Ấn{/b} [name]"])
        for c in "ĐđặngợiẤn\u0302\u0301\u0323": self.assertIn(ord(c), chars)
        self.assertNotIn(ord("{"), chars)
        self.assertNotIn(ord("["), chars)

    def test_unity_unknown_is_not_compatible_and_does_not_claim_ttf_support(self):
        report = font_report("unity", ["Xin chào"])
        self.assertFalse(report["compatible"])
        self.assertEqual(report["mapping_status"], "UNKNOWN")
        self.assertEqual(report["runtime_status"], "NOT_PROVEN")
        self.assertIn("TMP", report["reason"])

    def test_font_parser_rejects_malformed_and_reports_missing_glyph(self):
        from tests.unit.test_renpy_font_cmap_audit import font
        sub = struct.pack('>HHLLL', 12, 0, 28, 0, 1) + struct.pack('>LLL', 65, 65, 3)
        report = cmap_glyphs(font(sub, encoding=10), [65, ord("Đ")])
        self.assertEqual(report["glyph_ids"]["U+0041"], 3)
        self.assertTrue(report["missing"])
        with self.assertRaises((ValueError, KeyError, struct.error)):
            cmap_glyphs(b"invalid", [65])


if __name__ == "__main__": unittest.main()
