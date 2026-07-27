"""Unit tests for domain logic."""

from __future__ import annotations

import pytest

from app.domain.enums import (
    SessionState,
    validate_transition,
)
from app.domain.route_policy import validate_route
from app.domain.schemas import (
    ArchitectureProposal,
    FollowUpQuestion,
    PlannerOutput,
)
from app.domain.transitions import InvalidTransitionError, enforce_transition


class TestSessionStateTransitions:
    def test_valid_transition_discovering_to_awaiting_answers(self) -> None:
        assert validate_transition(SessionState.DISCOVERING, SessionState.AWAITING_ANSWERS)

    def test_valid_transition_discovering_to_awaiting_approval(self) -> None:
        assert validate_transition(SessionState.DISCOVERING, SessionState.AWAITING_APPROVAL)

    def test_valid_transition_discovering_to_failed(self) -> None:
        assert validate_transition(SessionState.DISCOVERING, SessionState.FAILED)

    def test_valid_transition_discovering_to_cancelled(self) -> None:
        assert validate_transition(SessionState.DISCOVERING, SessionState.CANCELLED)

    def test_invalid_transition_handed_off_to_anything(self) -> None:
        for target in SessionState:
            if target != SessionState.HANDED_OFF:
                assert not validate_transition(SessionState.HANDED_OFF, target)

    def test_invalid_transition_cancelled_to_anything(self) -> None:
        for target in SessionState:
            if target != SessionState.CANCELLED:
                assert not validate_transition(SessionState.CANCELLED, target)

    def test_enforce_transition_valid(self) -> None:
        enforce_transition(SessionState.DISCOVERING, SessionState.AWAITING_ANSWERS)

    def test_enforce_transition_invalid(self) -> None:
        with pytest.raises(InvalidTransitionError):
            enforce_transition(SessionState.HANDED_OFF, SessionState.DISCOVERING)


class TestRoutePolicy:
    def test_valid_appdeveloper_route(self) -> None:
        from app.domain.enums import Route, SolutionType

        route = validate_route(
            Route.APPDEVELOPER,
            SolutionType.RAG,
            "This requires building a RAG application",
        )
        assert route == Route.APPDEVELOPER

    def test_valid_llmdeployer_route(self) -> None:
        from app.domain.enums import Route, SolutionType

        route = validate_route(
            Route.LLMDEPLOYER,
            SolutionType.NO_AI_OR_DETERMINISTIC_AUTOMATION,
            "This requires model serving and inference optimization",
        )
        assert route == Route.LLMDEPLOYER

    def test_ambiguous_route(self) -> None:
        from app.domain.enums import Route, SolutionType

        route = validate_route(
            Route.AMBIGUOUS,
            SolutionType.TOOL_USING_AGENT,
            "Need both application development and deployment",
        )
        assert route == Route.AMBIGUOUS


class TestPlannerOutputValidation:
    def test_valid_planner_output(self) -> None:
        output = PlannerOutput(
            assistant_message="Test message",
            facts_learned=["fact1"],
            questions=[],
            proposal=None,
            needs_more_information=True,
            requires_human_approval=False,
            safe_to_handoff=False,
        )
        assert output.assistant_message == "Test message"
        assert output.needs_more_information is True

    def test_planner_output_with_proposal(self) -> None:
        from app.domain.enums import Route, SolutionType

        proposal = ArchitectureProposal(
            title="Test",
            business_problem="Test problem",
            recommended_solution_type=SolutionType.CHATBOT,
            route_rationale="Test rationale",
            recommended_route=Route.APPDEVELOPER,
        )
        output = PlannerOutput(
            assistant_message="Test",
            facts_learned=[],
            questions=[],
            proposal=proposal,
            needs_more_information=False,
            requires_human_approval=True,
            safe_to_handoff=True,
        )
        assert output.proposal is not None
        assert output.requires_human_approval is True


class TestFollowUpQuestion:
    def test_valid_question(self) -> None:
        question = FollowUpQuestion(
            id="q1",
            question="What is your budget?",
            why_it_matters="Budget determines architecture options",
            required=True,
        )
        assert question.id == "q1"
        assert question.required is True

    def test_question_with_options(self) -> None:
        from app.domain.enums import AnswerType
        from app.domain.schemas import FollowUpQuestionOption

        question = FollowUpQuestion(
            id="q2",
            question="Select your priority",
            why_it_matters="Priority affects design",
            answer_type=AnswerType.SINGLE_SELECT,
            options=[
                FollowUpQuestionOption(label="Performance", value="performance"),
                FollowUpQuestionOption(label="Cost", value="cost"),
            ],
        )
        assert len(question.options) == 2
