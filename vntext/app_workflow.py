"""Shared workflow state helpers for Tk and Qt UIs."""
from __future__ import annotations

import csv
from pathlib import Path

from vntext.package_io import resolve_translation_package_dir


def package_dir_from_output(output_path: str) -> Path:
    return resolve_translation_package_dir(output_path.strip())


def has_translations(csv_path: Path) -> bool:
    if not csv_path.is_file():
        return False
    try:
        with csv_path.open("r", encoding="utf-8-sig", newline="") as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                if str(row.get("translation") or row.get("translated_text") or "").strip():
                    return True
    except OSError:
        return False
    return False


def workflow_status(input_path: str, output_path: str) -> dict:
    package = package_dir_from_output(output_path)
    csv_path = package / "translation.csv"
    manifest_path = package / "manifest.json"
    patch_dir = package / "Patch_Viet_Hoa"
    has_game = bool(input_path.strip())
    has_extract = csv_path.is_file() and manifest_path.is_file()
    has_translate = has_translations(csv_path)
    has_patch = patch_dir.is_dir() and any(patch_dir.iterdir())

    states = {
        "extract": "done" if has_extract else "pending",
        "translate": "done" if has_translate else "pending",
        "patch": "done" if has_patch else "pending",
    }
    if not has_game:
        current = "extract"
        states["extract"] = "current"
    elif not has_extract:
        current = "extract"
        states["extract"] = "current"
    elif not has_translate:
        current = "translate"
        states["translate"] = "current"
    elif not has_patch:
        current = "patch"
        states["patch"] = "current"
    else:
        current = "done"

    hero_map = {
        "extract": ("Lấy text từ game", "Chọn game bên dưới, rồi bấm «Lấy text» để xuất CSV."),
        "translate": ("Dịch tự động", "Dịch translation.csv bằng CT2 / OPUS-MT offline."),
        "patch": ("Tạo patch Việt hóa", "Đóng gói bản dịch thành patch cài vào game."),
        "done": ("Workflow hoàn tất", "Gói dịch và patch đã sẵn sàng. Có thể chạy lại bất kỳ bước nào."),
    }
    if not has_game:
        hero_map["extract"] = ("Chọn thư mục game", "Chọn game bên dưới, rồi bấm «Lấy text» để xuất CSV.")
    return {"states": states, "current": current, "hero": hero_map[current]}
