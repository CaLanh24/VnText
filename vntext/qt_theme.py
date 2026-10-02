"""VNText Studio Qt theme — reference visual parity."""
from __future__ import annotations

from vntext.ui_theme import BREAKPOINTS, PALETTE, RADIUS, RAW_FILTER_LABELS, SPACING

__all__ = [
    "BREAKPOINTS",
    "PALETTE",
    "RADIUS",
    "RAW_FILTER_LABELS",
    "SPACING",
    "QT_LIGHT",
    "build_stylesheet",
    "status_colors",
]

from vntext.ref_tokens import C_SIDEBAR, C_WINDOW

QT_LIGHT = {
    **PALETTE,
    "window": C_WINDOW,
    "sidebar": C_SIDEBAR,
    "surface": "#FFFFFF",
    "surface_muted": "#FAFAFC",
    "border": "#E5E5EA",
    "border_strong": "#E5E5EA",
    "text": "#1D1D1F",
    "text_secondary": "#3A3A3C",
    "text_muted": "#6E6E73",
    "text_tertiary": "#8E8E93",
    "accent": "#007AFF",
    "accent_hover": "#006FE8",
    "accent_pressed": "#005ED1",
    "accent_subtle": "#DDE8F7",
    "accent_text": "#FFFFFF",
    "success": "#34C759",
    "success_bg": "#EAF6EC",
    "error": "#FF3B30",
    "error_bg": "#FDECEA",
    "log_bg": "#FAFAFC",
    "log_border": "#E5E5EA",
    "progress_trough": "#E5E5EA",
    "progress_fill": "#007AFF",
    "control_bg": "#FFFFFF",
    "control_disabled": "#F2F2F4",
    "scrollbar": "#C7C7CC",
    "footer_bg": "#FFFFFF",
    "footer_border": "#EBEBF0",
}

DARK_PALETTE = {
    "window": "#1C1C1E",
    "sidebar": "#2C2C2E",
    "surface": "#2C2C2E",
    "surface_muted": "#1C1C1E",
    "border": "#3A3A3C",
    "border_strong": "#48484A",
    "text": "#F5F5F7",
    "text_secondary": "#E5E5EB",
    "text_muted": "#AEAEB2",
    "text_tertiary": "#8E8E93",
    "accent": "#0A84FF",
    "accent_hover": "#409CFF",
    "accent_pressed": "#0066CC",
    "accent_subtle": "#1A2F44",
    "accent_text": "#FFFFFF",
    "success": "#30D158",
    "success_bg": "#1A3324",
    "error": "#FF453A",
    "error_bg": "#3D1F1C",
    "log_bg": "#1C1C1E",
    "log_border": "#3A3A3C",
    "progress_trough": "#3A3A3C",
    "progress_fill": "#0A84FF",
    "control_bg": "#2C2C2E",
    "control_disabled": "#3A3A3C",
    "scrollbar": "#636366",
    "footer_bg": "#2C2C2E",
    "footer_border": "#3A3A3C",
}


def status_colors(palette: dict) -> dict[str, tuple[str, str]]:
    return {
        "idle": (palette["text_muted"], palette.get("surface_muted", "#F2F2F4")),
        "running": (palette["accent"], palette["accent_subtle"]),
        "done": (palette["success"], palette["success_bg"]),
        "error": (palette["error"], palette["error_bg"]),
        "pending": (palette["text_tertiary"], palette.get("surface_muted", "#F2F2F4")),
        "current": (palette["accent"], palette["accent_subtle"]),
    }


