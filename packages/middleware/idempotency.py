from __future__ import annotations

import hashlib
import json
import time
import uuid
from typing import Any

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from sqlalchemy import text

from packages.schemas.database import get_session


class IdempotencyMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, header_name: str = "Idempotency-Key", ttl_seconds: int = 86400):
        super().__init__(app)
        self.header_name = header_name
        self.ttl_seconds = ttl_seconds
        self._write_methods = {"POST", "PUT", "PATCH", "DELETE"}

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if request.method not in self._write_methods:
            return await call_next(request)

        idempotency_key = request.headers.get(self.header_name)
        if not idempotency_key:
            idempotency_key = str(uuid.uuid4())

        body = await request.body()
        content_hash = hashlib.sha256(
            f"{request.method}:{request.url.path}:{body.decode()}".encode()
        ).hexdigest()

        cached = await self._get_cached_response(idempotency_key, content_hash)
        if cached:
            return Response(
                content=cached["response_body"],
                status_code=cached["status_code"],
                headers={"X-Idempotent-Replay": "true"},
            )

        response = await call_next(request)

        if response.status_code < 400:
            response_body = b""
            async for chunk in response.body_iterator:
                if isinstance(chunk, str):
                    response_body += chunk.encode()
                else:
                    response_body += chunk

            await self._cache_response(
                idempotency_key,
                content_hash,
                response.status_code,
                response_body,
            )

            return Response(
                content=response_body,
                status_code=response.status_code,
                headers=dict(response.headers),
            )

        return response

    async def _get_cached_response(self, key: str, content_hash: str) -> dict | None:
        async with get_session() as session:
            result = await session.execute(
                text(
                    """
                    SELECT response_body, status_code FROM idempotency_cache
                    WHERE idempotency_key = :key AND content_hash = :hash
                      AND expires_at > NOW()
                    """
                ),
                {"key": key, "hash": content_hash},
            )
            row = result.mappings().first()
            return dict(row) if row else None

    async def _cache_response(
        self,
        key: str,
        content_hash: str,
        status_code: int,
        response_body: bytes,
    ) -> None:
        from datetime import datetime, timedelta
        expires_at = datetime.utcnow() + timedelta(seconds=self.ttl_seconds)

        async with get_session() as session:
            await session.execute(
                text(
                    """
                    INSERT INTO idempotency_cache (idempotency_key, content_hash, response_body, status_code, expires_at, created_at)
                    VALUES (:key, :hash, :body, :status, :expires, NOW())
                    ON CONFLICT (idempotency_key) DO UPDATE SET
                        content_hash = EXCLUDED.content_hash,
                        response_body = EXCLUDED.response_body,
                        status_code = EXCLUDED.status_code,
                        expires_at = EXCLUDED.expires_at
                    """
                ),
                {
                    "key": key,
                    "hash": content_hash,
                    "body": response_body,
                    "status": status_code,
                    "expires": expires_at,
                },
            )
