"""Image review tasks keep image output separate from script CSV/patch proof."""
import json
import shutil
from pathlib import Path
from vntext.image_text import _regular, _image, recognize_image, render_image, discover_images
from vntext_worker.protocol import emit_complete
from vntext.renpy_archive import RenPyArchive, RenPyArchiveError, parse_member_reference


def run_image_worker(task_id, task, params, is_cancelled):
    root = _regular(params["out"])
    if root.exists():
        raise ValueError("Thư mục review ảnh phải mới; giữ nguyên kết quả đã có.")
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
        inventory = discover_images(params["src"], is_cancelled=is_cancelled)
        root.mkdir(parents=True)
        (root / "image_index.json").write_text(json.dumps(inventory,ensure_ascii=False,indent=2),encoding="utf-8")
        qualifier = f"; inventory chưa đầy đủ do {len(inventory['errors'])} archive lỗi/không hỗ trợ" if not inventory["complete"] else ""
        summary = f"Tìm thấy {len(inventory['image_paths'])} ảnh ứng viên; chưa xác nhận có chữ{qualifier}. Chọn ảnh để OCR."
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
            if digest != document["source_sha256"]: raise ValueError("Ảnh thay đổi trong lúc OCR; hãy lấy lại text.")
            if is_cancelled(): raise ValueError("cancelled")
            image.save(root / "source-preview.png")
            (root / "image_text.json").write_text(json.dumps(document,ensure_ascii=False,indent=2),encoding="utf-8")
        except Exception:
            if root.exists(): shutil.rmtree(root)
            raise
        summary = "Không thấy text; kiểm ảnh/crop rồi thử lại." if not document["regions"] else f"OCR {len(document['regions'])} region — cần sửa text/tọa độ, duyệt nền phẳng và bản dịch trước render."
    else:
        document = params["document"]
        if is_cancelled(): raise ValueError("cancelled")
        container_path = document.get("source_container_path")
        if container_path:
            archive = RenPyArchive(container_path)
            current = archive.read_member(document.get("source_member_name", ""))
            if current["container_sha256"] != document.get("source_container_sha256") or current["member_sha256"] != document.get("source_member_sha256"):
                raise ValueError("RPA container/member đã đổi; hãy tạo lại inventory và OCR.")
        source, preview, digest = _image(document["source_path"])
        if digest != document["source_sha256"]: raise ValueError("Ảnh nguồn đã thay đổi; review lại.")
        render_image(document, root / "translated.png", params["font_path"])
        preview.save(root / "source-preview.png")
        (root / "image_text.json").write_text(json.dumps(document,ensure_ascii=False,indent=2),encoding="utf-8")
        summary = "Đã dựng ảnh từ bản dịch duyệt; mở preview để kiểm trước khi dùng. Ảnh nguồn giữ nguyên."
    emit_complete(task_id,ok=True,summary=summary)
