"""Repository for architecture proposal operations."""

from __future__ import annotations

import hashlib
import json
from typing import TYPE_CHECKING, Any

from sqlalchemy import select

from app.db.models import ArchitectureProposalModel

if TYPE_CHECKING:
    import uuid

    from sqlalchemy.ext.asyncio import AsyncSession


class ProposalRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(
        self,
        session_id: uuid.UUID,
        plan_version: int,
        proposal_json: dict[str, Any],
    ) -> ArchitectureProposalModel:
        content_hash = hashlib.sha256(
            json.dumps(proposal_json, sort_keys=True, default=str).encode()
        ).hexdigest()
        proposal = ArchitectureProposalModel(
            session_id=session_id,
            plan_version=plan_version,
            proposal_json=proposal_json,
            content_hash=content_hash,
        )
        self.db.add(proposal)
        await self.db.flush()
        return proposal

    async def get_latest_for_session(
        self, session_id: uuid.UUID
    ) -> ArchitectureProposalModel | None:
        result = await self.db.execute(
            select(ArchitectureProposalModel)
            .where(ArchitectureProposalModel.session_id == session_id)
            .order_by(ArchitectureProposalModel.plan_version.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_by_version(
        self, session_id: uuid.UUID, plan_version: int
    ) -> ArchitectureProposalModel | None:
        result = await self.db.execute(
            select(ArchitectureProposalModel).where(
                ArchitectureProposalModel.session_id == session_id,
                ArchitectureProposalModel.plan_version == plan_version,
            )
        )
        return result.scalar_one_or_none()

    async def set_approval_summary(
        self,
        proposal: ArchitectureProposalModel,
        summary: str,
    ) -> None:
        proposal.approval_summary = summary
        await self.db.flush()
