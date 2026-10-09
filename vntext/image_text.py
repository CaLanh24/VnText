"""Review-only Windows OCR and approved flat-panel image output; never writes input."""
from __future__ import annotations
import io
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import time

MAX_PIXELS = 16_000_000
OCR_SCRIPT = "param([string]$ImagePath)\n[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)\n$ErrorActionPreference = 'Stop'\nAdd-Type -AssemblyName System.Runtime.WindowsRuntime\n[Windows.Storage.StorageFile,Windows.Storage,ContentType=WindowsRuntime] > $null\n[Windows.Graphics.Imaging.BitmapDecoder,Windows.Graphics.Imaging,ContentType=WindowsRuntime] > $null\n[Windows.Graphics.Imaging.SoftwareBitmap,Windows.Graphics.Imaging,ContentType=WindowsRuntime] > $null\n[Windows.Media.Ocr.OcrEngine,Windows.Foundation,ContentType=WindowsRuntime] > $null\n[Windows.Globalization.Language,Windows.Globalization,ContentType=WindowsRuntime] > $null\nfunction Await($Operation, $Type) {\n $method = [System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object {$_.Name -eq 'AsTask' -and $_.IsGenericMethod -and $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1'} | Select-Object -First 1\n $task = $method.MakeGenericMethod($Type).Invoke($null,@($Operation))\n try { if (-not $task.Wait(15000)) { throw 'OCR operation timeout' } } catch { throw $_.Exception.ToString() }\n return $task.Result\n}\n$file = Await ([Windows.Storage.StorageFile]::GetFileFromPathAsync($ImagePath)) ([Windows.Storage.StorageFile])\n$stream = Await ($file.OpenAsync([Windows.Storage.FileAccessMode]::Read)) ([Windows.Storage.Streams.IRandomAccessStream])\ntry {\n $decoder = Await ([Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($stream)) ([Windows.Graphics.Imaging.BitmapDecoder])\n $bitmap = Await ($decoder.GetSoftwareBitmapAsync()) ([Windows.Graphics.Imaging.SoftwareBitmap])\n $converted = [Windows.Graphics.Imaging.SoftwareBitmap]::Convert($bitmap,[Windows.Graphics.Imaging.BitmapPixelFormat]::Bgra8,[Windows.Graphics.Imaging.BitmapAlphaMode]::Premultiplied)\n try {\n  $engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromLanguage([Windows.Globalization.Language]::new('en-US'))\n  if ($null -eq $engine) { throw 'English OCR unavailable' }\n  $result = Await ($engine.RecognizeAsync($converted)) ([Windows.Media.Ocr.OcrResult])\n  $lines = @($result.Lines | ForEach-Object { @{ text=$_.Text; words=@($_.Words | ForEach-Object { @{ text=$_.Text; x=$_.BoundingRect.X; y=$_.BoundingRect.Y; width=$_.BoundingRect.Width; height=$_.BoundingRect.Height } }) } })\n  @{text=$result.Text; lines=$lines; confidence=$null; review_required=$true; angle=$result.TextAngle} | ConvertTo-Json -Depth 8\n } finally { if($converted) {$converted.Dispose()}; if($bitmap) {$bitmap.Dispose()} }\n} finally { $stream.Dispose() }\n"

def _regular(path):
    path = Path(path).absolute()
    for part in (path, *path.parents):
        if part.exists() and (part.is_symlink() or getattr(part.stat(), "st_file_attributes", 0) & 0x400):
            raise ValueError("Đường dẫn ảnh/output không được qua link hoặc reparse point.")
    return path


def _image(source):
    from PIL import Image
    source = _regular(source)
    if source.suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp"}:
        raise ValueError("Chỉ hỗ trợ ảnh tĩnh PNG/JPEG/WebP; không xử lý ảnh động.")
    if source.stat().st_size > 32 * 1024 * 1024:
        raise ValueError("Ảnh vượt 32 MiB; hãy chọn crop nhỏ hơn.")
    with source.open("rb") as stream: content = stream.read(32 * 1024 * 1024 + 1)
    if len(content) > 32 * 1024 * 1024: raise ValueError("Ảnh tăng kích thước vượt budget; dừng đọc.")
    with Image.open(io.BytesIO(content)) as opened:
        if opened.width * opened.height > MAX_PIXELS or getattr(opened, "n_frames", 1) != 1:
            raise ValueError("Ảnh quá lớn hoặc có nhiều frame; hãy chọn ảnh tĩnh/crop.")
        opened.load()
        image = opened.convert("RGBA")
    return source, image, hashlib.sha256(content).hexdigest()


