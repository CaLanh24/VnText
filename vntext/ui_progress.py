"""Real-data progress formatting and completion signaling for VNText Studio UI."""
from __future__ import annotations

import sys
from dataclasses import dataclass, field

from vntext.extract import format_duration

PHASE_LABELS = {
    "extract": "Lấy text",
    "patch": "Tạo patch",
    "dump": "Dump / soi Unity",
    "asset_index": "Chỉ mục asset",
    "auto_raw": "Lọc raw tự động",
    "idle": "Sẵn sàng",
}

STATUS_LABELS = {
    "idle": "Chờ",
    "running": "Đang chạy",
    "done": "Hoàn tất",
    "error": "Lỗi",
}


def phase_label(phase: str | None) -> str:
    if not phase:
        return PHASE_LABELS["idle"]
    return PHASE_LABELS.get(phase, phase)


def compute_percent(done: int, total: int, *, allow_complete: bool = False) -> int:
    if total <= 0:
        return 100 if allow_complete else 0
    raw = int((done / total) * 100)
    if allow_complete:
        return min(100, max(0, raw))
    return min(99, max(0, raw))


def format_progress_lines(info: dict, *, allow_complete: bool = False) -> dict[str, str]:
    done = int(info.get("done") or 0)
    total = int(info.get("total") or 0)
    phase = info.get("phase") or "idle"
    elapsed = float(info.get("elapsed") or 0)
    eta = float(info.get("eta") or 0)
    item = str(info.get("file") or info.get("item") or "").strip()
    found = info.get("found")

    percent = compute_percent(done, total, allow_complete=allow_complete)
    step = phase_label(phase)

    if total > 0:
        counts = f"{done}/{total}"
        ratio = f"{percent}%"
    elif done > 0:
        counts = f"{done}/—"
        ratio = f"{percent}%"
    else:
        counts = "0/0" if phase == "idle" else "0/—"
        ratio = f"{percent}%" if allow_complete and percent >= 100 else (f"{percent}%" if percent else "0%")

    time_parts = []
    if elapsed > 0 or allow_complete or phase != "idle":
        time_parts.append(f"Đã chạy: {format_duration(elapsed)}")

    lines = {
        "step": step,
        "counts": counts,
        "ratio": ratio or "0%",
        "item": item,
        "time": time_parts[0] if time_parts else "Đã chạy: 0s",
        "eta": f"~{format_duration(eta)}" if total > 0 and done > 0 and eta > 0 and not allow_complete else "—",
    }
    if found is not None and phase == "extract":
        lines["extra"] = f"Mới được {found} dòng"
    return lines


@dataclass
class ProgressSnapshot:
    step: str = "Sẵn sàng"
    counts: str = ""
    ratio: str = ""
    item: str = ""
    time: str = ""
    eta: str = ""
    extra: str = ""
    percent: int = 0
    status: str = "idle"
    ok: bool | None = None
    error: str = ""


@dataclass
class ProgressController:
    task_name: str = ""
    running: bool = False
    last_info: dict = field(default_factory=dict)

    def begin(self, task_name: str, status: str = "") -> ProgressSnapshot:
        self.task_name = task_name
        self.running = True
        self.last_info = {}
        return ProgressSnapshot(
            step=task_name,
            counts="0/0",
            ratio="0%",
            item=status or "Đang bắt đầu…",
            time="Đã chạy: 0s",
            eta="—",
            percent=0,
            status="running",
        )

    def update(self, info: dict) -> ProgressSnapshot:
        self.last_info = dict(info)
        lines = format_progress_lines(info, allow_complete=False)
        return ProgressSnapshot(
            step=lines["step"],
            counts=lines["counts"],
            ratio=lines["ratio"],
            item=lines["item"],
            time=lines["time"],
            eta=lines["eta"],
            extra=lines.get("extra", ""),
            percent=compute_percent(int(info.get("done") or 0), int(info.get("total") or 0)),
            status="running",
        )

    def complete(self, ok: bool, summary: str = "", error: str = "") -> ProgressSnapshot:
        self.running = False
        if ok:
            info = dict(self.last_info)
            if info.get("total"):
                info["done"] = info["total"]
            lines = format_progress_lines(info, allow_complete=True)
            return ProgressSnapshot(
                step=self.task_name,
                counts=lines["counts"] or str(info.get("total") or ""),
                ratio="100%",
                item=summary or lines["item"],
                time=lines["time"],
                eta="",
                percent=100,
                status="done",
                ok=True,
            )
        lines = format_progress_lines(self.last_info, allow_complete=False)
        return ProgressSnapshot(
            step=self.task_name,
            counts=lines["counts"],
            ratio=lines["ratio"] or f"{compute_percent(int(self.last_info.get('done') or 0), int(self.last_info.get('total') or 0))}%",
            item=error or summary or "Có lỗi xảy ra",
            time=lines["time"],
            eta=lines["eta"],
            percent=compute_percent(
                int(self.last_info.get("done") or 0),
                int(self.last_info.get("total") or 0),
            ),
            status="error",
            ok=False,
            error=error or summary,
        )

    def idle(self) -> ProgressSnapshot:
        self.running = False
        self.task_name = ""
        self.last_info = {}
        return ProgressSnapshot(
            step="Sẵn sàng",
            counts="",
            ratio="",
            item="Chưa bắt đầu",
            time="",
            eta="",
            percent=0,
            status="idle",
        )


def play_success_sound() -> None:
    if sys.platform != "win32":
        return
    try:
        import winsound

        winsound.MessageBeep(winsound.MB_OK)
    except Exception:
        pass
