from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field

from packages.logging.structured import get_logger

logger = get_logger("websocket")


class WSMessage(BaseModel):
    event: str
    data: dict = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ConnectionManager:
    def __init__(self):
        self._connections: dict[str, WebSocket] = {}
        self._subscriptions: dict[str, set[str]] = {}
        self._message_history: list[WSMessage] = []
        self._max_history = 100

    async def connect(self, websocket: WebSocket, client_id: str | None = None) -> str:
        await websocket.accept()
        cid = client_id or str(uuid.uuid4())
        self._connections[cid] = websocket
        logger.info(f"WebSocket connected: {cid}")
        return cid

    def disconnect(self, client_id: str):
        if client_id in self._connections:
            del self._connections[client_id]
            for topic, subscribers in self._subscriptions.items():
                subscribers.discard(client_id)
            logger.info(f"WebSocket disconnected: {client_id}")

    def subscribe(self, client_id: str, topic: str):
        if topic not in self._subscriptions:
            self._subscriptions[topic] = set()
        self._subscriptions[topic].add(client_id)

    def unsubscribe(self, client_id: str, topic: str):
        if topic in self._subscriptions:
            self._subscriptions[topic].discard(client_id)

    async def broadcast(self, event: str, data: dict, topic: str | None = None):
        message = WSMessage(event=event, data=data)
        self._message_history.append(message)
        if len(self._message_history) > self._max_history:
            self._message_history = self._message_history[-self._max_history:]

        targets = set()
        if topic and topic in self._subscriptions:
            targets = self._subscriptions[topic].copy()
        else:
            targets = set(self._connections.keys())

        disconnected = []
        for client_id in targets:
            ws = self._connections.get(client_id)
            if ws:
                try:
                    await ws.send_json(message.model_dump())
                except Exception:
                    disconnected.append(client_id)

        for cid in disconnected:
            self.disconnect(cid)

    async def send_to(self, client_id: str, event: str, data: dict):
        ws = self._connections.get(client_id)
        if ws:
            message = WSMessage(event=event, data=data)
            try:
                await ws.send_json(message.model_dump())
            except Exception:
                self.disconnect(client_id)

    def get_history(self, limit: int = 50) -> list[dict]:
        return [m.model_dump() for m in self._message_history[-limit:]]

    def get_connections(self) -> dict[str, str]:
        return {cid: str(ws.url) for cid, ws in self._connections.items()}

    def get_subscriptions(self) -> dict[str, list[str]]:
        return {topic: list(subs) for topic, subs in self._subscriptions.items()}


ws_manager = ConnectionManager()


class RunStatusBroadcaster:
    async def on_run_created(self, run_id: str, tenant_id: str, goal: str):
        await ws_manager.broadcast("run.created", {
            "run_id": run_id,
            "tenant_id": tenant_id,
            "goal": goal,
        }, topic=f"tenant:{tenant_id}")

    async def on_run_updated(self, run_id: str, tenant_id: str, state: str, **kwargs):
        await ws_manager.broadcast("run.updated", {
            "run_id": run_id,
            "tenant_id": tenant_id,
            "state": state,
            **kwargs,
        }, topic=f"tenant:{tenant_id}")

    async def on_run_completed(self, run_id: str, tenant_id: str, state: str, cost: float):
        await ws_manager.broadcast("run.completed", {
            "run_id": run_id,
            "tenant_id": tenant_id,
            "state": state,
            "cost": cost,
        }, topic=f"tenant:{tenant_id}")

    async def on_step_completed(self, run_id: str, tenant_id: str, step: int, success: bool):
        await ws_manager.broadcast("step.completed", {
            "run_id": run_id,
            "tenant_id": tenant_id,
            "step": step,
            "success": success,
        }, topic=f"run:{run_id}")

    async def on_approval_needed(self, run_id: str, tenant_id: str, approval_id: str):
        await ws_manager.broadcast("approval.needed", {
            "run_id": run_id,
            "tenant_id": tenant_id,
            "approval_id": approval_id,
        }, topic=f"tenant:{tenant_id}")


run_broadcaster = RunStatusBroadcaster()
