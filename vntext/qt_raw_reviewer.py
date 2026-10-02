"""Qt dialog to review and promote raw_candidates.csv rows."""
from __future__ import annotations

import re
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from vntext.package_io import read_csv_rows_file, resolve_translation_package_dir
from vntext.app_backend import promote_raw_candidates


class RawCandidateReviewer(QDialog):
    def __init__(self, parent, package_dir: Path):
        super().__init__(parent)
        self.package_dir = resolve_translation_package_dir(package_dir)
        self.raw_path = self.package_dir / "raw_candidates.csv"
        self.translation_path = self.package_dir / "translation.csv"
        self.setWindowTitle("Duyệt raw_candidates.csv")
        self.resize(1120, 650)
        self.setMinimumSize(900, 480)
        self.rows: list[dict] = []
        self.visible: list[dict] = []
        self.checked_keys: set[str] = set()
        self._build_ui()
        self.reload_rows()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        info = (
            "Tick các dòng là thoại/UI thật trong raw_candidates.csv, rồi bấm Chuyển dòng đã tick. "
            "App sẽ giữ nguyên key, source_text và tên cột CSV."
        )
        root.addWidget(QLabel(info))

        filter_row = QHBoxLayout()
        filter_row.addWidget(QLabel("Lọc:"))
        self.filter_edit = QLineEdit()
        self.filter_edit.textChanged.connect(self.refresh_tree)
        filter_row.addWidget(self.filter_edit, 1)
        filter_btn = QPushButton("Lọc")
        filter_btn.clicked.connect(self.refresh_tree)
        filter_row.addWidget(filter_btn)
        root.addLayout(filter_row)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Tick", "source_text", "file_path/context", "backend", "safety"])
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.ExtendedSelection)
        self.table.cellDoubleClicked.connect(self._toggle_row)
        root.addWidget(self.table, 1)

        actions = QHBoxLayout()
        for text, slot in (
            ("Tick dòng đang chọn", self.check_selected),
            ("Bỏ tick dòng đang chọn", self.uncheck_selected),
            ("Tick toàn bộ dòng đang lọc", self.check_visible),
            ("Chuyển dòng đã tick sang translation.csv", self.promote_checked),
            ("Tải lại", self.reload_rows),
        ):
            btn = QPushButton(text)
            btn.clicked.connect(slot)
            actions.addWidget(btn)
        root.addLayout(actions)

        self.status_label = QLabel()
        root.addWidget(self.status_label)

    @staticmethod
    def _shorten(value: str, limit: int) -> str:
        text = re.sub(r"\s+", " ", str(value or "").strip())
        return text if len(text) <= limit else text[: limit - 1] + "…"

    def reload_rows(self):
        if not self.translation_path.exists() or not self.raw_path.exists():
            QMessageBox.critical(self, "Thiếu file", f"Cần có translation.csv và raw_candidates.csv trong:\n{self.package_dir}")
            self.reject()
            return
        _fields, rows = read_csv_rows_file(self.raw_path)
        self.rows = rows
        self.checked_keys = {key for key in self.checked_keys if any(r.get("key", "").strip() == key for r in rows)}
        self.refresh_tree()

    def _matches_filter(self, row: dict, query: str) -> bool:
        if not query:
            return True
        hay = " ".join(str(row.get(name, "")) for name in ("source_text", "file_path", "context", "backend", "safety")).lower()
        return query.lower() in hay

    def refresh_tree(self):
        query = self.filter_edit.text().strip()
        matched = [row for row in self.rows if self._matches_filter(row, query)]
        self.visible = matched[:2000]
        self.table.setRowCount(len(self.visible))
        for idx, row in enumerate(self.visible):
            key = row.get("key", "").strip()
            mark = "✓" if key in self.checked_keys else ""
            file_context = f"{row.get('file_path', '')} | {row.get('context', '')}"
            for col, val in enumerate(
                (
                    mark,
                    self._shorten(row.get("source_text", ""), 180),
                    self._shorten(file_context, 130),
                    self._shorten(row.get("backend", ""), 40),
                    self._shorten(row.get("safety", ""), 20),
                )
            ):
                item = QTableWidgetItem(val)
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                self.table.setItem(idx, col, item)
        suffix = "" if len(matched) <= 2000 else f" | đang hiện 2000/{len(matched)} dòng khớp lọc"
        self.status_label.setText(f"raw_candidates: {len(self.rows)} dòng | đang tick: {len(self.checked_keys)}{suffix}")

    def _row_keys(self, rows: list[int]) -> set[str]:
        keys = set()
        for idx in rows:
            if 0 <= idx < len(self.visible):
                key = self.visible[idx].get("key", "").strip()
                if key:
                    keys.add(key)
        return keys

    def _toggle_row(self, row: int, _col: int):
        keys = self._row_keys([row])
        for key in keys:
            if key in self.checked_keys:
                self.checked_keys.remove(key)
            else:
                self.checked_keys.add(key)
        self.refresh_tree()

    def check_selected(self):
        rows = sorted({idx.row() for idx in self.table.selectedIndexes()})
        self.checked_keys.update(self._row_keys(rows))
        self.refresh_tree()

    def uncheck_selected(self):
        rows = sorted({idx.row() for idx in self.table.selectedIndexes()})
        self.checked_keys.difference_update(self._row_keys(rows))
        self.refresh_tree()

    def check_visible(self):
        for row in self.visible:
            key = row.get("key", "").strip()
            if key:
                self.checked_keys.add(key)
        self.refresh_tree()

    def promote_checked(self):
        if not self.checked_keys:
            QMessageBox.information(self, "Chưa tick", "Chưa tick dòng nào.")
            return
        count = len(self.checked_keys)
        ok = QMessageBox.question(
            self,
            "Chuyển raw candidates",
            f"Chuyển {count} dòng đã tick sang translation.csv?\n\n"
            "Các dòng này sẽ bị xóa khỏi raw_candidates.csv để dễ theo dõi.",
        )
        if ok != QMessageBox.Yes:
            return
        try:
            result = promote_raw_candidates(self.package_dir, set(self.checked_keys), move=True)
        except Exception as exc:
            QMessageBox.critical(self, "Lỗi", str(exc))
            return
        self.checked_keys.clear()
        self.reload_rows()
        QMessageBox.information(
            self,
            "Xong",
            f"Đã chuyển: {result['promoted']} dòng\n"
            f"Trùng key bỏ qua: {result['skipped_duplicate']}\n"
            f"Còn raw_candidates: {result['remaining_raw']}\n"
            f"translation.csv: {result['translation_rows']} dòng",
        )
