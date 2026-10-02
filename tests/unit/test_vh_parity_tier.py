# -*- coding: utf-8 -*-

"""Unit tests for VH parity tier cache + local validate (no MT)."""

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
sys.path.insert(0, str(TESTS / "harness" / "vh_parity"))

import tempfile
import unittest
from pathlib import Path


from vh_parity_cache import (  # noqa: E402
    RULE_VERSION,
    cache_hit,
    load_cache,
    record_pass,
    save_cache,
    sha256_text,
)
from vntext.package_io import write_csv_rows_file  # noqa: E402
from vh_parity_local_validate import validate_package  # noqa: E402


class TierCacheTests(unittest.TestCase):
    def test_cache_hit_requires_rule_and_source(self):
        doc = {"rule_version": RULE_VERSION, "entries": {}}
        row = {"key": "k1", "source_text": "Hello", "translation": "Xin chào"}
        record_pass(doc, row, kind="dialogue", strategy="test")
        self.assertTrue(cache_hit(doc, row, kind="dialogue"))
        row2 = dict(row)
        row2["source_text"] = "Hello!"
        self.assertFalse(cache_hit(doc, row2, kind="dialogue"))

    def test_stale_rule_version_clears_logic(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "cache.json"
            save_cache(
                path,
                {
                    "rule_version": "old",
                    "entries": {
                        "k1": {
                            "key": "k1",
                            "source_sha": sha256_text("a"),
                            "translation_sha": sha256_text("b"),
                            "pass": True,
                            "rule_version": "old",
                        }
                    },
                },
            )
            # Force wrong version on disk then load
            path.write_text(
                '{"rule_version":"ancient","entries":{"k1":{"pass":true,"source_sha":"%s","translation_sha":"%s","rule_version":"ancient"}}}'
                % (sha256_text("a"), sha256_text("b")),
                encoding="utf-8",
            )
            doc = load_cache(path)
            self.assertEqual(doc["rule_version"], RULE_VERSION)
            self.assertEqual(doc.get("entries"), {})


class LocalValidateSmoke(unittest.TestCase):
    def test_empty_package_pending(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fields = [
                "key",
                "source_text",
                "translation",
                "context",
                "file_path",
                "object_info",
                "import_method",
                "safety",
                "backend",
                "byte_limit",
                "patch_note",
            ]
            rows = [
                {
                    "key": "c1",
                    "source_text": "Shower",
                    "translation": "",
                    "context": "NaninovelScript:1:choice",
                    "file_path": "x",
                    "object_info": "",
                    "import_method": "naninovel_choice",
                    "safety": "safe",
                    "backend": "unity",
                    "byte_limit": "",
                    "patch_note": "",
                }
            ]
            write_csv_rows_file(root / "translation.csv", fields, rows)
            (root / "manifest.json").write_text('{"entries":[]}\n', encoding="utf-8")
            report = validate_package(root)
            self.assertGreaterEqual(report["pending"], 1)
            self.assertIn("c1", report["fail_keys"])
            self.assertFalse(report["pass"])


if __name__ == "__main__":
    unittest.main()
