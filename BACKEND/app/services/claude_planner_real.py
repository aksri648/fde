"""Real planner adapter using the Anthropic Messages API.

The client speaks the Anthropic wire format (``/v1/messages`` with an
``x-api-key`` header), but the destination is configurable via
``ANTHROPIC_BASE_URL``. Point it at the LiteLLM proxy — which exposes an
Anthropic-compatible ``/v1/messages`` endpoint and translates to your
OpenAI-compatible backend — and the planner transparently runs on that model
while still "thinking" it is talking to Claude.
"""

from __future__ import annotations

import json

import httpx
import structlog

from app.config import settings
from app.domain.schemas import PlannerOutput
from app.services.planner_prompt import PLANNER_SYSTEM_PROMPT

logger = structlog.get_logger(__name__)


class ClaudePlannerAdapter:
    """Planner using the Anthropic Messages API (routable to a LiteLLM proxy)."""

    def __init__(self) -> None:
        self._client: httpx.AsyncClient | None = None
        self._base_url = settings.anthropic_base_url.rstrip("/")
        self._api_key = settings.anthropic_api_key
        self._model = settings.fde_claude_model
        self._timeout = settings.claude_agent_sdk_timeout_seconds

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self._base_url,
                headers={
                    "x-api-key": self._api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                timeout=httpx.Timeout(self._timeout),
            )
        return self._client

    async def plan(
        self,
        conversation_history: list[dict[str, str]],
        facts: list[str],
        current_state: str,
        plan_version: int,
    ) -> PlannerOutput:
        messages = self._build_messages(
            conversation_history, facts, current_state, plan_version
        )

        client = await self._get_client()

        try:
            response = await client.post(
                "/v1/messages",
                json={
                    "model": self._model,
                    "max_tokens": 8192,
                    "system": PLANNER_SYSTEM_PROMPT,
                    "messages": messages,
                },
            )
            response.raise_for_status()

            data = response.json()
            content = data.get("content", [])
            text = ""
            for block in content:
                if block.get("type") == "text":
                    text = block.get("text", "")
                    break

            if not text:
                raise ValueError("No text content in response")

            parsed = json.loads(text)
            return PlannerOutput(**parsed)

        except json.JSONDecodeError as e:
            logger.error("planner_json_parse_error", error=str(e))
            return await self._repair_json(text if "text" in dir() else "", str(e))

        except httpx.HTTPStatusError as e:
            logger.error(
                "planner_http_error", status=e.response.status_code, error=str(e)
            )
            raise

        except Exception as e:
            logger.error("planner_error", error=str(e))
            raise

    async def _repair_json(self, text: str, original_error: str) -> PlannerOutput:
        """Attempt one repair of invalid JSON output."""
        client = await self._get_client()

        repair_prompt = (
            f"The previous response was not valid JSON. Error: {original_error}\n"
            f"Previous response:\n{text}\n\n"
            "Please output ONLY a valid JSON object matching the PlannerOutput schema. "
            "No markdown fences, no commentary."
        )

        try:
            response = await client.post(
                "/v1/messages",
                json={
                    "model": self._model,
                    "max_tokens": 8192,
                    "system": PLANNER_SYSTEM_PROMPT,
                    "messages": [{"role": "user", "content": repair_prompt}],
                },
            )
            response.raise_for_status()

            data = response.json()
            content = data.get("content", [])
            repaired_text = ""
            for block in content:
                if block.get("type") == "text":
                    repaired_text = block.get("text", "")
                    break

            parsed = json.loads(repaired_text)
            return PlannerOutput(**parsed)

        except Exception:
            logger.error("planner_repair_failed")
            return PlannerOutput(
                assistant_message="I encountered an error processing your request. Please try again.",
                facts_learned=[],
                questions=[],
                proposal=None,
                needs_more_information=True,
                requires_human_approval=False,
                safe_to_handoff=False,
            )

    def _build_messages(
        self,
        conversation_history: list[dict[str, str]],
        facts: list[str],
        current_state: str,
        plan_version: int,
    ) -> list[dict[str, str]]:
        messages = []

        context_msg = (
            f"Current session state: {current_state}\n"
            f"Current plan version: {plan_version}\n"
            f"Accumulated facts: {json.dumps(facts)}\n\n"
            "Based on the conversation below, produce your PlannerOutput JSON response."
        )
        messages.append({"role": "user", "content": context_msg})

        for turn in conversation_history:
            messages.append(
                {
                    "role": turn["role"],
                    "content": turn["content"],
                }
            )

        return messages
