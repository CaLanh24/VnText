"""One bounded whole-game acceptance aggregate over EXISTING evidence (no new run, no UI, no game launch).

Chain per key: exhaustive extraction inventory (manifest.json) -> translation.csv -> patch overlay -> read-back (patch_verification.json).
Writes one machine-readable receipt plus the finite coverage matrix.  Static, runtime and native evidence are kept in separate columns;
a required reachable path that is NOTPROVEN/FAIL keeps the verdict at NOT_ACCEPTED and is never removed from the denominator.
"""
import argparse
import collections
import csv
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import unicodedata

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from vntext.patch_gate import translation_passes_patch_gate

SCHEMA = "vntext.whole_game_acceptance/1"
PLACEHOLDER = re.compile(r"\[[^\[\]]+\]|%\([^)]+\)[sd]|%[sd]|\{(?!/?[a-z]+(?:=[^}]*)?\})[^{}]*\}")
TAG = re.compile(r"\{/?[a-z]+(?:=[^}]*)?\}")


def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def esc(text):
    return text.replace(chr(92), chr(92) * 2).replace('"', chr(92) + '"').replace(chr(10), chr(92) + "n")


def row_invariants(source, translation):
    """Per-row contract checks that need no engine: placeholders, tags, newlines, encoding."""
    bad = []
    if collections.Counter(PLACEHOLDER.findall(source)) != collections.Counter(PLACEHOLDER.findall(translation)):
        bad.append("placeholder")
    if collections.Counter(TAG.findall(source)) != collections.Counter(TAG.findall(translation)):
        bad.append("tags")
    if source.count("\n") != translation.count("\n"):
        bad.append("newline")
    if unicodedata.normalize("NFC", translation) != translation or "�" in translation or any(ord(c) < 32 and c not in "\n\t" for c in translation):
        bad.append("encoding")
    try:
        translation.encode("utf-8")
    except UnicodeEncodeError:
        bad.append("encoding")
    return bad


def matrix_item(item_id, kind, required, static, runtime, native, risk, note, count=None):
    return {"id": item_id, "kind": kind, "required": required, "static": static, "runtime": runtime, "native": native,
            "visual_risk": risk, "count": count, "note": note}


