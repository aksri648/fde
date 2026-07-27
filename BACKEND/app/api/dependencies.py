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

    Uses the real Claude-backed planner only when explicitly enabled and an
    Anthropic API key is configured; otherwise falls back to the deterministic
    FakePlanner so the planning flow works without external credentials.
    """
    if settings.planner_mode.lower() == "real" and settings.anthropic_api_key:
        from app.services.claude_planner_real import ClaudePlannerAdapter

        return ClaudePlannerAdapter()

    if settings.planner_mode.lower() == "real":
        logger.warning("planner_mode_real_but_no_api_key_using_fake_planner")
    return FakePlanner()


DBSession = Annotated[AsyncSession, Depends(get_db)]
Auth = Annotated[AuthContext, Depends(get_auth_context)]
PlannerDep = Annotated[Planner, Depends(get_planner)]
