"""Pydantic v2 schemas for request/response and LLM output validation."""

from __future__ import annotations

import uuid  # noqa: TC003  # needed at runtime by Pydantic
from datetime import datetime  # noqa: TC003  # needed at runtime by Pydantic
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.domain.enums import (
    AnswerType,
    ApprovalAction,
    Route,
    SolutionType,
)

# --- Documentation citations (defined early for forward refs) ---


class DocumentationCitation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    title: str
    url: str


# --- Conversation and proposal models ---


class SessionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    initial_message: str = Field(..., min_length=1, max_length=20000)
    client_request_id: uuid.UUID | None = None


class ConversationTurnCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: str = Field(..., min_length=1, max_length=20000)


class FollowUpQuestionOption(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str
    value: str


class FollowUpQuestion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(..., min_length=1, max_length=128)
    question: str = Field(..., min_length=1, max_length=2000)
    why_it_matters: str = Field(..., min_length=1, max_length=1000)
    required: bool = True
    answer_type: AnswerType = AnswerType.TEXT
    options: list[FollowUpQuestionOption] = Field(default_factory=list)


class ArchitectureOption(BaseModel):
    model_config = ConfigDict(extra="forbid")

    solution_type: SolutionType
    summary: str = Field(..., max_length=2000)
    pros: list[str] = Field(default_factory=list)
    cons: list[str] = Field(default_factory=list)
    why_not_recommended: str = Field(default="", max_length=1000)


class ArchitectureComponent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., max_length=200)
    description: str = Field(..., max_length=2000)
    technology: str = Field(default="", max_length=200)


class DeliveryPhase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., max_length=200)
    description: str = Field(..., max_length=2000)
    estimated_duration: str = Field(default="", max_length=200)


class ArchitectureProposal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(..., min_length=1, max_length=500)
    business_problem: str = Field(..., min_length=1, max_length=5000)
    business_context: str = Field(default="", max_length=5000)
    success_metrics: list[str] = Field(default_factory=list)
    users: str = Field(default="", max_length=2000)
    recommended_solution_type: SolutionType
    alternatives: list[ArchitectureOption] = Field(default_factory=list)
    architecture_components: list[ArchitectureComponent] = Field(default_factory=list)
    data_and_integration_plan: str = Field(default="", max_length=5000)
    security_and_compliance: str = Field(default="", max_length=3000)
    human_in_the_loop_design: str = Field(default="", max_length=3000)
    delivery_phases: list[DeliveryPhase] = Field(default_factory=list)
    estimated_complexity: str = Field(default="", max_length=500)
    assumptions: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)
    recommended_route: Route
    route_rationale: str = Field(..., min_length=1, max_length=3000)
    citation_ids: list[str] = Field(default_factory=list)


class PlannerOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    assistant_message: str = Field(..., min_length=1, max_length=10000)
    facts_learned: list[str] = Field(default_factory=list)
    questions: list[FollowUpQuestion] = Field(default_factory=list)
    proposal: ArchitectureProposal | None = None
    needs_more_information: bool = True
    requires_human_approval: bool = False
    safe_to_handoff: bool = False


class ApprovalRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    plan_version: int = Field(..., ge=1)
    action: ApprovalAction
    feedback: str | None = Field(default=None, max_length=10000)


class PlanPackage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = "1.0"
    session_id: uuid.UUID
    plan_version: int
    created_at: datetime
    approved_at: datetime
    facts: list[str] = Field(default_factory=list)
    proposal: ArchitectureProposal
    conversation_summary: str = Field(default="", max_length=10000)
    handoff_route: Route
    documentation_citations: list[DocumentationCitation] = Field(default_factory=list)


class HandoffReceipt(BaseModel):
    model_config = ConfigDict(extra="forbid")

    route: Route
    idempotency_key: uuid.UUID
    downstream_id: str = Field(default="", max_length=500)
    downstream_status: str = Field(default="", max_length=100)
    accepted_at: datetime | None = None
    attempt_count: int = 0


# --- API response models ---


class SessionSnapshot(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    state: str
    plan_version: int
    route: str | None = None
    created_at: datetime
    updated_at: datetime


class QuestionListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    questions: list[FollowUpQuestion]


class AnswerSubmit(BaseModel):
    model_config = ConfigDict(extra="forbid")

    answers: dict[str, Any]


class ErrorResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    error_code: str
    message: str
    correlation_id: str | None = None
