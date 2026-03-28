from __future__ import annotations

from PySide6.QtCore import QObject, QRunnable, Signal

from src.domain.models import GowallTheme, Wallpaper
from src.infrastructure.gowall.client import GowallClient


class GowallPreviewWorkerSignals(QObject):
    progress = Signal(int, int, str)
    preview_ready = Signal(object)
    theme_failed = Signal(str, str)
    finished = Signal(object)
    failed = Signal(str)


class GowallPreviewWorker(QRunnable):
    def __init__(self, client: GowallClient, wallpaper: Wallpaper, themes: list[GowallTheme]) -> None:
        super().__init__()
        self.client = client
        self.wallpaper = wallpaper
        self.themes = themes
        self.signals = GowallPreviewWorkerSignals()

    def run(self) -> None:
        results: list[object] = []
        errors: list[tuple[str, str]] = []
        try:
            total = len(self.themes)
            for index, theme in enumerate(self.themes, start=1):
                try:
                    result = self.client.ensure_preview(self.wallpaper, theme)
                    results.append(result)
                    self.signals.preview_ready.emit(result)
                except Exception as exc:
                    errors.append((theme.id, str(exc)))
                    self.signals.theme_failed.emit(theme.id, str(exc))
                self.signals.progress.emit(index, total, theme.display_name)
            self.signals.finished.emit({"results": results, "errors": errors})
        except Exception as exc:
            self.signals.failed.emit(str(exc))
