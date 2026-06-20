"""WebSocket routes with token-based authentication."""

from __future__ import annotations

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from packages.security.auth import auth_manager, TokenPayload
from packages.websocket.manager import ws_manager

router = APIRouter(tags=["websocket"])


@router.websocket("/ws/runs")
async def runs_websocket(
    websocket: WebSocket,
    token: str | None = Query(None),
):
    """Authenticated WebSocket for real-time run updates.

    Client connects with: ws://host/ws/runs?token=<jwt>
    Server validates token before accepting the connection.
    """
    if not token:
        await websocket.close(code=1008, reason="Missing token")
        return

    payload = auth_manager.verify_token(token)
    if payload is None:
        await websocket.close(code=1008, reason="Invalid or expired token")
        return

    tenant_id = payload.tenant_id
    client_id = f"{tenant_id}:{payload.sub}"

    cid = await ws_manager.connect(websocket, client_id)
    ws_manager.subscribe(client_id, f"tenant:{tenant_id}")

    try:
        while True:
            data = await websocket.receive_json()
            await _handle_message(client_id, tenant_id, data)
    except WebSocketDisconnect:
        ws_manager.disconnect(client_id)
    except Exception:
        ws_manager.disconnect(client_id)
        try:
            await websocket.close()
        except Exception:
            pass


@router.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    """Legacy unauthenticated WebSocket endpoint (kept for backwards compat)."""
    cid = await ws_manager.connect(websocket, client_id)
    try:
        while True:
            data = await websocket.receive_json()
            await _handle_message(cid, None, data)
    except WebSocketDisconnect:
        ws_manager.disconnect(cid)


async def _handle_message(client_id: str, tenant_id: str | None, data: dict):
    action = data.get("action")

    if action == "subscribe":
        topic = data.get("topic")
        if topic:
            ws_manager.subscribe(client_id, topic)
            await ws_manager.send_to(client_id, "subscribed", {"topic": topic})

    elif action == "unsubscribe":
        topic = data.get("topic")
        if topic:
            ws_manager.unsubscribe(client_id, topic)
            await ws_manager.send_to(client_id, "unsubscribed", {"topic": topic})

    elif action == "ping":
        await ws_manager.send_to(client_id, "pong", {})

    elif action == "history":
        limit = data.get("limit", 50)
        history = ws_manager.get_history(limit)
        await ws_manager.send_to(client_id, "history", {"messages": history})
