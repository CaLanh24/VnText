"""Headless RELEASE verification invoked from VNText Studio.exe."""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

from vntext.ui_progress import ProgressController, compute_percent, play_success_sound
from vntext.app_backend import VERSION, apply_translation_package, extract_project, write_package

def _app_root() -> Path:
    vntext_dir = Path(__file__).resolve().parent
    if vntext_dir.parent.name == "worker":
        return vntext_dir.parent.parent
    return vntext_dir.parent


def _artifacts_root() -> Path:
    root = _app_root()
    if (root / "tests" / "golden").is_dir():
        return root / "RELEASE_RUN"
    from vntext.runtime_paths import app_data_root

    return resolve_artifacts_root(
        app_data_root() / "_work",
        Path(tempfile.gettempdir()) / "VNTextStudio" / "_work",
    )


def _is_writable_directory(path: Path) -> bool:
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / f".write_probe_{os.getpid()}"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        return True
    except OSError:
        return False


def resolve_artifacts_root(primary: Path, fallback: Path) -> Path:
    for candidate in (primary, fallback):
        if _is_writable_directory(candidate):
            return candidate
    raise RuntimeError(f"No writable release artifact directory: {primary} or {fallback}")


def resolve_work_root(artifacts_root: Path) -> Path:
    """Return a writable release-verification directory below the artifact root."""
    primary = artifacts_root / "release_verify"
    for candidate in (primary, artifacts_root / f"release_verify_{os.getpid()}"):
        if _is_writable_directory(candidate):
            return candidate
    raise RuntimeError(f"No writable release verification directory under {artifacts_root}")


def _configured_work_root() -> Path:
    configured = os.environ.get("VNTEXT_RELEASE_VERIFY_RUN_ROOT", "").strip()
    if not configured:
        return resolve_work_root(_artifacts_root())
    root = Path(configured).expanduser().resolve()
    scope_root = os.environ.get("VNTEXT_ARTIFACT_SCOPE_ROOT", "").strip()
    dev_run_root = os.environ.get("VNTEXT_DEV_RUN_ROOT", "").strip()
    allowed_roots = [Path(value).expanduser().resolve() for value in (scope_root, dev_run_root) if value]
    if not allowed_roots or not any(root == allowed or allowed in root.parents for allowed in allowed_roots):
        raise RuntimeError("VNTEXT_RELEASE_VERIFY_RUN_ROOT must be under its registered scope or DEV_RUN")
    return root


WORK_ROOT = _configured_work_root()


def _report_path(default_name: str) -> Path:
    args = sys.argv[1:]
    for idx, arg in enumerate(args):
        if arg == "--report" and idx + 1 < len(args):
            return Path(args[idx + 1])
    return WORK_ROOT / default_name


