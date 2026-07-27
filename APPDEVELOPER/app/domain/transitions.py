from app.domain.enums import JobState, TerminalState

VALID_TRANSITIONS: dict[JobState, set[JobState | TerminalState]] = {
    JobState.CREATED: {
        JobState.ARCHITECTURE_PROPOSED,
        TerminalState.FAILED,
        TerminalState.CANCELLED,
    },
    JobState.ARCHITECTURE_PROPOSED: {
        JobState.AWAITING_ANSWERS,
        JobState.READY_TO_GENERATE,
        TerminalState.CANCELLED,
    },
    JobState.AWAITING_ANSWERS: {
        JobState.ARCHITECTURE_PROPOSED,
        JobState.READY_TO_GENERATE,
        TerminalState.CANCELLED,
    },
    JobState.READY_TO_GENERATE: {JobState.GENERATING, TerminalState.CANCELLED},
    JobState.GENERATING: {
        JobState.REVIEWING,
        TerminalState.FAILED,
        TerminalState.CANCELLED,
    },
    JobState.REVIEWING: {
        JobState.DEBUGGING,
        JobState.VERIFIED,
        TerminalState.REVIEW_FAILED,
        TerminalState.CANCELLED,
    },
    JobState.DEBUGGING: {
        JobState.REVIEWING,
        JobState.VERIFIED,
        TerminalState.REVIEW_FAILED,
        TerminalState.CANCELLED,
    },
    JobState.VERIFIED: {JobState.AWAITING_PUSH_DECISION, TerminalState.CANCELLED},
    JobState.AWAITING_PUSH_DECISION: {
        JobState.AWAITING_GITHUB_TOKEN,
        TerminalState.CANCELLED,
    },
    JobState.AWAITING_GITHUB_TOKEN: {JobState.PUSHING, TerminalState.CANCELLED},
    JobState.PUSHING: {
        JobState.PUSHED,
        TerminalState.PUSH_FAILED,
        TerminalState.CANCELLED,
    },
    JobState.PUSHED: set(),
    TerminalState.CANCELLED: set(),
    TerminalState.FAILED: set(),
    TerminalState.REVIEW_FAILED: set(),
    TerminalState.PUSH_FAILED: set(),
}


def is_valid_transition(
    current: JobState | TerminalState, target: JobState | TerminalState
) -> bool:
    return target in VALID_TRANSITIONS.get(current, set())
