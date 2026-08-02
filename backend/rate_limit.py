"""Small in-process rate limiter for public authentication/join endpoints.

The project intentionally keeps a single backend worker in the default
deployment.  This limiter therefore provides useful brute-force protection
without introducing another service.  A distributed deployment should move
the counters to Redis (and keep the same call sites).
"""
from __future__ import annotations

import os
import threading
import time
from collections import defaultdict, deque
from typing import Deque, Dict

from fastapi import HTTPException, Request, status


class SlidingWindowRateLimiter:
    def __init__(self) -> None:
        self._events: Dict[str, Deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def check(self, key: str, limit: int, window_sec: float) -> None:
        now = time.monotonic()
        cutoff = now - window_sec
        with self._lock:
            events = self._events[key]
            while events and events[0] <= cutoff:
                events.popleft()
            if len(events) >= limit:
                retry_after = max(1, int(window_sec - (now - events[0])))
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Qua nhieu yeu cau. Vui long thu lai sau.",
                    headers={"Retry-After": str(retry_after)},
                )
            events.append(now)

    def reset(self) -> None:
        """Clear counters (used by isolated tests)."""
        with self._lock:
            self._events.clear()


limiter = SlidingWindowRateLimiter()


def _positive_env_int(name: str, default: int) -> int:
    try:
        value = int(os.environ.get(name, str(default)))
    except ValueError:
        return default
    return value if value > 0 else default


def enforce_rate_limit(
    request: Request,
    bucket: str,
    identity: str = "",
    *,
    limit: int,
    window_sec: float = 60.0,
) -> None:
    client_host = request.client.host if request.client is not None else "unknown"
    normalized_identity = identity.strip().casefold()[:255]
    limiter.check(f"{bucket}:{client_host}:{normalized_identity}", limit, window_sec)


PUBLIC_IP_LIMIT_PER_MINUTE = _positive_env_int("PUBLIC_IP_LIMIT_PER_MINUTE", 120)
LOGIN_ACCOUNT_LIMIT_PER_MINUTE = _positive_env_int("LOGIN_ACCOUNT_LIMIT_PER_MINUTE", 10)
JOIN_CODE_LIMIT_PER_MINUTE = _positive_env_int("JOIN_CODE_LIMIT_PER_MINUTE", 30)