def write_report(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def verify_workflow(work: Path) -> dict:
    from vntext.package_io import read_csv_rows_file
    from vntext.mt_ct2 import run_ct2_translate

    src = work / "input"
    src.mkdir(parents=True, exist_ok=True)
    sample = src / "sample.txt"
    sample.write_text("Hello world\nGood morning\nSaved line\n", encoding="utf-8")

    out = work / "package"
    if out.exists():
        shutil.rmtree(out, ignore_errors=True)

    extract_percents: list[int] = []

    def extract_progress(info):
        extract_percents.append(
            compute_percent(int(info.get("done") or 0), int(info.get("total") or 0))
        )

    main, review, stats = extract_project(str(src), "deep", extract_progress, "balanced")
    write_package(str(out), main, review, stats, True, enforce_symmetry=True)
    csv_path = out / "translation.csv"
    manifest_path = out / "manifest.json"
    if not csv_path.is_file() or not manifest_path.is_file():
        raise RuntimeError("Extract did not produce translation.csv/manifest.json")

    translate_percents: list[int] = []
    translate_backend = "ct2"
    translate_qa = None

    def translate_progress(info):
        translate_percents.append(
            compute_percent(int(info.get("done") or 0), int(info.get("total") or 0))
        )

    translate_result = run_ct2_translate(
        csv_path,
        allow_overwrite=False,
        progress=translate_progress,
        log=lambda msg: None,
    )
    if not translate_result.get("ok"):
        raise RuntimeError("CT2 batch failed: %r" % translate_result)
    translate_qa = translate_result.get("qa")

    _, rows = read_csv_rows_file(csv_path)
    filled = sum(1 for row in rows if (row.get("translation") or "").strip())
    if filled < 1:
        raise RuntimeError("%s did not fill any translation rows" % translate_backend)

    patch_percents: list[int] = []

    def patch_progress(info):
        patch_percents.append(
            compute_percent(int(info.get("done") or 0), int(info.get("total") or 0))
        )

    patch_out = work / "patch_out"
    if patch_out.exists():
        shutil.rmtree(patch_out, ignore_errors=True)
    report = apply_translation_package(
        str(csv_path),
        str(manifest_path),
        str(src),
        str(patch_out),
        patch_progress,
    )
    patched = patch_out / "COPY_TO_GAME_ROOT" / "sample.txt"
    if not patched.is_file():
        raise RuntimeError("Patch did not produce COPY_TO_GAME_ROOT/sample.txt")

    patched_text = patched.read_text(encoding="utf-8-sig")
    if "Hello world" in patched_text and "Good morning" in patched_text and filled >= 2:
        raise RuntimeError("Patch did not apply translations to sample.txt")

    return {
        "backend": translate_backend,
        "extract_rows": len(main),
        "extract_progress_max": max(extract_percents or [0]),
        "translate_filled": filled,
        "translate_progress_max": max(translate_percents or [0]),
        "translate_qa": translate_qa,
        "patch_report_lines": len(report),
        "patch_progress_max": max(patch_percents or [0]),
        "patched_sample": patched_text.strip().splitlines()[:3],
        "traceability": {
            "status": "TRACE_NOT_ENABLED",
            "reason": "The headless verifier calls isolated extract/translate/patch functions directly.",
            "impact": "Workflow output is verified, but this run has no per-entry TraceStore stage/root-cause coverage.",
        },
    }


def verify_progress_and_sound() -> dict:
    ctrl = ProgressController()
    ctrl.begin("Kiểm tra RELEASE", "Đang chạy…")
    snap = ctrl.update(
        {
            "done": 1,
            "total": 3,
            "file": "sample.txt",
            "phase": "extract",
            "elapsed": 1.0,
            "eta": 2.0,
        }
    )
    mid_percent = snap.percent
    done = ctrl.complete(True, summary="Hoàn tất kiểm tra")
    play_success_sound()
    if mid_percent >= 100:
        raise RuntimeError("Progress hit 100%% before complete")
    if done.percent != 100 or done.status != "done":
        raise RuntimeError("Progress complete snapshot invalid")
    return {"mid_percent": mid_percent, "done_percent": done.percent, "sound": "ok"}


def run_release_verify() -> int:
    report_path = _report_path("release_verify.json")
    work = WORK_ROOT if os.environ.get("VNTEXT_RELEASE_VERIFY_RUN_ROOT") else WORK_ROOT / "run"
    if work.exists():
        shutil.rmtree(work, ignore_errors=True)
    work.mkdir(parents=True, exist_ok=True)

    payload = {"version": VERSION, "steps": {}, "ok": False}
    try:
        payload["steps"]["progress_sound"] = verify_progress_and_sound()
        payload["steps"]["workflow"] = verify_workflow(work)
        payload["ok"] = True
    except Exception as exc:
        payload["error"] = str(exc)
        write_report(report_path, payload)
        return 1
    write_report(report_path, payload)
    return 0


def run_release_verify_qml() -> int:
    """Headless QML shell load check for RELEASE EXE."""
    from PySide6.QtQuick import QQuickView
    from PySide6.QtWidgets import QApplication

    from qml_ui.bridge import create_view

    report_path = _report_path("release_verify_qml.json")
    app = QApplication.instance() or QApplication([])
    view = None
    backend = None
    payload = {"version": VERSION, "ok": False}
    try:
        _app, view, backend = create_view()
        if view.status() != QQuickView.Ready:
            raise RuntimeError(f"QML not ready: {view.errors()}")
        root = view.rootObject()
        if root is None:
            raise RuntimeError("QML root object missing")
        payload["ok"] = True
        payload["marker"] = str(root.property("marker") or "")
    except Exception as exc:
        payload["error"] = str(exc)
        write_report(report_path, payload)
        return 1
    finally:
        if backend is not None:
            backend.window.close()
        if view is not None:
            view.close()
    write_report(report_path, payload)
    return 0


def run_release_version() -> int:
    report_path = _report_path("release_version.json")
    write_report(report_path, {"version": VERSION, "ok": True})
    return 0


def run_release_verify_update() -> int:
    from vntext.app_update import check_for_update, download_pending_update, schedule_restart_for_update
    from vntext.runtime_paths import updates_dir

    report_path = _report_path("release_update.json")
    marker = WORK_ROOT / "update_e2e.marker"
    marker.parent.mkdir(parents=True, exist_ok=True)

    pending = updates_dir() / "VNText Studio.new.exe"
    meta = pending.with_suffix(".json")
    if pending.is_file():
        pending.unlink(missing_ok=True)
    if meta.is_file():
        meta.unlink(missing_ok=True)

    payload = {"from_version": VERSION, "ok": False}
    try:
        info = check_for_update(VERSION)
        if not info:
            raise RuntimeError("No update detected for version %s" % VERSION)
        payload["update"] = info
        download_pending_update(info)
        marker.write_text(
            json.dumps({"started": time.time(), "target": info.get("version")}, indent=2),
            encoding="utf-8",
        )
        write_report(report_path, {**payload, "stage": "downloaded", "ok": True})
        schedule_restart_for_update()
    except Exception as exc:
        payload["error"] = str(exc)
        write_report(report_path, payload)
        return 1
    return 0
