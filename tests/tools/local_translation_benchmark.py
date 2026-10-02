"""Private frozen-corpus tooling for local translation comparison.

This module is test-only.  It turns an explicit approval list into a
fail-closed manifest, materializes that manifest, and can run the existing
CT2/OPUS protection route without selecting rows dynamically.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
import platform
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests" / "lib"))
sys.path.insert(0, str(ROOT / "tests" / "tools"))

from vntext.mt_translation_safety import collect_spans  # noqa: E402
from vntext.mt_check import english_report, load_whitelist, structural_problems  # noqa: E402
from vntext.mt_strategies import candidate_quality_issues, translate_row_ct2  # noqa: E402
from cleanup_work_artifacts import cleanup_after_test  # noqa: E402
from work_paths import (  # noqa: E402
    WORK_ROOT,
    ambient_scope,
    assert_artifact_under_work,
    new_scope_id,
    register_artifact,
)


SCHEMA_VERSION = 1
CATEGORIES = ("normal", "contextual", "difficult")
FROZEN_V1_ROW_COUNT = 30
FROZEN_V1_COUNTS = {"normal": 10, "contextual": 10, "difficult": 10}
FROZEN_V1_IDENTITY_NAME = "identity_v1.json"
ENVIRONMENT_CACHE_NAMES = (
    "HF_HOME",
    "HF_HUB_CACHE",
    "TRANSFORMERS_CACHE",
    "TORCH_HOME",
    "VNTEXT_DIRECT_GPU_ROOT",
)


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8", "surrogatepass")).hexdigest()


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def ordered_key_source_sha256(rows: list[dict]) -> str:
    payload = "".join(
        f"{index:04d}\t{row['key']}\t{row['source']}\n"
        for index, row in enumerate(rows, 1)
    )
    return sha256_text(payload)


def _protected_inventory(source: str) -> list[dict[str, Any]]:
    return [
        {"start": start, "end": end, "text": original, "kind": kind}
        for start, end, original, kind in collect_spans(source)
    ]


def _source_rows(path: Path) -> tuple[dict, list[dict]]:
    assert_artifact_under_work(path, "frozen source corpus")
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read source corpus: {path}: {exc}") from exc
    rows = document.get("rows") if isinstance(document, dict) else None
    if not isinstance(rows, list) or not rows:
        raise ValueError("source corpus must contain a non-empty rows list")
    normalized: list[dict] = []
    seen: set[str] = set()
    for item in rows:
        if not isinstance(item, dict):
            raise ValueError("source corpus row must be an object")
        key = str(item.get("key") or "")
        source = str(item.get("source") or "")
        if not key or not source:
            raise ValueError("source corpus rows require key and source")
        if key in seen:
            raise ValueError(f"duplicate source corpus key: {key}")
        seen.add(key)
        normalized.append(dict(item))
    declared_count = document.get("row_count")
    if declared_count is not None and int(declared_count) != len(normalized):
        raise ValueError("source corpus row_count mismatch")
    declared_order = str(document.get("ordered_key_source_sha256") or "")
    actual_order = ordered_key_source_sha256(normalized)
    if declared_order and declared_order != actual_order:
        raise ValueError("source corpus ordered identity mismatch")
    return document, normalized


def _source_identity(path: Path, document: dict, rows: list[dict]) -> dict:
    file_hash = sha256_path(path)
    ordered = ordered_key_source_sha256(rows)
    identity = {
        "path": str(path.resolve()),
        "sha256": file_hash,
        "row_count": len(rows),
        "ordered_key_source_sha256": ordered,
    }
    identity["fingerprint"] = sha256_text(canonical_json(identity))
    return identity


def _corpus_rows(manifest: dict) -> list[dict]:
    return [
        {
            "ordinal": row["ordinal"],
            "key": row["key"],
            "source_text": row["source_text"],
            "source_sha256": row["source_sha256"],
            "category": row["category"],
            "rationale": row["rationale"],
            "protected_spans": row["protected_spans"],
            "source_metadata": row.get("source_metadata", {}),
            "origin": row.get("origin", "source_corpus"),
        }
        for row in manifest["rows"]
    ]


def _manifest_hash(document: dict) -> str:
    unsigned = dict(document)
    unsigned["manifest_sha256"] = ""
    return sha256_text(canonical_json(unsigned))


def _corpus_hash(document: dict) -> str:
    return sha256_text(canonical_json(_corpus_rows(document)))


def _expected_counts(value: dict[str, int] | None) -> dict[str, int]:
    if value is None:
        return dict(FROZEN_V1_COUNTS)
    actual = {str(key): int(count) for key, count in value.items()}
    if set(actual) != set(CATEGORIES) or any(count < 0 for count in actual.values()):
        raise ValueError(f"expected category counts must contain exactly {CATEGORIES}")
    if actual != FROZEN_V1_COUNTS:
        raise ValueError(
            "canonical frozen-v1 requires exactly 30 rows with normal/contextual/difficult=10/10/10"
        )
    return actual


def build_manifest(
    approval: dict,
    source_corpus_path: Path,
    *,
    expected_counts: dict[str, int] | None = None,
) -> dict:
    """Build a manifest from explicit approvals; no row selection occurs here."""
    expected = _expected_counts(expected_counts)
    source_path = source_corpus_path.expanduser().resolve()
    source_document, source_rows = _source_rows(source_path)
    by_key = {row["key"]: row for row in source_rows}
    approvals = approval.get("rows") if isinstance(approval, dict) else None
    if not isinstance(approvals, list) or not approvals:
        raise ValueError("approval document must contain a non-empty rows list")
    manifest_rows: list[dict] = []
    seen: set[str] = set()
    for ordinal, item in enumerate(approvals, 1):
        if not isinstance(item, dict):
            raise ValueError("approval row must be an object")
        key = str(item.get("key") or "")
        category = str(item.get("category") or "")
        rationale = str(item.get("rationale") or "").strip()
        if not key or key in seen:
            raise ValueError(f"missing or duplicate approved key: {key}")
        if category not in CATEGORIES:
            raise ValueError(f"unsupported category: {category}")
        if not rationale:
            raise ValueError(f"missing rationale for: {key}")
        seen.add(key)

        origin = str(item.get("origin") or "source_corpus")
        if origin == "synthetic":
            source = str(item.get("source") or "")
            metadata = {"origin": "synthetic"}
        else:
            source_row = by_key.get(key)
            if source_row is None:
                raise ValueError(f"approved key missing from source corpus: {key}")
            source = str(source_row["source"])
            metadata = {
                str(k): value
                for k, value in source_row.items()
                if k not in {"key", "source"}
            }
            origin = "source_corpus"
        if not source:
            raise ValueError(f"empty source for: {key}")
        manifest_rows.append(
            {
                "ordinal": ordinal,
                "key": key,
                "source_text": source,
                "source_sha256": sha256_text(source),
                "category": category,
                "rationale": rationale,
                "protected_spans": _protected_inventory(source),
                "source_metadata": metadata,
                "origin": origin,
            }
        )

    counts = dict(Counter(row["category"] for row in manifest_rows))
    counts = {category: int(counts.get(category, 0)) for category in CATEGORIES}
    if len(manifest_rows) != FROZEN_V1_ROW_COUNT or counts != expected:
        raise ValueError(f"approved category counts mismatch: {counts} != {expected}")
    source_identity = _source_identity(source_path, source_document, source_rows)
    document = {
        "schema_version": SCHEMA_VERSION,
        "corpus_id": str(approval.get("corpus_id") or "private-local-translation-v1"),
        "row_count": len(manifest_rows),
        "category_counts": counts,
        "ordered_key_source_sha256": ordered_key_source_sha256(
            [{"key": row["key"], "source": row["source_text"]} for row in manifest_rows]
        ),
        "source_corpus": source_identity,
        "source_corpus_fingerprint": source_identity["fingerprint"],
        "rows": manifest_rows,
        "corpus_sha256": "",
        "manifest_sha256": "",
    }
    document["corpus_sha256"] = _corpus_hash(document)
    document["manifest_sha256"] = _manifest_hash(document)
    return document


def _validate_source_identity(document: dict, source_corpus_path: Path | None) -> None:
    identity = document.get("source_corpus")
    if not isinstance(identity, dict):
        raise ValueError("manifest source_corpus identity is missing")
    path = (source_corpus_path or Path(str(identity.get("path") or ""))).expanduser().resolve()
    if not path.is_file():
        raise ValueError(f"manifest source corpus is missing: {path}")
    source_document, rows = _source_rows(path)
    actual = _source_identity(path, source_document, rows)
    for field in ("sha256", "row_count", "ordered_key_source_sha256"):
        if identity.get(field) != actual[field]:
            raise ValueError(f"source corpus {field} mismatch")
    if document.get("source_corpus_fingerprint") != actual["fingerprint"]:
        raise ValueError("source corpus fingerprint mismatch")


def validate_manifest(
    document: dict,
    *,
    source_corpus_path: Path | None = None,
    expected_counts: dict[str, int] | None = None,
) -> dict:
    if not isinstance(document, dict) or int(document.get("schema_version", -1)) != SCHEMA_VERSION:
        raise ValueError("unsupported manifest schema")
    rows = document.get("rows")
    if not isinstance(rows, list) or not rows:
        raise ValueError("manifest rows are missing")
    if int(document.get("row_count", -1)) != len(rows):
        raise ValueError("manifest row_count mismatch")
    expected = _expected_counts(expected_counts)
    if len(rows) != FROZEN_V1_ROW_COUNT:
        raise ValueError("canonical frozen-v1 requires exactly 30 rows")
    counts = Counter()
    seen: set[str] = set()
    for ordinal, row in enumerate(rows, 1):
        if not isinstance(row, dict):
            raise ValueError("manifest row must be an object")
        if int(row.get("ordinal", -1)) != ordinal:
            raise ValueError("manifest ordinal/order mismatch")
        key = str(row.get("key") or "")
        source = str(row.get("source_text") or "")
        category = str(row.get("category") or "")
        if not key or key in seen:
            raise ValueError(f"manifest key missing or duplicated: {key}")
        if not source or category not in CATEGORIES:
            raise ValueError(f"invalid manifest row: {key}")
        if not str(row.get("rationale") or "").strip():
            raise ValueError(f"manifest rationale missing: {key}")
        if row.get("source_sha256") != sha256_text(source):
            raise ValueError(f"source hash mismatch: {key}")
        expected_spans = _protected_inventory(source)
        if row.get("protected_spans") != expected_spans:
            raise ValueError(f"protected span inventory mismatch: {key}")
        seen.add(key)
        counts[category] += 1
    actual_counts = {category: int(counts.get(category, 0)) for category in CATEGORIES}
    if document.get("category_counts") != actual_counts:
        raise ValueError("manifest category counts mismatch")
    if expected is not None and actual_counts != expected:
        raise ValueError(f"manifest category counts mismatch: {actual_counts} != {expected}")
    ordered = ordered_key_source_sha256(
        [{"key": row["key"], "source": row["source_text"]} for row in rows]
    )
    if document.get("ordered_key_source_sha256") != ordered:
        raise ValueError("manifest ordered identity mismatch")
    if document.get("corpus_sha256") != _corpus_hash(document):
        raise ValueError("manifest corpus hash mismatch")
    if document.get("manifest_sha256") != _manifest_hash(document):
        raise ValueError("manifest canonical hash mismatch")
    _validate_source_identity(document, source_corpus_path)
    return document


def default_identity_path() -> Path:
    return WORK_ROOT / "local_translation_benchmark" / FROZEN_V1_IDENTITY_NAME


def identity_for_manifest(document: dict) -> dict:
    """Create a sidecar payload once; callers must not use this during runs."""
    if int(document.get("row_count", -1)) != FROZEN_V1_ROW_COUNT:
        raise ValueError("cannot seal identity for a non-canonical row count")
    if document.get("category_counts") != FROZEN_V1_COUNTS:
        raise ValueError("cannot seal identity for non-canonical category counts")
    return {
        "schema_version": SCHEMA_VERSION,
        "corpus_id": str(document.get("corpus_id") or ""),
        "row_count": FROZEN_V1_ROW_COUNT,
        "category_counts": dict(FROZEN_V1_COUNTS),
        "manifest_sha256": str(document.get("manifest_sha256") or ""),
        "corpus_sha256": str(document.get("corpus_sha256") or ""),
        "ordered_key_source_sha256": str(document.get("ordered_key_source_sha256") or ""),
    }


def validate_pinned_identity(document: dict, identity_path: Path) -> dict:
    """Compare current values with an independently retained sidecar."""
    resolved = identity_path.expanduser().resolve()
    assert_artifact_under_work(resolved, "frozen identity sidecar")
    if not resolved.is_file():
        raise FileNotFoundError(f"frozen identity sidecar is missing: {resolved}")
    try:
        identity = json.loads(resolved.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read frozen identity sidecar: {resolved}: {exc}") from exc
    if not isinstance(identity, dict) or int(identity.get("schema_version", -1)) != SCHEMA_VERSION:
        raise ValueError("unsupported frozen identity schema")
    if int(identity.get("row_count", -1)) != FROZEN_V1_ROW_COUNT:
        raise ValueError("frozen identity row_count mismatch")
    if identity.get("category_counts") != FROZEN_V1_COUNTS:
        raise ValueError("frozen identity category counts mismatch")
    if str(identity.get("corpus_id") or "") != str(document.get("corpus_id") or ""):
        raise ValueError("frozen identity corpus_id mismatch")
    for field in ("manifest_sha256", "corpus_sha256", "ordered_key_source_sha256"):
        expected = str(identity.get(field) or "")
        current = str(document.get(field) or "")
        if len(expected) != 64 or any(char not in "0123456789abcdef" for char in expected.lower()):
            raise ValueError(f"frozen identity {field} is not a SHA-256 value")
        if current != expected:
            raise ValueError(f"frozen identity {field} mismatch")
    return identity


def load_frozen_manifest(
    path: Path,
    *,
    source_corpus_path: Path | None = None,
    identity_path: Path | None = None,
) -> dict:
    """Canonical runner path: internal validation plus pinned identity."""
    document = load_manifest(path, source_corpus_path=source_corpus_path)
    validate_pinned_identity(document, identity_path or default_identity_path())
    return document


def seal_identity(
    manifest_path: Path,
    identity_path: Path | None = None,
    *,
    source_corpus_path: Path | None = None,
) -> dict:
    """One-time explicit sidecar creation; never overwrite an existing sidecar."""
    resolved = (identity_path or default_identity_path()).expanduser().resolve()
    assert_artifact_under_work(resolved, "frozen identity sidecar")
    if resolved.exists():
        raise FileExistsError(f"refusing to replace frozen identity sidecar: {resolved}")
    document = load_manifest(manifest_path, source_corpus_path=source_corpus_path)
    identity = identity_for_manifest(document)
    resolved.parent.mkdir(parents=True, exist_ok=True)
    resolved.write_text(json.dumps(identity, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _register(resolved.parent, artifact_id="local-translation-private-root", kind="benchmark_scope", purpose="retained private local-translation benchmark scope", lifecycle="RETAINED")
    _register(resolved, artifact_id="local-translation-private-identity", kind="benchmark_identity", purpose="retained independently pinned frozen-v1 identity", lifecycle="RETAINED")
    return identity


def load_manifest(
    path: Path,
    *,
    source_corpus_path: Path | None = None,
    expected_counts: dict[str, int] | None = None,
    identity_path: Path | None = None,
) -> dict:
    resolved = path.expanduser().resolve()
    assert_artifact_under_work(resolved, "private translation manifest")
    try:
        document = json.loads(resolved.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read manifest: {resolved}: {exc}") from exc
    document = validate_manifest(
        document,
        source_corpus_path=source_corpus_path,
        expected_counts=expected_counts,
    )
    if identity_path is not None:
        validate_pinned_identity(document, identity_path)
    return document


def materialize_manifest(
    manifest_path: Path,
    output_path: Path,
    *,
    source_corpus_path: Path | None = None,
    expected_counts: dict[str, int] | None = None,
    identity_path: Path | None = None,
    force: bool = False,
) -> dict:
    output = output_path.expanduser().resolve()
    assert_artifact_under_work(output, "materialized private corpus")
    if output.exists() and not force:
        raise FileExistsError(f"refusing to replace materialized corpus: {output}")
    _expected_counts(expected_counts)
    manifest = load_frozen_manifest(
        manifest_path,
        source_corpus_path=source_corpus_path,
        identity_path=identity_path,
    )
    rows = [
        {
            "ordinal": row["ordinal"],
            "key": row["key"],
            "source": row["source_text"],
            "source_sha256": row["source_sha256"],
            "category": row["category"],
            "rationale": row["rationale"],
            "protected_spans": row["protected_spans"],
            "source_metadata": row.get("source_metadata", {}),
            "origin": row.get("origin", "source_corpus"),
        }
        for row in manifest["rows"]
    ]
    output_document = {
        "schema_version": SCHEMA_VERSION,
        "manifest_sha256": manifest["manifest_sha256"],
        "corpus_sha256": manifest["corpus_sha256"],
        "row_count": len(rows),
        "category_counts": manifest["category_counts"],
        "ordered_key_source_sha256": manifest["ordered_key_source_sha256"],
        "rows": rows,
        "materialized_sha256": "",
    }
    unsigned = dict(output_document)
    unsigned["materialized_sha256"] = ""
    output_document["materialized_sha256"] = sha256_text(canonical_json(unsigned))
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(output_document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return output_document


def _source_sha() -> str:
    try:
        return subprocess.check_output(
            ["git", "-C", str(ROOT), "rev-parse", "HEAD"],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except (OSError, subprocess.SubprocessError):
        return "unavailable"


def _version(name: str) -> str:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return "unavailable"


def _file_identity(path: Path) -> dict:
    return {"path": str(path), "bytes": path.stat().st_size, "sha256": sha256_path(path)}


class _CapturingTranslator:
    def __init__(self, translator) -> None:
        self._translator = translator
        self.calls: list[dict[str, str]] = []

    def translate(self, text: str) -> str:
        value = self._translator.translate(text)
        self.calls.append({"protected_input": text, "raw_output": str(value or "")})
        return value


def _register(path: Path, *, artifact_id: str, kind: str, purpose: str, lifecycle: str) -> None:
    ambient = ambient_scope()
    register_artifact(
        artifact_id=artifact_id,
        path=path,
        kind=kind,
        created_by="local_translation_benchmark.py",
        owner="local_translation_benchmark.py",
        purpose=purpose,
        lifecycle=lifecycle,
        scope_id=ambient["scope_id"],
        run_id=ambient["run_id"],
        scope_root=ambient["scope_root"],
    )


def run_opus_baseline(
    manifest_path: Path,
    report_path: Path,
    model_dir: Path,
    *,
    source_corpus_path: Path | None = None,
    expected_counts: dict[str, int] | None = None,
    identity_path: Path | None = None,
) -> dict:
    """Run the existing protection + CT2 route on one explicit manifest."""
    from vntext.mt_ct2_model import Ct2Translator

    model = model_dir.expanduser().resolve()
    report_file = report_path.expanduser().resolve()
    assert_artifact_under_work(model, "local baseline model")
    assert_artifact_under_work(report_file, "local baseline report")
    _expected_counts(expected_counts)
    resolved_identity = (identity_path or default_identity_path()).expanduser().resolve()
    manifest = load_frozen_manifest(
        manifest_path,
        source_corpus_path=source_corpus_path,
        identity_path=resolved_identity,
    )
    if not (model / "model.bin").is_file():
        raise FileNotFoundError(f"CT2 model.bin missing: {model}")

    run_id = new_scope_id("local-opus-baseline")
    runtime_root = report_file.parent / "runtime" / run_id
    cache_root = runtime_root / "cache"
    _register(runtime_root, artifact_id=f"local-baseline-runtime:{run_id}", kind="benchmark_runtime", purpose="disposable local baseline runtime scope", lifecycle="DISPOSABLE")
    _register(cache_root, artifact_id=f"local-baseline-cache:{run_id}", kind="benchmark_cache", purpose="disposable local baseline cache scope", lifecycle="DISPOSABLE")
    old_env = {name: os.environ.get(name) for name in ENVIRONMENT_CACHE_NAMES}
    for name in ENVIRONMENT_CACHE_NAMES:
        os.environ[name] = str(cache_root / name)

    started = time.perf_counter()
    report: dict[str, Any] = {
        "schema_version": 1,
        "source_sha": _source_sha(),
        "frozen_identity_path": str(resolved_identity),
        "manifest_sha256": manifest["manifest_sha256"],
        "corpus_sha256": manifest["corpus_sha256"],
        "ordered_key_source_sha256": manifest["ordered_key_source_sha256"],
        "source_corpus": manifest["source_corpus"],
        "row_count": manifest["row_count"],
        "category_counts": manifest["category_counts"],
        "pipeline": "vntext.mt_strategies.translate_row_ct2 -> CT2/OPUS -> restore -> structural validation",
        "semantic_review_verdict": "NOT_REVIEWED",
        "semantic_review_reason": "Baseline evidence is handed to bilingual human review; no automatic semantic verdict.",
        "model": {
            "engine": "CT2",
            "family": "OPUS",
            "model_dir": str(model),
            "files": [
                _file_identity(path)
                for path in sorted(model.iterdir())
                if path.is_file() and path.name in {"model.bin", "config.json", "tokenizer_config.json", "shared_vocabulary.json"}
            ],
            "runtime": {
                "python": platform.python_version(),
                "ctranslate2": _version("ctranslate2"),
                "transformers": _version("transformers"),
            },
        },
        "rows": [],
    }
    translator = None
    try:
        translator = _CapturingTranslator(Ct2Translator(model))
        whitelist = load_whitelist()
        for row in manifest["rows"]:
            start = len(translator.calls)
            restored = translate_row_ct2(
                {
                    "key": row["key"],
                    "source_text": row["source_text"],
                    "file_path": str(row.get("source_metadata", {}).get("file_path") or ""),
                    "context": str(row.get("source_metadata", {}).get("scene") or ""),
                },
                translator,
            )
            calls = translator.calls[start:]
            structural = structural_problems(
                {"key": row["key"], "source_text": row["source_text"]},
                restored,
            )
            quality = candidate_quality_issues(
                {"key": row["key"], "source_text": row["source_text"]},
                restored,
                whitelist,
            )
            english_score, english_reasons = english_report(
                row["source_text"], restored, whitelist
            )
            report["rows"].append(
                {
                    "key": row["key"],
                    "category": row["category"],
                    "source": row["source_text"],
                    "protected_input": [call["protected_input"] for call in calls],
                    "raw_model_output": [call["raw_output"] for call in calls],
                    "restored_output": restored,
                    "automated_structural_verdict": "PASS" if not structural else "FAIL",
                    "automated_structural_reasons": structural,
                    "automated_quality_verdict": "PASS" if not quality else "REVIEW_REQUIRED",
                    "automated_quality_reasons": quality,
                    "residual_english": {
                        "score": english_score,
                        "verdict": "PASS" if not english_reasons else "REVIEW_REQUIRED",
                        "reasons": english_reasons,
                    },
                    "semantic_review_verdict": "NOT_REVIEWED",
                }
            )
        report["elapsed_seconds"] = round(time.perf_counter() - started, 4)
        report["benchmark_status"] = "BASELINE_COMPLETE"
    except Exception as exc:
        report["elapsed_seconds"] = round(time.perf_counter() - started, 4)
        report["benchmark_status"] = "BASELINE_FAILED"
        report["error"] = f"{type(exc).__name__}: {exc}"
        raise
    finally:
        for name, value in old_env.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value
        report_file.parent.mkdir(parents=True, exist_ok=True)
        _register(report_file, artifact_id=f"local-baseline-report:{report_file.name}", kind="benchmark_report", purpose="retained local translation baseline evidence", lifecycle="RETAINED")
        report_file.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        report["cleanup"] = cleanup_after_test(
            [runtime_root],
            reason="local translation baseline runtime payload",
            outcome="PASS" if report.get("benchmark_status") == "BASELINE_COMPLETE" else "FAIL",
            scope_id=ambient_scope()["scope_id"],
            run_id=ambient_scope()["run_id"],
        )
        report_file.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def _parse_counts(raw: str) -> dict[str, int] | None:
    if not raw.strip():
        return None
    values = {}
    for item in raw.split(","):
        name, sep, count = item.partition("=")
        if not sep:
            raise ValueError(f"invalid category count: {item}")
        values[name.strip()] = int(count)
    return values


def _write_manifest(args: argparse.Namespace) -> int:
    manifest_path = args.manifest.expanduser().resolve()
    assert_artifact_under_work(manifest_path, "private translation manifest")
    approval_path = args.approval.expanduser().resolve()
    assert_artifact_under_work(approval_path, "private approval specification")
    approval = json.loads(approval_path.read_text(encoding="utf-8"))
    document = build_manifest(
        approval,
        args.source_corpus.expanduser().resolve(),
        expected_counts=_parse_counts(args.expected_counts),
    )
    identity_path = args.identity.expanduser().resolve() if args.identity else default_identity_path()
    if identity_path.is_file():
        validate_pinned_identity(document, identity_path)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _register(manifest_path.parent, artifact_id="local-translation-private-root", kind="benchmark_scope", purpose="retained private local-translation benchmark scope", lifecycle="RETAINED")
    _register(approval_path, artifact_id="local-translation-private-approval", kind="benchmark_approval", purpose="retained private explicit approval specification", lifecycle="RETAINED")
    _register(manifest_path, artifact_id="local-translation-private-manifest", kind="benchmark_manifest", purpose="retained explicit private translation manifest", lifecycle="RETAINED")
    print(json.dumps({"manifest": str(manifest_path), "manifest_sha256": document["manifest_sha256"], "corpus_sha256": document["corpus_sha256"]}, ensure_ascii=False))
    return 0


def _materialize(args: argparse.Namespace) -> int:
    identity_path = args.identity.expanduser().resolve() if args.identity else default_identity_path()
    document = materialize_manifest(
        args.manifest.expanduser().resolve(),
        args.output.expanduser().resolve(),
        source_corpus_path=args.source_corpus.expanduser().resolve() if args.source_corpus else None,
        expected_counts=_parse_counts(args.expected_counts),
        identity_path=identity_path,
    )
    _register(args.output.expanduser().resolve().parent, artifact_id="local-translation-private-root", kind="benchmark_scope", purpose="retained private local-translation benchmark scope", lifecycle="RETAINED")
    _register(args.output.expanduser().resolve(), artifact_id="local-translation-materialized-corpus", kind="benchmark_corpus", purpose="retained materialized private translation corpus", lifecycle="RETAINED")
    print(json.dumps({"output": str(args.output.expanduser().resolve()), "row_count": document["row_count"], "materialized_sha256": document["materialized_sha256"]}, ensure_ascii=False))
    return 0


def _baseline(args: argparse.Namespace) -> int:
    identity_path = args.identity.expanduser().resolve() if args.identity else default_identity_path()
    report = run_opus_baseline(
        args.manifest.expanduser().resolve(),
        args.report.expanduser().resolve(),
        args.model_dir.expanduser().resolve(),
        source_corpus_path=args.source_corpus.expanduser().resolve() if args.source_corpus else None,
        expected_counts=_parse_counts(args.expected_counts),
        identity_path=identity_path,
    )
    print(json.dumps({"report": str(args.report.expanduser().resolve()), "benchmark_status": report["benchmark_status"]}, ensure_ascii=False))
    return 0


def _seal(args: argparse.Namespace) -> int:
    identity_path = args.identity.expanduser().resolve() if args.identity else default_identity_path()
    identity = seal_identity(
        args.manifest.expanduser().resolve(),
        identity_path,
        source_corpus_path=args.source_corpus.expanduser().resolve() if args.source_corpus else None,
    )
    print(json.dumps({"identity": str(identity_path), **identity}, ensure_ascii=False))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Private frozen local-translation benchmark tooling")
    sub = parser.add_subparsers(dest="command", required=True)

    create = sub.add_parser("create-manifest")
    create.add_argument("--approval", type=Path, required=True)
    create.add_argument("--source-corpus", type=Path, required=True)
    create.add_argument("--manifest", type=Path, required=True)
    create.add_argument("--expected-counts", default="")
    create.add_argument("--identity", type=Path, default=None)
    create.set_defaults(handler=_write_manifest)

    materialize = sub.add_parser("materialize")
    materialize.add_argument("--manifest", type=Path, required=True)
    materialize.add_argument("--source-corpus", type=Path, default=None)
    materialize.add_argument("--output", type=Path, required=True)
    materialize.add_argument("--expected-counts", default="")
    materialize.add_argument("--identity", type=Path, default=None)
    materialize.set_defaults(handler=_materialize)

    baseline = sub.add_parser("opus-baseline")
    baseline.add_argument("--manifest", type=Path, required=True)
    baseline.add_argument("--source-corpus", type=Path, default=None)
    baseline.add_argument("--report", type=Path, required=True)
    baseline.add_argument("--model-dir", type=Path, required=True)
    baseline.add_argument("--expected-counts", default="")
    baseline.add_argument("--identity", type=Path, default=None)
    baseline.set_defaults(handler=_baseline)

    seal = sub.add_parser("seal-identity")
    seal.add_argument("--manifest", type=Path, required=True)
    seal.add_argument("--source-corpus", type=Path, default=None)
    seal.add_argument("--identity", type=Path, default=None)
    seal.set_defaults(handler=_seal)
    args = parser.parse_args(argv)
    return int(args.handler(args))


if __name__ == "__main__":
    raise SystemExit(main())
