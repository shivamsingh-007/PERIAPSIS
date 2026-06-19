from __future__ import annotations

import time
import uuid

from sqlalchemy import text

from packages.schemas.database import get_session
from packages.runtime.graph import build_main_graph
from packages.runtime.state import BudgetPolicy, RunState, RunStatus, TerminalState


class RunService:
    def __init__(self):
        self._graph = None

    @property
    def graph(self):
        if self._graph is None:
            self._graph = build_main_graph()
        return self._graph

    async def execute_run(
        self,
        run_id: uuid.UUID,
        tenant_id: uuid.UUID,
        goal: str,
        budget: BudgetPolicy | None = None,
    ) -> dict:
        state = RunState(
            run_id=run_id,
            tenant_id=tenant_id,
            goal=goal,
            budget=budget or BudgetPolicy(),
        )

        await self._update_run_status(run_id, tenant_id, "running")

        start_time = time.time()
        try:
            result = await self.graph.ainvoke(state)
            runtime_seconds = time.time() - start_time

            if isinstance(result, dict):
                terminal = result.get("terminal_state")
                status = result.get("status", RunStatus.COMPLETED)
            else:
                terminal = getattr(result, "terminal_state", TerminalState.SUCCESS)
                status = getattr(result, "status", RunStatus.COMPLETED)

            await self._update_run_status(
                run_id,
                tenant_id,
                status.value if isinstance(status, RunStatus) else str(status),
                terminal.value if isinstance(terminal, TerminalState) else str(terminal),
            )

            return {
                "run_id": str(run_id),
                "status": status.value if isinstance(status, RunStatus) else str(status),
                "terminal_state": terminal.value if isinstance(terminal, TerminalState) else str(terminal),
                "runtime_seconds": runtime_seconds,
            }

        except Exception as e:
            await self._update_run_status(run_id, tenant_id, "failed")
            return {
                "run_id": str(run_id),
                "status": "failed",
                "terminal_state": TerminalState.FAIL_TOOLING.value,
                "error": str(e),
            }

    async def _update_run_status(
        self,
        run_id: uuid.UUID,
        tenant_id: uuid.UUID,
        status: str,
        terminal_state: str | None = None,
    ):
        async with get_session() as session:
            updates = ["status = :status", "updated_at = NOW()"]
            params: dict = {"run_id": run_id, "tenant_id": tenant_id, "status": status}

            if terminal_state:
                updates.append("terminal_state = :terminal_state")
                params["terminal_state"] = terminal_state

            await session.execute(
                text(
                    f"UPDATE runs SET {', '.join(updates)} WHERE run_id = :run_id AND tenant_id = :tenant_id"
                ),
                params,
            )


run_service = RunService()
