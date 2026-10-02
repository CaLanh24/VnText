"""Write translations into the `translation` column of translation.csv by `key`.

Refuses to write anything at all if any row in the batch breaks a hard rule
(placeholder / tag / literal \\n / heart glyph / synonym variant count /
English inflection glued onto a lexical placeholder).

Writing is crash-safe: a rolling backup is taken first, the full file is
rendered to a temp file in the same directory, flushed and fsynced, and only
then swapped in with os.replace (atomic on Windows and POSIX).
"""
from __future__ import annotations

import csv
import os
import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path

from vntext import mt_check
from vntext.mt_paths import ensure_mt_dir, paths_for_csv

csv.field_size_limit(10 ** 9)


@dataclass
class ApplyResult:
    ok: bool
    applied: int = 0
    unchanged: int = 0
    translated: int = 0
    total: int = 0
    remaining: int = 0
    message: str = ""
    problems: list[tuple] = field(default_factory=list)
    rolling_backup: str = ""


def _load_csv(csv_path: Path):
    with csv_path.open(encoding='utf-8-sig', newline='') as f:
        reader = csv.DictReader(f)
        fields = reader.fieldnames
        rows = list(reader)
    return fields, rows


def apply_batch(
    csv_path: str | Path,
    mapping: dict[str, str] | list[tuple[str, str]],
    *,
    allow_overwrite: bool = False,
    frozen: dict | None = None,
) -> ApplyResult:
    csv_path = Path(csv_path).resolve()
    paths = paths_for_csv(csv_path)
    ensure_mt_dir(paths)

    if isinstance(mapping, list):
        pairs = [(k, v) for k, v in mapping]
        mapping = dict(pairs)
        if len(mapping) != len(pairs):
            seen: set[str] = set()
            dupes = sorted({k for k, _ in pairs if k in seen or seen.add(k)})
            return ApplyResult(
                ok=False,
                message='duplicate key(s) in batch: %s' % dupes[:20],
            )

    if not mapping:
        return ApplyResult(ok=True, message='empty')

    fields, rows = _load_csv(csv_path)
    if not fields or 'key' not in fields or 'translation' not in fields:
        return ApplyResult(ok=False, message='unexpected csv header')

    n_before = len(rows)
    problems = []
    staged = []
    unknown = set(mapping)
    noop = 0
    by_key = {r['key']: r for r in rows}

    for k, new in mapping.items():
        r = by_key.get(k)
        if r is None:
            unknown.add(k)
            continue
        unknown.discard(k)
        if frozen and k in frozen:
            return ApplyResult(
                ok=False,
                message='refuse apply: frozen key %s' % k,
            )
        if r['translation'].strip() and r['translation'] != new and not allow_overwrite:
            return ApplyResult(
                ok=False,
                message='refuse apply: would overwrite existing translation %s' % k,
            )
        if r['translation'] == new:
            noop += 1
            continue
        for why in mt_check.structural_problems(r, new):
            problems.append((k, why, r['source_text'], new))
        staged.append((r, new))

    if problems:
        return ApplyResult(
            ok=False,
            applied=0,
            unchanged=noop,
            message='BLOCKED: %d problem(s), nothing written' % len(problems),
            problems=problems,
        )

    for r, new in staged:
        r['translation'] = new

    if len(rows) != n_before:
        return ApplyResult(ok=False, message='row count changed')

    roll = paths.rolling_backup
    shutil.copy2(csv_path, roll)

    tmp = str(csv_path) + '.tmp'
    with open(tmp, 'w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=fields, lineterminator='\r\n')
        w.writeheader()
        w.writerows(rows)
        f.flush()
        os.fsync(f.fileno())

    with open(tmp, encoding='utf-8-sig', newline='') as f:
        check = list(csv.DictReader(f))
    if len(check) != n_before:
        os.remove(tmp)
        return ApplyResult(
            ok=False,
            message='temp file has %d rows, expected %d. Nothing written.' % (len(check), n_before),
        )

    os.replace(tmp, csv_path)

    done = sum(1 for r in rows if r['translation'].strip())
    msg = (
        'OK applied=%d unchanged=%d  translated=%d/%d  remaining=%d'
        % (len(staged), noop, done, len(rows), len(rows) - done)
    )
    return ApplyResult(
        ok=True,
        applied=len(staged),
        unchanged=noop,
        translated=done,
        total=len(rows),
        remaining=len(rows) - done,
        message=msg,
        rolling_backup='%s (%s)' % (roll, time.strftime('%H:%M:%S')),
    )
