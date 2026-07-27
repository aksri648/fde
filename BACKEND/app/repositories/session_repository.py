"""Repository for planning session CRUD operations."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import select

from app.db.models import PlanningSession

if TYPE_CHECKING:
    import uuid

    from sqlalchemy.ext.asyncio import AsyncSession


class SessionRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(
        self,
        tenant_id: str,
        owner_id: str,
        initial_state: str = "DISCOVERING",
    ) -> PlanningSession:
        session = PlanningSession(
            tenant_id=tenant_id,
            owner_id=owner_id,
            state=initial_state,
        )
        self.db.add(session)
        await self.db.flush()
        return session

    async def get_by_id(self, session_id: uuid.UUID) -> PlanningSession | None:
        result = await self.db.execute(
            select(PlanningSession).where(PlanningSession.id == session_id)
        )
        return result.scalar_one_or_none()

    async def get_by_id_for_tenant(
        self, session_id: uuid.UUID, tenant_id: str
    ) -> PlanningSession | None:
        result = await self.db.execute(
            select(PlanningSession).where(
                PlanningSession.id == session_id,
                PlanningSession.tenant_id == tenant_id,
            )
        )
        return result.scalar_one_or_none()

    async def update_state(
        self,
        session: PlanningSession,
        new_state: str,
        *,
        increment_version: bool = False,
        route: str | None = None,
    ) -> PlanningSession:
        session.state = new_state
        if increment_version:
            session.current_plan_version += 1
        if route is not None:
            session.current_route = route
        await self.db.flush()
        return session
