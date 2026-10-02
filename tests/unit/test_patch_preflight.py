"""Tests for patch preflight gate — blocks garbage without mutating CSV."""

from __future__ import annotations

import sys
from pathlib import Path

def _tests_lib_on_path() -> None:
    cur = Path(__file__).resolve().parent
    while cur.name != "tests" and cur.parent != cur:
        cur = cur.parent
    lib = cur / "lib"
    p = str(lib)
    if p not in sys.path:
        sys.path.insert(0, p)

_tests_lib_on_path()
from bootstrap import bootstrap
TESTS, ROOT, LIB = bootstrap(__file__)

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from vntext.patch_gate import (
    audit_patch_package,
    has_garbage_repetition,
    has_html_garbage,
    legacy_manifest_reason,
    load_review_only_keys,
    patch_skip_reason,
)


def _entry(key: str, source: str, **extra) -> dict:
    row = {
        "key": key,
        "source_text": source,
        "context": extra.get("context", "UI:Text"),
        "file_path": extra.get("file_path", "Game_Data/data.unity3d"),
        "import_method": extra.get("import_method", "unity_ui_text"),
    }
    row.update(extra)
    return row


class PatchPreflightTests(unittest.TestCase):
    def test_verified_cloud_output_only_skips_ct2_specific_heuristic(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            csv_path = root / "translation.cloud_repair.csv"
            manifest_path = root / "manifest.json"
            csv_path.write_text(
                "key,source_text,translation,context,file_path,import_method\n"
                "money,But money is money!,Nhưng tiền vẫn là tiền!,UI:Text,game/data.unity3d,unity_ui_text\n",
                encoding="utf-8",
            )
            manifest_path.write_text(
                json.dumps({"entries": [_entry("money", "But money is money!")]}),
                encoding="utf-8",
            )
            self.assertEqual(audit_patch_package(csv_path, manifest_path)["blocked"], 1)

            report_path = root / ".mt" / "cloud_repair_import_report.json"
            report_path.parent.mkdir()
            digest = hashlib.sha256(csv_path.read_bytes()).hexdigest()
            report_path.write_text(
                json.dumps({
                    "status": "PASS",
                    "merge_applied": True,
                    "output_path": str(csv_path),
                    "output_sha256": digest,
                    "result_csv_identity": {"sha256": digest},
                }),
                encoding="utf-8",
            )
            self.assertEqual(audit_patch_package(csv_path, manifest_path)["blocked"], 0)

            csv_path.write_text(csv_path.read_text(encoding="utf-8") + "\n", encoding="utf-8")
            self.assertEqual(audit_patch_package(csv_path, manifest_path)["blocked"], 1)

    def test_escort_garbage_repetition_blocked(self):
        trans = (
            "Đồng bán bán bán bán bán bán bán bán bán bán bán bán bán bán bán bán bán bán bán bán "
            "bán bán bán bán bán bán bán bán bán bán bán bán bán bán bán bán bán bán bán bán bán "
            "bán bán bán bán bán bán bán bán bán bán bán bán bán lao"
        )
        entry = _entry("c5c2bdfd4f371e1c", "Escort")
        self.assertTrue(has_garbage_repetition(trans))
        self.assertEqual(patch_skip_reason(entry, trans, set()), "garbage_repetition")

    def test_date_short_wrong_translation_not_structural_block(self):
        entry = _entry("c9228925ef9017e5", "Date")
        trans = "Không có gì khớp"
        self.assertEqual(patch_skip_reason(entry, trans, set()), "")

    def test_removed_profile_metadata_fails_closed(self):
        self.assertIn(
            "legacy_profile_unsupported",
            legacy_manifest_reason({"profile": "removed-profile", "entries": []}),
        )

    def test_removed_locator_metadata_fails_closed(self):
        entry = _entry(
            "legacy-entry",
            "Hello",
            backend="legacy_slot_reference",
        )
        self.assertEqual(
            patch_skip_reason(entry, "Xin chào", set()),
            "legacy_external_reference",
        )

    def test_audit_rejects_legacy_manifest_without_mutating_csv(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            csv_path = root / "translation.csv"
            original = (
                "key,source_text,translation,file_path,import_method\n"
                "k1,Hello,Xin chào,Game:Text,unity_textasset_line\n"
            )
            csv_path.write_text(
                original,
                encoding="utf-8",
            )
            manifest_path = root / "manifest.json"
            manifest_path.write_text(
                json.dumps(
                    {
                        "profile": "removed-profile",
                        "entries": [
                            {
                                "key": "k1",
                                "source_text": "Hello",
                                "file_path": "Game_Data/data.unity3d",
                                "import_method": "unity_textasset_line",
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            before = csv_path.read_text(encoding="utf-8")
            audit = audit_patch_package(csv_path, manifest_path)
            self.assertEqual(audit["eligible"], 0, audit)
            self.assertEqual(audit["reason_counts"].get("legacy_profile_unsupported"), 1)
            self.assertEqual(csv_path.read_text(encoding="utf-8"), before)

    def test_placeholder_or_garbage_blocked(self):
        entry = _entry(
            "bd2f75d416377446",
            "Ahhh... {SWEARING}... Ngggghhh...♡",
            context="TextAsset:scene:line:2",
            import_method="unity_textasset_line",
        )
        trans = "À, ờ... {SWEARING}- - - - - - - - - - - - - - - - - - - - - - - - - - -♡"
        reason = patch_skip_reason(entry, trans, set())
        self.assertTrue(reason in {"garbage_repetition", "tag mismatch", "placeholder mismatch"})

    def test_tag_mismatch_blocked(self):
        entry = _entry(
            "line1",
            "Hello <color=red>world</color>",
            import_method="unity_textasset_line",
        )
        trans = "Xin chào world"
        self.assertEqual(patch_skip_reason(entry, trans, set()), "tag mismatch")

    def test_html_garbage_blocked(self):
        entry = _entry(
            "line2",
            "({mName} {MOAN}s)",
            import_method="unity_textasset_line",
        )
        trans = "(indededede in{mName} {MOAN} ♪lt & lt & lt in in in)"
        self.assertTrue(has_html_garbage(trans))
        self.assertIn(patch_skip_reason(entry, trans, set()), {"html_garbage", "garbage_repetition"})

    def test_comparison_ops_not_html_garbage(self):
        # Tip/HUD có >= / <= / <digit — không được coi là lệch thẻ HTML.
        src = (
            "<color=orange>Hint\\n"
            "(Attractiveness + Pheromone >= 300)\\n"
            "Submissive>=90 & Corruption<50</color>"
        )
        self.assertFalse(has_html_garbage(src))
        entry = _entry("tip1", src, import_method="unity_textasset_line")
        vi = (
            "<color=orange>Gợi ý\\n"
            "(Hấp dẫn + Pheromone >= 300)\\n"
            "Phục tùng>=90 & Tha hóa<50</color>"
        )
        self.assertFalse(has_html_garbage(vi))
        self.assertEqual(patch_skip_reason(entry, vi, set()), "")

    def test_note_spam_and_phrase_loop_are_garbage(self):
        self.assertTrue(has_garbage_repetition("♪ Tôi sẽ có mặt ♪ ♪ Tôi sẽ là ♪♡"))
        self.assertTrue(has_garbage_repetition("có một nốt ♪ duy nhất"))
        self.assertTrue(
            has_garbage_repetition(
                "Không có tổ cảnh hoặc không có tổ cảnh vô hoặc không có tổ cảnh vô"
            )
        )
        self.assertTrue(has_garbage_repetition("Vâng, có bán bán lao {FUCK} Hỡi anh em"))
        self.assertFalse(has_garbage_repetition("Tiếp tục"))

    def test_concatenated_ct2_loop_is_garbage(self):
        self.assertTrue(
            has_garbage_repetition("Kurai unitunitunitunitunitunitunitunitunitunit.")
        )
        glrk_src = (
            "*GLRK* *GLRK* *GLRK*[br](I feel vomit rise as {mName}'s {SALTY} {COCK})"
        )
        glrk_vi = (
            "*GLRK* *GLRK* *GLRK*[br](Tôi cảm thấy buồn nôn khi {COCK} {SALTY} của {mName})"
        )
        self.assertFalse(has_garbage_repetition(glrk_vi))
        self.assertEqual(
            patch_skip_reason(
                _entry("glrk1", glrk_src, import_method="unity_textasset_line"),
                glrk_vi,
                set(),
            ),
            "",
        )

    def test_synonym_valid_translation_passes(self):
        entry = _entry(
            "syn1",
            "{COCK}=boner,cock,dick",
            context="TextAsset:_synonyms:line:1",
            import_method="unity_textasset_line",
        )
        trans = "{COCK}=cặc,cu,cu"
        self.assertEqual(patch_skip_reason(entry, trans, set()), "")

    def test_randpick_repetition_is_not_treated_as_intentional_echo(self):
        entry = _entry(
            "randpick1",
            "RouteAlpha,AreaWest,AreaWest,AreaWest2,RoomA,RoomA,AreaSouth",
            context="NaninovelScript:fixture:2",
            import_method="naninovel_script_string",
        )
        trans = "Comment,Không có bởi bởi bởi bởi bởi bởi bởi bởi bởi bởi"
        self.assertEqual(patch_skip_reason(entry, trans, set()), "garbage_repetition")

    def test_synonym_prefix_mismatch_blocked(self):
        entry = _entry(
            "syn1",
            "{COCK}=boner,cock,dick",
            context="TextAsset:_synonyms:line:1",
            import_method="unity_textasset_line",
        )
        trans = "{DICK}=cặc,cu,cu"
        self.assertIn("synonym prefix mismatch", patch_skip_reason(entry, trans, set()))

    def test_audit_review_only_excluded(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            csv_path = root / "translation.csv"
            manifest_path = root / "manifest.json"
            review_path = root / "review_only.csv"
            csv_path.write_text(
                "key,source_text,translation,context,file_path\n"
                "k1,Hello,Xin chào,UI:Text,game/data.unity3d\n"
                "k2,World,Thế giới,UI:Text,game/data.unity3d\n",
                encoding="utf-8",
            )
            review_path.write_text(
                "key,source_text,translation,context,file_path,patch_note\n"
                "k2,World,,UI:Text,game/data.unity3d,MT blocked\n",
                encoding="utf-8",
            )
            manifest_path.write_text(
                json.dumps(
                    {
                        "entries": [
                            {"key": "k1", "source_text": "Hello", "file_path": "game/data.unity3d"},
                            {"key": "k2", "source_text": "World", "file_path": "game/data.unity3d"},
                        ]
                    }
                ),
                encoding="utf-8",
            )
            audit = audit_patch_package(csv_path, manifest_path)
            self.assertEqual(audit["eligible"], 1)
            self.assertEqual(audit["reason_counts"].get("review_only"), 1)
            self.assertEqual(load_review_only_keys(root), {"k2"})

    def test_audit_does_not_mutate_translation_csv(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            csv_path = root / "translation.csv"
            manifest_path = root / "manifest.json"
            original = (
                "key,source_text,translation,context,file_path\n"
                "k1,Escort,Đồng bán bán bán bán bán bán bán bán bán bán bán bán bán bán bán bán bán "
                "bán bán bán bán bán bán bán bán bán bán bán bán bán bán bán bán bán bán bán bán bán "
                "bán bán bán bán bán bán bán bán bán bán bán bán bán lao,UI:Text,game/data.unity3d\n"
            )
            csv_path.write_text(original, encoding="utf-8")
            manifest_path.write_text(
                json.dumps({"entries": [{"key": "k1", "source_text": "Escort", "file_path": "game/data.unity3d"}]}),
                encoding="utf-8",
            )
            before = csv_path.read_text(encoding="utf-8")
            audit = audit_patch_package(csv_path, manifest_path)
            after = csv_path.read_text(encoding="utf-8")
            self.assertEqual(before, after)
            self.assertEqual(audit["eligible"], 0)
            self.assertEqual(audit["reason_counts"].get("garbage_repetition"), 1)

    def test_large_output_preflight_smoke(self):
        import csv
        from work_paths import work_temp_dir
        package = work_temp_dir("mixed_preflight")
        csv_path = package / "translation.csv"
        manifest_path = package / "manifest.json"
        rows = [{"key": f"garbage-{i}", "source_text": "Escort",
                 "translation": "Đồng " + "bán " * 50, "context": "UI:Text",
                 "file_path": "fixture/data.unity3d"} for i in range(1001)]
        rows.append({**rows[0], "key": "valid", "source_text": "Hello", "translation": "Xin chào"})
        with csv_path.open("w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
        manifest_path.write_text(json.dumps({"entries": [
            {k: v for k, v in row.items() if k != "translation"} for row in rows
        ]}), encoding="utf-8")
        audit = audit_patch_package(csv_path, manifest_path)
        self.assertGreater(audit["translated_rows"], 0)
        self.assertGreater(audit["blocked"], 0)
        self.assertGreater(audit["eligible"], 0)
        self.assertGreater(audit["reason_counts"].get("garbage_repetition", 0), 1000)


if __name__ == "__main__":
    unittest.main()
