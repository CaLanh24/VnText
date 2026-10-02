"""macOS-style Qt widgets — VNText Studio reference design system."""
from __future__ import annotations

from PySide6.QtCore import QPointF, QRect, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QFont, QFontMetrics, QLinearGradient, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (
    QAbstractButton,
    QFrame,
    QGraphicsDropShadowEffect,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QPushButton,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from vntext import ref_tokens as T

# Aliases for existing imports
SIDEBAR_WIDTH = T.SIDEBAR_W
CONTENT_MARGIN = T.CONTENT_PAD_X
CONTENT_GAP = T.SECTION_GAP
CARD_PAD = T.CARD_PAD
CARD_RADIUS = T.CARD_RADIUS
CONTROL_COL_WIDTH = T.DROPDOWN_W
BTN_HEIGHT = T.CTRL_H
BTN_PAD_X = T.PATH_BTN_PAD_X
PATH_BTN_GAP = T.PATH_BTN_GAP
PATH_BTN_PAD_X = T.PATH_BTN_PAD_X
PATH_BTN_MIN_W = T.PATH_BTN_MIN_W
TOGGLE_HIT = 34
CHIP_HEIGHT = 26
NAV_H_TWO = T.NAV_H2
NAV_H_ONE = T.NAV_H1
COLLAPSED_H = T.PANEL_H
HERO_ICON_TILE = T.ICON_HERO
PRIMARY_BTN_HEIGHT = T.PRIMARY_H
PRIMARY_BTN_MIN_W = T.PRIMARY_MIN_W
CARD_ICON = T.ICON_CARD

ACCENT = T.C_ACCENT
ACCENT_HOVER = T.C_ACCENT_HOVER
ACCENT_SUBTLE = T.C_ACCENT_SUBTLE
ACCENT_TEXT = T.C_ACCENT
SURFACE = T.C_SURFACE
BORDER = T.C_BORDER
BORDER_LIGHT = T.C_BORDER_LIGHT
TEXT = T.C_TEXT
TEXT_MUTED = T.C_TEXT_MUTED
TEXT_TERTIARY = T.C_TEXT_TER
WINDOW_BG = T.C_WINDOW


def _max_v(widget: QWidget, policy_h: QSizePolicy.Policy = QSizePolicy.Expanding) -> None:
    widget.setSizePolicy(policy_h, QSizePolicy.Maximum)


def _paint_line_icon(p: QPainter, kind: str, rect: QRectF, color: QColor) -> None:
    p.save()
    p.setRenderHint(QPainter.Antialiasing)
    pen = QPen(color, 1.55)
    pen.setCapStyle(Qt.RoundCap)
    pen.setJoinStyle(Qt.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.NoBrush)
    cx, cy = rect.center().x(), rect.center().y()
    w, h = rect.width() * 0.58, rect.height() * 0.58
    if kind == "document":
        p.drawRoundedRect(QRectF(cx - w / 2, cy - h / 2, w, h), 2, 2)
        p.drawLine(QPointF(cx - w / 4, cy - h / 8), QPointF(cx + w / 4, cy - h / 8))
        p.drawLine(QPointF(cx - w / 4, cy + h / 12), QPointF(cx + w / 6, cy + h / 12))
    elif kind == "globe":
        p.drawEllipse(QPointF(cx, cy), w / 2, h / 2)
        p.drawLine(QPointF(cx - w / 2, cy), QPointF(cx + w / 2, cy))
        p.drawArc(QRectF(cx - w / 2, cy - h / 2, w, h), 0, 180 * 16)
    elif kind == "package":
        p.drawRoundedRect(QRectF(cx - w / 2, cy - h / 4, w, h * 0.65), 2, 2)
        p.drawLine(QPointF(cx - w / 2, cy - h / 4), QPointF(cx, cy - h / 2))
        p.drawLine(QPointF(cx + w / 2, cy - h / 4), QPointF(cx, cy - h / 2))
    elif kind == "folder":
        p.setBrush(color)
        path = QPainterPath()
        path.moveTo(cx - w / 2, cy + h / 3)
        path.lineTo(cx - w / 2, cy - h / 6)
        path.lineTo(cx - w / 6, cy - h / 6)
        path.lineTo(cx - w / 12, cy - h / 3)
        path.lineTo(cx + w / 2, cy - h / 3)
        path.lineTo(cx + w / 2, cy + h / 3)
        path.closeSubpath()
        p.drawPath(path)
    elif kind == "gear":
        p.drawEllipse(QPointF(cx, cy), w / 3, h / 3)
        for i in range(6):
            ang = i * 60
            p.save()
            p.translate(cx, cy)
            p.rotate(ang)
            p.drawLine(QPointF(0, -w / 3), QPointF(0, -w / 2))
            p.restore()
    elif kind == "chart":
        p.drawLine(QPointF(cx - w / 2, cy + h / 3), QPointF(cx - w / 6, cy - h / 6))
        p.drawLine(QPointF(cx - w / 6, cy - h / 6), QPointF(cx + w / 8, cy + h / 8))
        p.drawLine(QPointF(cx + w / 8, cy + h / 8), QPointF(cx + w / 2, cy - h / 3))
    elif kind == "journal":
        p.drawRoundedRect(QRectF(cx - w / 2, cy - h / 2, w, h), 2, 2)
        p.drawLine(QPointF(cx - w / 4, cy - h / 6), QPointF(cx + w / 4, cy - h / 6))
        p.drawLine(QPointF(cx - w / 4, cy + h / 12), QPointF(cx + w / 5, cy + h / 12))
    elif kind == "search":
        p.drawEllipse(QPointF(cx - w / 8, cy - h / 8), w / 3, h / 3)
        p.drawLine(QPointF(cx + w / 8, cy + h / 8), QPointF(cx + w / 2.5, cy + h / 2.5))
    elif kind == "list":
        for dy in (-h / 5, 0, h / 5):
            p.drawLine(QPointF(cx - w / 2, cy + dy), QPointF(cx + w / 2, cy + dy))
    elif kind == "filter":
        p.drawLine(QPointF(cx - w / 2, cy - h / 4), QPointF(cx + w / 2, cy - h / 4))
        p.drawLine(QPointF(cx - w / 3, cy), QPointF(cx + w / 3, cy))
        p.drawLine(QPointF(cx - w / 5, cy + h / 4), QPointF(cx + w / 5, cy + h / 4))
    elif kind == "eye":
        p.drawEllipse(QPointF(cx, cy), w / 2, h / 3)
        p.setBrush(color)
        p.drawEllipse(QPointF(cx, cy), w / 8, h / 8)
    elif kind == "info":
        p.drawEllipse(QPointF(cx, cy), w / 2.2, h / 2.2)
        p.setBrush(color)
        f = p.font()
        f.setBold(True)
        f.setPointSizeF(max(7.0, rect.height() * 0.28))
        p.setFont(f)
        p.drawText(rect, Qt.AlignCenter, "i")
    elif kind == "play":
        tri = QPainterPath()
        tri.moveTo(cx - w / 5, cy - h / 3)
        tri.lineTo(cx + w / 3, cy)
        tri.lineTo(cx - w / 5, cy + h / 3)
        tri.closeSubpath()
        p.setBrush(color)
        p.drawPath(tri)
    elif kind == "bulb":
        p.drawEllipse(QPointF(cx, cy - h / 8), w / 3, h / 3)
        p.drawLine(QPointF(cx, cy + h / 6), QPointF(cx, cy + h / 3))
        p.drawLine(QPointF(cx - w / 5, cy + h / 3), QPointF(cx + w / 5, cy + h / 3))
    elif kind == "book":
        p.drawRoundedRect(QRectF(cx - w / 2, cy - h / 2, w, h), 2, 2)
        p.drawLine(QPointF(cx, cy - h / 2), QPointF(cx, cy + h / 2))
    elif kind == "help":
        p.drawEllipse(QPointF(cx, cy), w / 2.2, h / 2.2)
        p.setBrush(color)
        f = p.font()
        f.setBold(True)
        f.setPointSizeF(max(7.0, rect.height() * 0.3))
        p.setFont(f)
        p.drawText(rect, Qt.AlignCenter, "?")
    elif kind == "moon":
        p.drawEllipse(QPointF(cx, cy), w / 2.2, h / 2.2)
        p.setBrush(QColor(SURFACE))
        p.setPen(Qt.NoPen)
        p.drawEllipse(QPointF(cx + w / 6, cy - h / 8), w / 2.5, h / 2.2)
    elif kind == "chevron_down":
        p.drawLine(QPointF(cx - w / 4, cy - h / 8), QPointF(cx, cy + h / 8))
        p.drawLine(QPointF(cx, cy + h / 8), QPointF(cx + w / 4, cy - h / 8))
    p.restore()


class LineIcon(QWidget):
    def __init__(self, kind: str, color: str = "#636366", *, size: int = 20, parent=None):
        super().__init__(parent)
        self._kind = kind
        self._color = QColor(color)
        self.setFixedSize(size, size)

    def set_color(self, color: str) -> None:
        self._color = QColor(color)
        self.update()

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        _paint_line_icon(p, self._kind, QRectF(self.rect()), self._color)
        p.end()


class TintIcon(QWidget):
    """Rounded tile icon — sidebar, cards, panels."""

    def __init__(
        self,
        kind: str,
        *,
        size: int = 36,
        tint: str = ACCENT_SUBTLE,
        fg: str = ACCENT,
        radius: int = 10,
        parent=None,
    ):
        super().__init__(parent)
        self._kind = kind
        self._tint = QColor(tint)
        self._fg = QColor(fg)
        self._radius = radius
        self.setFixedSize(size, size)

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(0.5, 0.5, self.width() - 1, self.height() - 1)
        p.setPen(Qt.NoPen)
        p.setBrush(self._tint)
        p.drawRoundedRect(r, self._radius, self._radius)
        pad = self.width() * 0.22
        _paint_line_icon(p, self._kind, QRectF(pad, pad, self.width() - pad * 2, self.height() - pad * 2), self._fg)
        p.end()


class AppLogo(QWidget):
    def __init__(self, parent=None, *, size: int = 40):
        super().__init__(parent)
        self._size = size
        self.setFixedSize(size, size)
        self._pixmap = self._load_pixmap()

    def _load_pixmap(self):
        from PySide6.QtGui import QIcon, QPixmap

        from vntext.brand_icon import logo_ico_path, logo_png_path

        path = logo_ico_path() or logo_png_path()
        if path is None:
            return QPixmap()
        icon = QIcon(str(path))
        return icon.pixmap(self._size, self._size)

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        if self._pixmap.isNull():
            p.end()
            return
        p.drawPixmap(0, 0, self._pixmap)
        p.end()


def _apply_card_shadow(frame: QFrame, *, strong: bool = False) -> None:
    shadow = QGraphicsDropShadowEffect(frame)
    if strong:
        shadow.setBlurRadius(36)
        shadow.setOffset(0, 6)
        shadow.setColor(QColor(0, 0, 0, 38))
    else:
        shadow.setBlurRadius(T.CARD_SHADOW_BLUR)
        shadow.setOffset(0, T.CARD_SHADOW_Y)
        shadow.setColor(QColor(0, 0, 0, T.CARD_SHADOW_ALPHA))
    frame.setGraphicsEffect(shadow)


class MacCard(QFrame):
    def __init__(self, parent=None, *, slim: bool = False, hero: bool = False, elevated: bool = False):
        super().__init__(parent)
        self.setObjectName("card")
        if hero:
            pad = (16, 18, 16, 14)
            spacing = 0
        elif slim:
            pad = (14, 12, 14, 12)
            spacing = 0
        else:
            pad = (CARD_PAD, CARD_PAD, CARD_PAD, CARD_PAD)
            spacing = 14
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(*pad)
        self._layout.setSpacing(spacing)
        _max_v(self)
        if hero:
            self.setFixedHeight(T.HERO_H)
        elif slim:
            self.setMinimumHeight(T.PANEL_H)
        else:
            _apply_card_shadow(self, strong=elevated)

    def add_header(self, kind: str, title: str, subtitle: str = "", *, accent: bool = True) -> None:
        row = QHBoxLayout()
        row.setSpacing(10)
        fg = ACCENT if accent else "#636366"
        tint = ACCENT_SUBTLE if accent else T.C_NAV_ICON_BG
        row.addWidget(TintIcon(kind, size=CARD_ICON, tint=tint, fg=fg, radius=11))
        col = QVBoxLayout()
        col.setSpacing(3)
        t = QLabel(title)
        t.setObjectName("cardTitle")
        _max_v(t)
        col.addWidget(t)
        if subtitle:
            s = QLabel(subtitle)
            s.setObjectName("cardSubtitle")
            s.setWordWrap(False)
            _max_v(s)
            col.addWidget(s)
        row.addLayout(col, 1)
        self._layout.addLayout(row)

    @property
    def body(self) -> QVBoxLayout:
        return self._layout


class MacLineEdit(QLineEdit):
    """Custom path/input field — painted background + border."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("macLineEdit")
        self.setFrame(False)
        self.setStyleSheet(
            "color:#1D1D1F; background:transparent; border:none; padding:8px 14px; font-size:10pt;"
        )

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(1, 1, self.width() - 2, self.height() - 2)
        if not self.isEnabled():
            bg = QColor("#F2F2F4")
            border = QColor("#E5E5EA")
        else:
            bg = QColor(SURFACE)
            border = QColor(BORDER)
        p.setBrush(bg)
        p.setPen(QPen(border, 1))
        p.drawRoundedRect(r, 9, 9)
        p.end()
        super().paintEvent(event)


class MacSwitch(QAbstractButton):
    """iOS-style toggle — fully custom painted."""

    def __init__(self, parent=None, *, checked: bool = False):
        super().__init__(parent)
        self.setCheckable(True)
        self.setChecked(checked)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedSize(T.SWITCH_W, T.SWITCH_H)
        self.toggled.connect(lambda _: self.update())

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        on = self.isChecked()
        if not self.isEnabled():
            track = QColor("#E5E5EA")
            knob = QColor("#FAFAFA")
        elif on:
            track = QColor(ACCENT)
            knob = QColor("#FFFFFF")
        else:
            track = QColor("#D1D1D6")
            knob = QColor("#FFFFFF")
        p.setPen(Qt.NoPen)
        p.setBrush(track)
        p.drawRoundedRect(QRectF(1, 2, T.SWITCH_W - 2, T.SWITCH_H - 4), T.SWITCH_H / 2, T.SWITCH_H / 2)
        kx = (T.SWITCH_W - 14) if on else 14
        p.setBrush(knob)
        p.drawEllipse(QPointF(kx, T.SWITCH_H / 2), 10, 10)
        p.end()


class MacPopupButton(QPushButton):
    """Custom dropdown — full paint, no Qt chrome."""

    def __init__(self, value_to_label: dict[str, str], current: str = "balanced", parent=None):
        super().__init__(parent)
        self._value_to_label = value_to_label
        self._value = current
        self.setObjectName("popupButton")
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(BTN_HEIGHT)
        self.setFixedWidth(CONTROL_COL_WIDTH)
        self._menu = QMenu(self)
        self._menu.setObjectName("popupMenu")
        for value, label in value_to_label.items():
            action = self._menu.addAction(label)
            action.triggered.connect(lambda _c=False, v=value: self.set_value(v))
        self.clicked.connect(lambda: self._menu.exec(self.mapToGlobal(self.rect().bottomLeft())))
        self._refresh_text()

    def set_value(self, value: str):
        self._value = value
        self._refresh_text()

    def value(self) -> str:
        return self._value

    def _refresh_text(self):
        self._label = self._value_to_label.get(self._value, self._value)

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(0.5, 0.5, self.width() - 1, self.height() - 1)
        bg = QColor("#FAFAFC") if self.underMouse() else QColor(SURFACE)
        p.setBrush(bg)
        p.setPen(QPen(QColor(BORDER), 1))
        p.drawRoundedRect(r, 9, 9)
        p.setFont(QFont("Segoe UI", 10, QFont.Medium))
        p.setPen(QColor(TEXT))
        label = getattr(self, "_label", "")
        p.drawText(QRectF(14, 0, self.width() - 36, self.height()), Qt.AlignVCenter, label)
        _paint_line_icon(
            p,
            "chevron_down",
            QRectF(self.width() - 28, 8, 18, self.height() - 16),
            QColor(TEXT_TERTIARY),
        )
        p.end()


class PathButton(QPushButton):
    """Independent path action button — full border + radius."""

    def __init__(self, text: str, parent=None):
        super().__init__(text, parent)
        self.setObjectName("pathBtn")
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(BTN_HEIGHT)
        fm = QFontMetrics(QFont("Segoe UI", 10))
        self.setFixedWidth(max(PATH_BTN_MIN_W, fm.horizontalAdvance(text) + PATH_BTN_PAD_X * 2 + 8))


class PathButtonGroup(QWidget):
    """Mở · Chọn… — separate buttons with gap."""

    def __init__(self, labels: list[str], callbacks: list, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(PATH_BTN_GAP)
        self._buttons: list[PathButton] = []
        for label, cb in zip(labels, callbacks):
            btn = PathButton(label)
            btn.clicked.connect(cb)
            layout.addWidget(btn)
            self._buttons.append(btn)

    @property
    def buttons(self) -> list[PathButton]:
        return self._buttons


class MacSettingsPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        _max_v(self)
        self._grid = QGridLayout(self)
        self._grid.setContentsMargins(0, 2, 0, 0)
        self._grid.setHorizontalSpacing(12)
        self._grid.setVerticalSpacing(T.SETTINGS_ROW_GAP)
        self._grid.setColumnStretch(0, 1)
        self._grid.setColumnMinimumWidth(1, CONTROL_COL_WIDTH)
        self._row = 0

    def add_row(self, title: str, helper: str, control: QWidget) -> None:
        left = QVBoxLayout()
        left.setSpacing(2)
        t = QLabel(title)
        t.setObjectName("settingTitle")
        _max_v(t)
        left.addWidget(t)
        if helper:
            h = QLabel(helper)
            h.setObjectName("settingHelper")
            h.setWordWrap(False)
            _max_v(h)
            left.addWidget(h)
        self._grid.addLayout(left, self._row, 0, Qt.AlignTop)
        rack = QWidget()
        rack.setFixedWidth(CONTROL_COL_WIDTH)
        rl = QHBoxLayout(rack)
        rl.setContentsMargins(0, 2, 0, 0)
        rl.addStretch(1)
        rl.addWidget(control, 0, Qt.AlignRight | Qt.AlignVCenter)
        self._grid.addWidget(rack, self._row, 1, Qt.AlignTop)
        self._row += 1


class SidebarNavItem(QPushButton):
    ICON_MAP = {
        "extract": "document",
        "translate": "globe",
        "patch": "package",
        "dump": "search",
        "index": "list",
        "filter": "filter",
        "review": "eye",
    }

    def __init__(
        self,
        text: str,
        *,
        subtitle: str = "",
        icon_key: str = "",
        workflow: bool = False,
        advanced: bool = False,
        parent=None,
    ):
        super().__init__(parent)
        self._title = text
        self._subtitle = subtitle
        self._icon_key = icon_key
        self._workflow = workflow
        self._advanced = advanced
        self._workflow_state = "pending"
        self._current = False
        self.setObjectName("navItemAdvanced" if advanced else "navItem")
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(NAV_H_ONE)
        self.setMinimumHeight(NAV_H_ONE)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def sizeHint(self) -> QSize:
        return QSize(200, NAV_H_ONE)

    def set_workflow_state(self, state: str):
        self._workflow_state = state
        self.update()

    def set_current(self, current: bool) -> None:
        if self._advanced:
            current = False
        self._current = current
        self.update()

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        mx = 8
        rect = QRectF(mx, 3, w - mx * 2, h - 6)
        is_current = self._current and self._workflow
        if not self.isEnabled():
            fg, sub = QColor("#AEAEB2"), QColor("#AEAEB2")
            bg = None
        elif is_current:
            bg = QColor(ACCENT_SUBTLE)
            fg, sub = QColor(ACCENT), QColor(TEXT_MUTED)
        elif self.underMouse():
            bg = QColor("#F2F2F4")
            fg, sub = QColor(TEXT), QColor(TEXT_MUTED)
        else:
            bg = None
            fg, sub = QColor(TEXT), QColor(TEXT_TERTIARY)
        if bg:
            p.setPen(Qt.NoPen)
            p.setBrush(bg)
            p.drawRoundedRect(rect, 11, 11)
        kind = self.ICON_MAP.get(self._icon_key, "document")
        icon_fg = QColor(ACCENT) if is_current else QColor(TEXT_TERTIARY)
        icon_bg = QColor(ACCENT_SUBTLE) if is_current else QColor(T.C_NAV_ICON_BG)
        ix = int(mx + 10)
        iy = h // 2
        tile = T.ICON_NAV
        p.setBrush(icon_bg)
        p.setPen(Qt.NoPen)
        p.drawRoundedRect(ix - tile // 2, iy - tile // 2, tile, tile, 8, 8)
        _paint_line_icon(p, kind, QRectF(ix - 10, iy - 10, 20, 20), icon_fg)
        tx = mx + 38
        title_font = QFont("Segoe UI", int(T.FS_NAV_TITLE), QFont.DemiBold if is_current else QFont.Medium)
        p.setFont(title_font)
        p.setPen(fg)
        fm = QFontMetrics(title_font)
        p.drawText(tx, (h + fm.ascent() - fm.descent()) // 2, self._title)
        if self._workflow:
            cx = w - mx - 12
            cy = h // 2
            if self._workflow_state == "done":
                p.setBrush(QColor("#34C759"))
                p.setPen(Qt.NoPen)
                p.drawEllipse(QPointF(cx, cy), 5, 5)
                p.setPen(QPen(QColor("#FFFFFF"), 1.3))
                p.drawLine(QPointF(cx - 2.5, cy), QPointF(cx - 0.5, cy + 2))
                p.drawLine(QPointF(cx - 0.5, cy + 2), QPointF(cx + 3.5, cy - 2.5))
            elif self._workflow_state == "current":
                p.setBrush(QColor(ACCENT))
                p.setPen(Qt.NoPen)
                p.drawEllipse(QPointF(cx, cy), 6, 6)
            else:
                p.setBrush(Qt.NoBrush)
                p.setPen(QPen(QColor("#C7C7CC"), 1.5))
                p.drawEllipse(QPointF(cx, cy), 5, 5)
        p.end()


class SidebarLink(QPushButton):
    ICON_MAP = {"Cài đặt": "gear", "Giới thiệu": "info"}

    def __init__(self, text: str, parent=None):
        super().__init__(parent)
        self._label = text
        self._icon = self.ICON_MAP.get(text, "gear")
        self.setObjectName("sidebarLink")
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(40)

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        fg = QColor("#525255") if not self.underMouse() else QColor(TEXT)
        _paint_line_icon(p, self._icon, QRectF(20, 12, 16, 16), fg)
        p.setFont(QFont("Segoe UI", 10, QFont.Medium))
        p.setPen(fg)
        p.drawText(42, 25, self._label)
        p.end()


class CollapsibleSection(QWidget):
    toggled = Signal(bool)

    def __init__(self, title: str, *, expanded: bool = False, parent=None):
        super().__init__(parent)
        _max_v(self)
        self._expanded = expanded
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 0)
        layout.setSpacing(0)
        self._header = QToolButton()
        self._header.setObjectName("sectionToggleAdvanced")
        self._header.setText(title.upper())
        self._header.setCheckable(True)
        self._header.setChecked(expanded)
        self._header.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self._header.setArrowType(Qt.DownArrow if expanded else Qt.RightArrow)
        self._header.setFixedHeight(28)
        self._header.clicked.connect(self.toggle)
        layout.addWidget(self._header)
        self._body = QWidget()
        _max_v(self._body)
        self._body_layout = QVBoxLayout(self._body)
        self._body_layout.setContentsMargins(0, 0, 0, 0)
        self._body_layout.setSpacing(0)
        layout.addWidget(self._body)
        self._set_body_visible(expanded)

    def add_widget(self, widget: QWidget):
        _max_v(widget)
        self._body_layout.addWidget(widget)
        widget.setVisible(self._expanded)

    def _set_body_visible(self, visible: bool) -> None:
        self._expanded = visible
        self._body.setVisible(visible)
        for i in range(self._body_layout.count()):
            item = self._body_layout.itemAt(i)
            w = item.widget() if item else None
            if w:
                w.setVisible(visible)
        if visible:
            self._body.setMaximumHeight(16777215)
        else:
            self._body.setFixedHeight(0)
            self._body.setMaximumHeight(0)
        self.updateGeometry()

    def toggle(self):
        self._expanded = not self._expanded
        self._header.setChecked(self._expanded)
        self._header.setArrowType(Qt.DownArrow if self._expanded else Qt.RightArrow)
        self._set_body_visible(self._expanded)
        self.toggled.emit(self._expanded)


class PanelChevron(QToolButton):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("panelChevron")
        self.setCheckable(True)
        self.setFixedSize(TOGGLE_HIT, TOGGLE_HIT)
        self.setArrowType(Qt.DownArrow)
        self.setAutoRaise(True)
        self.setCursor(Qt.PointingHandCursor)

    def hitButton(self, pos):
        pad = 8
        return QRect(-pad, -pad, self.width() + pad * 2, self.height() + pad * 2).contains(pos)


class StatusChip(QLabel):
    def __init__(self, text: str = "", parent=None):
        super().__init__(text, parent)
        self.setFixedHeight(CHIP_HEIGHT)
        self.setMinimumWidth(52)
        self.setAlignment(Qt.AlignCenter)
        self.setContentsMargins(10, 0, 10, 0)


class CollapsedPanel(QWidget):
    """Progress / Log — elevated card with icon + title/subtitle + chevron."""

    def __init__(self, kind: str, title: str, *, idle_hint: str = "", parent=None):
        super().__init__(parent)
        _max_v(self)
        self._card = MacCard(slim=True, elevated=False)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(self._card)
        self._card._layout.setSpacing(0)
        self._card._layout.setContentsMargins(14, 10, 14, 10)
        self._card.setMinimumHeight(T.PANEL_H)

        header = QWidget()
        header.setMinimumHeight(COLLAPSED_H)
        header.setMaximumHeight(COLLAPSED_H)
        hl = QHBoxLayout(header)
        hl.setContentsMargins(0, 0, 0, 0)
        hl.setSpacing(12)
        self._icon = TintIcon(kind, size=T.PANEL_ICON, tint=ACCENT_SUBTLE, fg=ACCENT, radius=10)
        hl.addWidget(self._icon, 0, Qt.AlignVCenter)
        text_col = QVBoxLayout()
        text_col.setSpacing(3)
        text_col.setContentsMargins(0, 0, 0, 0)
        self._title = QLabel(title)
        self._title.setObjectName("cardTitle")
        _max_v(self._title)
        text_col.addWidget(self._title)
        self._subtitle = QLabel(idle_hint)
        self._subtitle.setObjectName("panelSubtitle")
        _max_v(self._subtitle)
        text_col.addWidget(self._subtitle)
        hl.addLayout(text_col, 1)
        self._chip = StatusChip("")
        self._chip.setVisible(False)
        hl.addWidget(self._chip, 0, Qt.AlignVCenter)
        self._chevron = PanelChevron()
        hl.addWidget(self._chevron, 0, Qt.AlignVCenter)
        self._card.body.addWidget(header)

        self._body_host = QWidget()
        _max_v(self._body_host)
        self._body_layout = QVBoxLayout(self._body_host)
        self._body_layout.setContentsMargins(0, 12, 0, 2)
        self._body_layout.setSpacing(10)
        self._card.body.addWidget(self._body_host)
        self._chevron.clicked.connect(self._on_chevron)

    @property
    def toggle(self):
        return self._chevron

    def set_body_widget(self, widget: QWidget) -> None:
        self._body_layout.addWidget(widget)

    def _on_chevron(self):
        self.set_expanded(self._chevron.isChecked())

    def set_expanded(self, expanded: bool) -> None:
        self._chevron.setChecked(expanded)
        self._chevron.setArrowType(Qt.UpArrow if expanded else Qt.DownArrow)
        self._body_host.setVisible(expanded)
        if expanded:
            self._body_host.setMaximumHeight(16777215)
            self._card._layout.setContentsMargins(CARD_PAD, 16, CARD_PAD, CARD_PAD)
        else:
            self._body_host.setMaximumHeight(0)
            self._card._layout.setContentsMargins(CARD_PAD, 16, CARD_PAD, 16)
        self._card.updateGeometry()

    def set_idle(self, text: str) -> None:
        self._subtitle.setText(text)
        self._subtitle.setVisible(True)
        self._chip.setVisible(False)

    def set_active_chip(self, text: str, fg: str, bg: str) -> None:
        self._subtitle.setVisible(False)
        self._chip.setText(text)
        self._chip.setStyleSheet(
            f"background:{bg}; color:{fg}; border-radius:8px; font-size:9pt; font-weight:600;"
        )
        self._chip.setVisible(True)


class PrimaryButton(QPushButton):
    """Hero CTA — blue pill with play icon."""

    def __init__(self, text: str, parent=None):
        super().__init__(parent)
        self._label = text
        self.setObjectName("primary")
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(PRIMARY_BTN_HEIGHT)
        self.setMinimumWidth(PRIMARY_BTN_MIN_W)

    def set_label(self, text: str) -> None:
        self._label = text.replace("▶  ", "").replace("▶ ", "")
        self.update()

    def setText(self, text: str) -> None:  # noqa: N802
        self.set_label(text)

    def text(self) -> str:
        return self._label

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(0.5, 0.5, self.width() - 1, self.height() - 1)
        if not self.isEnabled():
            p.setBrush(QColor("#B0D4FF"))
        elif self.underMouse():
            p.setBrush(QColor(ACCENT_HOVER))
        else:
            p.setBrush(QColor(ACCENT))
        p.setPen(Qt.NoPen)
        p.drawRoundedRect(r, 10, 10)
        _paint_line_icon(p, "play", QRectF(14, 12, 18, self.height() - 24), QColor("#FFFFFF"))
        p.setFont(QFont("Segoe UI", 11, QFont.DemiBold))
        p.setPen(QColor("#FFFFFF"))
        fm = QFontMetrics(p.font())
        p.drawText(38, (self.height() + fm.ascent() - fm.descent()) // 2, self._label)
        p.end()


class FooterLink(QPushButton):
    def __init__(self, text: str, icon_kind: str, parent=None):
        super().__init__(parent)
        self._label = text
        self._icon = icon_kind
        self.setObjectName("footerLink")
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(36)

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        fg = QColor(TEXT_MUTED) if not self.underMouse() else QColor(TEXT)
        _paint_line_icon(p, self._icon, QRectF(6, 10, 16, 16), fg)
        p.setFont(QFont("Segoe UI", 10))
        p.setPen(fg)
        p.drawText(26, 23, self._label)
        p.end()


# Back-compat aliases
PanelCard = CollapsedPanel
IconBadge = TintIcon
