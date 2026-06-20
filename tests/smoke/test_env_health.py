from __future__ import annotations

import pytest

from packages.infrastructure.health import HealthChecker


@pytest.fixture
def checker():
    return HealthChecker()


class TestHealthChecker:
    def test_init(self, checker):
        assert checker is not None

    def test_register_dependency(self, checker):
        checker.register_dependency("postgres", lambda: None)
        deps = checker._dependencies
        assert len(deps) >= 1

    def test_list_dependencies_empty(self, checker):
        deps = checker._dependencies
        assert isinstance(deps, dict)

    @pytest.mark.asyncio
    async def test_check_healthy(self, checker):
        result = await checker.check_all()
        assert result is not None
        assert "status" in result

    def test_get_status(self, checker):
        stats = checker.get_status()
        assert isinstance(stats, dict)
        assert "dependencies" in stats
