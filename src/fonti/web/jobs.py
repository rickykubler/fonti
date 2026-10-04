"""Background ingestion of uploaded files, one at a time."""

import shutil
import tempfile
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path

from fonti.errors import FontiError
from fonti.service import Fonti, IngestStatus


class JobState(StrEnum):
    QUEUED = "in coda"
    RUNNING = "in corso"
    DONE = "completato"
    FAILED = "errore"


@dataclass
class Job:
    id: str
    filename: str
    state: JobState = JobState.QUEUED
    message: str = ""
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())


class IngestJobs:
    def __init__(self, fonti: Fonti, lock: threading.Lock) -> None:
        self._fonti = fonti
        self._lock = lock
        self._jobs: dict[str, Job] = {}
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="ingest")
        self._uploads = Path(tempfile.mkdtemp(prefix="fonti-uploads-"))

    def submit(self, filename: str, content: bytes) -> Job:
        job = Job(uuid.uuid4().hex, filename)
        folder = self._uploads / job.id
        folder.mkdir()
        path = folder / Path(filename).name  # keep the extension, drop any directory part
        path.write_bytes(content)
        self._jobs[job.id] = job
        self._executor.submit(self._run, job, path)
        return job

    def recent(self, limit: int = 10) -> list[Job]:
        return sorted(self._jobs.values(), key=lambda job: job.created_at, reverse=True)[:limit]

    def busy(self) -> bool:
        return any(job.state in (JobState.QUEUED, JobState.RUNNING) for job in self._jobs.values())

    def shutdown(self) -> None:
        self._executor.shutdown(wait=False, cancel_futures=True)
        shutil.rmtree(self._uploads, ignore_errors=True)

    def _run(self, job: Job, path: Path) -> None:
        job.state = JobState.RUNNING
        try:
            with self._lock:
                [result] = self._fonti.ingest([path])
            if result.status is IngestStatus.FAILED:
                job.state, job.message = JobState.FAILED, result.message
            else:
                job.state = JobState.DONE
                job.message = (
                    "già indicizzato"
                    if result.status is IngestStatus.SKIPPED
                    else f"{result.chunks} chunk"
                    + (f", {result.message}" if result.message else "")
                )
        except FontiError as exc:
            job.state, job.message = JobState.FAILED, str(exc)
        finally:
            shutil.rmtree(path.parent, ignore_errors=True)
