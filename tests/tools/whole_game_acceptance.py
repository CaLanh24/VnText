"""One bounded whole-game acceptance aggregate over EXISTING evidence (no new run, no UI, no game launch, no model).

Chain per key: exhaustive extraction inventory (manifest.json) -> translation.csv -> patch overlay -> read-back.  The overlay is regenerated from
manifest + CSV with the product renderer (vntext.patch_renpy._render_overlay) and must be contained byte-for-byte in the shipped overlay; anything else
in the overlay (extra dialogue block / string pair) is a failure.  Inputs are explicit and fail closed: a missing, unreadable or hash-mismatched input,
an unbound reuse claim or an investigation that does not cover its denominator never becomes a PASS.

Native/runtime evidence is REUSED only through a basis file whose items are bound to component hashes (CSV, overlay) and to hashed evidence files.  The
verdict is ACCEPT_ELIGIBLE only when every required matrix item is statically PROVEN and its runtime and native columns are PROVEN_BOUND or
NOT_REQUIRED (with a verified reason).  Every other value (PENDING_NATIVE, REPORTED_ONLY, MISMATCH, NOTPROVEN, ...) blocks.
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
import zlib
import zipfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from vntext.patch_gate import translation_passes_patch_gate
from vntext.patch_renpy import _render_overlay

SCHEMA = "vntext.whole_game_acceptance/2"
PLACEHOLDER = re.compile(r"\[[^\[\]]+\]|%\([^)]+\)[sd]|%[sd]|\{(?!/?[a-z]+(?:=[^}]*)?\})[^{}]*\}")
TAG = re.compile(r"\{/?[a-z]+(?:=[^}]*)?\}")
OK_RUNTIME = {"PROVEN_BOUND", "PROVEN_BOUND_INFERENCE", "NOT_REQUIRED"}
STATIC_CLASSES = {"COVERED_BY_STATIC_STRINGS", "EXCLUDED_TECHNICAL", "EXCLUDED_USER_DATA", "COVERED_BY_DIALOGUE", "UNREACHABLE_BY_SOURCE"}
NATIVE_CLASSES = {"SHORT_LABEL_REVIEW", "RUNTIME_FORMAT_OBSERVE", "RUNTIME_SPEAKER_OBSERVE", "RUNTIME_LOAD_OBSERVE"}


class InputError(Exception):
    """A required input is missing/unreadable/mismatched: the aggregate must not produce a verdict."""


def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def need(path, what):
    p = Path(path) if path else None
    if p is None or not p.is_file():
        raise InputError("missing input file: %s (%s)" % (what, path))
    return p


def load_json(path, what):
    try:
        return json.loads(need(path, what).read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as exc:
        raise InputError("unreadable JSON %s: %s" % (what, exc)) from exc


def row_invariants(source, translation):
    """Per-row contract checks that need no engine.  Decomposed (NFD) Vietnamese is valid Unicode and is NOT a failure; replacement
    characters, control characters and unencodable text are."""
    bad = []
    s, t = unicodedata.normalize("NFC", source), unicodedata.normalize("NFC", translation)
    if collections.Counter(PLACEHOLDER.findall(s)) != collections.Counter(PLACEHOLDER.findall(t)):
        bad.append("placeholder")
    if collections.Counter(TAG.findall(s)) != collections.Counter(TAG.findall(t)):
        bad.append("tags")
    if source.count("\n") != translation.count("\n"):
        bad.append("newline")
    try:
        translation.encode("utf-8")
        if "�" in translation or any(ord(c) < 32 and c not in "\n\t" for c in translation):
            bad.append("encoding")
    except UnicodeEncodeError:
        bad.append("encoding")
    return bad


def tree_hashes(root, expected):
    """Compare the current file set/hashes under root with the recorded {relative path: sha256}; read-only."""
    root = Path(root)
    if not root.is_dir():
        raise InputError("missing directory: %s" % root)
    current = {p.relative_to(root).as_posix(): p for p in root.rglob("*") if p.is_file()}
    missing = sorted(set(expected) - set(current))
    extra = sorted(set(current) - set(expected))
    changed = sorted(k for k in set(expected) & set(current) if sha(current[k]) != expected[k])
    return {"files": len(expected), "missing": missing, "extra": extra, "changed": changed, "match": not (missing or extra or changed)}


def verify_candidate(setup, route_zip, route_feed, expect_source):
    setup, route_zip, route_feed = need(setup, "candidate Setup"), need(route_zip, "route zip"), need(route_feed, "route feed")
    feed = json.loads(route_feed.read_text(encoding="utf-8-sig"))
    manifest = feed["manifest"] if isinstance(feed.get("manifest"), dict) else json.loads(feed["manifest"])
    problems = []
    if sha(route_zip) != feed.get("package_sha256") or route_zip.name != feed.get("package_file"):
        problems.append("route zip does not match its feed (name/sha)")
    with zipfile.ZipFile(route_zip) as z:
        exe = hashlib.sha256(z.read("VNText Studio.exe")).hexdigest()
        names = [n for n in z.namelist() if n.endswith("VNTextPatchInstaller.exe")]
        installer = hashlib.sha256(z.read(names[0])).hexdigest() if names else None
    if expect_source and not str(manifest.get("source_sha", "")).startswith(expect_source):
        problems.append("feed source_sha %s is not the expected candidate source %s" % (manifest.get("source_sha"), expect_source))
    if manifest.get("version") is None:
        problems.append("feed carries no version")
    return {"setup_sha256": sha(setup), "setup_bytes": setup.stat().st_size, "route_zip_sha256": sha(route_zip), "app_exe_sha256": exe, "patch_installer_sha256": installer,
            "feed_source_sha": manifest.get("source_sha"), "feed_version": manifest.get("version"), "problems": problems, "match": not problems}


def check_chain(manifest, rows, overlay_text, verification):
    entries = manifest["entries"]
    by_key = {}
    dup_inventory = sorted(k for k, n in collections.Counter(e["key"] for e in entries).items() if n > 1)
    for e in entries:
        by_key.setdefault(e["key"], e)
    expected = sorted(k for k, e in by_key.items() if not e.get("review_only") and e.get("safety") == "safe")
    csv_keys = [r["key"] for r in rows]
    readback_pass = [r["key"] for r in verification.get("results", []) if r.get("status") == "PASS"]
    out = {"expected": len(expected), "dup_inventory": dup_inventory,
           "dup_csv": sorted(k for k, n in collections.Counter(csv_keys).items() if n > 1),
           "dup_readback": sorted(k for k, n in collections.Counter(readback_pass).items() if n > 1),
           "missing_csv": sorted(set(expected) - set(csv_keys)), "extra_csv": sorted(set(csv_keys) - set(expected)),
           "missing_readback": sorted(set(csv_keys) - set(readback_pass)), "extra_readback": sorted(set(readback_pass) - set(csv_keys)),
           "readback_status": verification.get("status"), "readback_counts_consistent":
               verification.get("counts", {}).get("PASS") == len(readback_pass) and verification.get("counts", {}).get("FAIL", 0) == sum(r.get("status") != "PASS" for r in verification.get("results", []))}
    translation = {r["key"]: r["translation"] for r in rows}
    invariant, gate, locator = {}, {}, {}
    dialogues, strings = [], {}
    for k in csv_keys:
        e = by_key.get(k)
        if e is None:
            continue
        bad = row_invariants(e["source_text"], translation[k])
        if bad:
            invariant[k] = bad
        ok, reason = translation_passes_patch_gate(e, translation[k], set())
        if not ok:
            gate[k] = reason
        if e["import_method"] == "renpy_dialogue":
            dialogues.append((e, translation[k]))
            locator[k] = "dialogue:" + e["locator"]["native_id"]
        elif e["import_method"] == "renpy_string":
            strings[("vietnamese", e["source_text"])] = translation[k]
            locator[k] = "string:" + hashlib.sha256(e["source_text"].encode()).hexdigest()[:12]
        else:
            locator[k] = "unsupported:" + e["import_method"]
    # emitted order = manifest order for dialogues
    order = {e["key"]: i for i, e in enumerate(entries)}
    dialogues.sort(key=lambda p: order[p[0]["key"]])
    rendered = _render_overlay(dialogues, strings) if dialogues or strings else ""
    contained = bool(rendered) and rendered in overlay_text
    remainder = overlay_text.replace(rendered, "", 1) if contained else overlay_text
    extra_blocks = re.findall(r"^translate vietnamese (?!strings:|style )(\w+):", remainder, re.M) if contained else None
    extra_pairs = len(re.findall(r"^\s+old \"", remainder, re.M)) if contained else None
    wrong_locator = sorted(k for k, v in locator.items() if v.startswith("unsupported:"))
    out.update({"invariant_failures": invariant, "gate_failures": gate, "unsupported_methods": wrong_locator,
                "overlay_regenerated_with_product_renderer": contained, "overlay_extra_dialogue_blocks": extra_blocks, "overlay_extra_string_pairs": extra_pairs,
                "dialogues": len(dialogues), "strings": len(strings), "per_key": locator})
    out["pass"] = (not dup_inventory and not out["dup_csv"] and not out["dup_readback"] and not out["missing_csv"] and not out["extra_csv"]
                   and not out["missing_readback"] and not out["extra_readback"] and verification.get("status") == "PASS" and out["readback_counts_consistent"]
                   and not invariant and not gate and not wrong_locator and contained and not extra_blocks and not extra_pairs)
    return out


def bind_actual(components):
    return {"csv_sha256": components["csv_sha256"], "overlay_sha256": components["overlay_sha256"]}


def evaluate_basis(basis, components):
    """Reuse claims: item -> status.  Only attestation 'receipt' bound to the actual component hashes with hashed evidence files is PROVEN_BOUND."""
    result = {}
    for item in basis.get("items", []):
        status, why = "PROVEN_BOUND", []
        for k, v in (item.get("bind") or {}).items():
            if components.get(k) != v:
                status = "MISMATCH"
                why.append("%s bound to %s but the accepted component is %s" % (k, v, components.get(k)))
        if not item.get("bind"):
            status = "UNBOUND"
            why.append("no component hashes")
        for ev in item.get("evidence", []):
            p = Path(ev["path"])
            if not p.is_file():
                status = "EVIDENCE_MISSING"; why.append("missing " + ev["path"])
            elif sha(p) != ev["sha256"]:
                status = "EVIDENCE_MISMATCH"; why.append("hash differs " + ev["path"])
        if not item.get("evidence"):
            status = "EVIDENCE_MISSING"; why.append("no evidence files")
        if item.get("attestation") != "receipt" and status == "PROVEN_BOUND":
            status = "REPORTED_ONLY"; why.append("attestation is not a machine receipt")
        if item.get("inference") and status == "PROVEN_BOUND":
            # An inference is never direct evidence: it counts only with a named acceptor and a reference to the acceptance, and it stays labelled in the receipt.
            if item.get("accepted_by") and item.get("acceptance_ref"):
                status = "PROVEN_BOUND_INFERENCE"
            else:
                status = "INFERENCE_NOT_ACCEPTED"; why.append("inference without accepted_by / acceptance_ref")
        for cid in item.get("covers", []):
            slot = result.setdefault(cid, {})
            kind = item.get("kind", "native")
            if kind not in slot or slot[kind]["status"] != "PROVEN_BOUND":
                slot[kind] = {"status": status, "item": item["id"], "why": why, "limits": item.get("limits"), "statement": item.get("statement")}
    return result


def strip_tokens(text):
    return re.sub(r"[\W\d_]", "", re.sub(r"\[[^\]]*\]|\{[^}]*\}", "", text))


def unreachable_errors(item):
    """Source-absence proofs recomputed from a scan file (every .rpy archive member read statically): a screen nobody can open is not a visible path."""
    reach = load_json(item.get("reachability"), "reachability scan")
    gallery = reach.get("gallery", {})
    proofs = {
        "gallery_has_no_caller": lambda: len(gallery.get("refs", [])) == 1 and gallery["refs"][0][2].startswith("screen achievement_gallery")
        and "achievement_gallery" not in gallery.get("showmenu_targets", []),
        "popups_disabled": lambda: any("define myconfig.SHOW_ACHIEVEMENT_POPUPS = False" in h[2] for h in reach.get("popup_flag_hits", []))
        and not any(re.search(r"myconfig\.SHOW_ACHIEVEMENT_POPUPS\s*=\s*True", h[2]) for h in reach.get("popup_flag_hits", [])),
    }
    errs = [] if item.get("requires") else ["no requires listed"]
    if gallery.get("rpy_members_scanned", 0) < 1:
        errs.append("scan covers no .rpy member")
    for need in item.get("requires", []):
        if need not in proofs or not proofs[need]():
            errs.append("source-absence proof %r does not hold" % need)
    return errs


def evaluate_investigation(inv, excluded, overlay_text, manifest, dialogue_count):
    """Each excluded coverage group must be fully inspected; every classification is re-checked mechanically where it can be."""
    olds = dict(re.findall(r'^\s+old "((?:[^"\\]|\\.)*)"\n\s+new "((?:[^"\\]|\\.)*)"$', overlay_text, re.M))
    members = collections.defaultdict(set)
    for e in manifest["entries"] + manifest.get("technical_skipped", []):
        c = (e.get("native_contract") or {}).get("provenance", {}).get("source_container") or {}
        if c.get("member_name"):
            members[c["resolved_game_path"] if c.get("resolved_game_path") else c["member_name"]].add(c.get("member_sha256"))
    groups, problems = {}, []
    for g in inv.get("groups", []):
        items = []
        for it in g.get("items", []):
            st, errs = "NOTPROVEN", []
            cl = it.get("classification")
            if it.get("member_sha256") and it.get("file") in members and it["member_sha256"] not in members[it["file"]]:
                errs.append("member hash differs from the inventory provenance")
            if cl == "COVERED_BY_STATIC_STRINGS":
                miss = [s for s in it.get("covered_sources", []) if s not in olds]
                errs += ["not translated in overlay: " + s for s in miss]
                errs += [] if it.get("covered_sources") else ["no covered_sources listed"]
            elif cl == "EXCLUDED_TECHNICAL":
                if strip_tokens(it.get("text", "")):
                    errs.append("technical text still contains letters: " + it.get("text", ""))
            elif cl == "COVERED_BY_DIALOGUE":
                if not dialogue_count:
                    errs.append("no dialogue entries")
            elif cl == "UNREACHABLE_BY_SOURCE":
                errs += unreachable_errors(it)
            elif cl == "EXCLUDED_USER_DATA":
                if not it.get("reason"):
                    errs.append("no reason")
            elif cl not in NATIVE_CLASSES:
                errs.append("unknown classification %r" % cl)
            if not errs:
                st = "STATIC_CLASSIFIED" if cl in STATIC_CLASSES else "NATIVE_OBSERVATION_REQUIRED"
            items.append({"id": it.get("id"), "file": it.get("file"), "line": it.get("line"), "classification": cl, "status": st, "errors": errs, "native": it.get("native"),
                          "observation": it.get("observation")})
        want = next((x["count"] for x in excluded if x["code"] == g.get("code")), None)
        if want is None or want != len(items):
            problems.append("group %s: investigation covers %d of %s" % (g.get("code"), len(items), want))
        groups[g.get("code")] = items
    for x in excluded:
        if x["code"] not in groups:
            problems.append("excluded group %s has no investigation" % x["code"])
    return groups, problems


def cache_load_evidence(spec):
    """Compiled-cache presence (zlib, no unpickle, no execution): evidence that the loader compiled the member, NOT that it ran."""
    out = []
    for item in spec:
        p = need(item["path"], "cache evidence")
        raw = p.read_bytes()
        try:
            data = zlib.decompress(raw)
        except zlib.error:
            data = raw
        found = {n: n.encode() in data for n in item["names"]}
        out.append({"path": str(p), "sha256": sha(p), "contains": found, "all_present": all(found.values())})
    return out


def representative_cases(rows, entries_by_key):
    """Finite visual sample per WORKFLOW (font/wrap/long/short/special characters/decomposed text), derived from the CSV itself."""
    dlg = [(r, entries_by_key[r["key"]]) for r in rows if entries_by_key.get(r["key"], {}).get("import_method") == "renpy_dialogue"]
    picks = {}
    if dlg:
        picks["longest_dialogue"] = max(dlg, key=lambda p: len(p[0]["translation"]))[0]["key"]
        picks["shortest_dialogue"] = min(dlg, key=lambda p: len(p[0]["translation"]))[0]["key"]
    for name, pred in (("tagged_or_placeholder", lambda t: bool(TAG.search(t) or PLACEHOLDER.search(t))), ("explicit_newline", lambda t: "\n" in t),
                       ("decomposed_vietnamese_nfd", lambda t: unicodedata.normalize("NFC", t) != t),
                       ("ellipsis_or_special_punctuation", lambda t: any(c in t for c in "…—“”‘’"))):
        for r, _ in dlg:
            if pred(r["translation"]):
                picks[name] = r["key"]
                break
    return picks


def build(args):
    package = Path(args.package)
    manifest = load_json(package / "manifest.json", "manifest")
    csv_path = need(package / "translation.csv", "translation.csv")
    with csv_path.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    patch = Path(args.patch)
    verification = load_json(patch / "patch_verification.json", "patch_verification")
    coverage = load_json(patch / "patch_coverage.json", "patch_coverage")
    overlay_path = need(patch / "COPY_TO_GAME_ROOT/game/tl/vietnamese/vntext.rpy", "overlay")
    overlay_text = overlay_path.read_text(encoding="utf-8")
    before_path = need(args.game_before, "pre-game before.json")
    before = load_json(before_path, "before.json")
    basis = load_json(args.basis, "native basis")
    inv = load_json(args.investigation, "coverage investigation")
    flow = load_json(args.story_flow, "story flow census")
    audit = load_json(args.script_audit, "script audit census")
    stats = manifest.get("stats", {})
    by_key = {e["key"]: e for e in manifest["entries"]}
    components = {"csv_sha256": sha(csv_path), "overlay_sha256": sha(overlay_path), "manifest_sha256": sha(package / "manifest.json")}

    chain = check_chain(manifest, rows, overlay_text, verification)
    game = tree_hashes(args.game_root, before["game"]["files"])
    owner = tree_hashes(args.owner_root, before["appdata"]["files"])
    history = None
    if args.historical_before:
        old = load_json(args.historical_before, "historical before.json")
        old_state = tree_hashes(args.owner_root, old["appdata"]["files"])
        history = {"historical_before_sha256": sha(args.historical_before), "differs_from_current": not old_state["match"], "missing": len(old_state["missing"]), "changed": old_state["changed"],
                   "extra": old_state["extra"]}
        if not old_state["match"]:
            gap = load_json(args.owner_gap, "owner historical gap record (required when the historical snapshot differs)")
            history["gap_status"] = gap.get("status")
            owner_resolved = gap.get("status") == "RESOLVED_BY_OWNER" and bool(gap.get("owner_decision"))
            # A bounded Root review of the CURRENT task data against the current baseline: both snapshots stay, the historical cause stays UNKNOWN and visible, and it is never
            # recorded as an Owner approval.  It must name the exact baseline and historical snapshot files it reviewed.
            root_reviewed = (gap.get("status") == "ROOT_REVIEWED_CURRENT_TASK" and gap.get("reviewed_by") == "Root" and bool(gap.get("review_ref"))
                             and gap.get("current_baseline_sha256") == sha(args.game_before) and gap.get("historical_snapshot_sha256") == sha(args.historical_before)
                             and gap.get("historical_cause") == "UNKNOWN")
            history["gap_resolved"] = owner_resolved or root_reviewed
            history["disposition"] = "OWNER_RESOLVED" if owner_resolved else "ROOT_REVIEWED_CURRENT_TASK_ONLY" if root_reviewed else "OPEN"
            history["gap_record_sha256"] = sha(args.owner_gap)
    candidate = verify_candidate(args.candidate_setup, args.route_zip, args.route_feed, args.candidate_source)
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    excluded = [{"code": x["code"], "count": x["count"], "reason": x["message"]} for x in coverage.get("excluded_coverage", [])]
    dialogue_count = sum(e["import_method"] == "renpy_dialogue" for e in manifest["entries"])
    groups, inv_problems = evaluate_investigation(inv, excluded, overlay_text, manifest, dialogue_count)
    basis_status = evaluate_basis(basis, components)
    cache = cache_load_evidence(inv.get("cache_evidence", []))
    cases = representative_cases(rows, by_key)

    items = []

    def add(item_id, kind, static, count, note, native_key=None, native_required=True):
        slot = basis_status.get(native_key or item_id, {})
        default = "PENDING_NATIVE" if native_required else "NOT_REQUIRED"
        nat = slot.get("native")
        rt = slot.get("runtime") or nat          # a native observation is also runtime evidence
        items.append({"id": item_id, "kind": kind, "required": True, "static": static, "runtime": rt["status"] if rt else default, "native": nat["status"] if nat else default,
                      "count": count, "note": note, "basis": (nat or rt or {}).get("item"), "basis_limits": (nat or rt or {}).get("limits")})

    flow_ok = (flow.get("say_lines") == dialogue_count and audit.get("totals", {}).get("menu_choice") == 0 and audit.get("menu_choices") == []
               and audit.get("entry_labels") == ["start"] and audit.get("reachable") == 1 and audit.get("say_in_unreachable") == [])
    add("text.dialogue", "scene/label", "PROVEN" if chain["pass"] and chain["dialogues"] == dialogue_count else "FAIL", chain["dialogues"],
        "per-key inventory->CSV->overlay->readback over every dialogue entry", native_key="story.route")
    add("text.ui_strings", "ui/settings/language", "PROVEN" if chain["pass"] else "FAIL", chain["strings"], "per-key chain over every patched UI string", native_key="ui.menus")
    add("flow.branches", "branch/choice", "PROVEN" if flow_ok else "FAIL", 0 if flow_ok else None,
        "census: %d reachable label(s), entry %s, menu choices %s, unreachable %s; flow census says %s" % (audit.get("reachable"), audit.get("entry_labels"), audit.get("totals", {}).get("menu_choice"),
                                                                                                         audit.get("unreachable_labels"), flow.get("branching")), native_key="story.route")
    add("flow.ending", "ending", "PROVEN" if flow_ok and flow.get("end_line") else "FAIL", 1, "single linear route, final return at line %s" % flow.get("end_line"), native_key="story.ending")
    add("ui.save_load", "save/load", "PROVEN" if chain["pass"] else "FAIL", None, "Load/Save strings patched and read back", native_key="ui.save_load")
    add("ui.history_settings_language", "history/settings/language", "PROVEN" if chain["pass"] else "FAIL", None, "History/Preferences strings patched and read back", native_key="ui.menus")
    add("font.glyph", "glyph", "CHARSET_LISTED", len({c for r in rows for c in r["translation"] if ord(c) > 127}),
        "non-ASCII characters used: %s" % "".join(sorted({c for r in rows for c in r["translation"] if ord(c) > 127})), native_key="font.glyph")
    for name, key in cases.items():
        add("representative." + name, "visual-sample", "PROVEN" if chain["pass"] else "FAIL", 1, "key %s" % key, native_key="representative." + name)
    for code, its in groups.items():
        for it in its:
            required_native = it["status"] == "NATIVE_OBSERVATION_REQUIRED"
            add("%s:%s" % (code, it["id"]), "residual-coverage", it["status"] if not it["errors"] else "FAIL", 1,
                "%s %s:%s %s" % (it["classification"], it["file"], it["line"], it.get("observation") or "; ".join(it["errors"])), native_key="residual." + str(it["id"]),
                native_required=required_native)
    blocking = []
    for it in items:
        if it["static"] not in ("PROVEN", "STATIC_CLASSIFIED", "NATIVE_OBSERVATION_REQUIRED", "CHARSET_LISTED"):
            blocking.append({"id": it["id"], "why": "static=" + str(it["static"])})
        for col in ("runtime", "native"):
            if it[col] not in OK_RUNTIME:
                blocking.append({"id": it["id"], "why": "%s=%s" % (col, it[col])})
    if history and history["differs_from_current"] and not history["gap_resolved"]:
        blocking.append({"id": "gate.owner_history", "why": "Owner AppData differs from the historical snapshot (%d missing); gap status %s - needs Owner/Root resolution, never restored or attributed here" % (history["missing"], history["gap_status"])})
    for name, ok, why in (("chain", chain["pass"], "per-key chain failed"), ("game_hashes", game["match"], "original game differs from the recorded hashes"),
                          ("owner_hashes", owner["match"], "Owner AppData differs from the recorded hashes"), ("candidate", candidate["match"], "; ".join(candidate["problems"])),
                          ("investigation", not inv_problems, "; ".join(inv_problems))):
        if not ok:
            blocking.append({"id": "gate." + name, "why": why})
    for c in cache:
        if not c["all_present"]:
            blocking.append({"id": "cache." + c["path"], "why": "compiled cache lacks a listed member"})
    for cid, kinds in basis_status.items():
        for kind, b in kinds.items():
            if b["status"] not in ("PROVEN_BOUND", "PROVEN_BOUND_INFERENCE"):
                blocking.append({"id": "basis.%s.%s" % (cid, kind), "why": "%s: %s" % (b["status"], "; ".join(b["why"]))})
    return {
        "schema": SCHEMA,
        "source_head": head,
        "candidate": candidate,
        "components": components,
        "game": {"root": before.get("game_root"), "recorded_files": game["files"], "current": {k: game[k] for k in ("missing", "extra", "changed", "match")}, "before_receipt_sha256": sha(before_path),
                 "archive_rpa_sha256": before["game"]["files"].get("game/archive.rpa") or next((v for k, v in before["game"]["files"].items() if k.lower().endswith("archive.rpa")), None)},
        "userdata": {"recorded_files": owner["files"], "current": {k: owner[k] for k in ("missing", "extra", "changed", "match")}, "historical": history},
        "inputs": {"manifest": str(package / "manifest.json"), "csv": str(csv_path), "overlay": str(overlay_path), "readback_sha256": sha(patch / "patch_verification.json"),
                   "coverage_sha256": sha(patch / "patch_coverage.json"), "basis_sha256": sha(args.basis), "investigation_sha256": sha(args.investigation),
                   "story_flow_sha256": sha(args.story_flow), "script_audit_sha256": sha(args.script_audit)},
        "chain": chain,
        "counts": {"inventory_entries": len(manifest["entries"]), "native_units": stats.get("native_units"), "csv_rows": len(rows), "achieved": len(chain["per_key"]) if chain["pass"] else 0,
                   "missing": len(chain["missing_csv"]) + len(chain["missing_readback"]), "duplicate": len(chain["dup_inventory"]) + len(chain["dup_csv"]) + len(chain["dup_readback"]),
                   "skipped_technical": len(manifest.get("technical_skipped", [])), "excluded_review_only": stats.get("native_string_ledger_counts", {}).get("review_only"),
                   "blocked_excluded_groups": excluded, "invariant_failures": len(chain["invariant_failures"]), "gate_failures": len(chain["gate_failures"])},
        "investigation": {"groups": groups, "problems": inv_problems, "compiled_cache": cache},
        "basis": basis_status,
        "matrix": items,
        "representative_cases": cases,
        "visible_gaps": ([] if not history or not history["differs_from_current"] else
                         ["Owner AppData differs from the historical snapshot (%d files missing); cause UNKNOWN; disposition %s" % (history["missing"], history.get("disposition"))]),
        "blocking": blocking,
        "residual_checklist": sorted({b["id"] for b in blocking}),
        "verdict": "ACCEPT_ELIGIBLE" if not blocking else "NOT_ACCEPTED",
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("package", "patch", "game-before", "game-root", "owner-root", "candidate-setup", "route-zip", "route-feed", "basis", "investigation", "story-flow", "script-audit", "output"):
        parser.add_argument("--" + name, required=True)
    parser.add_argument("--historical-before", default="", help="older before.json whose Owner AppData snapshot is kept as immutable history; a difference needs --owner-gap")
    parser.add_argument("--owner-gap", default="", help="gap record JSON {status, owner_decision}; only RESOLVED_BY_OWNER with a decision clears the history gate")
    parser.add_argument("--candidate-source", default="", help="expected candidate source SHA (prefix ok); the feed's source_sha must match")
    args = parser.parse_args(argv)
    args = argparse.Namespace(**{k.replace("-", "_"): v for k, v in vars(args).items()})
    try:
        receipt = build(args)
    except InputError as exc:
        print(json.dumps({"verdict": "INPUT_ERROR", "error": str(exc)}, ensure_ascii=False))
        return 2
    Path(args.output).write_text(json.dumps(receipt, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({"verdict": receipt["verdict"], "chain": receipt["chain"]["pass"], "counts": {k: v for k, v in receipt["counts"].items() if k != "blocked_excluded_groups"},
                      "blocking": len(receipt["blocking"])}, ensure_ascii=False))
    return 0 if receipt["chain"]["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
