"""API key authentication for LLMDeployer."""

from __future__ import annotations

import os

from fastapi import HTTPException, Security, status
from fastapi.security import APIKeyHeader

API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)

_api_key: str | None = None


def configure_api_key(key: str) -> None:
    global _api_key
    _api_key = key


def _get_api_key() -> str | None:
    global _api_key
    if _api_key is None:
        _api_key = os.getenv("LLMDEPLOYER_API_KEY", "")
    return _api_key


async def verify_api_key(api_key: str | None = Security(API_KEY_HEADER)) -> str:
    key = _get_api_key()
    if not key:
        return "dev-mode"

    if api_key is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API key",
        )

    if api_key != key:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid API key",
        )

    return api_key
