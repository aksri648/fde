import asyncio
from typing import Any

import structlog

from app.domain.enums import EventName
from app.domain.schemas import Event, Snapshot
from app.repositories.job_repository import EventRepository, JobRepository
from app.security.redaction import redact_dict

logger = structlog.get_logger()

MAX_EVENT_PAYLOAD = 10000


class EventService:
    def __init__(self, event_repo: EventRepository, job_repo: JobRepository) -> None:
        self._event_repo = event_repo
        self._job_repo = job_repo
        self._connections: dict[str, list[asyncio.Queue[dict[str, Any]]]] = {}

    async def emit(self, job_id: str, name: EventName, data: dict[str, Any]) -> Event:
        sequence = await self._event_repo.get_max_sequence(job_id) + 1
        sanitized_data = redact_dict(data)

        for key, value in sanitized_data.items():
            if isinstance(value, str) and len(value) > MAX_EVENT_PAYLOAD:
                sanitized_data[key] = value[:MAX_EVENT_PAYLOAD] + "...[truncated]"

        await self._event_repo.create(job_id, name, sanitized_data, sequence)

        event = Event(
            name=name,
            data=sanitized_data,
            sequence=sequence,
        )

        await self._broadcast(job_id, event.model_dump())
        return event

    async def get_snapshot(self, job_id: str) -> Snapshot:
        job = await self._job_repo.get(job_id)
        if job is None:
            raise ValueError(f"Job not found: {job_id}")

        event_rows = await self._event_repo.list_for_job(job_id)
        events = [
            Event(
                name=EventName(row.name),
                data=row.get_data(),
                sequence=row.sequence,
            )
            for row in event_rows
        ]

        return Snapshot(
            job_id=job_id,
            state=job.state,
            events=events,
        )

    def subscribe(self, job_id: str) -> asyncio.Queue[dict[str, Any]]:
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        if job_id not in self._connections:
            self._connections[job_id] = []
        self._connections[job_id].append(queue)
        return queue

    def unsubscribe(self, job_id: str, queue: asyncio.Queue[dict[str, Any]]) -> None:
        if job_id in self._connections:
            self._connections[job_id] = [
                q for q in self._connections[job_id] if q is not queue
            ]
            if not self._connections[job_id]:
                del self._connections[job_id]

    async def _broadcast(self, job_id: str, event_data: dict[str, Any]) -> None:
        if job_id not in self._connections:
            return

        dead_queues: list[asyncio.Queue[dict[str, Any]]] = []
        for queue in self._connections[job_id]:
            try:
                queue.put_nowait(event_data)
            except asyncio.QueueFull:
                dead_queues.append(queue)

        for queue in dead_queues:
            self.unsubscribe(job_id, queue)
