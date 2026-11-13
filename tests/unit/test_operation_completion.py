"""Operation ownership across the worker boundary, independent of model inference."""
import unittest
from unittest.mock import patch

from vntext_worker.task_runners import _make_callbacks, run_translate_worker


class OperationCompletionTests(unittest.TestCase):
    def test_checked_row_completion_keeps_package_counts_on_wire(self):
        with patch("vntext_worker.protocol.emit") as emit:
            complete = _make_callbacks("selected", lambda: False)[2]
            complete(dict(ok=True, complete=True, summary="saved", operation_scope="selected_rows",
                          selected_total=2, selected_done=2, package_counts=dict(pending=4),
                          image_summary="images pending", image_pending=1))
        payload = emit.call_args.args[0]
        self.assertEqual(2, payload["selected_done"])
        self.assertEqual(4, payload["package_counts"]["pending"])
        self.assertEqual(1, payload["image_pending"])

    def test_image_failure_does_not_turn_finished_text_into_failed_text(self):
        text = dict(ok=True, complete=True, summary="text saved", translated=3, pending=0, review_only=0, blocked=0)
        with patch("vntext_worker.task_runners.run_translate_ct2_task", side_effect=lambda *a, **kw: kw["complete"](text)), \
             patch("vntext.package_io.read_csv_rows_file", return_value=([], [{"key": "text"}])), \
             patch("vntext.image_batch.cached_image_report", return_value={}), \
             patch("vntext.image_batch.translate_cached_images", side_effect=ValueError("image error")), \
             patch("vntext_worker.protocol.emit") as emit:
            run_translate_worker("text", dict(csv_path="C:/v/TEST_RUN/fixture/translation.csv"), lambda: False)
        payload = next(call.args[0] for call in emit.call_args_list if call.args[0]["type"] == "complete")
        self.assertTrue(payload["ok"])
        self.assertTrue(payload["complete"])
        self.assertEqual("text saved", payload["summary"])
        self.assertIn("image error", payload["image_summary"])
        self.assertEqual(1, payload["image_pending"])
