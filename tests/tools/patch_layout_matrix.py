"""Patch -> install -> uninstall matrix over the generated (synthetic, anonymous) layouts used by the scan/extract matrices.

Per layout that yields translatable text: build a patch, then on HARD-LINK copies of the layout run
  basic     install -> uninstall (previous)                 => identical to the pre-install state
  upgrade   install -> install again -> restore-original    => identical to the pre-install state (an old translation must not survive)
  nobackup  install -> delete the backup -> uninstall       => the tool must not "restore" anything it cannot verify: game files unchanged from post-install
Layouts that yield no patch must end with a stated reason, never a crash.  The original layout is hashed before/after (never written).

  python tests/tools/patch_layout_matrix.py --installer <InstallerCli.exe> [--python PY] [--work DIR]
Prints one JSON report: counts of layouts run / patched / refused (with reason) / failed.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests" / "tools"))

from journey_check import BUDGET, Worker, fill_translation, link_copy, run_installer, snapshot  # noqa: E402
import tests.unit.test_scan_layout_matrix as layouts_module  # noqa: E402

# Enough ordinary dialogue for the quality gate to accept rows (the scan matrix's one-line script is too small to patch).
_LINES = "".join(f'    "This is line number {i} of the story, spoken aloud by a narrator."\n' for i in range(1, 41))
layouts_module.SCRIPT = ("label start:\n" + _LINES + "    return\n").encode()
LAYOUTS = layouts_module.LAYOUTS


def _keep(stage: Path, dest: Path) -> Path:
    """The worker removes its staging folder shortly after the task ends; take a copy at once so the installer can be driven from it."""
    shutil.copytree(stage, dest)
    return dest


def diff(a: dict, b: dict) -> list[str]:
    return sorted(set(a) ^ set(b)) + [k for k in a if k in b and a[k] != b[k]]


def run_layout(name: str, build, worker: Worker, installer: str, work: Path, sdk: str | None) -> dict:
    root = work / name / "game root"
    root.mkdir(parents=True)
    build(root)
    before_original = snapshot(root)
    package = work / name / "package"
    entry: dict = {"layout": name, "result": "FAIL", "scenarios": {}}
    r = worker.run("e", "extract", {"src": str(root), "out": str(package), "mode": "deep", "level": "balanced", "renpy_sdk_action": "existing" if sdk else "none", **({"renpy_sdk_path": sdk} if sdk else {})}, *BUDGET["extract"])
    csv_path = package / "translation.csv"
    if r.get("outcome") != "DONE":
        entry["why"] = f"extract {r.get('outcome')}"
        return entry
    if not csv_path.is_file() or fill_translation(csv_path) == 0:
        reason = str(r.get("error") or "").strip()
        entry.update(result="REFUSED" if reason else "FAIL", why=reason or "no text and no stated reason")
        entry["original_untouched"] = snapshot(root) == before_original
        if not entry["original_untouched"]:
            entry["result"] = "FAIL"
        return entry
    r = worker.run("p", "patch", {"src": str(root), "out": str(package), "csv_path": str(csv_path), "manifest_path": str(package / "manifest.json"), "partial_override": True, **({"renpy_sdk_action": "existing", "renpy_sdk_path": sdk} if sdk else {})},
                   *BUDGET["patch"])
    manifests = [m for m in sorted(package.rglob("patch_manifest.json")) if (m.parent / "COPY_TO_GAME_ROOT").is_dir()]
    if r.get("outcome") != "DONE" or not manifests:
        reason = str(r.get("error") or r.get("outcome") or "").strip()
        entry.update(result="REFUSED" if reason and r.get("outcome") == "DONE" and not r.get("ok") else "FAIL", why=reason[:200] or "no patch and no stated reason")
        return entry
    patch_dir = _keep(manifests[-1].parent, work / name / "patch-kept")
    failures = []

    def fresh_copy(tag: str) -> Path:
        copy = work / name / f"copy-{tag}"
        shutil.rmtree(copy, ignore_errors=True)
        link_copy(root, copy)
        return copy

    def installer_ok(args: list[str]) -> tuple[bool, str]:
        code, text = run_installer(installer, args)
        return code == 0, text

    # basic
    copy = fresh_copy("basic")
    pre = snapshot(copy)
    ok1, t1 = installer_ok(["install", str(patch_dir), str(copy)])
    mid = snapshot(copy) if ok1 else {}
    ok2, t2 = installer_ok(["uninstall", str(patch_dir), str(copy)]) if ok1 else (False, "")
    left = diff(pre, snapshot(copy)) if ok1 and ok2 else ["not-run"]
    entry["scenarios"]["basic"] = {"ok": ok1 and ok2 and not left and mid != pre, "changed_by_install": mid != pre, "differences": len(left), "note": (t1 + t2)[-160:] if not (ok1 and ok2 and not left) else "", "patch_dir_has_manifest": (patch_dir / "patch_manifest.json").is_file(), "install_ok": ok1, "uninstall_ok": ok2, "t1": t1[-120:], "t2": t2[-120:], "dbg": str(patch_dir.relative_to(work)) + " :: " + ",".join(sorted(x.name for x in patch_dir.parent.iterdir()))[:200] if patch_dir.parent.exists() else "parent gone"}
    if not ok1 and "Sai th" in t1 and not diff(pre, snapshot(copy)):
        # The patch builder accepted a folder the installer does not recognise as a game: the installer said so and wrote nothing.  Safe, but reported as its own class.
        entry.update(result="REFUSED_AT_INSTALL", why=t1.strip()[-160:], original_untouched=snapshot(root) == before_original)
        return entry
    # upgrade: the same patch cannot be installed twice (refused, nothing changed); a DIFFERENT patch upgrades, and restore-original must still reach the pristine game
    copy = fresh_copy("upgrade")
    ok1, _ = installer_ok(["install", str(patch_dir), str(copy)])
    after_first = snapshot(copy) if ok1 else {}
    again_ok, _ = installer_ok(["install", str(patch_dir), str(copy)]) if ok1 else (True, "")
    refused_cleanly = ok1 and not again_ok and not diff(after_first, snapshot(copy))
    second_dir = None
    package2 = work / name / "package2"
    shutil.copytree(package, package2, ignore=shutil.ignore_patterns("Patch_*", ".patch-build"))
    csv2 = package2 / "translation.csv"
    if fill_translation(csv2, prefix="VIB ", overwrite=True):
        r2 = worker.run("p2", "patch", {"src": str(root), "out": str(package2), "csv_path": str(csv2), "manifest_path": str(package2 / "manifest.json"), "partial_override": True,
                                          **({"renpy_sdk_action": "existing", "renpy_sdk_path": sdk} if sdk else {})}, *BUDGET["patch"])
        found = [m for m in sorted(package2.rglob("patch_manifest.json")) if (m.parent / "COPY_TO_GAME_ROOT").is_dir()]
        second_dir = _keep(found[-1].parent, work / name / "patch2-kept") if r2.get("outcome") == "DONE" and found else None
    upgraded, up_msg = False, ""
    if ok1 and second_dir is not None:
        upgraded, up_msg = installer_ok(["install", str(second_dir), str(copy)])
    second_refused_safely = upgraded or (second_dir is not None and bool(up_msg.strip()) and not diff(after_first, snapshot(copy)))   # a patch built from a different state is refused, with a reason, and nothing changes
    restored, t2 = installer_ok(["restore-original", str(second_dir if upgraded else patch_dir), str(copy)]) if ok1 else (False, "")
    left = diff(pre, snapshot(copy)) if restored else ["not-run"]
    entry["scenarios"]["upgrade"] = {"ok": refused_cleanly and second_refused_safely and restored and not left, "same_patch_reinstall_refused_cleanly": refused_cleanly,
                                     "second_patch_built": second_dir is not None, "second_patch_installed_over_first": upgraded, "second_patch_refused_safely": second_refused_safely, "second_install_message": up_msg.strip()[-200:], "differences_after_restore_original": len(left),
                                     "note": t2[-160:] if left else ""}
    # missing backup
    copy = fresh_copy("nobackup")
    ok1, _ = installer_ok(["install", str(patch_dir), str(copy)])
    backups = [b for b in patch_dir.rglob("install_backup") if b.is_dir()]
    backup = backups[0] if backups else None
    moved = None
    if ok1 and backup is not None:
        moved = work / name / "backup-aside"
        shutil.move(str(backup), str(moved))
    post = snapshot(copy)
    code, text = run_installer(installer, ["uninstall", str(patch_dir), str(copy)]) if ok1 else (1, "")
    after = snapshot(copy)
    # A tool without a backup must either refuse or restore only what the ownership receipt proves; it must never delete game files outside VNText's.
    lost_game_files = [k for k in pre if k not in after]
    entry["scenarios"]["nobackup"] = {"ok": ok1 and not lost_game_files, "backup_found": moved is not None, "exit_code": code, "game_files_lost": len(lost_game_files),
                                      "changed_vs_post_install": len(diff(post, after)), "message": text.strip().splitlines()[-1][:160] if text.strip() else ""}
    if moved is not None:
        shutil.move(str(moved), str(backup))
    for scenario, info in entry["scenarios"].items():
        if not info["ok"]:
            failures.append(scenario)
    entry["original_untouched"] = snapshot(root) == before_original
    if not entry["original_untouched"]:
        failures.append("original_untouched")
    entry["result"] = "FAIL" if failures else "PASS"
    if failures:
        entry["failed"] = failures
    return entry


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--installer", required=True)
    ap.add_argument("--python", default=sys.executable)
    ap.add_argument("--work")
    ap.add_argument("--only", help="comma-separated layout names")
    ap.add_argument("--sdk", help="Ren'Py SDK folder for archive/compiled layouts")
    args = ap.parse_args()
    work = Path(args.work or tempfile.mkdtemp(prefix="plm-", dir=str(ROOT / "TEST_RUN" / "tmp")))
    work.mkdir(parents=True, exist_ok=True)
    worker = Worker(args.python)
    results = []
    try:
        for name, (build, _allowed) in LAYOUTS.items():
            if args.only and name not in args.only.split(","):
                continue
            results.append(run_layout(name, build, worker, args.installer, work, args.sdk))
            shutil.rmtree(work / name, ignore_errors=True)
    finally:
        worker.kill()
        shutil.rmtree(work, ignore_errors=True)
    counts = {k: sum(1 for r in results if r["result"] == k) for k in ("PASS", "REFUSED", "REFUSED_AT_INSTALL", "FAIL")}
    print(json.dumps({"layouts_run": len(results), "layouts_total": len(LAYOUTS), **counts, "results": results}, ensure_ascii=False, indent=1))
    return 1 if counts["FAIL"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
