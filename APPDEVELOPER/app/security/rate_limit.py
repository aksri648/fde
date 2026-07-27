import asyncio
import time
from collections import defaultdict


class RateLimiter:
    def __init__(self, max_requests: int = 10, window_seconds: int = 60) -> None:
        self._max_requests = max_requests
        self._window_seconds = window_seconds
        self._requests: dict[str, list[float]] = defaultdict(list)
        self._lock = asyncio.Lock()

    async def check(self, key: str) -> bool:
        async with self._lock:
            now = time.time()
            cutoff = now - self._window_seconds
            self._requests[key] = [t for t in self._requests[key] if t > cutoff]

            if len(self._requests[key]) >= self._max_requests:
                return False

            self._requests[key].append(now)
            return True

    async def get_remaining(self, key: str) -> int:
        async with self._lock:
            now = time.time()
            cutoff = now - self._window_seconds
            self._requests[key] = [t for t in self._requests[key] if t > cutoff]
            return max(0, self._max_requests - len(self._requests[key]))
