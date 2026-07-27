"""Handoff API endpoints."""

from __future__ import annotations

import uuid  # noqa: TC003  # runtime import required for FastAPI param resolution
from typing import Any

from fastapi import APIRouter, HTTPException, status

# Runtime imports required for FastAPI dependency injection (see sessions.py).
from app.api.dependencies import Auth, DBSession  # noqa: TC001
from app.domain.schemas import ErrorResponse
from app.repositories.audit_repository import AuditRepository
from app.repositories.outbox_repository import OutboxRepository
from app.repositories.session_repository import SessionRepository
from app.security.authorization import ensure_session_ownership

router = APIRouter(prefix="/v1/sessions", tags=["handoffs"])


@router.get(
    "/{session_id}/handoff",
    responses={404: {"model": ErrorResponse}},
)
async def get_handoff_status(
    session_id: uuid.UUID,
    auth: Auth,
    db: DBSession,
) -> dict[str, Any]:
    repo = SessionRepository(db)
    session = ensure_session_ownership(
        await repo.get_by_id_for_tenant(session_id, auth.tenant_id), auth
    )

    outbox_repo = OutboxRepository(db)
    outbox_entry = await outbox_repo.get_by_session_and_version(
        session_id, session.current_plan_version
    )

    if outbox_entry is None:
        return {
            "status": "no_outbox_entry",
            "session_id": str(session.id),
        }

    from sqlalchemy import select

    from app.db.models import HandoffReceiptModel

    result = await db.execute(
        select(HandoffReceiptModel).where(
            HandoffReceiptModel.session_id == session_id,
            HandoffReceiptModel.outbox_id == outbox_entry.id,
        )
    )
    receipt = result.scalar_one_or_none()

    response: dict[str, Any] = {
        "outbox_status": outbox_entry.status,
        "attempt_count": outbox_entry.attempt_count,
        "last_error": outbox_entry.last_error,
        "session_id": str(session.id),
    }

    if receipt:
        response["receipt"] = {
            "route": receipt.route,
            "downstream_id": receipt.downstream_id,
            "downstream_status": receipt.downstream_status,
            "accepted_at": receipt.accepted_at.isoformat() if receipt.accepted_at else None,
            "attempt_count": receipt.attempt_count,
        }

    return response


@router.post(
    "/{session_id}/handoff/retry",
    status_code=status.HTTP_202_ACCEPTED,
    responses={400: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
)
async def retry_handoff(
    session_id: uuid.UUID,
    body: dict[str, Any],
    auth: Auth,
    db: DBSession,
) -> dict[str, Any]:
    repo = SessionRepository(db)
    session = ensure_session_ownership(
        await repo.get_by_id_for_tenant(session_id, auth.tenant_id), auth
    )

    plan_version = body.get("plan_version")
    if not plan_version:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="plan_version is required",
        )

    outbox_repo = OutboxRepository(db)
    outbox_entry = await outbox_repo.get_by_session_and_version(session_id, plan_version)

    if outbox_entry is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No outbox entry found for this plan version",
        )

    if outbox_entry.status != "FAILED":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot retry outbox entry in status {outbox_entry.status}",
        )

    outbox_entry.status = "PENDING"
    outbox_entry.attempt_count = 0
    outbox_entry.last_error = None
    outbox_entry.locked_by = None
    outbox_entry.locked_at = None
    await db.flush()

    audit = AuditRepository(db)
    await audit.create_event(
        actor=auth.owner_id,
        action="handoff_retry_queued",
        session_id=session.id,
        proposal_version=plan_version,
    )

    return {
        "status": "retry_queued",
        "session_id": str(session.id),
        "plan_version": plan_version,
    }
