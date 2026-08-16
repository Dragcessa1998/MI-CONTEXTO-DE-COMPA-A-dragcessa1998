"""Rate limiting local y verificable para endpoints que invocan modelos."""

from __future__ import annotations

import os
import time
from collections import defaultdict, deque
from threading import Lock

from fastapi import Depends, HTTPException, Request, status

from auth_models import UserRecord
from security import get_current_user


class SlidingWindowRateLimiter:
    def __init__(self, max_requests: int, window_seconds: int) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._requests: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def check(self, key: str, *, now: float | None = None) -> None:
        timestamp = time.monotonic() if now is None else now
        with self._lock:
            bucket = self._requests[key]
            cutoff = timestamp - self.window_seconds
            while bucket and bucket[0] <= cutoff:
                bucket.popleft()
            if len(bucket) >= self.max_requests:
                retry_after = max(1, int(self.window_seconds - (timestamp - bucket[0])))
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Límite temporal de consultas al modelo alcanzado.",
                    headers={"Retry-After": str(retry_after)},
                )
            bucket.append(timestamp)

    def reset(self) -> None:
        with self._lock:
            self._requests.clear()


model_rate_limiter = SlidingWindowRateLimiter(
    max_requests=int(os.getenv("MODEL_RATE_LIMIT_REQUESTS", "10")),
    window_seconds=int(os.getenv("MODEL_RATE_LIMIT_WINDOW_SECONDS", "60")),
)


def enforce_model_rate_limit(
    request: Request,
    current_user: UserRecord = Depends(get_current_user),
) -> None:
    model_rate_limiter.check(f"{current_user.id}:{request.url.path}")


__all__ = ["SlidingWindowRateLimiter", "enforce_model_rate_limit", "model_rate_limiter"]
