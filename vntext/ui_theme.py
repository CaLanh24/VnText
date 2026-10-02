"""macOS Settings-inspired design system and custom Tk widgets."""
from __future__ import annotations

import os
import tkinter as tk
from tkinter import font as tkfont

# Design tokens
RADIUS = {"card": 12, "control": 8, "nav": 10, "chip": 8, "thumb": 5, "switch": 13}

SPACING = {"xs": 4, "sm": 8, "md": 12, "lg": 16, "xl": 20, "xxl": 24}

PALETTE = {
    "window": "#F2F2F7",
    "sidebar": "#ECECF1",
    "sidebar_hover": "#E0E0E8",
    "sidebar_selected": "#D6E8FF",
    "sidebar_selected_text": "#0066CC",
    "surface": "#FFFFFF",
    "surface_muted": "#FAFAFC",
    "border": "#DEDEDE",
    "border_strong": "#C7C7CC",
    "card_shadow": "#E6E6EA",
    "text": "#1D1D1F",
    "text_secondary": "#3A3A3C",
    "text_muted": "#636366",
    "text_tertiary": "#8E8E93",
    "accent": "#007AFF",
    "accent_hover": "#006FE8",
    "accent_pressed": "#005ED1",
    "accent_subtle": "#E8F2FF",
    "accent_text": "#FFFFFF",
    "success": "#248A3D",
    "success_bg": "#EAF6EC",
    "warning": "#9A6700",
    "warning_bg": "#FFF8E6",
    "error": "#C42B1C",
    "error_bg": "#FDECEA",
    "log_bg": "#F4F4F8",
    "log_border": "#D8D8DE",
    "progress_trough": "#E2E2E8",
    "progress_fill": "#007AFF",
    "scrollbar": "#BCBCC2",
    "scrollbar_hover": "#9E9EA4",
    "control_bg": "#FFFFFF",
    "control_disabled": "#EFEFF2",
    "focus_ring": "#007AFF",
}

FONTS = {
    "app_title": ("Segoe UI", 15, "bold"),
    "page_title": ("Segoe UI", 20),
    "hero_title": ("Segoe UI", 17, "bold"),
    "section": ("Segoe UI", 12),
    "headline": ("Segoe UI", 11, "bold"),
    "body": ("Segoe UI", 10),
    "body_medium": ("Segoe UI", 10, "bold"),
    "callout": ("Segoe UI", 10),
    "caption": ("Segoe UI", 10),
    "caption_bold": ("Segoe UI", 10, "bold"),
    "metric": ("Segoe UI", 24, "bold"),
    "metric_label": ("Segoe UI", 10),
    "nav": ("Segoe UI", 10),
    "nav_sub": ("Segoe UI", 9),
    "nav_section": ("Segoe UI", 9, "bold"),
    "mono": ("Cascadia Mono", 9),
}

BREAKPOINTS = {"narrow": 720, "medium": 980}

RAW_FILTER_LABELS = {
    "clean": "Sạch",
    "balanced": "Cân bằng",
    "exhaustive": "Quét sâu",
}
RAW_FILTER_VALUES = {v: k for k, v in RAW_FILTER_LABELS.items()}

REVIEW_MODE_LABELS = {
    True: "Bật",
    False: "Tắt",
}

WORKFLOW_STATES = ("pending", "current", "done")


def _mono_font() -> tuple:
    families = {name.lower() for name in tkfont.families()}
    if "cascadia mono" in families:
        return ("Cascadia Mono", 9)
    if "consolas" in families:
        return ("Consolas", 9)
    return ("Courier New", 9)


def _ui_font(key: str) -> tkfont.Font:
    family, size, *rest = FONTS[key]
    weight = "bold" if rest and rest[0] == "bold" else "normal"
    return tkfont.Font(family=family, size=size, weight=weight)


def _button_width(text: str, *, primary: bool = False, min_px: int = 76) -> int:
    measure = _ui_font("body_medium" if primary else "body").measure(text)
    return max(min_px, measure + 28)


