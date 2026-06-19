from __future__ import annotations

import asyncio
import os
import shutil
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from packages.logging.structured import get_logger

logger = get_logger("workspace")


class WorktreeInfo(BaseModel):
    worktree_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    branch_name: str
    worktree_path: str
    base_path: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    is_clean: bool = True


class WorkspaceIsolator:
    def __init__(self, base_repo_path: str | None = None):
        self.base_repo_path = base_repo_path or os.getcwd()
        self._worktrees: dict[uuid.UUID, WorktreeInfo] = {}

    async def create_worktree(
        self,
        agent_id: str,
        base_branch: str = "master",
    ) -> WorktreeInfo:
        branch_name = f"agent/{agent_id}/{uuid.uuid4().hex[:8]}"
        worktree_path = os.path.join(
            self.base_repo_path, ".worktrees", branch_name
        )

        os.makedirs(os.path.dirname(worktree_path), exist_ok=True)

        process = await asyncio.create_subprocess_exec(
            "git", "worktree", "add", "-b", branch_name, worktree_path, base_branch,
            cwd=self.base_repo_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()

        if process.returncode != 0:
            raise RuntimeError(f"Failed to create worktree: {stderr.decode()}")

        info = WorktreeInfo(
            branch_name=branch_name,
            worktree_path=worktree_path,
            base_path=self.base_repo_path,
        )
        self._worktrees[info.worktree_id] = info

        logger.info(f"Created worktree: {branch_name} at {worktree_path}")
        return info

    async def remove_worktree(self, worktree_id: uuid.UUID) -> bool:
        info = self._worktrees.get(worktree_id)
        if not info:
            return False

        process = await asyncio.create_subprocess_exec(
            "git", "worktree", "remove", info.worktree_path, "--force",
            cwd=self.base_repo_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await process.communicate()

        if process.returncode == 0:
            branch_process = await asyncio.create_subprocess_exec(
                "git", "branch", "-D", info.branch_name,
                cwd=self.base_repo_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await branch_process.communicate()

        del self._worktrees[worktree_id]
        logger.info(f"Removed worktree: {info.branch_name}")
        return True

    async def get_changes(self, worktree_id: uuid.UUID) -> dict:
        info = self._worktrees.get(worktree_id)
        if not info:
            raise ValueError(f"Worktree {worktree_id} not found")

        process = await asyncio.create_subprocess_exec(
            "git", "diff", "--stat",
            cwd=info.worktree_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await process.communicate()

        status_process = await asyncio.create_subprocess_exec(
            "git", "status", "--porcelain",
            cwd=info.worktree_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        status_out, _ = await status_process.communicate()

        return {
            "diff_stat": stdout.decode(),
            "modified_files": status_out.decode().strip().split("\n") if status_out.decode().strip() else [],
            "is_clean": not bool(status_out.decode().strip()),
        }

    async def commit_changes(
        self,
        worktree_id: uuid.UUID,
        message: str,
    ) -> str:
        info = self._worktrees.get(worktree_id)
        if not info:
            raise ValueError(f"Worktree {worktree_id} not found")

        await asyncio.create_subprocess_exec(
            "git", "add", "-A",
            cwd=info.worktree_path,
        )

        process = await asyncio.create_subprocess_exec(
            "git", "commit", "-m", message,
            cwd=info.worktree_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()

        if process.returncode != 0:
            raise RuntimeError(f"Commit failed: {stderr.decode()}")

        sha_process = await asyncio.create_subprocess_exec(
            "git", "rev-parse", "HEAD",
            cwd=info.worktree_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        sha_out, _ = await sha_process.communicate()
        sha = sha_out.decode().strip()

        logger.info(f"Committed to {info.branch_name}: {sha}")
        return sha

    async def merge_to_base(
        self,
        worktree_id: uuid.UUID,
        delete_branch: bool = True,
    ) -> bool:
        info = self._worktrees.get(worktree_id)
        if not info:
            raise ValueError(f"Worktree {worktree_id} not found")

        process = await asyncio.create_subprocess_exec(
            "git", "merge", info.branch_name,
            cwd=self.base_repo_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()

        if process.returncode != 0:
            logger.error(f"Merge failed: {stderr.decode()}")
            return False

        if delete_branch:
            await self.remove_worktree(worktree_id)

        logger.info(f"Merged {info.branch_name} to base")
        return True

    async def get_file_content(
        self,
        worktree_id: uuid.UUID,
        file_path: str,
    ) -> str | None:
        info = self._worktrees.get(worktree_id)
        if not info:
            return None

        full_path = os.path.join(info.worktree_path, file_path)
        if os.path.exists(full_path):
            with open(full_path) as f:
                return f.read()
        return None

    def list_worktrees(self) -> list[dict]:
        return [
            {
                "worktree_id": str(w.worktree_id),
                "branch_name": w.branch_name,
                "path": w.worktree_path,
                "created_at": w.created_at.isoformat(),
            }
            for w in self._worktrees.values()
        ]


workspace_isolator = WorkspaceIsolator()
