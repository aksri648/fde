"""Event service for publishing sanitized events to WebSocket clients."""

from __future__ import annotations

import asyncio
import contextlib
from collections import defaultdict
from datetime import UTC, datetime
from typing import Any

import structlog

from app.services.redaction_service import redact_dict

logger = structlog.get_logger(__name__)


class EventBroadcaster:
    def __init__(self) -> None:
        self._subscribers: dict[str, dict[int, asyncio.Queue[dict[str, Any]]]] = defaultdict(dict)
        self._counters: dict[str, int] = defaultdict(int)
        self._event_history: dict[str, list[dict[str, Any]]] = defaultdict(list)
        self._max_history: int = 100

    def _next_sequence(self, session_id: str) -> int:
        self._counters[session_id] += 1
        return self._counters[session_id]

    def subscribe(self, session_id: str) -> tuple[int, asyncio.Queue[dict[str, Any]]]:
        sequence = self._next_sequence(session_id)
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self._subscribers[session_id][sequence] = queue
        return sequence, queue

    def unsubscribe(self, session_id: str, sequence: int) -> None:
        self._subscribers[session_id].pop(sequence, None)

    def get_history_after(self, session_id: str, after_sequence: int) -> list[dict[str, Any]]:
        history = self._event_history.get(session_id, [])
        return [e for e in history if e.get("sequence", 0) > after_sequence]

    async def publish(
        self,
        session_id: str,
        event_name: str,
        data: dict[str, Any],
    ) -> None:
        sequence = self._next_sequence(session_id)
        event = {
            "sequence": sequence,
            "event": event_name,
            "timestamp": datetime.now(UTC).isoformat(),
            "data": redact_dict(data),
        }

        self._event_history[session_id].append(event)
        if len(self._event_history[session_id]) > self._max_history:
            self._event_history[session_id] = self._event_history[session_id][-self._max_history :]

        for seq, queue in self._subscribers.get(session_id, {}).items():
            if seq <= sequence:
                with contextlib.suppress(asyncio.QueueFull):
                    queue.put_nowait(event)

        logger.info(
            "event_published",
            session_id=session_id,
            event_name=event_name,
            sequence=sequence,
        )


event_broadcaster = EventBroadcaster()
