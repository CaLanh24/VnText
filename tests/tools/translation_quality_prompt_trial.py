"""Frozen synthetic development/final prompt experiment, outside product routing."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "tests/lib")]
from tests.tools.translation_quality_low_memory_trial import run_one, MODEL, CLI
from work_paths import WORK_ROOT, ambient_scope, register_artifact
from vntext.mt_check import structural_problems

EVIDENCE = ROOT / "DEV_RUN/translation-quality-phase4"
DATA = ROOT / "evaluation/translation_quality_phase1/dataset.v1.json"
BASELINE = ROOT / "DEV_RUN/translation-quality-phase2/pipeline-arms.v1.json"
DATA_HASH = "7f75108ff031022f94b5a68965eebc6f0a99ff37d3fd1804ebec4c6d2fe9242d"
MODEL_HASH = "dc5f44fcf1fa496ee7ad725982c0c8c553a4de00259b53af84c4b89fb0c06699"
PANEL = ("DLG-008", "IDI-005", "ADDR-008", "TERM-001", "TERM-014", "IDI-009",
         "IDI-013", "UI-001", "TERM-004", "TOK-001", "TOK-003", "TOK-006")
VARIANTS = ("source", "context", "repair")
GLOSSARY = {"checksum": "mã kiểm tra", "manifest": "bản kê khai", "cache": "bộ nhớ đệm",
            "glossary": "bảng thuật ngữ", "CSV": "CSV", "placeholder": "biến giữ chỗ"}


def digest(path):
    with Path(path).open("rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()


def context_for(row, rows):
    boundary = row["scenario_boundary"]
    prior = []
    if boundary.get("kind") != "standalone_line":
        prior = [other for other in rows if all(
            other["scenario_boundary"].get(k) == boundary.get(k)
            for k in ("file_id", "group_id", "engine"))
            and other["split"] == row["split"]
            and other["scenario_boundary"]["turn"] < boundary["turn"]]
    prior.sort(key=lambda other: other["scenario_boundary"]["turn"])
    selected = prior[-2:]
    lines = [r["source_en"] for r in selected]
    if row.get("address_context"):
        lines.append("Speaker relationship: " + row["address_context"])
    return "\n".join(lines), [r["id"] for r in selected]


def prompt_for(row, rows, variant, draft, style="explicit"):
    if variant not in VARIANTS:
        raise ValueError(variant)
    sections = ["Translate English into Vietnamese. Output only the translation of [Source Text]. "
                "Do not explain, quote headings, or add information. "
                "Preserve names, placeholders, tags, bracket tokens and literal \\n exactly."]
    if row["group"] in ("terminology", "ui"):
        sections.append("Domain: software documentation and application interface.")
    terms = [f"{term} translates to {target}" for term, target in GLOSSARY.items()
             if re.search(r"(?<!\w)" + re.escape(term) + r"(?!\w)", row["source_en"], re.I)]
    if terms:
        sections.append("Reference terminology:\n" + "\n".join(terms))
    context, ids = context_for(row, rows) if variant != "source" else ("", [])
    if style == "concise":
        short = []
        if row["group"] in ("terminology", "ui"):
            short.append("Domain: software documentation and application interface.")
        if terms:
            short.append("Reference translations:\n" + "\n".join(terms))
        if context:
            short.append("Background (reference only, do not translate):\n" + context)
        if variant == "repair" and draft:
            short.append("Vietnamese draft (may be incorrect; reference only):\n" + draft)
        if re.search(r"[{}<>\[\]]|\\[nrt]", row["source_en"]):
            short.append("Preserve placeholders, tags, bracket tokens and escape sequences exactly.")
        short.append("Translate the following English text into Vietnamese, without additional explanation:\n\n" + row["source_en"])
        return "\n\n".join(short), ids
    if style != "explicit":
        raise ValueError(style)
    if context:
        sections.append("[Background Information - reference only, NEVER translate this section]\n" + context)
    if variant == "repair" and draft:
        sections.append("[Draft - reference only, may be incorrect]\n" + draft)
    sections.append("Translate ONLY [Source Text] below, using background only to resolve ambiguity. "
                    "Do not translate background or copy its facts into the result.")
    sections.append("[Source Text]\n" + row["source_en"])
    return "\n\n".join(sections), ids


def output_from(result):
    marker = "> " + result["prompt"]
    if result.get("stdout", "").count(marker) != 1:
        raise ValueError("ambiguous or missing CLI prompt boundary")
    output = result["stdout"].split(marker, 1)[1]
    if "\n[ Prompt:" not in output:
        raise ValueError("missing completion timing boundary")
    return output.split("\n[ Prompt:", 1)[0].strip()


def completion_output(text):
    # llama-completion renders the terminal EOG token; retain raw stdout separately.
    value = text.strip()
    suffix = "[end of text]"
    if value.endswith(suffix):
        value = value[:-len(suffix)].rstrip()
    return value


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("stage", choices=("development", "final"))
    parser.add_argument("--attempt", type=int, default=1)
    parser.add_argument("--style", choices=("explicit", "concise"), default="explicit")
    args = parser.parse_args()
    report_path = EVIDENCE / (args.stage + (f"-{args.attempt}" if args.attempt != 1 else "") + ".json")
    if report_path.exists():
        raise FileExistsError(report_path)
    assert digest(DATA) == DATA_HASH
    assert digest(MODEL) == MODEL_HASH
    data = json.loads(DATA.read_text(encoding="utf-8"))
    baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
    arms = {a["name"]: {r["id"]: r for r in a["rows"]} for a in baseline["arms"]}
    unassisted, glossary = arms["unassisted"], arms["glossary"]
    script_hash = digest(Path(__file__))
    helper_hash = digest(ROOT / "tests/tools/translation_quality_low_memory_trial.py")
    variants = VARIANTS
    rows = [r for r in data["rows"] if r["id"] in PANEL]
    if args.stage == "development":
        assert len(rows) == len(PANEL) and all(r["split"] == "development" for r in rows)
    else:
        selection = json.loads((EVIDENCE / "selection.json").read_text(encoding="utf-8"))
        assert selection["script_sha256"] == script_hash
        assert selection["helper_sha256"] == helper_hash
        assert selection["dataset_sha256"] == DATA_HASH
        assert selection["variant"] in VARIANTS
        assert selection["style"] == args.style
        assert selection["held_out_outputs_reviewed"] is False
        variants, rows = (selection["variant"],), data["rows"]
    scope = ambient_scope()
    work = WORK_ROOT / "prompt-trial"
    register_artifact(artifact_id="prompt-trial", path=work, kind="test_temp", created_by=__file__,
                      owner=__file__, purpose="isolated synthetic CLI inference", lifecycle="DISPOSABLE",
                      scope_id=scope["scope_id"], run_id=scope["run_id"], scope_root=scope["scope_root"])
    work.mkdir(parents=True)
    report = {"stage": args.stage, "source_sha": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
              "script_sha256": script_hash, "helper_sha256": helper_hash,
              "dataset_sha256": DATA_HASH, "model_sha256": MODEL_HASH,
              "baseline_sha256": digest(BASELINE), "runtime_sha256": digest(CLI.with_name("llama-completion.exe")),
              "variants": variants, "style": args.style, "semantic_acceptance": "UNKNOWN; agent review only, no human gold",
              "runs": [], "status": "IN_PROGRESS"}
    started = time.monotonic()
    for row in rows:
        for variant in variants:
            if time.monotonic() - started > (1650 if args.stage == "development" else 3300):
                report["status"] = "TOTAL_TIMEOUT"
                break
            prompt, context_ids = prompt_for(row, data["rows"], variant, unassisted[row["id"]]["output"], args.style)
            result = run_one(prompt, work, row["id"]+"-"+variant, no_repack=True, max_tokens=128, completion=True)
            result.update(id=row["id"], split=row["split"], group=row["group"], source=row["source_en"],
                          variant=variant, context_ids=context_ids,
                          opus_unassisted=unassisted[row["id"]], opus_glossary=glossary[row["id"]])
            if result["status"] == "RETURNED":
                try:
                    result["output"] = completion_output(result["stdout"])
                    result["structural_reasons"] = structural_problems({"source_text": row["source_en"], "key": row["id"]}, result["output"])
                    if not result["output"]:
                        raise ValueError("empty translation")
                except ValueError as exc:
                    result.update(status="OUTPUT_BOUNDARY_ERROR", output_error=str(exc))
            report["runs"].append(result)
            if result["status"] != "RETURNED":
                report["status"] = result["status"]
            report["elapsed_seconds"] = round(time.monotonic()-started, 3)
            report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
            print(row["id"], variant, result["status"], result.get("seconds"), flush=True)
            if report["status"] != "IN_PROGRESS":
                return 1
        if report["status"] != "IN_PROGRESS":
            break
    else:
        report["status"] = "COMPLETED"
    report["model_unchanged"] = digest(MODEL) == MODEL_HASH
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0 if report["status"] == "COMPLETED" and report["model_unchanged"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
