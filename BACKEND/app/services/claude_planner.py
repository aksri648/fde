"""Planner protocol and fake planner for testing."""

from __future__ import annotations

from typing import Protocol

from app.domain.schemas import PlannerOutput


class Planner(Protocol):
    async def plan(
        self,
        conversation_history: list[dict[str, str]],
        facts: list[str],
        current_state: str,
        plan_version: int,
    ) -> PlannerOutput: ...


class FakePlanner:
    """Deterministic fake planner for testing."""

    def __init__(self) -> None:
        self.call_count = 0

    async def plan(
        self,
        conversation_history: list[dict[str, str]],
        facts: list[str],
        current_state: str,
        plan_version: int,
    ) -> PlannerOutput:
        self.call_count += 1

        if len(conversation_history) <= 2:
            return PlannerOutput(
                assistant_message="Thank you for describing your problem. I have a few follow-up questions to better understand your needs.",
                facts_learned=["User described initial problem"],
                questions=[
                    {
                        "id": "q1",
                        "question": "What is the primary business outcome you want to achieve?",
                        "why_it_matters": "Understanding the desired outcome helps us recommend the right architecture.",
                        "required": True,
                        "answer_type": "text",
                        "options": [],
                    },
                    {
                        "id": "q2",
                        "question": "Who are the primary users of this solution?",
                        "why_it_matters": "User profiles inform interface and performance requirements.",
                        "required": True,
                        "answer_type": "text",
                        "options": [],
                    },
                    {
                        "id": "q3",
                        "question": "What data sources will this solution need to access?",
                        "why_it_matters": "Data requirements determine the technical approach.",
                        "required": True,
                        "answer_type": "text",
                        "options": [],
                    },
                ],
                proposal=None,
                needs_more_information=True,
                requires_human_approval=False,
                safe_to_handoff=False,
            )

        from app.domain.enums import Route, SolutionType
        from app.domain.schemas import ArchitectureOption, ArchitectureProposal

        proposal = ArchitectureProposal(
            title="AI-Powered Document Processing Solution",
            business_problem="Automate document processing and information extraction",
            business_context="The organization needs to process large volumes of documents efficiently.",
            success_metrics=["Reduce processing time by 50%", "Improve accuracy to 95%"],
            users="Operations team and document reviewers",
            recommended_solution_type=SolutionType.TOOL_USING_AGENT,
            alternatives=[
                ArchitectureOption(
                    solution_type=SolutionType.RAG,
                    summary="Retrieval-augmented generation for document Q&A",
                    pros=["Good for knowledge retrieval", "Can handle multiple document types"],
                    cons=["Not ideal for structured extraction"],
                    why_not_recommended="Better suited for Q&A than structured extraction",
                ),
            ],
            architecture_components=[],
            data_and_integration_plan="Integration with document storage and processing pipeline",
            security_and_compliance="Standard data handling with role-based access",
            human_in_the_loop_design="Review stage for extracted data validation",
            delivery_phases=[],
            estimated_complexity="Medium",
            assumptions=[
                "Documents are in standard formats",
                "Existing data infrastructure is available",
            ],
            risks=["Data quality may affect extraction accuracy"],
            open_questions=[],
            recommended_route=Route.APPDEVELOPER,
            route_rationale="This requires application development for document processing pipeline",
            citation_ids=["langgraph_overview"],
        )

        return PlannerOutput(
            assistant_message="Based on our conversation, I recommend a Tool-Using Agent architecture for your document processing needs.",
            facts_learned=[*facts, "Recommended tool-using agent architecture"],
            questions=[],
            proposal=proposal,
            needs_more_information=False,
            requires_human_approval=True,
            safe_to_handoff=True,
        )
