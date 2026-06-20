from __future__ import annotations
"""Tests for packages.hooks.registry - HookRegistry."""

import asyncio

import pytest

from packages.hooks.registry import (
    HookEntry,
    HookRegistry,
    HookResult,
    HookType,
    hook_registry,
)


class TestHookType:
    def test_all_types(self):
        assert len(list(HookType)) == 10

    def test_before_run_start(self):
        assert HookType.BEFORE_RUN_START.value == "before_run_start"


class TestHookRegistry:
    def setup_method(self):
        self.registry = HookRegistry()

    def test_register_hook(self):
        async def my_hook(**kwargs):
            return {"status": "ok"}

        hid = self.registry.register(HookType.BEFORE_RUN_START, my_hook)
        assert hid is not None
        hooks = self.registry.list_hooks(HookType.BEFORE_RUN_START)
        assert len(hooks) == 1

    def test_register_with_custom_id(self):
        async def my_hook(**kwargs):
            return {}

        hid = self.registry.register(
            HookType.BEFORE_TOOL_CALL, my_hook, hook_id="my-custom-id"
        )
        assert hid == "my-custom-id"

    def test_unregister_hook(self):
        async def my_hook(**kwargs):
            return {}

        hid = self.registry.register(HookType.AFTER_TOOL_CALL, my_hook)
        result = self.registry.unregister(hid)
        assert result is True
        hooks = self.registry.list_hooks(HookType.AFTER_TOOL_CALL)
        assert len(hooks) == 0

    def test_unregister_nonexistent(self):
        result = self.registry.unregister("nonexistent")
        assert result is False

    def test_list_hooks_all(self):
        async def hook1(**kwargs):
            return {}

        async def hook2(**kwargs):
            return {}

        self.registry.register(HookType.BEFORE_RUN_START, hook1)
        self.registry.register(HookType.AFTER_TOOL_CALL, hook2)
        all_hooks = self.registry.list_hooks()
        assert len(all_hooks) == 2

    def test_priority_ordering(self):
        async def low_prio(**kwargs):
            return {}

        async def high_prio(**kwargs):
            return {}

        self.registry.register(HookType.BEFORE_RUN_START, low_prio, priority=1)
        self.registry.register(HookType.BEFORE_RUN_START, high_prio, priority=10)
        hooks = self.registry.list_hooks(HookType.BEFORE_RUN_START)
        assert hooks[0]["priority"] == 10
        assert hooks[1]["priority"] == 1

    @pytest.mark.asyncio
    async def test_execute_hook(self):
        async def my_hook(**kwargs):
            return {"result": "ok"}

        self.registry.register(HookType.BEFORE_RUN_START, my_hook)
        results = await self.registry.execute(HookType.BEFORE_RUN_START)
        assert len(results) == 1
        assert results[0].success is True
        assert results[0].output["result"] == "ok"

    @pytest.mark.asyncio
    async def test_execute_hook_failure(self):
        async def failing_hook(**kwargs):
            raise ValueError("hook failed")

        self.registry.register(HookType.AFTER_TOOL_CALL, failing_hook)
        results = await self.registry.execute(HookType.AFTER_TOOL_CALL)
        assert len(results) == 1
        assert results[0].success is False
        assert "hook failed" in results[0].error

    @pytest.mark.asyncio
    async def test_execute_hook_timeout(self):
        async def slow_hook(**kwargs):
            await asyncio.sleep(10)
            return {}

        self.registry.register(
            HookType.BEFORE_CHECKPOINT, slow_hook, timeout_seconds=0.1
        )
        results = await self.registry.execute(HookType.BEFORE_CHECKPOINT)
        assert len(results) == 1
        assert results[0].success is False
        assert "timed out" in results[0].error

    @pytest.mark.asyncio
    async def test_execute_disabled_hook(self):
        async def disabled_hook(**kwargs):
            return {"should_not": "run"}

        entry = HookEntry(
            hook_id="disabled",
            hook_type=HookType.AFTER_MEMORY_WRITE,
            func=disabled_hook,
            enabled=False,
        )
        self.registry._hooks[HookType.AFTER_MEMORY_WRITE].append(entry)
        results = await self.registry.execute(HookType.AFTER_MEMORY_WRITE)
        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_execution_log(self):
        async def my_hook(**kwargs):
            return {}

        self.registry.register(HookType.BEFORE_SHIP_GATE, my_hook)
        await self.registry.execute(HookType.BEFORE_SHIP_GATE)
        log = self.registry.get_execution_log()
        assert len(log) == 1
        assert log[0].success is True

    @pytest.mark.asyncio
    async def test_execution_log_limit(self):
        async def my_hook(**kwargs):
            return {}

        self.registry.register(HookType.BEFORE_RUN_START, my_hook)
        for _ in range(5):
            await self.registry.execute(HookType.BEFORE_RUN_START)
        log = self.registry.get_execution_log(limit=2)
        assert len(log) == 2
