"""Bounded Windows CPU mmap trial; never changes the product translation route."""
from __future__ import annotations

import argparse
import ctypes as C
from ctypes import wintypes as W
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "tests/lib")]
from work_paths import WORK_ROOT, ambient_scope, register_artifact

EVIDENCE = ROOT / "DEV_RUN/translation-quality-phase3"
MODEL = ROOT / ".dev-env/cache/models/Hy-MT2-1.8B-GGUF/Hy-MT2-1.8B-Q4_K_M.gguf"
CLI = ROOT / ".dev-env/tools/llama-b11724/llama-cli.exe"
MIB = 1024**2


class Memory(C.Structure):
    _fields_ = [("length", W.DWORD), ("load", W.DWORD)] + [
        (name, C.c_ulonglong) for name in (
            "total_physical", "available_physical", "total_commit", "available_commit",
            "total_virtual", "available_virtual", "available_extended")]


class ProcessMemory(C.Structure):
    _fields_ = [("cb", W.DWORD), ("faults", W.DWORD)] + [
        (name, C.c_size_t) for name in (
            "peak_ws", "ws", "peak_paged", "paged", "peak_nonpaged", "nonpaged",
            "pagefile", "peak_pagefile", "private")]


def memory(process=None):
    m = Memory()
    m.length = C.sizeof(m)
    if not C.windll.kernel32.GlobalMemoryStatusEx(C.byref(m)):
        raise C.WinError()
    result = {name: getattr(m, name) for name in (
        "total_physical", "available_physical", "total_commit", "available_commit")}
    if process is not None:
        pm = ProcessMemory()
        pm.cb = C.sizeof(pm)
        fn = C.windll.psapi.GetProcessMemoryInfo
        fn.argtypes = [W.HANDLE, C.c_void_p, W.DWORD]
        if not fn(W.HANDLE(int(process._handle)), C.byref(pm), pm.cb):
            raise C.WinError()
        result.update(working_set=pm.ws, peak_working_set=pm.peak_ws, private_bytes=pm.private)
    return result


def run_one(prompt, work, label, no_repack=False):
    before = memory()
    result = {"label": label, "prompt": prompt, "before": before, "samples": []}
    if before["available_physical"] < 256*MIB or before["available_commit"] < 2048*MIB:
        return {**result, "status": "PREFLIGHT_BLOCKED"}
    command = [str(CLI), "-m", str(MODEL), "-c", "512", "-b", "32", "-ub", "16",
               "-t", "2", "-n", "64", "--load-mode", "mmap", "--no-warmup",
               "--cache-ram", "0", "--offline", "--single-turn", "--simple-io",
               "--no-display-prompt", "--temp", "0", "--seed", "42", "-p", prompt]
    result["command"] = command
    if no_repack:
        command.append("--no-repack")
    started = time.monotonic()
    low_since = None
    out, err = work / (label + ".out"), work / (label + ".err")
    with out.open("wb") as stdout, err.open("wb") as stderr:
        child = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=stdout, stderr=stderr,
                                 creationflags=subprocess.CREATE_NO_WINDOW)
        try:
            while child.poll() is None:
                now = time.monotonic()
                sample = {"seconds": round(now-started, 3), **memory(child)}
                result["samples"].append(sample)
                low = sample["available_physical"] < 128*MIB
                low_since = (low_since or now) if low else None
                reason = None
                if low_since is not None and now-low_since >= 3:
                    reason = "LOW_PHYSICAL_MEMORY"
                if sample["available_commit"] < 512*MIB:
                    reason = "LOW_COMMIT_HEADROOM"
                if sample["private_bytes"] > 2048*MIB or sample["working_set"] > 1792*MIB:
                    reason = "MODEL_MEMORY_LIMIT"
                if now-started > 120:
                    reason = "TIMEOUT"
                if reason:
                    result["status"] = reason
                    child.kill()
                    break
                time.sleep(0.5)
        finally:
            if child.poll() is None:
                child.kill()
            result["exit_code"] = child.wait(timeout=10)
    result.setdefault("status", "RETURNED" if result["exit_code"] == 0 else "RUNTIME_ERROR")
    result.update(seconds=round(time.monotonic()-started, 3),
                  stdout=out.read_text(encoding="utf-8", errors="replace"),
                  stderr=err.read_text(encoding="utf-8", errors="replace"), after=memory())
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--comparison", action="store_true")
    parser.add_argument("--no-repack", action="store_true")
    args = parser.parse_args()
    stem = "low-memory-comparison" if args.comparison else "low-memory-smoke"
    report_path = EVIDENCE / (stem + ("-no-repack" if args.no_repack else "") + ".json")
    if report_path.exists():
        raise FileExistsError(report_path)
    scope = ambient_scope()
    work = WORK_ROOT / "low-memory-trial"
    register_artifact(artifact_id="low-memory-trial", path=work, kind="test_temp",
                      created_by=__file__, owner=__file__, purpose="bounded CPU trial outputs",
                      lifecycle="DISPOSABLE", scope_id=scope["scope_id"], run_id=scope["run_id"],
                      scope_root=scope["scope_root"])
    work.mkdir(parents=True)
    report = {"source_sha": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
              "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              "model_sha256": hashlib.file_digest(MODEL.open("rb"), "sha256").hexdigest(),
              "human_acceptance": "NOT_CONDUCTED", "runs": []}
    assert report["model_sha256"] == "dc5f44fcf1fa496ee7ad725982c0c8c553a4de00259b53af84c4b89fb0c06699"
    tasks = [("smoke", "Translate the following segment into Vietnamese, without additional explanation.\n\nThen save me a chair beside the back door.")]
    if args.comparison:
        data = json.loads((ROOT/"evaluation/translation_quality_phase1/dataset.v1.json").read_text(encoding="utf-8"))
        baseline = json.loads((ROOT/"DEV_RUN/translation-quality-phase2/pipeline-arms.v1.json").read_text(encoding="utf-8"))
        drafts = {r["id"]: r["output"] for r in baseline["arms"][0]["rows"]}
        tasks = []
        for row_id in ("DLG-008", "IDI-005", "ADDR-008", "TERM-001", "TERM-014"):
            row = next(r for r in data["rows"] if r["id"] == row_id)
            assert row["split"] == "development"
            prior = [r["source_en"] for r in data["rows"] if r["scenario_boundary"]["group_id"] == row["scenario_boundary"]["group_id"] and r["scenario_boundary"]["turn"] < row["scenario_boundary"]["turn"]]
            context = "\n".join(prior + ([row["address_context"]] if row.get("address_context") else [])) or "No prior context available."
            common = f"Context (do not translate):\n{context}\n\nEnglish source:\n{row['source_en']}"
            tasks.extend([(row_id+"-direct", common+"\n\nTranslate only the English source into Vietnamese. Output only the translation."),
                          (row_id+"-repair", common+f"\n\nVietnamese draft:\n{drafts[row_id]}\n\nCorrect this draft using the English source and context. Output only the corrected Vietnamese translation.")])
    for label, prompt in tasks:
        result = run_one(prompt, work, label, args.no_repack)
        report["runs"].append(result)
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(label, result["status"], result.get("seconds"), flush=True)
        if result["status"] != "RETURNED":
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
