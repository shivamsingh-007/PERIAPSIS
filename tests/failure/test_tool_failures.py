from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from packages.resilience.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitBreakerOpenError,
    CircuitBreakerRegistry,
    CircuitState,
)


@pytest.fixture
def breaker():
    return CircuitBreaker(
        service_name="test-breaker",
        config=CircuitBreakerConfig(failure_threshold=3, recovery_timeout=1),
    )


@pytest.fixture
def registry():
    return CircuitBreakerRegistry()


class TestCircuitBreaker:
    def test_init(self, breaker):
        assert breaker.service_name == "test-breaker"
        assert breaker.config.failure_threshold == 3

    def test_initial_state(self, breaker):
        assert breaker.state == CircuitState.CLOSED

    async def test_success_stays_closed(self, breaker):
        async def success_fn():
            return "success"
        result = await breaker.call(success_fn)
        assert result == "success"
        assert breaker.state == CircuitState.CLOSED

    async def test_failure_increments_count(self, breaker):
        async def fail_fn():
            raise ZeroDivisionError()
        with pytest.raises(ZeroDivisionError):
            await breaker.call(fail_fn)
        assert breaker.metrics.consecutive_failures == 1

    async def test_failures_open_circuit(self, breaker):
        async def fail_fn():
            raise ZeroDivisionError()
        for _ in range(3):
            with pytest.raises(ZeroDivisionError):
                await breaker.call(fail_fn)
        assert breaker.state == CircuitState.OPEN

    async def test_open_circuit_rejects(self, breaker):
        async def fail_fn():
            raise ZeroDivisionError()
        for _ in range(3):
            with pytest.raises(ZeroDivisionError):
                await breaker.call(fail_fn)
        async def should_not_run():
            return "should not run"
        with pytest.raises(CircuitBreakerOpenError):
            await breaker.call(should_not_run)

    def test_reset(self, breaker):
        breaker._transition_to(CircuitState.OPEN)
        breaker.metrics.consecutive_failures = 5
        breaker.reset()
        assert breaker.state == CircuitState.CLOSED
        assert breaker.metrics.consecutive_failures == 0

    def test_get_status(self, breaker):
        status = breaker.get_status()
        assert "service" in status
        assert "state" in status
        assert "metrics" in status


class TestCircuitBreakerRegistry:
    def test_get_or_create(self, registry):
        cb = registry.get_or_create("test")
        assert cb.service_name == "test"

    def test_get_existing(self, registry):
        cb1 = registry.get_or_create("test")
        cb2 = registry.get_or_create("test")
        assert cb1 is cb2

    def test_get_all(self, registry):
        registry.get_or_create("b1")
        registry.get_or_create("b2")
        breakers = registry.get_all()
        assert len(breakers) == 2

    def test_reset_all(self, registry):
        cb = registry.get_or_create("test")
        cb._transition_to(CircuitState.OPEN)
        cb.metrics.consecutive_failures = 5
        registry.reset_all()
        assert cb.state == CircuitState.CLOSED
