from __future__ import annotations

import json
import uuid
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from packages.runtime.checkpoint import CheckpointStore


@pytest.fixture
def store():
    return CheckpointStore()


def _mock_engine():
    """Create a mock engine that supports both begin() and connect()."""
    mock_conn = AsyncMock()
    mock_conn.execute = AsyncMock()
    mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_conn.__aexit__ = AsyncMock(return_value=False)

    mock_engine = MagicMock()
    mock_engine.begin.return_value = mock_conn
    mock_engine.connect.return_value = mock_conn
    return mock_engine, mock_conn


class TestCheckpointStore:
    @pytest.mark.asyncio
    async def test_save_checkpoint(self, store):
        mock_engine, mock_conn = _mock_engine()
        mock_result = MagicMock()
        mock_result.rowcount = 1
        mock_conn.execute.return_value = mock_result

        with patch("packages.runtime.checkpoint.get_engine", return_value=mock_engine):
            result = await store.save(
                run_id=uuid.uuid4(),
                tenant_id=uuid.uuid4(),
                state={"goal": "test", "step": 1},
            )
            assert result is not None
            assert result.startswith("cp_")

    @pytest.mark.asyncio
    async def test_load_checkpoint(self, store):
        mock_engine, mock_conn = _mock_engine()
        state_data = {"goal": "test", "step": 1}
        mock_result = MagicMock()
        mock_result.mappings.return_value.first.return_value = {
            "input_state_jsonb": json.dumps(state_data),
        }
        mock_conn.execute.return_value = mock_result

        with patch("packages.runtime.checkpoint.get_engine", return_value=mock_engine):
            result = await store.load(run_id=uuid.uuid4(), tenant_id=uuid.uuid4())
            assert result is not None
            assert result["goal"] == "test"

    @pytest.mark.asyncio
    async def test_load_not_found(self, store):
        mock_engine, mock_conn = _mock_engine()
        mock_result = MagicMock()
        mock_result.mappings.return_value.first.return_value = None
        mock_conn.execute.return_value = mock_result

        with patch("packages.runtime.checkpoint.get_engine", return_value=mock_engine):
            result = await store.load(run_id=uuid.uuid4(), tenant_id=uuid.uuid4())
            assert result is None

    @pytest.mark.asyncio
    async def test_diff_checkpoints(self, store):
        mock_engine, mock_conn = _mock_engine()
        state_a = {"goal": "test", "step": 1, "status": "running"}
        state_b = {"goal": "test", "step": 2, "status": "running"}

        mock_result = MagicMock()
        mock_result.mappings.return_value.all.return_value = [
            {"step_number": 1, "input_state_jsonb": json.dumps(state_a)},
            {"step_number": 2, "input_state_jsonb": json.dumps(state_b)},
        ]
        mock_conn.execute.return_value = mock_result

        with patch("packages.runtime.checkpoint.get_engine", return_value=mock_engine):
            result = await store.diff(
                run_id=uuid.uuid4(),
                tenant_id=uuid.uuid4(),
                step_a=1,
                step_b=2,
            )
            assert "step" in result
            assert result["step"] == {"from": 1, "to": 2}
