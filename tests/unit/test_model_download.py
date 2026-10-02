from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from vntext.mt_ct2_constants import MODEL_REPO, MODEL_REVISION
from vntext.mt_ct2_model import ensure_model


class ModelDownloadTests(unittest.TestCase):
    def test_download_pins_the_opus_snapshot_revision(self):
        with tempfile.TemporaryDirectory(prefix="vntext-model-download-") as temp:
            target = Path(temp)

            def download_snapshot(*, repo_id: str, revision: str, local_dir: str) -> None:
                self.assertEqual(MODEL_REPO, repo_id)
                self.assertEqual(MODEL_REVISION, revision)
                (Path(local_dir) / "model.bin").write_bytes(b"test model")

            with patch("huggingface_hub.snapshot_download", side_effect=download_snapshot) as download:
                self.assertEqual(target, ensure_model(target))

            download.assert_called_once_with(
                repo_id=MODEL_REPO,
                revision=MODEL_REVISION,
                local_dir=str(target),
            )


if __name__ == "__main__":
    unittest.main()
