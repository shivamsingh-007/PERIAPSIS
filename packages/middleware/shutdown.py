from __future__ import annotations

import asyncio
import signal
import time
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from sqlalchemy import text

from packages.schemas.database import get_engine, close_engine
from packages.logging.structured import get_logger

logger = get_logger("shutdown")


class GracefulShutdownManager:
    def __init__(self):
        self._shutting_down = False
        self._shutdown_event = asyncio.Event()
        self._active_requests = 0
        self._start_time = time.time()

    @property
    def is_shutting_down(self) -> bool:
        return self._shutting_down

    async def begin_shutdown(self):
        self._shutting_down = True
        logger.info("Graceful shutdown initiated")
        self._shutdown_event.set()

    async def wait_for_completion(self, timeout: int = 30):
        start = time.time()
        while self._active_requests > 0 and (time.time() - start) < timeout:
            logger.info(f"Waiting for {self._active_requests} active requests to complete")
            await asyncio.sleep(0.5)

        if self._active_requests > 0:
            logger.warning(f"Shutdown timeout reached with {self._active_requests} active requests")

    def track_request(self):
        self._active_requests += 1

    def release_request(self):
        self._active_requests -= 1

    async def cleanup_resources(self):
        logger.info("Cleaning up resources")
        try:
            engine = get_engine()
            await close_engine()
            logger.info("Database connections closed")
        except Exception as e:
            logger.error(f"Error closing database: {e}")

        logger.info("Cleanup complete")


shutdown_manager = GracefulShutdownManager()


@asynccontextmanager
async def graceful_shutdown_lifespan(app: FastAPI):
    loop = asyncio.get_event_loop()

    def signal_handler():
        asyncio.create_task(shutdown_manager.begin_shutdown())

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, signal_handler)
        except NotImplementedError:
            pass

    logger.info("Application started")

    yield

    await shutdown_manager.begin_shutdown()
    await shutdown_manager.wait_for_completion()
    await shutdown_manager.cleanup_resources()
    logger.info("Application shut down gracefully")