def _box(raw, size):
    if not isinstance(raw, list) or len(raw) != 4 or any(type(n) is not int for n in raw):
        raise ValueError("Region cần x,y,width,height nguyên.")
    x, y, w, h = raw
    if x < 0 or y < 0 or w <= 0 or h <= 0 or x + w > size[0] or y + h > size[1]:
        raise ValueError("Region nằm ngoài ảnh hoặc kích thước không hợp lệ.")
    return x, y, w, h


def recognize_image(source, *, is_cancelled=None):
    source, image, digest = _image(source)
    if os.name != "nt":
        raise ValueError("OCR ảnh hiện cần Windows OCR và language pack tiếng Anh.")
    # Pass the path as a literal argument, never interpolate it into executable code.
    env = os.environ.copy(); env["VNTEXT_OCR_IMAGE"] = str(source)
    command = [str(Path(os.environ["SystemRoot"]) / "System32/WindowsPowerShell/v1.0/powershell.exe"),
               "-NoProfile", "-Command", "& {" + OCR_SCRIPT + "} -ImagePath $env:VNTEXT_OCR_IMAGE"]
    proc = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
    deadline = time.monotonic() + 60
    try:
        while True:
            if is_cancelled and is_cancelled():
                raise ValueError("cancelled")
            if time.monotonic() >= deadline:
                raise ValueError("OCR quá 60 giây; chưa có kết quả hoàn tất.")
            try:
                stdout, stderr = proc.communicate(timeout=0.1); break
            except subprocess.TimeoutExpired:
                continue
    finally:
        if proc.poll() is None:
            proc.kill(); proc.communicate()
    if proc.returncode:
        raise ValueError("Windows OCR thất bại: " + stderr.decode("utf-8", "replace")[-1500:])
    raw = json.loads(stdout.decode("utf-8-sig"))
    if raw.get("angle") is not None and abs(raw["angle"]) > 2:
        raise ValueError("Chữ nghiêng cần xoay/crop và review thủ công trước OCR.")
    regions = []
    for line in raw.get("lines", []):
        words = line["words"]
        if not words or not line["text"].strip(): continue
        x = math.floor(min(w["x"] for w in words)); y = math.floor(min(w["y"] for w in words))
        right = math.ceil(max(w["x"] + w["width"] for w in words)); bottom = math.ceil(max(w["y"] + w["height"] for w in words))
        box = [x, y, right-x, bottom-y]; _box(box, image.size)
        identity = hashlib.sha256((digest + json.dumps(box) + line["text"]).encode()).hexdigest()[:24]
        regions.append({"id": identity, "box": box, "source_text": line["text"], "ocr_text": line["text"], "translation": "",
                        "approved": False, "flat_background_approved": False, "background": "#FFFFFF", "foreground": "#000000", "font_size": 24})
    return {"schema": 1, "source_path": str(source), "source_sha256": digest, "width": image.width,
            "height": image.height, "backend": "Windows.Media.Ocr/en-US", "confidence": None,
            "status": "REVIEW_REQUIRED" if regions else "NO_TEXT", "regions": regions}


