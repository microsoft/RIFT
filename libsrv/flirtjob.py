from enum import Enum
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from datetime import datetime
import threading
import uuid


class JobStatus(Enum):
    """Status states for a FLIRT generation job."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class FlirtJob:
    """Represents a FLIRT signature generation job."""
    job_id: str
    request_data: Dict[str, Any]
    status: JobStatus = JobStatus.PENDING
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    result_files: List[str] = field(default_factory=list)
    progress: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Convert job to JSON-serializable dict."""
        return {
            "job_id": self.job_id,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "error_message": self.error_message,
            "result_files": self.result_files,
            "progress": self.progress,
        }


class JobRegistry:
    """Thread-safe registry for managing FLIRT jobs."""

    def __init__(self, max_jobs: int = 100):
        self._jobs: Dict[str, FlirtJob] = {}
        self._lock = threading.RLock()
        self._max_jobs = max_jobs

    def create_job(self, request_data: Dict[str, Any]) -> FlirtJob:
        """Create and register a new job."""
        with self._lock:
            if len(self._jobs) >= self._max_jobs:
                self._prune_old_jobs()

            job_id = str(uuid.uuid4())
            job = FlirtJob(job_id=job_id, request_data=request_data)
            self._jobs[job_id] = job
            return job

    def get_job(self, job_id: str) -> Optional[FlirtJob]:
        """Get job by ID. Returns None if not found."""
        with self._lock:
            return self._jobs.get(job_id)

    def update_job(self, job_id: str, **kwargs) -> bool:
        """Update job fields. Returns True if job exists."""
        with self._lock:
            job = self._jobs.get(job_id)
            if job:
                for key, value in kwargs.items():
                    if hasattr(job, key):
                        setattr(job, key, value)
                return True
            return False

    def list_jobs(self, status: Optional[JobStatus] = None) -> List[Dict]:
        """List all jobs, optionally filtered by status."""
        with self._lock:
            jobs = list(self._jobs.values())
            if status:
                jobs = [j for j in jobs if j.status == status]
            return [j.to_dict() for j in jobs]

    def _prune_old_jobs(self):
        """Remove oldest completed/failed jobs to make room."""
        completed = [
            (jid, j) for jid, j in self._jobs.items()
            if j.status in (JobStatus.COMPLETED, JobStatus.FAILED)
        ]
        completed.sort(key=lambda x: x[1].completed_at or x[1].created_at)

        to_remove = len(completed) // 4 or 1
        for jid, _ in completed[:to_remove]:
            del self._jobs[jid]