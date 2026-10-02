"""Audit translation.csv. Read-only: never writes to the csv."""
from __future__ import annotations

import collections
import csv
import os
from pathlib import Path

from vntext import mt_check
from vntext.mt_paths import paths_for_csv

csv.field_size_limit(10 ** 9)


def run_qa(
    csv_path: str | Path,
    *,
    final: bool = False,
    scope: str | None = None,
    report_path: str | Path | None = None,
) -> tuple[bool, str]:
    csv_path = Path(csv_path).resolve()
    paths = paths_for_csv(csv_path)
    if report_path is None:
        report_path = paths.qa_report

    with csv_path.open(encoding='utf-8-sig', newline='') as f:
        reader = csv.DictReader(f)
        fields = reader.fieldnames
        rows = list(reader)

    package_dir = csv_path.parent
    whitelist = mt_check.load_whitelist(package_dir)
    cleared = mt_check.load_cleared(package_dir)
    policy = mt_check.load_policy_skipped(package_dir)

    empty = []
    skipped = []
    structural = []
    suffix = []
    english = []
    quality = []
    identical = []
    intentional_identical = set()
    translated = 0

    # Lazy imports keep the read-only QA module usable by lightweight tools.
    from vntext.intentional_keep import intentional_keep_reason
    from vntext.mt_classify import classify_row_authoritative
    from vntext.mt_strategies import candidate_quality_issues

    for r in rows:
        tr = r['translation']
        keep_reason = intentional_keep_reason(r)
        if not tr.strip():
            (skipped if r['key'] in policy else empty).append(r)
            continue
        translated += 1
        for why in mt_check.structural_problems(r, tr):
            if 'english suffix' in why:
                suffix.append((r['key'], why, r['source_text'], tr))
            else:
                structural.append((r['key'], why, r['source_text'], tr))

        quality_reasons = candidate_quality_issues(r, tr, whitelist)
        if quality_reasons:
            quality.append((r['key'], '; '.join(quality_reasons), r['source_text'], tr))

        if scope and scope not in r['context']:
            continue

        if tr.strip() == r['source_text'].strip():
            identical.append((r['key'], r['source_text'], r['context']))
            if keep_reason:
                intentional_identical.add(r['key'])
            if mt_check.is_script_identifier(r['source_text'], r['context']):
                continue

        score, reasons = mt_check.english_report(r['source_text'], tr, whitelist)
        reasons = [x for x in reasons if x != 'identical-to-source']
        # A literal vocalisation/SFX is intentionally kept in English-like
        # spelling.  It already has an explicit keep decision above; do not
        # turn that decision back into a residual-English failure.
        if r['key'] in intentional_identical or keep_reason:
            continue
        if reasons and r['key'] not in cleared:
            action, _reason, _decision = classify_row_authoritative({**r, 'translation': ''})
            if action in {'translate', 'translate_synonym', 'ui_label_fixed'}:
                english.append((r['key'], '; '.join(reasons), r['source_text'], tr))

    pairs = collections.defaultdict(dict)
    for r in rows:
        ctx = r['context']
        fp = r['file_path']
        base = None
        if ctx.startswith('TextAsset:'):
            base = ctx.split(':', 1)[1].split(':')[0]
            side = 'embedded'
        elif fp.lower().endswith('.txt'):
            base = os.path.splitext(os.path.basename(fp))[0]
            side = 'external'
        if base:
            pairs[(base, r['source_text'])].setdefault(side, set()).add(r['translation'])

    mirror = []

    for (base, src), sides in pairs.items():
        if len(sides) < 2:
            continue
        vals = set()
        for s in sides.values():
            vals |= s
        vals = {v for v in vals if v.strip()}
        if len(vals) > 1:
            mirror.append((base, src, sorted(vals)))

    lines = []
    w = lines.append
    w('== QA translation.csv ==')
    w('rows: %d   columns: %d' % (len(rows), len(fields)))
    w('translated: %d / %d   empty: %d   policy-skipped: %d'
      % (translated, len(rows), len(empty), len(skipped)))
    orphan = [k for k in policy if k not in {r['key'] for r in rows}]
    if orphan:
        w('policy ledger keys not present in csv: %d' % len(orphan))
    filled = [r['key'] for r in rows if r['key'] in policy and r['translation'].strip()]
    if filled:
        w('policy ledger keys that DO have a translation: %d' % len(filled))
    if scope:
        w('language checks scoped to context containing: %r' % scope)
    w('')
    w('structural violations (placeholder/tag/newline/heart/synonym): %d' % len(structural))
    for k, why, src, tr in structural[:40]:
        w('  - %s | %s' % (k, why))
        w('      SRC %s' % src[:200])
        w('      TRA %s' % tr[:200])
    w('')
    w('english suffix on lexical placeholder: %d' % len(suffix))
    for k, why, src, tr in suffix[:40]:
        w('  - %s | %s' % (k, why))
        w('      TRA %s' % tr[:200])
    w('')
    w('residual-english candidates: %d' % len(english))
    for k, why, src, tr in english[:120]:
        w('  - %s | %s' % (k, why))
        w('      SRC %s' % src[:200])
        w('      TRA %s' % tr[:200])
    w('')
    w('content-quality violations: %d' % len(quality))
    for k, why, src, tr in quality[:120]:
        w('  - %s | %s' % (k, why))
        w('      SRC %s' % src[:200])
        w('      TRA %s' % tr[:200])
    w('')

    ident_by_reason = collections.Counter()
    ident_bad = []
    for k, src, ctx in identical:
        why = mt_check.identical_reason(src, ctx, whitelist)
        if why == 'SUSPICIOUS' and k in cleared:
            why = 'reviewed by hand'
        ident_by_reason[why] += 1
        if why == 'SUSPICIOUS' and k not in intentional_identical:
            ident_bad.append((k, src, ctx))

    w('translation identical to source: %d' % len(identical))
    for why, n in ident_by_reason.most_common():
        w('  %-24s %d' % (why, n))
    for k, src, ctx in ident_bad[:80]:
        w('  ! %s | %s | %s' % (k, src[:120], ctx[:80]))
    w('')
    w('mirror mismatch (embedded vs external): %d' % len(mirror))
    for base, src, vals in mirror[:40]:
        w('  - %s | %s' % (base, src[:120]))
        for v in vals:
            w('      %s' % v[:160])
    w('VH oracle is audit-only; mirror mismatches are never exempt.')

    text = '\n'.join(lines)
    Path(report_path).parent.mkdir(parents=True, exist_ok=True)
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(text + '\n')

    hard = len(structural) + len(suffix) + len(mirror) + len(orphan) + len(filled)
    if final:
        hard += len(empty) + len(ident_bad) + len(english) + len(quality)
    return hard == 0, text
