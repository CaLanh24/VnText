"""Qt background workers — heavy tasks off the UI thread."""
from __future__ import annotations

from typing import Callable

from PySide6.QtCore import QObject, QThread, Signal


class TaskWorker(QObject):
    """Runs a callable on a QThread; emits log/progress/complete signals."""

    log = Signal(str)
    progress = Signal(dict)
    complete = Signal(dict)
    finished = Signal()

    def __init__(self, runner: Callable[..., None], **kwargs):
        super().__init__()
        self._runner = runner
        self._kwargs = kwargs

    def run(self) -> None:
        try:
            self._runner(
                progress=self.progress.emit,
                log=self.log.emit,
                complete=self.complete.emit,
                **self._kwargs,
            )
        finally:
            self.finished.emit()


class TaskRunner:
    """Manages one QThread + TaskWorker at a time."""

    def __init__(self):
        self._thread: QThread | None = None
        self._worker: TaskWorker | None = None

    @property
    def busy(self) -> bool:
        return self._thread is not None and self._thread.isRunning()

    def start(self, runner: Callable[..., None], **kwargs) -> bool:
        if self.busy:
            return False
        thread = QThread()
        worker = TaskWorker(runner, **kwargs)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(self._clear)
        self._thread = thread
        self._worker = worker
        thread.start()
        return True

    def _clear(self) -> None:
        self._thread = None
        self._worker = None

    @property
    def worker(self) -> TaskWorker | None:
        return self._worker
