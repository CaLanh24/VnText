"""Image review tasks keep image output separate from script CSV/patch proof."""
import json
from pathlib import Path
from vntext.image_text import _regular, _image, recognize_image, render_image, discover_images
from vntext_worker.protocol import emit_complete


def run_image_worker(task_id, task, params, is_cancelled):
    root = _regular(params["out"])
    if root.exists():
        raise ValueError("Thư mục review ảnh phải mới; giữ nguyên kết quả đã có.")
    if is_cancelled(): raise ValueError("cancelled")
    if task == "image_inventory":
        inventory = discover_images(params["src"], is_cancelled=is_cancelled)
        root.mkdir(parents=True)
        (root / "image_index.json").write_text(json.dumps(inventory,ensure_ascii=False,indent=2),encoding="utf-8")
        summary = f"Tìm thấy {len(inventory['image_paths'])} ảnh ứng viên; chưa xác nhận có chữ. Chọn ảnh để OCR."
    elif task == "image_extract":
        document = recognize_image(params["src"], is_cancelled=is_cancelled)
        source, image, digest = _image(document["source_path"])
        if digest != document["source_sha256"]: raise ValueError("Ảnh thay đổi trong lúc OCR; hãy lấy lại text.")
        if is_cancelled(): raise ValueError("cancelled")
        root.mkdir(parents=True)
        image.save(root / "source-preview.png")
        (root / "image_text.json").write_text(json.dumps(document,ensure_ascii=False,indent=2),encoding="utf-8")
        summary = "Không thấy text; kiểm ảnh/crop rồi thử lại." if not document["regions"] else f"OCR {len(document['regions'])} region — cần sửa text/tọa độ, duyệt nền phẳng và bản dịch trước render."
    else:
        document = params["document"]
        if is_cancelled(): raise ValueError("cancelled")
        source, preview, digest = _image(document["source_path"])
        if digest != document["source_sha256"]: raise ValueError("Ảnh nguồn đã thay đổi; review lại.")
        render_image(document, root / "translated.png", params["font_path"])
        preview.save(root / "source-preview.png")
        (root / "image_text.json").write_text(json.dumps(document,ensure_ascii=False,indent=2),encoding="utf-8")
        summary = "Đã dựng ảnh từ bản dịch duyệt; mở preview để kiểm trước khi dùng. Ảnh nguồn giữ nguyên."
    emit_complete(task_id,ok=True,summary=summary)
