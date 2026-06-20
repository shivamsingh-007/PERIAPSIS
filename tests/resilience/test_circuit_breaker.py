from __future__ import annotations
"""Tests for packages.resilience.circuit_breaker - CircuitBreaker, state transitions."""

import asyncio
import time

import pytest

from packages.resilience.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitBreakerMetrics,
    CircuitBreakerOpenError,
    CircuitBreakerRegistry,
    CircuitState,
)


class TestCircuitState:
    def test_all_states(self):
        assert len(list(CircuitState)) == 3

    def test_closed_value(self):
        assert CircuitState.CLOSED.value == "closed"

    def test_open_value(self):
        assert CircuitState.OPEN.value == "open"

    def test_half_open_value(self):
        assert CircuitState.HALF_OPEN.value == "half_open"


class TestCircuitBreakerConfig:
    def test_defaults(self):
        config = CircuitBreakerConfig()
        assert config.failure_threshold == 5
        assert config.recovery_timeout == 60.0
        assert config.success_threshold == 3
        assert config.timeout == 30.0

    def test_custom(self):
        config = CircuitBreakerConfig(failure_threshold=3, recovery_timeout=10.0)
        assert config.failure_threshold == 3


class TestCircuitBreakerMetrics:
    def test_defaults(self):
        m = CircuitBreakerMetrics()
        assert m.total_calls == 0
        assert m.successful_calls == 0
        assert m.failed_calls == 0


class TestCircuitBreaker:
    def setup_method(self):
        self.cb = CircuitBreaker("test-service")

    def test_initial_state(self):
        assert self.cb.state == CircuitState.CLOSED
        assert self.cb.is_open is False

    def test_get_status(self):
        status = self.cb.get_status()
        assert status["service"] == "test-service"
        assert status["state"] == "closed"

    def test_transition_to_open_on_failures(self):
        for _ in range(5):
            self.cb._on_failure()
        assert self.cb.state == CircuitState.OPEN
        assert self.cb.is_open is True

    def test_transition_to_half_open_after_recovery(self):
        cb = CircuitBreaker(
            "test", CircuitBreakerConfig(recovery_timeout=0.01)
        )
        cb._transition_to(CircuitState.OPEN)
        time.sleep(0.02)
        assert cb._should_attempt_reset() is True

    def test_success_resets_failures(self):
        self.cb._on_failure()
        self.cb._on_failure()
        self.cb._on_success()
        assert self.cb.metrics.consecutive_failures == 0
        assert self.cb.metrics.consecutive_successes == 1

    def test_half_open_to_closed_on_successes(self):
        cb = CircuitBreaker(
            "test", CircuitBreakerConfig(success_threshold=2)
        )
        cb._transition_to(CircuitState.HALF_OPEN)
        cb._on_success()
        assert cb.state == CircuitState.HALF_OPEN
        cb._on_success()
        assert cb.state == CircuitState.CLOSED

    def test_half_open_to_open_on_failure(self):
        cb = CircuitBreaker("test")
        cb._transition_to(CircuitState.HALF_OPEN)
        cb._on_failure()
        assert cb.state == CircuitState.OPEN

    def test_recovery_remaining(self):
        cb = CircuitBreaker(
            "test", CircuitBreakerConfig(recovery_timeout=100)
        )
        cb._transition_to(CircuitState.OPEN)
        remaining = cb.recovery_remaining
        assert remaining > 0
        assert remaining <= 100

    def test_recovery_remaining_not_open(self):
        remaining = self.cb.recovery_remaining
        assert remaining == 0.0

    def test_reset(self):
        self.cb._on_failure()
        self.cb._on_failure()
        self.cb._on_failure()
        self.cb._on_failure()
        self.cb._on_failure()
        assert self.cb.state == CircuitState.OPEN
        self.cb.reset()
        assert self.cb.state == CircuitState.CLOSED
        assert self.cb.metrics.total_calls == 0

    @pytest.mark.asyncio
    async def test_call_success(self):
        async def ok():
            return "ok"

        result = await self.cb.call(ok)
        assert result == "ok"
        assert self.cb.metrics.total_calls == 1
        assert self.cb.metrics.successful_calls == 1

    @pytest.mark.asyncio
    async def test_call_failure(self):
        async def fail():
            raise ValueError("boom")

        with pytest.raises(ValueError, match="boom"):
            await self.cb.call(fail)
        assert self.cb.metrics.failed_calls == 1

    @pytest.mark.asyncio
    async def test_call_open_raises(self):
        for _ in range(5):
            self.cb._on_failure()
        assert self.cb.state == CircuitState.OPEN

        async def ok():
            return "ok"

        with pytest.raises(CircuitBreakerOpenError):
            await self.cb.call(ok)

    @pytest.mark.asyncio
    async def test_call_open_attempt_reset_after_timeout(self):
        cb = CircuitBreaker(
            "test", CircuitBreakerConfig(recovery_timeout=0.01, success_threshold=1)
        )
        cb._transition_to(CircuitState.OPEN)
        time.sleep(0.02)

        async def ok():
            return "ok"

        result = await cb.call(ok)
        assert result == "ok"
        assert cb.state == CircuitState.CLOSED


class TestCircuitBreakerRegistry:
    def test_get_or_create(self):
        registry = CircuitBreakerRegistry()
        cb1 = registry.get_or_create("svc1")
        cb2 = registry.get_or_create("svc1")
        assert cb1 is cb2

    def test_different_services(self):
        registry = CircuitBreakerRegistry()
        cb1 = registry.get_or_create("svc1")
        cb2 = registry.get_or_create("svc2")
        assert cb1 is not cb2

    def test_get_all(self):
        registry = CircuitBreakerRegistry()
        registry.get_or_create("svc1")
        registry.get_or_create("svc2")
        all_status = registry.get_all()
        assert len(all_status) == 2

    def test_reset_all(self):
        registry = CircuitBreakerRegistry()
        cb = registry.get_or_create("svc1")
        cb._on_failure()
        cb._on_failure()
        cb._on_failure()
        cb._on_failure()
        cb._on_failure()
        registry.reset_all()
        assert cb.state == CircuitState.CLOSED
