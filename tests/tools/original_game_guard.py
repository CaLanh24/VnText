"""Per-file backup / hash guard and restoration for the ORIGINAL approved game around one native run.  DEV never launches the game.

  snapshot  baseline = the CURRENT game + the CURRENT Owner AppData files (+ sha-verified per-file backups of files a run is known to change).  Refuses to overwrite.
  verify    read-only comparison of game and Owner AppData with the baseline.
  restore   DRY-RUN by default.  --execute: archive run-owned saves, uninstall with the EXACT packaged installer (sha required), restore only files that have a
            sha-verified backup, remove only run-owned saves, then require an exact readback.  Anything unexplained is REFUSED (nothing is guessed or deleted).

Owner AppData is never written, restored, repopulated or deleted by this tool; differences are only reported.  The older 497-file snapshot is separate history."""
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

BS = chr(92)
GAME = Path(r"C:\Users\VNTextDev\Desktop\game\Cucked by My Wife")
OWNER = Path(r"C:\Users\VNTextDev\AppData\Roaming\RenPy")
RAR = Path(r"C:\Users\VNTextDev\Desktop\game\Cucked_by_My_Wife.rar")
BASELINE_DIR = Path(r"C:\vnrg\run017\pre-game-v2")
EVIDENCE = Path(r"C:\vnrg\run017\postgame-evidence-v2")
RESULT = Path(r"C:\vnrg\evidence\postgame-v2-restore-result.json")
# What the installed patch adds is read from the package's own patch_manifest.json (exact paths); a run writes saves/ (removed only by this tool) and Ren'Py always compiles
# a matching .rpyc next to each installed .rpy (removed only for those exact siblings).  Nothing else is ever deleted.
RUN_OWNED_PREFIX = "game/saves/"


class Refused(Exception):
    pass


def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def norm(value):
    return value.replace(BS, "/")


def is_reparse(path):
    return os.path.islink(path) or (hasattr(os.path, "isjunction") and os.path.isjunction(path))


def snap(root):
    """Hash every file and list every directory; a junction/symlink anywhere (including the root) is refused, never followed."""
    if is_reparse(root):
        raise Refused("root is a junction/symlink: %s" % root)
    files, dirs = {}, set()
    for r, ds, fs in os.walk(root):
        for d in ds:
            if is_reparse(os.path.join(r, d)):
                raise Refused("junction/symlink inside the tree: %s" % os.path.join(r, d))
            dirs.add(norm(os.path.relpath(os.path.join(r, d), root)))
        for n in fs:
            p = os.path.join(r, n)
            if is_reparse(p):
                raise Refused("symlink inside the tree: %s" % p)
            files[norm(os.path.relpath(p, root))] = sha(p)
    return files, sorted(dirs)


def patch_files(pkg):
    """Exact installed paths from the package manifest (game-relative, no traversal) and their compiled siblings."""
    manifest = Path(pkg) / "patch_manifest.json"
    if not manifest.is_file():
        raise Refused("patch_manifest.json missing in the package")
    paths = [norm(f["path"]) for f in json.loads(manifest.read_text(encoding="utf-8-sig")).get("files", [])]
    if not paths or any(not p.startswith("game/") or ".." in p.split("/") or not p.endswith(".rpy") for p in paths):
        raise Refused("patch manifest lists unexpected paths: %s" % paths)
    return paths, [p + "c" for p in paths]


def parents(rel):
    parts = rel.split("/")[:-1]
    return ["/".join(parts[:i]) for i in range(2, len(parts) + 1)]       # game/tl, game/tl/vietnamese (never "game" itself)


def diff(now, base):
    return {"added": sorted(set(now) - set(base)), "removed": sorted(set(base) - set(now)), "changed": sorted(k for k in now if k in base and now[k] != base[k])}


def game_running():
    return "ftworlds.exe" in os.popen("tasklist").read().lower()


