"""DB-backed repositories for auth tokens, secrets, and agent identities."""

from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from packages.schemas.models import AgentRecord, AuthTokenRecord, SecretRecord


class AuthRepository:
    """Persists auth tokens in Postgres instead of in-memory dict."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession] | None = None):
        self._session_factory = session_factory

    def _get_factory(self):
        if self._session_factory:
            return self._session_factory
        from packages.schemas.database import get_session_factory
        return get_session_factory()

    async def create_token(
        self,
        token_id: str,
        tenant_id: str,
        user_id: str,
        token_data: str,
        expires_at: datetime,
    ) -> AuthTokenRecord:
        factory = self._get_factory()
        async with factory() as session:
            record = AuthTokenRecord(
                id=token_id,
                tenant_id=tenant_id,
                user_id=user_id,
                token_data=token_data,
                expires_at=expires_at,
                is_revoked=False,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
            session.add(record)
            await session.commit()
            await session.refresh(record)
            return record

    async def get_token(self, token_id: str) -> Optional[AuthTokenRecord]:
        factory = self._get_factory()
        async with factory() as session:
            stmt = select(AuthTokenRecord).where(AuthTokenRecord.id == token_id)
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def revoke_token(self, token_id: str) -> bool:
        factory = self._get_factory()
        async with factory() as session:
            stmt = (
                update(AuthTokenRecord)
                .where(AuthTokenRecord.id == token_id)
                .values(is_revoked=True, updated_at=datetime.now(timezone.utc))
            )
            await session.execute(stmt)
            await session.commit()
            return True

    async def delete_expired(self) -> int:
        factory = self._get_factory()
        async with factory() as session:
            now = datetime.now(timezone.utc)
            stmt = select(AuthTokenRecord).where(AuthTokenRecord.expires_at < now)
            result = await session.execute(stmt)
            expired = result.scalars().all()
            for record in expired:
                await session.delete(record)
            await session.commit()
            return len(expired)


class SecretsRepository:
    """Persists secrets in Postgres instead of in-memory dict."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession] | None = None):
        self._session_factory = session_factory

    def _get_factory(self):
        if self._session_factory:
            return self._session_factory
        from packages.schemas.database import get_session_factory
        return get_session_factory()

    async def set_secret(
        self,
        tenant_id: str,
        name: str,
        encrypted_value: str,
        value_hash: str,
        environment: str = "dev",
        created_by: str = "system",
        description: str = "",
        tags: list[str] | None = None,
    ) -> SecretRecord:
        factory = self._get_factory()
        async with factory() as session:
            stmt = select(SecretRecord).where(
                SecretRecord.tenant_id == tenant_id,
                SecretRecord.name == name,
                SecretRecord.environment == environment,
            )
            result = await session.execute(stmt)
            existing = result.scalar_one_or_none()

            if existing:
                existing.encrypted_value = encrypted_value
                existing.value_hash = value_hash
                existing.updated_at = datetime.now(timezone.utc)
                existing.description = description or existing.description
                if tags is not None:
                    existing.tags = tags
                await session.commit()
                await session.refresh(existing)
                return existing

            record = SecretRecord(
                tenant_id=tenant_id,
                name=name,
                encrypted_value=encrypted_value,
                value_hash=value_hash,
                environment=environment,
                created_by=created_by,
                description=description,
                tags=tags or [],
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
            session.add(record)
            await session.commit()
            await session.refresh(record)
            return record

    async def get_secret(
        self, tenant_id: str, name: str, environment: str = "dev"
    ) -> Optional[SecretRecord]:
        factory = self._get_factory()
        async with factory() as session:
            stmt = select(SecretRecord).where(
                SecretRecord.tenant_id == tenant_id,
                SecretRecord.name == name,
                SecretRecord.environment == environment,
                SecretRecord.is_active == True,
            )
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def list_secrets(
        self,
        tenant_id: str,
        environment: str | None = None,
        active_only: bool = True,
    ) -> list[SecretRecord]:
        factory = self._get_factory()
        async with factory() as session:
            stmt = select(SecretRecord).where(SecretRecord.tenant_id == tenant_id)
            if active_only:
                stmt = stmt.where(SecretRecord.is_active == True)
            if environment:
                stmt = stmt.where(SecretRecord.environment == environment)
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def soft_delete(self, tenant_id: str, name: str, environment: str = "dev") -> bool:
        factory = self._get_factory()
        async with factory() as session:
            stmt = (
                update(SecretRecord)
                .where(
                    SecretRecord.tenant_id == tenant_id,
                    SecretRecord.name == name,
                    SecretRecord.environment == environment,
                )
                .values(is_active=False, updated_at=datetime.now(timezone.utc))
            )
            result = await session.execute(stmt)
            await session.commit()
            return result.rowcount > 0


class AgentsRepository:
    """Persists agent identities in Postgres instead of in-memory dict."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession] | None = None):
        self._session_factory = session_factory

    def _get_factory(self):
        if self._session_factory:
            return self._session_factory
        from packages.schemas.database import get_session_factory
        return get_session_factory()

    async def create_agent(
        self,
        tenant_id: str,
        name: str,
        role: str,
        api_key_hash: str,
        permissions: list[str] | None = None,
        allowed_tools: list[str] | None = None,
        denied_tools: list[str] | None = None,
    ) -> AgentRecord:
        factory = self._get_factory()
        async with factory() as session:
            record = AgentRecord(
                tenant_id=tenant_id,
                name=name,
                role=role,
                api_key_hash=api_key_hash,
                is_active=True,
                permissions=permissions or [],
                allowed_tools=allowed_tools or [],
                denied_tools=denied_tools or [],
                trust_score=1.0,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
            session.add(record)
            await session.commit()
            await session.refresh(record)
            return record

    async def get_by_api_key_hash(self, api_key_hash: str) -> Optional[AgentRecord]:
        factory = self._get_factory()
        async with factory() as session:
            stmt = select(AgentRecord).where(
                AgentRecord.api_key_hash == api_key_hash,
                AgentRecord.is_active == True,
            )
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def get_by_id(self, agent_id: uuid.UUID) -> Optional[AgentRecord]:
        factory = self._get_factory()
        async with factory() as session:
            stmt = select(AgentRecord).where(AgentRecord.id == agent_id)
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def revoke(self, agent_id: uuid.UUID) -> bool:
        factory = self._get_factory()
        async with factory() as session:
            stmt = (
                update(AgentRecord)
                .where(AgentRecord.id == agent_id)
                .values(is_active=False, updated_at=datetime.now(timezone.utc))
            )
            result = await session.execute(stmt)
            await session.commit()
            return result.rowcount > 0

    async def list_agents(self, tenant_id: str, active_only: bool = True) -> list[AgentRecord]:
        factory = self._get_factory()
        async with factory() as session:
            stmt = select(AgentRecord).where(AgentRecord.tenant_id == tenant_id)
            if active_only:
                stmt = stmt.where(AgentRecord.is_active == True)
            result = await session.execute(stmt)
            return list(result.scalars().all())
