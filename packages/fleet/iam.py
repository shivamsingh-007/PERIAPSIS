from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from packages.logging.structured import get_logger

logger = get_logger("iam")


class Permission(str, Enum):
    READ = "read"
    WRITE = "write"
    EXECUTE = "execute"
    ADMIN = "admin"
    AUDIT = "audit"


class AgentRole(str, Enum):
    RESEARCHER = "researcher"
    CODER = "coder"
    TESTER = "tester"
    REVIEWER = "reviewer"
    GOVERNANCE = "governance"
    SECURITY = "security"
    COORDINATOR = "coordinator"


ROLE_PERMISSIONS: dict[AgentRole, list[Permission]] = {
    AgentRole.RESEARCHER: [Permission.READ, Permission.EXECUTE],
    AgentRole.CODER: [Permission.READ, Permission.WRITE, Permission.EXECUTE],
    AgentRole.TESTER: [Permission.READ, Permission.EXECUTE],
    AgentRole.REVIEWER: [Permission.READ, Permission.AUDIT],
    AgentRole.GOVERNANCE: [Permission.READ, Permission.AUDIT, Permission.ADMIN],
    AgentRole.SECURITY: [Permission.READ, Permission.AUDIT, Permission.EXECUTE],
    AgentRole.COORDINATOR: [
        Permission.READ, Permission.WRITE, Permission.EXECUTE,
        Permission.ADMIN, Permission.AUDIT,
    ],
}


class AgentIdentity(BaseModel):
    agent_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    name: str
    role: AgentRole
    api_key: str = Field(default_factory=lambda: secrets.token_urlsafe(32))
    api_key_hash: str = ""
    permissions: list[Permission] = Field(default_factory=list)
    allowed_tools: list[str] = Field(default_factory=list)
    denied_tools: list[str] = Field(default_factory=list)
    allowed_data_domains: list[str] = Field(default_factory=list)
    max_tokens_per_request: int = 4096
    max_requests_per_minute: int = 60
    max_cost_per_hour: float = 5.0
    allowed_environments: list[str] = Field(default_factory=lambda: ["dev"])
    trust_score: float = 1.0
    created_at: datetime = Field(default_factory=datetime.utcnow)
    is_active: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)

    def model_post_init(self, __context: Any) -> None:
        if not self.api_key_hash:
            self.api_key_hash = hashlib.sha256(self.api_key.encode()).hexdigest()
        if not self.permissions:
            self.permissions = ROLE_PERMISSIONS.get(self.role, [Permission.READ])

    def has_permission(self, perm: Permission) -> bool:
        return perm in self.permissions

    def can_use_tool(self, tool_name: str) -> bool:
        if tool_name in self.denied_tools:
            return False
        if self.allowed_tools and tool_name not in self.allowed_tools:
            return False
        return True

    def can_access_data_domain(self, domain: str) -> bool:
        if not self.allowed_data_domains:
            return True
        return domain in self.allowed_data_domains

    def can_use_environment(self, env: str) -> bool:
        return env in self.allowed_environments


class AgentIAM:
    def __init__(self):
        self._identities: dict[uuid.UUID, AgentIdentity] = {}
        self._api_key_index: dict[str, uuid.UUID] = {}

    def create_identity(
        self,
        name: str,
        role: AgentRole,
        allowed_tools: list[str] | None = None,
        denied_tools: list[str] | None = None,
        allowed_data_domains: list[str] | None = None,
        allowed_environments: list[str] | None = None,
        max_tokens_per_request: int = 4096,
        max_requests_per_minute: int = 60,
        max_cost_per_hour: float = 5.0,
    ) -> AgentIdentity:
        identity = AgentIdentity(
            name=name,
            role=role,
            allowed_tools=allowed_tools or [],
            denied_tools=denied_tools or [],
            allowed_data_domains=allowed_data_domains or [],
            allowed_environments=allowed_environments or ["dev"],
            max_tokens_per_request=max_tokens_per_request,
            max_requests_per_minute=max_requests_per_minute,
            max_cost_per_hour=max_cost_per_hour,
        )

        self._identities[identity.agent_id] = identity
        self._api_key_index[identity.api_key_hash] = identity.agent_id

        logger.info(f"Created identity: {name} ({role.value})")
        return identity

    def authenticate(self, api_key: str) -> AgentIdentity | None:
        key_hash = hashlib.sha256(api_key.encode()).hexdigest()
        agent_id = self._api_key_index.get(key_hash)
        if agent_id:
            identity = self._identities.get(agent_id)
            if identity and identity.is_active:
                return identity
        return None

    def authorize(
        self,
        identity: AgentIdentity,
        permission: Permission,
        tool_name: str | None = None,
        data_domain: str | None = None,
        environment: str | None = None,
    ) -> bool:
        if not identity.is_active:
            logger.warning(f"Inactive agent {identity.name} denied access")
            return False

        if not identity.has_permission(permission):
            logger.warning(f"Agent {identity.name} lacks permission {permission.value}")
            return False

        if tool_name and not identity.can_use_tool(tool_name):
            logger.warning(f"Agent {identity.name} denied tool: {tool_name}")
            return False

        if data_domain and not identity.can_access_data_domain(data_domain):
            logger.warning(f"Agent {identity.name} denied data domain: {data_domain}")
            return False

        if environment and not identity.can_use_environment(environment):
            logger.warning(f"Agent {identity.name} denied environment: {environment}")
            return False

        return True

    def get_identity(self, agent_id: uuid.UUID) -> AgentIdentity | None:
        return self._identities.get(agent_id)

    def revoke_identity(self, agent_id: uuid.UUID) -> bool:
        identity = self._identities.get(agent_id)
        if identity:
            identity.is_active = False
            logger.info(f"Revoked identity: {identity.name}")
            return True
        return False

    def rotate_api_key(self, agent_id: uuid.UUID) -> str | None:
        identity = self._identities.get(agent_id)
        if not identity:
            return None

        old_hash = identity.api_key_hash
        self._api_key_index.pop(old_hash, None)

        new_key = secrets.token_urlsafe(32)
        identity.api_key = new_key
        identity.api_key_hash = hashlib.sha256(new_key.encode()).hexdigest()
        self._api_key_index[identity.api_key_hash] = agent_id

        logger.info(f"Rotated API key for: {identity.name}")
        return new_key

    def update_trust_score(self, agent_id: uuid.UUID, score: float) -> None:
        identity = self._identities.get(agent_id)
        if identity:
            identity.trust_score = max(0.0, min(1.0, score))
            if identity.trust_score < 0.3:
                identity.is_active = False
                logger.warning(f"Agent {identity.name} deactivated due to low trust: {identity.trust_score}")

    def list_identities(self, active_only: bool = True) -> list[dict]:
        return [
            {
                "agent_id": str(i.agent_id),
                "name": i.name,
                "role": i.role.value,
                "trust_score": i.trust_score,
                "is_active": i.is_active,
                "permissions": [p.value for p in i.permissions],
                "created_at": i.created_at.isoformat(),
            }
            for i in self._identities.values()
            if not active_only or i.is_active
        ]


agent_iam = AgentIAM()
