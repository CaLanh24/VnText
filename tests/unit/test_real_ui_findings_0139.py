"""0.1.39: findings from driving the installed app by hand (each one was seen on screen, then fixed)."""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
APP = ROOT / "wpf_app" / "VNText.Studio.App"


def _read(path):
    return path.read_text(encoding="utf-8").replace("\r\n", "\n")


class RealUiFindingTests(unittest.TestCase):
    def test_saving_revalidates_after_the_review_ledger_was_pruned(self):
        # "Chấp nhận đề xuất" saved the file but the row kept "Đã dịch — bấm Lưu" and the review count did not drop.
        text = _read(APP / "ViewModels" / "MainViewModel.CsvEditor.cs")
        self.assertRegex(text, r"var save = TranslationCsvEditorService\.Save\(path, fields, rows, expectedSha256\);\n(?:.*\n)*?\s+if \(save\.Ok\)\n\s+\{\n\s+var after = TranslationCsvEditorService\.Validate\(path, rows\);")

    def test_a_translation_waiting_for_review_is_a_warning_with_the_next_step(self):
        text = _read(APP / "ViewModels" / "MainViewModel.Worker.cs")
        self.assertIn("RecordPersistent(completedTask, HumanReviewWaitingText(evt.HumanReviewRequiredCount), \"\", warning: true);", text)
        self.assertIn("Chấp nhận đề xuất", text)

    def test_no_developer_word_is_left_in_the_build_result_messages(self):
        for rel in ("ViewModels/MainViewModel.Worker.cs", "Services/UiText.cs"):
            text = _read(APP / rel)
            self.assertNotIn("Tạo overlay Ren'Py hoàn tất", text, rel)
            self.assertNotIn("ngoài CSV", text, rel)
        python = _read(ROOT / "vntext" / "app_tasks.py")
        self.assertNotIn("Ren'Py native overlay nằm tại", python)

    def test_the_model_download_is_online_only_inside_the_explicit_repair(self):
        text = _read(ROOT / "vntext_worker" / "resource_tasks.py")
        self.assertRegex(text, r"with _online_for_model_download\(\):\n\s+ensure_model\(folder, download=True\)")


if __name__ == "__main__":
    unittest.main()
