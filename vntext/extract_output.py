"""Refresh generated output without clearing a user-selected directory."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
import threading
import time
import uuid


def _no_links(path: Path) -> None:
    for item in (path, *path.parents):
        if item.exists() or item.is_symlink():
            if item.is_symlink() or getattr(item.lstat(), "st_file_attributes", 0) & 0x400:
                raise ValueError(f"Output must not contain a link or junction: {item}")


def _digest(path: Path) -> str | None:
    _no_links(path)
    if not path.exists():
        return None
    if not path.is_file():
        raise ValueError(f"Generated output conflicts with a directory: {path}")
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def _write(path: Path, data: bytes, expected: str | None) -> None:
    _no_links(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(".vntext-new-" + uuid.uuid4().hex)
    try:
        with temp.open("xb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        if _digest(path) != expected:
            raise ValueError(f"Output changed externally; refused overwrite: {path}")
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def _sweep_interrupted_leftovers(root: Path) -> list[str]:
    """Remove what a killed extraction left behind (forced stop, power loss).  Runs only while this call holds the output lock, so nothing live can own
    them: private staging directories and half-written temp files carry VNText's own unique prefixes; every other file in the output is left alone."""
    removed = []
    for child in root.iterdir():
        try:
            if child.is_symlink() or getattr(child.lstat(), "st_file_attributes", 0) & 0x400:
                continue
            if child.is_dir() and child.name.startswith(".vntext-extract-"):
                shutil.rmtree(child)
                removed.append(child.name)
            elif child.is_file() and child.name.startswith(".vntext-new-"):
                child.unlink()
                removed.append(child.name)
        except OSError:
            continue
    return removed


# The lock is the operating system's own byte-range lock on the open lock file: the system drops it the moment the owning process ends (killed,
# crashed, power loss), so a stale lock can never block the folder and no pid or process identity has to be guessed.  The JSON inside the file is
# only a description for messages (and the form older versions wrote); it never decides who owns the lock.  The locked byte lies far beyond the
# content so that other processes can still read the description.
_LOCK_OFFSET = 1 << 30
# Output locks this process holds right now.  The system lock is per process on some platforms, so a second extraction in the same process has to be
# refused here.
_HELD_LOCKS: set[str] = set()
_HELD_LOCKS_GUARD = threading.Lock()


def _held_key(lock: Path) -> str:
    return os.path.normcase(os.path.abspath(lock))


def _os_lock(fd: int) -> bool:
    """Take the system lock on ``fd`` without waiting; False when another handle or process holds it."""
    os.lseek(fd, _LOCK_OFFSET, os.SEEK_SET)
    try:
        if os.name == "nt":
            import msvcrt
            msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.lockf(fd, fcntl.LOCK_EX | fcntl.LOCK_NB, 1, _LOCK_OFFSET)
        return True
    except OSError:
        return False
    finally:
        os.lseek(fd, 0, os.SEEK_SET)


def _owner_text(lock: Path) -> str:
    from vntext.process_identity import describe_owner
    try:
        age = time.time() - lock.stat().st_mtime
        return describe_owner(json.loads(lock.read_bytes()), time.time() - age)
    except (OSError, ValueError, KeyError, TypeError):
        return "chủ khóa không đọc được"


def extract_lock_held(lock: Path) -> bool:
    """True when some process (possibly this one) holds the output lock now; a leftover file nobody holds is not a lock."""
    if not os.path.lexists(lock):
        return False
    if _held_key(lock) in _HELD_LOCKS:
        return True
    try:
        fd = os.open(lock, os.O_RDWR | getattr(os, "O_BINARY", 0))
    except OSError:
        return True              # cannot even open it: assume it is in use rather than overwrite a live extraction
    try:
        return not _os_lock(fd)
    finally:
        os.close(fd)


