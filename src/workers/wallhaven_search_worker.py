from __future__ import annotations

from PySide6.QtCore import QObject, QRunnable, Signal

from src.domain.models import WallhavenSearchRequest
from src.infrastructure.wallhaven.client import WallhavenClient


class WallhavenSearchWorkerSignals(QObject):
    progress = Signal(int, int, str)
    preview_ready = Signal(object, str)
    finished = Signal(object)
    failed = Signal(str)


class WallhavenSearchWorker(QRunnable):
    def __init__(
        self,
        client: WallhavenClient,
        request: WallhavenSearchRequest,
        *,
        api_key: str = "",
    ) -> None:
        super().__init__()
        self.client = client
        self.request = request
        self.api_key = api_key
        self.signals = WallhavenSearchWorkerSignals()

    def run(self) -> None:
        try:
            page = self.client.search(self.request, api_key=self.api_key)
            total = len(page.results)
            for index, result in enumerate(page.results, start=1):
                try:
                    preview_path = self.client.cache_thumbnail(result)
                except Exception:
                    preview_path = ""
                self.signals.preview_ready.emit(result, str(preview_path))
                self.signals.progress.emit(index, total, result.wallhaven_id)
            self.signals.finished.emit(page)
        except Exception as exc:
            self.signals.failed.emit(str(exc))
