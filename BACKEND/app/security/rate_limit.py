"""Per-tenant rate limiting using Redis."""

from __future__ import annotations

import time

import redis.asyncio as redis
from fastapi import HTTPException, Request, status

from app.config import settings


class RateLimiter:
    def __init__(self) -> None:
        self._redis: redis.Redis | None = None

    async def _get_redis(self) -> redis.Redis:
        if self._redis is None:
            self._redis = redis.from_url(  # type: ignore[no-untyped-call]
                settings.redis_url, decode_responses=True
            )
        return self._redis

    async def check_rate_limit(
        self,
        tenant_id: str,
        max_requests: int = 100,
        window_seconds: int = 60,
    ) -> bool:
        try:
            r = await self._get_redis()
            key = f"{settings.redis_rate_limit_key_prefix}{tenant_id}"
            now = time.time()
            window_start = now - window_seconds

            pipe = r.pipeline()
            pipe.zremrangebyscore(key, 0, window_start)
            pipe.zadd(key, {str(now): now})
            pipe.zcard(key)
            pipe.expire(key, window_seconds)
            results = await pipe.execute()

            request_count: int = results[2]
            return request_count <= max_requests
        except redis.ConnectionError:
            return True


rate_limiter = RateLimiter()


async def enforce_rate_limit(request: Request, tenant_id: str = "default") -> None:
    allowed = await rate_limiter.check_rate_limit(tenant_id)
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded",
        )
