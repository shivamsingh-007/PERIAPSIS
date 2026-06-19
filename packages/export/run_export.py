from __future__ import annotations

import csv
import io
import json
import uuid
from datetime import datetime
from enum import Enum
from typing import Any

from sqlalchemy import text

from packages.schemas.database import get_session
from packages.logging.structured import get_logger

logger = get_logger("export")


class ExportFormat(str, Enum):
    JSON = "json"
    CSV = "csv"


class RunExporter:
    async def export_run(self, run_id: uuid.UUID, format: ExportFormat = ExportFormat.JSON) -> str | dict:
        run_data = await self._get_run_data(run_id)
        if not run_data:
            raise ValueError(f"Run {run_id} not found")

        steps = await self._get_run_steps(run_id)
        governance = await self._get_governance_events(run_id)
        reflections = await self._get_reflections(run_id)

        full_data = {
            "run": run_data,
            "steps": steps,
            "governance_events": governance,
            "reflections": reflections,
            "exported_at": datetime.utcnow().isoformat(),
        }

        if format == ExportFormat.JSON:
            return json.dumps(full_data, indent=2, default=str)
        elif format == ExportFormat.CSV:
            return self._to_csv(full_data)

        return full_data

    async def export_runs_bulk(
        self,
        tenant_id: uuid.UUID,
        format: ExportFormat = ExportFormat.JSON,
        limit: int = 100,
    ) -> str | dict:
        runs = await self._get_tenant_runs(tenant_id, limit)

        export_data = []
        for run in runs:
            run_id = run["run_id"]
            steps = await self._get_run_steps(run_id)
            export_data.append({
                "run": run,
                "steps": steps,
            })

        if format == ExportFormat.JSON:
            return json.dumps({
                "runs": export_data,
                "count": len(export_data),
                "exported_at": datetime.utcnow().isoformat(),
            }, indent=2, default=str)
        elif format == ExportFormat.CSV:
            return self._runs_to_csv(export_data)

        return {"runs": export_data, "count": len(export_data)}

    def _to_csv(self, data: dict) -> str:
        output = io.StringIO()
        writer = csv.writer(output)

        writer.writerow(["Section", "Key", "Value"])
        for key, value in data.get("run", {}).items():
            writer.writerow(["run", key, str(value)])

        for i, step in enumerate(data.get("steps", [])):
            for key, value in step.items():
                writer.writerow([f"step_{i}", key, str(value)])

        for i, event in enumerate(data.get("governance_events", [])):
            for key, value in event.items():
                writer.writerow([f"governance_{i}", key, str(value)])

        return output.getvalue()

    def _runs_to_csv(self, runs: list[dict]) -> str:
        output = io.StringIO()
        writer = csv.writer(output)

        writer.writerow(["Run ID", "Goal", "State", "Cost", "Steps Count", "Created At"])
        for item in runs:
            run = item["run"]
            writer.writerow([
                run.get("run_id"),
                run.get("goal"),
                run.get("state"),
                run.get("total_cost"),
                len(item.get("steps", [])),
                run.get("created_at"),
            ])

        return output.getvalue()

    async def _get_run_data(self, run_id: uuid.UUID) -> dict | None:
        async with get_session() as session:
            result = await session.execute(
                text("SELECT * FROM runs WHERE run_id = :run_id"),
                {"run_id": run_id},
            )
            row = result.mappings().first()
            return dict(row) if row else None

    async def _get_run_steps(self, run_id: uuid.UUID) -> list[dict]:
        async with get_session() as session:
            result = await session.execute(
                text("SELECT * FROM run_steps WHERE run_id = :run_id ORDER BY step_number"),
                {"run_id": run_id},
            )
            return [dict(row) for row in result.mappings().all()]

    async def _get_governance_events(self, run_id: uuid.UUID) -> list[dict]:
        async with get_session() as session:
            result = await session.execute(
                text("SELECT * FROM governance_events WHERE run_id = :run_id"),
                {"run_id": run_id},
            )
            return [dict(row) for row in result.mappings().all()]

    async def _get_reflections(self, run_id: uuid.UUID) -> list[dict]:
        async with get_session() as session:
            result = await session.execute(
                text("SELECT * FROM reflections WHERE run_id = :run_id"),
                {"run_id": run_id},
            )
            return [dict(row) for row in result.mappings().all()]

    async def _get_tenant_runs(self, tenant_id: uuid.UUID, limit: int) -> list[dict]:
        async with get_session() as session:
            result = await session.execute(
                text(
                    """
                    SELECT * FROM runs
                    WHERE tenant_id = :tenant_id
                    ORDER BY created_at DESC
                    LIMIT :limit
                    """
                ),
                {"tenant_id": tenant_id, "limit": limit},
            )
            return [dict(row) for row in result.mappings().all()]


run_exporter = RunExporter()
