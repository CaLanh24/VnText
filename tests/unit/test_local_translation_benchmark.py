from __future__ import annotations

import copy
import importlib.util
import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "local_translation_benchmark",
    ROOT / "tests" / "tools" / "local_translation_benchmark.py",
)
assert SPEC and SPEC.loader
BENCHMARK = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = BENCHMARK
SPEC.loader.exec_module(BENCHMARK)

TESTS = ROOT / "tests"
sys.path.insert(0, str(TESTS / "lib"))
from work_paths import work_temp_dir  # noqa: E402


class LocalTranslationBenchmarkTests(unittest.TestCase):
    def setUp(self) -> None:
        self.root = work_temp_dir("local_translation_benchmark_unit")
        self.source_path = self.root / "source.json"
        self.manifest_path = self.root / "manifest.json"
        self.identity_path = self.root / "identity.json"
        self.materialized_path = self.root / "materialized.json"
        rows = []
        approvals = []
        for index in range(30):
            category = BENCHMARK.CATEGORIES[index // 10]
            source = f"Line {index + 1} is ready."
            if index == 29:
                source = r"Tell {NAME} to use <color=#fff>[br]\n♡</color>."
            rows.append({"key": f"row:{index + 1:02d}", "source": source, "file_path": f"scene_{index // 5}.txt", "line": index + 1})
            approvals.append({"key": f"row:{index + 1:02d}", "category": category, "rationale": f"approved {category} fixture"})
        source_document = {
            "schema_version": 1,
            "row_count": len(rows),
            "ordered_key_source_sha256": BENCHMARK.ordered_key_source_sha256(rows),
            "rows": rows,
        }
        self.source_path.write_text(json.dumps(source_document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        self.approval = {"corpus_id": "synthetic-local-v1", "rows": approvals}
        self.manifest = BENCHMARK.build_manifest(
            self.approval,
            self.source_path,
            expected_counts={"normal": 10, "contextual": 10, "difficult": 10},
        )
        self.manifest_path.write_text(json.dumps(self.manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        self.identity = BENCHMARK.identity_for_manifest(self.manifest)
        self.identity_path.write_text(json.dumps(self.identity, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def _write_variant(self, name: str, document: dict) -> Path:
        path = self.root / f"{name}.json"
        path.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return path

    @staticmethod
    def _reseal(document: dict) -> None:
        document["corpus_sha256"] = BENCHMARK._corpus_hash(document)
        document["manifest_sha256"] = BENCHMARK._manifest_hash(document)

    def test_manifest_and_materialization_are_deterministic(self):
        loaded = BENCHMARK.load_frozen_manifest(
            self.manifest_path,
            source_corpus_path=self.source_path,
            identity_path=self.identity_path,
        )
        self.assertEqual(loaded["row_count"], 30)
        self.assertEqual(loaded["category_counts"], {"normal": 10, "contextual": 10, "difficult": 10})
        materialized = BENCHMARK.materialize_manifest(
            self.manifest_path,
            self.materialized_path,
            source_corpus_path=self.source_path,
            identity_path=self.identity_path,
        )
        self.assertEqual(materialized["row_count"], 30)
        self.assertEqual(materialized["ordered_key_source_sha256"], loaded["ordered_key_source_sha256"])
        self.assertEqual([row["key"] for row in materialized["rows"]], [row["key"] for row in loaded["rows"]])

    def test_frozen_count_contract_is_default_without_expected_counts(self):
        bad_approval = copy.deepcopy(self.approval)
        bad_approval["rows"].pop()
        with self.assertRaises(ValueError):
            BENCHMARK.build_manifest(bad_approval, self.source_path)

        bad_manifest = copy.deepcopy(self.manifest)
        bad_manifest["rows"].pop()
        bad_manifest["row_count"] = 29
        path = self._write_variant("bad_count_default", bad_manifest)
        with self.assertRaises(ValueError):
            BENCHMARK.load_manifest(path, source_corpus_path=self.source_path)

    def test_identity_seal_refuses_rewrite(self):
        with self.assertRaises(FileExistsError):
            BENCHMARK.seal_identity(
                self.manifest_path,
                self.identity_path,
                source_corpus_path=self.source_path,
            )

    def test_protected_inventory_covers_placeholder_tag_newline_and_heart(self):
        row = self.manifest["rows"][-1]
        inventory = row["protected_spans"]
        protected = {item["text"] for item in inventory}
        self.assertTrue({"{NAME}", "<color=#fff>", "[br]", r"\n", "♡"}.issubset(protected))

    def test_explicit_approval_rejects_missing_or_duplicate_keys(self):
        missing = copy.deepcopy(self.approval)
        missing["rows"][0]["key"] = "row:missing"
        with self.assertRaises(ValueError):
            BENCHMARK.build_manifest(missing, self.source_path)

        duplicate = copy.deepcopy(self.approval)
        duplicate["rows"][1]["key"] = duplicate["rows"][0]["key"]
        with self.assertRaises(ValueError):
            BENCHMARK.build_manifest(duplicate, self.source_path)

    def test_resealed_category_order_and_source_drift_still_fail_external_identity(self):
        category_drift = copy.deepcopy(self.manifest)
        category_drift["rows"][0]["category"], category_drift["rows"][10]["category"] = (
            category_drift["rows"][10]["category"],
            category_drift["rows"][0]["category"],
        )
        self._reseal(category_drift)
        category_path = self._write_variant("category_drift", category_drift)
        BENCHMARK.load_manifest(category_path, source_corpus_path=self.source_path)
        with self.assertRaises(ValueError):
            BENCHMARK.load_frozen_manifest(
                category_path,
                source_corpus_path=self.source_path,
                identity_path=self.identity_path,
            )

        order_drift = copy.deepcopy(self.manifest)
        order_drift["rows"][0], order_drift["rows"][1] = order_drift["rows"][1], order_drift["rows"][0]
        for ordinal, row in enumerate(order_drift["rows"], 1):
            row["ordinal"] = ordinal
        order_drift["ordered_key_source_sha256"] = BENCHMARK.ordered_key_source_sha256(
            [{"key": row["key"], "source": row["source_text"]} for row in order_drift["rows"]]
        )
        self._reseal(order_drift)
        order_path = self._write_variant("order_drift", order_drift)
        BENCHMARK.load_manifest(order_path, source_corpus_path=self.source_path)
        with self.assertRaises(ValueError):
            BENCHMARK.load_frozen_manifest(
                order_path,
                source_corpus_path=self.source_path,
                identity_path=self.identity_path,
            )

        source_drift = copy.deepcopy(self.manifest)
        source_drift["rows"][0]["source_text"] = "Changed source text."
        source_drift["rows"][0]["source_sha256"] = BENCHMARK.sha256_text(source_drift["rows"][0]["source_text"])
        source_drift["rows"][0]["protected_spans"] = BENCHMARK._protected_inventory(
            source_drift["rows"][0]["source_text"]
        )
        source_drift["ordered_key_source_sha256"] = BENCHMARK.ordered_key_source_sha256(
            [{"key": row["key"], "source": row["source_text"]} for row in source_drift["rows"]]
        )
        self._reseal(source_drift)
        source_path = self._write_variant("source_drift", source_drift)
        BENCHMARK.load_manifest(source_path, source_corpus_path=self.source_path)
        with self.assertRaises(ValueError):
            BENCHMARK.load_frozen_manifest(
                source_path,
                source_corpus_path=self.source_path,
                identity_path=self.identity_path,
            )

    def test_manifest_mutations_fail_closed(self):
        variants = {}

        missing = copy.deepcopy(self.manifest)
        missing["rows"].pop()
        missing["row_count"] = 29
        variants["missing"] = missing

        duplicate = copy.deepcopy(self.manifest)
        duplicate["rows"].append(copy.deepcopy(duplicate["rows"][0]))
        duplicate["row_count"] = 31
        variants["duplicate"] = duplicate

        reordered = copy.deepcopy(self.manifest)
        reordered["rows"][0], reordered["rows"][1] = reordered["rows"][1], reordered["rows"][0]
        reordered["ordered_key_source_sha256"] = BENCHMARK.ordered_key_source_sha256(
            [{"key": row["key"], "source": row["source_text"]} for row in reordered["rows"]]
        )
        self._reseal(reordered)
        variants["order"] = reordered

        bad_category = copy.deepcopy(self.manifest)
        bad_category["rows"][0]["category"] = "unknown"
        self._reseal(bad_category)
        variants["category"] = bad_category

        bad_source_hash = copy.deepcopy(self.manifest)
        bad_source_hash["rows"][0]["source_sha256"] = "0" * 64
        self._reseal(bad_source_hash)
        variants["source_hash"] = bad_source_hash

        bad_spans = copy.deepcopy(self.manifest)
        bad_spans["rows"][-1]["protected_spans"] = []
        self._reseal(bad_spans)
        variants["protected_spans"] = bad_spans

        bad_count = copy.deepcopy(self.manifest)
        bad_count["category_counts"]["normal"] = 9
        self._reseal(bad_count)
        variants["count"] = bad_count

        bad_fingerprint = copy.deepcopy(self.manifest)
        bad_fingerprint["source_corpus_fingerprint"] = "0" * 64
        self._reseal(bad_fingerprint)
        variants["source_fingerprint"] = bad_fingerprint

        bad_canonical_hash = copy.deepcopy(self.manifest)
        bad_canonical_hash["manifest_sha256"] = "0" * 64
        variants["canonical_hash"] = bad_canonical_hash

        for name, variant in variants.items():
            with self.subTest(name=name):
                path = self._write_variant(name, variant)
                with self.assertRaises(ValueError):
                    BENCHMARK.load_manifest(path, source_corpus_path=self.source_path)

    def test_source_corpus_file_drift_is_rejected(self):
        changed = json.loads(self.source_path.read_text(encoding="utf-8"))
        changed["rows"][0]["source"] = "Changed source"
        self.source_path.write_text(json.dumps(changed, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        with self.assertRaises(ValueError):
            BENCHMARK.load_manifest(self.manifest_path, source_corpus_path=self.source_path)


if __name__ == "__main__":
    unittest.main()
