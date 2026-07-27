"""Shared API dependencies."""

from __future__ import annotations

from typing import Annotated

import structlog
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.session import get_db_session
from app.security.auth import AuthContext, get_auth_context
from app.services.claude_planner import FakePlanner, Planner

logger = structlog.get_logger(__name__)


async def get_db(
    session: AsyncSession = Depends(get_db_session),
) -> AsyncSession:
    return session


def get_planner() -> Planner:
    """Select the planner implementation.

    Uses the real Anthropic-format planner when ``PLANNER_MODE=real`` (routed to
    whatever ``ANTHROPIC_BASE_URL`` points at — e.g. the LiteLLM proxy);
    otherwise falls back to the deterministic FakePlanner so the planning flow
    works with no LLM configured.
    """
    if settings.planner_mode.lower() == "real":
        from app.services.claude_planner_real import ClaudePlannerAdapter

        return ClaudePlannerAdapter()

    return FakePlanner()


DBSession = Annotated[AsyncSession, Depends(get_db)]
Auth = Annotated[AuthContext, Depends(get_auth_context)]
PlannerDep = Annotated[Planner, Depends(get_planner)]
