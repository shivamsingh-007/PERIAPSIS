"""Tests for secrets persistence via SecretsRepository (mocked DB session)."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from cryptography.fernet import Fernet

from packages.security.secrets import SecretsManager
from packages.security.repositories import SecretsRepository
from packages.schemas.models import SecretRecord


class FakeSecretsRepo:
    """In-memory fake of SecretsRepository for testing SecretsManager."""

    def __init__(self):
        self._store: dict[str, SecretRecord] = {}

    def _key(self, tenant_id, name, environment="dev"):
        return f"{tenant_id}:{name}:{environment}"

    async def set_secret(self, tenant_id, name, encrypted_value, value_hash,
                         environment="dev", created_by="system",
                         description="", tags=None):
        key = self._key(tenant_id, name, environment)
        if key in self._store:
            rec = self._store[key]
            rec.encrypted_value = encrypted_value
            rec.value_hash = value_hash
            rec.updated_at = datetime.now(timezone.utc)
            if description:
                rec.description = description
            if tags is not None:
                rec.tags = tags
            return rec
        rec = SecretRecord(
            tenant_id=tenant_id, name=name, encrypted_value=encrypted_value,
            value_hash=value_hash, environment=environment, created_by=created_by,
            description=description, tags=tags or [], is_active=True,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        self._store[key] = rec
        return rec

    async def get_secret(self, tenant_id, name, environment="dev"):
        key = self._key(tenant_id, name, environment)
        rec = self._store.get(key)
        if rec and rec.is_active:
            return rec
        return None

    async def list_secrets(self, tenant_id, environment=None, active_only=True):
        results = []
        for key, rec in self._store.items():
            if rec.tenant_id == tenant_id:
                if active_only and not rec.is_active:
                    continue
                if environment and rec.environment != environment:
                    continue
                results.append(rec)
        return results

    async def soft_delete(self, tenant_id, name, environment="dev"):
        key = self._key(tenant_id, name, environment)
        rec = self._store.get(key)
        if rec:
            rec.is_active = False
            return True
        return False


class TestSecretsRepository:
    def _make_repo_with_store(self):
        """Use the fake repo for pure logic tests."""
        repo = FakeSecretsRepo()
        return repo

    @pytest.mark.asyncio
    async def test_set_and_get_secret(self):
        repo = self._make_repo_with_store()
        record = await repo.set_secret(
            tenant_id="tenant-1", name="api_key",
            encrypted_value="encrypted-data", value_hash="hash123",
        )
        assert record.name == "api_key"
        assert record.tenant_id == "tenant-1"

        fetched = await repo.get_secret("tenant-1", "api_key")
        assert fetched is not None
        assert fetched.encrypted_value == "encrypted-data"

    @pytest.mark.asyncio
    async def test_get_nonexistent_secret(self):
        repo = self._make_repo_with_store()
        result = await repo.get_secret("tenant-1", "nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_update_existing_secret(self):
        repo = self._make_repo_with_store()
        await repo.set_secret(tenant_id="t1", name="key", encrypted_value="v1", value_hash="h1")
        await repo.set_secret(tenant_id="t1", name="key", encrypted_value="v2", value_hash="h2")
        record = await repo.get_secret("t1", "key")
        assert record.encrypted_value == "v2"

    @pytest.mark.asyncio
    async def test_soft_delete(self):
        repo = self._make_repo_with_store()
        await repo.set_secret(tenant_id="t1", name="key", encrypted_value="v", value_hash="h")
        result = await repo.soft_delete("t1", "key")
        assert result is True
        fetched = await repo.get_secret("t1", "key")
        assert fetched is None

    @pytest.mark.asyncio
    async def test_list_secrets(self):
        repo = self._make_repo_with_store()
        await repo.set_secret(tenant_id="t1", name="k1", encrypted_value="v1", value_hash="h1")
        await repo.set_secret(tenant_id="t1", name="k2", encrypted_value="v2", value_hash="h2")
        await repo.set_secret(tenant_id="t2", name="k3", encrypted_value="v3", value_hash="h3")
        results = await repo.list_secrets("t1")
        assert len(results) == 2


class TestSecretsWithRepo:
    def _make_manager(self):
        secrets_repo = FakeSecretsRepo()
        key = Fernet.generate_key()
        manager = SecretsManager(encryption_key=key, secrets_repo=secrets_repo)
        return manager, secrets_repo

    def test_sync_set_get(self):
        manager, _ = self._make_manager()
        manager.set_secret("api_key", "secret-value")
        value = manager.get_secret_value("api_key")
        assert value == "secret-value"

    @pytest.mark.asyncio
    async def test_async_set_persists_to_repo(self):
        manager, repo = self._make_manager()
        entry = await manager.set_secret_async("api_key", "secret-value", tenant_id="t1")
        assert entry.name == "api_key"
        value = manager.get_secret_value("api_key")
        assert value == "secret-value"

    @pytest.mark.asyncio
    async def test_async_get_from_repo(self):
        manager, repo = self._make_manager()
        fernet = manager._fernet
        encrypted = fernet.encrypt(b"db-value").decode()
        value_hash = hashlib.sha256(b"db-value").hexdigest()
        await repo.set_secret(
            tenant_id="t1", name="db_key",
            encrypted_value=encrypted, value_hash=value_hash,
        )
        value = await manager.get_secret_value_async("db_key", tenant_id="t1")
        assert value == "db-value"

    def test_encryption_roundtrip(self):
        manager, _ = self._make_manager()
        manager.set_secret("test", "my-secret")
        entry = manager.get_secret("test")
        fernet = manager._fernet
        decrypted = fernet.decrypt(entry.encrypted_value.encode()).decode()
        assert decrypted == "my-secret"

    def test_vault_status(self):
        manager, _ = self._make_manager()
        manager.set_secret("k1", "v1")
        manager.set_secret("k2", "v2")
        status = manager.get_vault_status()
        assert status["total_secrets"] == 2
        assert status["active_secrets"] == 2
