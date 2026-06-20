from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from packages.middleware.shutdown import GracefulShutdownManager


@pytest.fixture
def shutdown_manager():
    return GracefulShutdownManager()


class TestGracefulShutdownManager:
    def test_init(self, shutdown_manager):
        assert shutdown_manager.is_shutting_down is False

    async def test_begin_shutdown(self, shutdown_manager):
        await shutdown_manager.begin_shutdown()
        assert shutdown_manager.is_shutting_down is True

    def test_track_request(self, shutdown_manager):
        shutdown_manager.track_request()
        assert shutdown_manager._active_requests >= 1

    def test_release_request(self, shutdown_manager):
        shutdown_manager.track_request()
        shutdown_manager.release_request()
        assert shutdown_manager._active_requests == 0

    async def test_cleanup_resources(self, shutdown_manager):
        await shutdown_manager.cleanup_resources()

    async def test_wait_for_completion(self, shutdown_manager):
        await shutdown_manager.begin_shutdown()
        await shutdown_manager.wait_for_completion(timeout=1)
