"""0.1.38: the in-app model repair ("Sửa tự động" / "Cài bộ dịch") must be allowed to use the network even though the worker runs offline (found in the real UI: the download failed with HF_HUB_OFFLINE)."""
import os
import unittest
from unittest import mock

from vntext_worker import resource_tasks


class OnlineForModelDownloadTests(unittest.TestCase):
    def test_offline_switches_are_lifted_only_during_the_download_and_restored(self):
        env = {"HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1"}
        with mock.patch.dict(os.environ, env):
            with resource_tasks._online_for_model_download():
                self.assertEqual("0", os.environ["HF_HUB_OFFLINE"])
                self.assertEqual("0", os.environ["TRANSFORMERS_OFFLINE"])
            self.assertEqual("1", os.environ["HF_HUB_OFFLINE"])
            self.assertEqual("1", os.environ["TRANSFORMERS_OFFLINE"])

    def test_unset_switches_stay_unset_afterwards(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("HF_HUB_OFFLINE", None)
            os.environ.pop("TRANSFORMERS_OFFLINE", None)
            with resource_tasks._online_for_model_download():
                pass
            self.assertNotIn("HF_HUB_OFFLINE", os.environ)
            self.assertNotIn("TRANSFORMERS_OFFLINE", os.environ)

    def test_the_model_download_runs_inside_the_online_window(self):
        text = open(resource_tasks.__file__, encoding="utf-8").read()
        self.assertRegex(text.replace("\r\n", "\n"), r"with _online_for_model_download\(\):\n\s+ensure_model\(folder, download=True\)")


if __name__ == "__main__":
    unittest.main()
