"""LLMDeployer downstream client."""

from __future__ import annotations

import uuid
from typing import Any

import httpx
import structlog

from app.config import settings
from app.domain.schemas import ArchitectureProposal

logger = structlog.get_logger(__name__)


class LLMDeployerClient:
    def __init__(self) -> None:
        self._base_url = settings.llmdeployer_base_url
        self._api_key = settings.llmdeployer_api_key

    async def create_deployment_session(self, package_json: dict[str, Any]) -> dict[str, str]:
        correlation_id = str(uuid.uuid4())
        session_id = package_json.get("session_id", "")
        plan_version = package_json.get("plan_version", 0)

        proposal_data = package_json.get("proposal", {})
        proposal = ArchitectureProposal(**proposal_data)

        idempotency_key = package_json.get("idempotency_key") or str(uuid.uuid4())

        headers = {
            "X-API-Key": self._api_key,
            "X-Correlation-ID": correlation_id,
            "X-FDE-Session-ID": str(session_id),
            "X-FDE-Plan-Version": str(plan_version),
            "Idempotency-Key": str(idempotency_key),
        }

        async with httpx.AsyncClient(
            base_url=self._base_url,
            headers=headers,
            timeout=httpx.Timeout(30.0),
        ) as client:
            session_response = await client.post("/api/sessions")
            session_response.raise_for_status()
            downstream_session_id = session_response.json().get("session_id", "")

            answers = self._build_answers(package_json, proposal)
            answers_response = await client.post(
                f"/api/sessions/{downstream_session_id}/answers",
                json={"answers": answers},
            )
            answers_response.raise_for_status()

            return {
                "session_id": downstream_session_id,
                "status": "created",
            }

    def _build_answers(
        self,
        package_json: dict[str, Any],
        proposal: ArchitectureProposal,
    ) -> dict[str, Any]:
        facts = package_json.get("facts", [])

        brief = (
            "FDE Backend Planning Package\n\n"
            f"Title: {proposal.title}\n"
            f"Business Problem: {proposal.business_problem}\n"
            f"Context: {proposal.business_context}\n"
            f"Metrics: {', '.join(proposal.success_metrics)}\n"
            f"Complexity: {proposal.estimated_complexity}\n"
            f"Assumptions: {'; '.join(proposal.assumptions)}\n"
            f"Risks: {'; '.join(proposal.risks)}\n"
            f"Facts: {'; '.join(facts)}"
        )

        return {
            "purpose": proposal.title,
            "concurrent_users": 10,
            "peak_capacity": 50,
            "business_context": brief,
            "compliance": ["standard"],
            "model_preference": "claude-sonnet-4-20250514",
            "latency_requirements": "Standard response times",
            "budget_constraints": "Standard budget",
        }
