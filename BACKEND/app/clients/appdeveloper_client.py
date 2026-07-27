"""AppDeveloper downstream client."""

from __future__ import annotations

import uuid
from typing import Any

import httpx
import structlog

from app.config import settings
from app.domain.citation_catalog import resolve_citations
from app.domain.schemas import ArchitectureProposal

logger = structlog.get_logger(__name__)


class AppDeveloperClient:
    def __init__(self) -> None:
        self._base_url = settings.appdeveloper_base_url
        self._api_key = settings.appdeveloper_api_key

    async def create_job(self, package_json: dict[str, Any]) -> dict[str, str]:
        prompt = self._render_markdown_brief(package_json)

        correlation_id = str(uuid.uuid4())
        session_id = package_json.get("session_id", "")
        plan_version = package_json.get("plan_version", 0)
        idempotency_key = package_json.get("idempotency_key") or str(uuid.uuid4())

        async with httpx.AsyncClient(
            base_url=self._base_url,
            headers={
                "X-API-Key": self._api_key,
                "X-Correlation-ID": correlation_id,
                "X-FDE-Session-ID": str(session_id),
                "X-FDE-Plan-Version": str(plan_version),
                "Idempotency-Key": str(idempotency_key),
            },
            timeout=httpx.Timeout(30.0),
        ) as client:
            response = await client.post(
                "/v1/jobs",
                json={"prompt": prompt},
            )
            response.raise_for_status()

            data = response.json()
            return {
                "job_id": data.get("job_id", ""),
                "state": data.get("state", ""),
            }

    def _render_markdown_brief(self, package_json: dict[str, Any]) -> str:
        proposal_data = package_json.get("proposal", {})
        proposal = ArchitectureProposal(**proposal_data)

        citation_ids = proposal.citation_ids
        citations = resolve_citations(citation_ids)
        citation_links = (
            "\n".join(f"- [{c.title}]({c.url})" for c in citations) if citations else "None"
        )

        sections = [
            f"# Planning Package: {proposal.title}",
            "",
            "## Business Problem",
            proposal.business_problem,
            "",
            "## Business Context",
            proposal.business_context,
            "",
            "## Success Metrics",
        ]
        for metric in proposal.success_metrics:
            sections.append(f"- {metric}")

        sections.extend(
            [
                "",
                "## Users",
                proposal.users,
                "",
                "## Recommended Solution",
                f"**Type:** {proposal.recommended_solution_type.value}",
                "",
                "## Alternatives",
            ]
        )
        for alt in proposal.alternatives:
            sections.append(f"### {alt.solution_type.value}")
            sections.append(alt.summary)
            sections.append(f"Pros: {', '.join(alt.pros)}")
            sections.append(f"Cons: {', '.join(alt.cons)}")
            sections.append(f"Why not recommended: {alt.why_not_recommended}")
            sections.append("")

        sections.extend(
            [
                "## Architecture Components",
                proposal.data_and_integration_plan,
                "",
                "## Data and Integration Plan",
                proposal.data_and_integration_plan,
                "",
                "## Security and Compliance",
                proposal.security_and_compliance,
                "",
                "## Human-in-the-Loop Design",
                proposal.human_in_the_loop_design,
                "",
                "## Delivery Phases",
            ]
        )
        for phase in proposal.delivery_phases:
            sections.append(f"- **{phase.name}**: {phase.description}")

        sections.extend(
            [
                "",
                "## Estimated Complexity",
                proposal.estimated_complexity,
                "",
                "## Assumptions",
            ]
        )
        for assumption in proposal.assumptions:
            sections.append(f"- {assumption}")

        sections.extend(
            [
                "",
                "## Risks",
            ]
        )
        for risk in proposal.risks:
            sections.append(f"- {risk}")

        sections.extend(
            [
                "",
                "## Official Documentation",
                citation_links,
                "",
                "## Facts Learned",
            ]
        )
        facts = package_json.get("facts", [])
        for fact in facts:
            sections.append(f"- {fact}")

        return "\n".join(sections)
