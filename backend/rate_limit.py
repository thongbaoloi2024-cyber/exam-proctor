"""Sliding/fixed-window rate limiting for public authentication endpoints.

Development uses an in-process sliding window. When ``REDIS_URL`` is set,
workers share fixed-window counters in Redis and fail closed if Redis is down.
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
        self._redis_url = os.environ.get("REDIS_URL", "").strip()
        self._redis = None

    def _redis_client(self):
        if self._redis is None:
            try:
                import redis
            except ImportError as exc:
                raise RuntimeError("REDIS_URL da dat nhung chua cai package redis") from exc
            self._redis = redis.Redis.from_url(
                self._redis_url,
                decode_responses=True,
                socket_connect_timeout=2,
                socket_timeout=2,
            )
        return self._redis

    def _check_redis(self, key: str, limit: int, window_sec: float) -> None:
        now = time.time()
        window = max(1, int(window_sec))
        bucket = int(now // window)
        redis_key = f"datt:rate:{bucket}:{key}"
        try:
            client = self._redis_client()
            with client.pipeline(transaction=True) as pipeline:
                pipeline.incr(redis_key)
                pipeline.expire(redis_key, window + 2)
                count, _ = pipeline.execute()
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Dich vu bao ve tan suat tam thoi khong san sang",
            ) from exc
        if int(count) > limit:
            retry_after = max(1, window - int(now % window))
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Qua nhieu yeu cau. Vui long thu lai sau.",
                headers={"Retry-After": str(retry_after)},
            )

    def check(self, key: str, limit: int, window_sec: float) -> None:
        if self._redis_url:
            self._check_redis(key, limit, window_sec)
            return
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
