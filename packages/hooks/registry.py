from __future__ import annotations

import asyncio
import logging
import time
import uuid
from enum import Enum
from typing import Any, Callable, Coroutine

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class HookType(str, Enum):
    BEFORE_RUN_START = "before_run_start"
    BEFORE_TOOL_CALL = "before_tool_call"
    AFTER_TOOL_CALL = "after_tool_call"
    BEFORE_CHECKPOINT = "before_checkpoint"
    BEFORE_MEMORY_WRITE = "before_memory_write"
    AFTER_MEMORY_WRITE = "after_memory_write"
    BEFORE_REFLECTION = "before_reflection"
    AFTER_REFLECTION = "after_reflection"
    AFTER_INCIDENT = "after_incident"
    BEFORE_SHIP_GATE = "before_ship_gate"


class HookResult(BaseModel):
    hook_id: str
    hook_type: HookType
    success: bool
    output: dict = Field(default_factory=dict)
    error: str | None = None
    duration_ms: float = 0.0


HookFunction = Callable[..., Coroutine[Any, Any, dict]]


class HookEntry(BaseModel):
    hook_id: str
    hook_type: HookType
    func: HookFunction
    priority: int = 0
    timeout_seconds: float = 5.0
    enabled: bool = True


class HookRegistry:
    def __init__(self):
        self._hooks: dict[HookType, list[HookEntry]] = {ht: [] for ht in HookType}
        self._execution_log: list[HookResult] = []

    def register(
        self,
        hook_type: HookType,
        func: HookFunction,
        hook_id: str | None = None,
        priority: int = 0,
        timeout_seconds: float = 5.0,
    ) -> str:
        hid = hook_id or f"{hook_type.value}_{uuid.uuid4().hex[:8]}"
        entry = HookEntry(
            hook_id=hid,
            hook_type=hook_type,
            func=func,
            priority=priority,
            timeout_seconds=timeout_seconds,
        )
        self._hooks[hook_type].append(entry)
        self._hooks[hook_type].sort(key=lambda e: e.priority, reverse=True)
        return hid

    def unregister(self, hook_id: str) -> bool:
        for hook_type, hooks in self._hooks.items():
            for i, entry in enumerate(hooks):
                if entry.hook_id == hook_id:
                    hooks.pop(i)
                    return True
        return False

    def list_hooks(self, hook_type: HookType | None = None) -> list[dict]:
        if hook_type:
            return [e.model_dump(exclude={"func"}) for e in self._hooks.get(hook_type, [])]
        result = []
        for ht, hooks in self._hooks.items():
            for e in hooks:
                result.append({**e.model_dump(exclude={"func"}), "hook_type": ht.value})
        return result

    async def execute(
        self,
        hook_type: HookType,
        **kwargs,
    ) -> list[HookResult]:
        hooks = self._hooks.get(hook_type, [])
        results = []

        for entry in hooks:
            if not entry.enabled:
                continue

            start = time.time()
            try:
                output = await asyncio.wait_for(
                    entry.func(**kwargs),
                    timeout=entry.duration_ms / 1000 if hasattr(entry, "duration_ms") else entry.timeout_seconds,
                )
                duration = (time.time() - start) * 1000
                result = HookResult(
                    hook_id=entry.hook_id,
                    hook_type=hook_type,
                    success=True,
                    output=output or {},
                    duration_ms=duration,
                )
            except asyncio.TimeoutError:
                duration = (time.time() - start) * 1000
                result = HookResult(
                    hook_id=entry.hook_id,
                    hook_type=hook_type,
                    success=False,
                    error=f"Hook timed out after {entry.timeout_seconds}s",
                    duration_ms=duration,
                )
                logger.warning(f"Hook {entry.hook_id} timed out")
            except Exception as e:
                duration = (time.time() - start) * 1000
                result = HookResult(
                    hook_id=entry.hook_id,
                    hook_type=hook_type,
                    success=False,
                    error=str(e),
                    duration_ms=duration,
                )
                logger.error(f"Hook {entry.hook_id} failed: {e}")

            results.append(result)
            self._execution_log.append(result)

        return results

    def get_execution_log(self, limit: int = 100) -> list[HookResult]:
        return self._execution_log[-limit:]


hook_registry = HookRegistry()
