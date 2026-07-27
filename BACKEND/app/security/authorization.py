"""Tenant authorization checks."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import HTTPException, status

if TYPE_CHECKING:
    from app.db.models import PlanningSession
    from app.security.auth import AuthContext


def ensure_session_ownership(
    session: PlanningSession | None,
    auth: AuthContext,
) -> PlanningSession:
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        )
    if session.tenant_id != auth.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: tenant mismatch",
        )
    return session
