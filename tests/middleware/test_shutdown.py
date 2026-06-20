from __future__ import annotations
"""Tests for packages.middleware.shutdown - GracefulShutdownManager."""

import pytest

from packages.middleware.shutdown import GracefulShutdownManager


class TestGracefulShutdownManager:
    def setup_method(self):
        self.manager = GracefulShutdownManager()

    def test_initial_state(self):
        assert self.manager.is_shutting_down is False

    @pytest.mark.asyncio
    async def test_begin_shutdown(self):
        await self.manager.begin_shutdown()
        assert self.manager.is_shutting_down is True

    def test_track_release_request(self):
        self.manager.track_request()
        assert self.manager._active_requests == 1
        self.manager.release_request()
        assert self.manager._active_requests == 0

    @pytest.mark.asyncio
    async def test_wait_for_completion_no_active(self):
        await self.manager.wait_for_completion(timeout=1)
        # Should return immediately since no active requests
        assert self.manager._active_requests == 0
