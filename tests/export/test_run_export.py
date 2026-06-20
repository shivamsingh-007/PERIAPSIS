from __future__ import annotations
"""Tests for packages.export.run_export - CSV conversion logic."""

import csv
import io

import pytest

from packages.export.run_export import ExportFormat, RunExporter


class TestRunExporterCSV:
    def setup_method(self):
        self.exporter = RunExporter()

    def test_to_csv(self):
        data = {
            "run": {"run_id": "abc", "goal": "test", "state": "SUCCESS"},
            "steps": [{"step_number": 1, "node_name": "execute"}],
            "governance_events": [{"event_id": "e1", "decision": "allow"}],
            "reflections": [],
        }
        csv_str = self.exporter._to_csv(data)
        reader = csv.reader(io.StringIO(csv_str))
        rows = list(reader)
        assert rows[0] == ["Section", "Key", "Value"]
        assert len(rows) > 1

    def test_runs_to_csv(self):
        runs = [
            {
                "run": {"run_id": "r1", "goal": "test", "state": "SUCCESS", "total_cost": 0.5, "created_at": "2024-01-01"},
                "steps": [{"step_number": 1}],
            }
        ]
        csv_str = self.exporter._runs_to_csv(runs)
        reader = csv.reader(io.StringIO(csv_str))
        rows = list(reader)
        assert rows[0] == ["Run ID", "Goal", "State", "Cost", "Steps Count", "Created At"]
        assert len(rows) == 2

    def test_export_format_enum(self):
        assert ExportFormat.JSON.value == "json"
        assert ExportFormat.CSV.value == "csv"
