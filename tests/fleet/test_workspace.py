from __future__ import annotations

import uuid

import pytest

from packages.fleet.workspace import (
    WorktreeInfo,
    WorkspaceIsolator,
)


@pytest.fixture
def isolator():
    return WorkspaceIsolator()


class TestWorktreeInfo:
    def test_create_info(self):
        info = WorktreeInfo(
            worktree_id=uuid.uuid4(),
            branch_name="feature/test",
            worktree_path="/tmp/worktree-1",
            base_path="/tmp/base",
        )
        assert info.branch_name == "feature/test"
        assert info.is_clean is True

    def test_info_defaults(self):
        info = WorktreeInfo(
            worktree_id=uuid.uuid4(),
            branch_name="main",
            worktree_path="/tmp/wt",
            base_path="/tmp/base",
        )
        assert info.is_clean is True


class TestWorkspaceIsolator:
    def test_list_worktrees_empty(self, isolator):
        result = isolator.list_worktrees()
        assert result == []

    @pytest.mark.asyncio
    async def test_get_changes_not_found(self, isolator):
        with pytest.raises(ValueError):
            await isolator.get_changes(uuid.uuid4())

    @pytest.mark.asyncio
    async def test_get_file_content_not_found(self, isolator):
        result = await isolator.get_file_content(uuid.uuid4(), "test.py")
        assert result is None
