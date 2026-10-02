"""PySide6 main window for VNText Studio."""
from __future__ import annotations

import os
import sys
from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont, QGuiApplication
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from vntext.app_tasks import (
    resolve_package_with_csv,
    resolve_package_with_manifest,
    resolve_package_with_raw,
    run_asset_index_task,
    run_auto_raw_task,
    run_dump_task,
    run_extract_task,
    run_patch_task,
    run_translate_ct2_task,
)
from vntext.app_workflow import workflow_status
from vntext.qt_raw_reviewer import RawCandidateReviewer
from vntext.ref_tokens import (
    C_ACCENT,
    C_ACCENT_SUBTLE,
    CARD_GAP,
    CARD_HEADER_GAP,
    CONTENT_PAD_BOTTOM,
    CONTENT_PAD_TOP,
    CONTENT_PAD_X,
    FOOTER_H,
    ICON_HERO,
    PATHS_COL,
    SECTION_GAP,
    SETTINGS_COL,
    SIDEBAR_W,
)
from vntext.qt_theme import BREAKPOINTS, QT_LIGHT, RAW_FILTER_LABELS, build_stylesheet, status_colors
from vntext.qt_widgets import (
    BTN_HEIGHT,
    CONTENT_GAP,
    CONTENT_MARGIN,
    HERO_ICON_TILE,
    MacLineEdit,
    SIDEBAR_WIDTH,
    AppLogo,
    CollapsedPanel,
    CollapsibleSection,
    FooterLink,
    LineIcon,
    MacCard,
    MacPopupButton,
    MacSettingsPanel,
    MacSwitch,
    PathButtonGroup,
    PrimaryButton,
    SidebarLink,
    SidebarNavItem,
    TintIcon,
    _max_v,
)
from vntext.qt_workers import TaskRunner
from vntext.runtime_paths import default_output_dir, is_frozen
from vntext.ui_progress import ProgressController, play_success_sound
from vntext.ui_theme import truncate_middle
from vntext.app_backend import VERSION


