from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, QRunnable, Signal

from src.infrastructure.imaging.thumbnails import ThumbnailManager


class ThumbnailWorkerSignals(QObject):
    finished = Signal(object)
    failed = Signal(str)


class ThumbnailWorker(QRunnable):
    def __init__(self, thumbnail_manager: ThumbnailManager, paths: list[Path]) -> None:
        super().__init__()
        self.thumbnail_manager = thumbnail_manager
        self.paths = paths
        self.signals = ThumbnailWorkerSignals()

    def run(self) -> None:
        generated: list[str] = []
        try:
            for path in self.paths:
                stat = path.stat()
                thumb = self.thumbnail_manager.ensure_thumbnail(path, mtime=stat.st_mtime, size_bytes=stat.st_size)
                generated.append(str(thumb))
            self.signals.finished.emit(generated)
        except Exception as exc:
            self.signals.failed.emit(str(exc))
