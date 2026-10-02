from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from vntext.mt_model_adapter import Ct2ModelAdapter
from vntext.mt_ct2_pipeline import _translation_cache_context, run_ct2_translate_keys
from vntext.translation_cache import (
    TranslationCache,
    TranslationCacheError,
    compute_cache_fingerprint,
)


class TranslationCacheTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="vntext-cache-")
        self.root = Path(self.temp.name)
        self.row = {
            "key": "k1",
            "source_text": "Hello world",
            "context": "NaninovelScript:Main:1",
            "import_method": "naninovel_script_string",
        }
        self.model = {
            "adapter_id": "ct2",
            "model_id": "opus-mt-en-vi-ct2-int8",
            "model_revision": "model-r1",
        }

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _fingerprint(self, row=None, **overrides):
        args = {
            "model_metadata": self.model,
            "glossary": {"Hello": "Xin chào"},
            "memory_scope": "memory-r1",
            "classifier_policy_version": "policy-1",
            "classifier_policy_hash": "policy-hash",
            "strategy_version": "strategy-1",
            "protected_span_schema_version": "1",
            "context_builder_version": "none",
            "engine_profile": "naninovel",
        }
        args.update(overrides)
        return compute_cache_fingerprint(row or self.row, **args)

    def test_fingerprint_changes_only_when_translation_inputs_change(self):
        base = self._fingerprint()
        self.assertEqual(base["cache_key"], self._fingerprint()["cache_key"])
        self.assertNotEqual(
            base["cache_key"], self._fingerprint(context_builder_version="bounded-v2")["cache_key"]
        )
        self.assertNotEqual(
            base["cache_key"], self._fingerprint(model_metadata={**self.model, "model_revision": "model-r2"})["cache_key"]
        )
        self.assertNotEqual(
            base["cache_key"],
            self._fingerprint(row={**self.row, "context": "NaninovelScript:Other:1"})["cache_key"],
        )
        self.assertNotEqual(
            base["cache_key"],
            self._fingerprint(decoding={"profile": "ct2-translate-batch-defaults-v2"})["cache_key"],
        )

    def test_cache_stores_pass_only_and_reopens_with_provenance(self):
        cache = TranslationCache(self.root)
        fp = self._fingerprint()
        try:
            self.assertFalse(cache.put(fp["cache_key"], self.row, "", validation_status="FAIL"))
            self.assertIsNone(cache.lookup(fp["cache_key"]))
            self.assertTrue(
                cache.put(
                    fp["cache_key"],
                    self.row,
                    "Xin chào",
                    validation_status="PASS",
                    provenance={"validator": "safe_candidate", "fingerprint": fp["fingerprint"]},
                )
            )
            self.assertEqual(cache.lookup(fp["cache_key"]), "Xin chào")
            self.assertEqual(cache.summary()["hits"], 1)
        finally:
            cache.close()

        reopened = TranslationCache(self.root)
        try:
            self.assertEqual(reopened.lookup(fp["cache_key"]), "Xin chào")
            provenance = json.loads(
                reopened.connection.execute(
                    "SELECT provenance_json FROM cache_entries WHERE cache_key = ?",
                    (fp["cache_key"],),
                ).fetchone()[0]
            )
            self.assertEqual(provenance["validator"], "safe_candidate")
        finally:
            reopened.close()

    def test_cache_has_single_writer_lock(self):
        first = TranslationCache(self.root)
        try:
            with self.assertRaises(TranslationCacheError):
                TranslationCache(self.root)
        finally:
            first.close()

    def test_ct2_adapter_exposes_only_model_surface_and_provenance(self):
        delegate = MagicMock()
        delegate.config = {"batch_size": 8}
        delegate.translate.return_value = "Xin chào"
        delegate.translate_many.return_value = ["Xin chào"]
        adapter = Ct2ModelAdapter(delegate, self.root / "model")
        self.assertEqual(adapter.config["batch_size"], 8)
        self.assertEqual(adapter.translate("Hello"), "Xin chào")
        self.assertEqual(adapter.translate_many(["Hello"]), ["Xin chào"])
        self.assertEqual(adapter.metadata()["adapter_id"], "ct2")
        self.assertEqual(adapter.metadata()["model_id"], "opus-mt-en-vi-ct2-int8")
        self.assertEqual(
            adapter.metadata()["decoding"]["profile"],
            "ct2-translate-batch-defaults-v1",
        )
        context = _translation_cache_context(
            self.root,
            adapter,
            {},
            {},
            allow_overwrite=False,
        )
        self.assertEqual(
            context["decoding"]["profile"],
            "ct2-translate-batch-defaults-v1",
        )

    def test_ct2_trace_uses_concrete_resolved_model_revision(self):
        from vntext.app_tasks import _ct2_trace_model_revision

        resolved = self.root / "models" / "opus-mt"
        with patch("vntext.mt_ct2_model.resolve_model_dir", return_value=resolved):
            self.assertEqual(_ct2_trace_model_revision(""), str(resolved.resolve()))

    def test_retranslate_hits_validated_cache_without_model_batch(self):
        csv_path = self.root / "translation.csv"
        csv_path.write_text(
            "key,source_text,translation,context,file_path,import_method\n"
            "k1,Hello world,,NaninovelScript:Main:1,game/sample.txt,naninovel_script_string\n",
            encoding="utf-8",
        )
        delegate = MagicMock()
        delegate.config = {"batch_size": 8, "inter_threads": 1, "flush_every": 8}

        with patch("vntext.mt_ct2_model.get_translator", return_value=delegate), patch(
            "vntext.mt_ct2_io._batch_translate_chunk", return_value={"k1": "Xin chào"}
        ) as batch:
            first = run_ct2_translate_keys(csv_path, ["k1"], backup=False)
            self.assertTrue(first["ok"])
            self.assertEqual(batch.call_count, 1)
            self.assertTrue(first["cache_fingerprints"]["k1"])

        csv_path.write_text(
            "key,source_text,translation,context,file_path,import_method\n"
            "k1,Hello world,,NaninovelScript:Main:1,game/sample.txt,naninovel_script_string\n",
            encoding="utf-8",
        )
        with patch("vntext.mt_ct2_model.get_translator", return_value=delegate), patch(
            "vntext.mt_ct2_io._batch_translate_chunk",
            side_effect=AssertionError("validated cache miss"),
        ):
            second = run_ct2_translate_keys(csv_path, ["k1"], backup=False)
        self.assertTrue(second["ok"])
        self.assertEqual(second["cache"]["hits"], 1)
        self.assertEqual(second["cache"]["misses"], 0)
        self.assertEqual(second["cache_fingerprints"]["k1"], first["cache_fingerprints"]["k1"])


if __name__ == "__main__":
    unittest.main()
