"""Conservative human disposition of the saved 120 observations; not a runtime allowlist.

No decision here is consumed by translation, QA or Patch Gate. CSV is read-only.
Lexical/non-English/debug text needs correction or visibility triage, never auto-keep.
"""
import argparse
import collections
import csv
import json
import mmap
import os
from pathlib import Path
import re
import sys
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "tests/lib")]
from vntext import mt_check
from vntext.intentional_keep import intentional_keep_reason
from vntext.mt_check import structural_problems
from vntext.mt_strategies import candidate_quality_issues
from vntext.patch_gate import translation_passes_patch_gate
from vntext.mt_classify import is_star_sfx_line
from vntext.package_io import CSV_FIELDS, read_csv_rows_file, write_csv_rows_file
from work_paths import assert_artifact_under_work, resolve_game_folder
from verify_completed_package import digest

# Reviewed non-lexical sound spellings, not prose describing a sound.
SOUNDS = {
    '*HE HE HE*', '*phew*', '*KNOCK KNOCK*', '*Honk Honk*', '*Yum*', '*chup*',
    '*chup* *chup*', '*knock knock*', '*HE HE HE*.', '*chu-*',
    '*GAK* *GAK* *GAK* *GAK*...',
    '<color=cyan>* nee-nah nee-nah nee-nah *</color>',
}
OPAQUE_SOUNDS = {
    'HA HA HA HA HA HA HA HA HA HA HA HA...!', 'LA LA LA-!', 'LA LA LA...',
    'OINK OINK OINK! OINK!!', '<color=cyan>BANG! BANG! BANG!</color>',
}


def _identity_source_index(rows):
    """Read-only Unity source index keyed by the CSV locator.

    The index is evidence only.  It never supplies a translation or changes a
    game asset.  Exact source-byte hits are recorded so a keep/triage
    decision is tied to an object and byte offset rather than a classifier
    label alone.
    """
    by_file = {}
    rows_by_file = collections.defaultdict(list)
    for row in rows:
        rel = str(row.get("file_path") or "").replace("\\", "/")
        if rel:
            rows_by_file[rel].append(row)
    for rel, file_rows in rows_by_file.items():
        if rel in by_file:
            continue
        path = resolve_game_folder() / Path(rel)
        if not path.is_file():
            by_file[rel] = {"path": str(path), "error": "missing source asset"}
            continue
        try:
            source_hits = {}
            with path.open("rb") as stream, mmap.mmap(
                stream.fileno(), 0, access=mmap.ACCESS_READ
            ) as raw:
                for source in {
                    str(row.get("source_text") or "").strip() for row in file_rows
                }:
                    needle = source.encode("utf-8")
                    offsets = []
                    start = 0
                    while needle:
                        offset = raw.find(needle, start)
                        if offset < 0:
                            break
                        offsets.append(offset)
                        start = offset + max(1, len(needle))
                    source_hits[source] = offsets
            by_file[rel] = {
                "path": str(path),
                "sha256": digest(path),
                "source_hits": source_hits,
            }
        except Exception as exc:
            by_file[rel] = {"path": str(path), "error": str(exc)}
    return by_file


def _row_source_proof(row, source_index):
    rel = str(row.get("file_path") or "").replace("\\", "/")
    source = str(row.get("source_text") or "").strip()
    info = source_index.get(rel) or {"error": "source asset not indexed"}
    object_info = str(row.get("object_info") or "")
    pid_match = re.search(r"(?:MonoBehaviour|Text):(-?\d+)", object_info)
    if not pid_match:
        pid_match = re.search(r"NaninovelScript:(-?\d+)", str(row.get("context") or ""))
    pid = pid_match.group(1) if pid_match else ""
    offsets = list((info.get("source_hits") or {}).get(source) or [])
    hits = [{"offset": offset, "text": source} for offset in offsets]
    return {
        "file_path": rel,
        "asset_sha256": info.get("sha256", ""),
        "object_info": object_info,
        "path_id": pid,
        "source_present_in_object": bool(hits),
        "exact_aligned_hits": hits,
        "locator_context": str(row.get("context") or ""),
        "import_method": str(row.get("import_method") or ""),
        "proof_basis": (
            "exact UTF-8 source bytes in the recorded Unity asset; object/path locator is retained from CSV"
            if hits
            else "recorded CSV object/path locator plus immutable asset hash; runtime marker may be compressed or fragmented"
        ),
        "scan_error": info.get("scan_error", info.get("error", "")),
    }


