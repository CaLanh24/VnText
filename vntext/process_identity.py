"""Tell a lock's real owner from an unrelated process that reuses its pid.

A pid alone is not an identity: Windows recycles pids quickly, so a lock left by a killed worker can point at an unrelated live process and block the
output forever.  A lock therefore records the owner's creation time too, and a live pid only keeps the lock when that time still matches."""
from __future__ import annotations

import os
from typing import Any, Callable, Mapping


def _win_open(pid: int):
    import ctypes
    from ctypes import wintypes
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    k32.OpenProcess.restype = wintypes.HANDLE
    k32.CloseHandle.argtypes = [wintypes.HANDLE]
    handle = k32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
    return k32, handle


def process_start_token(pid: int) -> str | None:
    """Creation time of ``pid`` as an opaque string, or None when it cannot be read."""
    if pid <= 0:
        return None
    try:
        if os.name == "nt":
            import ctypes
            from ctypes import wintypes
            k32, handle = _win_open(pid)
            if not handle:
                return None
            try:
                times = [wintypes.FILETIME() for _ in range(4)]
                k32.GetProcessTimes.argtypes = [wintypes.HANDLE] + [ctypes.POINTER(wintypes.FILETIME)] * 4
                k32.GetProcessTimes.restype = wintypes.BOOL
                if not k32.GetProcessTimes(handle, *(ctypes.byref(t) for t in times)):
                    return None
                return str((times[0].dwHighDateTime << 32) | times[0].dwLowDateTime)
            finally:
                k32.CloseHandle(handle)
        with open(f"/proc/{pid}/stat", "rb") as stream:
            return stream.read().rsplit(b")", 1)[1].split()[19].decode("ascii")
    except (OSError, ValueError, IndexError, AttributeError):
        return None


def process_image_name(pid: int) -> str | None:
    """Lower-case executable file name of ``pid``, or None when unknown."""
    if pid <= 0:
        return None
    try:
        if os.name == "nt":
            import ctypes
            from ctypes import wintypes
            k32, handle = _win_open(pid)
            if not handle:
                return None
            try:
                size = wintypes.DWORD(1024)
                buffer = ctypes.create_unicode_buffer(size.value)
                k32.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
                k32.QueryFullProcessImageNameW.restype = wintypes.BOOL
                if not k32.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(size)):
                    return None
                return os.path.basename(buffer.value).lower()
            finally:
                k32.CloseHandle(handle)
        return os.path.basename(os.readlink(f"/proc/{pid}/exe")).lower()
    except (OSError, ValueError, AttributeError):
        return None


def owner_record(extra: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Identity fields for a lock file written by this process."""
    record: dict[str, Any] = dict(extra or {})
    record["pid"] = os.getpid()
    token = process_start_token(os.getpid())
    if token:
        record["start"] = token
    return record


def describe_owner(record: Mapping[str, Any], lock_mtime: float | None = None) -> str:
    """Short, path-free description of a lock owner for messages and logs."""
    import time
    try:
        pid = int(record["pid"])
    except (KeyError, TypeError, ValueError):
        return "chủ khóa không rõ"
    parts = [f"PID {pid}", process_image_name(pid) or "tiến trình không đọc được tên"]
    if pid == os.getpid():
        parts.append("chính tiến trình này")
    elif pid == _parent_pid():
        parts.append("ứng dụng VNText Studio đã mở worker này")
    if lock_mtime is not None:
        parts.append(f"khóa {max(0, int(time.time() - lock_mtime))} giây tuổi")
    parts.append("khóa có thời điểm tạo tiến trình" if record.get("start") else "khóa kiểu cũ, không có thời điểm tạo tiến trình")
    return ", ".join(parts)


def _parent_pid() -> int:
    try:
        return os.getppid()
    except OSError:
        return 0


def watch_parent(on_dead: Callable[[], None], interval: float = 2.0, parent_pid: int | None = None) -> "threading.Thread | None":
    """Call ``on_dead`` once the process that started this one is gone (or its pid was reused).  Returns the daemon thread, or None when the
    parent cannot be identified, in which case nothing is watched."""
    import threading
    import time
    pid = _parent_pid() if parent_pid is None else parent_pid
    start = process_start_token(pid) if pid > 0 else None
    if pid <= 0 or start is None:
        return None

    def run() -> None:
        while True:
            time.sleep(interval)
            from vntext.traceability import _pid_alive
            current = process_start_token(pid)
            if current != start or not _pid_alive(pid):
                on_dead()
                return

    thread = threading.Thread(target=run, name="vntext-parent-watch", daemon=True)
    thread.start()
    return thread

