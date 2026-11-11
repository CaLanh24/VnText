"""Unity patch planning only; no filesystem writes or eligibility changes."""
from vntext.patch_constants import patch_skip_reason

def group_patch_entries(entries, translations, review_keys, whitelist, *, allow_ct2_junk=False):
    gate_skipped = 0
    report = []
    by_file: dict[str, list[tuple[dict, str]]] = {}
    for entry in entries:
        key = entry.get("key")
        if key not in translations:
            continue
        if key in review_keys:
            gate_skipped += 1
            continue
        trans = translations[key]["translation"]
        reason = patch_skip_reason(entry, trans, whitelist, allow_ct2_junk=allow_ct2_junk)
        if reason:
            gate_skipped += 1
            report.append(f"SKIP key {key}: {reason}")
            continue
        rel = str(entry.get("file_path", "") or "").replace("\\", "/")
        while "//" in rel:
            rel = rel.replace("//", "/")
        # Keep Windows-style for game tree; collapse accidental doubled separators.
        rel = rel.replace("/", "\\")
        by_file.setdefault(rel, []).append((entry, trans))

    return by_file, gate_skipped, report
