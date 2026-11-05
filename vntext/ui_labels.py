"""Generic UI-label routing policy.

The public build embeds no title-specific label table.  Owner decision (2026-11-02): a small CURATED catalog of the standard,
game-independent menu labels (Inventory, Save, Load, Options ...) is applied ONLY to an exact standalone label in an explicit UI context,
because the offline MT model turns such one-word strings into nonsense (``Inventory`` -> ``Nhà phát minh``).  It is not a substring
replacement, never touches sentences, story choices, dialogue or text carrying placeholders/tags, and it ranks BELOW every user/package
glossary and translation memory.  It cannot make every short string right: anything outside the catalog still goes through the model.
"""

from __future__ import annotations

import re

# Exact standalone labels only (matched case-insensitively after trimming/collapsing whitespace).  Deliberately conservative: no "OK",
# no "Back"/"Return" homographs outside UI contexts, nothing that is ordinary prose.
UI_LABEL_CATALOG: dict[str, str] = {
    "inventory": "Túi đồ",
    "save": "Lưu",
    "load": "Tải",
    "save game": "Lưu game",
    "load game": "Tải game",
    "new game": "Trò chơi mới",
    "options": "Tùy chọn",
    "preferences": "Tùy chọn",
    "settings": "Cài đặt",
    "continue": "Tiếp tục",
    "resume": "Tiếp tục",
    "start": "Bắt đầu",
    "start game": "Bắt đầu game",
    "quit": "Thoát",
    "exit": "Thoát",
    "back": "Quay lại",
    "return": "Quay lại",
    "main menu": "Menu chính",
    "history": "Lịch sử",
    "skip": "Bỏ qua",
    "auto": "Tự động",
    "help": "Trợ giúp",
    "about": "Giới thiệu",
    "credits": "Đội ngũ thực hiện",
    "gallery": "Thư viện ảnh",
    "yes": "Có",
    "no": "Không",
    "cancel": "Hủy",
    "confirm": "Xác nhận",
    "apply": "Áp dụng",
    "language": "Ngôn ngữ",
    "music": "Âm nhạc",
    "sound": "Âm thanh",
    "volume": "Âm lượng",
    "fullscreen": "Toàn màn hình",
    "quests": "Nhiệm vụ",
    "quest log": "Nhật ký nhiệm vụ",
    "journal": "Nhật ký",
    "map": "Bản đồ",
    "items": "Vật phẩm",
    "equipment": "Trang bị",
    "skills": "Kỹ năng",
    "status": "Trạng thái",
    "display": "Hiển thị",
    "window": "Cửa sổ",
    "keyboard": "Bàn phím",
    "mouse": "Chuột",
    "gamepad": "Tay cầm",
    "calibrate": "Hiệu chỉnh",
    "skipping": "Đang bỏ qua",
    "menu": "Menu",
    "video": "Video",
    "mute all": "Tắt tiếng tất cả",
    "your name": "Tên của bạn",
    "unlocked": "Đã mở khóa",
    "test": "Thử",
    "achievements:": "Thành tựu:",
    "made with ren'py": "Làm bằng Ren'Py",
}

# Exact numbered-label patterns ("Achievement3"); the number is carried over untouched.
UI_LABEL_PATTERNS = (
    (re.compile(r"achievement\s?(\d+)", re.IGNORECASE), "Thành tựu {0}"),
    (re.compile(r"chapter\s?(\d+)", re.IGNORECASE), "Chương {0}"),
    (re.compile(r"page\s?(\d+)", re.IGNORECASE), "Trang {0}"),
)

_TOKENS = re.compile(r"[\[\]{}<>%\\]|\bUI:")
_SPACE = re.compile(r"\s+")


def is_ui_row(row: dict) -> bool:
    context = str(row.get("context") or "")
    method = str(row.get("import_method") or "")
    return context.startswith("UI:") or method == "unity_ui_text"


def is_ui_label_context(context: str) -> bool:
    """An explicit UI-screen context.  Story choices/menus, dialogue and unknown contexts are NOT UI contexts."""
    if not context:
        return False
    lowered = context.lower()
    if "choice" in lowered or "dialog" in lowered:
        return False
    # ``:string:`` is the Ren'Py translatable-string table (``_("...")`` in screens/gui); story dialogue and menu choices never use it.
    return context.startswith("UI:") or "textbutton" in lowered or lowered.startswith("screen") or ":screen" in lowered or ":string:" in lowered


def resolve_ui_label_translation(src: str, context: str = "") -> str | None:
    """Catalog translation of an exact standalone UI label in an explicit UI context; None otherwise (the model/glossaries decide)."""
    if not src or not is_ui_label_context(context):
        return None
    text = _SPACE.sub(" ", src).strip()
    if not text or _TOKENS.search(text):
        return None
    translated = UI_LABEL_CATALOG.get(text.lower())
    if translated is None:
        for pattern, template in UI_LABEL_PATTERNS:        # numbered labels: exact "<word> <number>" only
            match = pattern.fullmatch(text)
            if match:
                translated = template.format(*match.groups())
                break
    if translated is None:
        return None
    letters = [ch for ch in text if ch.isalpha()]
    if len(letters) >= 3 and all(ch.isupper() for ch in letters):
        return translated.upper()                                   # ALL-CAPS art keeps its capitals
    return translated


def should_skip_mt_for_ui_label(row: dict) -> bool:
    """Do not silently drop generic UI labels for lack of a bundled table."""

    del row
    return False
