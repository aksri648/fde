"""Request body size limits and validation."""

from __future__ import annotations

from fastapi import HTTPException, Request, status

from app.config import settings


async def enforce_request_size_limit(request: Request) -> None:
    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > settings.request_max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Request body too large, max {settings.request_max_bytes} bytes",
        )