def _take_lock(lock: Path, log=None) -> int:
    from vntext.process_identity import owner_record
    _no_links(lock)
    key = _held_key(lock)
    with _HELD_LOCKS_GUARD:
        held_here = key in _HELD_LOCKS
    busy = ("Nơi lưu bản dịch đang được một lần lấy text khác sử dụng ({who}). Hãy đợi tác vụ đó xong hoặc hủy nó; "
            "nếu không còn tác vụ nào chạy, hãy đóng VNText Studio rồi mở lại.")
    if held_here:
        raise ValueError(busy.format(who="chính tiến trình này"))
    fd = os.open(lock, os.O_CREAT | os.O_RDWR | getattr(os, "O_BINARY", 0))
    try:
        if not _os_lock(fd):
            raise ValueError(busy.format(who=_owner_text(lock)))
        try:
            previous = os.read(fd, 4096)
        except OSError:
            previous = b""
        if previous.strip() and log is not None:
            log("Dọn nội dung khóa nơi lưu bản dịch của một tiến trình đã kết thúc.")
        os.lseek(fd, 0, os.SEEK_SET)
        os.ftruncate(fd, 0)
        os.write(fd, json.dumps(owner_record()).encode())
        os.fsync(fd)
    except BaseException:
        os.close(fd)
        raise
    with _HELD_LOCKS_GUARD:
        _HELD_LOCKS.add(key)
    return fd


def refresh_extract(src, out, produce, complete, log, is_cancelled=None):
    # Notify the host only after releasing the package lock and owned staging.
    try:
        result = _refresh_extract(src, out, produce, log, is_cancelled)
    finally:
        # Game files opened by the analysis (UnityPy reads through fsspec) can stay open inside reference cycles until the next collection, which
        # blocks removing a patch or renaming the game folder on Windows; free them before the host is told the extraction ended.
        import gc
        gc.collect()
    complete(result)


