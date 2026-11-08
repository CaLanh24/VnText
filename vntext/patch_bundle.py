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
FOOTER_SIZE = 32 + 8 + len(MAGIC)
MAX_ENTRIES = 100_000
MAX_TOTAL_BYTES = 64 * 1024 ** 3


def read_bundle_file(executable: Path, name: str) -> bytes:
    """One payload file of a built patch EXE (used by tests and diagnostics; the installer itself never trusts this path)."""
    verify_bundle(executable)
    executable = Path(executable)
    size = executable.stat().st_size
    with executable.open('rb') as handle:
        handle.seek(size - FOOTER_SIZE)
        length = struct.unpack('<Q', handle.read(FOOTER_SIZE)[32:40])[0]
        handle.seek(size - FOOTER_SIZE - length)
        import io
        with zipfile.ZipFile(io.BytesIO(handle.read(length))) as bundle:
            return bundle.read(name)


def verify_bundle(executable: Path) -> dict:
    """Re-read the footer of a built EXE: digest, length and the ZIP inventory (names only; nothing is extracted)."""
    executable = Path(executable)
    size = executable.stat().st_size
    with executable.open('rb') as handle:
        handle.seek(size - FOOTER_SIZE)
        footer = handle.read(FOOTER_SIZE)
        if footer[40:] != MAGIC:
            raise ValueError('EXE không có payload patch.')
        digest, length = footer[:32], struct.unpack('<Q', footer[32:40])[0]
        if not 22 <= length <= size - FOOTER_SIZE:
            raise ValueError('Độ dài payload patch không hợp lệ.')
        handle.seek(size - FOOTER_SIZE - length)
        check = hashlib.sha256()
        remaining = length
        while remaining:
            block = handle.read(min(1024 * 1024, remaining))
            if not block:
                raise ValueError('Payload patch bị cắt.')
            check.update(block); remaining -= len(block)
        if check.digest() != digest:
            raise ValueError('Hash payload patch không khớp.')
        handle.seek(size - FOOTER_SIZE - length)
        import io
        with zipfile.ZipFile(io.BytesIO(handle.read(length))) as bundle:
            names = [i.filename for i in bundle.infolist() if not i.is_dir()]
    return {'sha256': digest.hex(), 'payload_bytes': length, 'files': names}


def bundle_patch(installer: Path, patch: Path, destination: Path) -> Path:
    from vntext.image_text import _regular
    installer, patch, destination = map(_regular, (installer, patch, destination))
    if not (patch / 'patch_manifest.json').is_file():
        raise ValueError('Thiếu manifest patch; không thể tạo installer.')
    files = [p for p in patch.rglob('*') if p.is_file() and
             (p.relative_to(patch).parts[0] == 'COPY_TO_GAME_ROOT' or p.name in {'patch_manifest.json', 'patch_coverage.json', 'patch_verification.json'})]
    if not files or len(files) > MAX_ENTRIES:
        raise ValueError('Số file patch không hợp lệ.')
    total = 0
    seen: set[str] = set()
    for path in files:
        _regular(path)
        total += path.stat().st_size
        folded = path.relative_to(patch).as_posix().casefold()
        if folded in seen:
            raise ValueError('Tên file patch trùng nhau.')
        seen.add(folded)
    if total > MAX_TOTAL_BYTES:
        raise ValueError('Payload patch vượt giới hạn 64 GiB.')
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
