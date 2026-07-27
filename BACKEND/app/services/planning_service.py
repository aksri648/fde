"""Planning service orchestrating the planner and persistence."""

from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING, Any

import structlog

from app.domain.enums import SessionState
from app.domain.transitions import InvalidTransitionError
from app.repositories.audit_repository import AuditRepository
from app.repositories.proposal_repository import ProposalRepository
from app.repositories.session_repository import SessionRepository
from app.services.event_service import event_broadcaster
from app.services.redaction_service import redact_for_planner

if TYPE_CHECKING:
    import uuid

    from sqlalchemy.ext.asyncio import AsyncSession

    from app.domain.schemas import PlannerOutput
    from app.services.claude_planner import Planner

logger = structlog.get_logger(__name__)


class PlanningService:
    def __init__(self, db: AsyncSession, planner: Planner) -> None:
        self.db = db
        self.planner = planner
        self.session_repo = SessionRepository(db)
        self.proposal_repo = ProposalRepository(db)
        self.audit_repo = AuditRepository(db)

    async def run_planning_cycle(
        self,
        session_id: uuid.UUID,
        tenant_id: str,
    ) -> PlannerOutput:
        session = await self.session_repo.get_by_id_for_tenant(session_id, tenant_id)
        if session is None:
            raise ValueError(f"Session {session_id} not found")

        current_state = SessionState(session.state)
        if current_state in (SessionState.HANDED_OFF, SessionState.CANCELLED):
            raise InvalidTransitionError(current_state, SessionState.DISCOVERING)

        conversation_history = await self._build_conversation_history(session_id)
        facts = await self._get_accumulated_facts(session_id)

        try:
            output = await self.planner.plan(
                conversation_history=conversation_history,
                facts=facts,
                current_state=session.state,
                plan_version=session.current_plan_version,
            )
        except Exception as e:
            logger.error("planner_error", session_id=str(session_id), error=str(e))
            await self._handle_planner_error(session, str(e))
            raise

        await self._persist_planner_output(session, output)

        return output

    async def _build_conversation_history(self, session_id: uuid.UUID) -> list[dict[str, str]]:
        from sqlalchemy import select

        from app.db.models import ConversationTurn

        result = await self.db.execute(
            select(ConversationTurn)
            .where(ConversationTurn.session_id == session_id)
            .order_by(ConversationTurn.sequence)
        )
        turns = result.scalars().all()

        history: list[dict[str, str]] = []
        for turn in turns:
            history.append(
                {
                    "role": turn.role,
                    "content": redact_for_planner(turn.sanitized_text),
                }
            )
        return history

    async def _get_accumulated_facts(self, session_id: uuid.UUID) -> list[str]:
        from sqlalchemy import select

        from app.db.models import AuditEvent

        result = await self.db.execute(
            select(AuditEvent)
            .where(
                AuditEvent.session_id == session_id,
                AuditEvent.action == "planning_cycle_completed",
            )
            .order_by(AuditEvent.created_at.desc())
            .limit(1)
        )
        latest_event = result.scalar_one_or_none()
        if latest_event and latest_event.sanitized_metadata:
            facts: list[str] = latest_event.sanitized_metadata.get("facts_learned", [])
            return facts
        return []

    async def _persist_planner_output(
        self,
        session: Any,
        output: PlannerOutput,
    ) -> None:
        await self.audit_repo.create_event(
            actor="system",
            action="planning_cycle_completed",
            session_id=session.id,
            proposal_version=session.current_plan_version,
            sanitized_metadata={
                "facts_learned": output.facts_learned,
                "has_proposal": output.proposal is not None,
                "question_count": len(output.questions),
            },
        )

        if output.proposal is not None:
            proposal_data = output.proposal.model_dump()

            existing = await self.proposal_repo.get_latest_for_session(session.id)
            new_version = (existing.plan_version if existing else 0) + 1

            await self.proposal_repo.create(
                session_id=session.id,
                plan_version=new_version,
                proposal_json=proposal_data,
            )

            await self.session_repo.update_state(
                session,
                SessionState.AWAITING_APPROVAL.value,
                increment_version=True,
                route=output.proposal.recommended_route.value,
            )

            await event_broadcaster.publish(
                str(session.id),
                "proposal_ready",
                {
                    "session_id": str(session.id),
                    "plan_version": new_version,
                    "title": output.proposal.title,
                },
            )

            await event_broadcaster.publish(
                str(session.id),
                "approval_required",
                {
                    "session_id": str(session.id),
                    "plan_version": new_version,
                },
            )
        else:
            if output.questions:
                from app.db.models import FollowUpQuestionModel

                for q in output.questions:
                    q_model = FollowUpQuestionModel(
                        session_id=session.id,
                        plan_version=session.current_plan_version,
                        question_id=q.id,
                        question_json=q.model_dump(),
                    )
                    self.db.add(q_model)
                await self.db.flush()

                await self.session_repo.update_state(
                    session,
                    SessionState.AWAITING_ANSWERS.value,
                )

                await event_broadcaster.publish(
                    str(session.id),
                    "questions_ready",
                    {
                        "session_id": str(session.id),
                        "question_count": len(output.questions),
                    },
                )

        await event_broadcaster.publish(
            str(session.id),
            "assistant_message",
            {
                "session_id": str(session.id),
                "message": output.assistant_message,
            },
        )

        await self.db.flush()

    async def _handle_planner_error(
        self,
        session: Any,
        error: str,
    ) -> None:
        with contextlib.suppress(InvalidTransitionError):
            await self.session_repo.update_state(
                session,
                SessionState.FAILED.value,
            )

        await event_broadcaster.publish(
            str(session.id),
            "error",
            {
                "session_id": str(session.id),
                "error": "Planning cycle failed",
            },
        )

        await self.db.flush()
