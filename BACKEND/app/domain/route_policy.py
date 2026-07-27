"""Deterministic downstream routing policy."""

from __future__ import annotations

from app.domain.enums import Route, SolutionType


class RoutePolicyError(Exception):
    pass


def validate_route(
    recommended_route: Route,
    solution_type: SolutionType,
    explanation: str,
) -> Route:
    if recommended_route == Route.AMBIGUOUS:
        return Route.AMBIGUOUS

    if recommended_route not in (Route.APPDEVELOPER, Route.LLMDEPLOYER):
        raise RoutePolicyError(f"Invalid route: {recommended_route}")

    if recommended_route == Route.APPDEVELOPER:
        deploy_keywords = {
            "model serving",
            "inference",
            "gpu",
            "endpoint hosting",
            "autoscaling",
            "vllm",
            "nim",
            "serverless deployment",
            "llm gateway",
        }
        lower_explanation = explanation.lower()
        has_deploy_keywords = any(kw in lower_explanation for kw in deploy_keywords)
        has_build_keywords = any(
            kw in lower_explanation
            for kw in {
                "application",
                "backend",
                "frontend",
                "integration",
                "rag",
                "chatbot",
                "agent",
                "code",
            }
        )
        if has_deploy_keywords and not has_build_keywords:
            raise RoutePolicyError(
                "Route APPDEVELOPER selected but explanation suggests LLMDEPLOYER"
            )

    if recommended_route == Route.LLMDEPLOYER:
        build_keywords = {
            "application",
            "backend",
            "frontend",
            "rag",
            "chatbot",
            "langgraph",
            "openai agents",
            "tool-using",
        }
        lower_explanation = explanation.lower()
        has_build_keywords = any(kw in lower_explanation for kw in build_keywords)
        if has_build_keywords:
            return Route.AMBIGUOUS

    return recommended_route
