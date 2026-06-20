"""Supabase client wrapper for the agentic loop platform.

Provides:
- Lazy-initialized Supabase client from environment variables
- Typed helpers for common operations (auth, storage, edge functions)
- Health check integration
"""

from __future__ import annotations

import os
from typing import Any

from packages.logging.structured import get_logger

logger = get_logger("supabase")

_client = None


def get_supabase_client():
    """Get or create the Supabase client singleton.

    Reads SUPABASE_URL and SUPABASE_KEY from environment.
    Returns None if env vars are missing or supabase package not installed.
    """
    global _client
    if _client is not None:
        return _client

    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_KEY")

    if not url or not key:
        logger.warning("SUPABASE_URL or SUPABASE_KEY not set, Supabase client unavailable")
        return None

    try:
        from supabase import create_client

        _client = create_client(url, key)
        logger.info("Supabase client initialized", extra={"url": url})
        return _client
    except ImportError:
        logger.warning("supabase package not installed. Run: pip install supabase")
        return None
    except Exception as exc:
        logger.error("Failed to initialize Supabase client", extra={"error": str(exc)})
        return None


async def supabase_health_check() -> dict[str, Any]:
    """Check Supabase connectivity for health endpoint."""
    client = get_supabase_client()
    if client is None:
        return {"status": "unavailable", "error": "client not initialized"}

    try:
        # Lightweight query to verify connectivity
        client.table("health_check").select("*").limit(1).execute()
        return {"status": "healthy"}
    except Exception as exc:
        return {"status": "unhealthy", "error": str(exc)}


class SupabaseRepository:
    """Base class for Supabase-backed repositories.

    Provides typed access to a specific table with common CRUD operations.
    Subclass and add domain-specific methods.
    """

    def __init__(self, table_name: str):
        self.table_name = table_name

    def _get_client(self):
        client = get_supabase_client()
        if client is None:
            raise RuntimeError("Supabase client not initialized")
        return client

    @property
    def table(self):
        return self._get_client().table(self.table_name)

    async def get_by_id(self, record_id: Any) -> dict | None:
        """Fetch a single record by its primary key."""
        try:
            result = self.table.select("*").eq("id", record_id).limit(1).execute()
            rows = result.data
            return rows[0] if rows else None
        except Exception as exc:
            logger.error("get_by_id failed", extra={"table": self.table_name, "error": str(exc)})
            return None

    async def list_all(self, limit: int = 100, offset: int = 0) -> list[dict]:
        """List records with pagination."""
        try:
            result = (
                self.table.select("*")
                .range(offset, offset + limit - 1)
                .execute()
            )
            return result.data or []
        except Exception as exc:
            logger.error("list_all failed", extra={"table": self.table_name, "error": str(exc)})
            return []

    async def insert(self, data: dict) -> dict | None:
        """Insert a record and return it."""
        try:
            result = self.table.insert(data).execute()
            rows = result.data
            return rows[0] if rows else None
        except Exception as exc:
            logger.error("insert failed", extra={"table": self.table_name, "error": str(exc)})
            return None

    async def update(self, record_id: Any, data: dict) -> dict | None:
        """Update a record by ID and return it."""
        try:
            result = self.table.update(data).eq("id", record_id).execute()
            rows = result.data
            return rows[0] if rows else None
        except Exception as exc:
            logger.error("update failed", extra={"table": self.table_name, "error": str(exc)})
            return None

    async def delete(self, record_id: Any) -> bool:
        """Delete a record by ID."""
        try:
            self.table.delete().eq("id", record_id).execute()
            return True
        except Exception as exc:
            logger.error("delete failed", extra={"table": self.table_name, "error": str(exc)})
            return False

    async def query(
        self,
        filters: dict[str, Any] | None = None,
        order_by: str | None = None,
        ascending: bool = True,
        limit: int = 100,
    ) -> list[dict]:
        """Query with filters, ordering, and limit."""
        try:
            q = self.table.select("*")
            if filters:
                for col, val in filters.items():
                    if isinstance(val, list):
                        q = q.in_(col, val)
                    else:
                        q = q.eq(col, val)
            if order_by:
                q = q.order(order_by, desc=not ascending)
            q = q.limit(limit)
            result = q.execute()
            return result.data or []
        except Exception as exc:
            logger.error("query failed", extra={"table": self.table_name, "error": str(exc)})
            return []