def build_stylesheet(*, dark: bool = False) -> str:
    from vntext.qt_widgets import (
        BTN_PAD_X,
        BTN_HEIGHT,
        CARD_RADIUS,
        NAV_H_TWO,
        PATH_BTN_PAD_X,
        PRIMARY_BTN_HEIGHT,
        TOGGLE_HIT,
    )

    p = DARK_PALETTE if dark else QT_LIGHT
    r = RADIUS
    return f"""
    * {{
        font-family: "Segoe UI", "SF Pro Text", system-ui, sans-serif;
        font-size: 10pt;
    }}
    QWidget {{ color: {p["text"]}; background: transparent; }}
    QMainWindow {{ background: {p["window"]}; }}
    #centralWidget, #contentHost, QScrollArea, QScrollArea > QWidget > QWidget {{
        background: {p["window"]};
    }}
    #sidebar {{
        background: {p["sidebar"]};
        border-right: 1px solid {p["border"]};
    }}
    #sidebarBrand {{
        font-size: 14pt;
        font-weight: 600;
        color: {p["text"]};
        letter-spacing: -0.2px;
    }}
    #sectionLabel {{
        color: {p["text_tertiary"]};
        font-size: 8pt;
        font-weight: 600;
        letter-spacing: 0.9px;
        padding: 12px 14px 6px 14px;
    }}
    QToolButton#sectionToggleAdvanced {{
        color: {p["text_secondary"]};
        font-size: 8pt;
        font-weight: 700;
        letter-spacing: 0.8px;
        padding: 8px 20px 4px 20px;
        border: none;
        text-align: left;
    }}
    QToolButton#sectionToggleAdvanced:hover {{ color: {p["text"]}; }}
    #sidebarDivider {{
        background: {p["border"]};
        max-height: 1px;
        margin: 12px 18px;
    }}
    QPushButton#sidebarLink {{
        border: none;
        background: transparent;
        color: {p["text_secondary"]};
        text-align: left;
        padding: 0;
        font-size: 10.5pt;
        font-weight: 500;
    }}
    QPushButton#sidebarLink:hover {{ color: {p["text"]}; }}
    #sidebarStatus {{ color: {p["text_secondary"]}; font-size: 10pt; font-weight: 600; }}
    #sidebarVersion {{ color: {p["text_muted"]}; font-size: 9.5pt; font-weight: 500; }}
    #appFooter {{
        background: {p["footer_bg"]};
        border-top: 1px solid {p["footer_border"]};
    }}
    #footerTip {{ color: {p["text_tertiary"]}; font-size: 9.5pt; }}
    QFrame#card {{
        background: {p["surface"]};
        border: 1px solid {p["border_strong"]};
        border-radius: {CARD_RADIUS}px;
    }}
    QLabel#cardTitle {{ font-size: 13pt; font-weight: 600; color: {p["text"]}; }}
    QLabel#cardSubtitle, QLabel#settingHelper {{ color: {p["text_tertiary"]}; font-size: 9pt; }}
    QLabel#settingTitle {{ color: {p["text"]}; font-size: 10.5pt; font-weight: 500; }}
    QLabel#heroTitle {{ font-size: 19pt; font-weight: 600; color: {p["text"]}; letter-spacing: -0.3px; }}
    QLabel#heroHint {{ color: {p["text_tertiary"]}; font-size: 10pt; }}
    QLabel#fieldLabel {{ color: {p["text_secondary"]}; font-size: 10pt; font-weight: 600; }}
    QLabel#metricLabel {{ color: {p["text_muted"]}; font-size: 10pt; }}
    QLabel#metricValue {{ font-size: 19pt; font-weight: 600; color: {p["text"]}; }}
    QLabel#metricValueAccent {{ font-size: 19pt; font-weight: 600; color: {p["accent"]}; }}
    QLabel#itemLabel {{ color: {p["text_secondary"]}; font-size: 10.5pt; }}
    QLabel#panelSubtitle {{ color: {p["text_muted"]}; font-size: 10pt; }}
    QPushButton {{
        background: {p["surface"]};
        border: 1px solid {p["border_strong"]};
        border-radius: {r["control"]}px;
        padding: 6px {BTN_PAD_X}px;
        color: {p["text_secondary"]};
        min-height: 30px;
        font-size: 10pt;
    }}
    QPushButton#pathBtn {{
        background: {p["surface"]};
        border: 1px solid {p["border_strong"]};
        border-radius: 9px;
        padding: 6px {PATH_BTN_PAD_X}px;
        color: {p["text_secondary"]};
        font-size: 10pt;
        min-height: {BTN_HEIGHT - 4}px;
        max-height: {BTN_HEIGHT}px;
    }}
    QPushButton#pathBtn:hover {{ background: {p["surface_muted"]}; color: {p["text"]}; }}
    QPushButton#pathBtn:disabled {{
        color: {p["text_tertiary"]};
        background: {p["control_disabled"]};
        border-color: {p["border"]};
    }}
    QPushButton:hover {{ background: {p["surface_muted"]}; }}
    QPushButton:disabled {{ color: {p["text_tertiary"]}; background: {p["control_disabled"]}; }}
    QPushButton#primary {{
        background: transparent;
        border: none;
        padding: 0;
        min-height: {PRIMARY_BTN_HEIGHT}px;
    }}
    QPushButton#footerLink {{
        border: none; background: transparent; color: {p["text_muted"]};
        padding: 0; min-height: 36px; font-size: 10pt;
    }}
    QPushButton#footerLink:hover {{ color: {p["text_secondary"]}; background: transparent; }}
    QPushButton#popupButton {{
        background: transparent;
        border: none;
        padding: 0;
        min-width: 140px;
    }}
    QPushButton#navItem, QPushButton#navItemAdvanced {{
        border: none; background: transparent; text-align: left; padding: 0; margin: 0 6px;
        min-height: {NAV_H_TWO}px; max-height: {NAV_H_TWO}px;
    }}
    QLineEdit#macLineEdit {{
        background: transparent;
        border: none;
        padding: 8px 14px;
        color: {p["text"]};
        font-size: 10pt;
        selection-background-color: {p["accent_subtle"]};
    }}
    QLineEdit#macLineEdit:disabled {{ color: {p["text_tertiary"]}; }}
    QLineEdit {{
        background: {p["control_bg"]};
        border: 1px solid {p["border_strong"]};
        border-radius: 9px;
        padding: 8px 14px;
        color: {p["text"]};
        min-height: 36px;
        font-size: 10pt;
        selection-background-color: {p["accent_subtle"]};
    }}
    QLineEdit:disabled {{ background: {p["control_disabled"]}; color: {p["text_tertiary"]}; }}
    QMenu#popupMenu {{
        background: {p["surface"]};
        border: 1px solid {p["border_strong"]};
        border-radius: 10px;
        padding: 6px;
    }}
    QMenu#popupMenu::item {{ padding: 9px 26px 9px 14px; border-radius: 6px; font-size: 10pt; }}
    QMenu#popupMenu::item:selected {{ background: {p["accent_subtle"]}; color: {p["text"]}; }}
    QProgressBar {{
        border: none; border-radius: 4px;
        background: {p["progress_trough"]};
        min-height: 7px; max-height: 7px;
    }}
    QProgressBar::chunk {{ background: {p["progress_fill"]}; border-radius: 4px; }}
    QTextEdit#logView {{
        background: {p["log_bg"]};
        border: 1px solid {p["log_border"]};
        border-radius: 9px;
        font-family: "Cascadia Mono", "Consolas", monospace;
        font-size: 9.5pt;
        color: {p["text_secondary"]};
        padding: 12px;
    }}
    QScrollBar:vertical {{ width: 7px; background: transparent; }}
    QScrollBar::handle:vertical {{ background: {p["scrollbar"]}; border-radius: 3px; min-height: 20px; }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
    QToolButton#panelChevron {{
        border: none; background: transparent; color: {p["text_tertiary"]};
        padding: 2px; min-width: {TOGGLE_HIT}px; min-height: {TOGGLE_HIT}px;
        font-size: 11pt;
    }}
    QToolButton#panelChevron:hover {{ color: {p["text_secondary"]}; background: {p["surface_muted"]}; border-radius: 9px; }}
    QToolButton#panelChevron:checked {{ color: {p["text_secondary"]}; }}
    QScrollArea {{ border: none; background: {p["window"]}; }}
    """
