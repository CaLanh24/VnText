"""Operating-system byte-range lock on an open file: held by the open handle, released by the system when the handle closes or the process ends.

A pid in a lock file is only a description for messages: it never decides who owns the lock, so a killed process can never leave a lock behind and a
recycled pid can never keep one alive.  The locked byte lies far beyond the description so other processes can still read it.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

LOCK_OFFSET = 1 << 30
_BINARY = getattr(os, "O_BINARY", 0)


def try_lock(fd: int) -> bool:
    """Take the system lock on ``fd`` without waiting; False when another handle or process holds it."""
    os.lseek(fd, LOCK_OFFSET, os.SEEK_SET)
    try:
        if os.name == "nt":
            import msvcrt
            msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.lockf(fd, fcntl.LOCK_EX | fcntl.LOCK_NB, 1, LOCK_OFFSET)
        return True
    except OSError:
        return False
    finally:
        os.lseek(fd, 0, os.SEEK_SET)


def open_lock_file(path: str | os.PathLike) -> int:
    return os.open(path, os.O_CREAT | os.O_RDWR | _BINARY)


def write_description(fd: int, payload: bytes) -> None:
    """Replace the description in place (the file is never swapped, so the lock stays on the same file)."""
    os.lseek(fd, 0, os.SEEK_SET)
    os.ftruncate(fd, 0)
    os.write(fd, payload)
    os.fsync(fd)


def describe_holder(path: str | os.PathLike) -> str:
    """Path-free description of the lock's recorded holder, for messages."""
    from vntext.process_identity import describe_owner
    try:
        mtime = os.stat(path).st_mtime
        with open(path, "rb") as stream:
            record = json.loads(stream.read(4096))
        return describe_owner(record, mtime)
    except (OSError, ValueError, KeyError, TypeError):
        return "chủ khóa không đọc được"


def is_held(path: str | os.PathLike) -> bool:
    """True when some other handle (process) holds the lock now; a leftover file nobody holds is not a lock."""
    if not os.path.lexists(path):
        return False
    try:
        fd = os.open(path, os.O_RDWR | _BINARY)
    except OSError:
        return True
    try:
        return not try_lock(fd)
    finally:
        os.close(fd)


def release(fd: int, path: str | os.PathLike | None = None) -> None:
    """Close the handle (this releases the lock) and remove the file when nobody grabbed it in between."""
    try:
        os.close(fd)
    finally:
        if path is not None:
            try:
                Path(path).unlink(missing_ok=True)
            except OSError:
                pass
