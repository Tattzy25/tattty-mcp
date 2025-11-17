"""Runtime metrics collection utilities."""
from __future__ import annotations

import asyncio
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Deque, Dict, List


@dataclass
class RequestRecord:
    path: str
    method: str
    status: int
    duration_ms: float
    timestamp: float


class MetricsCollector:
    """Thread-safe structure tracking request counts and latency."""

    def __init__(self, window: int = 60, max_entries: int = 200) -> None:
        self._lock = asyncio.Lock()
        self._window = window
        self._max_entries = max_entries
        self._start_time = time.time()
        self._total_requests = 0
        self._total_errors = 0
        self._per_path: Dict[str, int] = defaultdict(int)
        self._records: Deque[RequestRecord] = deque(maxlen=max_entries)

    async def record(self, path: str, method: str, status: int, duration_ms: float) -> None:
        async with self._lock:
            self._total_requests += 1
            if status >= 500:
                self._total_errors += 1
            self._per_path[path] += 1
            self._records.append(
                RequestRecord(
                    path=path,
                    method=method,
                    status=status,
                    duration_ms=round(duration_ms, 2),
                    timestamp=time.time(),
                )
            )

    async def snapshot(self) -> Dict[str, object]:
        async with self._lock:
            per_path = dict(self._per_path)
            records: List[dict] = [
                {
                    "path": record.path,
                    "method": record.method,
                    "status": record.status,
                    "duration_ms": record.duration_ms,
                    "timestamp": record.timestamp,
                }
                for record in list(self._records)
            ]

        uptime = time.time() - self._start_time
        return {
            "uptime_seconds": round(uptime, 2),
            "total_requests": self._total_requests,
            "total_errors": self._total_errors,
            "per_path_counts": per_path,
            "recent_requests": records[-50:],
        }
