from __future__ import annotations

import csv
import io
import json
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from packages.export.run_export import ExportFormat, RunExporter


@pytest.fixture
def exporter():
    return RunExporter()


@pytest.fixture
def mock_get_session():
    with patch("packages.export.run_export.get_session") as mock:
        session = AsyncMock()
        mock.return_value.__aenter__ = AsyncMock(return_value=session)
        mock.return_value.__aexit__ = AsyncMock(return_value=False)
        yield mock


class TestExportFormat:
    def test_json_value(self):
        assert ExportFormat.JSON.value == "json"

    def test_csv_value(self):
        assert ExportFormat.CSV.value == "csv"

    def test_enum_members(self):
        assert len(ExportFormat) == 2


class TestRunExporterCSVExtended:
    def setup_method(self):
        self.exporter = RunExporter()

    def test_to_csv_with_reflections(self):
        data = {
            "run": {"run_id": "abc", "goal": "test"},
            "steps": [],
            "governance_events": [],
            "reflections": [{"reflection_id": "r1", "lesson": "learned"}],
        }
        csv_str = self.exporter._to_csv(data)
        assert "run_id" in csv_str
        assert "abc" in csv_str

    def test_to_csv_multiple_steps(self):
        data = {
            "run": {"run_id": "abc", "goal": "test"},
            "steps": [
                {"step_number": 1, "node_name": "planner"},
                {"step_number": 2, "node_name": "executor"},
                {"step_number": 3, "node_name": "reviewer"},
            ],
            "governance_events": [],
            "reflections": [],
        }
        csv_str = self.exporter._to_csv(data)
        reader = csv.reader(io.StringIO(csv_str))
        rows = list(reader)
        step_rows = [r for r in rows if r[0].startswith("step_")]
        assert len(step_rows) == 6

    def test_to_csv_multiple_governance_events(self):
        data = {
            "run": {"run_id": "abc"},
            "steps": [],
            "governance_events": [
                {"event_id": "e1", "decision": "allow"},
                {"event_id": "e2", "decision": "deny"},
            ],
            "reflections": [],
        }
        csv_str = self.exporter._to_csv(data)
        reader = csv.reader(io.StringIO(csv_str))
        rows = list(reader)
        gov_rows = [r for r in rows if r[0].startswith("governance_")]
        assert len(gov_rows) == 4

    def test_to_csv_empty_data(self):
        data = {"run": {}, "steps": [], "governance_events": [], "reflections": []}
        csv_str = self.exporter._to_csv(data)
        reader = csv.reader(io.StringIO(csv_str))
        rows = list(reader)
        assert rows[0] == ["Section", "Key", "Value"]
        assert len(rows) == 1

    def test_runs_to_csv_multiple_runs(self):
        runs = [
            {
                "run": {"run_id": "r1", "goal": "g1", "state": "SUCCESS", "total_cost": 0.1, "created_at": "2024-01-01"},
                "steps": [{"step_number": 1}, {"step_number": 2}],
            },
            {
                "run": {"run_id": "r2", "goal": "g2", "state": "FAILED", "total_cost": 0.5, "created_at": "2024-01-02"},
                "steps": [],
            },
        ]
        csv_str = self.exporter._runs_to_csv(runs)
        reader = csv.reader(io.StringIO(csv_str))
        rows = list(reader)
        assert len(rows) == 3  # header + 2 runs

    def test_runs_to_csv_empty(self):
        csv_str = self.exporter._runs_to_csv([])
        reader = csv.reader(io.StringIO(csv_str))
        rows = list(reader)
        assert len(rows) == 1  # header only

    def test_runs_to_csv_missing_fields(self):
        runs = [{"run": {}, "steps": []}]
        csv_str = self.exporter._runs_to_csv(runs)
        reader = csv.reader(io.StringIO(csv_str))
        rows = list(reader)
        assert len(rows) == 2


