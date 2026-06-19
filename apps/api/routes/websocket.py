from __future__ import annotations

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from packages.websocket.manager import ws_manager

router = APIRouter(tags=["websocket"])


@router.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    cid = await ws_manager.connect(websocket, client_id)
    try:
        while True:
            data = await websocket.receive_json()
            await _handle_message(cid, data)
    except WebSocketDisconnect:
        ws_manager.disconnect(cid)


async def _handle_message(client_id: str, data: dict):
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
