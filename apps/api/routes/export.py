from __future__ import annotations

import uuid
from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse

from packages.export.run_export import run_exporter, ExportFormat

router = APIRouter(prefix="/export", tags=["export"])


@router.get("/runs/{run_id}")
async def export_run(
    run_id: uuid.UUID,
    format: ExportFormat = Query(ExportFormat.JSON),
):
    try:
        data = await run_exporter.export_run(run_id, format)

        if format == ExportFormat.JSON:
            return StreamingResponse(
                iter([data]),
                media_type="application/json",
                headers={"Content-Disposition": f"attachment; filename=run_{run_id}.json"},
            )
        elif format == ExportFormat.CSV:
            return StreamingResponse(
                iter([data]),
                media_type="text/csv",
                headers={"Content-Disposition": f"attachment; filename=run_{run_id}.csv"},
            )
    except ValueError as e:
        return {"error": str(e)}


@router.get("/runs/bulk/{tenant_id}")
async def export_runs_bulk(
    tenant_id: uuid.UUID,
    format: ExportFormat = Query(ExportFormat.JSON),
    limit: int = Query(100, le=1000),
):
    data = await run_exporter.export_runs_bulk(tenant_id, format, limit)

    if format == ExportFormat.JSON:
        return StreamingResponse(
            iter([data]),
            media_type="application/json",
            headers={"Content-Disposition": f"attachment; filename=runs_{tenant_id}.json"},
        )
    elif format == ExportFormat.CSV:
        return StreamingResponse(
            iter([data]),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=runs_{tenant_id}.csv"},
        )
