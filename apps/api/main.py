from __future__ import annotations

import time
from contextlib import asynccontextmanager

from fastapi import FastAPI
from pydantic import BaseModel
from sqlalchemy import text

from packages.schemas.database import get_engine, init_engine
from packages.logging.structured import setup_structured_logging, get_logger
from packages.middleware.idempotency import IdempotencyMiddleware
from packages.middleware.rate_limit import RateLimitMiddleware
from packages.middleware.shutdown import graceful_shutdown_lifespan
from packages.security.rls import RowLevelSecurityMiddleware
from packages.security.rbac import RBACMiddleware

from .middleware.tracing import TracingMiddleware, setup_langfuse
from .routes.approvals import router as approvals_router
from .routes.export import router as export_router
from .routes.harness import router as harness_router
from .routes.memory import router as memory_router
from .routes.runs import router as runs_router
from .routes.scheduler_api import router as scheduler_router
from .routes.webhook_api import router as webhook_router
from .routes.websocket import router as ws_router
from .routes.resilience import router as resilience_router
from .routes.fleet import router as fleet_router

logger = get_logger("api")


class HealthResponse(BaseModel):
    status: str
    timestamp: float
    database: str


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_structured_logging()
    database_url = "postgresql+asyncpg://agentic:agentic_dev@localhost:5432/agentic_loop"
    init_engine(database_url)
    setup_langfuse(app)
    logger.info("Application starting")
    yield
    from packages.schemas.database import close_engine

    logger.info("Application shutting down")
    await close_engine()


app = FastAPI(
    title="Agentic Loop Platform",
    description="Production-grade, governance-first, closed-loop agent platform",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(TracingMiddleware)
app.add_middleware(IdempotencyMiddleware)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(RowLevelSecurityMiddleware)
app.add_middleware(RBACMiddleware)

app.include_router(runs_router)
app.include_router(approvals_router)
app.include_router(memory_router)
app.include_router(harness_router)
app.include_router(export_router)
app.include_router(webhook_router)
app.include_router(scheduler_router)
app.include_router(ws_router)
app.include_router(resilience_router)
app.include_router(fleet_router)


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
