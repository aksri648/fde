"""LiteLLM health client for readiness checks."""

from __future__ import annotations

import httpx
import structlog

from app.config import settings

logger = structlog.get_logger(__name__)


class LitellmHealthClient:
    def __init__(self) -> None:
        self._base_url = settings.litellm_proxy_url

    async def check_health(self) -> dict[str, str | bool]:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self._base_url}/health")
                if response.status_code == 200:
                    return {"status": "ok", "healthy": True}
                return {"status": "error", "healthy": False}
        except Exception as e:
            logger.error("litellm_health_check_failed", error=str(e))
            return {"status": "error", "healthy": False}
