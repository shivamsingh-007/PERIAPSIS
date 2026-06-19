from __future__ import annotations

import time
from contextlib import asynccontextmanager

from fastapi import FastAPI
from pydantic import BaseModel
from sqlalchemy import text

from packages.schemas.database import get_engine, init_engine

from .middleware.tracing import TracingMiddleware, setup_langfuse


class HealthResponse(BaseModel):
    status: str
    timestamp: float
    database: str


@asynccontextmanager
async def lifespan(app: FastAPI):
    database_url = "postgresql+asyncpg://agentic:agentic_dev@localhost:5432/agentic_loop"
    init_engine(database_url)
    setup_langfuse(app)
    yield
    from packages.schemas.database import close_engine

    await close_engine()


app = FastAPI(
    title="Agentic Loop Platform",
    description="Production-grade, governance-first, closed-loop agent platform",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(TracingMiddleware)


@app.get("/health", response_model=HealthResponse)
async def health_check():
    db_status = "disconnected"
    try:
        engine = get_engine()
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        db_status = "connected"
    except Exception:
        db_status = "error"

    return HealthResponse(
        status="ok" if db_status == "connected" else "degraded",
        timestamp=time.time(),
        database=db_status,
    )


@app.get("/")
async def root():
    return {"message": "Agentic Loop Platform", "docs": "/docs"}
