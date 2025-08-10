from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional
from uuid import UUID


class JobStatus(str, Enum):
    pending = "pending"
    completed = "completed"


@dataclass
class JobRecord:
    id: UUID
    status: JobStatus
    created_at: datetime
    user_query: str
    history: Optional[list[Any]]
    result: Optional[str] = None


class JobStore:
    """In-memory, asyncio-locked job store. Suitable for single-process deployments."""

    def __init__(self) -> None:
        self._jobs: Dict[UUID, JobRecord] = {}
        self._lock = asyncio.Lock()

    async def create_job(self, job_id: UUID, history: Optional[list[Any]], user_query: str) -> JobRecord:
        async with self._lock:
            record = JobRecord(
                id=job_id,
                status=JobStatus.pending,
                created_at=datetime.now(timezone.utc),
                history=history,
                user_query=user_query,
            )
            self._jobs[job_id] = record
            return record

    async def set_result(self, job_id: UUID, result: str) -> None:
        async with self._lock:
            record = self._jobs.get(job_id)
            if record is None:
                return
            record.status = JobStatus.completed
            record.result = result
            self._jobs[job_id] = record

    async def get_job(self, job_id: UUID) -> Optional[JobRecord]:
        async with self._lock:
            return self._jobs.get(job_id)

    async def delete_job(self, job_id: UUID) -> None:
        async with self._lock:
            self._jobs.pop(job_id, None)
