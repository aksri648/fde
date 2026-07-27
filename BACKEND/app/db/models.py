"""SQLAlchemy ORM models for the FDE backend."""

from __future__ import annotations

import uuid
from datetime import datetime  # noqa: TC003  # needed at runtime by SQLAlchemy
from typing import Any

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class PlanningSession(Base):
    __tablename__ = "planning_sessions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    owner_id: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    state: Mapped[str] = mapped_column(String(32), nullable=False, default="DISCOVERING")
    current_plan_version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    current_route: Mapped[str | None] = mapped_column(String(32), nullable=True)
    is_cancelled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    turns: Mapped[list[ConversationTurn]] = relationship(back_populates="session", lazy="selectin")
    proposals: Mapped[list[ArchitectureProposalModel]] = relationship(
        back_populates="session", lazy="selectin"
    )
    questions: Mapped[list[FollowUpQuestionModel]] = relationship(
        back_populates="session", lazy="selectin"
    )
    answers: Mapped[list[QuestionAnswer]] = relationship(back_populates="session", lazy="selectin")
    outbox_entries: Mapped[list[HandoffOutbox]] = relationship(
        back_populates="session", lazy="selectin"
    )
    receipts: Mapped[list[HandoffReceiptModel]] = relationship(
        back_populates="session", lazy="selectin"
    )
    audit_events: Mapped[list[AuditEvent]] = relationship(back_populates="session", lazy="selectin")


class ConversationTurn(Base):
    __tablename__ = "conversation_turns"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("planning_sessions.id"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    sanitized_text: Mapped[str] = mapped_column(Text, nullable=False)
    correlation_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    session: Mapped[PlanningSession] = relationship(back_populates="turns")


class ArchitectureProposalModel(Base):
    __tablename__ = "architecture_proposals"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("planning_sessions.id"), nullable=False, index=True
    )
    plan_version: Mapped[int] = mapped_column(Integer, nullable=False)
    proposal_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    approval_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    session: Mapped[PlanningSession] = relationship(back_populates="proposals")


class FollowUpQuestionModel(Base):
    __tablename__ = "follow_up_questions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("planning_sessions.id"), nullable=False, index=True
    )
    plan_version: Mapped[int] = mapped_column(Integer, nullable=False)
    question_id: Mapped[str] = mapped_column(String(128), nullable=False)
    question_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    session: Mapped[PlanningSession] = relationship(back_populates="questions")


class QuestionAnswer(Base):
    __tablename__ = "question_answers"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("planning_sessions.id"), nullable=False, index=True
    )
    question_id: Mapped[str] = mapped_column(String(128), nullable=False)
    plan_version: Mapped[int] = mapped_column(Integer, nullable=False)
    answer_value: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    session: Mapped[PlanningSession] = relationship(back_populates="answers")


class HandoffOutbox(Base):
    __tablename__ = "handoff_outbox"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("planning_sessions.id"), nullable=False, index=True
    )
    plan_version: Mapped[int] = mapped_column(Integer, nullable=False)
    route: Mapped[str] = mapped_column(String(32), nullable=False)
    idempotency_key: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, unique=True
    )
    package_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="PENDING")
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    locked_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    session: Mapped[PlanningSession] = relationship(back_populates="outbox_entries")


class HandoffReceiptModel(Base):
    __tablename__ = "handoff_receipts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("planning_sessions.id"), nullable=False, index=True
    )
    outbox_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    route: Mapped[str] = mapped_column(String(32), nullable=False)
    idempotency_key: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    downstream_id: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    downstream_status: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    response_digest: Mapped[str | None] = mapped_column(Text, nullable=True)
    accepted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    session: Mapped[PlanningSession] = relationship(back_populates="receipts")


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    actor: Mapped[str] = mapped_column(String(128), nullable=False)
    action: Mapped[str] = mapped_column(String(128), nullable=False)
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("planning_sessions.id"), nullable=False, index=True
    )
    proposal_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    correlation_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    sanitized_metadata: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    session: Mapped[PlanningSession] = relationship(back_populates="audit_events")
