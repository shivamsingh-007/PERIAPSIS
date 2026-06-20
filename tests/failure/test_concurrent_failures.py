from __future__ import annotations

import asyncio
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
def registry():
    return CircuitBreakerRegistry()


def make_breaker(name: str, threshold: int = 3) -> CircuitBreaker:
    return CircuitBreaker(
        service_name=name,
        config=CircuitBreakerConfig(failure_threshold=threshold, recovery_timeout=1),
    )


class TestConcurrentFailures:
    @pytest.mark.asyncio
    async def test_multiple_breakers_independent(self, registry):
        cb1 = registry.get_or_create("svc1")
        cb2 = registry.get_or_create("svc2")

        async def fail1():
            raise RuntimeError("svc1 fail")

        async def fail2():
            raise ValueError("svc2 fail")

        with pytest.raises(RuntimeError):
            await cb1.call(fail1)
        with pytest.raises(ValueError):
            await cb2.call(fail2)

        assert cb1.state == CircuitState.CLOSED
        assert cb2.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_one_breaker_opens_others_stay_closed(self, registry):
        cb1 = CircuitBreaker(
            service_name="svc1",
            config=CircuitBreakerConfig(failure_threshold=3, recovery_timeout=1),
        )
        cb2 = CircuitBreaker(
            service_name="svc2",
            config=CircuitBreakerConfig(failure_threshold=3, recovery_timeout=1),
        )

        async def fail():
            raise RuntimeError("fail")

        for _ in range(3):
            with pytest.raises(RuntimeError):
                await cb1.call(fail)

        assert cb1.state == CircuitState.OPEN
        assert cb2.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_parallel_failures_same_breaker(self):
        cb = make_breaker("parallel", threshold=5)
        errors = []

        async def fail(i):
            try:
                await cb.call(lambda: (_ for _ in ()).throw(RuntimeError(f"err-{i}")))
            except RuntimeError:
                errors.append(i)

        await asyncio.gather(*[fail(i) for i in range(5)])
        assert cb.state == CircuitState.OPEN
        assert len(errors) == 5

    @pytest.mark.asyncio
    async def test_parallel_success_and_failure(self):
        cb = make_breaker("mixed", threshold=3)
        success_count = 0
        fail_count = 0

        async def mixed_task(i):
            nonlocal success_count, fail_count
            if i % 2 == 0:
                async def ok():
                    return "ok"
                await cb.call(ok)
                success_count += 1
            else:
                async def fail():
                    raise RuntimeError("fail")
                try:
                    await cb.call(fail)
                except RuntimeError:
                    fail_count += 1

        await asyncio.gather(*[mixed_task(i) for i in range(10)])
        assert cb.metrics.consecutive_failures >= 1

    @pytest.mark.asyncio
    async def test_cascade_failure_detection(self):
        breakers = [make_breaker(f"svc{i}", threshold=2) for i in range(5)]

        async def fail_all():
            async def fail():
                raise RuntimeError("fail")
            tasks = [cb.call(fail) for cb in breakers]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            return results

        results = await fail_all()
        open_count = sum(1 for r in results if isinstance(r, RuntimeError))
        assert open_count == 5

    @pytest.mark.asyncio
    async def test_concurrent_reset_during_failure(self):
        cb = make_breaker("reset-test", threshold=100)

        async def fail():
            raise RuntimeError("fail")

        async def do_failures():
            for _ in range(3):
                try:
                    await cb.call(fail)
                except RuntimeError:
                    pass

        async def do_reset():
            await asyncio.sleep(0.001)
            cb.reset()

        await asyncio.gather(do_failures(), do_reset())
        assert cb.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_registry_concurrent_access(self, registry):
        async def create_breaker(i):
            return registry.get_or_create(f"svc-{i}")

        breakers = await asyncio.gather(*[create_breaker(i) for i in range(20)])
        assert len(set(id(b) for b in breakers)) == 20

    @pytest.mark.asyncio
    async def test_metrics_accumulate(self):
        cb = make_breaker("metrics", threshold=10)

        async def fail():
            raise RuntimeError("fail")

        for _ in range(5):
            with pytest.raises(RuntimeError):
                await cb.call(fail)

        status = cb.get_status()
        assert status["metrics"]["consecutive_failures"] == 5

    @pytest.mark.asyncio
    async def test_success_resets_failure_count(self):
        cb = make_breaker("reset-count", threshold=5)

        async def fail():
            raise RuntimeError("fail")

        async def succeed():
            return "ok"

        with pytest.raises(RuntimeError):
            await cb.call(fail)
        with pytest.raises(RuntimeError):
            await cb.call(fail)

        await cb.call(succeed)
        assert cb.metrics.consecutive_failures == 0

    @pytest.mark.asyncio
    async def test_registry_reset_all(self, registry):
        cb1 = CircuitBreaker(
            service_name="a",
            config=CircuitBreakerConfig(failure_threshold=3, recovery_timeout=1),
        )
        cb2 = CircuitBreaker(
            service_name="b",
            config=CircuitBreakerConfig(failure_threshold=3, recovery_timeout=1),
        )
        registry._breakers["a"] = cb1
        registry._breakers["b"] = cb2

        async def fail():
            raise RuntimeError("fail")

        for _ in range(3):
            with pytest.raises(RuntimeError):
                await cb1.call(fail)
            with pytest.raises(RuntimeError):
                await cb2.call(fail)

        assert cb1.state == CircuitState.OPEN
        assert cb2.state == CircuitState.OPEN

        registry.reset_all()

        assert cb1.state == CircuitState.CLOSED
        assert cb2.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_get_all_breakers(self, registry):
        for i in range(5):
            registry.get_or_create(f"svc{i}")
        all_breakers = registry.get_all()
        assert len(all_breakers) == 5
