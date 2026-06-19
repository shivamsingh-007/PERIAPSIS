from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import text

from packages.schemas.database import get_engine


class CheckpointStore:
    """Postgres-backed checkpoint persistence for run state."""

    async def save(self, run_id: uuid.UUID, tenant_id: uuid.UUID, state: dict[str, Any]) -> str:
        checkpoint_ref = f"cp_{run_id}_{int(datetime.utcnow().timestamp())}"
        state_json = json.dumps(state, default=str)

        engine = get_engine()
        async with engine.begin() as conn:
            await conn.execute(
                text(
                    """
                    INSERT INTO run_steps (step_id, run_id, tenant_id, step_number, node_name,
                                           input_state_jsonb, checkpoint_ref, created_at)
                    VALUES (:step_id, :run_id, :tenant_id, :step_number, :node_name,
                            :input_state_jsonb, :checkpoint_ref, NOW())
                    ON CONFLICT (tenant_id, run_id, step_number) DO UPDATE SET
                        input_state_jsonb = EXCLUDED.input_state_jsonb,
                        checkpoint_ref = EXCLUDED.checkpoint_ref
                    """
                ),
                {
                    "step_id": uuid.uuid4(),
                    "run_id": run_id,
                    "tenant_id": tenant_id,
                    "step_number": state.get("current_step", 0),
                    "node_name": state.get("last_node", "unknown"),
                    "input_state_jsonb": state_json,
                    "checkpoint_ref": checkpoint_ref,
                },
            )
        return checkpoint_ref

    async def load(self, run_id: uuid.UUID, tenant_id: uuid.UUID) -> dict[str, Any] | None:
        engine = get_engine()
        async with engine.connect() as conn:
            result = await conn.execute(
                text(
                    """
                    SELECT input_state_jsonb FROM run_steps
                    WHERE run_id = :run_id AND tenant_id = :tenant_id
                    ORDER BY step_number DESC LIMIT 1
                    """
                ),
                {"run_id": run_id, "tenant_id": tenant_id},
            )
            row = result.mappings().first()
            if row and row["input_state_jsonb"]:
                return json.loads(row["input_state_jsonb"])
            return None

    async def diff(
        self,
        run_id: uuid.UUID,
        tenant_id: uuid.UUID,
        step_a: int,
        step_b: int,
    ) -> dict[str, Any]:
        engine = get_engine()
        async with engine.connect() as conn:
            result = await conn.execute(
                text(
                    """
                    SELECT step_number, input_state_jsonb FROM run_steps
                    WHERE run_id = :run_id AND tenant_id = :tenant_id
                      AND step_number IN (:step_a, :step_b)
                    ORDER BY step_number
                    """
                ),
                {"run_id": run_id, "tenant_id": tenant_id, "step_a": step_a, "step_b": step_b},
            )
            rows = result.mappings().all()

        states = {row["step_number"]: json.loads(row["input_state_jsonb"]) for row in rows}
        state_a = states.get(step_a, {})
        state_b = states.get(step_b, {})

        all_keys = set(state_a.keys()) | set(state_b.keys())
        diff_result = {}
        for key in all_keys:
            val_a = state_a.get(key)
            val_b = state_b.get(key)
            if val_a != val_b:
                diff_result[key] = {"from": val_a, "to": val_b}

        return diff_result


checkpoint_store = CheckpointStore()
