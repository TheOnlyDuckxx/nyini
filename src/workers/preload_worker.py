from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, QRunnable, Signal


class PreloadWorkerSignals(QObject):
    finished = Signal(object)
    failed = Signal(str)


class PreloadWorker(QRunnable):
    def __init__(self, paths: list[Path]) -> None:
        super().__init__()
        self.paths = paths
        self.signals = PreloadWorkerSignals()

    def run(self) -> None:
        loaded: dict[str, int] = {}
        try:
            for path in self.paths:
                with path.open("rb") as file_handle:
                    loaded[str(path)] = len(file_handle.read(131072))
            self.signals.finished.emit(loaded)
        except Exception as exc:
            self.signals.failed.emit(str(exc))
