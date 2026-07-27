"""Proposal service for handling approval and handoff preparation."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.enums import ApprovalAction, SessionState
from app.domain.schemas import ApprovalRequest, PlanPackage
from app.domain.transitions import InvalidTransitionError
from app.repositories.audit_repository import AuditRepository
from app.repositories.outbox_repository import OutboxRepository
from app.repositories.proposal_repository import ProposalRepository
from app.repositories.session_repository import SessionRepository
from app.services.event_service import event_broadcaster

if TYPE_CHECKING:
    import uuid

    from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger(__name__)


class ProposalService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.session_repo = SessionRepository(db)
        self.proposal_repo = ProposalRepository(db)
        self.outbox_repo = OutboxRepository(db)
        self.audit_repo = AuditRepository(db)

    async def handle_approval(
        self,
        session_id: uuid.UUID,
        tenant_id: str,
        request: ApprovalRequest,
    ) -> dict[str, str | int]:
        session = await self.session_repo.get_by_id_for_tenant(session_id, tenant_id)
        if session is None:
            raise ValueError(f"Session {session_id} not found")

        current_state = SessionState(session.state)
        if current_state != SessionState.AWAITING_APPROVAL:
            raise InvalidTransitionError(current_state, SessionState.AWAITING_APPROVAL)

        if request.plan_version != session.current_plan_version:
            raise ValueError(
                f"Stale plan version: expected {session.current_plan_version}, got {request.plan_version}"
            )

        proposal = await self.proposal_repo.get_by_version(session_id, request.plan_version)
        if proposal is None:
            raise ValueError(f"Proposal version {request.plan_version} not found")

        if request.action == ApprovalAction.APPROVE:
            return await self._approve(session, proposal, request)
        elif request.action == ApprovalAction.REQUEST_CHANGES:
            result = await self._request_changes(session, request)
            return dict(result)
        elif request.action == ApprovalAction.CANCEL:
            result = await self._cancel(session, request)
            return dict(result)
        else:
            raise ValueError(f"Unknown action: {request.action}")

    async def _approve(
        self,
        session: Any,
        proposal: Any,
        request: ApprovalRequest,
    ) -> dict[str, str | int]:
        from app.domain.citation_catalog import resolve_citations
        from app.domain.enums import Route
        from app.domain.schemas import ArchitectureProposal

        proposal_data = ArchitectureProposal(**proposal.proposal_json)
        citations = resolve_citations(proposal_data.citation_ids)

        plan_package = PlanPackage(
            session_id=session.id,
            plan_version=session.current_plan_version,
            created_at=proposal.created_at,
            approved_at=datetime.now(UTC),
            facts=proposal.proposal_json.get("facts_learned", []),
            proposal=proposal_data,
            conversation_summary="",
            handoff_route=Route(session.current_route or "APPDEVELOPER"),
            documentation_citations=citations,
        )

        import uuid as uuid_mod

        idempotency_key = uuid_mod.uuid4()

        await self.outbox_repo.create(
            session_id=session.id,
            plan_version=session.current_plan_version,
            route=session.current_route or "APPDEVELOPER",
            idempotency_key=idempotency_key,
            package_json=plan_package.model_dump(mode="json"),
        )

        await self.session_repo.update_state(
            session,
            SessionState.HANDOFF_QUEUED.value,
        )

        await self.audit_repo.create_event(
            actor="system",
            action="plan_approved_and_queued",
            session_id=session.id,
            proposal_version=session.current_plan_version,
            sanitized_metadata={
                "route": session.current_route,
                "idempotency_key": str(idempotency_key),
            },
        )

        await event_broadcaster.publish(
            str(session.id),
            "handoff_queued",
            {
                "session_id": str(session.id),
                "plan_version": session.current_plan_version,
                "route": session.current_route,
            },
        )

        await self.db.flush()

        return {
            "status": "approved",
            "plan_version": session.current_plan_version,
            "session_id": str(session.id),
        }

    async def _request_changes(
        self,
        session: Any,
        request: ApprovalRequest,
    ) -> dict[str, str]:
        await self.session_repo.update_state(
            session,
            SessionState.DISCOVERING.value,
        )

        await self.audit_repo.create_event(
            actor="system",
            action="changes_requested",
            session_id=session.id,
            proposal_version=session.current_plan_version,
            sanitized_metadata={
                "feedback_length": len(request.feedback) if request.feedback else 0
            },
        )

        await self.db.flush()

        return {
            "status": "changes_requested",
            "session_id": str(session.id),
        }

    async def _cancel(
        self,
        session: Any,
        request: ApprovalRequest,
    ) -> dict[str, str]:
        await self.session_repo.update_state(
            session,
            SessionState.CANCELLED.value,
        )

        await self.audit_repo.create_event(
            actor="system",
            action="session_cancelled",
            session_id=session.id,
        )

        await self.db.flush()

        return {
            "status": "cancelled",
            "session_id": str(session.id),
        }
