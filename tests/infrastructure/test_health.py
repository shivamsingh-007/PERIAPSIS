from __future__ import annotations
"""Tests for packages.infrastructure.health - HealthChecker."""

import pytest

from packages.infrastructure.health import DependencyHealth, HealthChecker, HealthStatus


class TestHealthChecker:
    def setup_method(self):
        self.checker = HealthChecker()

    def test_register_dependency(self):
        async def check():
            pass

        self.checker.register_dependency("db", check)
        assert "db" in self.checker._dependencies

    @pytest.mark.asyncio
    async def test_check_all_healthy(self):
        async def check_db():
            pass

        async def check_redis():
            pass

        self.checker.register_dependency("db", check_db)
        self.checker.register_dependency("redis", check_redis)
        result = await self.checker.check_all()
        assert result["status"] == "healthy"
        assert len(result["dependencies"]) == 2

    @pytest.mark.asyncio
    async def test_check_all_unhealthy(self):
        async def check_db():
            pass

        async def check_redis():
            raise ConnectionError("Redis down")

        self.checker.register_dependency("db", check_db)
        self.checker.register_dependency("redis", check_redis)
        result = await self.checker.check_all()
        assert result["status"] == "unhealthy"
        assert result["dependencies"]["redis"]["status"] == "unhealthy"
        assert "Redis down" in result["dependencies"]["redis"]["error"]

    @pytest.mark.asyncio
    async def test_check_all_latency(self):
        async def check():
            pass

        self.checker.register_dependency("db", check)
        result = await self.checker.check_all()
        assert result["dependencies"]["db"]["latency_ms"] >= 0

    def test_get_status_empty(self):
        result = self.checker.get_status()
        assert result["dependencies"] == {}
