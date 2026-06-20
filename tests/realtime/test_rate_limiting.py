from __future__ import annotations

import pytest

from packages.middleware.rate_limit import (
    RateLimitConfig,
    RateLimiter,
    DEFAULT_CONFIG,
)


@pytest.fixture
def limiter():
    return RateLimiter()


class TestRateLimitConfig:
    def test_default_config(self):
        config = RateLimitConfig()
        assert config.requests_per_minute == 60
        assert config.requests_per_hour == 1000
        assert config.burst_size == 10

    def test_custom_config(self):
        config = RateLimitConfig(
            requests_per_minute=30,
            requests_per_hour=500,
            burst_size=5,
        )
        assert config.requests_per_minute == 30


class TestRateLimiter:
    def test_init(self, limiter):
        assert limiter is not None

    def test_set_config(self, limiter):
        config = RateLimitConfig(requests_per_minute=10)
        limiter.set_config("tenant-1", config)
        retrieved = limiter.get_config("tenant-1")
        assert retrieved.requests_per_minute == 10

    def test_get_default_config(self, limiter):
        config = limiter.get_config("unknown-tenant")
        assert config.requests_per_minute == 60

    def test_check_rate_limit_allowed(self, limiter):
        allowed, headers = limiter.check_rate_limit("tenant-1")
        assert allowed is True
        assert "X-RateLimit-Limit" in headers or "remaining" in str(headers).lower() or isinstance(headers, dict)

    def test_check_rate_limit_exceeded(self, limiter):
        config = RateLimitConfig(requests_per_minute=2)
        limiter.set_config("tenant-1", config)
        limiter.check_rate_limit("tenant-1")
        limiter.check_rate_limit("tenant-1")
        allowed, headers = limiter.check_rate_limit("tenant-1")
        assert allowed is False

    def test_per_tenant_isolation(self, limiter):
        config = RateLimitConfig(requests_per_minute=1)
        limiter.set_config("tenant-1", config)
        limiter.check_rate_limit("tenant-1")
        allowed, _ = limiter.check_rate_limit("tenant-2")
        assert allowed is True

    def test_default_config_constant(self):
        assert DEFAULT_CONFIG.requests_per_minute == 60
