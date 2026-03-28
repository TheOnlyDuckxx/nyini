from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, QRunnable, Signal

from src.application.services import WallManagerService


class IndexWorkerSignals(QObject):
    progress = Signal(int, int, str)
    finished = Signal(object)
    failed = Signal(str)


class IndexWorker(QRunnable):
    def __init__(self, library_root: Path | None = None, *, compute_hashes: bool = False) -> None:
        super().__init__()
        self.library_root = library_root
        self.compute_hashes = compute_hashes
        self.signals = IndexWorkerSignals()

    def run(self) -> None:
        service = WallManagerService.create(library_root=self.library_root)
        try:
            summary = service.scan_library(
                compute_hashes=self.compute_hashes,
                progress_callback=self.signals.progress.emit,
            )
            self.signals.finished.emit(summary)
        except Exception as exc:
            self.signals.failed.emit(str(exc))
        finally:
            service.close()
