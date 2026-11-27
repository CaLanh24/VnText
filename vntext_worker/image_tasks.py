"""Image review tasks keep image output separate from script CSV/patch proof."""
import json
import shutil
from pathlib import Path
from vntext.image_text import _regular, _image, recognize_image, render_image, discover_images
from vntext_worker.protocol import emit_complete
from vntext.renpy_archive import RenPyArchive, RenPyArchiveError, parse_member_reference


def run_image_worker(task_id, task, params, is_cancelled):
    if task == 'image_batch':
        from vntext.image_batch import run_image_batch, translate_cached_images
        from vntext_worker.protocol import emit_progress
        if params.get('cached_only'):
            result = translate_cached_images(params['out'], source=params['src'], is_cancelled=is_cancelled,
                progress=lambda info: emit_progress(task_id, **info))
        elif params.get('after_extract'):
            # Background image scan that follows a finished text extraction: OCR only, never touches translation.csv.
            import time
            from vntext.image_batch import clear_empty_image_stub
            from vntext_worker.protocol import emit_log
            clear_empty_image_stub(params['out'])
            started = time.monotonic()
            result = run_image_batch(params['src'], params['out'], sources=None if Path(params['src']).is_dir() else [params['src']],
                is_cancelled=is_cancelled, translate=False, progress=lambda info: emit_progress(task_id, **info))
            failed = int(result.get('ocr_failed') or 0)         # the no-images shortcut result carries no failure count
            emit_log(task_id, f"Quét ảnh: {round(time.monotonic() - started, 1)} giây; {result['total']} ảnh có chữ, {failed} ảnh chưa nhận dạng được.")
            summary = (f"Quét ảnh xong: {result['total']} ảnh có chữ" if result['total'] else "Quét ảnh xong: không thấy ảnh có chữ")                 + (f"; {failed} ảnh chưa nhận dạng được" if failed else "") + ". Bản dịch text không bị ảnh hưởng."
            emit_complete(task_id, ok=not result['cancelled'], summary=summary, error='cancelled' if result['cancelled'] else '')
            return
        else:
            result = run_image_batch(params['src'], params['out'], sources=None if Path(params['src']).is_dir() else [params['src']],
                is_cancelled=is_cancelled, progress=lambda info: emit_progress(task_id, **info))
        summary = f"Ảnh: {result['translated']} bản dịch nháp, {result['untranslated']} chưa dịch. {result['output']}"
        emit_complete(task_id, ok=not result['cancelled'], summary=summary,
                      error='cancelled' if result['cancelled'] else '')
        return
    root = _regular(params["out"])
    if root.exists():
        raise ValueError("Thư mục bản xem lại ảnh phải mới; kết quả đã có được giữ nguyên.")
    if is_cancelled(): raise ValueError("cancelled")
    if task in {"image_delivery", "image_apply", "image_rollback"}:
        from vntext.image_delivery import prepare_image_delivery, install_image_delivery, rollback_image_delivery
        if task == "image_delivery":
            result = prepare_image_delivery(params["document"], params["rendered"], params["game_root"], root)
            summary = "Đã tạo gói ảnh locale Vietnamese. Cài vào bản sao game; cần chọn ngôn ngữ vietnamese trong game."
        elif task == "image_apply":
            result = install_image_delivery(params["package"], params["game_copy"], root)
            summary = "Đã cài ảnh vào bản sao game và kiểm hash đọc lại. Chưa xác nhận game đang chọn Vietnamese."
        else:
            result = rollback_image_delivery(params["transaction"])
            root.mkdir(parents=True)
            summary = "Đã gỡ đúng ảnh của giao dịch; giữ nguyên ảnh nguồn."
        (root / "delivery_result.json").write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
    elif task == "image_inventory":
        from vntext.image_batch import run_image_batch
        result = run_image_batch(params['src'], root, translate=False, is_cancelled=is_cancelled)
        report_path = Path(result['output']) / 'report.json' if result['output'] else None
        report = json.loads(report_path.read_text(encoding='utf-8')) if report_path else {'items': []}
        inventory = {'image_paths': [item['source'] for item in report['items'] if item.get('text_detected')],
                     'complete': not result['cancelled'] and not result['ocr_failed'], 'errors': report.get('inventory_errors', [])}
        root.mkdir(parents=True, exist_ok=True)
        (root / "image_index.json").write_text(json.dumps(inventory,ensure_ascii=False,indent=2),encoding="utf-8")
        qualifier = f"; danh sách tệp chưa đầy đủ do {len(inventory['errors'])} tệp đóng gói lỗi hoặc không hỗ trợ" if not inventory["complete"] else ""
        summary = f"Tìm thấy {len(inventory['image_paths'])} ảnh có chữ{qualifier}. Các ảnh không phát hiện chữ không được xuất."
    elif task == "image_extract":
        archive_ref = parse_member_reference(params["src"])
        try:
            if archive_ref:
                container, member = archive_ref
                archive = RenPyArchive(container)
                item = archive.read_member(member)
                if Path(member).suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp"}:
                    raise ValueError("RPA member không phải ảnh tĩnh được hỗ trợ.")
                root.mkdir(parents=True)
                source_path = root / ("archive-source" + Path(member).suffix.lower())
                with source_path.open("xb") as stream: stream.write(item["content"])
                document = recognize_image(source_path, is_cancelled=is_cancelled)
                document.update(source_container_path=str(container), source_container_sha256=item["container_sha256"],
                                source_member_name=member, source_member_sha256=item["member_sha256"])
            else:
                document = recognize_image(params["src"], is_cancelled=is_cancelled)
                root.mkdir(parents=True)
            source, image, digest = _image(document["source_path"])
            if digest != document["source_sha256"]: raise ValueError("Ảnh thay đổi trong lúc nhận dạng chữ; hãy Lấy text lại.")
            if is_cancelled(): raise ValueError("cancelled")
            image.save(root / "source-preview.png")
            (root / "image_text.json").write_text(json.dumps(document,ensure_ascii=False,indent=2),encoding="utf-8")
        except Exception:
            if root.exists(): shutil.rmtree(root)
            raise
        summary = "Không thấy chữ; hãy kiểm tra ảnh hoặc vùng cắt rồi thử lại." if not document["regions"] else f"Đã nhận dạng {len(document['regions'])} vùng chữ — cần sửa chữ và tọa độ, duyệt nền phẳng và bản dịch trước khi dựng ảnh."
    else:
        document = params["document"]
        if is_cancelled(): raise ValueError("cancelled")
        container_path = document.get("source_container_path")
        if container_path:
            archive = RenPyArchive(container_path)
            current = archive.read_member(document.get("source_member_name", ""))
            if current["container_sha256"] != document.get("source_container_sha256") or current["member_sha256"] != document.get("source_member_sha256"):
                raise ValueError("Tệp đóng gói của game đã đổi; hãy Lấy text lại rồi nhận dạng chữ lại.")
        source, preview, digest = _image(document["source_path"])
        if digest != document["source_sha256"]: raise ValueError("Ảnh nguồn đã thay đổi; hãy xem lại.")
        render_image(document, root / "translated.png", params["font_path"])
        preview.save(root / "source-preview.png")
        (root / "image_text.json").write_text(json.dumps(document,ensure_ascii=False,indent=2),encoding="utf-8")
        summary = "Đã dựng ảnh từ bản dịch đã duyệt; hãy mở ảnh xem trước để kiểm tra trước khi dùng. Ảnh nguồn giữ nguyên."
    emit_complete(task_id,ok=True,summary=summary)
