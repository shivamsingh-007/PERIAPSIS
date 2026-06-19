from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy import text

from packages.schemas.database import get_session
from packages.logging.structured import get_logger

logger = get_logger("replay")


class ReplayConfig(BaseModel):
    original_run_id: uuid.UUID
    modified_state: dict | None = None
    skip_steps: list[int] = Field(default_factory=list)
    override_goal: str | None = None
    override_budget: float | None = None


class ReplayResult(BaseModel):
    replay_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    original_run_id: uuid.UUID
    new_run_id: uuid.UUID | None = None
    status: str = "pending"
    differences: list[dict] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class RunReplayer:
    async def create_replay(
        self,
        tenant_id: uuid.UUID,
        config: ReplayConfig,
    ) -> ReplayResult:
        original_run = await self._get_run(config.original_run_id)
        if not original_run:
            raise ValueError(f"Original run {config.original_run_id} not found")

        replay = ReplayResult(
            original_run_id=config.original_run_id,
            status="created",
        )

        differences = self._calculate_differences(
            original_run,
            config.modified_state,
            config.skip_steps,
            config.override_goal,
            config.override_budget,
        )
        replay.differences = differences

        await self._persist_replay(replay, tenant_id)
        return replay

    async def execute_replay(
        self,
        replay_id: uuid.UUID,
        tenant_id: uuid.UUID,
    ) -> ReplayResult:
        replay = await self._get_replay(replay_id)
        if not replay:
            raise ValueError(f"Replay {replay_id} not found")

        original_run = await self._get_run(replay.original_run_id)
        if not original_run:
            raise ValueError(f"Original run not found")

        new_run_config = self._build_replay_config(original_run, replay.differences)

        logger.info(f"Executing replay {replay_id} from run {replay.original_run_id}")

        replay.status = "executing"
        await self._update_replay_status(replay_id, "executing")

        return replay

    def _calculate_differences(
        self,
        original_run: dict,
        modified_state: dict | None,
        skip_steps: list[int],
        override_goal: str | None,
        override_budget: float | None,
    ) -> list[dict]:
        differences = []

        if override_goal and override_goal != original_run.get("goal"):
            differences.append({
                "type": "goal_override",
                "original": original_run.get("goal"),
                "modified": override_goal,
            })

        if override_budget and override_budget != original_run.get("budget_limit"):
            differences.append({
                "type": "budget_override",
                "original": original_run.get("budget_limit"),
                "modified": override_budget,
            })

        if skip_steps:
            differences.append({
                "type": "skip_steps",
                "steps": skip_steps,
            })

        if modified_state:
            for key, value in modified_state.items():
                if key in original_run and original_run[key] != value:
                    differences.append({
                        "type": "state_modification",
                        "field": key,
                        "original": original_run[key],
                        "modified": value,
                    })

        return differences

    def _build_replay_config(self, original_run: dict, differences: list[dict]) -> dict:
        config = {
            "goal": original_run.get("goal"),
            "budget_limit": original_run.get("budget_limit"),
            "risk_tier": original_run.get("risk_tier"),
        }

        for diff in differences:
            if diff["type"] == "goal_override":
                config["goal"] = diff["modified"]
            elif diff["type"] == "budget_override":
                config["budget_limit"] = diff["modified"]

        return config

    async def _get_run(self, run_id: uuid.UUID) -> dict | None:
        async with get_session() as session:
            result = await session.execute(
                text("SELECT * FROM runs WHERE run_id = :run_id"),
                {"run_id": run_id},
            )
            row = result.mappings().first()
            return dict(row) if row else None

    async def _get_replay(self, replay_id: uuid.UUID) -> ReplayResult | None:
        async with get_session() as session:
            result = await session.execute(
                text("SELECT * FROM run_replays WHERE replay_id = :replay_id"),
                {"replay_id": replay_id},
            )
            row = result.mappings().first()
            if row:
                data = dict(row)
                data["differences"] = json.loads(data.get("differences", "[]"))
                return ReplayResult(**data)
            return None

    async def _persist_replay(self, replay: ReplayResult, tenant_id: uuid.UUID):
        async with get_session() as session:
            await session.execute(
                text(
                    """
                    INSERT INTO run_replays
                        (replay_id, original_run_id, new_run_id, status, differences, tenant_id, created_at)
                    VALUES
                        (:replay_id, :original_run_id, :new_run_id, :status, :differences, :tenant_id, NOW())
                    """
                ),
                {
                    "replay_id": replay.replay_id,
                    "original_run_id": replay.original_run_id,
                    "new_run_id": replay.new_run_id,
                    "status": replay.status,
                    "differences": json.dumps(replay.differences),
                    "tenant_id": tenant_id,
                },
            )

    async def _update_replay_status(self, replay_id: uuid.UUID, status: str):
        async with get_session() as session:
            await session.execute(
                text("UPDATE run_replays SET status = :status WHERE replay_id = :replay_id"),
                {"replay_id": replay_id, "status": status},
            )

    async def list_replays(self, tenant_id: uuid.UUID) -> list[ReplayResult]:
        async with get_session() as session:
            result = await session.execute(
                text(
                    """
                    SELECT * FROM run_replays
                    WHERE tenant_id = :tenant_id
                    ORDER BY created_at DESC
                    """
                ),
                {"tenant_id": tenant_id},
            )
            replays = []
            for row in result.mappings().all():
                data = dict(row)
                data["differences"] = json.loads(data.get("differences", "[]"))
                replays.append(ReplayResult(**data))
            return replays


run_replayer = RunReplayer()
