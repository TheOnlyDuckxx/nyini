from __future__ import annotations

from dataclasses import dataclass
import itertools

from PySide6.QtCore import QObject, QThreadPool, Signal


@dataclass(slots=True)
class JobInfo:
    job_id: str
    name: str
    status: str
    message: str = ""


class BackgroundJobQueue(QObject):
    job_updated = Signal(object)

    def __init__(self, thread_pool: QThreadPool, parent=None) -> None:
        super().__init__(parent)
        self.thread_pool = thread_pool
        self._counter = itertools.count(1)
        self._jobs: dict[str, JobInfo] = {}

    def submit(self, name: str, runnable, *, description: str = "") -> str:
        job_id = f"job-{next(self._counter)}"
        info = JobInfo(job_id=job_id, name=name, status="running", message=description or name)
        self._jobs[job_id] = info
        self.job_updated.emit(info)

        signals = getattr(runnable, "signals", None)
        if signals is not None:
            finished = getattr(signals, "finished", None)
            failed = getattr(signals, "failed", None)
            if finished is not None:
                finished.connect(lambda *_args, _job_id=job_id: self._finish(_job_id, "done"))
            if failed is not None:
                failed.connect(lambda message, _job_id=job_id: self._finish(_job_id, "failed", str(message)))

        self.thread_pool.start(runnable)
        return job_id

    def update_message(self, job_id: str, message: str) -> None:
        info = self._jobs.get(job_id)
        if info is None:
            return
        info.message = message
        self.job_updated.emit(info)

    def _finish(self, job_id: str, status: str, message: str = "") -> None:
        info = self._jobs.get(job_id)
        if info is None:
            return
        info.status = status
        if message:
            info.message = message
        self.job_updated.emit(info)