def snapshot(game, owner, rar, baseline_dir, previous_changed, archive_sha, running=game_running):
    if baseline_dir.exists():
        raise Refused("baseline exists and is immutable: %s" % baseline_dir)
    if running():
        raise Refused("the game is running")
    gf, gd = snap(game)
    af, ad = snap(owner)
    baseline_dir.mkdir(parents=True)
    backup = []
    for rel in sorted(previous_changed):
        if rel in gf:
            dst = baseline_dir / "game-files" / Path(*rel.split("/"))
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(game / Path(*rel.split("/")), dst)
            if sha(dst) != gf[rel]:
                raise Refused("backup hash mismatch: " + rel)
            backup.append(rel)
    before = {"utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "game_root": str(game), "owner_root": str(owner), "game": {"files": gf, "dirs": gd},
              "appdata": {"files": af, "dirs": ad}, "backup_game_files": backup, "archive_rpa_sha256": gf.get("game/archive.rpa"), "archive_rpa_ok": gf.get("game/archive.rpa") == archive_sha,
              "rar_sha256": sha(rar) if rar.is_file() else None, "status": "PREPARED_NOT_LAUNCHED"}
    (baseline_dir / "before.json").write_text(json.dumps(before, indent=1), encoding="utf-8")
    return before


def verify(baseline, game, owner):
    gf, gd = snap(game)
    af, ad = snap(owner)
    g, a = diff(gf, baseline["game"]["files"]), diff(af, baseline["appdata"]["files"])
    report = {"game": g, "game_dirs_diff": sorted(set(gd) ^ set(baseline["game"]["dirs"])), "owner": a, "owner_dirs_diff": sorted(set(ad) ^ set(baseline["appdata"]["dirs"]))}
    report["exact"] = not any(g.values()) and not report["game_dirs_diff"] and not any(a.values()) and not report["owner_dirs_diff"]
    return report


def preconditions(baseline, game, owner, rar, pkg, installer_sha, running):
    if not installer_sha:
        raise Refused("the exact installer sha256 is required")
    installer = Path(pkg) / "VNTextPatchInstaller.exe"
    if not installer.is_file():
        raise Refused("installer missing in the package: %s" % installer)
    if sha(installer) != installer_sha:
        raise Refused("installer sha256 differs from the expected exact installer")
    root, package = os.path.realpath(game), os.path.realpath(pkg)
    if package == root or package.startswith(root + os.sep) or root.startswith(package + os.sep):
        raise Refused("the package and the game must be separate trees")
    for tree in (pkg, game, owner):
        if is_reparse(tree):
            raise Refused("junction/symlink root: %s" % tree)
    if running():
        raise Refused("the game is running")
    if Path(baseline["game_root"]) != Path(game):
        raise Refused("baseline belongs to another game root")
    if baseline.get("rar_sha256") is not None and (not rar.is_file() or sha(rar) != baseline["rar_sha256"]):
        raise Refused("RAR sha256 differs from the baseline value")
    if not baseline.get("archive_rpa_ok"):
        raise Refused("baseline archive.rpa was not the expected archive")
    return installer


def plan(baseline, baseline_dir, game, owner, pkg):
    """Classify every difference; anything not explained is listed under refuse."""
    base = baseline["game"]["files"]
    patch, compiled = patch_files(pkg)
    now, now_dirs = snap(game)
    d = diff(now, base)
    refuse, restore, remove_saves, expect_uninstall, remove_compiled = [], [], [], [], []
    for rel in d["added"]:
        if rel.startswith(RUN_OWNED_PREFIX):
            remove_saves.append(rel)
        elif rel in patch:
            expect_uninstall.append(rel)
        elif rel in compiled:
            remove_compiled.append(rel)                                          # only the .rpyc sibling of an exact installed patch file
        else:
            refuse.append({"file": rel, "why": "added and not run-owned"})
    for rel in d["changed"] + d["removed"]:
        backup = baseline_dir / "game-files" / Path(*rel.split("/"))
        if rel in baseline.get("backup_game_files", []) and backup.is_file() and sha(backup) == base[rel]:
            restore.append(rel)
        else:
            refuse.append({"file": rel, "why": "changed/removed without a sha-verified backup"})
    return {"added": d["added"], "changed": d["changed"], "removed": d["removed"], "restore_from_backup": restore, "remove_run_owned_saves": remove_saves, "remove_compiled_siblings": remove_compiled,
            "removed_by_exact_uninstall": expect_uninstall, "refuse": refuse, "owner_vs_baseline": owner_report(baseline, owner),
            "dirs_added": sorted(set(now_dirs) - set(baseline["game"]["dirs"]))}


