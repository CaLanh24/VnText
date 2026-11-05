"""Curated exact-label UI catalog (Owner decision 2026-11-02): exact standalone labels in an explicit UI context only; glossaries rank above it."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

cur = Path(__file__).resolve().parent
while cur.name != "tests" and cur.parent != cur:
    cur = cur.parent
sys.path.insert(0, str(cur / "lib"))
from bootstrap import bootstrap

TESTS, ROOT, LIB = bootstrap(__file__)

from tests.lib.work_paths import work_temp_dir
from vntext.image_batch import translate_region_texts
from vntext.mt_classify import classify_row_authoritative
from vntext.ui_labels import resolve_ui_label_translation


class Model:
    """Stands in for the offline model and reproduces its real weakness on one-word labels."""
    def __init__(self):
        self.seen = []

    def translate_many(self, texts):
        self.seen += list(texts)
        return ["Nhà phát minh" if text == "Inventory" else "MODEL:" + text for text in texts]


class UiLabelCatalogTests(unittest.TestCase):
    def test_standard_menu_labels_resolve_only_as_exact_standalone_labels_in_a_ui_context(self):
        expected = {"Inventory": "Túi đồ", "Save": "Lưu", "Load": "Tải", "Options": "Tùy chọn", "Settings": "Cài đặt",
                    "New Game": "Trò chơi mới", "Quit": "Thoát", "Continue": "Tiếp tục", "Back": "Quay lại"}
        for source, target in expected.items():
            with self.subTest(source):
                self.assertEqual(target, resolve_ui_label_translation(source, "UI:Menu"))
        self.assertEqual("TÚI ĐỒ", resolve_ui_label_translation("INVENTORY", "UI:Menu"))      # ALL-CAPS art stays in capitals
        self.assertEqual("Túi đồ", resolve_ui_label_translation("  inventory ", "UI:Menu"))   # case/space tolerant, still exact
        self.assertEqual("Lưu game", resolve_ui_label_translation("Save   Game", "UI:Menu"))

    def test_ambiguous_prose_choices_tokens_and_unknown_contexts_never_force_the_catalog(self):
        ui = "UI:Menu"
        for source in ("Save the world", "Inventory is full", "Please load the game now", "Save [name]", "{b}Save{/b}", "Save %s",
                       "Options.", "Inventories", "OK", "Save\\nLoad", "Save, Load"):
            with self.subTest(source):
                self.assertIsNone(resolve_ui_label_translation(source, ui))
        for context in ("", "NaninovelScript:Main:12", "TextAsset:story:line:4", "NaninovelScript:Main:3:choice", "renpy_dialogue:say"):
            with self.subTest(context):
                self.assertIsNone(resolve_ui_label_translation("Save", context))             # a story choice/dialogue "Save" is not a menu label

    def test_classification_routes_a_menu_label_but_not_the_same_word_in_story_text(self):
        menu = {"key": "k1", "source_text": "Inventory", "translation": "", "context": "UI:Menu", "file_path": "g.txt", "import_method": "unity_ui_text"}
        story = {**menu, "key": "k2", "context": "TextAsset:story:line:4", "import_method": "unity_textasset_line"}
        self.assertEqual(("ui_label_fixed", "Túi đồ"), classify_row_authoritative(menu)[:2])
        self.assertEqual("translate", classify_row_authoritative(story)[0])

    def test_image_regions_use_the_catalog_for_exact_labels_and_the_model_for_the_rest(self):
        model = Model()
        result = translate_region_texts(model, ["INVENTORY", "Save", "Welcome home", "Inventory is full"])
        self.assertEqual(["TÚI ĐỒ", "Lưu", "MODEL:Welcome home", "MODEL:Inventory is full"], result)
        self.assertEqual(["Welcome home", "Inventory is full"], model.seen)                   # catalog labels never reach the model
        self.assertEqual([], translate_region_texts(Model(), []))

    def test_user_and_package_glossary_outrank_the_catalog_in_the_translate_pipeline(self):
        from vntext.mt_ct2_pipeline import run_ct2_translate
        with tempfile.TemporaryDirectory(dir=work_temp_dir("ui-label-catalog")) as temp:
            package = Path(temp)
            (package / ".mt").mkdir()
            (package / ".mt" / "glossary.json").write_text(json.dumps({"Save": "Ghi lại"}), encoding="utf-8")
            csv_path = package / "translation.csv"
            csv_path.write_text(
                "key,source_text,translation,context,file_path,import_method\n"
                "k1,Inventory,,UI:Menu,game/ui.txt,unity_ui_text\n"
                "k2,Save,,UI:Menu,game/ui.txt,unity_ui_text\n"
                "k3,Load,,UI:Menu,game/ui.txt,unity_ui_text\n",
                encoding="utf-8",
            )
            model = Model()
            model.config = {"batch_size": 8, "inter_threads": 1, "flush_every": 8}
            with patch("vntext.mt_ct2_model.get_translator", return_value=model):
                result = run_ct2_translate(csv_path, model_dir=package)
            import csv as csv_module
            with csv_path.open(encoding="utf-8-sig", newline="") as stream:
                rows = {row["key"]: row["translation"] for row in csv_module.DictReader(stream)}
            self.assertEqual("Túi đồ", rows["k1"])                                           # catalog beats the model's "Nhà phát minh"-style output
            self.assertEqual("Tải", rows["k3"], (rows, result))
            self.assertNotIn("Save", model.seen)                                             # catalog labels and glossary terms never reach the model
            self.assertEqual("Ghi lại", rows["k2"], {k: v for k, v in result.items() if k in ("error", "review_only", "blocked", "pending", "summary", "ok")})                                          # the user glossary keeps the higher priority


class RenpyConfirmationPromptTests(unittest.TestCase):
    """The delete-save prompt was translated as a folder question ("xoá thư mục này"); the stock prompt now has an exact catalog entry."""

    def test_stock_delete_save_prompt_is_exact_and_context_bounded(self):
        source = "Are you sure you want to delete this save?"
        self.assertEqual("Bạn có chắc muốn xóa bản lưu này không?", resolve_ui_label_translation(source, "RenPy:game/screens.rpy:1614:string:screens.rpy:231"))
        self.assertIsNone(resolve_ui_label_translation(source, "RenPy:game/script.rpy:40:start"))
        self.assertIsNone(resolve_ui_label_translation(source + " Really?", "RenPy:game/screens.rpy:1614:string:screens.rpy:231"))
        self.assertIsNone(resolve_ui_label_translation(source, "RenPy:game/script.rpy:40:choice"))


if __name__ == "__main__":
    unittest.main()
