"""Tests for auth persistence via AuthRepository (mocked DB session)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from packages.security.auth import AuthManager
from packages.security.repositories import AuthRepository
from packages.schemas.models import AuthTokenRecord


class FakeAuthRepo:
    """In-memory fake of AuthRepository for testing."""

    def __init__(self):
        self._store: dict[str, AuthTokenRecord] = {}

    async def create_token(self, token_id, tenant_id, user_id, token_data, expires_at):
        rec = AuthTokenRecord(
            id=token_id, tenant_id=tenant_id, user_id=user_id,
            token_data=token_data, expires_at=expires_at,
            is_revoked=False, created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        self._store[token_id] = rec
        return rec

    async def get_token(self, token_id):
        return self._store.get(token_id)

    async def revoke_token(self, token_id):
        if token_id in self._store:
            self._store[token_id].is_revoked = True
        return True

    async def delete_expired(self):
        now = datetime.now(timezone.utc)
        expired = [k for k, v in self._store.items() if v.expires_at < now]
        for k in expired:
            del self._store[k]
        return len(expired)


class TestAuthRepository:
    def _make_repo(self):
        return FakeAuthRepo()

    @pytest.mark.asyncio
    async def test_create_and_get_token(self):
        repo = self._make_repo()
        now = datetime.now(timezone.utc)
        record = await repo.create_token(
            token_id="tok-123",
            tenant_id="tenant-1",
            user_id="user-1",
            token_data="raw-token-data",
            expires_at=now + timedelta(hours=1),
        )
        assert record.id == "tok-123"
        assert record.tenant_id == "tenant-1"
        assert record.user_id == "user-1"
        assert record.is_revoked is False

        fetched = await repo.get_token("tok-123")
        assert fetched is not None
        assert fetched.token_data == "raw-token-data"

    @pytest.mark.asyncio
    async def test_get_nonexistent_token(self):
        repo = self._make_repo()
        result = await repo.get_token("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_revoke_token(self):
        repo = self._make_repo()
        now = datetime.now(timezone.utc)
        await repo.create_token(
            token_id="tok-revoke",
            tenant_id="t1",
            user_id="u1",
            token_data="data",
            expires_at=now + timedelta(hours=1),
        )
        await repo.revoke_token("tok-revoke")
        record = await repo.get_token("tok-revoke")
        assert record.is_revoked is True

    @pytest.mark.asyncio
    async def test_delete_expired(self):
        repo = self._make_repo()
        now = datetime.now(timezone.utc)
        await repo.create_token("tok-expired", "t1", "u1", "d", now - timedelta(hours=1))
        await repo.create_token("tok-valid", "t1", "u1", "d", now + timedelta(hours=1))
        deleted = await repo.delete_expired()
        assert deleted == 1
        assert await repo.get_token("tok-expired") is None
        assert await repo.get_token("tok-valid") is not None


class TestAuthManagerWithRepo:
    def _make_manager_with_mock_repo(self):
        token_store = {}
        repo = FakeAuthRepo()
        repo._store = token_store
        manager = AuthManager(secret_key="test-key-for-persistence", auth_repo=repo)
        return manager, repo, token_store

    def test_sync_create_token(self):
        manager, _, _ = self._make_manager_with_mock_repo()
        token = manager.create_token("user1", "tenant1")
        assert token.access_token
        payload = manager.verify_token(token.access_token)
        assert payload is not None
        assert payload.sub == "user1"

    @pytest.mark.asyncio
    async def test_async_create_token_with_repo(self):
        manager, _, _ = self._make_manager_with_mock_repo()
        token = await manager.create_token_async("user1", "tenant1")
        assert token.access_token
        payload = manager.verify_token(token.access_token)
        assert payload is not None
        assert payload.sub == "user1"

    @pytest.mark.asyncio
    async def test_async_verify_checks_revocation_in_repo(self):
        manager, _, token_store = self._make_manager_with_mock_repo()
        token = await manager.create_token_async("user1", "tenant1")
        payload = manager.verify_token(token.access_token)
        token_store[payload.jti].is_revoked = True
        result = await manager.verify_token_async(token.access_token)
        assert result is None

    @pytest.mark.asyncio
    async def test_async_revoke_persists_to_repo(self):
        manager, _, token_store = self._make_manager_with_mock_repo()
        token = await manager.create_token_async("user1", "tenant1")
        result = await manager.revoke_token_async(token.access_token)
        assert result is True
        payload = await manager.verify_token_async(token.access_token)
        assert payload is None

    def test_sync_revoke_still_works(self):
        manager, _, _ = self._make_manager_with_mock_repo()
        token = manager.create_token("user1", "tenant1")
        result = manager.revoke_token(token.access_token)
        assert result is True
        payload = manager.verify_token(token.access_token)
        assert payload is None
