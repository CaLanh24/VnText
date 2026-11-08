"""One distributable executable. Build/audit files stay private to the app."""
from __future__ import annotations
import hashlib
import os
from pathlib import Path
import shutil
import struct
import uuid
import zipfile

MAGIC = b'VNTEXT-PATCH-001!'


def bundle_patch(installer: Path, patch: Path, destination: Path) -> Path:
    from vntext.image_text import _regular
    installer, patch, destination = map(_regular, (installer, patch, destination))
    if not (patch / 'patch_manifest.json').is_file():
        raise ValueError('Thiếu manifest patch; không thể tạo installer.')
    files = [p for p in patch.rglob('*') if p.is_file() and
             (p.relative_to(patch).parts[0] == 'COPY_TO_GAME_ROOT' or p.name in {'patch_manifest.json', 'patch_coverage.json', 'patch_verification.json'})]
    for path in files:
        _regular(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(destination.name + '.' + uuid.uuid4().hex + '.tmp')
    archive = temporary.with_suffix('.zip')
    try:
        with zipfile.ZipFile(archive, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as bundle:
            for path in files:
                bundle.write(path, path.relative_to(patch).as_posix())
        with zipfile.ZipFile(archive) as bundle:
            if bundle.testzip() is not None:
                raise ValueError('Payload patch không qua kiểm tra ZIP.')
        digest = hashlib.sha256()
        with temporary.open('xb') as output, installer.open('rb') as stub, archive.open('rb') as payload:
            shutil.copyfileobj(stub, output)
            for block in iter(lambda: payload.read(1024 * 1024), b''):
                digest.update(block); output.write(block)
            output.write(digest.digest() + struct.pack('<Q', archive.stat().st_size) + MAGIC)
            output.flush(); os.fsync(output.fileno())
        temporary.replace(destination)
        return destination
    finally:
        temporary.unlink(missing_ok=True)
        archive.unlink(missing_ok=True)