class TestRunExporterExportRun:
    def setup_method(self):
        self.exporter = RunExporter()

    @pytest.mark.asyncio
    async def test_export_run_json(self, mock_get_session):
        session = AsyncMock()
        run_id = uuid.uuid4()
        mock_result = MagicMock()
        mock_result.mappings.return_value.first.return_value = {
            "run_id": run_id,
            "goal": "test",
            "state": "SUCCESS",
        }
        mock_result.mappings.return_value.all.return_value = []
        session.execute = AsyncMock(return_value=mock_result)
        mock_get_session.return_value.__aenter__ = AsyncMock(return_value=session)

        result = await self.exporter.export_run(run_id, ExportFormat.JSON)
        assert isinstance(result, str)
        parsed = json.loads(result)
        assert "run" in parsed
        assert "steps" in parsed
        assert "exported_at" in parsed

    @pytest.mark.asyncio
    async def test_export_run_not_found(self, mock_get_session):
        session = AsyncMock()
        mock_result = MagicMock()
        mock_result.mappings.return_value.first.return_value = None
        session.execute = AsyncMock(return_value=mock_result)
        mock_get_session.return_value.__aenter__ = AsyncMock(return_value=session)

        with pytest.raises(ValueError, match="not found"):
            await self.exporter.export_run(uuid.uuid4())

    @pytest.mark.asyncio
    async def test_export_run_csv(self, mock_get_session):
        session = AsyncMock()
        run_id = uuid.uuid4()
        mock_result = MagicMock()
        mock_result.mappings.return_value.first.return_value = {
            "run_id": run_id,
            "goal": "test",
        }
        mock_result.mappings.return_value.all.return_value = []
        session.execute = AsyncMock(return_value=mock_result)
        mock_get_session.return_value.__aenter__ = AsyncMock(return_value=session)

        result = await self.exporter.export_run(run_id, ExportFormat.CSV)
        assert isinstance(result, str)
        assert "Section" in result


class TestRunExporterBulkExport:
    def setup_method(self):
        self.exporter = RunExporter()

    @pytest.mark.asyncio
    async def test_bulk_export_json(self, mock_get_session):
        session = AsyncMock()
        tenant_id = uuid.uuid4()
        run_id = uuid.uuid4()
        runs_result = MagicMock()
        runs_result.mappings.return_value.all.return_value = [
            {"run_id": run_id, "goal": "test"},
        ]
        steps_result = MagicMock()
        steps_result.mappings.return_value.all.return_value = []

        call_count = 0
        async def mock_execute(query, params=None):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return runs_result
            return steps_result

        session.execute = mock_execute
        mock_get_session.return_value.__aenter__ = AsyncMock(return_value=session)

        result = await self.exporter.export_runs_bulk(tenant_id, ExportFormat.JSON, limit=10)
        assert isinstance(result, str)
        parsed = json.loads(result)
        assert parsed["count"] == 1

    @pytest.mark.asyncio
    async def test_bulk_export_csv(self, mock_get_session):
        session = AsyncMock()
        tenant_id = uuid.uuid4()
        runs_result = MagicMock()
        runs_result.mappings.return_value.all.return_value = []
        steps_result = MagicMock()
        steps_result.mappings.return_value.all.return_value = []

        call_count = 0
        async def mock_execute(query, params=None):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return runs_result
            return steps_result

        session.execute = mock_execute
        mock_get_session.return_value.__aenter__ = AsyncMock(return_value=session)

        result = await self.exporter.export_runs_bulk(tenant_id, ExportFormat.CSV)
        assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_bulk_export_empty(self, mock_get_session):
        session = AsyncMock()
        tenant_id = uuid.uuid4()
        runs_result = MagicMock()
        runs_result.mappings.return_value.all.return_value = []
        steps_result = MagicMock()
        steps_result.mappings.return_value.all.return_value = []

        call_count = 0
        async def mock_execute(query, params=None):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return runs_result
            return steps_result

        session.execute = mock_execute
        mock_get_session.return_value.__aenter__ = AsyncMock(return_value=session)

        result = await self.exporter.export_runs_bulk(tenant_id, ExportFormat.JSON)
        parsed = json.loads(result)
        assert parsed["count"] == 0
