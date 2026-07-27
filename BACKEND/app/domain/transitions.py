"""State transition validation for planning sessions."""

from __future__ import annotations

from app.domain.enums import VALID_TRANSITIONS, SessionState


class InvalidTransitionError(Exception):
    def __init__(self, current: SessionState, target: SessionState) -> None:
        self.current = current
        self.target = target
        super().__init__(f"Invalid transition from {current.value} to {target.value}")


def enforce_transition(current: SessionState, target: SessionState) -> None:
    if target not in VALID_TRANSITIONS.get(current, set()):
        raise InvalidTransitionError(current, target)
