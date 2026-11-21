"""End-to-end user journey on ONE game folder, with time budgets and stall detection.  Works for any game; nothing is keyed to a particular title.

Steps: scan -> extract text -> image scan -> fill a deterministic stand-in translation -> build patch -> install into a HARD-LINK copy -> uninstall ->
compare the copy with the original by hash.  The original folder is never written: the copy shares its files by hard link, and the installer replaces files
by temp-and-move, so the original bytes cannot change (this is verified by hashing the original before and after).

The result is anonymous: a label you choose, counts and seconds; never a game or file name.

  python tests/tools/journey_check.py GAME_DIR --label corpus-01 --out WORK_DIR [--installer InstallerCli.exe (tests/installer_cli)] [--sdk RENPY_SDK_DIR]
  Env DOTNET_ROLL_FORWARD=Major may be needed to run the installer with a newer runtime.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import queue
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BUDGET = {"analyze": (180, 90), "extract": (900, 180), "image_scan": (7200, 180), "patch": (900, 180)}   # (total seconds, max silent seconds)
SMALL = 16 * 1024 * 1024


class Worker:
    def __init__(self, python: str):
        env = dict(os.environ, PYTHONUTF8="1", PYTHONIOENCODING="utf-8", PYTHONDONTWRITEBYTECODE="1", OMP_NUM_THREADS="1", PYTHONPATH=str(ROOT))
        self.proc = subprocess.Popen([python, "-m", "vntext_worker.worker_main"], cwd=ROOT, env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                     stderr=subprocess.DEVNULL, text=True, encoding="utf-8")
        self.events: queue.Queue = queue.Queue()
        threading.Thread(target=lambda: [self.events.put(line) for line in self.proc.stdout], daemon=True).start()
        self.wait_ready()

    def wait_ready(self):
        while json.loads(self.events.get(timeout=60))["type"] != "ready":
            pass

    def run(self, task_id: str, task: str, params: dict, total: float, silent: float) -> dict:
        started = last = time.monotonic()
        self.proc.stdin.write(json.dumps({"v": 1, "type": "run", "id": task_id, "task": task, "params": params}) + "\n")
        self.proc.stdin.flush()
        progress_seen = 0
        while True:
            now = time.monotonic()
            if now - started > total:
                return {"outcome": "OVER_BUDGET", "seconds": round(now - started, 1)}
            if now - last > silent:
                return {"outcome": "STALLED", "seconds": round(now - started, 1)}
            try:
                event = json.loads(self.events.get(timeout=1))
            except queue.Empty:
                continue
            if event.get("id") != task_id:
                continue
            last = time.monotonic()
            if event["type"] == "progress":
                progress_seen += 1
            elif event["type"] == "complete":
                event["outcome"] = "DONE"
                event["seconds"] = round(time.monotonic() - started, 1)
                event["progress_events"] = progress_seen
                return event

    def kill(self):
        try:
            self.proc.kill()
        except OSError:
            pass


def _sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def snapshot(root: Path) -> dict[str, tuple]:
    """Relative path -> (size, content id).  Big files are identified by size+mtime (hashing tens of GB per run is not the point); small ones by hash."""
    result = {}
    for current, _dirs, names in os.walk(root):
        for name in names:
            full = Path(current) / name
            info = full.lstat()
            ident = _sha(full) if info.st_size <= SMALL else f"{info.st_size}:{info.st_mtime_ns}"
            result[full.relative_to(root).as_posix()] = (info.st_size, ident)
    return result


def link_copy(source: Path, dest: Path) -> int:
    count = 0
    for current, dirs, names in os.walk(source):
        rel = Path(current).relative_to(source)
        (dest / rel).mkdir(parents=True, exist_ok=True)
        for name in names:
            os.link(Path(current) / name, dest / rel / name)
            count += 1
    return count


def _same_length(text: str) -> str:
    """Different but equally long text: swap the case of letters outside tags/placeholders (Unity v22+ cannot grow objects, so a longer stand-in cannot be patched)."""
    out, depth = [], 0
    for ch in text:
        if ch in "<{[":
            depth += 1
        elif ch in ">}]" and depth:
            depth -= 1
        out.append(ch if depth or not ch.isalpha() else (ch.lower() if ch.isupper() else ch.upper()))
    return "".join(out)


def fill_translation(csv_path: Path, same_length: bool = False) -> int:
    with csv_path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        fields = reader.fieldnames or []
        rows = list(reader)
    source_col = next((c for c in ("source_text", "source", "text") if c in fields), None)
    if "translation" not in fields or source_col is None:
        return 0
    filled = 0
    for row in rows:
        if not (row.get("translation") or "").strip() and (row.get(source_col) or "").strip():
            row["translation"] = _same_length(row[source_col]) if same_length else "VI " + row[source_col]
            filled += 1
    with csv_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    return filled


def run_installer(installer: str, args: list[str]) -> tuple[int, str]:
    env = dict(os.environ, DOTNET_ROLL_FORWARD=os.environ.get("DOTNET_ROLL_FORWARD", "Major"))
    proc = subprocess.run([installer, *args], capture_output=True, text=True, encoding="utf-8", errors="replace", env=env, timeout=600)
    return proc.returncode, (proc.stdout + proc.stderr)[-1500:]


def journey(game: Path, label: str, out: Path, python: str, installer: str | None, sdk: str | None) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    result: dict = {"label": label, "steps": {}, "verdict": "PASS", "not_run": []}
    steps = result["steps"]

    def fail(step: str, why: str):
        steps[step]["ok"] = False
        steps[step]["why"] = why
        result["verdict"] = "FAIL"

    package = out / "package"
    shutil.rmtree(package, ignore_errors=True)
    original_before = snapshot(game)
    worker = Worker(python)
    try:
        r = worker.run("a", "analyze", {"src": str(game), "report_out": str(package), "include_sha256": True, "probe_unity_objects": True}, *BUDGET["analyze"])
        steps["scan"] = {"ok": r.get("outcome") == "DONE" and bool(r.get("ok")), "seconds": r["seconds"], "progress_events": r.get("progress_events", 0), "outcome": r["outcome"]}
        report_file = package / "unity_analysis.json"
        if report_file.is_file():
            report = json.loads(report_file.read_text(encoding="utf-8"))
            steps["scan"]["engine"] = (report.get("engine_detection") or {}).get("engine")
            steps["scan"]["step_seconds"] = report.get("timings_seconds")
        if not steps["scan"]["ok"]:
            fail("scan", r.get("outcome") if r.get("outcome") != "DONE" else (r.get("error") or "scan not ok")[:200])
        extract_params = {"src": str(game), "out": str(package), "mode": "deep", "level": "balanced", "renpy_sdk_action": "existing" if sdk else "none"}
        if sdk:
            extract_params["renpy_sdk_path"] = sdk
        r = worker.run("e", "extract", extract_params, *BUDGET["extract"])
        csv_path = package / "translation.csv"
        steps["extract"] = {"ok": r.get("outcome") == "DONE" and csv_path.is_file(), "seconds": r["seconds"], "status": r.get("extract_status"),
                            "csv_present_at_terminal": csv_path.is_file(), "outcome": r["outcome"], "progress_events": r.get("progress_events", 0)}
        if not steps["extract"]["ok"]:
            fail("extract", r.get("outcome") if r.get("outcome") != "DONE" else (r.get("error") or "no csv")[:200])
        if r.get("image_scan_pending"):
            r2 = worker.run("i", "image_batch", {"src": str(game), "out": str(package), "after_extract": True}, *BUDGET["image_scan"])
            steps["image_scan"] = {"ok": r2.get("outcome") == "DONE" and bool(r2.get("ok")), "seconds": r2["seconds"], "outcome": r2["outcome"], "progress_events": r2.get("progress_events", 0)}
            if not steps["image_scan"]["ok"]:
                fail("image_scan", r2.get("outcome") if r2.get("outcome") != "DONE" else (r2.get("error") or "")[:200])
        if not csv_path.is_file():
            result["not_run"] += ["patch", "install", "uninstall"]
        else:
            filled = fill_translation(csv_path, same_length=steps["scan"].get("engine") == "UNITY")
            steps["stand_in_translation"] = {"ok": filled > 0, "rows": filled}
            if filled == 0:
                result["not_run"] += ["patch", "install", "uninstall"]
                steps["stand_in_translation"]["why"] = "no translatable rows"
            else:
                manifest = package / "manifest.json"
                r = worker.run("p", "patch", {"src": str(game), "out": str(package), "csv_path": str(csv_path), "manifest_path": str(manifest), "partial_override": True},
                               *BUDGET["patch"])
                patches = sorted(package.rglob("Patch_*/**/*.exe")) or sorted(package.rglob("Patch_*/*.exe")) or sorted(package.rglob("patch_manifest.json"))
                steps["patch"] = {"ok": r.get("outcome") == "DONE" and bool(patches), "seconds": r["seconds"], "outcome": r["outcome"], "patch_built": bool(patches),
                                  "progress_events": r.get("progress_events", 0)}
                if not steps["patch"]["ok"]:
                    fail("patch", r.get("outcome") if r.get("outcome") != "DONE" else (r.get("error") or "no patch built")[:200])
                    result["not_run"] += ["install", "uninstall"]
                elif not installer and patches[-1].suffix.lower() != ".exe":
                    result["not_run"] += ["install", "uninstall"]
                else:
                    patch_file = patches[-1]
                    bundled = patch_file.suffix.lower() == ".exe"        # the product's own self-contained installer: use exactly what a player would run
                    copy = out / "game-copy"
                    shutil.rmtree(copy, ignore_errors=True)
                    linked = link_copy(game, copy)
                    before_copy = snapshot(copy)
                    code, text = (run_installer(str(patch_file), ["--install", str(copy)]) if bundled else run_installer(installer, ["install", str(patch_file.parent), str(copy)]))
                    steps["install"] = {"ok": code == 0, "linked_files": linked}
                    if code != 0:
                        fail("install", text[-300:])
                    else:
                        code, text = (run_installer(str(patch_file), ["--uninstall", str(copy)]) if bundled else run_installer(installer, ["uninstall", str(patch_file.parent), str(copy)]))
                        steps["uninstall"] = {"ok": code == 0}
                        if code != 0:
                            fail("uninstall", text[-300:])
                        else:
                            after_copy = snapshot(copy)
                            leftover = sorted(set(after_copy) ^ set(before_copy)) + [k for k in before_copy if k in after_copy and before_copy[k] != after_copy[k]]
                            steps["uninstall"]["identical_to_pre_install"] = not leftover
                            steps["uninstall"]["differences"] = len(leftover)
                            if leftover:
                                fail("uninstall", f"{len(leftover)} path(s) differ from the pre-install state")
                    shutil.rmtree(copy, ignore_errors=True)
        steps["original_untouched"] = {"ok": snapshot(game) == original_before}
        if not steps["original_untouched"]["ok"]:
            fail("original_untouched", "the source folder changed during the journey")
    finally:
        worker.kill()
    return result


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("game")
    ap.add_argument("--label", required=True, help="anonymous label for the result, e.g. corpus-01")
    ap.add_argument("--out", required=True, help="work folder OUTSIDE the game and outside the repo")
    ap.add_argument("--python", default=sys.executable)
    ap.add_argument("--installer")
    ap.add_argument("--sdk")
    args = ap.parse_args()
    game = Path(args.game).resolve()
    out = Path(args.out).resolve()
    if out == game or game in out.parents or out in game.parents:
        print("--out must be separate from the game folder", file=sys.stderr)
        return 2
    result = journey(game, args.label, out, args.python, args.installer, args.sdk)
    print(json.dumps(result, ensure_ascii=False, indent=1))
    return 0 if result["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