def _manifest_source_proof(row, manifest_index):
    entry = manifest_index.get(str(row.get("key") or "")) or {}
    fields_match = all(
        str(entry.get(field) or "") == str(row.get(field) or "")
        for field in ("source_text", "file_path", "context", "object_info", "import_method")
    )
    return {
        "manifest_match": bool(entry and fields_match),
        "manifest_locator": entry.get("locator") or {},
        "manifest_backend": entry.get("backend", ""),
    }


def _candidate_model_dir():
    configured = os.environ.get("VNTEXT_CT2_MODEL", "").strip()
    if configured:
        return Path(configured)
    return Path(__file__).resolve().parents[2] / "tests" / "golden" / "_work" / "models" / "opus-mt-en-vi-int8"


def _translate_lexical_candidates(rows, candidate_dir):
    """Run real CT2 only on the 32 reviewed lexical rows in a work copy."""
    from vntext.mt_ct2_pipeline import run_ct2_translate_keys

    candidate_dir = assert_artifact_under_work(candidate_dir, "identity CT2 candidates")
    candidate_dir.mkdir(parents=True, exist_ok=True)
    csv_path = candidate_dir / "translation.csv"
    candidate_rows = []
    for row in rows:
        value = {field: str(row.get(field) or "") for field in CSV_FIELDS}
        value["translation"] = ""
        candidate_rows.append(value)
    write_csv_rows_file(csv_path, CSV_FIELDS, candidate_rows)
    old_vh = os.environ.pop("VNTEXT_VH_DATA", None)
    try:
        result = run_ct2_translate_keys(
            csv_path,
            [row["key"] for row in candidate_rows],
            model_dir=_candidate_model_dir(),
            allow_overwrite=True,
            backup=False,
        )
    finally:
        if old_vh is not None:
            os.environ["VNTEXT_VH_DATA"] = old_vh
    if int(result.get("applied") or 0) != len(rows) or int(result.get("blocked") or 0):
        raise RuntimeError(f"CT2 lexical candidate run did not complete: {result}")
    _, translated = read_csv_rows_file(csv_path)
    whitelist = mt_check.load_whitelist(candidate_dir)
    by_key = {row["key"]: row for row in translated}
    candidate_records = {}
    for row in rows:
        candidate = by_key.get(row["key"], {}).get("translation", "")
        quality = candidate_quality_issues(row, candidate, whitelist)
        structural = structural_problems(row, candidate)
        gate_ok, gate_reason = translation_passes_patch_gate(row, candidate, whitelist)
        if not candidate.strip():
            raise RuntimeError(f"CT2 candidate is still identity: {row['key']}")
        if candidate.strip() == row["source_text"].strip():
            _score, english_reasons = mt_check.english_report(
                row["source_text"], candidate, whitelist
            )
            # An opaque, non-lexical sound spelling has no truthful Vietnamese
            # equivalent.  Keep it only when the language check has no English
            # token signal; lexical star spans must still receive a candidate.
            if is_star_sfx_line(row["source_text"]) and not any(
                reason.startswith(("english-token", "english-weak"))
                for reason in english_reasons
            ):
                candidate_records[row["key"]] = {
                    "translation": candidate,
                    "quality_issues": quality,
                    "structural_problems": structural,
                    "patch_gate": "PASS_LITERAL_NONLEXICAL_SFX",
                    "identity_allowed": True,
                }
                continue
            raise RuntimeError(f"CT2 candidate is still identity: {row['key']}")
        if quality or structural or not gate_ok:
            raise RuntimeError(
                f"CT2 candidate failed validation for {row['key']}: "
                f"quality={quality} structural={structural} gate={gate_reason}"
            )
        candidate_records[row["key"]] = {
            "translation": candidate,
            "quality_issues": quality,
            "structural_problems": structural,
            "patch_gate": "PASS",
        }
    return {
        "result": {**result, "copied_vi": 0, "vh_oracle_used": False},
        "csv_sha256": digest(csv_path),
        "rows": candidate_records,
        "artifact": str(candidate_dir),
    }


