"""The restored 'Text trong ảnh' workspace drives these exact worker tasks; this runs the whole chain on real files.

Only the native Windows OCR call is replaced (it is gated by VNTEXT_TEST_NATIVE_IMAGES); every other step is the
production code path: inventory -> OCR document -> reviewed/approved regions -> render -> delivery package ->
install into a game COPY with read-back -> rollback.  Nothing is approved automatically: the approval flags are set
by the test exactly like the reviewer does in the UI, and an unapproved region must be refused.
"""
import hashlib
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image, ImageDraw, ImageFont

from tests.lib.work_paths import work_temp_dir
from vntext_worker import image_tasks

FONT = Path(os.environ.get("SystemRoot", "C:/Windows")) / "Fonts/arial.ttf"


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class ImageWorkspaceChainTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.work = work_temp_dir("image-workspace-chain")

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=self.work)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        # Supported container: genuine Ren'Py layout whose only player-visible text is inside an image.
        self.game = self.root / "container"
        (self.game / "game/images").mkdir(parents=True)
        (self.game / "game/options.rpy").write_text('define config.version = "1.0"\n', encoding="utf-8")
        self.png = self.game / "game/images/ui_01.png"
        image = Image.new("RGBA", (420, 120), (255, 255, 255, 255))
        ImageDraw.Draw(image).text((20, 30), "NEW GAME", font=ImageFont.truetype(str(FONT), 44), fill=(0, 0, 0, 255))
        image.save(self.png)
        self.events = []

    def run_task(self, task, params):
        def complete(task_id, **kwargs):
            self.events.append((task, kwargs))
        with patch.object(image_tasks, "emit_complete", complete):
            image_tasks.run_image_worker(f"t-{task}", task, params, lambda: False)
        self.assertTrue(self.events[-1][1].get("ok"), self.events[-1])
        return self.events[-1][1]

    def ocr_document(self, source_path):
        digest = _sha(source_path)
        return {"schema": 1, "source_path": str(source_path), "source_sha256": digest, "width": 420, "height": 120,
                "backend": "fixture", "status": "REVIEW_REQUIRED",
                "regions": [{"id": "r1", "box": [10, 20, 330, 70], "source_text": "NEW GAME", "ocr_text": "NEW GAME", "translation": ""}]}

    def test_inventory_ocr_review_render_delivery_install_readback_rollback(self):
        original_game_hash = _sha(self.png)
        # 1. inventory finds the image in the container
        inventory_out = self.root / "inv"
        self.run_task("image_inventory", {"src": str(self.game), "out": str(inventory_out)})
        index = json.loads((inventory_out / "image_index.json").read_text(encoding="utf-8"))
        self.assertEqual([str(self.png)], [p for p in index["image_paths"]])
        # 2. OCR (native OCR call replaced by a document for this image)
        extract_out = self.root / "ocr"
        with patch.object(image_tasks, "recognize_image", lambda src, is_cancelled=None: self.ocr_document(src)):
            self.run_task("image_extract", {"src": str(self.png), "out": str(extract_out)})
        document = json.loads((extract_out / "image_text.json").read_text(encoding="utf-8"))
        self.assertEqual(1, len(document["regions"]))
        self.assertTrue((extract_out / "source-preview.png").is_file())
        # 3. nothing is approved by OCR: render refuses an unreviewed region
        region = document["regions"][0]
        region.update(translation="GAME MỚI", background="#FFFFFF", foreground="#000000", font_size=40)
        with self.assertRaises(ValueError):
            self.run_task("image_render", {"document": document, "out": str(self.root / "bad"), "font_path": str(FONT)})
        self.events.clear()
        # 4. reviewer approves text/crop and picks exactly one background mode (what the UI checkboxes write)
        region.update(approved=True, flat_background_approved=True)
        render_out = self.root / "render"
        self.run_task("image_render", {"document": document, "out": str(render_out), "font_path": str(FONT)})
        rendered = render_out / "translated.png"
        self.assertTrue(rendered.is_file())
        self.assertNotEqual(_sha(rendered), original_game_hash)
        with Image.open(rendered) as output:
            self.assertEqual((420, 120), output.size)
        # 5. delivery package for the container, then install into a COPY and read back
        package = self.root / "delivery"
        self.run_task("image_delivery", {"document": document, "rendered": str(rendered), "game_root": str(self.game), "out": str(package)})
        copy = self.root / "game-copy"
        shutil.copytree(self.game, copy)
        transaction = self.root / "transaction"
        result = self.run_task("image_apply", {"package": str(package), "game_copy": str(copy), "out": str(transaction)})
        self.assertIn("kiểm hash đọc lại", result["summary"])
        delivery_result = json.loads((transaction / "delivery_result.json").read_text(encoding="utf-8"))
        self.assertEqual("READ_BACK_VERIFIED", delivery_result["status"])
        self.assertEqual(_sha(rendered), _sha(delivery_result["target"]))
        # the source game and the copy's original image are untouched
        self.assertEqual(original_game_hash, _sha(self.png))
        self.assertEqual(original_game_hash, _sha(copy / "game/images/ui_01.png"))
        # 6. rollback removes only this transaction's image
        self.run_task("image_rollback", {"transaction": str(transaction), "out": str(self.root / "rollback")})
        self.assertFalse(Path(delivery_result["target"]).exists())
        self.assertEqual(original_game_hash, _sha(copy / "game/images/ui_01.png"))


if __name__ == "__main__":
    unittest.main()
