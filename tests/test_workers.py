from __future__ import annotations

from tests.conftest import create_image
from src.workers.preload_worker import PreloadWorker


def test_preload_worker_reads_files_without_decoding(tmp_path):
    image_path = create_image(tmp_path / "preload.jpg", color="cyan")
    worker = PreloadWorker([image_path])
    finished_payload: dict[str, int] = {}
    failures: list[str] = []
    worker.signals.finished.connect(lambda payload: finished_payload.update(payload))
    worker.signals.failed.connect(failures.append)

    worker.run()

    assert failures == []
    assert finished_payload[str(image_path)] > 0
