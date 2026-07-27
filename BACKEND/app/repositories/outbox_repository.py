"""Repository for handoff outbox operations."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import select

from app.db.models import HandoffOutbox

if TYPE_CHECKING:
    import uuid

    from sqlalchemy.ext.asyncio import AsyncSession


class OutboxRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(
        self,
        session_id: uuid.UUID,
        plan_version: int,
        route: str,
        idempotency_key: uuid.UUID,
        package_json: dict[str, Any],
        max_attempts: int = 5,
    ) -> HandoffOutbox:
        outbox = HandoffOutbox(
            session_id=session_id,
            plan_version=plan_version,
            route=route,
            idempotency_key=idempotency_key,
            package_json=package_json,
            max_attempts=max_attempts,
        )
        self.db.add(outbox)
        await self.db.flush()
        return outbox

    async def get_pending_entries(self, limit: int = 10) -> list[HandoffOutbox]:
        now = datetime.now(UTC)
        result = await self.db.execute(
            select(HandoffOutbox)
            .where(
                HandoffOutbox.status == "PENDING",
                (HandoffOutbox.next_attempt_at.is_(None)) | (HandoffOutbox.next_attempt_at <= now),
            )
            .order_by(HandoffOutbox.created_at)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def lock_entry(self, entry: HandoffOutbox, worker_id: str) -> HandoffOutbox:
        entry.status = "PROCESSING"
        entry.locked_by = worker_id
        entry.locked_at = datetime.now(UTC)
        await self.db.flush()
        return entry

    async def mark_completed(self, entry: HandoffOutbox) -> HandoffOutbox:
        entry.status = "COMPLETED"
        await self.db.flush()
        return entry

    async def mark_failed(self, entry: HandoffOutbox, error: str) -> HandoffOutbox:
        entry.attempt_count += 1
        entry.last_error = error
        if entry.attempt_count >= entry.max_attempts:
            entry.status = "FAILED"
        else:
            entry.status = "PENDING"
            entry.locked_by = None
            entry.locked_at = None
        await self.db.flush()
        return entry

    async def get_by_idempotency_key(self, idempotency_key: uuid.UUID) -> HandoffOutbox | None:
        result = await self.db.execute(
            select(HandoffOutbox).where(HandoffOutbox.idempotency_key == idempotency_key)
        )
        return result.scalar_one_or_none()

    async def get_by_session_and_version(
        self, session_id: uuid.UUID, plan_version: int
    ) -> HandoffOutbox | None:
        result = await self.db.execute(
            select(HandoffOutbox).where(
                HandoffOutbox.session_id == session_id,
                HandoffOutbox.plan_version == plan_version,
            )
        )
        return result.scalar_one_or_none()
