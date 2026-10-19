"""Compare actual production CT2 pipeline arms on independent synthetic packages."""
from __future__ import annotations

import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "tests/lib")]

from tests.tools import translation_quality_phase1 as evaluator
from work_paths import WORK_ROOT, ambient_scope, register_artifact
from vntext.entry import Entry
from vntext.package_io import write_package, read_csv_rows_file
from vntext.mt_ct2_pipeline import run_ct2_translate
from vntext.mt_memory import build_translation_memory, lookup_translation_memory
from vntext.mt_check import structural_problems, load_whitelist
from vntext.mt_strategies import candidate_quality_issues

EVIDENCE = ROOT / "DEV_RUN/translation-quality-phase2"
REPORT = EVIDENCE / "pipeline-arms.v1.json"
GLOSSARY = {
    "checksum": "mã kiểm tra", "manifest": "bản kê khai", "cache": "bộ nhớ đệm",
    "glossary": "bảng thuật ngữ", "CSV": "CSV", "placeholder": "biến giữ chỗ",
}
MEMORY_DRAFTS = {
    "DLG-008": "Vậy hãy để dành cho tôi một cái ghế bên cạnh cửa sau.",
    "IDI-005": "Đối với Lin, câu đố đầu tiên rất dễ.",
}


def main() -> int:
    if REPORT.exists():
        raise FileExistsError("refusing to overwrite trial evidence")
    dataset, raw, _ = evaluator.load_dataset()
    assert evaluator.sha256_bytes(raw) == "7f75108ff031022f94b5a68965eebc6f0a99ff37d3fd1804ebec4c6d2fe9242d"
    evaluator._configure_offline_cache()
    scope = ambient_scope()
    work = WORK_ROOT / "quality-pipeline-arms"
    register_artifact(
        artifact_id="quality-pipeline-arms", path=work, kind="test_temp",
        created_by=__file__, owner=__file__, purpose="three disposable synthetic pipeline packages",
        lifecycle="DISPOSABLE", scope_id=scope["scope_id"], run_id=scope["run_id"],
        scope_root=scope["scope_root"],
    )
    model_before = evaluator._model_identity()
    report = {
        "schema": 1, "source_sha": evaluator._git_head(),
        "script_sha256": evaluator.sha256_file(Path(__file__)),
        "dataset_sha256": evaluator.sha256_bytes(raw), "arms": [],
        "glossary": GLOSSARY, "memory_fixture_ids": list(MEMORY_DRAFTS),
        "semantic_acceptance": "UNKNOWN; independent agent review, no human gold",
        "memory_generalization": "NOT_CLAIMED: two deliberately in-sample development fixtures",
        "model": model_before, "run_status": "IN_PROGRESS",
    }
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()

    def stopped():
        memory = evaluator._windows_process_memory()
        return time.perf_counter() - started > 840 or (
            not memory["available"] or memory["peak_working_set_bytes"] >= 1024**3
        )

    def save():
        REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    try:
        save()
        for arm in ("unassisted", "glossary", "glossary_memory"):
            if stopped():
                raise RuntimeError("resource/deadline stop before next arm")
            package = work / arm
            entries = [Entry(
                key=row["id"], source_text=row["source_en"],
                file_path=row["scenario_boundary"]["file_id"],
                context=row["scenario_boundary"]["group_id"] + ":" + row["id"],
                import_method="plain_text_line", safety="safe",
                locator={"line": i}, backend="synthetic",
            ).finalize() for i, row in enumerate(dataset["rows"], 1)]
            write_package(str(package), entries, [], {"files_scanned": 54},
                          separate_review=False, enable_trace=True)
            fields, before = read_csv_rows_file(package / "translation.csv")
            if arm != "unassisted":
                (package / ".mt").mkdir(exist_ok=True)
                (package / ".mt/glossary.json").write_text(
                    json.dumps(GLOSSARY, ensure_ascii=False), encoding="utf-8")
            memory = {"entries": []}
            if arm == "glossary_memory":
                seeds = [{**row, "translation": MEMORY_DRAFTS[row["key"]]}
                         for row in before if row["key"] in MEMORY_DRAFTS]
                memory = build_translation_memory(seeds, package)
                assert len(memory["entries"]) == 2
            seed_hash = evaluator.sha256_bytes(evaluator.canonical_json(memory).encode("utf-8"))
            arm_started = time.perf_counter()
            result = run_ct2_translate(package / "translation.csv", model_dir=evaluator.MODEL_DIR,
                                       is_cancelled=stopped)
            after_fields, after = read_csv_rows_file(package / "translation.csv")
            assert fields == after_fields
            assert [(x["key"], x["source_text"]) for x in before] == [
                (x["key"], x["source_text"]) for x in after]
            assert len(after) == 100
            whitelist = load_whitelist()
            rows = []
            for source, row in zip(dataset["rows"], after):
                output = row.get("translation") or ""
                memory_expected = lookup_translation_memory(row, memory)
                rows.append({
                    "id": source["id"], "split": source["split"], "group": source["group"],
                    "source": source["source_en"], "output": output,
                    "disposition": "WRITTEN" if output else "EMPTY_OR_BLOCKED",
                    "structural_reasons": structural_problems(row, output) if output else None,
                    "quality_reasons": candidate_quality_issues(row, output, whitelist) if output else None,
                    "memory_lookup_match": memory_expected is not None,
                    "memory_output_exact": memory_expected is not None and output == memory_expected,
                })
            report["arms"].append({
                "name": arm, "elapsed_seconds": time.perf_counter() - arm_started,
                "pipeline_result": result, "memory_seed_sha256": seed_hash,
                "source_order_schema_unchanged": True, "rows": rows,
                "written": sum(bool(row["output"]) for row in rows),
                "blocked_or_empty": sum(not row["output"] for row in rows),
                "written_structural_failures": sum(bool(row["structural_reasons"]) for row in rows),
            })
            save()
        report["run_status"] = "COMPLETED"
    except BaseException as exc:
        report["run_status"] = "FAILED"
        report["error"] = f"{type(exc).__name__}: {exc}"
        raise
    finally:
        report["elapsed_seconds"] = time.perf_counter() - started
        report["memory_measurement"] = evaluator._windows_process_memory()
        report["model_unchanged"] = evaluator._model_identity()["tree_sha256"] == model_before["tree_sha256"]
        save()
    assert report["model_unchanged"]
    print(json.dumps({"run_status": report["run_status"], "arms": [
        {key: arm[key] for key in ("name", "written", "blocked_or_empty", "written_structural_failures")}
        for arm in report["arms"]]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
