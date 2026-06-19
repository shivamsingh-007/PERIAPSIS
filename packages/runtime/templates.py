from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy import text

from packages.schemas.database import get_session
from packages.logging.structured import get_logger

logger = get_logger("templates")


class RunTemplate(BaseModel):
    template_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    tenant_id: uuid.UUID
    name: str
    description: str = ""
    goal: str
    risk_tier: str = "low"
    budget_limit: float = 1.0
    max_iterations: int = 20
    tool_whitelist: list[str] = Field(default_factory=list)
    config: dict = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class TemplateManager:
    async def create_template(
        self,
        tenant_id: uuid.UUID,
        name: str,
        goal: str,
        description: str = "",
        risk_tier: str = "low",
        budget_limit: float = 1.0,
        max_iterations: int = 20,
        tool_whitelist: list[str] | None = None,
        config: dict | None = None,
    ) -> RunTemplate:
        template = RunTemplate(
            tenant_id=tenant_id,
            name=name,
            description=description,
            goal=goal,
            risk_tier=risk_tier,
            budget_limit=budget_limit,
            max_iterations=max_iterations,
            tool_whitelist=tool_whitelist or [],
            config=config or {},
        )

        async with get_session() as session:
            await session.execute(
                text(
                    """
                    INSERT INTO run_templates
                        (template_id, tenant_id, name, description, goal, risk_tier,
                         budget_limit, max_iterations, tool_whitelist, config, created_at, updated_at)
                    VALUES
                        (:template_id, :tenant_id, :name, :description, :goal, :risk_tier,
                         :budget_limit, :max_iterations, :tool_whitelist, :config, NOW(), NOW())
                    """
                ),
                {
                    "template_id": template.template_id,
                    "tenant_id": tenant_id,
                    "name": name,
                    "description": description,
                    "goal": goal,
                    "risk_tier": risk_tier,
                    "budget_limit": budget_limit,
                    "max_iterations": max_iterations,
                    "tool_whitelist": json.dumps(tool_whitelist or []),
                    "config": json.dumps(config or {}),
                },
            )

        logger.info(f"Template created: {template.name}")
        return template

    async def get_template(self, template_id: uuid.UUID) -> RunTemplate | None:
        async with get_session() as session:
            result = await session.execute(
                text("SELECT * FROM run_templates WHERE template_id = :id"),
                {"id": template_id},
            )
            row = result.mappings().first()
            if row:
                data = dict(row)
                data["tool_whitelist"] = json.loads(data.get("tool_whitelist", "[]"))
                data["config"] = json.loads(data.get("config", "{}"))
                return RunTemplate(**data)
            return None

    async def list_templates(self, tenant_id: uuid.UUID) -> list[RunTemplate]:
        async with get_session() as session:
            result = await session.execute(
                text(
                    """
                    SELECT * FROM run_templates
                    WHERE tenant_id = :tenant_id
                    ORDER BY created_at DESC
                    """
                ),
                {"tenant_id": tenant_id},
            )
            templates = []
            for row in result.mappings().all():
                data = dict(row)
                data["tool_whitelist"] = json.loads(data.get("tool_whitelist", "[]"))
                data["config"] = json.loads(data.get("config", "{}"))
                templates.append(RunTemplate(**data))
            return templates

    async def update_template(
        self,
        template_id: uuid.UUID,
        **kwargs,
    ) -> bool:
        updates = []
        params = {"template_id": template_id}

        for key, value in kwargs.items():
            if key in ("name", "description", "goal", "risk_tier", "budget_limit", "max_iterations"):
                updates.append(f"{key} = :{key}")
                params[key] = value
            elif key == "tool_whitelist":
                updates.append("tool_whitelist = :tool_whitelist")
                params["tool_whitelist"] = json.dumps(value)
            elif key == "config":
                updates.append("config = :config")
                params["config"] = json.dumps(value)

        if not updates:
            return False

        updates.append("updated_at = NOW()")
        set_clause = ", ".join(updates)

        async with get_session() as session:
            result = await session.execute(
                text(f"UPDATE run_templates SET {set_clause} WHERE template_id = :template_id"),
                params,
            )
            return result.rowcount > 0

    async def delete_template(self, template_id: uuid.UUID) -> bool:
        async with get_session() as session:
            result = await session.execute(
                text("DELETE FROM run_templates WHERE template_id = :id"),
                {"id": template_id},
            )
            return result.rowcount > 0

    async def create_run_from_template(
        self,
        template_id: uuid.UUID,
        overrides: dict | None = None,
    ) -> dict:
        template = await self.get_template(template_id)
        if not template:
            raise ValueError(f"Template {template_id} not found")

        run_config = {
            "goal": template.goal,
            "risk_tier": template.risk_tier,
            "budget_limit": template.budget_limit,
            "max_iterations": template.max_iterations,
            "tool_whitelist": template.tool_whitelist,
            "template_id": str(template.template_id),
            **(overrides or {}),
        }

        return run_config


template_manager = TemplateManager()