class ToolTip:
    def __init__(self, widget: tk.Misc, text: str = ""):
        self._widget = widget
        self._text = text
        self._tip: tk.Toplevel | None = None
        widget.bind("<Enter>", self._show, add="+")
        widget.bind("<Leave>", self._hide, add="+")

    def set_text(self, text: str) -> None:
        self._text = text

    def _show(self, _event=None):
        text = self._text.strip()
        if not text or self._tip:
            return
        x = self._widget.winfo_rootx() + 12
        y = self._widget.winfo_rooty() + self._widget.winfo_height() + 6
        self._tip = tw = tk.Toplevel(self._widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        tk.Label(
            tw, text=text, bg=PALETTE["text"], fg=PALETTE["surface"],
            font=FONTS["caption"], padx=10, pady=6, justify="left",
        ).pack()

    def _hide(self, _event=None):
        if self._tip:
            self._tip.destroy()
            self._tip = None


def truncate_middle(text: str, max_len: int = 58) -> str:
    text = str(text or "").strip()
    if len(text) <= max_len:
        return text
    half = (max_len - 1) // 2
    return f"{text[:half]}…{text[-half:]}"


def round_rectangle(canvas: tk.Canvas, x1: float, y1: float, x2: float, y2: float, radius: float, **kwargs):
    r = max(0, min(radius, (x2 - x1) / 2, (y2 - y1) / 2))
    points = [
        x1 + r, y1, x2 - r, y1, x2 - r, y1, x2, y1, x2, y1 + r,
        x2, y2 - r, x2, y2, x2 - r, y2, x1 + r, y2, x1 + r, y2,
        x1, y2, x1, y2 - r, x1, y1 + r, x1, y1 + r, x1, y1,
    ]
    return canvas.create_polygon(points, smooth=True, splinesteps=36, **kwargs)


def draw_nav_icon(canvas: tk.Canvas, kind: str, x: int, y: int, color: str):
    if kind == "extract":
        canvas.create_rectangle(x, y - 7, x + 11, y + 7, outline=color, width=1.4)
        canvas.create_line(x + 2, y - 3, x + 9, y - 3, fill=color, width=1.2)
        canvas.create_line(x + 2, y + 1, x + 7, y + 1, fill=color, width=1.2)
    elif kind == "translate":
        canvas.create_oval(x, y - 6, x + 12, y + 6, outline=color, width=1.3)
        canvas.create_text(x + 6, y + 1, text="A", fill=color, font=("Segoe UI", 8, "bold"))
    elif kind == "patch":
        canvas.create_rectangle(x + 1, y - 6, x + 11, y + 6, outline=color, width=1.3)
        canvas.create_line(x + 3, y + 1, x + 5, y + 4, x + 10, y - 3, fill=color, width=1.5)
    elif kind == "tool":
        canvas.create_oval(x + 4, y - 7, x + 10, y - 1, outline=color, width=1.3)
        canvas.create_line(x + 3, y, x + 9, y + 7, fill=color, width=1.5)
    else:
        canvas.create_oval(x + 3, y - 4, x + 9, y + 4, outline=color, width=1.2)


def apply_theme(root: tk.Misc) -> None:
    root.option_add("*Font", FONTS["body"])
    root.option_add("*Background", PALETTE["window"])
    root.option_add("*Foreground", PALETTE["text"])


class MacCard(tk.Frame):
    def __init__(self, master, title: str = "", subtitle: str = "", compact: bool = False, slim: bool = False, **kwargs):
        super().__init__(master, bg=PALETTE["window"], **kwargs)
        self._radius = RADIUS["card"]
        self._compact = compact
        self._slim = slim
        self._canvas = tk.Canvas(self, bg=PALETTE["window"], highlightthickness=0, bd=0)
        self._canvas.pack(fill="both", expand=True)
        self._inner = tk.Frame(self._canvas, bg=PALETTE["surface"])
        self._win_id = self._canvas.create_window(2, 2, window=self._inner, anchor="nw")
        self._subtitle_label: tk.Label | None = None
        self._title_label: tk.Label | None = None
        self._canvas.bind("<Configure>", self._redraw)
        self._inner.bind("<Configure>", self._sync_inner_height)
        pad_x = SPACING["md"] if slim else (SPACING["lg"] if compact else SPACING["xl"])
        pad_y = SPACING["sm"] if slim else (SPACING["md"] if compact else SPACING["lg"])
        self._inner.configure(padx=pad_x, pady=pad_y)
        head_pad = SPACING["xs"] if slim else SPACING["md"]
        if title or subtitle:
            head = tk.Frame(self._inner, bg=PALETTE["surface"])
            head.pack(fill="x", pady=(0, head_pad))
            if title:
                self._title_label = tk.Label(
                    head, text=title, bg=PALETTE["surface"], fg=PALETTE["text"],
                    font=FONTS["section"], anchor="w",
                )
                self._title_label.pack(anchor="w")
            if subtitle:
                self._subtitle_label = tk.Label(
                    head, text=subtitle, bg=PALETTE["surface"], fg=PALETTE["text_muted"],
                    font=FONTS["caption"], wraplength=520, justify="left", anchor="w",
                )
                self._subtitle_label.pack(anchor="w", pady=(SPACING["xs"], 0))
        self.content = tk.Frame(self._inner, bg=PALETTE["surface"])
        self.content.pack(fill="both", expand=True)
        self.bind("<Configure>", self._on_self_configure)

    def set_wraplength(self, width: int) -> None:
        if self._subtitle_label:
            self._subtitle_label.configure(wraplength=max(180, width - 48))

    def _sync_inner_height(self, event=None):
        if event is not None and event.widget is not self._inner:
            return
        self._inner.update_idletasks()
        req = max(24, self._inner.winfo_reqheight())
        alloc = max(req + 6, self.winfo_height()) if self.winfo_height() > 40 else req + 6
        self._canvas.configure(height=alloc)
        self._canvas.itemconfigure(self._win_id, height=req)
        self._redraw()

    def _on_self_configure(self, event=None):
        if event is None or event.widget is not self:
            return
        self._sync_inner_height()

    def _redraw(self, _event=None):
        w = max(40, self._canvas.winfo_width())
        h = max(40, self._canvas.winfo_height())
        self._canvas.delete("card")
        round_rectangle(self._canvas, 2, 3, w - 1, h - 1, self._radius, fill=PALETTE["card_shadow"], outline="", tags="card")
        round_rectangle(
            self._canvas, 1, 1, w - 2, h - 3, self._radius,
            fill=PALETTE["surface"], outline=PALETTE["border"], width=1, tags="card",
        )
        self._canvas.itemconfigure(self._win_id, width=max(100, w - 4))


class MacStatusChip(tk.Canvas):
    MIN_W = 84
    H = 26

    def __init__(self, master, **kwargs):
        super().__init__(master, height=self.H, width=self.MIN_W, bg=PALETTE["surface"], highlightthickness=0, bd=0)
        self._text_id = self.create_text(self.MIN_W // 2, self.H // 2, text="Chờ", font=FONTS["caption_bold"], anchor="center")
        self.set_status("idle")

    def set_status(self, status: str):
        styles = {
            "idle": (PALETTE["surface_muted"], PALETTE["text_muted"], "Chờ"),
            "running": (PALETTE["accent_subtle"], PALETTE["sidebar_selected_text"], "Đang chạy"),
            "done": (PALETTE["success_bg"], PALETTE["success"], "Hoàn tất"),
            "error": (PALETTE["error_bg"], PALETTE["error"], "Lỗi"),
        }
        bg, fg, label = styles.get(status, styles["idle"])
        self.delete("chip")
        w = max(self.MIN_W, len(label) * 9 + 24)
        self.configure(width=w)
        round_rectangle(self, 0, 0, w, self.H, RADIUS["chip"], fill=bg, outline=PALETTE["border"], width=1, tags="chip")
        self.coords(self._text_id, w // 2, self.H // 2)
        self.itemconfigure(self._text_id, text=label, fill=fg)
        self.tag_raise(self._text_id)


class MacEntry(tk.Frame):
    HEIGHT = 34

    def __init__(self, master, textvariable: tk.StringVar | None = None, *, tooltip_text: str = "", **kwargs):
        super().__init__(master, bg=PALETTE["surface"], **kwargs)
        self._var = textvariable
        self._enabled = True
        self._focused = False
        self._tooltip = ToolTip(self, tooltip_text) if tooltip_text else None
        self._canvas = tk.Canvas(self, height=self.HEIGHT, bg=PALETTE["surface"], highlightthickness=0, bd=0)
        self._canvas.pack(fill="x", expand=True)
        self._entry = tk.Entry(
            self._canvas, textvariable=textvariable, relief="flat", bg=PALETTE["control_bg"],
            fg=PALETTE["text"], font=FONTS["body"], insertbackground=PALETTE["accent"],
            bd=0, highlightthickness=0,
        )
        self._win = self._canvas.create_window(12, self.HEIGHT // 2, window=self._entry, anchor="w")
        self._canvas.bind("<Configure>", self._redraw)
        self._entry.bind("<FocusIn>", self._on_focus_in)
        self._entry.bind("<FocusOut>", self._on_focus_out)
        if textvariable:
            textvariable.trace_add("write", lambda *_: self._refresh_display())
        self._refresh_display()

    def set_tooltip(self, text: str) -> None:
        if self._tooltip:
            self._tooltip.set_text(text)
        else:
            self._tooltip = ToolTip(self, text)

    def _refresh_display(self):
        if self._focused or not self._var:
            return
        full = self._var.get()
        display = truncate_middle(full, max_len=max(24, (self._canvas.winfo_width() - 28) // 7))
        if self._tooltip:
            self._tooltip.set_text(full)
        pos = self._entry.index("insert")
        self._entry.delete(0, "end")
        self._entry.insert(0, display)
        try:
            self._entry.icursor(min(pos, len(display)))
        except tk.TclError:
            pass

    def _on_focus_in(self, _event=None):
        self._focused = True
        if self._var:
            full = self._var.get()
            self._entry.delete(0, "end")
            self._entry.insert(0, full)
        self._redraw()

    def _on_focus_out(self, _event=None):
        self._focused = False
        self._refresh_display()
        self._redraw()

    def _redraw(self, _event=None):
        w = max(80, self._canvas.winfo_width())
        outline = PALETTE["focus_ring"] if self._focused and self._enabled else PALETTE["border_strong"]
        fill = PALETTE["control_bg"] if self._enabled else PALETTE["control_disabled"]
        self._canvas.delete("bg")
        round_rectangle(self._canvas, 1, 1, w - 1, self.HEIGHT - 1, RADIUS["control"], fill=fill, outline=outline, width=1.5 if self._focused else 1, tags="bg")
        self._canvas.itemconfigure(self._win, width=max(20, w - 24))

    def set_enabled(self, enabled: bool) -> None:
        self._enabled = enabled
        self._entry.configure(state="normal" if enabled else "disabled")
        self._redraw()


class MacPathField(tk.Frame):
    def __init__(self, master, textvariable: tk.StringVar, browse_cmd, *, open_folder: bool = True, **kwargs):
        super().__init__(master, bg=PALETTE["surface"], **kwargs)
        self.columnconfigure(0, weight=1)
        self._var = textvariable
        self._entry = MacEntry(self, textvariable=textvariable)
        self._entry.grid(row=0, column=0, sticky="ew")
        self._open_btn = None
        self._copy_btn = None
        self._sync_tooltip()
        textvariable.trace_add("write", lambda *_: (self._sync_tooltip(), self._sync_actions()))
        tools = tk.Frame(self, bg=PALETTE["surface"])
        tools.grid(row=1, column=0, sticky="e", pady=(SPACING["xs"], 0))
        if open_folder:
            self._open_btn = MacButton(tools, text="Mở thư mục", command=self._open_path, width=0)
            self._open_btn.pack(side="left", padx=(0, SPACING["xs"]))
        self._copy_btn = MacButton(tools, text="Sao chép", command=self._copy, width=0)
        self._copy_btn.pack(side="left", padx=(0, SPACING["xs"]))
        MacButton(tools, text="Chọn…", command=browse_cmd, primary=True, width=0).pack(side="left")
        self._sync_actions()

    def _sync_actions(self):
        has_path = bool(self._var.get().strip())
        if self._open_btn:
            self._open_btn.set_enabled(has_path)
        if self._copy_btn:
            self._copy_btn.set_enabled(has_path)

    def _sync_tooltip(self):
        self._entry.set_tooltip(self._var.get().strip())

    def _copy(self):
        value = self._var.get().strip()
        if value:
            self.clipboard_clear()
            self.clipboard_append(value)

    def _open_path(self):
        value = self._var.get().strip()
        if not value:
            return
        path = value
        if not os.path.isdir(path):
            path = os.path.dirname(path)
        if path and os.path.isdir(path):
            os.startfile(path)  # type: ignore[attr-defined]

    def set_enabled(self, enabled: bool):
        self._entry.set_enabled(enabled)
        if enabled:
            self._sync_actions()
        else:
            if self._open_btn:
                self._open_btn.set_enabled(False)
            if self._copy_btn:
                self._copy_btn.set_enabled(False)


class MacButton(tk.Frame):
    HEIGHT = 34

    def __init__(self, master, text: str, command=None, *, primary: bool = False, width: int | None = None, **kwargs):
        super().__init__(master, bg=kwargs.get("bg", PALETTE["surface"]), **{k: v for k, v in kwargs.items() if k != "bg"})
        self._text, self._command, self._primary = text, command, primary
        self._enabled, self._hover, self._pressed = True, False, False
        canvas_w = _button_width(text, primary=primary) if not width else max(_button_width(text, primary=primary), width * 8)
        self._canvas = tk.Canvas(
            self, height=self.HEIGHT, width=canvas_w,
            bg=self.cget("bg"), highlightthickness=0, bd=0, cursor="hand2",
        )
        self._canvas.pack(fill="x" if width is None else None)
        self._label = self._canvas.create_text(
            canvas_w // 2, self.HEIGHT // 2, text=text,
            font=_ui_font("body_medium" if primary else "body"), anchor="center",
        )
        for seq, handler in (
            ("<Configure>", self._redraw),
            ("<Enter>", lambda _e: self._set_hover(True)),
            ("<Leave>", lambda _e: self._set_hover(False)),
            ("<Button-1>", lambda _e: self._set_pressed(True)),
            ("<ButtonRelease-1>", self._on_release),
        ):
            self._canvas.bind(seq, handler)
        self._redraw()

    def _set_hover(self, hover: bool):
        self._hover = hover
        if not hover:
            self._pressed = False
        self._redraw()

    def _set_pressed(self, pressed: bool):
        self._pressed = pressed
        self._redraw()

    def _on_release(self, _event):
        was = self._pressed
        self._pressed = False
        self._redraw()
        if was and self._enabled and self._hover and self._command:
            self._command()

    def _colors(self):
        if not self._enabled:
            return PALETTE["control_disabled"], PALETTE["text_tertiary"], PALETTE["border"]
        if self._primary:
            if self._pressed:
                return PALETTE["accent_pressed"], PALETTE["accent_text"], PALETTE["accent_pressed"]
            if self._hover:
                return PALETTE["accent_hover"], PALETTE["accent_text"], PALETTE["accent_hover"]
            return PALETTE["accent"], PALETTE["accent_text"], PALETTE["accent"]
        if self._hover:
            return PALETTE["surface_muted"], PALETTE["text"], PALETTE["border_strong"]
        return PALETTE["surface"], PALETTE["text_secondary"], PALETTE["border_strong"]

    def _redraw(self, _event=None):
        w = max(_button_width(self._text, primary=self._primary), self._canvas.winfo_width(), 76)
        fill, fg, outline = self._colors()
        self._canvas.delete("bg")
        round_rectangle(self._canvas, 1, 1, w - 1, self.HEIGHT - 1, RADIUS["control"], fill=fill, outline=outline, width=1, tags="bg")
        self._canvas.coords(self._label, w // 2, self.HEIGHT // 2)
        self._canvas.itemconfigure(self._label, fill=fg, text=self._text)
        self._canvas.tag_raise(self._label)

    def set_text(self, text: str) -> None:
        self._text = text
        self._redraw()

    def set_enabled(self, enabled: bool) -> None:
        self._enabled = enabled
        self._canvas.configure(cursor="hand2" if enabled else "")
        self._redraw()


class MacSwitch(tk.Canvas):
    W, H = 46, 28

    def __init__(self, master, variable: tk.BooleanVar, command=None, **kwargs):
        super().__init__(master, width=self.W, height=self.H, bg=PALETTE["surface"], highlightthickness=0, bd=0, cursor="hand2")
        self._var, self._command, self._enabled = variable, command, True
        self._var.trace_add("write", lambda *_: self._draw())
        self.bind("<Button-1>", self._toggle)
        self._draw()

    def _toggle(self, _event=None):
        if not self._enabled:
            return
        self._var.set(not self._var.get())
        if self._command:
            self._command()

    def _draw(self):
        self.delete("all")
        on = bool(self._var.get())
        track = PALETTE["accent"] if on and self._enabled else PALETTE["border_strong"]
        if not self._enabled:
            track = PALETTE["control_disabled"]
        round_rectangle(self, 1, 4, self.W - 1, self.H - 4, RADIUS["switch"], fill=track, outline="")
        knob_x = self.W - 16 if on else 14
        self.create_oval(knob_x - 10, 5, knob_x + 10, self.H - 5, fill=PALETTE["surface"], outline=PALETTE["border"])

    def set_enabled(self, enabled: bool):
        self._enabled = enabled
        self.configure(cursor="hand2" if enabled else "")
        self._draw()


class MacSettingRow(tk.Frame):
    """macOS Settings row: label + optional helper left, control right."""

    def __init__(self, master, title: str, helper: str = "", *, compact_control: bool = False, tight: bool = False, **kwargs):
        super().__init__(master, bg=PALETTE["surface"], **kwargs)
        self.columnconfigure(0, weight=1)
        self.columnconfigure(1, weight=0)
        left = tk.Frame(self, bg=PALETTE["surface"])
        left.grid(row=0, column=0, sticky="w")
        tk.Label(left, text=title, bg=PALETTE["surface"], fg=PALETTE["text"], font=FONTS["body"], anchor="w").pack(anchor="w")
        if helper:
            wrap = 360 if tight else 480
            tk.Label(
                left, text=helper, bg=PALETTE["surface"], fg=PALETTE["text_muted"],
                font=FONTS["caption"], anchor="w", wraplength=wrap, justify="left",
            ).pack(anchor="w", pady=(1 if tight else 2, 0))
        self.control_host = tk.Frame(self, bg=PALETTE["surface"])
        pad = SPACING["xs"] if compact_control else SPACING["sm"]
        self.control_host.grid(row=0, column=1, sticky="ne", padx=(pad, 0))


class MacPopupButton(tk.Frame):
    HEIGHT = 34

    def __init__(self, master, textvariable: tk.StringVar, options: dict[str, str], width: int = 140, **kwargs):
        super().__init__(master, bg=PALETTE["surface"], **kwargs)
        self._var = textvariable
        self._choices = options
        self._enabled, self._hover = True, False
        self._canvas = tk.Canvas(self, height=self.HEIGHT, width=width, bg=PALETTE["surface"], highlightthickness=0, bd=0, cursor="hand2")
        self._canvas.pack(fill="x")
        self._menu = tk.Menu(self, tearoff=0, bg=PALETTE["surface"], fg=PALETTE["text"], activebackground=PALETTE["accent_subtle"], activeforeground=PALETTE["text"], borderwidth=1, relief="solid")
        for label, value in self._choices.items():
            self._menu.add_command(label=label, command=lambda v=value: self._choose(v))
        self._var.trace_add("write", lambda *_: self._redraw())
        self._canvas.bind("<Configure>", self._redraw)
        self._canvas.bind("<Button-1>", self._open)
        self._canvas.bind("<Enter>", lambda _e: self._set_hover(True))
        self._canvas.bind("<Leave>", lambda _e: self._set_hover(False))

    def _label_for(self, value: str) -> str:
        for label, val in self._choices.items():
            if val == value:
                return label
        return value

    def _choose(self, value: str):
        self._var.set(value)

    def _set_hover(self, hover: bool):
        self._hover = hover
        self._redraw()

    def _open(self, event):
        if self._enabled:
            self._menu.tk_popup(event.x_root, event.y_root + 4)

    def _redraw(self, _event=None):
        w = max(120, self._canvas.winfo_width())
        fill = PALETTE["control_bg"] if self._enabled else PALETTE["control_disabled"]
        outline = PALETTE["focus_ring"] if self._hover else PALETTE["border_strong"]
        self._canvas.delete("all")
        round_rectangle(self._canvas, 1, 1, w - 1, self.HEIGHT - 1, RADIUS["control"], fill=fill, outline=outline, width=1)
        label = self._label_for(self._var.get())
        self._canvas.create_text(12, self.HEIGHT // 2, text=label, anchor="w", fill=PALETTE["text"], font=_ui_font("body"))
        self._canvas.create_line(
            w - 18, self.HEIGHT // 2 - 3, w - 10, self.HEIGHT // 2 + 3,
            w - 18, self.HEIGHT // 2 + 3, fill=PALETTE["text_secondary"], width=1.3, smooth=True,
        )

    def set_enabled(self, enabled: bool):
        self._enabled = enabled
        self._redraw()


class MacProgressbar(tk.Canvas):
    HEIGHT = 10

    def __init__(self, master, **kwargs):
        super().__init__(master, height=self.HEIGHT, bg=PALETTE["surface"], highlightthickness=0, bd=0, **kwargs)
        self._value = 0
        self.bind("<Configure>", self._draw)

    def set_value(self, percent: int) -> None:
        self._value = max(0, min(100, int(percent)))
        self._draw()

    def __getitem__(self, key):
        if key == "value":
            return self._value
        raise KeyError(key)

    def _draw(self, _event=None):
        w = max(40, self.winfo_width())
        h = self.HEIGHT
        self.delete("all")
        round_rectangle(self, 0, 0, w, h, h // 2, fill=PALETTE["progress_trough"], outline="")
        if self._value > 0:
            fill_w = max(h, int(w * (self._value / 100.0)))
            round_rectangle(self, 0, 0, fill_w, h, h // 2, fill=PALETTE["progress_fill"], outline="")


class MacScrollbar(tk.Canvas):
    WIDTH = 8

    def __init__(self, master, command=None, **kwargs):
        super().__init__(master, width=self.WIDTH, highlightthickness=0, bd=0, bg=PALETTE["window"], **kwargs)
        self._command = command
        self._top, self._bottom, self._drag_offset = 0.0, 1.0, 0.0
        self.bind("<Configure>", self._redraw)
        self.bind("<Button-1>", self._on_press)
        self.bind("<B1-Motion>", self._on_drag)

    def set(self, first, last):
        self._top, self._bottom = float(first), float(last)
        self._redraw()

    def _thumb_bounds(self):
        h = max(1, self.winfo_height())
        if self._bottom - self._top >= 0.999:
            return None
        y1, y2 = int(h * self._top) + 4, int(h * self._bottom) - 4
        if y2 - y1 < 28:
            y2 = y1 + 28
        return 1, min(y1, h - 30), self.WIDTH - 1, min(y2, h - 2)

    def _on_press(self, event):
        bounds = self._thumb_bounds()
        if not bounds:
            return
        _, y1, _, y2 = bounds
        if y1 <= event.y <= y2:
            self._drag_offset = (event.y - y1) / max(1, y2 - y1)
        elif self._command:
            self._command("scroll", -3 if event.y < y1 else 3, "pages")

    def _on_drag(self, event):
        if not self._command or self._bottom - self._top >= 0.999:
            return
        h, span = max(1, self.winfo_height()), self._bottom - self._top
        pos = max(0.0, min(1.0 - span, (event.y / h) - self._drag_offset * span))
        self._command("moveto", pos)

    def _redraw(self, _event=None):
        self.delete("all")
        bounds = self._thumb_bounds()
        if bounds:
            round_rectangle(self, *bounds, RADIUS["thumb"], fill=PALETTE["scrollbar"], outline="")


class SidebarNavItem(tk.Frame):
    HEIGHT = 46

    def __init__(self, master, text: str, command, *, subtitle: str = "", icon: str = "tool", on_select=None, workflow: bool = False):
        super().__init__(master, bg=PALETTE["sidebar"])
        self._text, self._subtitle, self._icon = text, subtitle, icon
        self._command, self._on_select = command, on_select
        self._workflow = workflow
        self._selected = False
        self._enabled = True
        self._hover = False
        self._workflow_state = "pending"
        self._canvas = tk.Canvas(self, height=self.HEIGHT, bg=PALETTE["sidebar"], highlightthickness=0, bd=0, cursor="hand2")
        self._canvas.pack(fill="x", padx=SPACING["sm"], pady=1)
        self._canvas.bind("<Configure>", self._redraw)
        self._canvas.bind("<Enter>", lambda _e: self._set_hover(True))
        self._canvas.bind("<Leave>", lambda _e: self._set_hover(False))
        self._canvas.bind("<Button-1>", self._on_click)

    def _set_hover(self, hover: bool):
        if self._enabled:
            self._hover = hover
            self._redraw()

    def _on_click(self, _event):
        if not self._enabled:
            return
        if self._on_select:
            self._on_select(self)
        if self._command:
            self._command()

    def _redraw(self, _event=None):
        w, h = max(40, self._canvas.winfo_width()), self.HEIGHT
        self._canvas.delete("all")
        if not self._enabled:
            bg, fg, sub_fg = PALETTE["sidebar"], PALETTE["text_tertiary"], PALETTE["text_tertiary"]
        elif self._selected:
            bg, fg, sub_fg = PALETTE["sidebar_selected"], PALETTE["sidebar_selected_text"], PALETTE["sidebar_selected_text"]
        elif self._hover:
            bg, fg, sub_fg = PALETTE["sidebar_hover"], PALETTE["text"], PALETTE["text_muted"]
        else:
            bg, fg, sub_fg = None, PALETTE["text"], PALETTE["text_muted"]
        if bg:
            round_rectangle(self._canvas, 0, 1, w, h - 1, RADIUS["nav"], fill=bg, outline="", tags="pill")
        icon_x = 22 if self._workflow else 14
        draw_nav_icon(self._canvas, self._icon, icon_x, h // 2, fg)
        text_x = 46 if self._workflow else 38
        ty = h // 2 - (7 if self._subtitle else 0)
        self._canvas.create_text(text_x, ty, text=self._text, anchor="w", fill=fg, font=_ui_font("nav"), tags="fg")
        if self._subtitle:
            self._canvas.create_text(text_x, ty + 15, text=self._subtitle, anchor="w", fill=sub_fg, font=_ui_font("nav_sub"), tags="fg")
        if self._workflow:
            self._draw_workflow_badge(w, h)

    def _draw_workflow_badge(self, w: int, h: int):
        cx, cy = w - 16, h // 2
        if self._workflow_state == "done":
            self._canvas.create_oval(cx - 6, cy - 6, cx + 6, cy + 6, fill=PALETTE["success"], outline="", tags="fg")
            self._canvas.create_text(cx, cy + 1, text="✓", fill=PALETTE["surface"], font=("Segoe UI", 8, "bold"), tags="fg")
        elif self._workflow_state == "current":
            self._canvas.create_oval(cx - 6, cy - 6, cx + 6, cy + 6, fill=PALETTE["accent"], outline=PALETTE["accent"], width=1, tags="fg")
        else:
            self._canvas.create_oval(cx - 5, cy - 5, cx + 5, cy + 5, outline=PALETTE["border_strong"], width=1.2, tags="fg")

    def set_workflow_state(self, state: str):
        if state in WORKFLOW_STATES:
            self._workflow_state = state
            self._redraw()

    def set_selected(self, selected: bool):
        self._selected = selected
        self._redraw()

    def set_enabled(self, enabled: bool):
        self._enabled = enabled
        self._canvas.configure(cursor="hand2" if enabled else "")
        self._redraw()


class MacCollapsibleSection(tk.Frame):
    def __init__(self, master, title: str, *, expanded: bool = False, **kwargs):
        super().__init__(master, bg=PALETTE["sidebar"], **kwargs)
        self._expanded = expanded
        self._body = tk.Frame(self, bg=PALETTE["sidebar"])
        header = tk.Frame(self, bg=PALETTE["sidebar"], cursor="hand2")
        header.pack(fill="x", padx=SPACING["lg"], pady=(SPACING["xs"], SPACING["xs"]))
        self._title = tk.Label(header, text=title, bg=PALETTE["sidebar"], fg=PALETTE["text_tertiary"], font=FONTS["nav_section"], anchor="w")
        self._title.pack(side="left")
        self._chevron = tk.Label(header, text="▼" if expanded else "▶", bg=PALETTE["sidebar"], fg=PALETTE["text_tertiary"], font=FONTS["nav_sub"])
        self._chevron.pack(side="right")
        header.bind("<Button-1>", lambda _e: self.toggle())
        self._title.bind("<Button-1>", lambda _e: self.toggle())
        self._chevron.bind("<Button-1>", lambda _e: self.toggle())
        if expanded:
            self._body.pack(fill="x")

    def add(self, widget: tk.Widget):
        widget.pack(in_=self._body, fill="x")

    def toggle(self):
        self._expanded = not self._expanded
        if self._expanded:
            self._body.pack(fill="x")
            self._chevron.configure(text="▼")
        else:
            self._body.pack_forget()
            self._chevron.configure(text="▶")


class MacCollapsibleLog(tk.Frame):
    def __init__(self, master, **kwargs):
        super().__init__(master, bg=PALETTE["surface"], **kwargs)
        self._expanded = True
        self._auto_scroll = tk.BooleanVar(value=True)
        header = tk.Frame(self, bg=PALETTE["surface"])
        header.pack(fill="x")
        tk.Label(header, text="Nhật ký", bg=PALETTE["surface"], fg=PALETTE["text"], font=FONTS["section"]).pack(side="left")
        self._toggle_btn = MacButton(header, text="Thu gọn", command=self.toggle, width=0)
        self._toggle_btn.pack(side="right", padx=(SPACING["xs"], 0))
        MacButton(header, text="Xóa", command=self.clear, width=0).pack(side="right", padx=(SPACING["xs"], 0))
        MacButton(header, text="Sao chép", command=self.copy_all, width=0).pack(side="right", padx=(SPACING["xs"], 0))
        self.body = tk.Frame(self, bg=PALETTE["log_bg"], highlightbackground=PALETTE["log_border"], highlightthickness=1)
        self.body.pack(fill="both", expand=True, pady=(SPACING["sm"], 0))
        self.text = tk.Text(
            self.body, height=6, wrap="word", font=_mono_font(), bg=PALETTE["log_bg"], fg=PALETTE["text"],
            relief="flat", padx=12, pady=10, borderwidth=0, highlightthickness=0,
        )
        self.text.pack(side="left", fill="both", expand=True)
        self._scroll = MacScrollbar(self.body, command=self.text.yview)
        self._scroll.pack(side="right", fill="y", padx=(0, 4), pady=4)
        self.text.configure(yscrollcommand=self._scroll.set)
        self.bind("<Configure>", self._resize_log)
        for tag, color in (
            ("info", PALETTE["text"]), ("success", PALETTE["success"]), ("warning", PALETTE["warning"]),
            ("error", PALETTE["error"]), ("muted", PALETTE["text_muted"]),
        ):
            self.text.tag_configure(tag, foreground=color)
        self.text.insert("end", "Chưa có log. Log sẽ hiện khi bạn chạy một tác vụ.\n", "muted")

    def _resize_log(self, event=None):
        if event is not None and event.widget is not self:
            return
        h = max(80, self.winfo_height() - 44)
        rows = max(4, h // 18)
        self.text.configure(height=rows)

    def _show_body(self, show: bool):
        self._expanded = show
        if show:
            self.body.pack(fill="both", expand=True, pady=(SPACING["sm"], 0))
            self._toggle_btn.set_text("Thu gọn")
        else:
            self.body.pack_forget()
            self._toggle_btn.set_text("Mở rộng")

    def toggle(self):
        self._show_body(not self._expanded)

    def expand(self):
        self._show_body(True)

    def copy_all(self):
        content = self.text.get("1.0", "end-1c").strip()
        if content:
            self.clipboard_clear()
            self.clipboard_append(content)

    def clear(self):
        self.text.delete("1.0", "end")
        self.text.insert("end", "Đã xóa log.\n", "muted")

    def append_line(self, text: str) -> None:
        if not self._expanded:
            self.expand()
        line = text.rstrip()
        lower = line.lower()
        tag = "info"
        if lower.startswith("lỗi:") or lower.startswith("loi:") or "thất bại" in lower or "that bai" in lower:
            tag = "error"
        elif lower.startswith("xong") or "hoàn tất" in lower or "hoan tat" in lower:
            tag = "success"
        elif "cảnh báo" in lower or "canh bao" in lower:
            tag = "warning"
        self.text.insert("end", line + "\n", tag)
        if self._auto_scroll.get():
            self.text.see("end")


MacLogText = MacCollapsibleLog
MacCheckbox = MacSwitch
MacCombobox = MacPopupButton
SidebarButton = SidebarNavItem