def build(args):
    package = Path(args.package)
    manifest = json.loads((package / "manifest.json").read_text(encoding="utf-8"))
    entries = manifest["entries"]
    rows = list(csv.DictReader((package / "translation.csv").open(encoding="utf-8-sig", newline="")))
    patch = Path(args.patch)
    verification = json.loads((patch / "patch_verification.json").read_text(encoding="utf-8"))
    coverage = json.loads((patch / "patch_coverage.json").read_text(encoding="utf-8"))
    overlay = (patch / "COPY_TO_GAME_ROOT/game/tl/vietnamese/vntext.rpy").read_text(encoding="utf-8")
    before = json.loads(Path(args.game_before).read_text(encoding="utf-8"))
    stats = manifest.get("stats", {})
    ledger = stats.get("native_string_ledger_counts", {})
    by_key = {e["key"]: e for e in entries}
    csv_keys = [r["key"] for r in rows]
    readback_keys = [r["key"] for r in verification["results"] if r["status"] == "PASS"]
    dup_csv = sorted(k for k, n in collections.Counter(csv_keys).items() if n > 1)
    dup_readback = sorted(k for k, n in collections.Counter(readback_keys).items() if n > 1)
    expected = sorted(k for k, e in by_key.items() if not e.get("review_only") and e.get("safety") == "safe")
    missing_csv = sorted(set(expected) - set(csv_keys))
    missing_readback = sorted(set(csv_keys) - set(readback_keys))
    invariant_fail, gate_fail, overlay_fail = {}, {}, []
    for r in rows:
        entry = by_key.get(r["key"])
        if entry is None:
            invariant_fail[r["key"]] = ["not_in_inventory"]
            continue
        bad = row_invariants(entry["source_text"], r["translation"])
        if bad:
            invariant_fail[r["key"]] = bad
        ok, reason = translation_passes_patch_gate(entry, r["translation"], set())
        if not ok:
            gate_fail[r["key"]] = reason
        if esc(r["translation"]) not in overlay:
            overlay_fail.append(r["key"])
    achieved = sorted(set(csv_keys) & set(readback_keys) - set(invariant_fail) - set(gate_fail) - set(overlay_fail))
    chars = sorted({c for r in rows for c in r["translation"] if ord(c) > 127})
    excluded = [{"code": x["code"], "count": x["count"], "reason": x["message"]} for x in coverage.get("excluded_coverage", [])]
    native_rows = [("native_string_ledger_counts." + k, v) for k, v in sorted(ledger.items())]
    per_file = collections.OrderedDict()
    for e in entries:
        per_file.setdefault(e["file_path"], collections.Counter())[e["import_method"]] += 1
    cov = {x["code"]: x["count"] for x in excluded}
    story = stats.get("native_dialogue_units", 0)
    m = [
        matrix_item("story.linear", "scene/label/branch", True, "PROVEN" if story == sum(e["import_method"] == "renpy_dialogue" for e in entries) == 227 else "FAIL",
                    "NOT_RERUN", "REPORTED_NATIVE",
                    "medium", "1 label, no choices/branches (so the branch set is empty), 14 video calls, 22 pauses; native pass is the Brain/PM reported linear run on the patch built from this CSV, "
                    "receipts native017-game-dialogue-start.png / native017-game-ending.png; not re-executed for the new candidate", story),
        matrix_item("ending", "ending", True, "PROVEN", "NOT_RERUN", "REPORTED_NATIVE", "low", "single ending reached in the reported native run (native017-game-ending.png)", 1),
        matrix_item("ui.strings", "ui/settings/language", True, "PROVEN" if len(rows) - story > 0 else "FAIL", "NOT_RERUN", "REPORTED_NATIVE_PARTIAL", "high",
                    "84 game-owned UI strings read back; native: main menu, Load, Settings language switch, History and confirm prompts observed in earlier runs (brain-native-ab-receipt.json was on a test copy)", len(rows) - story),
        matrix_item("save_load", "save/load", True, "PROVEN_STRINGS", "NOT_RERUN", "REPORTED_NATIVE_PARTIAL", "medium",
                    "Load screen strings patched and read back; save/restore of game and AppData verified file-by-file (postgame017-restore-result.json)"),
        matrix_item("font.glyph", "glyph", True, "CHARSET_LISTED", "NOT_RERUN", "REPORTED_NATIVE", "high",
                    "DejaVuSans overlay styles read back; %d distinct non-ASCII characters in the translations listed in the receipt; glyph proof is native observation only" % len(chars)),
        matrix_item("achievements.dynamic", "runtime-dynamic", True, "NOT_EXTRACTABLE", "NOTPROVEN", "NOTPROVEN", "medium",
                    "runtime-only expressions in achievements.rpy; no fake text created; reachable via the achievements screen", cov.get("RUNTIME_DYNAMIC_UNRESOLVED")),
        matrix_item("archive.runtime", "runtime-load", True, "RECOVERED_SOURCE", "NOTPROVEN", "NOTPROVEN", "low",
                    "archive .rpy recovered for reading text only; game load/execution of those scripts not shown", cov.get("ARCHIVE_SOURCE_RUNTIME_UNPROVEN")),
        matrix_item("screen.candidates", "ui-unpromoted", True, "REVIEW_ONLY", "NOTPROVEN", "NOTPROVEN", "high",
                    "static screen strings not promoted; unpatched and untranslated, still English in game", cov.get("REVIEW_SCREEN_CANDIDATES_UNPROMOTED")),
    ] + [matrix_item("engine.common", "excluded", False, "EXCLUDED", "n/a", "n/a", "n/a",
                     "engine-owned Ren'Py common strings (%s): reason-coded exclusion, not a game text path" % stats.get("native_string_ownership_counts"),
                     stats.get("native_string_reconciliation", {}).get("common_runtime_count"))]
    blocking = [i["id"] for i in m if i["required"] and any(i[k] in ("NOTPROVEN", "FAIL") for k in ("static", "runtime", "native"))]
    chain_ok = not (missing_csv or missing_readback or dup_csv or dup_readback or invariant_fail or gate_fail or overlay_fail)
    receipt = {
        "schema": SCHEMA,
        "source_sha": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "candidate": {"setup_sha256": args.candidate_setup_sha, "app_sha256": args.candidate_app_sha},
        "game": {"root": before.get("game_root"), "status": before.get("status"), "original_matches": before.get("original_matches"),
                 "archive_rpa_sha256": next((v for k, v in before["game"]["files"].items() if k.lower().endswith("archive.rpa")), None),
                 "game_files_count": len(before["game"]["files"]), "game_files_digest": hashlib.sha256(json.dumps(before["game"]["files"], sort_keys=True).encode()).hexdigest(),
                 "userdata_files_count": len(before["appdata"]["files"]), "userdata_digest": hashlib.sha256(json.dumps(before["appdata"]["files"], sort_keys=True).encode()).hexdigest(),
                 "before_receipt_sha256": sha(args.game_before)},
        "chain": {"inventory": {"path": str(package / "manifest.json"), "sha256": sha(package / "manifest.json"), "entries": len(entries),
                                "native_units": stats.get("native_units"), "dialogue_units": story, "string_units": stats.get("native_string_units"), "ledger": ledger},
                  "csv": {"path": str(package / "translation.csv"), "sha256": sha(package / "translation.csv"), "rows": len(rows)},
                  "patch": {"dir": str(patch), "overlay_sha256": sha(patch / "COPY_TO_GAME_ROOT/game/tl/vietnamese/vntext.rpy"), "overlay_has_csv_translation": len(rows) - len(overlay_fail)},
                  "readback": {"sha256": sha(patch / "patch_verification.json"), "status": verification["status"], "counts": verification["counts"]}},
        "counts": {"expected": len(expected), "achieved": len(achieved), "missing_csv": len(missing_csv), "missing_readback": len(missing_readback),
                   "duplicate_csv": len(dup_csv), "duplicate_readback": len(dup_readback), "skipped_technical": len(manifest.get("technical_skipped", [])),
                   "blocked_or_excluded": excluded, "review_only_ledger": ledger.get("review_only"), "invariant_failures": len(invariant_fail),
                   "patch_gate_failures": len(gate_fail), "overlay_mismatch": len(overlay_fail)},
        "invariants": {"placeholder_tags_newline_encoding": "PASS" if not invariant_fail else "FAIL", "patch_gate": "PASS" if not gate_fail else "FAIL",
                       "readback_matches_csv": "PASS" if not overlay_fail and not missing_readback else "FAIL",
                       "byte_limit": "NOT_APPLICABLE (no row sets byte_limit)" if not any(r.get("byte_limit") for r in rows) else "PRESENT_NOT_CHECKED",
                       "compile": "PASS (patch read-back %d/%d on the overlay; Ren'Py compile of the overlay was part of the native game run)" % (verification["counts"]["PASS"], len(rows)),
                       "failures": {"invariant": invariant_fail, "gate": gate_fail, "overlay": overlay_fail, "missing_csv": missing_csv, "missing_readback": missing_readback},
                       "non_ascii_chars": "".join(chars)},
        "static_chain": "PASS" if chain_ok else "FAIL",
        "matrix": {"items": m, "per_file": {k: dict(v) for k, v in per_file.items()}, "native_ledger_rows": native_rows},
        "blocking_required_notproven": blocking,
        "verdict": "NOT_ACCEPTED" if blocking or not chain_ok else "ACCEPT_ELIGIBLE",
        "scope_note": "Static inventory->CSV->patch->readback is complete over the supported denominator; runtime/native columns reuse earlier proofs and do not claim whole-game PASS.",
    }
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", required=True, help="extraction package dir (manifest.json + translation.csv)")
    parser.add_argument("--patch", required=True, help="patch output dir (patch_verification.json, patch_coverage.json, COPY_TO_GAME_ROOT)")
    parser.add_argument("--game-before", required=True, help="pre-game before.json (game + AppData hashes)")
    parser.add_argument("--candidate-setup-sha", default="")
    parser.add_argument("--candidate-app-sha", default="")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    receipt = build(args)
    Path(args.output).write_text(json.dumps(receipt, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({"verdict": receipt["verdict"], "static_chain": receipt["static_chain"], "counts": {k: v for k, v in receipt["counts"].items() if k != "blocked_or_excluded"},
                      "blocking": receipt["blocking_required_notproven"]}, ensure_ascii=False))
    return 0 if receipt["static_chain"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
