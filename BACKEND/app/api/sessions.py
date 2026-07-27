"""Session management API endpoints."""

from __future__ import annotations

import uuid  # noqa: TC003  # runtime import required for FastAPI param resolution

import structlog
from fastapi import APIRouter, HTTPException, status

# NOTE: These must be runtime imports (not under TYPE_CHECKING). With
# `from __future__ import annotations`, FastAPI resolves these dependency
# annotations at runtime; moving them into a type-checking block breaks
# dependency injection (params get mis-read as query fields).
from app.api.dependencies import Auth, DBSession, PlannerDep  # noqa: TC001
from app.domain.enums import SessionState
from app.domain.schemas import (
    AnswerSubmit,
    ConversationTurnCreate,
    ErrorResponse,
    SessionCreate,
    SessionSnapshot,
)
from app.domain.transitions import InvalidTransitionError
from app.repositories.audit_repository import AuditRepository
from app.repositories.session_repository import SessionRepository
from app.security.authorization import ensure_session_ownership
from app.services.event_service import event_broadcaster

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/v1/sessions", tags=["sessions"])


async def _run_planning(
    db: DBSession,
    planner: PlannerDep,
    session_id: uuid.UUID,
    tenant_id: str,
) -> None:
    """Run one planning cycle, keeping planner failures non-fatal to the request.

    ``PlanningService.run_planning_cycle`` already records a FAILED state and
    emits an error event if the planner raises, so we swallow the exception here
    to preserve the surrounding transaction (session creation / answers) rather
    than rolling it back.
    """
    from app.services.planning_service import PlanningService

    service = PlanningService(db, planner)
    try:
        await service.run_planning_cycle(session_id, tenant_id)
    except Exception:
        logger.warning("planning_cycle_failed", session_id=str(session_id))


@router.get(
    "",
    response_model=list[SessionSnapshot],
    responses={401: {"model": ErrorResponse}},
)
async def list_sessions(
    auth: Auth,
    db: DBSession,
) -> list[SessionSnapshot]:
    """List all sessions for the authenticated user."""
    repo = SessionRepository(db)
    sessions = await repo.list_for_tenant(auth.tenant_id)
    return [
        SessionSnapshot(
            id=s.id,
            state=s.state,
            plan_version=s.current_plan_version,
            route=s.current_route,
            created_at=s.created_at,
            updated_at=s.updated_at,
        )
        for s in sessions
    ]


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=SessionSnapshot,
    responses={400: {"model": ErrorResponse}, 429: {"model": ErrorResponse}},
)
async def create_session(
    body: SessionCreate,
    auth: Auth,
    db: DBSession,
    planner: PlannerDep,
) -> SessionSnapshot:
    repo = SessionRepository(db)
    audit = AuditRepository(db)

    session = await repo.create(
        tenant_id=auth.tenant_id,
        owner_id=auth.owner_id,
    )

    await _add_turn(db, session.id, "user", body.initial_message, body.client_request_id)

    await audit.create_event(
        actor=auth.owner_id,
        action="session_created",
        session_id=session.id,
        correlation_id=str(body.client_request_id) if body.client_request_id else None,
    )

    await event_broadcaster.publish(
        str(session.id),
        "state_changed",
        {"state": session.state, "session_id": str(session.id)},
    )

    # Kick off the first planning cycle so the session immediately advances to
    # AWAITING_ANSWERS (follow-up questions) or AWAITING_APPROVAL (proposal).
    await _run_planning(db, planner, session.id, auth.tenant_id)

    return SessionSnapshot(
        id=session.id,
        state=session.state,
        plan_version=session.current_plan_version,
        route=session.current_route,
        created_at=session.created_at,
        updated_at=session.updated_at,
    )


@router.get(
    "/{session_id}",
    response_model=SessionSnapshot,
    responses={404: {"model": ErrorResponse}, 403: {"model": ErrorResponse}},
)
async def get_session(
    session_id: uuid.UUID,
    auth: Auth,
    db: DBSession,
) -> SessionSnapshot:
    repo = SessionRepository(db)
    session = ensure_session_ownership(
        await repo.get_by_id_for_tenant(session_id, auth.tenant_id), auth
    )

    return SessionSnapshot(
        id=session.id,
        state=session.state,
        plan_version=session.current_plan_version,
        route=session.current_route,
        created_at=session.created_at,
        updated_at=session.updated_at,
    )


