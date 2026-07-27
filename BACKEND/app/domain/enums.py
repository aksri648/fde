"""Domain enums for the FDE backend."""

from __future__ import annotations

from enum import StrEnum


class SessionState(StrEnum):
    DISCOVERING = "DISCOVERING"
    AWAITING_ANSWERS = "AWAITING_ANSWERS"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    HANDOFF_QUEUED = "HANDOFF_QUEUED"
    HANDOFF_FAILED = "HANDOFF_FAILED"
    HANDED_OFF = "HANDED_OFF"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class SolutionType(StrEnum):
    NO_AI_OR_DETERMINISTIC_AUTOMATION = "NO_AI_OR_DETERMINISTIC_AUTOMATION"
    CHATBOT = "CHATBOT"
    RAG = "RAG"
    TOOL_USING_AGENT = "TOOL_USING_AGENT"
    LANGGRAPH_WORKFLOW = "LANGGRAPH_WORKFLOW"
    OPENAI_AGENTS_SDK_APPLICATION = "OPENAI_AGENTS_SDK_APPLICATION"


class Route(StrEnum):
    APPDEVELOPER = "APPDEVELOPER"
    LLMDEPLOYER = "LLMDEPLOYER"
    AMBIGUOUS = "AMBIGUOUS"


class ApprovalAction(StrEnum):
    APPROVE = "approve"
    REQUEST_CHANGES = "request_changes"
    CANCEL = "cancel"


class AnswerType(StrEnum):
    TEXT = "text"
    SINGLE_SELECT = "single_select"
    MULTI_SELECT = "multi_select"
    NUMBER = "number"
    BOOLEAN = "boolean"


class OutboxStatus(StrEnum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class HandoffTarget(StrEnum):
    APPDEVELOPER = "APPDEVELOPER"
    LLMDEPLOYER = "LLMDEPLOYER"


VALID_TRANSITIONS: dict[SessionState, set[SessionState]] = {
    SessionState.DISCOVERING: {
        SessionState.AWAITING_ANSWERS,
        SessionState.AWAITING_APPROVAL,
        SessionState.FAILED,
        SessionState.CANCELLED,
    },
    SessionState.AWAITING_ANSWERS: {
        SessionState.DISCOVERING,
        SessionState.CANCELLED,
    },
    SessionState.AWAITING_APPROVAL: {
        SessionState.DISCOVERING,
        SessionState.HANDOFF_QUEUED,
        SessionState.CANCELLED,
    },
    SessionState.HANDOFF_QUEUED: {
        SessionState.HANDED_OFF,
        SessionState.HANDOFF_FAILED,
        SessionState.CANCELLED,
    },
    SessionState.HANDOFF_FAILED: {
        SessionState.HANDOFF_QUEUED,
        SessionState.CANCELLED,
    },
    SessionState.HANDED_OFF: set(),
    SessionState.FAILED: {
        SessionState.DISCOVERING,
        SessionState.CANCELLED,
    },
    SessionState.CANCELLED: set(),
}


def validate_transition(current: SessionState, target: SessionState) -> bool:
    return target in VALID_TRANSITIONS.get(current, set())
