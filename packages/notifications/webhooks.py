from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import time
import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Callable

import httpx
from pydantic import BaseModel, Field
from sqlalchemy import text

from packages.schemas.database import get_session
from packages.logging.structured import get_logger

logger = get_logger("webhooks")


class WebhookEvent(str, Enum):
    RUN_CREATED = "run.created"
    RUN_UPDATED = "run.updated"
    RUN_COMPLETED = "run.completed"
    RUN_FAILED = "run.failed"
    APPROVAL_NEEDED = "approval.needed"
    APPROVAL_GRANTED = "approval.granted"
    APPROVAL_DENIED = "approval.denied"
    STEP_COMPLETED = "step.completed"
    POLICY_VIOLATION = "policy.violation"
    ESCALATION = "escalation"


class WebhookConfig(BaseModel):
    webhook_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    tenant_id: uuid.UUID
    url: str
    events: list[WebhookEvent]
    secret: str | None = None
    active: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)


class WebhookDelivery(BaseModel):
    delivery_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    webhook_id: uuid.UUID
    event: WebhookEvent
    payload: dict
    status: str = "pending"
    response_code: int | None = None
    error: str | None = None
    attempts: int = 0
    created_at: datetime = Field(default_factory=datetime.utcnow)


class WebhookManager:
    def __init__(self, max_retries: int = 3, timeout_seconds: int = 10):
        self.max_retries = max_retries
        self.timeout_seconds = timeout_seconds

    async def register_webhook(
        self,
        tenant_id: uuid.UUID,
        url: str,
        events: list[WebhookEvent],
        secret: str | None = None,
    ) -> WebhookConfig:
        config = WebhookConfig(
            tenant_id=tenant_id,
            url=url,
            events=events,
            secret=secret,
        )

        async with get_session() as session:
            await session.execute(
                text(
                    """
                    INSERT INTO webhook_configs
                        (webhook_id, tenant_id, url, events, secret, active, created_at)
                    VALUES
                        (:webhook_id, :tenant_id, :url, :events, :secret, :active, NOW())
                    """
                ),
                {
                    "webhook_id": config.webhook_id,
                    "tenant_id": tenant_id,
                    "url": url,
                    "events": [e.value for e in events],
                    "secret": secret,
                    "active": True,
                },
            )

        logger.info(f"Webhook registered: {config.webhook_id}")
        return config

    async def trigger_event(self, event: WebhookEvent, payload: dict, tenant_id: uuid.UUID):
        webhooks = await self._get_active_webhooks(tenant_id, event)

        for webhook in webhooks:
            delivery = WebhookDelivery(
                webhook_id=webhook["webhook_id"],
                event=event,
                payload=payload,
            )
            await self._deliver_webhook(webhook, delivery)

    async def _deliver_webhook(self, webhook: dict, delivery: WebhookDelivery):
        headers = {
            "Content-Type": "application/json",
            "X-Webhook-Event": delivery.event.value,
            "X-Webhook-Delivery": str(delivery.delivery_id),
            "X-Webhook-Timestamp": str(int(time.time())),
        }

        if webhook.get("secret"):
            signature = self._sign_payload(webhook["secret"], delivery.payload)
            headers["X-Webhook-Signature"] = signature

        for attempt in range(self.max_retries):
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        webhook["url"],
                        json=delivery.payload,
                        headers=headers,
                        timeout=self.timeout_seconds,
                    )

                delivery.response_code = response.status_code
                delivery.attempts = attempt + 1

                if response.status_code < 300:
                    delivery.status = "delivered"
                    await log_delivery(delivery)
                    return

            except Exception as e:
                delivery.error = str(e)
                logger.warning(f"Webhook delivery failed: {e}")

            if attempt < self.max_retries - 1:
                await asyncio.sleep(2 ** attempt)

        delivery.status = "failed"
        await log_delivery(delivery)

    def _sign_payload(self, secret: str, payload: dict) -> str:
        payload_bytes = json.dumps(payload, sort_keys=True).encode()
        return hmac.new(secret.encode(), payload_bytes, hashlib.sha256).hexdigest()

    async def _get_active_webhooks(self, tenant_id: uuid.UUID, event: WebhookEvent) -> list[dict]:
        async with get_session() as session:
            result = await session.execute(
                text(
                    """
                    SELECT * FROM webhook_configs
                    WHERE tenant_id = :tenant_id
                      AND active = true
                      AND :event = ANY(events)
                    """
                ),
                {"tenant_id": tenant_id, "event": event.value},
            )
            return [dict(row) for row in result.mappings().all()]

    async def list_webhooks(self, tenant_id: uuid.UUID) -> list[dict]:
        async with get_session() as session:
            result = await session.execute(
                text(
                    """
                    SELECT webhook_id, url, events, active, created_at
                    FROM webhook_configs
                    WHERE tenant_id = :tenant_id
                    """
                ),
                {"tenant_id": tenant_id},
            )
            return [dict(row) for row in result.mappings().all()]

    async def delete_webhook(self, webhook_id: uuid.UUID, tenant_id: uuid.UUID) -> bool:
        async with get_session() as session:
            result = await session.execute(
                text(
                    """
                    DELETE FROM webhook_configs
                    WHERE webhook_id = :webhook_id AND tenant_id = :tenant_id
                    """
                ),
                {"webhook_id": webhook_id, "tenant_id": tenant_id},
            )
            return result.rowcount > 0

    async def get_delivery_log(self, webhook_id: uuid.UUID, limit: int = 50) -> list[dict]:
        async with get_session() as session:
            result = await session.execute(
                text(
                    """
                    SELECT * FROM webhook_deliveries
                    WHERE webhook_id = :webhook_id
                    ORDER BY created_at DESC
                    LIMIT :limit
                    """
                ),
                {"webhook_id": webhook_id, "limit": limit},
            )
            return [dict(row) for row in result.mappings().all()]


async def log_delivery(delivery: WebhookDelivery):
    async with get_session() as session:
        await session.execute(
            text(
                """
                INSERT INTO webhook_deliveries
                    (delivery_id, webhook_id, event, payload, status, response_code, error, attempts, created_at)
                VALUES
                    (:delivery_id, :webhook_id, :event, :payload, :status, :response_code, :error, :attempts, NOW())
                """
            ),
            {
                "delivery_id": delivery.delivery_id,
                "webhook_id": delivery.webhook_id,
                "event": delivery.event.value,
                "payload": delivery.payload,
                "status": delivery.status,
                "response_code": delivery.response_code,
                "error": delivery.error,
                "attempts": delivery.attempts,
            },
        )


webhook_manager = WebhookManager()
