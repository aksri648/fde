"""Server-owned citation catalog for official documentation links."""

from __future__ import annotations

from app.domain.schemas import DocumentationCitation

CITATION_CATALOG: dict[str, DocumentationCitation] = {
    "claude_agent_sdk": DocumentationCitation(
        id="claude_agent_sdk",
        title="Claude Agent SDK Overview",
        url="https://platform.claude.com/docs/en/agent-sdk/overview",
    ),
    "litellm_proxy": DocumentationCitation(
        id="litellm_proxy",
        title="LiteLLM Proxy Documentation",
        url="https://docs.litellm.ai/docs/proxy/quick_start",
    ),
    "openai_agents_sdk": DocumentationCitation(
        id="openai_agents_sdk",
        title="OpenAI Agents SDK",
        url="https://openai.github.io/openai-agents-python/",
    ),
    "openai_responses_api": DocumentationCitation(
        id="openai_responses_api",
        title="OpenAI Responses API",
        url="https://developers.openai.com/api/docs/guides/conversation-state",
    ),
    "langgraph_overview": DocumentationCitation(
        id="langgraph_overview",
        title="LangGraph Overview",
        url="https://docs.langchain.com/oss/python/langgraph/overview",
    ),
    "langgraph_hitl": DocumentationCitation(
        id="langgraph_hitl",
        title="LangGraph Human-in-the-Loop",
        url="https://docs.langchain.com/oss/python/langchain/human-in-the-loop",
    ),
    "fastapi": DocumentationCitation(
        id="fastapi",
        title="FastAPI Documentation",
        url="https://fastapi.tiangolo.com/",
    ),
    "owasp_prompt_injection": DocumentationCitation(
        id="owasp_prompt_injection",
        title="OWASP Prompt Injection Prevention",
        url="https://genai.owasp.org/llmrisk/llm01-prompt-injection/",
    ),
}


def resolve_citations(citation_ids: list[str]) -> list[DocumentationCitation]:
    resolved = []
    for cid in citation_ids:
        if cid in CITATION_CATALOG:
            resolved.append(CITATION_CATALOG[cid])
    return resolved


def validate_citation_ids(citation_ids: list[str]) -> list[str]:
    invalid = [cid for cid in citation_ids if cid not in CITATION_CATALOG]
    if invalid:
        raise ValueError(f"Invalid citation IDs: {invalid}")
    return citation_ids
