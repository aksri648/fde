from enum import StrEnum


class JobState(StrEnum):
    CREATED = "CREATED"
    ARCHITECTURE_PROPOSED = "ARCHITECTURE_PROPOSED"
    AWAITING_ANSWERS = "AWAITING_ANSWERS"
    READY_TO_GENERATE = "READY_TO_GENERATE"
    GENERATING = "GENERATING"
    REVIEWING = "REVIEWING"
    DEBUGGING = "DEBUGGING"
    VERIFIED = "VERIFIED"
    AWAITING_PUSH_DECISION = "AWAITING_PUSH_DECISION"
    AWAITING_GITHUB_TOKEN = "AWAITING_GITHUB_TOKEN"
    PUSHING = "PUSHING"
    PUSHED = "PUSHED"


class TerminalState(StrEnum):
    CANCELLED = "CANCELLED"
    FAILED = "FAILED"
    REVIEW_FAILED = "REVIEW_FAILED"
    PUSH_FAILED = "PUSH_FAILED"


class EventName(StrEnum):
    STATE_CHANGED = "state_changed"
    ARCHITECTURE_READY = "architecture_ready"
    QUESTIONS_READY = "questions_ready"
    AGENT_MESSAGE = "agent_message"
    TOOL_ACTIVITY = "tool_activity"
    FILE_CREATED = "file_created"
    VALIDATION_STARTED = "validation_started"
    VALIDATION_RESULT = "validation_result"
    REVIEW_FINDING = "review_finding"
    GITHUB_STATUS = "github_status"
    COMPLETED = "completed"
    ERROR = "error"
