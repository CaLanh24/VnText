"""Owner-approved R03 remediation: plan -> CAS -> lossless snapshots -> cold records.

No game, model, user data, lifecycle promotion or epoch/source/approval rewriting.
At most 2 MiB of new storage per snapshot is permitted while remediating an
already over-budget tree. This is not a build allocation or a quota increase.
"""
from __future__ import annotations
import argparse
from collections import Counter
import hashlib
import json
import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'lib'))
from registry_storage import regular, snapshot_bytes, pack_exact, archive_missing, cold_records


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def plan(root: Path):
    manifest = root / 'TEST_RUN/artifacts_manifest.json'
    regular(manifest)
    history = root / 'TEST_RUN/artifact-registry-epochs'
    files = []
    for p in sorted(history.rglob('*.json')):
        regular(p)
        if p.stat().st_size > 1024**2:
            files.append(dict(path=str(p.relative_to(root)), stored_sha256=digest(p), bytes=p.stat().st_size))
    return dict(version=1, root=str(root.resolve()), manifest_sha256=digest(manifest), snapshots=files,
                authority='Owner 2026-11-11 approved audit R01-R12, including hash/CAS/readback history compaction',
                scratch_limit_bytes=2*1024**2, deletions='none: every logical historical byte is retained')


def apply(root: Path, reviewed: dict, *, publish=None):
    manifest = root / 'TEST_RUN/artifacts_manifest.json'
    if reviewed.get('root') != str(root.resolve()) or digest(manifest) != reviewed['manifest_sha256']:
        raise ValueError('compaction plan/registry changed; no mutation')
    for item in reviewed['snapshots']:
        p = (root / item['path']).resolve()
        if not p.is_relative_to(root / 'TEST_RUN/artifact-registry-epochs'):
            raise ValueError('snapshot escaped immutable epoch root')
        regular(p)
        if digest(p) != item['stored_sha256']:
            raise ValueError('snapshot changed since plan; no mutation')
    before = manifest.read_bytes()
    document = json.loads(before)
    epoch_before = json.dumps(document.get('prospective_epoch'), sort_keys=True)
    packed = [pack_exact(root / item['path'], scratch_limit=reviewed['scratch_limit_bytes']) for item in reviewed['snapshots']]
    updated = archive_missing(document, manifest)
    if json.dumps(updated.get('prospective_epoch'), sort_keys=True) != epoch_before:
        raise ValueError('epoch metadata changed')
    if manifest.read_bytes() != before:
        raise ValueError('registry changed; logical snapshots preserved, live registry untouched')
    # Preserve the exact old live-registry bytes as an immutable rollback basis.
    rollback = manifest.parent / 'registry-history' / (hashlib.sha256(before).hexdigest()+'.registry-before.json')
    if not rollback.exists():
        import gzip
        encoded = gzip.compress(before, mtime=0)
        if len(encoded) > reviewed['scratch_limit_bytes']:
            raise ValueError('rollback storage scratch bound exceeded')
        with rollback.open('xb') as f:
            f.write(encoded); f.flush(); os.fsync(f.fileno())
    if snapshot_bytes(rollback) != before:
        raise ValueError('registry rollback readback differs')
    if publish:
        publish(updated)
    else:
        temp = manifest.with_suffix('.compacting')
        try:
            temp.write_text(json.dumps(updated, ensure_ascii=False, indent=2)+'\n', encoding='utf8')
            if manifest.read_bytes() != before:
                raise ValueError('registry CAS changed')
            os.replace(temp, manifest)
        finally:
            temp.unlink(missing_ok=True)
    current = json.loads(manifest.read_text(encoding='utf8'))
    historical = list(cold_records(current, manifest))
    encode = lambda x: json.dumps(x, sort_keys=True, ensure_ascii=False)
    before_records = Counter(encode(x) for x in [*document['artifacts'], *cold_records(document, manifest)])
    after_records = Counter(encode(x) for x in [*current['artifacts'], *historical])
    if after_records != before_records:
        raise ValueError('registry record readback differs')
    return dict(ok=True, packed=packed, before_manifest_bytes=len(before), after_manifest_bytes=manifest.stat().st_size,
                records_preserved=sum(before_records.values()), active_records=len(current['artifacts']),
                cold_records=len(historical), rollback_path=str(rollback), rollback_logical_sha256=hashlib.sha256(before).hexdigest(),
                before_epoch_equals_after=True, lifecycle_verdict='unchanged; cold MISSING records remain unresolved',
                freed_bytes=sum(x['before_bytes']-x['after_bytes'] for x in packed)+len(before)-manifest.stat().st_size)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=['plan','apply']);p.add_argument('--plan',type=Path,required=True);p.add_argument('--receipt',type=Path)
    args=p.parse_args();root=Path(__file__).resolve().parents[2]
    # Mutation only when no live epoch writer owns the registry.
    if args.action == 'apply':
        from cleanup_work_artifacts import _prospective_epoch_writer_status
        if _prospective_epoch_writer_status().get('active'):
            raise ValueError('epoch writer active; compaction refused')
    if args.action=='plan':
        result=plan(root);args.plan.write_text(json.dumps(result,indent=2),encoding='utf8')
        print(json.dumps({'ok':True,'snapshots':len(result['snapshots']),'manifest_sha256':result['manifest_sha256']}));return
    from work_paths import _registry_lock, _save_manifest
    with _registry_lock():
        result=apply(root,json.loads(args.plan.read_text(encoding='utf8')),publish=_save_manifest)
    if args.receipt:args.receipt.write_text(json.dumps(result,indent=2),encoding='utf8')
    print(json.dumps({k:v for k,v in result.items() if k!='packed'}))


if __name__=='__main__':main()
