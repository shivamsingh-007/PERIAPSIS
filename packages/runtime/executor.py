from __future__ import annotations

from typing import Protocol

from pydantic import BaseModel

from packages.runtime.state import RunState


class ToolExecutionResult(BaseModel):
    """Structured result from an executor."""

    output: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    tools_used: list[str] | None = None
    model: str | None = None
    latency_ms: int = 0
    cost_usd: float = 0.0
    error: str | None = None


class Executor(Protocol):
    """Protocol for LLM/tool execution backends."""

    async def execute(self, state: RunState) -> ToolExecutionResult: ...
