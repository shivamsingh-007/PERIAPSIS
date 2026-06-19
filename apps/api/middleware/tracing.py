from __future__ import annotations

import os
import time
from typing import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class TracingMiddleware(BaseHTTPMiddleware):
    """Middleware that wraps every request with a Langfuse trace when enabled."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start_time = time.time()

        trace_id = None
        langfuse_client = getattr(request.app.state, "langfuse_client", None)

        if langfuse_client:
            trace = langfuse_client.trace(
                name=f"{request.method} {request.url.path}",
                metadata={
                    "method": request.method,
                    "path": request.url.path,
                    "query": str(request.query_params),
                },
            )
            trace_id = trace.id
            request.state.trace_id = trace_id
            request.state.langfuse = langfuse_client

        response = await call_next(request)

        latency_ms = int((time.time() - start_time) * 1000)
        response.headers["X-Latency-Ms"] = str(latency_ms)

        if langfuse_client and trace_id:
            langfuse_client.trace(
                id=trace_id,
                metadata={
                    "status_code": response.status_code,
                    "latency_ms": latency_ms,
                },
            )

        return response


def setup_langfuse(app) -> None:
    """Initialize Langfuse client and attach to app state."""
    public_key = os.getenv("LANGFUSE_PUBLIC_KEY")
    secret_key = os.getenv("LANGFUSE_SECRET_KEY")
    host = os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com")
    enabled = os.getenv("LANGFUSE_ENABLED", "false").lower() == "true"

    if not enabled or not public_key or not secret_key:
        app.state.langfuse_client = None
        return

    try:
        from langfuse import Langfuse

        client = Langfuse(public_key=public_key, secret_key=secret_key, host=host)
        app.state.langfuse_client = client
    except Exception:
        app.state.langfuse_client = None