def owner_report(baseline, owner):
    files, dirs = snap(owner)
    return {**diff(files, baseline["appdata"]["files"]), "dirs_diff": sorted(set(dirs) ^ set(baseline["appdata"]["dirs"]))}


def default_uninstall(installer, game, pkg):
    env = {k: v for k, v in os.environ.items() if not k.startswith(("DOTNET_", "VNTEXT_", "PYTHON"))}
    r = subprocess.run([str(installer), "--uninstall", str(game), str(pkg)], capture_output=True, text=True, encoding="utf-8", errors="replace", env=env, stdin=subprocess.DEVNULL,
                       timeout=600, cwd=str(pkg))
    return {"exit": r.returncode, "stdout": r.stdout.strip()[-600:], "stderr": r.stderr.strip()[-300:]}


def restore(baseline_dir, game, owner, rar, pkg, installer_sha, execute=False, evidence=EVIDENCE, result_path=RESULT, uninstall=default_uninstall, running=game_running):
    baseline = json.loads((baseline_dir / "before.json").read_text(encoding="utf-8"))
    installer = preconditions(baseline, game, owner, rar, pkg, installer_sha, running)
    if execute and Path(result_path).exists():
        raise Refused("result file exists (never overwritten): %s" % result_path)
    p = plan(baseline, baseline_dir, game, owner, pkg)
    result = {"utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "mode": "EXECUTE" if execute else "DRY_RUN", "installer_sha256": installer_sha, "plan": p}
    if p["refuse"]:
        raise Refused("unexplained differences, nothing changed: " + json.dumps(p["refuse"][:10]))
    if not execute:
        result["note"] = "dry run: no file was written, restored, uninstalled or deleted"
        return result
    evidence = Path(evidence)
    evidence.mkdir(parents=True, exist_ok=True)
    for rel in p["remove_run_owned_saves"] + p["remove_compiled_siblings"]:   # 1 archive run-owned files first
        shutil.copy2(game / Path(*rel.split("/")), evidence / Path(rel).name)
    result["uninstall"] = uninstall(installer, game, pkg)                       # 2 exact installer
    after = plan(baseline, baseline_dir, game, owner, pkg)
    if after["refuse"] or after["removed_by_exact_uninstall"]:
        result["after_uninstall"] = after
        result["final"] = {"game_exact": False}
        Path(result_path).write_text(json.dumps(result, indent=1), encoding="utf-8")
        raise Refused("after the uninstall unexplained or patch files remain; stopped before any other change")
    base = baseline["game"]["files"]
    for rel in after["restore_from_backup"]:                                   # 3 only sha-verified backups
        shutil.copyfile(baseline_dir / "game-files" / Path(*rel.split("/")), game / Path(*rel.split("/")))
    removed = []
    for rel in after["remove_run_owned_saves"]:                                # 4 only run-owned saves
        target = game / Path(*rel.split("/"))
        if target.is_file() and not target.is_symlink():
            target.unlink()
            removed.append(rel)
    for rel in after["remove_compiled_siblings"]:                              # 4b only compiled siblings of the exact installed patch files
        target = game / Path(*rel.split("/"))
        if target.is_file() and not target.is_symlink():
            target.unlink()
            removed.append(rel)
    # 4c only EMPTY directories that this run created and the baseline did not have (saves/, tl/vietnamese, tl), deepest first
    for rel in sorted({"game/saves"} | {d for p_ in patch_files(pkg)[0] for d in parents(p_)}, key=lambda x: -x.count("/")):
        folder = game / Path(*rel.split("/"))
        if rel not in baseline["game"]["dirs"] and folder.is_dir() and not is_reparse(folder) and not any(folder.iterdir()):
            folder.rmdir()
            removed.append(rel + "/ (empty run-created dir)")
    final = verify(baseline, game, owner)                                      # 5 exact readback: game AND Owner files + dirs
    result["restored"] = after["restore_from_backup"]
    result["removed"] = removed
    game_exact = not any(final["game"].values()) and not final["game_dirs_diff"]
    owner_exact = not any(final["owner"].values()) and not final["owner_dirs_diff"]
    result["final"] = {"game_exact": game_exact, "owner_exact": owner_exact, "game": final["game"], "game_dirs_diff": final["game_dirs_diff"], "owner": final["owner"],
                       "owner_dirs_diff": final["owner_dirs_diff"], "note": "Owner AppData is only reported, never written by this tool"}
    Path(result_path).write_text(json.dumps(result, indent=1), encoding="utf-8")
    if not (game_exact and owner_exact):
        raise Refused("final readback is not exact (game_exact=%s owner_exact=%s); see %s" % (game_exact, owner_exact, result_path))
    return result


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("mode", choices=["snapshot", "verify", "restore"])
    ap.add_argument("--baseline-dir", default=str(BASELINE_DIR))
    ap.add_argument("--pkg")
    ap.add_argument("--installer-sha256")
    ap.add_argument("--execute", action="store_true")
    ap.add_argument("--result-path", help="new result file (never overwritten); default: a UTC-stamped file next to postgame-v2-restore-result.json")
    ap.add_argument("--evidence-dir", help="new directory for archived run-owned files; default: a UTC-stamped sibling of postgame-evidence-v2")
    ap.add_argument("--previous-changed-json", default=r"C:\vnrg\run017\postgame-evidence\runtime-hashes.json")
    ap.add_argument("--archive-sha256", default="537aaa6eae5f07c21779ed4fcbd4de309b2cb8aebecee52d7bb44a58a8026c98")
    a = ap.parse_args(argv)
    bdir = Path(a.baseline_dir)
    try:
        if a.mode == "snapshot":
            prev = json.loads(Path(a.previous_changed_json).read_text(encoding="utf-8"))["changed_now"]
            b = snapshot(GAME, OWNER, RAR, bdir, prev, a.archive_sha256)
            print(json.dumps({"game_files": len(b["game"]["files"]), "owner_files": len(b["appdata"]["files"]), "backed_up": len(b["backup_game_files"])}))
            return 0
        baseline = json.loads((bdir / "before.json").read_text(encoding="utf-8"))
        if a.mode == "verify":
            r = verify(baseline, GAME, OWNER)
            print(json.dumps({"exact": r["exact"], "game": {k: len(v) for k, v in r["game"].items()}, "game_dirs_diff": len(r["game_dirs_diff"]), "owner": {k: len(v) for k, v in r["owner"].items()},
                              "owner_dirs_diff": len(r["owner_dirs_diff"])}))
            return 0 if r["exact"] else 1
        stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
        result_path = Path(a.result_path) if a.result_path else RESULT.with_name("postgame-v2-restore-result-%s.json" % stamp)
        evidence = Path(a.evidence_dir) if a.evidence_dir else EVIDENCE.with_name("postgame-evidence-v2-%s" % stamp)
        r = restore(bdir, GAME, OWNER, RAR, Path(a.pkg or ""), a.installer_sha256 or "", execute=a.execute, evidence=evidence, result_path=result_path)
        print(json.dumps({"mode": r["mode"], "refuse": r["plan"]["refuse"], "restore": len(r["plan"]["restore_from_backup"]), "saves": len(r["plan"]["remove_run_owned_saves"]),
                          "compiled_siblings": r["plan"]["remove_compiled_siblings"], "uninstall_expected": r["plan"]["removed_by_exact_uninstall"], "final": r.get("final")}))
        return 0
    except Refused as exc:
        print(json.dumps({"REFUSED": str(exc)}))
        return 2


if __name__ == "__main__":
    sys.exit(main())
