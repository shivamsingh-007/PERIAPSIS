from __future__ import annotations
"""Tests for packages.middleware.rate_limit - RateLimiter."""

import time

import pytest

from packages.middleware.rate_limit import RateLimitConfig, RateLimiter


class TestRateLimitConfig:
    def test_defaults(self):
        config = RateLimitConfig()
        assert config.requests_per_minute == 60
        assert config.requests_per_hour == 1000
        assert config.burst_size == 10

    def test_custom(self):
        config = RateLimitConfig(requests_per_minute=10, requests_per_hour=100)
        assert config.requests_per_minute == 10


class TestRateLimiter:
    def setup_method(self):
        self.limiter = RateLimiter()

    def test_first_request_allowed(self):
        allowed, info = self.limiter.check_rate_limit("tenant1")
        assert allowed is True
        assert info["remaining"] >= 0

    def test_set_and_get_config(self):
        config = RateLimitConfig(requests_per_minute=5)
        self.limiter.set_config("tenant1", config)
        assert self.limiter.get_config("tenant1").requests_per_minute == 5

    def test_default_config(self):
        config = self.limiter.get_config("unknown-tenant")
        assert config.requests_per_minute == 60

    def test_minute_limit_exceeded(self):
        config = RateLimitConfig(requests_per_minute=3, requests_per_hour=10000)
        self.limiter.set_config("tenant1", config)

        # First 3 should pass
        for _ in range(3):
            allowed, _ = self.limiter.check_rate_limit("tenant1")
            assert allowed is True

        # 4th should fail
        allowed, info = self.limiter.check_rate_limit("tenant1")
        assert allowed is False
        assert "Rate limit exceeded (per minute)" in info["error"]
