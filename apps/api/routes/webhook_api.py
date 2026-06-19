from __future__ import annotations

import uuid
from pydantic import BaseModel
from fastapi import APIRouter

from packages.notifications.webhooks import webhook_manager, WebhookEvent

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


class WebhookCreateRequest(BaseModel):
    tenant_id: uuid.UUID
    url: str
    events: list[str]
    secret: str | None = None


class WebhookResponse(BaseModel):
    status: str
    webhook_id: uuid.UUID | None = None
    message: str = ""


@router.post("/", response_model=WebhookResponse)
async def create_webhook(request: WebhookCreateRequest):
    events = [WebhookEvent(e) for e in request.events]
    config = await webhook_manager.register_webhook(
        tenant_id=request.tenant_id,
        url=request.url,
        events=events,
        secret=request.secret,
    )
    return WebhookResponse(
        status="created",
        webhook_id=config.webhook_id,
        message=f"Webhook registered for {len(events)} events",
    )


@router.get("/{tenant_id}")
async def list_webhooks(tenant_id: uuid.UUID):
    webhooks = await webhook_manager.list_webhooks(tenant_id)
    return {"webhooks": webhooks, "count": len(webhooks)}


@router.delete("/{webhook_id}")
async def delete_webhook(webhook_id: uuid.UUID, tenant_id: uuid.UUID):
    deleted = await webhook_manager.delete_webhook(webhook_id, tenant_id)
    return {"deleted": deleted}


@router.get("/{webhook_id}/deliveries")
async def get_deliveries(webhook_id: uuid.UUID, limit: int = 50):
    deliveries = await webhook_manager.get_delivery_log(webhook_id, limit)
    return {"deliveries": deliveries, "count": len(deliveries)}
