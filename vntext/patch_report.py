"""Plain-Vietnamese statistics of one "Tạo bản Việt hóa" run: how many sentences were patched, skipped, or left in English, and why.

Inputs are the two receipts the pipeline already writes: ``patch_verification.json`` (next to the patch) and ``extract_status.json`` (of the package the
patch was made from).  Only numbers and reason words are reported - never the text of a sentence - so the report is safe to put in a bug package."""
from __future__ import annotations

import json
from pathlib import Path

REPORT_FILE = "bao_cao_viet_hoa.json"
REPORT_TEXT_FILE = "bao_cao_viet_hoa.txt"

# patch-side reasons (omitted_by_reason keys) -> plain wording
_PATCH_REASONS = (
    ("untranslated", "chưa dịch"),
    ("no_translation", "chưa dịch"),
    ("renpy_markup_invalid", "bị chặn vì dấu [ ] hoặc thẻ { } hỏng (game sẽ báo lỗi)"),
    ("technical_control", "là mã điều khiển của game, không phải câu thoại"),
    ("existing_translation_conflict", "game đã có sẵn bản dịch khác"),
    ("source_text_not_locatable", "không tìm thấy câu gốc trong tệp của game"),
)


def _read_json(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _plain_patch_reason(reason: str) -> str:
    for key, words in _PATCH_REASONS:
        if reason == key or reason.startswith(key):
            return words
    if reason.startswith("validation:"):
        return "bị chặn bởi bộ kiểm tra bản dịch máy"
    return "bị chặn vì bản dịch chưa đạt kiểm tra (" + (reason.split(";")[0] or "không rõ") + ")"


def build_patch_report(patch_out: str | Path, extract_status: str | Path | None = None) -> dict:
    out = Path(patch_out)
    verification = _read_json(out / "patch_verification.json")
    counts = verification.get("counts") if isinstance(verification.get("counts"), dict) else {}
    patched = int(counts.get("PASS", 0) or 0)
    failed = int(counts.get("FAIL", 0) or 0)
    kept_english: dict[str, int] = {}
    for reason, number in (verification.get("omitted_by_reason") or {}).items():
        words = _plain_patch_reason(str(reason))
        kept_english[words] = kept_english.get(words, 0) + int(number or 0)
    review_only = int(verification.get("review_only_skipped", 0) or 0)
    if review_only:
        kept_english["chỉ để xem lại, không có đường ghi an toàn"] = kept_english.get("chỉ để xem lại, không có đường ghi an toàn", 0) + review_only
    extract = _read_json(Path(extract_status)) if extract_status else {}
    outside_patch: dict[str, int] = {}
    for key, words in (
        ("skipped", "là mã kỹ thuật của game, không phải chữ người chơi đọc"),
        ("excluded_engine_common", "là chuỗi chung của engine Ren'Py, không thuộc game"),
        ("user_excluded", "bạn đã bỏ qua (hoặc được dọn khỏi bản dịch)"),
        ("runtime_dynamic_unresolved", "do game ghép lúc chạy, chưa biết trước nội dung"),
        ("excluded_technical_ui", "là giao diện kỹ thuật, không dịch"),
    ):
        number = int(extract.get(key, 0) or 0)
        if number:
            outside_patch[words] = number
    return {
        "schema": 1,
        "patched": patched,
        "patched_failed_readback": failed,
        "repaired_markup": len(verification.get("repaired_markup_keys") or []),
        "already_satisfied": int(verification.get("already_satisfied", 0) or 0),
        "kept_english_in_patch": kept_english,
        "left_out_before_patch": outside_patch,
        "native_units": int(extract.get("native_units", 0) or 0),
    }


def format_patch_report_vi(report: dict) -> list[str]:
    lines = [f"Đã Việt hóa: {report.get('patched', 0)} câu."]
    if report.get("repaired_markup"):
        lines.append(f"  Trong đó {report['repaired_markup']} câu được tự sửa lại dấu [ ] / thẻ { '{ }' } cho khớp câu gốc.")
    kept = report.get("kept_english_in_patch") or {}
    if kept:
        lines.append(f"Còn tiếng Anh vì chưa đủ điều kiện ghi vào game: {sum(kept.values())} câu.")
        for words, number in sorted(kept.items(), key=lambda item: -item[1]):
            lines.append(f"  - {number} câu {words}")
    left = report.get("left_out_before_patch") or {}
    if left:
        lines.append(f"Không nằm trong bản dịch ngay từ lúc lấy text: {sum(left.values())} mục.")
        for words, number in sorted(left.items(), key=lambda item: -item[1]):
            lines.append(f"  - {number} mục {words}")
    if report.get("already_satisfied"):
        lines.append(f"Game đã có đúng bản dịch này sẵn: {report['already_satisfied']} câu.")
    return lines


def write_patch_report(patch_out: str | Path, extract_status: str | Path | None = None) -> dict:
    """Build the report, store it next to the patch (json + text) and return it with a ``lines`` entry."""
    out = Path(patch_out)
    report = build_patch_report(out, extract_status)
    lines = format_patch_report_vi(report)
    try:
        (out / REPORT_FILE).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        (out / REPORT_TEXT_FILE).write_text("\n".join(lines) + "\n", encoding="utf-8")
    except OSError:
        pass
    return {**report, "lines": lines}