@router.post(
    "/{session_id}/turns",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=SessionSnapshot,
    responses={400: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
)
async def add_turn(
    session_id: uuid.UUID,
    body: ConversationTurnCreate,
    auth: Auth,
    db: DBSession,
    planner: PlannerDep,
) -> SessionSnapshot:
    repo = SessionRepository(db)
    audit = AuditRepository(db)
    session = ensure_session_ownership(
        await repo.get_by_id_for_tenant(session_id, auth.tenant_id), auth
    )

    allowed_states = {
        SessionState.AWAITING_ANSWERS,
        SessionState.AWAITING_APPROVAL,
        SessionState.FAILED,
    }
    if SessionState(session.state) not in allowed_states:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot add turn in state {session.state}",
        )

    await _add_turn(db, session.id, "user", body.message, None)

    await audit.create_event(
        actor=auth.owner_id,
        action="turn_added",
        session_id=session.id,
    )

    # A new user turn re-opens discovery; re-run the planner to produce updated
    # questions or a revised proposal.
    await repo.update_state(session, SessionState.DISCOVERING.value)
    await _run_planning(db, planner, session.id, auth.tenant_id)

    return SessionSnapshot(
        id=session.id,
        state=session.state,
        plan_version=session.current_plan_version,
        route=session.current_route,
        created_at=session.created_at,
        updated_at=session.updated_at,
    )


@router.post(
    "/{session_id}/answers",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=SessionSnapshot,
    responses={400: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
)
async def submit_answers(
    session_id: uuid.UUID,
    body: AnswerSubmit,
    auth: Auth,
    db: DBSession,
    planner: PlannerDep,
) -> SessionSnapshot:
    repo = SessionRepository(db)
    audit = AuditRepository(db)
    session = ensure_session_ownership(
        await repo.get_by_id_for_tenant(session_id, auth.tenant_id), auth
    )

    allowed_states = {
        SessionState.AWAITING_ANSWERS,
        SessionState.DISCOVERING,
    }
    if SessionState(session.state) not in allowed_states:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot submit answers in state {session.state}",
        )

    from app.db.models import QuestionAnswer

    for question_id, answer_value in body.answers.items():
        qa = QuestionAnswer(
            session_id=session.id,
            question_id=question_id,
            plan_version=session.current_plan_version,
            answer_value=str(answer_value),
        )
        db.add(qa)
    await db.flush()

    await audit.create_event(
        actor=auth.owner_id,
        action="answers_submitted",
        session_id=session.id,
        sanitized_metadata={"question_ids": list(body.answers.keys())},
    )

    # Record answers as conversation turns so the planner incorporates them,
    # then re-enter discovery and run the next planning cycle (which typically
    # produces the architecture proposal and moves to AWAITING_APPROVAL).
    for question_id, answer_value in body.answers.items():
        await _add_turn(
            db, session.id, "user", f"Answer to {question_id}: {answer_value}", None
        )

    await repo.update_state(session, SessionState.DISCOVERING.value)
    await _run_planning(db, planner, session.id, auth.tenant_id)

    return SessionSnapshot(
        id=session.id,
        state=session.state,
        plan_version=session.current_plan_version,
        route=session.current_route,
        created_at=session.created_at,
        updated_at=session.updated_at,
    )


@router.post(
    "/{session_id}/cancel",
    status_code=status.HTTP_200_OK,
    response_model=SessionSnapshot,
    responses={400: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
)
async def cancel_session(
    session_id: uuid.UUID,
    auth: Auth,
    db: DBSession,
) -> SessionSnapshot:
    repo = SessionRepository(db)
    audit = AuditRepository(db)
    session = ensure_session_ownership(
        await repo.get_by_id_for_tenant(session_id, auth.tenant_id), auth
    )

    current_state = SessionState(session.state)
    if current_state == SessionState.HANDED_OFF:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot cancel after handoff is complete",
        )

    try:
        await repo.update_state(session, SessionState.CANCELLED.value)
    except InvalidTransitionError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    await audit.create_event(
        actor=auth.owner_id,
        action="session_cancelled",
        session_id=session.id,
    )

    await event_broadcaster.publish(
        str(session.id),
        "state_changed",
        {"state": session.state, "session_id": str(session.id)},
    )

    return SessionSnapshot(
        id=session.id,
        state=session.state,
        plan_version=session.current_plan_version,
        route=session.current_route,
        created_at=session.created_at,
        updated_at=session.updated_at,
    )


async def _add_turn(
    db: DBSession,
    session_id: uuid.UUID,
    role: str,
    text: str,
    correlation_id: uuid.UUID | None,
) -> None:
    from sqlalchemy import func as sqlfunc
    from sqlalchemy import select

    from app.db.models import ConversationTurn

    max_seq = await db.execute(
        select(sqlfunc.coalesce(sqlfunc.max(ConversationTurn.sequence), 0)).where(
            ConversationTurn.session_id == session_id
        )
    )
    next_seq = (max_seq.scalar() or 0) + 1

    turn = ConversationTurn(
        session_id=session_id,
        role=role,
        sequence=next_seq,
        sanitized_text=text,
        correlation_id=str(correlation_id) if correlation_id else None,
    )
    db.add(turn)
    await db.flush()
