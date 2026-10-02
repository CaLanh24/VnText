"""Verify a completed translation package without mutating its inputs.

An external Unity source root may be supplied explicitly for a patch smoke;
without it the tool remains a package-only verification.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "tests/lib")]
from work_paths import assert_artifact_under_work
from unity_patch_baseline import hash_game_files, inspect_patched_file
from worker_test_lib import start_worker, read_ready, run_task, complete_for, stop_worker
from vntext.mt_qa import run_qa
from vntext.patch_gate import audit_patch_package


def digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def authenticate(package, completion, expected_hash):
    if digest(package / "translation.csv") != expected_hash:
        raise ValueError("saved translation checksum mismatch")
    if completion.get("complete") is not True or completion.get("ok") is not True:
        raise ValueError("saved translation is not complete")
    if any(completion.get(k) != 0 for k in ("pending", "review_only", "blocked")):
        raise ValueError("saved translation contains unresolved rows")
    with (package / "translation.csv").open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    if not rows or any(not row["translation"].strip() for row in rows):
        raise ValueError("empty translations")
    if len(rows) != completion.get("translated"):
        raise ValueError("completion row count mismatch")
    return rows


def authenticate_source(recorded, current):
    if not recorded:
        raise ValueError("missing source fingerprint")
    for rel, expected in recorded.items():
        if current.get(rel.replace("\\", "/"), {}).get("sha256") != expected:
            raise ValueError(f"source fingerprint mismatch: {rel}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", type=Path, required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--csv-sha256", required=True)
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--game-root",
        type=Path,
        default=None,
        help="optional external Unity root for an isolated patch smoke",
    )
    args = parser.parse_args()
    out = assert_artifact_under_work(args.output, "completed-package evidence")
    out.mkdir(parents=True, exist_ok=False)
    provenance = json.loads((args.evidence / "pipeline_status.json").read_text(encoding="utf-8"))
    if provenance["source_sha"] != args.source_sha:
        raise ValueError("translation source provenance mismatch")
    completion = json.loads((args.evidence / "translate_complete.json").read_text(encoding="utf-8"))
    authenticate(args.package, completion, args.csv_sha256)
    before = {str(p.relative_to(args.package)): digest(p) for p in args.package.rglob("*") if p.is_file()}
    result = {
        "mode": "saved-completed-package",
        "translation_source_sha": args.source_sha,
        "tested_head": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        "saved_hashes": before,
        "completion": completion,
        "verdict": "FAIL",
    }
    result["provenance_hashes"] = {
        name: digest(args.evidence / name)
        for name in ("pipeline_status.json", "translate_complete.json")
    }
    result["tested_diff"] = subprocess.check_output(["git", "diff", "--", "tests"], text=True, encoding="utf-8")
    external_root = args.game_root.resolve() if args.game_root else None
    rels: list[str] = []
    original_before: dict = {}
    if external_root is not None:
        if not external_root.is_dir():
            raise ValueError(f"external Unity root is not a directory: {external_root}")
        rels = [
            str(path.relative_to(external_root))
            for path in external_root.rglob("*")
            if path.is_file()
        ]
        original_before = hash_game_files(external_root, rels)
    try:
        recorded_path = args.evidence / "source_fingerprint_before.json"
        if external_root is not None and recorded_path.is_file():
            authenticate_source(
                json.loads(recorded_path.read_text(encoding="utf-8")),
                original_before,
            )
        package = out / "package"
        package.mkdir()
        # Preserve package ledgers, not old patch output or worker results.
        for name in (
            "translation.csv",
            "manifest.json",
            "review_only.csv",
            "raw_unpatchable.csv",
            "technical_skipped.csv",
        ):
            if (args.package / name).is_file():
                shutil.copy2(args.package / name, package / name)
        if (args.package / ".mt").is_dir():
            shutil.copytree(args.package / ".mt", package / ".mt")
        ok, _ = run_qa(package / "translation.csv", final=True, report_path=out / "mt_qa.txt")
        result["mt_qa"] = ok
        if not ok:
            raise AssertionError("fresh read-only mt_qa failed")
        result["preflight"] = audit_patch_package(
            package / "translation.csv",
            package / "manifest.json",
            game_root=external_root,
        )
        if external_root is None:
            result["patch"] = {
                "status": "NOT_TESTABLE",
                "reason": "external Unity root not supplied",
            }
            result["verdict"] = "PASS package validation; external patch not tested"
        else:
            if result["preflight"]["eligible"] != completion["translated"]:
                raise AssertionError("not all translated rows eligible")
            proc = start_worker({"PYTHONDONTWRITEBYTECODE": "1"})
            try:
                read_ready(proc, timeout=90)
                events = run_task(
                    proc,
                    "saved-final-patch",
                    "patch",
                    {"src": str(external_root), "out": str(package)},
                    timeout=1800,
                )
                (out / "worker_events.json").write_text(
                    json.dumps(events, ensure_ascii=False, indent=2), encoding="utf-8"
                )
                result["patch"] = complete_for(events, "saved-final-patch")
                if not result["patch"].get("ok"):
                    raise AssertionError(result["patch"])
            finally:
                stop_worker(proc)
            patch_root = package / "Patch_Viet_Hoa/COPY_TO_GAME_ROOT"
            result["inspections"] = {
                str(path.relative_to(patch_root)): inspect_patched_file(path)
                for path in patch_root.rglob("*")
                if path.is_file()
            } if patch_root.is_dir() else {}
            if not result["inspections"] or not all(
                item["openable"] for item in result["inspections"].values()
            ):
                raise AssertionError("missing or unopenable patch output")
            result["verdict"] = "PASS package and external patch verification"
    finally:
        result["original_before"] = original_before
        result["original_after"] = (
            hash_game_files(external_root, rels) if external_root is not None else {}
        )
        result["saved_unchanged"] = before == {
            str(path.relative_to(args.package)): digest(path)
            for path in args.package.rglob("*")
            if path.is_file()
        }
        if not result["saved_unchanged"] or (
            external_root is not None
            and result["original_before"] != result["original_after"]
        ):
            result["verdict"] = "FAIL immutable input changed"
        (out / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        assert result["saved_unchanged"], "saved package changed"
        if external_root is not None:
            assert result["original_before"] == result["original_after"], "external source changed"


if __name__ == "__main__":
    main()
