from __future__ import annotations

import time
from collections import defaultdict
from typing import Callable

from fastapi import Request, Response, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint


class RateLimitConfig:
    def __init__(
        self,
        requests_per_minute: int = 60,
        requests_per_hour: int = 1000,
        burst_size: int = 10,
    ):
        self.requests_per_minute = requests_per_minute
        self.requests_per_hour = requests_per_hour
        self.burst_size = burst_size


DEFAULT_CONFIG = RateLimitConfig()


class RateLimiter:
    def __init__(self):
        self._windows: dict[str, list[float]] = defaultdict(list)
        self._configs: dict[str, RateLimitConfig] = {}

    def set_config(self, tenant_id: str, config: RateLimitConfig):
        self._configs[tenant_id] = config

    def get_config(self, tenant_id: str) -> RateLimitConfig:
        return self._configs.get(tenant_id, DEFAULT_CONFIG)

    def check_rate_limit(self, tenant_id: str) -> tuple[bool, dict]:
        config = self.get_config(tenant_id)
        now = time.time()
        window = self._windows[tenant_id]

        window = [t for t in window if now - t < 3600]
        self._windows[tenant_id] = window

        minute_count = sum(1 for t in window if now - t < 60)
        hour_count = len(window)

        if minute_count >= config.requests_per_minute:
            retry_after = 60 - (now - window[-(config.requests_per_minute)])
            return False, {
                "error": "Rate limit exceeded (per minute)",
                "retry_after": int(retry_after),
                "limit": config.requests_per_minute,
                "remaining": 0,
            }

        if hour_count >= config.requests_per_hour:
            retry_after = 3600 - (now - window[0])
            return False, {
                "error": "Rate limit exceeded (per hour)",
                "retry_after": int(retry_after),
                "limit": config.requests_per_hour,
                "remaining": 0,
            }

        self._windows[tenant_id].append(now)

        return True, {
            "limit": config.requests_per_minute,
            "remaining": config.requests_per_minute - minute_count - 1,
            "reset": int(60 - (now - (window[-1] if window else now))),
        }


rate_limiter = RateLimiter()


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, get_tenant_id: Callable | None = None):
        super().__init__(app)
        self.get_tenant_id = get_tenant_id or self._default_get_tenant

    def _default_get_tenant(self, request: Request) -> str:
        return request.headers.get("X-Tenant-ID", "default")

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        tenant_id = self.get_tenant_id(request)

        allowed, info = rate_limiter.check_rate_limit(tenant_id)

        if not allowed:
            return Response(
                content=f'{{"error": "{info["error"]}", "retry_after": {info["retry_after"]}}}',
                status_code=429,
                headers={
                    "Content-Type": "application/json",
                    "X-RateLimit-Limit": str(info["limit"]),
                    "X-RateLimit-Remaining": "0",
                    "Retry-After": str(info["retry_after"]),
                },
            )

        response = await call_next(request)

        response.headers["X-RateLimit-Limit"] = str(info["limit"])
        response.headers["X-RateLimit-Remaining"] = str(info["remaining"])
        response.headers["X-RateLimit-Reset"] = str(info["reset"])

        return response
