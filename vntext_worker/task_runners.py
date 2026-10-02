"""Bridge vntext.app_tasks to worker NDJSON protocol."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from vntext.app_tasks import (
    resolve_package_with_csv,
    resolve_package_with_manifest,
    run_cloud_repair_export_task,
    run_cloud_repair_import_task,
    run_external_translation_import_task,
    run_extract_task,
    run_patch_task,
    run_translate_ct2_task,
    run_translate_keys_ct2_task,
)
from vntext.app_workflow import has_translations
from vntext_worker.protocol import emit_complete, emit_error, emit_log, emit_progress


class WorkerCancelled(Exception):
    """Raised when host requests cancel during a long task."""


def _check_cancel(is_cancelled: Callable[[], bool]) -> None:
    if is_cancelled():
        raise WorkerCancelled()


def _make_callbacks(
    task_id: str,
    is_cancelled: Callable[[], bool],
):
    def progress(info: dict) -> None:
        _check_cancel(is_cancelled)
        emit_progress(
            task_id,
            done=int(info.get("done") or 0),
            total=int(info.get("total") or 0),
            step=str(info.get("step") or ""),
            item=str(info.get("item") or ""),
            eta=str(info.get("eta") or "") or None,
        )

    def log(text: str) -> None:
        emit_log(task_id, text)

    def complete(payload: dict) -> None:
        extra: dict[str, Any] = {}
        if "complete" in payload:
            extra["complete"] = bool(payload.get("complete"))
            extra["pending"] = int(payload.get("pending") or 0)
            extra["review_only"] = int(payload.get("review_only") or 0)
            extra["blocked"] = int(payload.get("blocked") or 0)
            extra["translated"] = int(payload.get("translated") or 0)
        if "applied" in payload:
            extra["applied"] = int(payload.get("applied") or 0)
        if "copied_vi" in payload:
            extra["copied_vi"] = int(payload.get("copied_vi") or 0)
        if "human_review_required_count" in payload:
            value = payload.get("human_review_required_count")
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError("human_review_required_count must be a non-negative integer")
            extra["human_review_required_count"] = value
        if "renpy_sdk_missing" in payload:
            extra["renpy_sdk_missing"] = bool(payload.get("renpy_sdk_missing"))
        if "pipeline_liveness" in payload:
            extra["pipeline_liveness"] = bool(payload.get("pipeline_liveness"))
        for key in (
            "diagnostic_path",
            "diagnostic_stage",
            "diagnostic_root_cause",
            "diagnostic_action",
            "diagnostic_status",
            "patch_engine",
            "patch_delivery",
            "patch_payload_path",
            "patch_install_instructions",
        ):
            if payload.get(key) not in (None, ""):
                extra[key] = str(payload[key])
        if payload.get("diagnostic_affected_count") is not None:
            value = payload.get("diagnostic_affected_count")
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError("diagnostic_affected_count must be a non-negative integer")
            extra["diagnostic_affected_count"] = value
        emit_complete(
            task_id,
            ok=bool(payload.get("ok")),
            summary=str(payload.get("summary") or ""),
            error=str(payload.get("error") or ""),
            **extra,
        )

    return progress, log, complete


def _finish_cancelled(task_id: str) -> None:
    emit_log(task_id, "Đã hủy theo yêu cầu host.")
    emit_complete(task_id, ok=False, error="cancelled")


def run_analyze_worker(
    task_id: str,
    params: dict[str, Any],
    is_cancelled: Callable[[], bool],
) -> None:
    """Run the read-only Unity inventory through the stable worker boundary."""

    src = str(params.get("src") or "").strip()
    report_out = str(params.get("report_out") or params.get("out") or "").strip()
    if not src:
        emit_error(task_id, "Thiếu params.src (đường dẫn game)")
        emit_complete(task_id, ok=False, error="Thiếu params.src")
        return
    if is_cancelled():
        _finish_cancelled(task_id)
        return

    import json

    from vntext.unity_analyzer import AnalyzerOptions, UnityAnalysisCancelled, analyze_unity_game

    def analyzer_progress(info: dict[str, Any]) -> None:
        emit_progress(
            task_id,
            done=int(info.get("done") or 0),
            total=int(info.get("total") or 0),
            step=str(info.get("step") or ""),
            item=str(info.get("item") or ""),
        )

    try:
        options = AnalyzerOptions(
            include_sha256=bool(params.get("include_sha256", True)),
            probe_unity_objects=bool(params.get("probe_unity_objects", True)),
            max_unity_probe_bytes=int(params.get("max_unity_probe_bytes", 128 * 1024 * 1024)),
            sample_bytes=int(params.get("sample_bytes", 1024 * 1024)),
            candidate_limit=int(params.get("candidate_limit", 20)),
        )
        report = analyze_unity_game(
            src,
            options=options,
            progress_callback=analyzer_progress,
            is_cancelled=is_cancelled,
        )
        if is_cancelled():
            _finish_cancelled(task_id)
            return

        output_path = None
        if report_out:
            scan_root = Path(str(report.get("scan_root") or src)).resolve()
            output_path = Path(report_out).expanduser()
            if output_path.suffix.lower() != ".json":
                output_path = output_path / "unity_analysis.json"
            output_path = output_path.resolve()
            try:
                output_path.relative_to(scan_root)
            except ValueError:
                output_path.parent.mkdir(parents=True, exist_ok=True)
                output_path.write_text(
                    json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8",
                )
            else:
                raise ValueError("report_out phải nằm ngoài thư mục game đang phân tích")

        unity = report.get("unity") or {}
        summary = (
            f"Unity analyzer: {unity.get('status', 'NOT_DETECTED')}; "
            f"resources={report.get('summary', {}).get('resource_count', 0)}; "
            f"unknown={report.get('summary', {}).get('unknown_resources', 0)}; "
            f"scan_errors={report.get('summary', {}).get('scan_error_count', 0)}"
        )
        if output_path:
            summary += f"; report={output_path}"
        emit_log(task_id, summary)
        emit_complete(
            task_id,
            ok=bool(report.get("inventory_complete")),
            summary=summary,
            error="; ".join(str(item.get("error") or "") for item in report.get("scan_errors", [])),
        )
    except UnityAnalysisCancelled:
        _finish_cancelled(task_id)
    except Exception as exc:
        emit_error(task_id, str(exc))
        emit_complete(task_id, ok=False, error=str(exc))


def run_extract_worker(
    task_id: str,
    params: dict[str, Any],
    is_cancelled: Callable[[], bool],
) -> None:
    src = str(params.get("src") or "").strip()
    out = str(params.get("out") or "").strip()
    mode = str(params.get("mode") or "deep").strip() or "deep"
    level = str(params.get("level") or "balanced").strip() or "balanced"
    separate_review = bool(params.get("separate_review", True))
    renpy_sdk_path = str(params.get("renpy_sdk_path") or "").strip()
    renpy_sdk_action = str(params.get("renpy_sdk_action") or "auto").strip() or "auto"

    if not src:
        emit_error(task_id, "Thiếu params.src (đường dẫn game)")
        emit_complete(task_id, ok=False, error="Thiếu params.src")
        return
    if not out:
        emit_error(task_id, "Thiếu params.out (thư mục xuất)")
        emit_complete(task_id, ok=False, error="Thiếu params.out")
        return

    progress, log, complete = _make_callbacks(task_id, is_cancelled)
    try:
        run_extract_task(
            src,
            out,
            mode,
            level,
            separate_review,
            renpy_sdk_path=renpy_sdk_path,
            renpy_sdk_action=renpy_sdk_action,
            progress=progress,
            log=log,
            complete=complete,
            is_cancelled=is_cancelled,
        )
    except WorkerCancelled:
        _finish_cancelled(task_id)


def run_translate_worker(
    task_id: str,
    params: dict[str, Any],
    is_cancelled: Callable[[], bool],
) -> None:
    out = str(params.get("out") or "").strip()
    csv_raw = params.get("csv_path")
    model_dir = str(params.get("model_dir") or "").strip()
    model = str(params.get("model") or "ct2").strip().lower()
    overwrite = bool(params.get("overwrite", False))
    human_review_required = params.get("human_review_required") is True

    if model != "ct2":
        msg = f"Model dịch không được hỗ trợ: {model}; hiện chỉ có CT2/OPUS-MT."
        emit_error(task_id, msg)
        emit_complete(task_id, ok=False, error=msg)
        return

    if csv_raw:
        csv_path = Path(str(csv_raw))
        package_dir = csv_path.parent
    else:
        if not out:
            emit_error(task_id, "Thiếu params.out hoặc csv_path")
            emit_complete(task_id, ok=False, error="Thiếu params.out")
            return
        resolved = resolve_package_with_csv(out)
        if resolved is None:
            msg = "Không tìm thấy translation.csv trong thư mục xuất"
            emit_error(task_id, msg)
            emit_complete(task_id, ok=False, error=msg)
            return
        package_dir, csv_path = resolved

    progress, log, complete = _make_callbacks(task_id, is_cancelled)
    keys_raw = params.get("keys")
    keys = [str(k) for k in keys_raw if k] if isinstance(keys_raw, list) else []
    try:
        if keys:
            run_translate_keys_ct2_task(
                csv_path,
                package_dir,
                keys,
                model_dir=model_dir,
                human_review_required=human_review_required,
                progress=progress,
                log=log,
                complete=complete,
                is_cancelled=is_cancelled,
            )
        else:
            run_translate_ct2_task(
                csv_path,
                package_dir,
                overwrite,
                model_dir=model_dir,
                human_review_required=human_review_required,
                progress=progress,
                log=log,
                complete=complete,
                is_cancelled=is_cancelled,
            )
    except WorkerCancelled:
        _finish_cancelled(task_id)


def run_patch_worker(
    task_id: str,
    params: dict[str, Any],
    is_cancelled: Callable[[], bool],
) -> None:
    cloud_action = str(params.get("cloud_action") or "").strip().lower()
    if cloud_action in {"export", "import", "external_import"}:
        run_cloud_repair_worker(task_id, params, is_cancelled)
        return

    src = str(params.get("src") or "").strip()
    out = str(params.get("out") or "").strip()
    csv_raw = params.get("csv_path")
    manifest_raw = params.get("manifest_path")

    if not src:
        emit_error(task_id, "Thiếu params.src (đường dẫn game)")
        emit_complete(task_id, ok=False, error="Thiếu params.src")
        return
    if not out and not (csv_raw and manifest_raw):
        emit_error(task_id, "Thiếu params.out hoặc csv_path/manifest_path")
        emit_complete(task_id, ok=False, error="Thiếu params.out")
        return

    if csv_raw and manifest_raw:
        csv_path = Path(str(csv_raw))
        manifest_path = Path(str(manifest_raw))
        package_dir = csv_path.parent
        patch_out = out or str(package_dir / "Patch_Viet_Hoa")
    else:
        resolved = resolve_package_with_manifest(out)
        if resolved is None:
            msg = "Không tìm thấy translation.csv + manifest.json trong thư mục xuất"
            emit_error(task_id, msg)
            emit_complete(task_id, ok=False, error=msg)
            return
        package_dir, csv_path, manifest_path = resolved
        patch_out = str(package_dir / "Patch_Viet_Hoa")

    if not has_translations(csv_path):
        msg = "translation.csv chưa có bản dịch — hãy dịch trước khi tạo patch"
        emit_error(task_id, msg)
        emit_complete(task_id, ok=False, error=msg)
        return

    progress, log, complete = _make_callbacks(task_id, is_cancelled)

    from vntext.patch_gate import audit_patch_package, format_preflight_log

    try:
        preflight = audit_patch_package(csv_path, manifest_path, game_root=src)
        log(format_preflight_log(preflight))
        if preflight.get("eligible", 0) <= 0:
            msg = "Không có dòng hợp lệ để patch sau kiểm tra chất lượng"
            emit_error(task_id, msg)
            emit_complete(task_id, ok=False, error=msg)
            return
    except Exception as exc:
        msg = f"Kiểm tra patch thất bại: {exc}"
        emit_error(task_id, msg)
        emit_complete(task_id, ok=False, error=msg)
        return

    try:
        run_patch_task(
            csv_path,
            manifest_path,
            src,
            patch_out,
            progress=progress,
            log=log,
            complete=complete,
            # ``patch_out`` is already the worker's package-level
            # Patch_Viet_Hoa directory.  Pass it as an override so the
            # worker contract stays flat (COPY_TO_GAME_ROOT directly below
            # Patch_Viet_Hoa) instead of creating a versioned subdirectory
            # that callers and installers cannot find.
            patch_out_override=patch_out,
            enable_trace=True,
        )
    except WorkerCancelled:
        _finish_cancelled(task_id)


def run_cloud_repair_worker(
    task_id: str,
    params: dict[str, Any],
    is_cancelled: Callable[[], bool],
) -> None:
    """Run provider-neutral cloud repair through the additive v1 worker route."""

    action = str(params.get("cloud_action") or "").strip().lower()
    progress, log, complete = _make_callbacks(task_id, is_cancelled)
    if is_cancelled():
        _finish_cancelled(task_id)
        return

    if action == "export":
        package_dir = str(params.get("package_dir") or "").strip()
        output_zip = str(params.get("output_zip") or "").strip()
        if not package_dir or not output_zip:
            msg = "Thiếu package_dir hoặc output_zip cho Cloud Repair export"
            emit_error(task_id, msg)
            emit_complete(task_id, ok=False, error=msg)
            return
        try:
            run_cloud_repair_export_task(
                Path(package_dir),
                Path(output_zip),
                log=log,
                complete=complete,
            )
        except WorkerCancelled:
            _finish_cancelled(task_id)
        return

    if action == "import":
        package_zip = str(params.get("package_zip") or "").strip()
        result_csv = str(params.get("result_csv") or "").strip()
        output_csv = str(params.get("output_csv") or "").strip()
        if not package_zip or not result_csv or not output_csv:
            msg = "Thiếu package_zip, result_csv hoặc output_csv cho Cloud Repair import"
            emit_error(task_id, msg)
            emit_complete(task_id, ok=False, error=msg)
            return
        try:
            run_cloud_repair_import_task(
                Path(package_zip),
                Path(result_csv),
                Path(output_csv),
                log=log,
                complete=complete,
            )
        except WorkerCancelled:
            _finish_cancelled(task_id)
        return

    if action == "external_import":
        target_csv = str(params.get("target_csv") or "").strip()
        source_csv = str(params.get("source_csv") or "").strip()
        if not target_csv or not source_csv:
            msg = "Thiếu target_csv hoặc source_csv để nhập bản dịch cũ"
            emit_error(task_id, msg)
            emit_complete(task_id, ok=False, error=msg)
            return
        try:
            run_external_translation_import_task(
                Path(target_csv),
                Path(source_csv),
                log=log,
                complete=complete,
            )
        except WorkerCancelled:
            _finish_cancelled(task_id)
        return

    msg = f"Thao tác nhập CSV không được hỗ trợ: {action or 'trống'}"
    emit_error(task_id, msg)
    emit_complete(task_id, ok=False, error=msg)
