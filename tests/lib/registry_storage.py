"""Lossless registry storage. Logical snapshot bytes (and their hashes) never change.

Only immutable epoch JSON may use gzip-in-place. Live registries remain JSON.
Cold records retain their original lifecycle/provenance; cold is not deleted/PASS.
"""
from __future__ import annotations
import gzip
import hashlib
import json
import os
import stat
import uuid
from pathlib import Path

MAX_LOGICAL = 256 * 1024**2


def regular(path: Path) -> None:
    for part in (path, *path.parents):
        if part.exists():
            s = part.lstat()
            if stat.S_ISLNK(s.st_mode) or getattr(s, 'st_file_attributes', 0) & 0x400:
                raise OSError(f'linked registry path refused: {part}')
    if not path.is_file():
        raise FileNotFoundError(f'registry file missing: {path}')


def snapshot_bytes(path: Path) -> bytes:
    regular(path)
    with path.open('rb') as f:
        magic = f.read(2)
        f.seek(0)
        if magic != b'\x1f\x8b':
            return f.read()
        try:
            with gzip.GzipFile(fileobj=f) as g:
                data = g.read(MAX_LOGICAL + 1)
                if len(data) > MAX_LOGICAL:
                    raise ValueError('snapshot exceeds logical size bound')
                return data  # gzip CRC is verified at EOF
        except EOFError as exc:
            raise OSError('truncated registry snapshot') from exc


def snapshot_json(path: Path):
    return json.loads(snapshot_bytes(path).decode('utf-8'))


def pack_exact(path: Path, *, scratch_limit=2 * 1024**2) -> dict:
    """Atomic per-file compaction, bounded scratch, verified raw SHA before replace."""
    regular(path)
    before = path.read_bytes()
    logical = snapshot_bytes(path)
    digest = hashlib.sha256(logical).hexdigest()
    if before.startswith(b'\x1f\x8b'):
        return dict(path=str(path), logical_sha256=digest, before_bytes=len(before), after_bytes=len(before), changed=False)
    temporary = path.with_name(path.name + '.' + uuid.uuid4().hex + '.pack')
    try:
        with temporary.open('xb') as f:
            with gzip.GzipFile(fileobj=f, mode='wb', mtime=0) as g:
                for i in range(0, len(before), 64 * 1024):
                    g.write(before[i:i+64*1024])
                    if f.tell() > scratch_limit:
                        raise ValueError('compaction scratch bound exceeded')
            f.flush(); os.fsync(f.fileno())
        if temporary.stat().st_size > scratch_limit or snapshot_bytes(temporary) != before:
            raise ValueError('lossless compaction readback failed')
        if path.read_bytes() != before:
            raise ValueError('snapshot changed during compaction')
        os.replace(temporary, path)
        if hashlib.sha256(snapshot_bytes(path)).hexdigest() != digest:
            raise ValueError('published snapshot readback failed')
        return dict(path=str(path), logical_sha256=digest, stored_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                    before_bytes=len(before), after_bytes=path.stat().st_size, changed=True)
    finally:
        temporary.unlink(missing_ok=True)


def cold_records(document: dict, registry: Path):
    """Explicit history reader, never silently inflate the live working set."""
    root = registry.parent.resolve() / 'registry-history'
    for ref in document.get('cold_records', []):
        path = (registry.parent / ref['path']).resolve()
        if not path.is_relative_to(root):
            raise ValueError('cold archive escaped registry-history')
        regular(path)
        if hashlib.sha256(path.read_bytes()).hexdigest() != ref['stored_sha256']:
            raise ValueError('cold archive storage hash mismatch')
        raw = snapshot_bytes(path)
        if hashlib.sha256(raw).hexdigest() != ref['logical_sha256']:
            raise ValueError('cold archive logical hash mismatch')
        records = json.loads(raw)
        if not isinstance(records, list) or len(records) != ref['count']:
            raise ValueError('cold archive count mismatch')
        yield from records


def verify_cold(document: dict, registry: Path) -> None:
    # Full parse/count verification; no trusting a caller-supplied summary.
    for _record in cold_records(document, registry):
        if not isinstance(_record, dict) or not _record.get('id'):
            raise ValueError('invalid cold registry record')


def archive_missing(document: dict, registry: Path) -> dict:
    """Plan the cold working set; physical deletion and lifecycle promotion forbidden."""
    selected, active = [], []
    for item in document['artifacts']:
        p = Path(str(item.get('path') or ''))
        if (item.get('lifecycle') == 'MISSING' and not os.path.lexists(p)
                and not str(item.get('id', '')).startswith('artifact-registry-epoch:')):
            selected.append(item)
        else:
            active.append(item)
    if not selected:
        return dict(document)
    raw = json.dumps(selected, ensure_ascii=False, separators=(',', ':')).encode('utf8')
    logical = hashlib.sha256(raw).hexdigest()
    root = registry.parent / 'registry-history'
    root.mkdir(exist_ok=True)
    blob = root / (logical + '.json.gz')
    packed = gzip.compress(raw, mtime=0)
    if len(packed) > 2 * 1024**2:
        raise ValueError('cold archive exceeds remediation scratch bound')
    if not blob.exists():
        with blob.open('xb') as f:
            f.write(packed); f.flush(); os.fsync(f.fileno())
    elif blob.read_bytes() != packed:
        raise ValueError('content-addressed cold archive differs')
    result = dict(document, artifacts=active)
    # Missing records keep their unresolved state, including missing deletion evidence.
    ref = dict(path=str(blob.relative_to(registry.parent)), count=len(selected),
               logical_sha256=logical, stored_sha256=hashlib.sha256(packed).hexdigest(), unresolved_missing=len(selected))
    result['cold_records'] = [*document.get('cold_records', []), ref]
    verify_cold(result, registry)
    return result


def project_epoch_chain_manifest(document):
    """Keep exactly what the epoch chain reads from a PREVIOUS registry: every top-level field, and from ``artifacts`` only the epoch records
    (the sole artifact records the chain compares).  Anything else, including a non-list ``artifacts``, passes through so the shape checks still fail closed."""

    if isinstance(document, dict) and isinstance(document.get("artifacts"), list):
        projected = dict(document)
        projected["artifacts"] = [
            item for item in document["artifacts"]
            if isinstance(item, dict) and str(item.get("id") or "").startswith("artifact-registry-epoch:")
        ]
        return projected
    return document

