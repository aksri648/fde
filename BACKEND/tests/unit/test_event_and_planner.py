"""Unit tests for event service and planner."""

from __future__ import annotations

import asyncio
import uuid

import pytest

from app.services.event_service import EventBroadcaster


class TestEventBroadcaster:
    def test_subscribe_and_publish(self) -> None:
        broadcaster = EventBroadcaster()
        _sequence, queue = broadcaster.subscribe("session-1")

        asyncio.get_event_loop().run_until_complete(
            broadcaster.publish("session-1", "test_event", {"key": "value"})
        )

        assert not queue.empty()
        event = queue.get_nowait()
        assert event["event"] == "test_event"
        assert event["data"]["key"] == "value"
        assert event["sequence"] > 0

    def test_unsubscribe(self) -> None:
        broadcaster = EventBroadcaster()
        sequence, queue = broadcaster.subscribe("session-1")
        broadcaster.unsubscribe("session-1", sequence)

        asyncio.get_event_loop().run_until_complete(
            broadcaster.publish("session-1", "test_event", {"key": "value"})
        )

        assert queue.empty()

    def test_get_history_after(self) -> None:
        broadcaster = EventBroadcaster()

        asyncio.get_event_loop().run_until_complete(
            broadcaster.publish("session-1", "event1", {"data": 1})
        )
        asyncio.get_event_loop().run_until_complete(
            broadcaster.publish("session-1", "event2", {"data": 2})
        )

        history = broadcaster.get_history_after("session-1", 0)
        assert len(history) == 2

        history = broadcaster.get_history_after("session-1", 1)
        assert len(history) == 1
        assert history[0]["event"] == "event2"

    def test_multiple_subscribers(self) -> None:
        broadcaster = EventBroadcaster()
        _, queue1 = broadcaster.subscribe("session-1")
        _, queue2 = broadcaster.subscribe("session-1")

        asyncio.get_event_loop().run_until_complete(
            broadcaster.publish("session-1", "test_event", {"data": "test"})
        )

        assert not queue1.empty()
        assert not queue2.empty()


class TestFakePlanner:
    @pytest.mark.asyncio
    async def test_fake_planner_first_call_returns_questions(self) -> None:
        from app.services.claude_planner import FakePlanner

        planner = FakePlanner()
        result = await planner.plan(
            conversation_history=[{"role": "user", "content": "Help me build an AI app"}],
            facts=[],
            current_state="DISCOVERING",
            plan_version=0,
        )

        assert len(result.questions) == 3
        assert result.proposal is None
        assert result.needs_more_information is True

    @pytest.mark.asyncio
    async def test_fake_planner_second_call_returns_proposal(self) -> None:
        from app.services.claude_planner import FakePlanner

        planner = FakePlanner()
        result = await planner.plan(
            conversation_history=[
                {"role": "user", "content": "Help me build an AI app"},
                {"role": "assistant", "content": "Tell me more"},
                {"role": "user", "content": "I need a document processor"},
            ],
            facts=["User needs document processing"],
            current_state="AWAITING_ANSWERS",
            plan_version=1,
        )

        assert result.proposal is not None
        assert result.requires_human_approval is True
        assert result.safe_to_handoff is True


class TestPlanningService:
    @pytest.mark.asyncio
    async def test_build_conversation_history(self) -> None:
        from unittest.mock import AsyncMock, MagicMock

        from app.services.planning_service import PlanningService

        mock_db = AsyncMock()
        mock_planner = MagicMock()

        mock_turn = MagicMock()
        mock_turn.role = "user"
        mock_turn.sanitized_text = "Test message"

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_turn]
        mock_db.execute = AsyncMock(return_value=mock_result)

        service = PlanningService(mock_db, mock_planner)
        history = await service._build_conversation_history(uuid.uuid4())

        assert len(history) == 1
        assert history[0]["role"] == "user"
        assert history[0]["content"] == "Test message"
