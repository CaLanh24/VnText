"""Run an external Phase C corpus through the production worker route."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests" / "lib"))
sys.path.insert(0, str(ROOT / "tests" / "tools"))

from cleanup_work_artifacts import cleanup_after_test  # noqa: E402
from worker_test_lib import (  # noqa: E402
    complete_for,
    read_ready,
    run_task,
    start_worker,
    stop_worker,
)
from work_paths import WORK_ROOT, new_scope_id, register_artifact  # noqa: E402
from vntext.entry import Entry  # noqa: E402
from vntext.mt_check import english_report, load_whitelist, structural_problems  # noqa: E402
from vntext.mt_strategies import candidate_quality_issues  # noqa: E402
from vntext.package_io import read_csv_rows_file, write_package  # noqa: E402


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _source_sha() -> str:
    return subprocess.check_output(
        ["git", "-C", str(ROOT), "rev-parse", "HEAD"], text=True, stderr=subprocess.DEVNULL
    ).strip()


def _load_corpus(path: Path) -> list[str]:
    document = json.loads(path.read_text(encoding="utf-8"))
    rows = document.get("rows") if isinstance(document, dict) else None
    if not isinstance(rows, list) or not rows:
        raise ValueError("benchmark input must be a JSON object with non-empty rows")
    sources = [str(item.get("source") or "") for item in rows if isinstance(item, dict)]
    if len(sources) != len(rows) or any(not value for value in sources):
        raise ValueError("each benchmark row requires a non-empty source")
    return sources


def _parse_indices(raw: str, count: int) -> list[int]:
    if not raw.strip():
        return list(range(1, count + 1))
    indices = [int(value.strip()) for value in raw.split(",") if value.strip()]
    if not indices or len(set(indices)) != len(indices) or any(index < 1 or index > count for index in indices):
        raise ValueError(f"row indices must be unique 1-based values within 1..{count}")
    return indices


def _corpus_identity(path: Path, entries: list[Entry]) -> dict:
    ordered = "".join(f"{index:04d}\t{entry.key}\t{entry.source_text}\n" for index, entry in enumerate(entries, 1))
    return {
        "canonical_input_path": str(path),
        "input_sha256": _sha256(path),
        "row_count": len(entries),
        "ordered_key_source_sha256": hashlib.sha256(ordered.encode("utf-8", "surrogatepass")).hexdigest(),
    }


def _entry(index: int, source: str) -> Entry:
    return Entry(
        source_text=source,
        file_path="phase_c_external_benchmark.txt",
        context=f"phase-c-benchmark:{index:03d}",
        import_method="plain_text_line",
        safety="safe",
        locator={"line": index},
        backend="external_benchmark",
    ).finalize()


def _read_json(path: Path, fallback):
    try:
        return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else fallback
    except (OSError, ValueError, TypeError):
        return fallback


def _copy_trace(package: Path, evidence: Path) -> dict:
    copied = {}
    for relative in (
        Path(".mt/trace_summary.json"),
        Path(".mt/diagnostic_summary.json"),
        Path(".mt/trace_export.jsonl"),
        Path(".mt/blocker_inventory.json"),
        Path("review_only.csv"),
        Path("raw_candidates.csv"),
        Path("raw_candidates_rejected.csv"),
    ):
        source = package / relative
        if not source.is_file():
            continue
        target = evidence / relative.name
        shutil.copy2(source, target)
        copied[relative.name] = str(target)
    return copied


def _worker_success(completion: dict) -> bool:
    """Require the worker's quality-gated completion, not only event transport OK."""
    return bool(
        completion.get("ok")
        and completion.get("complete")
        and not completion.get("pending")
        and not completion.get("review_only")
        and not completion.get("blocked")
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--model", choices=("ct2",), default="ct2")
    parser.add_argument("--model-dir", type=Path, default=None)
    parser.add_argument("--model-revision", default="")
    parser.add_argument("--indices", default="", help="comma-separated 1-based corpus row indices")
    parser.add_argument("--scope", default="")
    parser.add_argument("--timeout", type=int, default=900)
    args = parser.parse_args()

    input_path = args.input.expanduser().resolve()
    model_dir = args.model_dir.expanduser().resolve() if args.model_dir else None
    scope_id = args.scope.strip() or new_scope_id("phase-c-ct2-benchmark")
    scope_root = WORK_ROOT / "phase_c_benchmark" / scope_id
    package = scope_root / "package"
    evidence = WORK_ROOT / "evidence" / scope_id
    report_path = evidence / f"{args.model}_worker_benchmark.json"
    for artifact_id, path, kind, lifecycle, purpose in (
        (f"phase-c-benchmark-work:{scope_id}", scope_root, "benchmark_workspace", "DISPOSABLE", "temporary worker package"),
        (f"phase-c-benchmark-package:{scope_id}", package, "translation_package", "DISPOSABLE", "temporary production worker package"),
        (f"phase-c-benchmark-evidence:{scope_id}", evidence, "benchmark_evidence", "RETAINED", "worker benchmark report and trace export"),
    ):
        register_artifact(
            artifact_id=artifact_id,
            path=path,
            kind=kind,
            created_by="phase_c_ct2_sample.py",
            owner="phase_c_ct2_sample.py",
            purpose=purpose,
            lifecycle=lifecycle,
            scope_id=scope_id,
            run_id=scope_id,
            scope_root=scope_root,
        )

    report = {
        "schema_version": 1,
        "source_sha": _source_sha(),
        "model_request": {"model": args.model, "model_dir": str(model_dir) if model_dir else "", "model_revision": args.model_revision},
        "model_lifecycle": {"status": "PREEXISTING", "created_by_benchmark": False},
        "scope_id": scope_id,
        "scope_root": str(scope_root),
        "rows": [],
    }
    proc = None
    try:
        all_sources = _load_corpus(input_path)
        selected_indices = _parse_indices(args.indices, len(all_sources))
        sources = [all_sources[index - 1] for index in selected_indices]
        entries = [_entry(index, source) for index, source in enumerate(sources, 1)]
        report["corpus"] = _corpus_identity(input_path, entries)
        report["corpus"].update(
            {
                "canonical_row_count": len(all_sources),
                "selected_indices": selected_indices,
                "canonical_input_sha256": _sha256(input_path),
            }
        )
        package.mkdir(parents=True, exist_ok=True)
        evidence.mkdir(parents=True, exist_ok=True)
        write_package(str(package), entries, [], {"files_scanned": 1, "phase_c_benchmark": True}, separate_review=False, enable_trace=True)
        proc = start_worker()
        read_ready(proc, timeout=min(args.timeout, 120))
        events = run_task(
            proc,
            f"phase-c-{args.model}",
            "translate",
            {"csv_path": str(package / "translation.csv"), "model": args.model, "model_dir": str(model_dir) if model_dir else "", "model_revision": args.model_revision, "overwrite": True},
            timeout=args.timeout,
        )
        complete = complete_for(events, f"phase-c-{args.model}")
        _fields, translated_rows = read_csv_rows_file(package / "translation.csv")
        translated_by_key = {str(row.get("key") or ""): row for row in translated_rows}
        whitelist = load_whitelist()
        status = _read_json(package / ".mt" / "translate_status.json", {})
        model_metadata = status.get("model_metadata") if isinstance(status, dict) else None
        trace_evidence = _copy_trace(package, evidence)
        trace_path = str(trace_evidence.get("trace_export.jsonl") or "")
        for index, entry in enumerate(entries, 1):
            row = translated_by_key.get(entry.key, {})
            output = str(row.get("translation") or "")
            structural = structural_problems({**entry.to_csv_row(), "key": entry.key}, output)
            quality = candidate_quality_issues({**entry.to_csv_row(), "key": entry.key}, output, whitelist)
            english_score, english_reasons = english_report(entry.source_text, output, whitelist)
            report["rows"].append({
                "ordinal": index, "key": entry.key, "source": entry.source_text, "translation": output, "output": output,
                "model_metadata": model_metadata,
                "trace_evidence_path": trace_path,
                "automated_structural_verdict": "PASS" if not structural else "FAIL", "automated_structural_reasons": structural,
                "automated_quality_verdict": "PASS" if not quality else "REVIEW_REQUIRED", "automated_quality_reasons": quality,
                "residual_english": {"verdict": "PASS" if not english_reasons else "FAIL", "score": english_score, "reasons": english_reasons},
                "semantic_review_verdict": "REVIEW_REQUIRED",
                "semantic_review_reason": "Requires explicit human comparison of source meaning and model output.",
            })
        report["worker_complete"] = complete
        report["translate_status"] = status
        report["model_metadata"] = status.get("model_metadata") if isinstance(status, dict) else None
        report["trace_evidence"] = trace_evidence
        worker_success = _worker_success(complete)
        report["benchmark_status"] = "WORKER_COMPLETE" if worker_success else "WORKER_FAILED"
    except Exception as exc:
        report["benchmark_status"] = "WORKER_BLOCKED"
        report["error"] = f"{type(exc).__name__}: {exc}"
    finally:
        if proc is not None:
            stop_worker(proc)
        # Benchmark verdict and artifact cleanup are independent: copied evidence
        # is retained, while the disposable package/cache scope is always removed.
        report["cleanup"] = cleanup_after_test(
            [scope_root],
            reason="phase_c_ct2_sample.py worker benchmark",
            outcome="PASS",
            scope_id=scope_id,
            run_id=scope_id,
        )
        evidence.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"benchmark_status": report["benchmark_status"], "report": str(report_path)}, ensure_ascii=False))
    return 0 if report["benchmark_status"] == "WORKER_COMPLETE" else 1


if __name__ == "__main__":
    raise SystemExit(main())
