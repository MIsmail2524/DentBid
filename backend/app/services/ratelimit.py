"""Small in-process sliding-window rate limiter.

Good for a single API process. With several workers or servers, back it with Redis.
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request

from ..config import get_settings


class SlidingWindow:
    def __init__(self) -> None:
        self.hits: dict[str, deque[float]] = defaultdict(deque)
        self.lock = threading.Lock()

    def hit(self, key: str, limit: int, window_s: float) -> tuple[bool, float]:
        """Records a hit. Returns (allowed, retry_after_seconds)."""
        now = time.monotonic()
        with self.lock:
            q = self.hits[key]
            while q and q[0] <= now - window_s:
                q.popleft()
            if len(q) >= limit:
                return False, q[0] + window_s - now
            q.append(now)
            if len(self.hits) > 50_000:  # bound memory under key-spraying
                for k in [k for k, v in self.hits.items() if not v][:10_000]:
                    del self.hits[k]
            return True, 0.0

    def reset(self) -> None:
        with self.lock:
            self.hits.clear()


limiter = SlidingWindow()


def client_ip(request: Request) -> str:
    # uvicorn --proxy-headers already resolves X-Forwarded-For from trusted proxies
    return request.client.host if request.client else "unknown"


def check(key: str, limit: int, window_s: float) -> None:
    ok, retry = limiter.hit(key, limit, window_s)
    if not ok:
        raise HTTPException(429, "Too many attempts, try again later", headers={"Retry-After": str(int(retry) + 1)})


def login_guard(request: Request, email: str) -> None:
    s = get_settings()
    check(f"login:{client_ip(request)}:{email.lower()}", s.login_attempts_per_15min, 900)
    check(f"login-ip:{client_ip(request)}", s.login_attempts_per_15min * 5, 900)


def register_guard(request: Request) -> None:
    check(f"register:{client_ip(request)}", 10, 3600)
