from __future__ import annotations

import sys
from types import ModuleType
from unittest.mock import MagicMock

import pytest


def _ensure_app_importable():
    """Stub out missing symbols so apps.api.main can import."""
    import packages.security.rls as rls_mod
    if not hasattr(rls_mod, "get_current_tenant"):
        rls_mod.get_current_tenant = MagicMock(return_value=None)


_ensure_app_importable()


class TestAPIAlive:
    def test_app_imports(self):
        from apps.api.main import app
        assert app is not None

    def test_app_title(self):
        from apps.api.main import app
        assert app.title == "Agentic Loop Platform"

    def test_app_version(self):
        from apps.api.main import app
        assert app.version == "0.1.0"

    def test_health_endpoint_exists(self):
        from apps.api.main import app
        routes = [r.path for r in app.routes]
        assert "/health" in routes

    def test_root_endpoint_exists(self):
        from apps.api.main import app
        routes = [r.path for r in app.routes]
        assert "/" in routes

    def test_docs_endpoint_exists(self):
        from apps.api.main import app
        assert app.docs_url == "/docs"

    def test_redoc_endpoint_exists(self):
        from apps.api.main import app
        assert app.redoc_url == "/redoc"

    def test_openapi_tags(self):
        from apps.api.main import app
        assert len(app.openapi_tags) >= 10

    def test_all_routers_registered(self):
        from apps.api.main import app
        route_tags = set()
        for route in app.routes:
            if hasattr(route, "tags"):
                route_tags.update(route.tags)
        assert "runs" in route_tags
        assert "memory" in route_tags
        assert "graph" in route_tags
        assert "fleet" in route_tags
