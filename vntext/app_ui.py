from __future__ import annotations

import queue
import re
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk


class RawCandidateReviewer(tk.Toplevel):
    def __init__(self, master, package_dir: Path):
        super().__init__(master)
        self.master_app = master
        self.package_dir = resolve_translation_package_dir(package_dir)
        self.raw_path = self.package_dir / "raw_candidates.csv"
        self.translation_path = self.package_dir / "translation.csv"
        self.title("Duyet raw_candidates.csv")
        self.geometry("1120x650")
        self.minsize(900, 480)
        self.configure(bg=PALETTE["window"])
        apply_theme(self)
        self.filter_var = tk.StringVar()
        self.status_var = tk.StringVar(value="Dang tai raw_candidates.csv...")
        self.rows: list[dict] = []
        self.visible: list[dict] = []
        self.checked_keys: set[str] = set()
        self._build_ui()
        self.reload_rows()

    def _build_ui(self):
        root = ttk.Frame(self, padding=10)
        root.pack(fill="both", expand=True)
        info = (
            "Tick cac dong la thoai/UI that trong raw_candidates.csv, roi bam Chuyen dong da tick. "
            "App se giu nguyen key, source_text va ten cot CSV."
        )
        ttk.Label(root, text=info).grid(row=0, column=0, columnspan=5, sticky="w")
        ttk.Label(root, text="Loc:").grid(row=1, column=0, sticky="w", pady=(8, 4))
        entry = ttk.Entry(root, textvariable=self.filter_var)
        entry.grid(row=1, column=1, columnspan=3, sticky="ew", pady=(8, 4), padx=(4, 8))
        ttk.Button(root, text="Loc", command=self.refresh_tree).grid(row=1, column=4, sticky="ew", pady=(8, 4))
        self.filter_var.trace_add("write", lambda *_: self.refresh_tree())

        columns = ("pick", "source", "file", "backend", "safety")
        self.tree = ttk.Treeview(root, columns=columns, show="headings", selectmode="extended")
        self.tree.heading("pick", text="Tick")
        self.tree.heading("source", text="source_text")
        self.tree.heading("file", text="file_path/context")
        self.tree.heading("backend", text="backend")
        self.tree.heading("safety", text="safety")
        self.tree.column("pick", width=52, minwidth=45, anchor="center", stretch=False)
        self.tree.column("source", width=520, minwidth=240)
        self.tree.column("file", width=340, minwidth=180)
        self.tree.column("backend", width=150, minwidth=100, stretch=False)
        self.tree.column("safety", width=80, minwidth=60, stretch=False)
        self.tree.grid(row=2, column=0, columnspan=5, sticky="nsew")
        yscroll = ttk.Scrollbar(root, orient="vertical", command=self.tree.yview)
        yscroll.grid(row=2, column=5, sticky="ns")
        self.tree.configure(yscrollcommand=yscroll.set)
        self.tree.bind("<Double-1>", self.toggle_current)
        self.tree.bind("<space>", self.toggle_current)

        actions = ttk.Frame(root)
        actions.grid(row=3, column=0, columnspan=5, sticky="ew", pady=(8, 0))
        ttk.Button(actions, text="Tick dong dang chon", command=self.check_selected).pack(side="left", padx=(0, 8))
        ttk.Button(actions, text="Bo tick dong dang chon", command=self.uncheck_selected).pack(side="left", padx=(0, 8))
        ttk.Button(actions, text="Tick toan bo dong dang loc", command=self.check_visible).pack(side="left", padx=(0, 8))
        ttk.Button(actions, text="Chuyen dong da tick sang translation.csv", command=self.promote_checked).pack(side="left", padx=(12, 8))
        ttk.Button(actions, text="Tai lai", command=self.reload_rows).pack(side="left", padx=(0, 8))
        ttk.Label(root, textvariable=self.status_var).grid(row=4, column=0, columnspan=5, sticky="w", pady=(8, 0))
        root.columnconfigure(1, weight=1)
        root.rowconfigure(2, weight=1)

    @staticmethod
    def _shorten(value: str, limit: int) -> str:
        text = re.sub(r"\s+", " ", str(value or "").strip())
        return text if len(text) <= limit else text[:limit - 1] + "…"

    def reload_rows(self):
        if not self.translation_path.exists() or not self.raw_path.exists():
            messagebox.showerror("Thieu file", f"Can co translation.csv va raw_candidates.csv trong:\n{self.package_dir}")
            self.destroy()
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
        query = self.filter_var.get().strip()
        self.tree.delete(*self.tree.get_children())
        matched = [row for row in self.rows if self._matches_filter(row, query)]
        self.visible = matched[:2000]
        for idx, row in enumerate(self.visible):
            key = row.get("key", "").strip()
            mark = "✓" if key in self.checked_keys else ""
            file_context = f"{row.get('file_path','')} | {row.get('context','')}"
            self.tree.insert(
                "", "end", iid=str(idx),
                values=(
                    mark,
                    self._shorten(row.get("source_text", ""), 180),
                    self._shorten(file_context, 130),
                    self._shorten(row.get("backend", ""), 40),
                    self._shorten(row.get("safety", ""), 20),
                ),
            )
        suffix = "" if len(matched) <= 2000 else f" | dang hien 2000/{len(matched)} dong khop loc"
        self.status_var.set(f"raw_candidates: {len(self.rows)} dong | dang tick: {len(self.checked_keys)}{suffix}")

    def keys_from_selection(self) -> set[str]:
        keys = set()
        for iid in self.tree.selection():
            try:
                row = self.visible[int(iid)]
            except (ValueError, IndexError):
                continue
            key = row.get("key", "").strip()
            if key:
                keys.add(key)
        return keys

    def toggle_current(self, event=None):
        keys = self.keys_from_selection()
        if not keys and self.tree.focus():
            try:
                row = self.visible[int(self.tree.focus())]
                keys = {row.get("key", "").strip()}
            except Exception:
                keys = set()
        for key in keys:
            if key in self.checked_keys:
                self.checked_keys.remove(key)
            elif key:
                self.checked_keys.add(key)
        self.refresh_tree()
        return "break"

    def check_selected(self):
        self.checked_keys.update(self.keys_from_selection())
        self.refresh_tree()

    def uncheck_selected(self):
        self.checked_keys.difference_update(self.keys_from_selection())
        self.refresh_tree()

    def check_visible(self):
        for row in self.visible:
            key = row.get("key", "").strip()
            if key:
                self.checked_keys.add(key)
        self.refresh_tree()

    def promote_checked(self):
        if not self.checked_keys:
            messagebox.showinfo("Chua tick", "Chua tick dong nao.")
            return
        count = len(self.checked_keys)
        ok = messagebox.askyesno(
            "Chuyen raw candidates",
            f"Chuyen {count} dong da tick sang translation.csv?\n\n"
            "Cac dong nay se bi xoa khoi raw_candidates.csv de de theo doi."
        )
        if not ok:
            return
        try:
            result = promote_raw_candidates(self.package_dir, set(self.checked_keys), move=True)
        except Exception as exc:
            messagebox.showerror("Loi", str(exc))
            return
        self.checked_keys.clear()
        self.reload_rows()
        messagebox.showinfo(
            "Xong",
            f"Da chuyen: {result['promoted']} dong\n"
            f"Trung key bo qua: {result['skipped_duplicate']}\n"
            f"Con raw_candidates: {result['remaining_raw']}\n"
            f"translation.csv: {result['translation_rows']} dong"
        )

