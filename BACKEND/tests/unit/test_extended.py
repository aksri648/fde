"""Unit tests for auth, citation catalog, and other modules."""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock

import pytest

from app.domain.citation_catalog import (
    CITATION_CATALOG,
    resolve_citations,
    validate_citation_ids,
)
from app.domain.route_policy import validate_route
from app.security.auth import AuthContext
from app.security.authorization import ensure_session_ownership


class TestCitationCatalog:
    def test_catalog_has_required_entries(self) -> None:
        required = [
            "claude_agent_sdk",
            "litellm_proxy",
            "openai_agents_sdk",
            "openai_responses_api",
            "langgraph_overview",
            "langgraph_hitl",
            "fastapi",
            "owasp_prompt_injection",
        ]
        for key in required:
            assert key in CITATION_CATALOG

    def test_resolve_citations_valid(self) -> None:
        citations = resolve_citations(["claude_agent_sdk", "fastapi"])
        assert len(citations) == 2
        assert citations[0].id == "claude_agent_sdk"
        assert citations[1].id == "fastapi"

    def test_resolve_citations_invalid_id_ignored(self) -> None:
        citations = resolve_citations(["invalid_id", "claude_agent_sdk"])
        assert len(citations) == 1

    def test_resolve_citations_empty(self) -> None:
        citations = resolve_citations([])
        assert len(citations) == 0

    def test_validate_citation_ids_valid(self) -> None:
        result = validate_citation_ids(["claude_agent_sdk", "fastapi"])
        assert result == ["claude_agent_sdk", "fastapi"]

    def test_validate_citation_ids_invalid(self) -> None:
        with pytest.raises(ValueError):
            validate_citation_ids(["invalid_id"])

    def test_all_citations_have_urls(self) -> None:
        for cid, citation in CITATION_CATALOG.items():
            assert citation.url.startswith("https://"), f"Citation {cid} must have HTTPS URL"
            assert citation.title, f"Citation {cid} must have a title"


class TestAuthorization:
    def test_ensure_session_ownership_success(self) -> None:
        session = MagicMock()
        session.tenant_id = "tenant-1"
        auth = AuthContext(tenant_id="tenant-1", owner_id="user-1", token="tok")

        result = ensure_session_ownership(session, auth)
        assert result == session

    def test_ensure_session_ownership_none_session(self) -> None:
        from fastapi import HTTPException

        auth = AuthContext(tenant_id="tenant-1", owner_id="user-1", token="tok")
        with pytest.raises(HTTPException) as exc_info:
            ensure_session_ownership(None, auth)
        assert exc_info.value.status_code == 404

    def test_ensure_session_ownership_wrong_tenant(self) -> None:
        from fastapi import HTTPException

        session = MagicMock()
        session.tenant_id = "tenant-1"
        auth = AuthContext(tenant_id="tenant-2", owner_id="user-1", token="tok")
        with pytest.raises(HTTPException) as exc_info:
            ensure_session_ownership(session, auth)
        assert exc_info.value.status_code == 403


class TestRoutePolicyEdgeCases:
    def test_ambiguous_route_passthrough(self) -> None:
        from app.domain.enums import Route, SolutionType

        route = validate_route(Route.AMBIGUOUS, SolutionType.RAG, "Need both build and deploy")
        assert route == Route.AMBIGUOUS

    def test_llmdeployer_with_build_keywords_returns_ambiguous(self) -> None:
        from app.domain.enums import Route, SolutionType

        route = validate_route(
            Route.LLMDEPLOYER,
            SolutionType.TOOL_USING_AGENT,
            "Need to build a RAG application and deploy it",
        )
        assert route == Route.AMBIGUOUS


class TestSchemasEdgeCases:
    def test_plan_package_serialization(self) -> None:
        from datetime import UTC, datetime

        from app.domain.enums import Route, SolutionType
        from app.domain.schemas import ArchitectureProposal, PlanPackage

        proposal = ArchitectureProposal(
            title="Test",
            business_problem="Test problem",
            recommended_solution_type=SolutionType.CHATBOT,
            route_rationale="Test rationale",
            recommended_route=Route.APPDEVELOPER,
        )
        package = PlanPackage(
            session_id=uuid.uuid4(),
            plan_version=1,
            created_at=datetime.now(UTC),
            approved_at=datetime.now(UTC),
            proposal=proposal,
            handoff_route=Route.APPDEVELOPER,
        )
        data = package.model_dump()
        assert data["schema_version"] == "1.0"
        assert data["plan_version"] == 1

    def test_handoff_receipt_defaults(self) -> None:
        from app.domain.enums import Route
        from app.domain.schemas import HandoffReceipt

        receipt = HandoffReceipt(
            route=Route.APPDEVELOPER,
            idempotency_key=uuid.uuid4(),
        )
        assert receipt.downstream_id == ""
        assert receipt.attempt_count == 0

    def test_planner_output_validation_extra_fields(self) -> None:
        from pydantic import ValidationError

        from app.domain.schemas import PlannerOutput

        with pytest.raises(ValidationError):
            PlannerOutput(
                assistant_message="test",
                unknown_field="should fail",
            )

    def test_session_create_min_length(self) -> None:
        from pydantic import ValidationError

        from app.domain.schemas import SessionCreate

        with pytest.raises(ValidationError):
            SessionCreate(initial_message="")

    def test_follow_up_question_types(self) -> None:
        from app.domain.enums import AnswerType
        from app.domain.schemas import FollowUpQuestion

        for answer_type in AnswerType:
            q = FollowUpQuestion(
                id=f"q-{answer_type.value}",
                question="Test",
                why_it_matters="Test",
                answer_type=answer_type,
            )
            assert q.answer_type == answer_type


class TestEventBroadcasterExtended:
    def test_history_max_size(self) -> None:
        import asyncio

        from app.services.event_service import EventBroadcaster

        broadcaster = EventBroadcaster()
        broadcaster._max_history = 3

        for i in range(5):
            asyncio.get_event_loop().run_until_complete(
                broadcaster.publish("s1", "event", {"i": i})
            )

        history = broadcaster.get_history_after("s1", 0)
        assert len(history) == 3

    def test_publish_to_session_with_no_subscribers(self) -> None:
        import asyncio

        from app.services.event_service import EventBroadcaster

        broadcaster = EventBroadcaster()
        asyncio.get_event_loop().run_until_complete(
            broadcaster.publish("s1", "event", {"data": "test"})
        )
        history = broadcaster.get_history_after("s1", 0)
        assert len(history) == 1


class TestRateLimiter:
    def test_rate_limiter_creation(self) -> None:
        from app.security.rate_limit import RateLimiter

        limiter = RateLimiter()
        assert limiter._redis is None
