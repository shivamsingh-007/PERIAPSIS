from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from packages.runtime.templates import (
    RunTemplate,
    TemplateManager,
)


class TestRunTemplate:
    def test_create_template(self):
        tmpl = RunTemplate(
            template_id=uuid.uuid4(),
            tenant_id=uuid.uuid4(),
            name="test-template",
            description="A test template",
            goal="Test goal",
            risk_tier="low",
            budget_limit=5.0,
            max_iterations=10,
        )
        assert tmpl.name == "test-template"
        assert tmpl.goal == "Test goal"

    def test_template_defaults(self):
        tmpl = RunTemplate(
            template_id=uuid.uuid4(),
            tenant_id=uuid.uuid4(),
            name="t",
            description="d",
            goal="g",
            risk_tier="low",
            budget_limit=5.0,
            max_iterations=10,
        )
        assert tmpl.tool_whitelist == []
        assert tmpl.config == {}


def _mock_session():
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.mappings.return_value.first.return_value = None
    mock_result.mappings.return_value.all.return_value = []
    mock_result.rowcount = 1
    mock_session.execute.return_value = mock_result
    return mock_session


class TestTemplateManager:
    @pytest.mark.asyncio
    async def test_create_template(self):
        mgr = TemplateManager()
        mock_session = _mock_session()
        with patch("packages.runtime.templates.get_session") as mock_get:
            mock_get.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_get.return_value.__aexit__ = AsyncMock(return_value=False)
            tmpl = await mgr.create_template(
                tenant_id=uuid.uuid4(),
                name="auth-refactor",
                description="Refactor auth",
                goal="Refactor authentication",
                risk_tier="medium",
                budget_limit=10.0,
                max_iterations=20,
            )
        assert tmpl.name == "auth-refactor"
        assert tmpl.template_id is not None

    @pytest.mark.asyncio
    async def test_get_template(self):
        mgr = TemplateManager()
        tid = uuid.uuid4()
        tmpl_id = uuid.uuid4()

        mock_session = _mock_session()
        mock_result = MagicMock()
        row = {
            "template_id": tmpl_id,
            "tenant_id": tid,
            "name": "t",
            "description": "d",
            "goal": "g",
            "risk_tier": "low",
            "budget_limit": 5.0,
            "max_iterations": 10,
            "tool_whitelist": "[]",
            "config": "{}",
            "created_at": "2025-01-01",
            "updated_at": "2025-01-01",
        }
        mock_result.mappings.return_value.first.return_value = row
        mock_session.execute.return_value = mock_result

        with patch("packages.runtime.templates.get_session") as mock_get:
            mock_get.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_get.return_value.__aexit__ = AsyncMock(return_value=False)
            retrieved = await mgr.get_template(tmpl_id)
        assert retrieved is not None
        assert retrieved.name == "t"

    @pytest.mark.asyncio
    async def test_get_template_not_found(self):
        mgr = TemplateManager()
        mock_session = _mock_session()
        with patch("packages.runtime.templates.get_session") as mock_get:
            mock_get.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_get.return_value.__aexit__ = AsyncMock(return_value=False)
            result = await mgr.get_template(uuid.uuid4())
        assert result is None

    @pytest.mark.asyncio
    async def test_list_templates(self):
        mgr = TemplateManager()
        tid = uuid.uuid4()
        mock_session = _mock_session()
        mock_result = MagicMock()
        mock_result.mappings.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result

        with patch("packages.runtime.templates.get_session") as mock_get:
            mock_get.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_get.return_value.__aexit__ = AsyncMock(return_value=False)
            result = await mgr.list_templates(tid)
        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_list_templates_other_tenant(self):
        mgr = TemplateManager()
        mock_session = _mock_session()
        mock_result = MagicMock()
        mock_result.mappings.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result

        with patch("packages.runtime.templates.get_session") as mock_get:
            mock_get.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_get.return_value.__aexit__ = AsyncMock(return_value=False)
            result = await mgr.list_templates(uuid.uuid4())
        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_update_template(self):
        mgr = TemplateManager()
        tmpl_id = uuid.uuid4()
        mock_session = _mock_session()
        mock_result = MagicMock()
        mock_result.rowcount = 1
        mock_session.execute.return_value = mock_result

        with patch("packages.runtime.templates.get_session") as mock_get:
            mock_get.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_get.return_value.__aexit__ = AsyncMock(return_value=False)
            updated = await mgr.update_template(tmpl_id, name="updated")
        assert updated is True

    @pytest.mark.asyncio
    async def test_delete_template(self):
        mgr = TemplateManager()
        tmpl_id = uuid.uuid4()
        mock_session = _mock_session()
        mock_result = MagicMock()
        mock_result.rowcount = 1
        mock_session.execute.return_value = mock_result

        with patch("packages.runtime.templates.get_session") as mock_get:
            mock_get.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_get.return_value.__aexit__ = AsyncMock(return_value=False)
            result = await mgr.delete_template(tmpl_id)
        assert result is True

    @pytest.mark.asyncio
    async def test_delete_not_found(self):
        mgr = TemplateManager()
        mock_session = _mock_session()
        mock_result = MagicMock()
        mock_result.rowcount = 0
        mock_session.execute.return_value = mock_result

        with patch("packages.runtime.templates.get_session") as mock_get:
            mock_get.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_get.return_value.__aexit__ = AsyncMock(return_value=False)
            result = await mgr.delete_template(uuid.uuid4())
        assert result is False

    @pytest.mark.asyncio
    async def test_create_run_from_template(self):
        mgr = TemplateManager()
        tid = uuid.uuid4()
        tmpl_id = uuid.uuid4()

        mock_session = _mock_session()
        mock_result = MagicMock()
        row = {
            "template_id": tmpl_id,
            "tenant_id": tid,
            "name": "t",
            "description": "d",
            "goal": "Refactor auth",
            "risk_tier": "low",
            "budget_limit": 5.0,
            "max_iterations": 10,
            "tool_whitelist": "[]",
            "config": "{}",
            "created_at": "2025-01-01",
            "updated_at": "2025-01-01",
        }
        mock_result.mappings.return_value.first.return_value = row
        mock_session.execute.return_value = mock_result

        with patch("packages.runtime.templates.get_session") as mock_get:
            mock_get.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_get.return_value.__aexit__ = AsyncMock(return_value=False)
            run_config = await mgr.create_run_from_template(tmpl_id)
        assert run_config is not None
        assert run_config["goal"] == "Refactor auth"
        assert run_config["risk_tier"] == "low"

    @pytest.mark.asyncio
    async def test_create_run_from_template_with_overrides(self):
        mgr = TemplateManager()
        tid = uuid.uuid4()
        tmpl_id = uuid.uuid4()

        mock_session = _mock_session()
        mock_result = MagicMock()
        row = {
            "template_id": tmpl_id,
            "tenant_id": tid,
            "name": "t",
            "description": "d",
            "goal": "Original goal",
            "risk_tier": "low",
            "budget_limit": 5.0,
            "max_iterations": 10,
            "tool_whitelist": "[]",
            "config": "{}",
            "created_at": "2025-01-01",
            "updated_at": "2025-01-01",
        }
        mock_result.mappings.return_value.first.return_value = row
        mock_session.execute.return_value = mock_result

        with patch("packages.runtime.templates.get_session") as mock_get:
            mock_get.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_get.return_value.__aexit__ = AsyncMock(return_value=False)
            run_config = await mgr.create_run_from_template(
                tmpl_id,
                overrides={"goal": "Overridden goal", "budget_limit": 20.0},
            )
        assert run_config["goal"] == "Overridden goal"
        assert run_config["budget_limit"] == 20.0

    @pytest.mark.asyncio
    async def test_create_run_from_nonexistent_template(self):
        mgr = TemplateManager()
        mock_session = _mock_session()
        with patch("packages.runtime.templates.get_session") as mock_get:
            mock_get.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_get.return_value.__aexit__ = AsyncMock(return_value=False)
            with pytest.raises(ValueError, match="not found"):
                await mgr.create_run_from_template(uuid.uuid4())
