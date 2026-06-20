from __future__ import annotations

import os
import uuid

import pytest

from packages.runtime.executor import ToolExecutionResult
from packages.runtime.llm_executor import LLMExecutor, estimate_cost
from packages.runtime.state import RunState, BudgetPolicy


def _make_state(**kwargs) -> RunState:
    defaults = {
        "run_id": uuid.uuid4(),
        "tenant_id": uuid.uuid4(),
        "goal": "test goal",
        "budget": BudgetPolicy(),
    }
    defaults.update(kwargs)
    return RunState(**defaults)


class TestEstimateCost:
    def test_gpt4o_mini(self):
        cost = estimate_cost("gpt-4o-mini", 1000, 500)
        assert cost == pytest.approx(0.00045, rel=1e-3)

    def test_gpt4o(self):
        cost = estimate_cost("gpt-4o", 1000, 500)
        assert cost == pytest.approx(0.0075, rel=1e-3)

    def test_unknown_model_uses_default(self):
        cost = estimate_cost("unknown-model", 1000, 500)
        assert cost > 0

    def test_zero_tokens(self):
        cost = estimate_cost("gpt-4o-mini", 0, 0)
        assert cost == 0.0


class TestLLMExecutor:
    def test_init_defaults(self):
        executor = LLMExecutor()
        assert executor.model == os.environ.get("LLM_MODEL", "gpt-4o-mini")
        assert executor.max_tokens == 1024

    def test_init_custom(self):
        executor = LLMExecutor(model="gpt-4o", max_tokens=512)
        assert executor.model == "gpt-4o"
        assert executor.max_tokens == 512

    @pytest.mark.asyncio
    async def test_execute_no_api_key(self):
        state = _make_state(goal="test")
        executor = LLMExecutor()
        # Remove any existing API key env var
        old_key = os.environ.pop("LLM_API_KEY", None)
        old_openai = os.environ.pop("OPENAI_API_KEY", None)
        try:
            result = await executor.execute(state)
            assert result.error is not None
            assert "LLM_API_KEY" in result.error or "OPENAI_API_KEY" in result.error
        finally:
            if old_key:
                os.environ["LLM_API_KEY"] = old_key
            if old_openai:
                os.environ["OPENAI_API_KEY"] = old_openai


class TestToolExecutionResult:
    def test_defaults(self):
        result = ToolExecutionResult(output="test")
        assert result.prompt_tokens == 0
        assert result.completion_tokens == 0
        assert result.tools_used is None
        assert result.model is None
        assert result.latency_ms == 0
        assert result.cost_usd == 0.0
        assert result.error is None

    def test_full_fields(self):
        result = ToolExecutionResult(
            output="test",
            prompt_tokens=100,
            completion_tokens=50,
            tools_used=["search"],
            model="gpt-4o",
            latency_ms=500,
            cost_usd=0.01,
            error=None,
        )
        assert result.tools_used == ["search"]
        assert result.cost_usd == 0.01
