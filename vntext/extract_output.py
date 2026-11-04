"""Refresh generated output without clearing a user-selected directory."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
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


def _take_lock(lock: Path) -> int:
    from vntext.traceability import _pid_alive
    for _ in range(2):
        _no_links(lock)
        try:
            fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            before = lock.read_bytes()
            try:
                pid = int(json.loads(before)["pid"])
            except (ValueError, KeyError, TypeError) as exc:
                raise ValueError("Cannot verify the existing output lock; preserved it") from exc
            if pid <= 0 or _pid_alive(pid):
                raise ValueError("Output is in use by another extraction")
            if lock.read_bytes() != before:
                raise ValueError("Output lock changed externally")
            lock.unlink()
            continue
        try:
            os.write(fd, json.dumps({"pid": os.getpid()}).encode())
            os.fsync(fd)
        except Exception:
            os.close(fd)
            lock.unlink(missing_ok=True)
            raise
        return fd
    raise ValueError("Cannot acquire extraction output lock")


def refresh_extract(src, out, produce, complete, log, is_cancelled=None):
    # Notify the host only after releasing the package lock and owned staging.
    complete(_refresh_extract(src, out, produce, log, is_cancelled))


def _refresh_extract(src, out, produce, log, is_cancelled=None):
    """Generate privately, then overwrite only emitted files; retain no old backup."""
    started = time.time_ns()
    root = Path(os.path.abspath(out))
    _no_links(root)
    source = Path(src).resolve()
    source = source if source.is_dir() else source.parent
    if root == source or root.is_relative_to(source) or source.is_relative_to(root):
        raise ValueError("Thư mục xuất phải nằm riêng, không chứa hoặc nằm trong thư mục game.")
    root.mkdir(parents=True, exist_ok=True)
    lock = root / ".vntext-extract.lock"
    fd = _take_lock(lock)
    stage = None
    try:
        def idle():
            for name in ("traceability.lock", "traceability.sqlite3-wal", "traceability.sqlite3-shm"):
                if (root / ".mt" / name).exists():
                    raise ValueError("Gói dịch đang được sử dụng; hãy đóng tác vụ đang dùng gói rồi thử lại.")
        idle()
        reserved = ("translation.csv", "manifest.json", "review_only.csv", "raw_candidates.csv", "raw_unpatchable.csv",
                    "raw_candidates_rejected.csv", "technical_skipped.csv", "unity_analysis.json", "extract_report.txt",
                    "renpy_runtime_dynamic.json", "renpy_engine_common_exclusions.json", "images/report.json",
                    ".mt/traceability.sqlite3", ".mt/translate_status.json", ".mt/diagnostic_summary.json")
        baseline = {Path(name): _digest(root / name) for name in reserved}
        stage = Path(tempfile.mkdtemp(prefix=".vntext-extract-", dir=root))
        status = root / "extract_status.json"
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
        log("Đã cập nhật các file kết quả; giữ nguyên file không liên quan, không lưu bản sao cũ.")
        result = relocate(result)
        for key in ("summary", "error", "diagnostic_action"):
            if isinstance(result.get(key), str):
                result[key] = result[key].replace(str(stage), str(root))
        return result
    except Exception:
        if stage is not None:
            status = root / "extract_status.json"
            _write(status, json.dumps({"status": "FAILED", "complete": False, "patch_scope": "NONE", "errors": 1}).encode(), _digest(status))
        raise
    finally:
        os.close(fd)
        lock.unlink(missing_ok=True)
        if stage is not None:
            # Only the unique directory created by this call is disposable.
            if stage.parent != root or not stage.name.startswith(".vntext-extract-"):
                raise ValueError("Invalid owned extraction staging path")
            shutil.rmtree(stage)
