import structlog

from app.domain.enums import EventName
from app.domain.schemas import ArchitectureProposal, FollowUpQuestion
from app.services.agent_service import AgentService
from app.services.event_service import EventService

logger = structlog.get_logger()


class ArchitectureService:
    def __init__(
        self,
        agent_service: AgentService,
        event_service: EventService,
    ) -> None:
        self._agent = agent_service
        self._events = event_service

    async def propose_architecture(
        self,
        job_id: str,
        prompt: str,
        answer_history: dict[str, str] | None = None,
    ) -> tuple[ArchitectureProposal, list[FollowUpQuestion]]:
        await self._events.emit(
            job_id,
            EventName.AGENT_MESSAGE,
            {"role": "planner", "status": "starting"},
        )

        try:
            proposal, questions = await self._agent.run_planner(
                prompt=prompt,
                answer_history=answer_history,
            )

            await self._events.emit(
                job_id,
                EventName.ARCHITECTURE_READY,
                {
                    "app_type": proposal.app_type,
                    "stack": proposal.stack,
                    "components_count": len(proposal.components),
                },
            )

            if questions:
                await self._events.emit(
                    job_id,
                    EventName.QUESTIONS_READY,
                    {
                        "questions": [
                            {"id": q.id, "question": q.question} for q in questions
                        ]
                    },
                )

            return proposal, questions

        except Exception as e:
            logger.error("architecture_proposal_failed", job_id=job_id, error=str(e))
            await self._events.emit(
                job_id,
                EventName.ERROR,
                {"error": f"Architecture proposal failed: {e}"},
            )
            raise

    def create_brief(
        self,
        proposal: ArchitectureProposal,
        answers: dict[str, str],
    ) -> str:
        brief_parts = [
            f"App Type: {proposal.app_type}",
            f"Stack: {', '.join(proposal.stack)}",
            f"Components: {', '.join(proposal.components)}",
            "",
            "Data Model:",
        ]

        for table, fields in proposal.data_model.items():
            brief_parts.append(f"  {table}: {fields}")

        if proposal.api_boundaries:
            brief_parts.append("")
            brief_parts.append("API Endpoints:")
            for endpoint in proposal.api_boundaries:
                brief_parts.append(f"  {endpoint}")

        if proposal.security_concerns:
            brief_parts.append("")
            brief_parts.append("Security Concerns:")
            for concern in proposal.security_concerns:
                brief_parts.append(f"  - {concern}")

        if proposal.assumptions:
            brief_parts.append("")
            brief_parts.append("Assumptions:")
            for assumption in proposal.assumptions:
                brief_parts.append(f"  - {assumption}")

        if proposal.risks:
            brief_parts.append("")
            brief_parts.append("Risks:")
            for risk in proposal.risks:
                brief_parts.append(f"  - {risk}")

        if proposal.deliverables:
            brief_parts.append("")
            brief_parts.append("Deliverables:")
            for deliverable in proposal.deliverables:
                brief_parts.append(f"  - {deliverable}")

        if answers:
            brief_parts.append("")
            brief_parts.append("User Answers:")
            for q_id, answer in answers.items():
                brief_parts.append(f"  {q_id}: {answer}")

        return "\n".join(brief_parts)
