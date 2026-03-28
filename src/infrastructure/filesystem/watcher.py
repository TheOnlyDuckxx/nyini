from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, QTimer, Signal

from src.infrastructure.imaging.metadata import SUPPORTED_EXTENSIONS


class PollingLibraryWatcher(QObject):
    library_changed = Signal()

    def __init__(self, root_dir: Path, interval_ms: int = 5000) -> None:
        super().__init__()
        self.root_dir = root_dir
        self.timer = QTimer(self)
        self.timer.setInterval(interval_ms)
        self.timer.timeout.connect(self.check_for_changes)
        self._snapshot: dict[str, tuple[float, int]] = {}

    def start(self) -> None:
        self._snapshot = self._build_snapshot()
        self.timer.start()

    def stop(self) -> None:
        self.timer.stop()

    def set_interval(self, interval_ms: int) -> None:
        self.timer.setInterval(interval_ms)

    def set_root_dir(self, root_dir: Path) -> None:
        self.root_dir = root_dir
        self._snapshot = self._build_snapshot()

    def _build_snapshot(self) -> dict[str, tuple[float, int]]:
        if not self.root_dir.exists():
            return {}
        snapshot: dict[str, tuple[float, int]] = {}
        for path in self.root_dir.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in SUPPORTED_EXTENSIONS:
                continue
            stat = path.stat()
            snapshot[str(path)] = (stat.st_mtime, stat.st_size)
        return snapshot

    def check_for_changes(self) -> None:
        current = self._build_snapshot()
        if current != self._snapshot:
            self._snapshot = current
            self.library_changed.emit()
