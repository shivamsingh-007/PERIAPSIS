"""Tests for Supabase client wrapper."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


class TestGetSupabaseClient:
    def setup_method(self):
        import packages.infrastructure.supabase_client as mod
        mod._client = None  # reset singleton

    @patch.dict("os.environ", {}, clear=True)
    def test_returns_none_when_env_missing(self):
        from packages.infrastructure.supabase_client import get_supabase_client
        result = get_supabase_client()
        assert result is None

    @patch.dict("os.environ", {"SUPABASE_URL": "", "SUPABASE_KEY": ""}, clear=True)
    def test_returns_none_when_env_empty(self):
        from packages.infrastructure.supabase_client import get_supabase_client
        result = get_supabase_client()
        assert result is None

    @patch.dict(
        "os.environ",
        {"SUPABASE_URL": "https://test.supabase.co", "SUPABASE_KEY": "test-key"},
        clear=True,
    )
    @patch("supabase.create_client")
    def test_creates_client_when_env_set(self, mock_create):
        from packages.infrastructure.supabase_client import get_supabase_client
        mock_client = MagicMock()
        mock_create.return_value = mock_client
        result = get_supabase_client()
        assert result is mock_client
        mock_create.assert_called_once_with("https://test.supabase.co", "test-key")

    @patch.dict(
        "os.environ",
        {"SUPABASE_URL": "https://test.supabase.co", "SUPABASE_KEY": "test-key"},
        clear=True,
    )
    @patch("supabase.create_client")
    def test_returns_singleton(self, mock_create):
        from packages.infrastructure.supabase_client import get_supabase_client
        mock_create.return_value = MagicMock()
        c1 = get_supabase_client()
        c2 = get_supabase_client()
        assert c1 is c2
        assert mock_create.call_count == 1

    @patch.dict(
        "os.environ",
        {"SUPABASE_URL": "https://test.supabase.co", "SUPABASE_KEY": "test-key"},
        clear=True,
    )
    @patch("supabase.create_client", side_effect=ImportError)
    def test_returns_none_on_import_error(self, mock_create):
        from packages.infrastructure.supabase_client import get_supabase_client
        result = get_supabase_client()
        assert result is None

    @patch.dict(
        "os.environ",
        {"SUPABASE_URL": "https://test.supabase.co", "SUPABASE_KEY": "test-key"},
        clear=True,
    )
    @patch("supabase.create_client", side_effect=RuntimeError("connection failed"))
    def test_returns_none_on_connection_error(self, mock_create):
        from packages.infrastructure.supabase_client import get_supabase_client
        result = get_supabase_client()
        assert result is None


class TestSupabaseHealthCheck:
    def setup_method(self):
        import packages.infrastructure.supabase_client as mod
        mod._client = None

    @patch("packages.infrastructure.supabase_client.get_supabase_client", return_value=None)
    @pytest.mark.asyncio
    async def test_unavailable_when_no_client(self, mock_get):
        from packages.infrastructure.supabase_client import supabase_health_check
        result = await supabase_health_check()
        assert result["status"] == "unavailable"

    @patch("packages.infrastructure.supabase_client.get_supabase_client")
    @pytest.mark.asyncio
    async def test_healthy_when_query_succeeds(self, mock_get):
        from packages.infrastructure.supabase_client import supabase_health_check
        mock_client = MagicMock()
        mock_table = MagicMock()
        mock_client.table.return_value = mock_table
        mock_table.select.return_value = mock_table
        mock_table.limit.return_value = mock_table
        mock_table.execute.return_value = MagicMock(data=[])
        mock_get.return_value = mock_client
        result = await supabase_health_check()
        assert result["status"] == "healthy"

    @patch("packages.infrastructure.supabase_client.get_supabase_client")
    @pytest.mark.asyncio
    async def test_unhealthy_on_exception(self, mock_get):
        from packages.infrastructure.supabase_client import supabase_health_check
        mock_client = MagicMock()
        mock_table = MagicMock()
        mock_client.table.return_value = mock_table
        mock_table.select.return_value = mock_table
        mock_table.limit.return_value = mock_table
        mock_table.execute.side_effect = RuntimeError("connection refused")
        mock_get.return_value = mock_client
        result = await supabase_health_check()
        assert result["status"] == "unhealthy"
        assert "connection refused" in result["error"]


class TestSupabaseRepository:
    def setup_method(self):
        import packages.infrastructure.supabase_client as mod
        mod._client = None

    @patch("packages.infrastructure.supabase_client.get_supabase_client", return_value=None)
    def test_raises_when_no_client(self, mock_get):
        from packages.infrastructure.supabase_client import SupabaseRepository
        repo = SupabaseRepository("test_table")
        with pytest.raises(RuntimeError, match="Supabase client not initialized"):
            repo.table

    @patch("packages.infrastructure.supabase_client.get_supabase_client")
    def test_table_property_returns_table(self, mock_get):
        from packages.infrastructure.supabase_client import SupabaseRepository
        mock_client = MagicMock()
        mock_get.return_value = mock_client
        repo = SupabaseRepository("runs")
        _ = repo.table
        mock_client.table.assert_called_once_with("runs")
