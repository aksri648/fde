"""Repository for audit event operations."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from app.db.models import AuditEvent

if TYPE_CHECKING:
    import uuid

    from sqlalchemy.ext.asyncio import AsyncSession


class AuditRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create_event(
        self,
        actor: str,
        action: str,
        session_id: uuid.UUID,
        *,
        proposal_version: int | None = None,
        correlation_id: str | None = None,
        sanitized_metadata: dict[str, Any] | None = None,
    ) -> AuditEvent:
        event = AuditEvent(
            actor=actor,
            action=action,
            session_id=session_id,
            proposal_version=proposal_version,
            correlation_id=correlation_id,
            sanitized_metadata=sanitized_metadata,
        )
        self.db.add(event)
        await self.db.flush()
        return event
