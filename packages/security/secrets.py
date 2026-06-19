from __future__ import annotations

import base64
import hashlib
import os
import secrets
import uuid
from datetime import datetime
from typing import Any

from cryptography.fernet import Fernet
from pydantic import BaseModel, Field

from packages.logging.structured import get_logger

logger = get_logger("secrets")


class SecretEntry(BaseModel):
    secret_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    name: str
    encrypted_value: str
    value_hash: str
    environment: str = "dev"
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    created_by: str = "system"
    description: str = ""
    tags: list[str] = Field(default_factory=list)
    is_active: bool = True


class SecretsManager:
    def __init__(self, encryption_key: str | None = None):
        if encryption_key:
            self._fernet = Fernet(encryption_key.encode() if isinstance(encryption_key, str) else encryption_key)
        else:
            key = Fernet.generate_key()
            self._fernet = Fernet(key)
            logger.warning("Using generated encryption key - not persistent across restarts")

        self._secrets: dict[str, SecretEntry] = {}

    def set_secret(
        self,
        name: str,
        value: str,
        environment: str = "dev",
        created_by: str = "system",
        description: str = "",
        tags: list[str] | None = None,
    ) -> SecretEntry:
        encrypted = self._fernet.encrypt(value.encode()).decode()
        value_hash = hashlib.sha256(value.encode()).hexdigest()

        existing = self.get_secret(name, environment)
        if existing:
            existing.encrypted_value = encrypted
            existing.value_hash = value_hash
            existing.updated_at = datetime.utcnow()
            existing.description = description or existing.description
            existing.tags = tags or existing.tags
            logger.info(f"Updated secret: {name} ({environment})")
            return existing

        entry = SecretEntry(
            name=name,
            encrypted_value=encrypted,
            value_hash=value_hash,
            environment=environment,
            created_by=created_by,
            description=description,
            tags=tags or [],
        )

        key = f"{name}:{environment}"
        self._secrets[key] = entry
        logger.info(f"Created secret: {name} ({environment})")
        return entry

    def get_secret(self, name: str, environment: str = "dev") -> SecretEntry | None:
        key = f"{name}:{environment}"
        return self._secrets.get(key)

    def get_secret_value(self, name: str, environment: str = "dev") -> str | None:
        entry = self.get_secret(name, environment)
        if not entry:
            return None

        try:
            decrypted = self._fernet.decrypt(entry.encrypted_value.encode())
            return decrypted.decode()
        except Exception as e:
            logger.error(f"Failed to decrypt secret {name}: {e}")
            return None

    def delete_secret(self, name: str, environment: str = "dev") -> bool:
        key = f"{name}:{environment}"
        if key in self._secrets:
            self._secrets[key].is_active = False
            logger.info(f"Deleted secret: {name} ({environment})")
            return True
        return False

    def list_secrets(
        self,
        environment: str | None = None,
        tags: list[str] | None = None,
        active_only: bool = True,
    ) -> list[SecretEntry]:
        entries = list(self._secrets.values())

        if active_only:
            entries = [e for e in entries if e.is_active]
        if environment:
            entries = [e for e in entries if e.environment == environment]
        if tags:
            entries = [e for e in entries if any(t in e.tags for t in tags)]

        return entries

    def rotate_secret(self, name: str, environment: str = "dev") -> SecretEntry | None:
        entry = self.get_secret(name, environment)
        if not entry:
            return None

        new_value = secrets.token_urlsafe(32)
        return self.set_secret(
            name=name,
            value=new_value,
            environment=environment,
            created_by=entry.created_by,
            description=f"Rotated from {entry.name}",
            tags=entry.tags,
        )

    def get_vault_status(self) -> dict:
        entries = list(self._secrets.values())
        active = [e for e in entries if e.is_active]
        return {
            "total_secrets": len(entries),
            "active_secrets": len(active),
            "environments": list(set(e.environment for e in active)),
            "oldest_secret": min((e.created_at for e in active), default=None),
            "newest_secret": max((e.created_at for e in active), default=None),
        }


secrets_manager = SecretsManager()
