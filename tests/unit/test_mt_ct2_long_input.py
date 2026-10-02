"""Tests for CT2 long-input splitting (model max 512 tokens)."""

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

import unittest
from pathlib import Path


from vntext.mt_ct2 import CT2_MAX_SRC_TOKENS, Ct2Translator, _split_text_under_token_limit


class Ct2LongInputTests(unittest.TestCase):
    def test_split_preserves_all_characters(self):
        text = ("Hello world. " * 40) + "End marker XYZ."
        max_tok = 50

        def tok_len(s: str) -> int:
            return len(s)

        parts = _split_text_under_token_limit(text, tok_len, max_tokens=max_tok)
        self.assertGreater(len(parts), 1)
        self.assertEqual("".join(parts), text)
        for p in parts:
            self.assertLessEqual(tok_len(p), max_tok)

    def test_short_text_not_split(self):
        text = "Short sentence."
        parts = _split_text_under_token_limit(text, lambda s: len(s), max_tokens=480)
        self.assertEqual(parts, [text])

    def test_default_budget_under_model_limit(self):
        self.assertLessEqual(CT2_MAX_SRC_TOKENS, 512)
        self.assertGreaterEqual(CT2_MAX_SRC_TOKENS, 64)

    def test_model_declared_target_prefix_is_added_once(self):
        inst = object.__new__(Ct2Translator)

        class PrefixTokenizer:
            target_lang = "vie"

            def get_vocab(self):
                return {">>vie<<": 3}

            def encode(self, text, add_special_tokens=True):
                return list(range(len(text or "") + (2 if add_special_tokens else 0)))

        inst._tokenizer = PrefixTokenizer()
        inst._target_prefix = Ct2Translator._resolve_target_prefix(inst)
        self.assertEqual(inst._target_prefix, ">>vie<<")
        self.assertEqual(Ct2Translator._model_input(inst, "Hello"), ">>vie<< Hello")
        self.assertEqual(Ct2Translator._model_input(inst, ">>vie<< Hello"), ">>vie<< Hello")
        self.assertGreater(
            Ct2Translator._input_token_len(inst, "Hello"),
            Ct2Translator._token_len(inst, "Hello"),
        )

    def test_translate_many_chunks_long_input(self):
        inst = object.__new__(Ct2Translator)
        inst._batch_size = 8
        inst._max_batch_size = 64
        inst._max_src_tokens = 40
        seen_lens: list[int] = []

        class FakeTok:
            def encode(self, text, add_special_tokens=True):
                n = len(text or "") + (2 if add_special_tokens else 0)
                return list(range(n))

            def __call__(self, texts, return_tensors=None, padding=True, truncation=False):
                return {"input_ids": [self.encode(t) for t in texts]}

            def convert_ids_to_tokens(self, ids):
                return [f"t{i}" for i in ids]

            def convert_tokens_to_ids(self, tokens):
                return list(range(len(tokens)))

            def decode(self, ids, skip_special_tokens=True):
                return "VI"

        class FakeCT2:
            def translate_batch(self, src_tokens, batch_type="tokens", max_batch_size=64):
                class R:
                    hypotheses = [["ok"]]

                for tokens in src_tokens:
                    seen_lens.append(len(tokens))
                return [R() for _ in src_tokens]

        inst._tokenizer = FakeTok()
        inst._translator = FakeCT2()

        long_text = "A" * 200
        outs = Ct2Translator.translate_many(inst, [long_text, "hi"])
        self.assertEqual(len(outs), 2)
        self.assertTrue(outs[0])
        self.assertIn("VI", outs[0])
        self.assertEqual(outs[1], "VI")
        self.assertTrue(seen_lens)
        self.assertTrue(all(n <= inst._max_src_tokens + 8 for n in seen_lens))


if __name__ == "__main__":
    unittest.main()
