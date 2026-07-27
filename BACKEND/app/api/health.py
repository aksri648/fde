"""Health and readiness check endpoints."""

from __future__ import annotations

from typing import Any

import httpx
from fastapi import APIRouter

from app.config import settings

router = APIRouter(tags=["health"])


@router.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/readyz")
async def readyz() -> dict[str, Any]:
    checks: dict[str, Any] = {}

    try:
        from app.db.session import engine

        async with engine.connect() as conn:
            await conn.execute(__import__("sqlalchemy").text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as e:
        checks["database"] = f"error: {type(e).__name__}"

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{settings.litellm_proxy_url}/health")
            checks["litellm"] = "ok" if resp.status_code == 200 else f"error: {resp.status_code}"
    except Exception as e:
        checks["litellm"] = f"error: {type(e).__name__}"

    all_ok = all(v == "ok" for v in checks.values())
    return {"status": "ok" if all_ok else "degraded", "checks": checks}
