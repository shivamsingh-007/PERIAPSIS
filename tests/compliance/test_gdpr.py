from __future__ import annotations
"""Tests for packages.compliance.gdpr - GDPRManager."""

import pytest

from packages.compliance.gdpr import GDPRManager, GDPRRequest


class TestGDPRManager:
    def setup_method(self):
        self.manager = GDPRManager()

    @pytest.mark.asyncio
    async def test_export_user_data(self):
        result = await self.manager.export_user_data("user1")
        assert result["user_id"] == "user1"
        assert "export_date" in result
        assert result["runs"] == []

    @pytest.mark.asyncio
    async def test_delete_user_data(self):
        result = await self.manager.delete_user_data("user1")
        assert result["user_id"] == "user1"
        assert "runs" in result["deleted_tables"]
        assert "memory" in result["deleted_tables"]

    @pytest.mark.asyncio
    async def test_request_created_on_export(self):
        await self.manager.export_user_data("user1")
        requests = self.manager.list_requests("user1")
        assert len(requests) == 1
        assert requests[0].request_type == "export"
        assert requests[0].status == "completed"

    @pytest.mark.asyncio
    async def test_request_created_on_delete(self):
        await self.manager.delete_user_data("user1")
        requests = self.manager.list_requests("user1")
        assert len(requests) == 1
        assert requests[0].request_type == "deletion"
        assert requests[0].data_deleted is True

    def test_get_request(self):
        req = GDPRRequest(user_id="u1", request_type="export")
        self.manager._requests[str(req.request_id)] = req
        found = self.manager.get_request(str(req.request_id))
        assert found is not None

    def test_get_request_not_found(self):
        assert self.manager.get_request("nonexistent") is None

    def test_list_requests_all(self):
        r1 = GDPRRequest(user_id="u1", request_type="export")
        r2 = GDPRRequest(user_id="u2", request_type="deletion")
        self.manager._requests[str(r1.request_id)] = r1
        self.manager._requests[str(r2.request_id)] = r2
        assert len(self.manager.list_requests()) == 2

    def test_list_requests_by_user(self):
        r1 = GDPRRequest(user_id="u1", request_type="export")
        r2 = GDPRRequest(user_id="u2", request_type="deletion")
        self.manager._requests[str(r1.request_id)] = r1
        self.manager._requests[str(r2.request_id)] = r2
        assert len(self.manager.list_requests(user_id="u1")) == 1