def _refresh_extract(src, out, produce, log, is_cancelled=None):
    """Generate privately, then overwrite only emitted files; retain no old backup."""
    started = time.time_ns()
    root = Path(os.path.abspath(out))
    _no_links(root)
    source = Path(src).resolve()
    source = source if source.is_dir() else source.parent
    if root == source or root.is_relative_to(source) or source.is_relative_to(root):
        raise ValueError("Nơi lưu bản dịch phải nằm riêng, không chứa hoặc nằm trong thư mục game.")
    root.mkdir(parents=True, exist_ok=True)
    lock = root / ".vntext-extract.lock"
    fd = _take_lock(lock, log)
    stage = None
    prior_status = None
    publishing = False
    try:
        def idle():
            # Only a process that really holds the trace lock is "using" the package.  The lock file and the SQLite -wal/-shm files a killed
            # process leaves behind prove nothing (SQLite recovers them on the next open), so they must not block a new extraction.
            from vntext import os_lock
            if os_lock.is_held(root / ".mt" / "traceability.lock"):
                raise ValueError("Gói dịch đang được sử dụng; hãy đóng tác vụ đang dùng gói rồi thử lại.")
        idle()
        _sweep_interrupted_leftovers(root)
        reserved = ("translation.csv", "manifest.json", "review_only.csv", "raw_candidates.csv", "raw_unpatchable.csv",
                    "raw_candidates_rejected.csv", "technical_skipped.csv", "unity_analysis.json", "extract_report.txt",
                    "renpy_runtime_dynamic.json", "renpy_engine_common_exclusions.json", "images/report.json",
                    ".mt/traceability.sqlite3", ".mt/translate_status.json", ".mt/diagnostic_summary.json",
                    # Carried into the stage and republished: compared by content (a change DURING the run is still refused), never by a
                    # modification time that a removal made just before the run can share with its start.
                    "user_exclusions.json", "native_accounting.json")
        baseline = {Path(name): _digest(root / name) for name in reserved}
        stage = Path(tempfile.mkdtemp(prefix=".vntext-extract-", dir=root))
        status = root / "extract_status.json"
        prior_status = status.read_bytes() if status.is_file() else None
        marker = {"status": "RUNNING", "complete": False, "patch_scope": "NONE", "errors": 1}
        _write(status, json.dumps(marker).encode(), _digest(status))
        results = []
        produce(stage, results.append, lambda text: log(str(text).replace(str(stage), str(root))))
        if not results:
            raise ValueError("Extract did not return a terminal result")
        result = results[-1]
        if is_cancelled and is_cancelled() or result.get("error") == "cancelled":
            raise ValueError("cancelled")
        if not (stage / "manifest.json").is_file():
            _write(status, json.dumps({"status": "FAILED", "complete": False, "patch_scope": "NONE", "errors": 1}).encode(), _digest(status))
            for key in ("summary", "error", "diagnostic_path"):
                if isinstance(result.get(key), str):
                    result[key] = result[key].replace(str(stage), str(root))
            return result
        # Replace stale generated ledgers with empty ledgers, never remove user files.
        from vntext.package_io import write_csv
        for name in ("raw_candidates.csv", "raw_unpatchable.csv", "raw_candidates_rejected.csv", "technical_skipped.csv"):
            if (root / name).exists() and not (stage / name).exists():
                write_csv(stage / name, [])
        meta = stage / ".mt"
        meta.mkdir(exist_ok=True)
        from vntext.mt_ct2_status import snapshot_translate_status
        translation_status = snapshot_translate_status(stage)
        translation_status["complete"] = False
        (meta / "translate_status.json").write_text(json.dumps(translation_status), encoding="utf-8")
        if (root / "images/report.json").exists() and not (stage / "images/report.json").exists():
            (stage / "images").mkdir(exist_ok=True)
            (stage / "images/report.json").write_text(json.dumps({"schema": 1, "status": "EMPTY", "items": [], "total": 0, "translated": 0, "ocr_ready": 0}), encoding="utf-8")
        def relocate(value, key=""):
            if isinstance(value, dict):
                return {k: relocate(v, k) for k, v in value.items()}
            if isinstance(value, list):
                return [relocate(v, key) for v in value]
            if isinstance(value, str) and (key.endswith("path") or key in {"output", "root", "package_dir"}) and value.startswith(str(stage) + os.sep):
                return str(root) + value[len(str(stage)):]
            return value
        files = sorted(p for p in stage.rglob("*") if p.is_file())
        idle()
        expected = {}
        for path in files:
            relative = path.relative_to(stage)
            target = root / relative
            digest = _digest(target)
            if relative in baseline:
                if digest != baseline[relative]:
                    raise ValueError(f"Output changed externally during extraction: {target}")
            elif path.name != "extract_status.json" and target.exists() and target.stat().st_mtime_ns >= started:
                raise ValueError(f"Output changed externally during extraction: {target}")
            expected[relative] = digest
        # The readiness sidecar is committed last. An interrupted publish stays blocked.
        files.sort(key=lambda p: p.name == "extract_status.json")
        publishing = True
        for path in files:
            _no_links(path)
            relative = path.relative_to(stage)
            data = path.read_bytes()
            if path.suffix == ".json":
                document = json.loads(data)
                relocated = relocate(document)
                if relocated != document:
                    data = json.dumps(relocated, ensure_ascii=False, indent=2).encode("utf-8")
            _write(root / relative, data, expected[relative])
        log("Đã cập nhật các tệp kết quả; giữ nguyên tệp không liên quan, không lưu bản sao cũ.")
        result = relocate(result)
        for key in ("summary", "error", "diagnostic_action"):
            if isinstance(result.get(key), str):
                result[key] = result[key].replace(str(stage), str(root))
        return result
    except Exception as exc:
        if stage is not None:
            status = root / "extract_status.json"
            if str(exc) == "cancelled" and not publishing:
                # A user cancel before anything was published leaves the previous package exactly as it was: put its status back
                # (or remove the RUNNING marker when there was none) instead of calling the untouched package FAILED.
                if prior_status is not None:
                    _write(status, prior_status, _digest(status))
                else:
                    status.unlink(missing_ok=True)
            else:
                _write(status, json.dumps({"status": "FAILED", "complete": False, "patch_scope": "NONE", "errors": 1}).encode(), _digest(status))
        raise
    finally:
        with _HELD_LOCKS_GUARD:
            _HELD_LOCKS.discard(_held_key(lock))
        os.close(fd)
        try:
            lock.unlink(missing_ok=True)
        except OSError:
            pass          # another process already holds it again; the system lock, not the file, decides ownership
        if stage is not None:
            # Only the unique directory created by this call is disposable.
            if stage.parent != root or not stage.name.startswith(".vntext-extract-"):
                raise ValueError("Invalid owned extraction staging path")
            shutil.rmtree(stage)
