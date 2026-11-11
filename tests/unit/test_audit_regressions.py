"""Small, in-memory regressions for the 2026-11-11 repository audit."""
from pathlib import Path
import unittest
from unittest.mock import patch

from PIL import Image
from release.make_icon import _fit_square
from vntext import csv_editor_api


class IconAlphaTests(unittest.TestCase):
    def test_translucent_pixels_keep_color_and_alpha(self):
        image = Image.new("RGBA", (2, 2), (255, 0, 0, 128))
        result = _fit_square(image, 4, padding=0)
        self.assertEqual(result.getpixel((1, 1)), (255, 0, 0, 128))
        self.assertEqual(result.getpixel((0, 0)), (0, 0, 0, 0))

    def test_opaque_pixels_remain_opaque(self):
        result = _fit_square(Image.new("RGBA", (2, 2), (20, 40, 60, 255)), 4, padding=0)
        self.assertEqual(result.getpixel((1, 1)), (20, 40, 60, 255))


class ReplaceRollbackTests(unittest.TestCase):
    def _replace(self, rollback_error):
        fields = ["key", "source_text", "translation"]
        rows = [{"key": "k1", "source_text": "Hello", "translation": "Xin chào"}]
        with patch.object(csv_editor_api, "validate_document", return_value={"ok": True}), \
             patch.object(csv_editor_api, "backup_translation_csv", return_value=Path("backup.csv")), \
             patch.object(csv_editor_api, "read_csv_rows_file", return_value=(fields, rows)), \
             patch.object(csv_editor_api, "_atomic_write_csv", side_effect=[OSError("write failed"), rollback_error]):
            return csv_editor_api.replace_translation("translation.csv", fields, rows, "chào", "chào bạn")

    def test_rollback_failure_is_not_reported_as_success(self):
        result = self._replace(OSError("restore denied"))
        self.assertFalse(result["ok"])
        self.assertFalse(result["rolled_back"])
        self.assertTrue(result["rollback_failed"])
        self.assertIn("write failed", result["error"])
        self.assertIn("restore denied", result["error"])
        self.assertEqual(result["backup_path"], "backup.csv")

    def test_completed_rollback_is_reported(self):
        result = self._replace(None)
        self.assertFalse(result["ok"])
        self.assertTrue(result["rolled_back"])
        self.assertNotIn("rollback_failed", result)


if __name__ == "__main__":
    unittest.main()
