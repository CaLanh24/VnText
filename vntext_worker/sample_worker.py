"""Sample long-running task for milestone 1 (progress/log/cancel)."""
from __future__ import annotations

import time
from typing import Callable

from vntext_worker.protocol import emit_complete, emit_log, emit_progress


def run_sample_task(
    task_id: str,
    *,
    steps: int = 20,
    delay_ms: int = 80,
    is_cancelled: Callable[[], bool],
) -> None:
    steps = max(1, int(steps))
    delay_ms = max(10, int(delay_ms))
    emit_log(task_id, f"Worker mẫu: {steps} bước, delay {delay_ms}ms")
    for i in range(1, steps + 1):
        if is_cancelled():
            emit_log(task_id, "Đã hủy theo yêu cầu host.")
            emit_complete(task_id, ok=False, error="cancelled")
            return
        emit_progress(
            task_id,
            done=i - 1,
            total=steps,
            step="Đang chạy worker mẫu",
            item=f"Bước {i}/{steps}",
            eta=f"{max(0, steps - i) * delay_ms // 1000}s",
        )
        time.sleep(delay_ms / 1000.0)
        emit_log(task_id, f"Hoàn thành bước {i}/{steps}")
    emit_progress(task_id, done=steps, total=steps, step="Hoàn tất", item="")
    emit_complete(task_id, ok=True, summary=f"Worker mẫu xong ({steps} bước)")