from vntext.runtime_paths import default_output_dir, is_frozen
from vntext.ui_progress import ProgressController, play_success_sound
from vntext.ui_theme import (
    BREAKPOINTS,
    FONTS,
    PALETTE,
    RAW_FILTER_LABELS,
    SPACING,
    MacButton,
    MacCard,
    MacCollapsibleLog,
    MacCollapsibleSection,
    MacPathField,
    MacPopupButton,
    MacProgressbar,
    MacSettingRow,
    MacStatusChip,
    MacSwitch,
    SidebarNavItem,
    apply_theme,
)


class VNTextApp(tk.Tk):
    SIDEBAR_WIDTH = 268
    CONTENT_PAD = 20

    WORKFLOW_STEPS = (
        ("extract", "Lấy text", "Xuất CSV"),
        ("translate", "Dịch tự động", "CT2 / OPUS-MT"),
        ("patch", "Tạo patch", "Việt hóa game"),
    )

    def __init__(self):
        super().__init__()
        self.title(f"VNText Studio {VERSION}")
        self.geometry("1360x820")
        self.minsize(920, 700)
        self.messages = queue.Queue()
        self.input_path = tk.StringVar()
        if is_frozen():
            default_out = str(default_output_dir())
        else:
            default_out = str(Path.cwd() / "VNText_Output" / "Unity_Translation_Package")
        self.output_path = tk.StringVar(value=default_out)
        self.separate_review = tk.BooleanVar(value=True)
        self.extract_level = tk.StringVar(value="balanced")
        self.translation_overwrite = tk.BooleanVar(value=False)
        self._progress = ProgressController()
        self._busy = False
        self._sound_played = False
        self._sidebar_items: list[SidebarNavItem] = []
        self._workflow_items: dict[str, SidebarNavItem] = {}
        self._active_sidebar: SidebarNavItem | None = None
        self._path_widgets: list = []
        self._cards: list[MacCard] = []
        self._wrap_labels: list[tk.Label] = []
        self._metric_cells: list[tk.Frame] = []
        self._progress_metrics: tk.Frame | None = None
        self._progress_detail: tk.Frame | None = None
        self._main_frame: tk.Frame | None = None
        self._hero_title: tk.Label | None = None
        self._hero_hint: tk.Label | None = None
        self.progress_item_label: tk.Label | None = None
        self.input_path.trace_add("write", lambda *_: self._refresh_workflow_state())
        self.output_path.trace_add("write", lambda *_: self._refresh_workflow_state())
        self._build()
        idle = self._progress.idle()
        self._apply_progress_snapshot(idle)
        self._refresh_workflow_state()
        self.after(120, self._poll)

    def _build(self):
        apply_theme(self)
        self.configure(bg=PALETTE["window"])

        shell = tk.Frame(self, bg=PALETTE["window"])
        shell.pack(fill="both", expand=True)

        sidebar = tk.Frame(shell, bg=PALETTE["sidebar"], width=self.SIDEBAR_WIDTH)
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)
        tk.Frame(sidebar, bg=PALETTE["border_strong"], width=1).pack(side="right", fill="y")
        self._build_sidebar(sidebar)

        main_outer = tk.Frame(shell, bg=PALETTE["window"])
        main_outer.pack(side="left", fill="both", expand=True, padx=(0, SPACING["md"]), pady=SPACING["md"])

        main = tk.Frame(main_outer, bg=PALETTE["window"])
        self._main_frame = main
        main.pack(fill="both", expand=True, padx=SPACING["md"])
        main.grid_rowconfigure(3, weight=1)
        main.grid_columnconfigure(0, weight=1)

        def _layout_main(_event=None):
            w = max(400, main_outer.winfo_width() - SPACING["md"] * 2)
            self._apply_responsive_layout(w)
            self._sync_cards()

        main_outer.bind("<Configure>", _layout_main)

        self._build_hero(main)
        body = tk.Frame(main, bg=PALETTE["window"])
        body.grid(row=1, column=0, sticky="ew")
        body.columnconfigure(0, weight=1)
        body.columnconfigure(1, weight=1)
        self._body = body
        self._build_paths_card(body, 0)
        self._build_options_card(body, 1)
        self._build_progress_card(main)
        self._build_log_card(main)
        self.after_idle(lambda: (_layout_main(), self._sync_cards()))

    def _apply_responsive_layout(self, content_w: int):
        self._last_content_w = content_w
        wrap = max(220, content_w - 48)
        for card in self._cards:
            card.set_wraplength(wrap)
        for label in self._wrap_labels:
            label.configure(wraplength=wrap)
        if self.progress_item_label:
            self.progress_item_label.configure(wraplength=wrap)
        if self._hero_hint:
            self._hero_hint.configure(wraplength=min(wrap, 760))

        narrow = content_w < BREAKPOINTS["narrow"]
        medium = content_w < BREAKPOINTS["medium"]
        if hasattr(self, "_body"):
            children = list(self._body.winfo_children())
            if narrow or medium:
                for i, child in enumerate(children):
                    child.grid(row=i, column=0, sticky="nsew", pady=(0, SPACING["md"]))
                self._body.rowconfigure(0, weight=0)
                self._body.rowconfigure(1, weight=0)
            elif len(children) >= 2:
                children[0].grid(row=0, column=0, sticky="nsew", padx=(0, SPACING["sm"]))
                children[1].grid(row=0, column=1, sticky="nsew", padx=(SPACING["sm"], 0))
                self._body.rowconfigure(0, weight=1)

        if self._metric_cells and self._progress_metrics:
            for idx, cell in enumerate(self._metric_cells):
                cell.grid_forget()
                if narrow:
                    cell.grid(row=idx // 2, column=idx % 2, sticky="nsew", padx=(0 if idx % 2 == 0 else SPACING["xs"], 0), pady=(0, SPACING["sm"]))
                else:
                    cell.grid(row=0, column=idx, sticky="nsew", padx=(0 if idx == 0 else SPACING["sm"], 0))

    def _select_sidebar(self, item: SidebarNavItem):
        self._active_sidebar = item
        for nav in self._sidebar_items:
            nav.set_selected(nav is item)

    def _package_dir(self) -> Path:
        return resolve_translation_package_dir(self.output_path.get().strip())

    def _has_translations(self, csv_path: Path) -> bool:
        if not csv_path.is_file():
            return False
        try:
            import csv
            with csv_path.open("r", encoding="utf-8-sig", newline="") as fh:
                reader = csv.DictReader(fh)
                for row in reader:
                    if str(row.get("translation") or row.get("translated_text") or "").strip():
                        return True
        except OSError:
            return False
        return False

    def _workflow_status(self) -> dict[str, str]:
        package = self._package_dir()
        csv_path = package / "translation.csv"
        manifest_path = package / "manifest.json"
        patch_dir = package / "Patch_Viet_Hoa"
        has_game = bool(self.input_path.get().strip())
        has_extract = csv_path.is_file() and manifest_path.is_file()
        has_translate = self._has_translations(csv_path)
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

    def _refresh_workflow_state(self):
        info = self._workflow_status()
        for key, item in self._workflow_items.items():
            item.set_workflow_state(info["states"].get(key, "pending"))
        current = info["current"]
        if current in self._workflow_items:
            self._select_sidebar(self._workflow_items[current])
        elif self._workflow_items:
            self._select_sidebar(self._workflow_items["extract"])
        if self._hero_title and self._hero_hint:
            title, hint = info["hero"]
            self._hero_title.configure(text=title)
            self._hero_hint.configure(text=hint)

    def _build_hero(self, parent):
        hero = MacCard(parent, slim=True)
        hero.grid(row=0, column=0, sticky="ew", pady=(0, SPACING["sm"]))
        self._cards.append(hero)
        row = tk.Frame(hero.content, bg=PALETTE["surface"])
        row.pack(fill="x")
        row.columnconfigure(0, weight=1)
        left = tk.Frame(row, bg=PALETTE["surface"])
        left.grid(row=0, column=0, sticky="ew")
        self._hero_title = tk.Label(left, text="Chọn thư mục game", bg=PALETTE["surface"], fg=PALETTE["text"], font=FONTS["hero_title"])
        self._hero_title.pack(anchor="w")
        self._hero_hint = tk.Label(
            left,
            text="Chọn game bên dưới, rồi bấm «Lấy text» để xuất CSV.",
            bg=PALETTE["surface"],
            fg=PALETTE["text_muted"],
            font=FONTS["caption"],
            wraplength=720,
            justify="left",
        )
        self._hero_hint.pack(anchor="w", pady=(2, 0))
        self._wrap_labels.append(self._hero_hint)
        MacButton(row, text="Lấy text", command=lambda: self.run_extract("deep"), primary=True).grid(row=0, column=1, sticky="e", padx=(SPACING["md"], 0))

    def _build_sidebar(self, sidebar: tk.Frame):
        header = tk.Frame(sidebar, bg=PALETTE["sidebar"])
        header.pack(fill="x", padx=SPACING["lg"], pady=(SPACING["lg"], SPACING["md"]))
        tk.Label(header, text="VNText Studio", bg=PALETTE["sidebar"], fg=PALETTE["text"], font=FONTS["app_title"]).pack(anchor="w")

        self._section_label(sidebar, "Quy trình")
        self._add_workflow_item(sidebar, "extract", "Lấy text", lambda: self.run_extract("deep"), subtitle="Xuất CSV", icon="extract")
        self._add_workflow_item(sidebar, "translate", "Dịch tự động", self.run_ct2_translate, subtitle="CT2 · OPUS-MT", icon="translate")
        self._add_workflow_item(sidebar, "patch", "Tạo patch", self.run_import_patch, subtitle="Việt hóa game", icon="patch")

        tk.Frame(sidebar, bg=PALETTE["border"], height=1).pack(fill="x", padx=SPACING["lg"], pady=SPACING["md"])

        advanced = MacCollapsibleSection(sidebar, "Công cụ nâng cao", expanded=False)
        advanced.pack(fill="x")
        for text, cmd, sub in (
            ("Dump Unity", self.run_dump, "Soi asset"),
            ("Chỉ mục asset", self.run_asset_index, ""),
            ("Lọc raw tự động", self.run_auto_raw_candidates, ""),
            ("Duyệt raw", self.run_raw_candidate_reviewer, ""),
        ):
            item = SidebarNavItem(advanced._body, text=text, command=cmd, subtitle=sub, icon="tool", on_select=self._select_sidebar)
            advanced.add(item)
            self._sidebar_items.append(item)

        tk.Frame(sidebar, bg=PALETTE["sidebar"]).pack(fill="both", expand=True)
        tk.Label(
            sidebar,
            text=f"v{VERSION}",
            bg=PALETTE["sidebar"],
            fg=PALETTE["text_tertiary"],
            font=FONTS["nav_sub"],
        ).pack(side="bottom", anchor="w", padx=SPACING["lg"], pady=SPACING["md"])

    def _add_workflow_item(self, parent, key: str, text, command, *, subtitle: str = "", icon: str = "tool"):
        item = SidebarNavItem(parent, text=text, subtitle=subtitle, icon=icon, command=command, on_select=self._select_sidebar, workflow=True)
        item.pack(fill="x")
        self._sidebar_items.append(item)
        self._workflow_items[key] = item

    def _section_label(self, parent, text: str):
        tk.Label(
            parent,
            text=text,
            bg=PALETTE["sidebar"],
            fg=PALETTE["text_tertiary"],
            font=FONTS["nav_section"],
        ).pack(anchor="w", padx=SPACING["lg"], pady=(SPACING["sm"], SPACING["xs"]))

    def _add_sidebar_item(self, parent, text, command, *, subtitle: str = "", icon: str = "tool"):
        item = SidebarNavItem(parent, text=text, subtitle=subtitle, icon=icon, command=command, on_select=self._select_sidebar)
        item.pack(fill="x")
        self._sidebar_items.append(item)

    def _build_paths_card(self, parent, col: int = 0):
        card = MacCard(parent, title="Đường dẫn", subtitle="Game gốc và thư mục xuất gói dịch.", compact=True)
        card.grid(row=0, column=col, sticky="nsew", padx=(0, SPACING["sm"]))
        self._cards.append(card)
        body = card.content
        self._path_field(body, "Game / asset", self.input_path, self.choose_input)
        self._path_field(body, "Thư mục xuất", self.output_path, self.choose_output, last=True)

    def _path_field(self, parent, label, variable, browse_cmd, *, last: bool = False):
        block = tk.Frame(parent, bg=PALETTE["surface"])
        block.pack(fill="x", pady=(0, 0 if last else SPACING["sm"]))
        tk.Label(block, text=label, bg=PALETTE["surface"], fg=PALETTE["text_muted"], font=FONTS["caption"]).pack(anchor="w", pady=(0, SPACING["xs"]))
        field = MacPathField(block, textvariable=variable, browse_cmd=browse_cmd)
        field.pack(fill="x")
        self._path_widgets.append(field)
        block.bind("<Configure>", lambda _e: parent.event_generate("<Configure>"))

    def _build_options_card(self, parent, col: int = 1):
        card = MacCard(parent, title="Thiết lập", subtitle="Tùy chọn extract và dịch.", compact=True)
        card.grid(row=0, column=col, sticky="nsew", padx=(SPACING["sm"], 0))
        self._cards.append(card)
        body = card.content

        row1 = MacSettingRow(body, "Tách dòng cần duyệt", "Tách dòng chưa chắc sang file riêng.", compact_control=True, tight=True)
        row1.pack(fill="x", pady=(0, SPACING["sm"]))
        MacSwitch(row1.control_host, variable=self.separate_review).pack(anchor="e")

        row2 = MacSettingRow(body, "Mức lọc văn bản thô", "Sạch · Cân bằng (khuyên dùng) · Quét sâu.", tight=True)
        row2.pack(fill="x", pady=(0, SPACING["sm"]))
        popup = MacPopupButton(row2.control_host, self.extract_level, RAW_FILTER_LABELS, width=160)
        popup.pack(anchor="e")
        self._path_widgets.append(popup)

        row3 = MacSettingRow(body, "Ghi đè bản dịch cũ", "Cho phép thay nội dung đã có.", compact_control=True, tight=True)
        row3.pack(fill="x")
        MacSwitch(row3.control_host, variable=self.translation_overwrite).pack(anchor="e")

    def _build_progress_card(self, parent):
        card = MacCard(parent, title="Tiến trình", compact=True)
        card.grid(row=2, column=0, sticky="ew", pady=(0, SPACING["sm"]))
        self._cards.append(card)
        body = card.content

        self.progress_step_var = tk.StringVar(value="Sẵn sàng")
        self.progress_ratio_var = tk.StringVar(value="")
        self.progress_counts_var = tk.StringVar(value="")
        self.progress_item_var = tk.StringVar(value="Chưa bắt đầu")
        self.progress_time_var = tk.StringVar(value="")
        self.progress_eta_var = tk.StringVar(value="")
        self._metric_cells = []

        header = tk.Frame(body, bg=PALETTE["surface"])
        header.pack(fill="x", pady=(0, SPACING["sm"]))
        left = tk.Frame(header, bg=PALETTE["surface"])
        left.pack(side="left", fill="x", expand=True)
        tk.Label(left, textvariable=self.progress_step_var, bg=PALETTE["surface"], fg=PALETTE["text"], font=FONTS["section"]).pack(anchor="w")
        self._status_chip = MacStatusChip(header)
        self._status_chip.pack(side="right", anchor="ne")

        self._progress_metrics = tk.Frame(body, bg=PALETTE["surface"])
        for col in range(4):
            self._progress_metrics.columnconfigure(col, weight=1, uniform="metric")

        def _metric(title: str, var: tk.StringVar, accent: bool = False):
            cell = tk.Frame(self._progress_metrics, bg=PALETTE["surface"])
            tk.Label(cell, text=title, bg=PALETTE["surface"], fg=PALETTE["text_muted"], font=FONTS["metric_label"]).pack(anchor="w")
            tk.Label(
                cell, textvariable=var, bg=PALETTE["surface"],
                fg=PALETTE["accent"] if accent else PALETTE["text"],
                font=FONTS["metric"] if accent else FONTS["body_medium"],
            ).pack(anchor="w", pady=(2, 0))
            self._metric_cells.append(cell)

        _metric("Phần trăm", self.progress_ratio_var, accent=True)
        _metric("Đã xử lý / tổng", self.progress_counts_var)
        _metric("Đã chạy", self.progress_time_var)
        _metric("Còn lại (ETA)", self.progress_eta_var)

        self.progress = MacProgressbar(body)
        self._progress_detail = tk.Frame(body, bg=PALETTE["surface"])
        self._eta_label = tk.Label(
            self._progress_detail,
            text="Mục hiện tại",
            bg=PALETTE["surface"],
            fg=PALETTE["text_muted"],
            font=FONTS["caption"],
            anchor="w",
        )
        self._eta_label.pack(fill="x")
        self.progress_item_label = tk.Label(
            self._progress_detail,
            textvariable=self.progress_item_var,
            bg=PALETTE["surface"],
            fg=PALETTE["text_secondary"],
            font=FONTS["callout"],
            anchor="w",
            justify="left",
            wraplength=900,
        )
        self.progress_item_label.pack(fill="x", pady=(SPACING["xs"], 0))
        self._progress_detail.pack(fill="x")
        self._show_progress_mode("idle")

    def _build_log_card(self, parent):
        wrap = tk.Frame(
            parent, bg=PALETTE["surface"],
            highlightbackground=PALETTE["border"], highlightthickness=1,
        )
        wrap.grid(row=3, column=0, sticky="nsew", pady=(0, SPACING["sm"]))
        inner = tk.Frame(wrap, bg=PALETTE["surface"], padx=SPACING["md"], pady=SPACING["sm"])
        inner.pack(fill="both", expand=True)
        self.log = MacCollapsibleLog(inner)
        self.log.pack(fill="both", expand=True)
        self._log_wrap = wrap

    def _sync_cards(self):
        for card in self._cards:
            card._sync_inner_height()
        if hasattr(self, "log"):
            self.log._resize_log()

    def _set_busy(self, busy: bool):
        for widget in self._path_widgets:
            if hasattr(widget, "set_enabled"):
                widget.set_enabled(not busy)
            else:
                try:
                    widget.configure(state="disabled" if busy else "normal")
                except tk.TclError:
                    pass
        for item in self._sidebar_items:
            item.set_enabled(not busy)

    def _show_progress_mode(self, mode: str):
        if mode == "idle":
            self._progress_metrics.pack_forget()
            self.progress.pack_forget()
            self._eta_label.pack_forget()
        else:
            self._progress_metrics.pack(fill="x", pady=(0, SPACING["sm"]), before=self._progress_detail)
            self.progress.pack(fill="x", pady=(0, SPACING["sm"]), before=self._progress_detail)
            self._eta_label.pack(fill="x")
            for idx, cell in enumerate(self._metric_cells):
                cell.grid_forget()
                narrow = hasattr(self, "_last_content_w") and self._last_content_w < BREAKPOINTS["narrow"]
                if narrow:
                    cell.grid(row=idx // 2, column=idx % 2, sticky="nsew", padx=(0 if idx % 2 == 0 else SPACING["xs"], 0), pady=(0, SPACING["sm"]))
                else:
                    cell.grid(row=0, column=idx, sticky="nsew", padx=(0 if idx == 0 else SPACING["sm"], 0))

    def _set_status_badge(self, status: str):
        self._status_chip.set_status(status)

    def _apply_progress_snapshot(self, snap):
        self._show_progress_mode("idle" if snap.status == "idle" else "active")
        self.progress.set_value(snap.percent if snap.status != "idle" else 0)
        self.progress_step_var.set(snap.step)
        if snap.status == "idle":
            self.progress_item_var.set(snap.item or "Chưa bắt đầu")
            self.progress_ratio_var.set("")
            self.progress_counts_var.set("")
            self.progress_time_var.set("")
            self.progress_eta_var.set("")
        else:
            self.progress_ratio_var.set(snap.ratio or "0%")
            self.progress_counts_var.set(snap.counts or "—")
            self.progress_item_var.set(snap.item)
            self.progress_time_var.set(snap.time or "Đã chạy: 0s")
            self.progress_eta_var.set(snap.eta if snap.eta else "—")
            if snap.ok is False:
                self.progress_item_var.set(snap.error or snap.item)
        self._set_status_badge(snap.status)

    def _append_log(self, text: str):
        self.log.append_line(text)

    def _finish_task(self, ok: bool, summary: str = "", error: str = ""):
        snap = self._progress.complete(ok, summary=summary, error=error)
        self._apply_progress_snapshot(snap)
        self._refresh_workflow_state()
        if ok:
            if summary:
                self._append_log(summary)
            if not self._sound_played:
                play_success_sound()
                self._sound_played = True
        else:
            msg = error or summary or "Có lỗi xảy ra."
            self._append_log(f"Lỗi: {msg}")
            messagebox.showerror("Lỗi", msg)

    def start_task(self, task_name: str, work, status: str = ""):
        if self._busy:
            messagebox.showinfo("Đang chạy", "Một tác vụ khác đang chạy. Hãy đợi xong.")
            return False
        self._busy = True
        self._sound_played = False
        self._set_busy(True)
        self.log.expand()
        self.progress.set_value(0)
        snap = self._progress.begin(task_name, status)
        self._apply_progress_snapshot(snap)
        threading.Thread(target=work, daemon=True).start()
        return True

    def choose_input(self):
        path = filedialog.askdirectory(title="Chọn thư mục game")
        if not path:
            path = filedialog.askopenfilename(title="Hoặc chọn file asset/bundle")
        if path:
            self.input_path.set(path)

    def choose_output(self):
        path = filedialog.askdirectory(title="Chọn thư mục xuất")
        if path:
            self.output_path.set(path)

    def start_background(self, task_name: str, work):
        return self.start_task(task_name, work)

    def start_extract_background(self, work, status: str = "Dang bat dau..."):
        return self.start_task("Xu ly", work, status)

    def _start_shared_task(self, task_name: str, runner, *, status: str = "", **kwargs):
        """Bridge the shared task callback contract onto Tk's message queue."""

        def work():
            try:
                runner(
                    progress=lambda info: self.messages.put(("PROGRESS", info)),
                    log=lambda text: self.messages.put(str(text)),
                    complete=lambda payload: self.messages.put(("COMPLETE", payload)),
                    **kwargs,
                )
            except Exception as exc:
                self.messages.put(("COMPLETE", {"ok": False, "error": str(exc)}))
            finally:
                self.messages.put("__STOP__")

        return self.start_task(task_name, work, status)

    def run_extract(self, mode: str):
        src = self.input_path.get().strip()
        if not src:
            messagebox.showwarning("Thiếu dữ liệu", "Hãy chọn file hoặc thư mục game trước.")
            return
        out = self.output_path.get().strip()
        level = self.extract_level.get().strip() or "balanced"

        self._start_shared_task(
            "Lấy text",
            run_extract_task,
            status="Đang bắt đầu lấy text…",
            src=src,
            out=out,
            mode=mode,
            level=level,
            separate_review=self.separate_review.get(),
        )

    def run_dump(self):
        src = self.input_path.get().strip()
        if not src:
            messagebox.showwarning("Thiếu dữ liệu", "Hãy chọn file hoặc thư mục game trước.")
            return
        out = self.output_path.get().strip()
        level = self.extract_level.get().strip() or "balanced"

        self._start_shared_task("Dump Unity", run_dump_task, src=src, out=out, level=level)

    def run_auto_raw_candidates(self):
        package_dir = resolve_translation_package_dir(self.output_path.get().strip())
        if not (package_dir / "translation.csv").exists() or not (package_dir / "raw_candidates.csv").exists():
            selected = filedialog.askdirectory(title="Chon thu muc co translation.csv va raw_candidates.csv")
            if not selected:
                return
            package_dir = resolve_translation_package_dir(selected)
        if not (package_dir / "translation.csv").exists() or not (package_dir / "raw_candidates.csv").exists():
            messagebox.showerror("Thiếu file", "Không tìm thấy translation.csv hoặc raw_candidates.csv.")
            return
        ok = messagebox.askyesno(
            "Auto loc raw candidates",
            "Tu dong dua dong kha chac sang translation.csv, rac sang raw_candidates_rejected.csv, dong lung chung giu lai?"
        )
        if not ok:
            return

        self._start_shared_task("Auto loc raw", run_auto_raw_task, package_dir=package_dir)

    def run_asset_index(self):
        src = self.input_path.get().strip()
        if not src:
            messagebox.showwarning("Thiếu dữ liệu", "Hãy chọn file hoặc thư mục game trước.")
            return
        out = self.output_path.get().strip()
        level = self.extract_level.get().strip() or "balanced"

        self._start_shared_task("Asset index", run_asset_index_task, src=src, out=out)


    def run_raw_candidate_reviewer(self):
        package_dir = resolve_translation_package_dir(self.output_path.get().strip())
        if not (package_dir / "translation.csv").exists() or not (package_dir / "raw_candidates.csv").exists():
            selected = filedialog.askdirectory(title="Chon thu muc co translation.csv va raw_candidates.csv")
            if not selected:
                return
            package_dir = resolve_translation_package_dir(selected)
        if not (package_dir / "translation.csv").exists() or not (package_dir / "raw_candidates.csv").exists():
            messagebox.showerror("Thiếu file", "Không tìm thấy translation.csv hoặc raw_candidates.csv.")
            return
        RawCandidateReviewer(self, package_dir)

    def run_ct2_translate(self):
        package_dir = resolve_translation_package_dir(self.output_path.get().strip())
        csv_path = package_dir / "translation.csv"
        if not csv_path.exists():
            selected = filedialog.askdirectory(title="Chon thu muc co translation.csv")
            if not selected:
                return
            package_dir = resolve_translation_package_dir(selected)
            csv_path = package_dir / "translation.csv"
        if not csv_path.exists():
            messagebox.showerror("Thiếu file", "Không tìm thấy translation.csv. Hãy chạy bước 1 trước.")
            return
        overwrite = self.translation_overwrite.get()
        if overwrite:
            ok = messagebox.askyesno(
                "Ghi de translation",
                "Ban bat che do ghi de. Cac dong translation da co co the bi thay. Tiep tuc?",
            )
            if not ok:
                return

        self._start_shared_task(
            "Dịch CT2 / OPUS-MT",
            run_translate_ct2_task,
            status="Đang dịch CT2 / OPUS-MT offline…",
            csv_path=csv_path,
            package_dir=package_dir,
            overwrite=overwrite,
        )

    def run_import_patch(self):
        src = self.input_path.get().strip()
        if not src:
            messagebox.showwarning("Thiếu dữ liệu", "Hãy chọn file hoặc thư mục game gốc trước.")
            return
        package_dir = Path(self.output_path.get().strip())
        csv_path = package_dir / "translation.csv"
        manifest_path = package_dir / "manifest.json"
        if not csv_path.exists() or not manifest_path.exists():
            selected = filedialog.askdirectory(title="Chon thu muc co translation.csv va manifest.json")
            if not selected:
                return
            package_dir = Path(selected)
            csv_path = package_dir / "translation.csv"
            manifest_path = package_dir / "manifest.json"
        if not csv_path.exists() or not manifest_path.exists():
            messagebox.showerror("Thiếu file", "Không tìm thấy translation.csv hoặc manifest.json.")
            return
        out = str(package_dir / "Patch_Viet_Hoa")

        self._start_shared_task(
            "Tạo patch",
            run_patch_task,
            status="Đang tạo patch Việt hóa…",
            csv_path=csv_path,
            manifest_path=manifest_path,
            src=src,
            out=out,
            patch_out_override=out,
            include_installer=False,
            write_manifest_file=False,
        )

    def _poll(self):
        try:
            while True:
                msg = self.messages.get_nowait()
                if msg == "__STOP__":
                    self._busy = False
                    self._set_busy(False)
                elif isinstance(msg, tuple) and msg[0] == "COMPLETE":
                    payload = msg[1]
                    self._finish_task(bool(payload.get("ok")), summary=str(payload.get("summary") or ""), error=str(payload.get("error") or ""))
                elif isinstance(msg, tuple) and msg[0] == "PROGRESS":
                    snap = self._progress.update(msg[1])
                    self._apply_progress_snapshot(snap)
                    info = msg[1]
                    if info.get("log"):
                        line = f"{snap.ratio} | {snap.step} | {snap.item}"
                        if snap.time:
                            line += f" | {snap.time}"
                        if snap.eta:
                            line += f" | ETA {snap.eta}"
                        if snap.extra:
                            line += f" | {snap.extra}"
                        self._append_log(line)
                else:
                    self._append_log(str(msg))
        except queue.Empty:
            pass
        self.after(120, self._poll)

from vntext.app_tasks import (
    run_asset_index_task,
    run_auto_raw_task,
    run_dump_task,
    run_extract_task,
    run_patch_task,
    run_translate_ct2_task,
)
from vntext.app_backend import (
    VERSION,
    promote_raw_candidates,
    read_csv_rows_file,
    resolve_translation_package_dir,
)
