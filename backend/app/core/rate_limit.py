"""Minimal in-process abuse protection for the expensive public endpoints.

Single VPS, single process: a sliding window per (bucket, identity) is enough to
stop an anonymous visitor from looping registration, coaching, SP chat, case
generation or scoring against a paid model. It is deliberately not a distributed
limiter; ARCH.md records when it would need to be replaced.
"""

import os
import threading
import time
from collections import deque

from fastapi import HTTPException, Request, status

DEFAULT_LIMITS = {
    "register": (3, 3600),
    "login": (60, 3600),
    "coach": (80, 3600),
    "sp_message": (80, 3600),
    "submit": (40, 3600),
    "case_generate": (20, 3600),
    "ai_probe": (30, 3600),
}


def _limit(bucket: str) -> tuple[int, int]:
    limit, window = DEFAULT_LIMITS[bucket]
    configured = os.getenv(f"RATE_LIMIT_{bucket.upper()}_PER_HOUR")
    if configured:
        try:
            limit = int(configured)
        except ValueError:
            pass
    return limit, window


class SlidingWindowLimiter:
    def __init__(self, max_keys: int = 10_000) -> None:
        self._lock = threading.Lock()
        self._hits: dict[tuple[str, str], deque] = {}
        self._max_keys = max_keys

    def hit(self, bucket: str, identity: str) -> tuple[bool, int]:
        limit, window_seconds = _limit(bucket)
        now = time.monotonic()
        key = (bucket, identity)
        with self._lock:
            hits = self._hits.setdefault(key, deque())
            while hits and now - hits[0] > window_seconds:
                hits.popleft()
            if len(hits) >= limit:
                retry_after = max(1, int(window_seconds - (now - hits[0])))
                return False, retry_after
            hits.append(now)
            if len(self._hits) > self._max_keys:
                self._prune(now, window_seconds)
            return True, 0

    def _prune(self, now: float, window_seconds: int) -> None:
        stale = [key for key, hits in self._hits.items() if not hits or now - hits[-1] > window_seconds]
        for key in stale:
            self._hits.pop(key, None)


limiter = SlidingWindowLimiter()


def client_identity(request: Request) -> str:
    forwarded = (request.headers.get("x-forwarded-for") or "").split(",")[0].strip()
    if forwarded:
        return forwarded
    return request.client.host if request.client else "unknown"


def enforce(bucket: str, identity: str) -> None:
    allowed, retry_after = limiter.hit(bucket, identity)
    if allowed:
        return
    raise HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail=f"Too many requests for {bucket}. Retry later.",
        headers={"Retry-After": str(retry_after)},
    )