def render_image(document, output, font_path):
    from PIL import ImageDraw, ImageFont, ImageColor
    if document.get("schema") != 1: raise ValueError("Schema review ảnh không hợp lệ.")
    source, image, digest = _image(document["source_path"])
    output = _regular(output)
    if output == source or output.exists() or output.suffix.lower() != ".png":
        raise ValueError("Output phải là file PNG mới; không ghi đè ảnh gốc/output đã có.")
    if digest != document["source_sha256"] or image.size != (document["width"], document["height"]):
        raise ValueError("Ảnh nguồn đã thay đổi; OCR/review lại trước render.")
    regions = document["regions"]
    if not regions or len(regions) > 500:
        raise ValueError("Không có region đã duyệt hoặc quá 500 region.")
    alpha = image.getchannel("A"); draw = ImageDraw.Draw(image)
    used = []; deadline = time.monotonic() + 30
    for region in regions:
        if time.monotonic() > deadline: raise ValueError("Render vượt 30 giây; giảm số region.")
        x, y, w, h = _box(region["box"], image.size)
        if any(x < a+c and a < x+w and y < b+d and b < y+h for a,b,c,d in used):
            raise ValueError("Region chồng nhau; gộp/sửa crop rồi duyệt lại.")
        used.append((x,y,w,h))
        # shortcut: transparent glyph backgrounds need a compositing workflow; reject until that slice is verified.
        if alpha.crop((x,y,x+w,y+h)).getextrema()[0] < 255:
            raise ValueError("Vùng chữ có alpha trong suốt; chưa hỗ trợ render biến thể này. Chuẩn bị panel nền phẳng opaque trước.")
        if region.get("approved") is not True or region.get("flat_background_approved") is not True:
            raise ValueError("Cần duyệt text/region và xác nhận nền phẳng; không hỗ trợ inpainting nền phức tạp.")
        text = region.get("translation", "")
        if not isinstance(text, str) or not text.strip() or len(text) > 2000:
            raise ValueError("Bản dịch region cần text đã duyệt, tối đa 2000 ký tự.")
        size = region.get("font_size", 24)
        if type(size) is not int or not 6 <= size <= 144:
            raise ValueError("Font size phải từ 6 đến 144.")
        bg = ImageColor.getrgb(region["background"]); fg = ImageColor.getrgb(region["foreground"])
        if len(bg) != 3 or len(fg) != 3: raise ValueError("Màu nền/chữ phải là RGB.")
        colors = image.crop((x,y,x+w,y+h)).convert("RGB").getcolors(4096)
        flat = sum(count for count,pixel in (colors or []) if max(abs(a-b) for a,b in zip(pixel,bg)) <= 8)
        if flat / (w*h) < .70:
            raise ValueError("Nền region không đủ phẳng theo màu đã chọn; hãy crop/chuẩn bị nền thủ công.")
        font = ImageFont.truetype(str(_regular(font_path)), size)
        bounds = draw.multiline_textbbox((0,0),text,font=font,spacing=2)
        if bounds[2]-bounds[0] > w or bounds[3]-bounds[1] > h:
            raise ValueError("Bản dịch tràn region; sửa xuống dòng/font/region rồi duyệt lại.")
        draw.rectangle((x,y,x+w-1,y+h-1),fill=bg)
        draw.multiline_text((x-bounds[0],y-bounds[1]),text,font=font,fill=fg,spacing=2)
    image.putalpha(alpha)
    output.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive creation prevents a render from replacing another user's output.
    created = None
    try:
        with output.open("xb") as handle:
            created = os.fstat(handle.fileno())
            image.save(handle,format="PNG")
    except Exception:
        if created is not None and output.exists():
            current = output.stat()
            if (current.st_dev,current.st_ino) == (created.st_dev,created.st_ino): output.unlink()
        raise
    return str(output)


def discover_images(root, *, is_cancelled=None):
    root = _regular(root)
    if not root.is_dir(): raise ValueError("Chọn thư mục game/ảnh để tìm ảnh.")
    paths = []; seen = 0; deadline = time.monotonic() + 30
    for base, dirs, names in os.walk(root, followlinks=False):
        for name in dirs + names:
            seen += 1
            if seen > 10000 or time.monotonic() > deadline: raise ValueError("Inventory ảnh vượt budget; chọn thư mục ảnh nhỏ hơn.")
            if is_cancelled and is_cancelled(): raise ValueError("cancelled")
            item = _regular(Path(base) / name)
            if item.is_file() and item.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}:
                paths.append(str(item))
    return {"source_root": str(root), "image_paths": sorted(paths), "complete": True,
            "note": "Ảnh ứng viên, chưa chứng minh có chữ; chọn từng ảnh để OCR/review. Không đọc archive/animation."}
