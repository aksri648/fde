"""Planning and proposal API endpoints."""

from __future__ import annotations

import uuid  # noqa: TC003  # runtime import required for FastAPI param resolution
from typing import Any

from fastapi import APIRouter, HTTPException, status

# Runtime imports required for FastAPI dependency injection (see sessions.py).
from app.api.dependencies import Auth, DBSession  # noqa: TC001
from app.domain.schemas import (
    ApprovalRequest,
    ErrorResponse,
    FollowUpQuestion,
    QuestionListResponse,
)
from app.domain.transitions import InvalidTransitionError
from app.repositories.proposal_repository import ProposalRepository
from app.repositories.session_repository import SessionRepository
from app.security.authorization import ensure_session_ownership
from app.services.proposal_service import ProposalService

router = APIRouter(prefix="/v1/sessions", tags=["planning"])


@router.get(
    "/{session_id}/questions",
    response_model=QuestionListResponse,
    responses={404: {"model": ErrorResponse}},
)
async def get_questions(
    session_id: uuid.UUID,
    auth: Auth,
    db: DBSession,
) -> QuestionListResponse:
    repo = SessionRepository(db)
    session = ensure_session_ownership(
        await repo.get_by_id_for_tenant(session_id, auth.tenant_id), auth
    )

    from sqlalchemy import select

    from app.db.models import FollowUpQuestionModel

    result = await db.execute(
        select(FollowUpQuestionModel).where(
            FollowUpQuestionModel.session_id == session_id,
            FollowUpQuestionModel.plan_version == session.current_plan_version,
        )
    )
    questions = []
    for q in result.scalars().all():
        q_data: dict[str, Any] = q.question_json
        questions.append(FollowUpQuestion(**q_data))

    return QuestionListResponse(questions=questions)


@router.get(
    "/{session_id}/proposal",
    responses={404: {"model": ErrorResponse}},
)
async def get_proposal(
    session_id: uuid.UUID,
    auth: Auth,
    db: DBSession,
) -> dict[str, Any]:
    repo = SessionRepository(db)
    ensure_session_ownership(await repo.get_by_id_for_tenant(session_id, auth.tenant_id), auth)

    prop_repo = ProposalRepository(db)
    proposal = await prop_repo.get_latest_for_session(session_id)
    if proposal is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No proposal found for this session",
        )

    from app.domain.citation_catalog import resolve_citations

    proposal_data: dict[str, Any] = proposal.proposal_json
    citation_ids = proposal_data.get("citation_ids", [])
    citations = resolve_citations(citation_ids)

    return {
        "proposal": proposal_data,
        "plan_version": proposal.plan_version,
        "content_hash": proposal.content_hash,
        "citations": [c.model_dump() for c in citations],
    }


@router.post(
    "/{session_id}/approval",
    status_code=status.HTTP_202_ACCEPTED,
    responses={
        400: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
    },
)
async def submit_approval(
    session_id: uuid.UUID,
    body: ApprovalRequest,
    auth: Auth,
    db: DBSession,
) -> dict[str, Any]:
    service = ProposalService(db)
    try:
        result = await service.handle_approval(
            session_id=session_id,
            tenant_id=auth.tenant_id,
            request=body,
        )
        return result
    except InvalidTransitionError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except ValueError as e:
        detail = str(e)
        if "Stale plan version" in detail:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=detail,
            )
        if "not found" in detail.lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=detail,
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=detail,
        )
