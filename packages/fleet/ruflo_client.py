from __future__ import annotations

import asyncio
import json
import os
import shutil
import signal
import uuid
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from packages.logging.structured import get_logger

logger = get_logger("ruflo_client")


class RufloToolCall(BaseModel):
    name: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))


class RufloToolResult(BaseModel):
    tool_call_id: str
    content: Any
    is_error: bool = False


class RufloMCPMessage(BaseModel):
    jsonrpc: str = "2.0"
    id: int | str | None = None
    method: str | None = None
    params: dict | None = None
    result: Any = None
    error: dict | None = None


class RufloClient:
    def __init__(self, ruflo_path: str | None = None, workspace_dir: str | None = None):
        self.ruflo_path = ruflo_path or self._find_ruflo()
        self.workspace_dir = workspace_dir or os.getcwd()
        self._process: asyncio.subprocess.Process | None = None
        self._request_id = 0
        self._pending: dict[int, asyncio.Future] = {}
        self._initialized = False
        self._reader_task: asyncio.Task | None = None

    def _find_ruflo(self) -> str:
        found = shutil.which("npx")
        if found:
            return found
        npm_path = shutil.which("npm")
        if npm_path:
            return npm_path
        raise FileNotFoundError("npx or npm not found. Install Node.js to use Ruflo integration.")

    async def start(self) -> None:
        if self._process and self._process.returncode is None:
            return

        logger.info("Starting Ruflo MCP server")

        self._process = await asyncio.create_subprocess_exec(
            self.ruflo_path,
            "ruflo@latest",
            "mcp",
            "start",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env={**os.environ, "RUFLO_WORKSPACE": self.workspace_dir},
        )

        self._reader_task = asyncio.create_task(self._read_responses())

        init_result = await self._send_request("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {
                "name": "agentic-loop-platform",
                "version": "1.0.0",
            },
        })

        await self._send_notification("notifications/initialized", {})

        self._initialized = True
        logger.info("Ruflo MCP server initialized")

    async def stop(self) -> None:
        if self._reader_task:
            self._reader_task.cancel()
            try:
                await self._reader_task
            except asyncio.CancelledError:
                pass

        if self._process and self._process.returncode is None:
            self._process.terminate()
            try:
                await asyncio.wait_for(self._process.wait(), timeout=5.0)
            except asyncio.TimeoutError:
                self._process.kill()
                await self._process.wait()

        self._initialized = False
        logger.info("Ruflo MCP server stopped")

    async def call_tool(self, tool_name: str, arguments: dict[str, Any] | None = None) -> Any:
        if not self._initialized:
            await self.start()

        result = await self._send_request("tools/call", {
            "name": tool_name,
            "arguments": arguments or {},
        })

        if result.get("isError"):
            raise RuntimeError(f"Ruflo tool error: {result}")

        content = result.get("content", [])
        if content and len(content) > 0:
            return content[0].get("text", content[0])
        return result

    async def list_tools(self) -> list[dict]:
        if not self._initialized:
            await self.start()

        result = await self._send_request("tools/list", {})
        return result.get("tools", [])

    async def swarm_init(self, topology: str = "hierarchical", agents: list[str] | None = None) -> dict:
        return await self.call_tool("swarm_init", {
            "topology": topology,
            "agents": agents or [],
        })

    async def agent_spawn(self, role: str, task: str, swarm_id: str | None = None) -> dict:
        return await self.call_tool("agent_spawn", {
            "role": role,
            "task": task,
            "swarmId": swarm_id,
        })

    async def memory_store(self, key: str, value: str, namespace: str = "default") -> dict:
        return await self.call_tool("memory_store", {
            "key": key,
            "value": value,
            "namespace": namespace,
        })

    async def memory_search(self, query: str, namespace: str = "default", limit: int = 5) -> dict:
        return await self.call_tool("memory_search", {
            "query": query,
            "namespace": namespace,
            "limit": limit,
        })

    async def federation_init(self) -> dict:
        return await self.call_tool("federation_init", {})

    async def federation_send(self, to: str, message: str, msg_type: str = "task-request") -> dict:
        return await self.call_tool("federation_send", {
            "to": to,
            "message": message,
            "type": msg_type,
        })

    async def federation_status(self) -> dict:
        return await self.call_tool("federation_status", {})

    async def _send_request(self, method: str, params: dict) -> dict:
        self._request_id += 1
        msg_id = self._request_id

        message = RufloMCPMessage(
            id=msg_id,
            method=method,
            params=params,
        )

        future: asyncio.Future = asyncio.get_event_loop().create_future()
        self._pending[msg_id] = future

        line = json.dumps(message.model_dump(exclude_none=True)) + "\n"
        self._process.stdin.write(line.encode())
        await self._process.stdin.drain()

        try:
            result = await asyncio.wait_for(future, timeout=60.0)
        except asyncio.TimeoutError:
            self._pending.pop(msg_id, None)
            raise TimeoutError(f"Ruflo request timed out: {method}")

        if result.get("error"):
            raise RuntimeError(f"Ruflo error: {result['error']}")

        return result.get("result", {})

    async def _send_notification(self, method: str, params: dict) -> None:
        message = RufloMCPMessage(
            method=method,
            params=params,
        )
        line = json.dumps(message.model_dump(exclude_none=True)) + "\n"
        self._process.stdin.write(line.encode())
        await self._process.stdin.drain()

    async def _read_responses(self) -> None:
        try:
            while True:
                line = await self._process.stdout.readline()
                if not line:
                    break

                try:
                    data = json.loads(line.decode().strip())
                    msg = RufloMCPMessage(**data)

                    if msg.id is not None and msg.id in self._pending:
                        self._pending[msg.id].set_result(data)
                        del self._pending[msg.id]

                except json.JSONDecodeError:
                    continue
                except Exception as e:
                    logger.error(f"Error processing Ruflo response: {e}")
        except asyncio.CancelledError:
            pass

    @property
    def is_running(self) -> bool:
        return self._process is not None and self._process.returncode is None


ruflo_client = RufloClient()
