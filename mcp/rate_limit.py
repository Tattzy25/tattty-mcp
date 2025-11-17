"""Simple in-memory IP based rate limiter."""
from __future__ import annotations

import asyncio
import time
from collections import defaultdict, deque
from typing import Deque, Dict

from fastapi import HTTPException, status


class RateLimiter:
    def __init__(self, window_seconds: int = 60) -> None:
        self._window = window_seconds
        self._lock = asyncio.Lock()
        self._hits: Dict[str, Deque[float]] = defaultdict(deque)

    async def check(self, key: str, limit: int | None) -> None:
        if limit is None or limit <= 0:
            return

        now = time.time()
        async with self._lock:
            bucket = self._hits[key]
            while bucket and now - bucket[0] > self._window:
                bucket.popleft()

            if len(bucket) >= limit:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Rate limit exceeded",
                )

            bucket.append(now)