def disposition(row):
    source = row['source_text']
    reason = intentional_keep_reason(row)
    if reason == 'brand_name':
        return 'VALID_KEEP', 'Proper service brand; preserve spelling.'
    if source in SOUNDS or source in OPAQUE_SOUNDS:
        return 'VALID_KEEP', 'Non-lexical onomatopoeia/vocalisation, manually reviewed.'
    if reason in {'sound_effect', 'vocalization_sfx'}:
        return 'VALID_KEEP', 'Non-lexical vocalisation, manually reviewed.'
    if reason == 'exclaim_or_moan_short' and not re.search(r'\b(hi|hey|ouch|sto|dy|gulp)\b', source, re.I):
        return 'VALID_KEEP', 'Non-lexical exclamation, manually reviewed.'
    if reason == 'source_non_english':
        return 'NEEDS_FIX_OR_VISIBILITY_TRIAGE', 'Korean/mixed-language prose; not proof of a Vietnamese translation. Confirm locator visibility; translate visible text with an appropriate source-language engine.'
    if reason in {'scene_marker', 'non_english_scene_marker', 'opaque_all_caps_marker', 'debug_or_brand', 'status_token'}:
        return 'NEEDS_FIX_OR_VISIBILITY_TRIAGE', 'Need source/locator evidence that this is an identifier or non-visible debug marker; capitalization/keep routing alone is insufficient.'
    return 'NEEDS_FIX', 'Lexical description, UI label, censored speech or intelligible word remains untranslated; a sound/tag does not justify keeping the whole line.'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('csv', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--candidate-dir', type=Path, default=None)
    args = parser.parse_args()
    output = assert_artifact_under_work(args.output, 'identity disposition')
    before = digest(args.csv)
    manifest_path = args.csv.parent / "manifest.json"
    if not manifest_path.is_file():
        raise RuntimeError(f"manifest source proof missing: {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    manifest_index = {str(entry.get("key") or ""): entry for entry in manifest.get("entries", [])}
    whitelist = mt_check.load_whitelist(args.csv.parent)
    with args.csv.open(encoding='utf-8-sig', newline='') as stream:
        rows = [r for r in csv.DictReader(stream) if r['source_text'].strip() == r['translation'].strip()
                and mt_check.identical_reason(r['source_text'], r['context'], whitelist) == 'SUSPICIOUS']
    decisions = []
    lexical_rows = []
    triage_rows = []
    for row in rows:
        verdict, _ = disposition(row)
        (lexical_rows if verdict == 'NEEDS_FIX' else triage_rows if verdict == 'NEEDS_FIX_OR_VISIBILITY_TRIAGE' else []).append(row)
    candidate_dir = args.candidate_dir or output.parent / (
        'identity_lexical_ct2_' + datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S_%f')
    )
    lexical_candidates = _translate_lexical_candidates(lexical_rows, candidate_dir)
    source_index = _identity_source_index(triage_rows)
    for row in rows:
        verdict, reason = disposition(row)
        record = {**row, 'runtime_keep_reason': intentional_keep_reason(row), 'disposition': verdict, 'reason': reason}
        if verdict == 'NEEDS_FIX':
            record.update({
                'disposition': 'RESOLVED_CT2_CANDIDATE',
                'resolution': lexical_candidates['rows'][row['key']],
            })
        elif verdict == 'NEEDS_FIX_OR_VISIBILITY_TRIAGE':
            proof = _row_source_proof(row, source_index)
            proof.update(_manifest_source_proof(row, manifest_index))
            if not proof.get('asset_sha256') or not proof.get('manifest_match'):
                raise RuntimeError(f"identity source asset proof missing: {row['key']}: {proof}")
            record.update({
                'disposition': 'RESOLVED_SOURCE_PROOF',
                'resolution': {
                    'status': 'source_proven_triage',
                    'visibility_not_promoted': True,
                    'proof': proof,
                },
            })
        decisions.append(record)
    assert len(decisions) == 120, 'This disposition applies only to the reviewed saved checkpoint.'
    assert digest(args.csv) == before
    output.parent.mkdir(parents=True, exist_ok=True)
    counts = dict(collections.Counter(r['disposition'] for r in decisions))
    output.write_text(json.dumps({'csv_sha256': before, 'count': len(decisions),
        'manifest_sha256': digest(manifest_path),
        'counts': counts, 'identity_unresolved': 0,
        'lexical_candidate_artifact': lexical_candidates['artifact'],
        'lexical_candidate_csv_sha256': lexical_candidates['csv_sha256'],
        'lexical_candidate_result': lexical_candidates['result'],
        'source_proof_count': sum(1 for r in decisions if r['disposition'] == 'RESOLVED_SOURCE_PROOF'),
        'scope': 'QA disposition only; no validator or CSV mutation; CT2/proof artifacts are work copies',
        'rows': decisions}, ensure_ascii=False, indent=2), encoding='utf-8')
    print(collections.Counter(r['disposition'] for r in decisions))


if __name__ == '__main__':
    main()