class PathField(QWidget):
    def __init__(self, label: str, browse_cb, parent=None):
        super().__init__(parent)
        _max_v(self)
        self._full_path = ""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        lbl = QLabel(label)
        lbl.setObjectName("fieldLabel")
        layout.addWidget(lbl)
        row = QHBoxLayout()
        row.setSpacing(8)
        self.edit = MacLineEdit()
        self.edit.setReadOnly(True)
        self.edit.setFixedHeight(BTN_HEIGHT)
        row.addWidget(self.edit, 1)
        self._btn_group = PathButtonGroup(
            ["Mở", "Chọn…"],
            [self._open_folder, browse_cb],
        )
        self.open_btn = self._btn_group.buttons[0]
        self._browse_btn = self._btn_group.buttons[1]
        row.addWidget(self._btn_group, 0)
        layout.addLayout(row)
        self.edit.textChanged.connect(self._sync_buttons)

    def text(self) -> str:
        return self._full_path

    def setText(self, value: str) -> None:
        self._full_path = value
        self._apply_elide()
        self._sync_buttons()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._apply_elide()

    def _apply_elide(self):
        if not self._full_path:
            self.edit.setText("")
            self.edit.setToolTip("")
            return
        width = max(80, self.edit.width() - 16)
        chars = max(32, width // 7)
        self.edit.setText(truncate_middle(self._full_path, max_len=chars))
        self.edit.setToolTip(self._full_path)

    def set_enabled(self, enabled: bool) -> None:
        self.edit.setEnabled(enabled)
        has_path = bool(self.text().strip())
        self.open_btn.setEnabled(enabled and has_path)
        self._browse_btn.setEnabled(enabled)

    def _sync_buttons(self):
        has_path = bool(self.text().strip())
        self.open_btn.setEnabled(has_path)

    def _open_folder(self):
        path = self.text().strip()
        if not path:
            return
        p = Path(path)
        target = p if p.is_dir() else p.parent
        if target.exists():
            os.startfile(str(target))

class CollapsibleLog(QWidget):
    LOG_EXPANDED_HEIGHT = 150

    def __init__(self, parent=None):
        super().__init__(parent)
        _max_v(self)
        self._line_count = 0
        self.view = QTextEdit()
        self.view.setObjectName("logView")
        self.view.setReadOnly(True)
        self.view.setMinimumHeight(0)
        self.view.setMaximumHeight(0)
        self.view.setVisible(False)

    def append_line(self, text: str) -> None:
        self._line_count += 1
        self.view.append(text.rstrip())
        self.view.verticalScrollBar().setValue(self.view.verticalScrollBar().maximum())

    def expand(self) -> None:
        self.view.setVisible(True)
        self.view.setMinimumHeight(self.LOG_EXPANDED_HEIGHT)
        self.view.setMaximumHeight(16777215)

    def collapse_if_empty(self) -> None:
        if self._line_count == 0:
            self.view.setVisible(False)
            self.view.setMinimumHeight(0)
            self.view.setMaximumHeight(0)

    @property
    def line_count(self) -> int:
        return self._line_count


class VNTextQtApp(QMainWindow):
    def __init__(self, version: str = VERSION):
        super().__init__()
        self._version = version
        self.setWindowTitle(f"VNText Studio {version}")
        self.resize(1360, 820)
        self.setMinimumSize(920, 700)
        from PySide6.QtGui import QIcon

        from vntext.brand_icon import logo_ico_path

        icon_path = logo_ico_path()
        if icon_path is not None:
            self.setWindowIcon(QIcon(str(icon_path)))
        self._progress = ProgressController()
        self._runner = TaskRunner()
        self._sound_played = False
        self._nav_buttons: list[SidebarNavItem] = []
        self._workflow_buttons: dict[str, SidebarNavItem] = {}
        self._path_fields: list[PathField] = []
        self._metric_labels: dict[str, QLabel] = {}
        self._body_mode = ""
        self._progress_user_expanded = False
        self._build_ui()
        self._apply_progress_snapshot(self._progress.idle())
        self._refresh_workflow_state()
        QTimer.singleShot(0, self._apply_responsive_layout)

    def _default_output(self) -> str:
        if is_frozen():
            return str(default_output_dir())
        return str(Path.cwd() / "VNText_Output" / "Unity_Translation_Package")

    def _build_ui(self):
        central = QWidget()
        central.setObjectName("centralWidget")
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        main_row = QHBoxLayout()
        main_row.setContentsMargins(0, 0, 0, 0)
        main_row.setSpacing(0)
        root.addLayout(main_row, 1)

        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(SIDEBAR_W)
        sb = QVBoxLayout(sidebar)
        sb.setContentsMargins(0, 0, 0, 0)
        sb.setSpacing(0)

        brand = QHBoxLayout()
        brand.setContentsMargins(14, 18, 14, 12)
        brand.setSpacing(10)
        brand.addWidget(AppLogo())
        brand_lbl = QLabel("VNText Studio")
        brand_lbl.setObjectName("sidebarBrand")
        brand.addWidget(brand_lbl, 1)
        sb.addLayout(brand)

        sb.addWidget(self._section_label("QUY TRÌNH"))
        sb.addSpacing(11)
        self._add_workflow_nav(sb, "extract", "Lấy text", "", "extract", self.run_extract)
        self._add_workflow_nav(sb, "translate", "Dịch tự động", "", "translate", self.run_ct2_translate)
        self._add_workflow_nav(sb, "patch", "Tạo patch", "", "patch", self.run_import_patch)

        divider = QFrame()
        divider.setObjectName("sidebarDivider")
        divider.setFixedHeight(1)
        sb.addWidget(divider)

        self._advanced = CollapsibleSection("Công cụ nâng cao", expanded=False)
        for text, key, cmd in (
            ("Dump Unity", "dump", self.run_dump),
            ("Chỉ mục asset", "index", self.run_asset_index),
            ("Lọc raw tự động", "filter", self.run_auto_raw_candidates),
            ("Duyệt raw", "review", self.run_raw_candidate_reviewer),
        ):
            btn = SidebarNavItem(text, icon_key=key, advanced=True)
            btn.clicked.connect(lambda _c=False, b=btn, fn=cmd: self._on_nav(b, fn))
            self._advanced.add_widget(btn)
            self._nav_buttons.append(btn)
        sb.addWidget(self._advanced)
        sb.addStretch(1)

        for label in ("Cài đặt", "Giới thiệu"):
            link = SidebarLink(label)
            sb.addWidget(link)

        status_row = QHBoxLayout()
        status_row.setContentsMargins(16, 10, 16, 8)
        self._status_dot = QLabel("●")
        self._status_dot.setStyleSheet("color:#34C759; font-size:11pt; font-weight:600;")
        self._sidebar_status = QLabel("Sẵn sàng")
        self._sidebar_status.setObjectName("sidebarStatus")
        status_row.addWidget(self._status_dot)
        status_row.addWidget(self._sidebar_status)
        status_row.addStretch(1)
        self._sidebar_version = QLabel(f"v{self._version}")
        self._sidebar_version.setObjectName("sidebarVersion")
        status_row.addWidget(self._sidebar_version)
        sb.addLayout(status_row)
        sb.addSpacing(10)
        main_row.addWidget(sidebar)

        content_wrap = QWidget()
        content_wrap.setObjectName("contentHost")
        wrap_layout = QVBoxLayout(content_wrap)
        wrap_layout.setContentsMargins(0, 0, 0, 0)
        wrap_layout.setSpacing(0)
        content_host = QWidget()
        content_host.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)
        self._content_layout = QVBoxLayout(content_host)
        self._content_layout.setContentsMargins(CONTENT_PAD_X, CONTENT_PAD_TOP, CONTENT_PAD_X, CONTENT_PAD_BOTTOM)
        self._content_layout.setSpacing(SECTION_GAP)
        self._content_layout.setAlignment(Qt.AlignTop)
        wrap_layout.addWidget(content_host, 0, Qt.AlignTop)
        main_row.addWidget(content_wrap, 1)

        self._build_hero()
        self._body_host = QWidget()
        _max_v(self._body_host)
        self._body_grid = QGridLayout(self._body_host)
        self._body_grid.setContentsMargins(0, 0, 0, 0)
        self._body_grid.setHorizontalSpacing(CARD_GAP)
        self._body_grid.setVerticalSpacing(SECTION_GAP)

        self._paths_card = MacCard()
        self._paths_card.body.setSpacing(6)
        self._paths_card.add_header("folder", "Đường dẫn", "Game gốc và thư mục xuất gói dịch.")
        self._paths_card.body.addSpacing(CARD_HEADER_GAP)
        self.input_field = PathField("Game / asset", self.choose_input)
        self.output_field = PathField("Thư mục xuất", self.choose_output)
        self.output_field.setText(self._default_output())
        self._path_fields.extend([self.input_field, self.output_field])
        self._paths_card.body.addWidget(self.input_field)
        self._paths_card.body.addWidget(self.output_field)

        self._options_card = MacCard()
        self._options_card.body.setSpacing(6)
        self._options_card.add_header("gear", "Thiết lập", "Tùy chọn extract và dịch.")
        self._options_card.body.addSpacing(CARD_HEADER_GAP)
        settings = MacSettingsPanel()
        self.separate_review = MacSwitch(checked=True)
        settings.add_row("Tách dòng cần duyệt", "Dòng chưa chắc → file riêng.", self.separate_review)
        self.extract_level = MacPopupButton(RAW_FILTER_LABELS, "balanced")
        settings.add_row("Mức lọc văn bản thô", "Sạch / Cân bằng / Quét sâu", self.extract_level)
        self.translation_overwrite = MacSwitch(checked=False)
        settings.add_row("Ghi đè bản dịch cũ", "Ghi đè translation đã có.", self.translation_overwrite)
        self._options_card.body.addWidget(settings)

        self._content_layout.addWidget(self._body_host)
        self._build_progress_panel()
        self._build_log_panel()

        self.input_field.edit.textChanged.connect(lambda: self._refresh_workflow_state())
        self.output_field.edit.textChanged.connect(lambda: self._refresh_workflow_state())

        footer = QFrame()
        footer.setObjectName("appFooter")
        footer.setFixedHeight(FOOTER_H)
        fl = QHBoxLayout(footer)
        fl.setContentsMargins(CONTENT_PAD_X, 0, CONTENT_PAD_X, 0)
        fl.setSpacing(12)
        tip_row = QHBoxLayout()
        tip_row.setSpacing(8)
        tip_row.addWidget(LineIcon("bulb", "#8E8E93", size=16))
        tip = QLabel("Mẹo: Bạn có thể kéo thả thư mục game vào ô «Game / asset» để chọn nhanh.")
        tip.setObjectName("footerTip")
        tip_row.addWidget(tip, 1)
        fl.addLayout(tip_row, 1)
        for label, icon in (("Hướng dẫn", "book"), ("Hỗ trợ", "help")):
            btn = FooterLink(label, icon)
            fl.addWidget(btn)
        self._dark_btn = FooterLink("Chế độ tối", "moon")
        self._dark_btn.clicked.connect(self._toggle_dark)
        fl.addWidget(self._dark_btn)
        root.addWidget(footer)

    def _section_label(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setObjectName("sectionLabel")
        _max_v(lbl)
        return lbl

    def _add_workflow_nav(self, parent: QVBoxLayout, key: str, text: str, subtitle: str, icon_key: str, cmd):
        btn = SidebarNavItem(text, subtitle=subtitle, icon_key=icon_key, workflow=True)
        btn.clicked.connect(lambda _c=False, b=btn, fn=cmd: self._on_nav(b, fn))
        parent.addWidget(btn)
        self._nav_buttons.append(btn)
        self._workflow_buttons[key] = btn

    def _on_nav(self, btn: SidebarNavItem, cmd):
        cmd()
        self._refresh_workflow_state()

    def _build_hero(self):
        card = MacCard(hero=True)
        row_host = QWidget()
        row_host.setFixedHeight(52)
        row = QHBoxLayout(row_host)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(12)
        row.addWidget(TintIcon("folder", size=ICON_HERO, tint=C_ACCENT_SUBTLE, fg=C_ACCENT, radius=10), 0, Qt.AlignVCenter)
        text_col = QVBoxLayout()
        text_col.setContentsMargins(0, 17, 0, 0)
        text_col.setSpacing(2)
        self._hero_title = QLabel("Chọn thư mục game")
        self._hero_title.setObjectName("heroTitle")
        _max_v(self._hero_title)
        text_col.addWidget(self._hero_title)
        self._hero_hint = QLabel("Chọn game bên dưới, rồi bấm «Lấy text» để xuất CSV.")
        self._hero_hint.setObjectName("heroHint")
        self._hero_hint.setWordWrap(False)
        self._hero_hint.setFixedWidth(268)
        _max_v(self._hero_hint)
        text_col.addWidget(self._hero_hint)
        row.addLayout(text_col, 1)
        self._hero_action = PrimaryButton("Lấy text")
        self._hero_action.clicked.connect(self._on_hero_action)
        btn_wrap = QWidget()
        btn_wrap.setFixedWidth(self._hero_action.minimumWidth())
        btn_l = QVBoxLayout(btn_wrap)
        btn_l.setContentsMargins(0, 18, 0, 0)
        btn_l.addWidget(self._hero_action)
        row.addWidget(btn_wrap, 0, Qt.AlignTop)
        card.body.addWidget(row_host)
        self._hero_card = card
        self._content_layout.addWidget(card)

    def _on_hero_action(self):
        info = workflow_status(self.input_field.text(), self.output_field.text())
        current = info["current"]
        if current == "translate":
            self.run_ct2_translate()
        elif current == "patch":
            self.run_import_patch()
        else:
            self.run_extract("deep")

    def _build_progress_panel(self):
        self._progress_panel = CollapsedPanel("chart", "Tiến trình", idle_hint="Chưa bắt đầu")
        self._progress_panel.toggle.clicked.connect(self._on_progress_toggle)
        body = QWidget()
        _max_v(body)
        bl = QVBoxLayout(body)
        bl.setContentsMargins(0, 0, 0, 0)
        bl.setSpacing(10)
        self._metrics_widget = QWidget()
        _max_v(self._metrics_widget)
        metrics = QGridLayout(self._metrics_widget)
        metrics.setContentsMargins(0, 0, 0, 0)
        metrics.setHorizontalSpacing(20)
        for idx, (key, title, accent) in enumerate(
            (
                ("ratio", "Phần trăm", True),
                ("counts", "Đã xử lý / tổng", False),
                ("time", "Đã chạy", False),
                ("eta", "Còn lại (ETA)", False),
            )
        ):
            cell = QVBoxLayout()
            cell.setSpacing(2)
            lbl = QLabel(title)
            lbl.setObjectName("metricLabel")
            _max_v(lbl)
            cell.addWidget(lbl)
            val = QLabel("")
            val.setObjectName("metricValueAccent" if accent else "metricValue")
            _max_v(val)
            cell.addWidget(val)
            self._metric_labels[key] = val
            metrics.addLayout(cell, 0, idx)
        bl.addWidget(self._metrics_widget)
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setFixedHeight(6)
        _max_v(self.progress_bar)
        bl.addWidget(self.progress_bar)
        item_title = QLabel("Mục hiện tại")
        item_title.setObjectName("metricLabel")
        _max_v(item_title)
        bl.addWidget(item_title)
        self._progress_item = QLabel("")
        self._progress_item.setObjectName("itemLabel")
        self._progress_item.setWordWrap(True)
        _max_v(self._progress_item)
        bl.addWidget(self._progress_item)
        self._progress_panel.set_body_widget(body)
        self._content_layout.addWidget(self._progress_panel)
        self._progress_panel.set_expanded(False)

    def _build_log_panel(self):
        self._log_panel = CollapsedPanel("journal", "Nhật ký", idle_hint="Nhật ký hoạt động sẽ hiển thị ở đây.")
        self.log = CollapsibleLog()
        self._log_panel.set_body_widget(self.log.view)
        self._log_panel.toggle.clicked.connect(self._on_log_toggle)
        self._content_layout.addWidget(self._log_panel)
        self._log_panel.set_expanded(False)

    def _on_log_toggle(self):
        expanded = self._log_panel.toggle.isChecked()
        self._log_panel.set_expanded(expanded)
        if expanded and self.log.line_count > 0:
            self.log.expand()

    def _on_progress_toggle(self):
        self._progress_user_expanded = self._progress_panel.toggle.isChecked()
        self._progress_panel.set_expanded(self._progress_user_expanded)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._apply_responsive_layout()

    def _apply_responsive_layout(self):
        w = max(400, self.width() - SIDEBAR_W - CONTENT_PAD_X * 2)
        mode = "stack" if w < BREAKPOINTS["medium"] else "row"
        if mode == self._body_mode:
            return
        self._body_mode = mode
        while self._body_grid.count():
            item = self._body_grid.takeAt(0)
            if item.widget():
                item.widget().setParent(None)
        if mode == "stack":
            self._body_grid.addWidget(self._paths_card, 0, 0)
            self._body_grid.addWidget(self._options_card, 1, 0)
        else:
            self._body_grid.addWidget(self._paths_card, 0, 0)
            self._body_grid.addWidget(self._options_card, 0, 1)
            self._body_grid.setColumnStretch(0, PATHS_COL)
            self._body_grid.setColumnStretch(1, SETTINGS_COL)

    def _show_progress_mode(self, mode: str):
        idle = mode == "idle"
        if idle:
            self._progress_panel.set_expanded(False)
        else:
            self._progress_user_expanded = True
            self._progress_panel.set_expanded(True)

    def _set_status_badge(self, status: str):
        labels = {"idle": "Chờ", "running": "Đang chạy", "done": "Hoàn tất", "error": "Lỗi"}
        sidebar_labels = {"idle": "Sẵn sàng", "running": "Đang chạy", "done": "Hoàn tất", "error": "Lỗi"}
        dot_colors = {"idle": "#34C759", "running": "#007AFF", "done": "#34C759", "error": "#FF3B30"}
        self._sidebar_status.setText(sidebar_labels.get(status, status))
        self._status_dot.setStyleSheet(f"color:{dot_colors.get(status, '#34C759')}; font-size:9pt;")
        colors = status_colors(QT_LIGHT)
        fg, bg = colors.get(status, colors["idle"])
        if status == "idle":
            self._progress_panel.set_idle("Chưa bắt đầu")
        elif status == "done":
            self._progress_panel.set_idle("Hoàn tất")
        else:
            self._progress_panel.set_active_chip(labels.get(status, status), fg, bg)

    def _apply_progress_snapshot(self, snap):
        self._show_progress_mode("idle" if snap.status == "idle" else "active")
        self.progress_bar.setValue(snap.percent if snap.status != "idle" else 0)
        if snap.status == "idle":
            for key in self._metric_labels:
                self._metric_labels[key].setText("")
            self._progress_item.setText("")
        else:
            self._metric_labels["ratio"].setText(snap.ratio or "0%")
            self._metric_labels["counts"].setText(snap.counts or "—")
            self._metric_labels["time"].setText(snap.time or "Đã chạy: 0s")
            self._metric_labels["eta"].setText(snap.eta if snap.eta else "—")
            self._progress_item.setText(snap.error or snap.item if snap.ok is False else snap.item)
        self._set_status_badge(snap.status)

    def _refresh_workflow_state(self):
        info = workflow_status(self.input_field.text(), self.output_field.text())
        for key, btn in self._workflow_buttons.items():
            btn.set_workflow_state(info["states"].get(key, "pending"))
        current = info["current"]
        for nav in self._nav_buttons:
            nav.set_current(False)
        if current in self._workflow_buttons:
            self._workflow_buttons[current].set_current(True)
        title, hint = info["hero"]
        self._hero_title.setText(title)
        self._hero_hint.setText(hint)
        action_labels = {
            "extract": "Lấy text",
            "translate": "Dịch CT2 / OPUS-MT",
            "patch": "Tạo patch",
            "done": "Mở patch",
        }
        self._hero_action.set_label(action_labels.get(current, "Lấy text"))

    def _set_busy(self, busy: bool):
        for field in self._path_fields:
            field.set_enabled(not busy)
        for btn in self._nav_buttons:
            btn.setEnabled(not busy)
        self.extract_level.setEnabled(not busy)
        self.separate_review.setEnabled(not busy)
        self.translation_overwrite.setEnabled(not busy)
        if busy:
            self._sidebar_status.setText("Đang chạy")
            self._status_dot.setStyleSheet("color:#007AFF; font-size:10pt;")

    def _append_log(self, text: str):
        self.log.append_line(text)
        self.log.expand()
        self._log_panel.set_expanded(True)
        self._log_panel.toggle.setChecked(True)
        self._log_panel.toggle.setArrowType(Qt.UpArrow)
        count = self.log.line_count
        self._log_panel.set_idle(f"{count} dòng")

    def _finish_task(self, ok: bool, summary: str = "", error: str = ""):
        snap = self._progress.complete(ok, summary=summary, error=error)
        self._apply_progress_snapshot(snap)
        self._refresh_workflow_state()
        self._set_busy(False)
        if ok:
            if summary:
                self._append_log(summary)
            if not self._sound_played:
                play_success_sound()
                self._sound_played = True
        else:
            msg = error or summary or "Có lỗi xảy ra."
            self._append_log(f"Lỗi: {msg}")
            QMessageBox.critical(self, "Lỗi", msg)

    def _on_worker_log(self, text: str):
        self._append_log(text)

    def _on_worker_progress(self, info: dict):
        snap = self._progress.update(info)
        self._apply_progress_snapshot(snap)
        if info.get("log"):
            line = f"{snap.ratio} | {snap.step} | {snap.item}"
            if snap.time:
                line += f" | {snap.time}"
            if snap.eta:
                line += f" | ETA {snap.eta}"
            if snap.extra:
                line += f" | {snap.extra}"
            self._append_log(line)

    def _on_worker_complete(self, payload: dict):
        self._finish_task(
            bool(payload.get("ok")),
            summary=str(payload.get("summary") or ""),
            error=str(payload.get("error") or ""),
        )

    def _connect_worker(self):
        worker = self._runner.worker
        if worker is None:
            return
        worker.log.connect(self._on_worker_log)
        worker.progress.connect(self._on_worker_progress)
        worker.complete.connect(self._on_worker_complete)

    def start_task(self, task_name: str, runner, **kwargs) -> bool:
        if self._runner.busy:
            QMessageBox.information(self, "Đang chạy", "Một tác vụ khác đang chạy. Hãy đợi xong.")
            return False
        self._sound_played = False
        self._set_busy(True)
        self.log.expand()
        self._log_panel.set_expanded(True)
        self._log_panel.toggle.setChecked(True)
        self.progress_bar.setValue(0)
        snap = self._progress.begin(task_name, kwargs.pop("status", ""))
        self._apply_progress_snapshot(snap)
        if not self._runner.start(runner, **kwargs):
            self._set_busy(False)
            return False
        self._connect_worker()
        return True

    def _extract_level_value(self) -> str:
        return self.extract_level.value()

    def _toggle_dark(self):
        dark = os.environ.get("VNTEXT_THEME", "").lower() not in ("dark", "1", "true")
        os.environ["VNTEXT_THEME"] = "dark" if dark else "light"
        QApplication.instance().setStyleSheet(build_stylesheet(dark=dark))
        label = "Chế độ sáng" if dark else "Chế độ tối"
        self._dark_btn._label = label
        self._dark_btn._icon = "moon" if not dark else "bulb"
        self._dark_btn.update()

    def choose_input(self):
        path = QFileDialog.getExistingDirectory(self, "Chọn thư mục game")
        if not path:
            path, _ = QFileDialog.getOpenFileName(self, "Hoặc chọn file asset/bundle")
        if path:
            self.input_field.setText(path)

    def choose_output(self):
        path = QFileDialog.getExistingDirectory(self, "Chọn thư mục xuất")
        if path:
            self.output_field.setText(path)

    def run_extract(self, mode: str = "deep"):
        src = self.input_field.text().strip()
        if not src:
            QMessageBox.warning(self, "Thiếu dữ liệu", "Hãy chọn file hoặc thư mục game trước.")
            return
        out = self.output_field.text().strip()
        self.start_task(
            "Lấy text",
            run_extract_task,
            status="Đang bắt đầu lấy text…",
            src=src,
            out=out,
            mode=mode,
            level=self._extract_level_value(),
            separate_review=self.separate_review.isChecked(),
        )

    def run_dump(self):
        src = self.input_field.text().strip()
        if not src:
            QMessageBox.warning(self, "Thiếu dữ liệu", "Hãy chọn file hoặc thư mục game trước.")
            return
        self.start_task("Dump Unity", run_dump_task, src=src, out=self.output_field.text().strip(), level=self._extract_level_value())

    def run_auto_raw_candidates(self):
        package_dir = resolve_package_with_raw(self.output_field.text())
        if package_dir is None:
            selected = QFileDialog.getExistingDirectory(self, "Chọn thư mục có translation.csv và raw_candidates.csv")
            if not selected:
                return
            package_dir = resolve_package_with_raw(selected)
        if package_dir is None:
            QMessageBox.critical(self, "Thiếu file", "Không tìm thấy translation.csv hoặc raw_candidates.csv.")
            return
        ok = QMessageBox.question(
            self,
            "Auto lọc raw candidates",
            "Tự động đưa dòng khá chắc sang translation.csv, rác sang raw_candidates_rejected.csv, dòng lưng chừng giữ lại?",
        )
        if ok != QMessageBox.Yes:
            return
        self.start_task("Auto lọc raw", run_auto_raw_task, package_dir=package_dir)

    def run_asset_index(self):
        src = self.input_field.text().strip()
        if not src:
            QMessageBox.warning(self, "Thiếu dữ liệu", "Hãy chọn file hoặc thư mục game trước.")
            return
        self.start_task("Asset index", run_asset_index_task, src=src, out=self.output_field.text().strip())

    def run_raw_candidate_reviewer(self):
        package_dir = resolve_package_with_raw(self.output_field.text())
        if package_dir is None:
            selected = QFileDialog.getExistingDirectory(self, "Chọn thư mục có translation.csv và raw_candidates.csv")
            if not selected:
                return
            package_dir = resolve_package_with_raw(selected)
        if package_dir is None:
            QMessageBox.critical(self, "Thiếu file", "Không tìm thấy translation.csv hoặc raw_candidates.csv.")
            return
        RawCandidateReviewer(self, package_dir).exec()

    def run_ct2_translate(self):
        resolved = resolve_package_with_csv(self.output_field.text())
        if resolved is None:
            selected = QFileDialog.getExistingDirectory(self, "Chọn thư mục có translation.csv")
            if not selected:
                return
            resolved = resolve_package_with_csv(selected)
        if resolved is None:
            QMessageBox.critical(self, "Thiếu file", "Không tìm thấy translation.csv. Hãy chạy bước 1 trước.")
            return
        package_dir, csv_path = resolved
        if self.translation_overwrite.isChecked():
            ok = QMessageBox.question(
                self,
                "Ghi đè translation",
                "Bạn bật chế độ ghi đè. Các dòng translation đã có có thể bị thay. Tiếp tục?",
            )
            if ok != QMessageBox.Yes:
                return
        self.start_task(
            "Dịch CT2 / OPUS-MT",
            run_translate_ct2_task,
            status="Đang dịch CT2 / OPUS-MT offline…",
            csv_path=csv_path,
            package_dir=package_dir,
            overwrite=self.translation_overwrite.isChecked(),
        )

    def run_import_patch(self):
        src = self.input_field.text().strip()
        if not src:
            QMessageBox.warning(self, "Thiếu dữ liệu", "Hãy chọn file hoặc thư mục game gốc trước.")
            return
        resolved = resolve_package_with_manifest(self.output_field.text())
        if resolved is None:
            selected = QFileDialog.getExistingDirectory(self, "Chọn thư mục có translation.csv và manifest.json")
            if not selected:
                return
            resolved = resolve_package_with_manifest(selected)
        if resolved is None:
            QMessageBox.critical(self, "Thiếu file", "Không tìm thấy translation.csv hoặc manifest.json.")
            return
        package_dir, csv_path, manifest_path = resolved
        self.start_task(
            "Tạo patch",
            run_patch_task,
            status="Đang tạo patch Việt hóa…",
            csv_path=csv_path,
            manifest_path=manifest_path,
            src=src,
            out=str(package_dir / "Patch_Viet_Hoa"),
        )


def _use_dark_theme() -> bool:
    return os.environ.get("VNTEXT_THEME", "").lower() in ("dark", "1", "true")


def launch_qt_window(version: str = VERSION):
    if QApplication.instance() is None:
        QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
        app = QApplication(sys.argv)
        app.setStyle("Fusion")
        app.setStyleSheet(build_stylesheet(dark=_use_dark_theme()))
        app.setFont(QFont("Segoe UI", 11))
    else:
        app = QApplication.instance()
    win = VNTextQtApp(version)
    return app, win


def run_qt_app(version: str = VERSION) -> int:
    app, win = launch_qt_window(version)
    win.show()
    return app.exec()
