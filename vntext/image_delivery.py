"""Additive Ren'Py locale images with verified baseline and recoverable installation."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

from vntext.image_text import _image, _regular
from vntext.renpy_archive import RenPyArchive


def _hash(path):
    digest = hashlib.sha256()
    with _regular(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def _relative(value, image=False):
    if not isinstance(value, str) or not RenPyArchive._safe_name(value):
        raise ValueError('Unsafe image delivery path')
    if image and (Path(value).suffix.lower() not in {'.png', '.jpg', '.jpeg', '.webp'}
                  or any(p.casefold() in {'tl', 'saves', 'cache'} for p in value.split('/'))):
        raise ValueError('Image delivery allows only original static image paths')
    return value


def _json(path):
    path = _regular(path)
    if path.stat().st_size > 65536:
        raise ValueError('Delivery manifest exceeds 64 KiB')
    return json.loads(path.read_text(encoding='utf-8'))


def _save(path, value):
    with path.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, ensure_ascii=True, indent=2)
        stream.flush(); os.fsync(stream.fileno())


def prepare_image_delivery(document, rendered, game_root, output):
    root = _regular(game_root).resolve()
    game = _regular(root / 'game')
    output = _regular(output).resolve()
    if not game.is_dir() or output.is_relative_to(root) or root.is_relative_to(output):
        raise ValueError('Delivery output must be separate from the source game')
    source, original, source_hash = _image(document['source_path'])
    rendered, image, rendered_hash = _image(rendered)
    if source_hash != document['source_sha256'] or image.size != original.size:
        raise ValueError('Source or rendered dimensions changed')
    container = document.get('source_container_path')
    if container:
        container = _regular(container).resolve()
        container_rel = container.relative_to(root).as_posix()
        if not container.is_relative_to(game) or container.suffix.lower() != '.rpa':
            raise ValueError('Archive must belong to the selected game')
        member = _relative(document['source_member_name'], image=True)
        item = RenPyArchive(container).read_member(member)
        if (item['container_sha256'] != document['source_container_sha256']
                or item['member_sha256'] != document['source_member_sha256']
                or source_hash != item['member_sha256']):
            raise ValueError('Archive source identity changed')
        baseline = {'path': container_rel, 'sha256': item['container_sha256'],
                    'member': member, 'member_sha256': source_hash}
        relative = member
        if (game / relative).exists(): raise ValueError('Loose image shadows archive member; select the loose image')
    else:
        relative = source.resolve().relative_to(game).as_posix()
        baseline = {'path': 'game/' + relative, 'sha256': source_hash}
    relative = _relative(relative, image=True)
    # Preserve the extension expected by Ren'Py; never disguise PNG bytes as JPEG/WebP.
    extension = Path(relative).suffix.lower()
    output.mkdir(parents=True, exist_ok=False)
    payload = output / ('image' + extension)
    with payload.open('xb') as stream:
        if extension == '.webp': image.save(stream, format='WEBP', lossless=True)
        elif extension in {'.jpg', '.jpeg'}: image.convert('RGB').save(stream, format='JPEG', quality=95)
        else: image.save(stream, format='PNG')
    manifest = {'schema': 1, 'source_root': str(root), 'baseline': baseline,
                'relative_image': relative, 'target': 'game/tl/vietnamese/' + relative,
                'payload': payload.name, 'sha256': _hash(payload), 'rendered_sha256': rendered_hash,
                'width': image.width, 'height': image.height,
                'activation': 'Requires RenPy language vietnamese; original game remains unchanged'}
    _save(output / 'image_delivery.json', manifest)
    return manifest


def install_image_delivery(package, game_copy, transaction):
    package = _regular(package).resolve()
    manifest = _json(package / 'image_delivery.json')
    if manifest['schema'] != 1: raise ValueError('Unsupported image delivery schema')
    relative = _relative(manifest['relative_image'], image=True)
    target_relative = 'game/tl/vietnamese/' + relative
    if manifest['target'] != target_relative: raise ValueError('Image target mismatch')
    payload_name = _relative(manifest['payload'])
    if '/' in payload_name: raise ValueError('Payload must be a single file')
    payload = _regular(package / payload_name)
    _, decoded, digest = _image(payload)
    if digest != manifest['sha256'] or decoded.size != (manifest['width'], manifest['height']):
        raise ValueError('Image payload tampered')
    target_root = _regular(game_copy).resolve()
    original_root = _regular(manifest['source_root']).resolve()
    transaction = _regular(transaction).resolve()
    if (target_root.is_relative_to(original_root) or original_root.is_relative_to(target_root)
            or transaction.is_relative_to(target_root) or target_root.is_relative_to(transaction)
            or transaction.is_relative_to(original_root) or original_root.is_relative_to(transaction)
            or not (target_root / 'game').is_dir()):
        raise ValueError('Install only into a separate game copy, with a separate transaction directory')
    baseline = manifest['baseline']
    baseline_path = _relative(baseline['path'])
    if not baseline_path.startswith('game/') or _hash(target_root / baseline_path) != baseline['sha256']:
        raise ValueError('Game copy baseline mismatch')
    if 'member' in baseline:
        if (target_root / 'game' / relative).exists(): raise ValueError('Loose image shadows archive baseline')
        item = RenPyArchive(target_root / baseline_path).read_member(_relative(baseline['member'], image=True))
        if item['member_sha256'] != baseline['member_sha256']: raise ValueError('Archive member mismatch')
    target = _regular(target_root / target_relative)
    if target.exists(): raise ValueError('Existing locale image preserved; choose a clean game copy')
    transaction.mkdir(parents=True, exist_ok=False)
    staged = transaction / payload.name
    with staged.open('xb') as stream:
        stream.write(payload.read_bytes()); stream.flush(); os.fsync(stream.fileno())
    if _hash(staged) != digest: raise ValueError('Staged image mismatch')
    journal = {'schema': 1, 'target_root': str(target_root), 'source_root': str(original_root),
               'relative_image': relative, 'sha256': digest, 'baseline': baseline, 'staged': staged.name}
    _save(transaction / 'intent.json', journal)
    target.parent.mkdir(parents=True, exist_ok=True)
    # Atomic no-overwrite publication; journal/staged bytes exist before the target appears.
    os.link(staged, target)
    try:
        if _hash(target) != digest: raise ValueError('Installed image readback mismatch')
        _save(transaction / 'applied.json', {'status': 'READ_BACK_VERIFIED', 'sha256': digest})
    except Exception:
        rollback_image_delivery(transaction)
        raise
    return {'status': 'READ_BACK_VERIFIED', 'target': str(target), 'transaction': str(transaction)}


def rollback_image_delivery(transaction):
    transaction = _regular(transaction).resolve()
    journal = _json(transaction / 'intent.json')
    if journal['schema'] != 1: raise ValueError('Unsupported recovery journal')
    relative = _relative(journal['relative_image'], image=True)
    root = _regular(journal['target_root']).resolve()
    source = _regular(journal['source_root']).resolve()
    if root.is_relative_to(source) or source.is_relative_to(root): raise ValueError('Source game is protected')
    target = _regular(root / 'game/tl/vietnamese' / relative)
    if target.exists():
        staged_name = _relative(journal['staged'])
        if '/' in staged_name or not os.path.samefile(_regular(transaction / staged_name), target):
            raise ValueError('Recovery target is not the file published by this transaction')
        if _hash(target) != journal['sha256']: raise ValueError('Locale image changed; rollback preserves user edits')
        target.unlink()
    return {'status': 'ROLLED_BACK', 'target': str(target)}
