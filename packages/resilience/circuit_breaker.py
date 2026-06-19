from __future__ import annotations

import time
from enum import Enum
from typing import Any, Callable, Coroutine

from pydantic import BaseModel

from packages.logging.structured import get_logger

logger = get_logger("circuit_breaker")


class CircuitState(str, Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreakerConfig(BaseModel):
    failure_threshold: int = 5
    recovery_timeout: float = 60.0
    success_threshold: int = 3
    timeout: float = 30.0


class CircuitBreakerMetrics(BaseModel):
    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    last_failure_time: float | None = None
    consecutive_successes: int = 0
    consecutive_failures: int = 0


class CircuitBreakerOpenError(Exception):
    def __init__(self, service_name: str, recovery_time: float):
        self.service_name = service_name
        self.recovery_time = recovery_time
        super().__init__(f"Circuit breaker open for {service_name}, recovers in {recovery_time:.1f}s")


class CircuitBreaker:
    def __init__(
        self,
        service_name: str,
        config: CircuitBreakerConfig | None = None,
    ):
        self.service_name = service_name
        self.config = config or CircuitBreakerConfig()
        self.state = CircuitState.CLOSED
        self.metrics = CircuitBreakerMetrics()
        self._last_state_change = time.time()

    @property
    def is_open(self) -> bool:
        return self.state == CircuitState.OPEN

    @property
    def recovery_remaining(self) -> float:
        if self.state != CircuitState.OPEN:
            return 0.0
        elapsed = time.time() - self._last_state_change
        return max(0.0, self.config.recovery_timeout - elapsed)

    async def call(
        self,
        func: Callable[..., Coroutine[Any, Any, Any]],
        *args,
        **kwargs,
    ) -> Any:
        if self.state == CircuitState.OPEN:
            if self._should_attempt_reset():
                self._transition_to(CircuitState.HALF_OPEN)
            else:
                raise CircuitBreakerOpenError(
                    self.service_name,
                    self.recovery_remaining,
                )

        self.metrics.total_calls += 1

        try:
            import asyncio
            result = await asyncio.wait_for(
                func(*args, **kwargs),
                timeout=self.config.timeout,
            )
            self._on_success()
            return result
        except Exception as e:
            self._on_failure()
            raise

    def _on_success(self):
        self.metrics.successful_calls += 1
        self.metrics.consecutive_successes += 1
        self.metrics.consecutive_failures = 0

        if self.state == CircuitState.HALF_OPEN:
            if self.metrics.consecutive_successes >= self.config.success_threshold:
                self._transition_to(CircuitState.CLOSED)

    def _on_failure(self):
        self.metrics.failed_calls += 1
        self.metrics.consecutive_failures += 1
        self.metrics.consecutive_successes = 0
        self.metrics.last_failure_time = time.time()

        if self.state == CircuitState.HALF_OPEN:
            self._transition_to(CircuitState.OPEN)
        elif self.metrics.consecutive_failures >= self.config.failure_threshold:
            self._transition_to(CircuitState.OPEN)

    def _should_attempt_reset(self) -> bool:
        if self.state != CircuitState.OPEN:
            return False
        elapsed = time.time() - self._last_state_change
        return elapsed >= self.config.recovery_timeout

    def _transition_to(self, new_state: CircuitState):
        old_state = self.state
        self.state = new_state
        self._last_state_change = time.time()

        if new_state == CircuitState.CLOSED:
            self.metrics.consecutive_failures = 0
            self.metrics.consecutive_successes = 0

        logger.info(f"Circuit breaker {self.service_name}: {old_state.value} -> {new_state.value}")

    def get_status(self) -> dict:
        return {
            "service": self.service_name,
            "state": self.state.value,
            "metrics": self.metrics.model_dump(),
            "recovery_remaining": self.recovery_remaining,
        }

    def reset(self):
        self._transition_to(CircuitState.CLOSED)
        self.metrics = CircuitBreakerMetrics()


class CircuitBreakerRegistry:
    def __init__(self):
        self._breakers: dict[str, CircuitBreaker] = {}

    def get_or_create(
        self,
        service_name: str,
        config: CircuitBreakerConfig | None = None,
    ) -> CircuitBreaker:
        if service_name not in self._breakers:
            self._breakers[service_name] = CircuitBreaker(service_name, config)
        return self._breakers[service_name]

    def get_all(self) -> list[dict]:
        return [b.get_status() for b in self._breakers.values()]

    def reset_all(self):
        for breaker in self._breakers.values():
            breaker.reset()


circuit_breaker_registry = CircuitBreakerRegistry()
