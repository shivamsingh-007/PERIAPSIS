from __future__ import annotations

import uuid

import pytest

from packages.fleet.iam import (
    AgentIAM,
    AgentIdentity,
    AgentRole,
    Permission,
    ROLE_PERMISSIONS,
)


@pytest.fixture
def iam():
    return AgentIAM()


@pytest.fixture
def coder_identity(iam):
    return iam.create_identity(name="test-coder", role=AgentRole.CODER)


class TestPermission:
    def test_all_variants(self):
        assert len(list(Permission)) == 5

    def test_values(self):
        assert Permission.READ.value == "read"
        assert Permission.WRITE.value == "write"
        assert Permission.EXECUTE.value == "execute"
        assert Permission.ADMIN.value == "admin"
        assert Permission.AUDIT.value == "audit"


class TestAgentRole:
    def test_all_variants(self):
        assert len(list(AgentRole)) == 7


class TestRolePermissions:
    def test_researcher_permissions(self):
        perms = ROLE_PERMISSIONS[AgentRole.RESEARCHER]
        assert Permission.READ in perms
        assert Permission.WRITE not in perms

    def test_coder_permissions(self):
        perms = ROLE_PERMISSIONS[AgentRole.CODER]
        assert Permission.READ in perms
        assert Permission.WRITE in perms
        assert Permission.EXECUTE in perms

    def test_coordinator_permissions(self):
        perms = ROLE_PERMISSIONS[AgentRole.COORDINATOR]
        assert Permission.ADMIN in perms
        assert Permission.AUDIT in perms

    def test_all_roles_have_permissions(self):
        for role in AgentRole:
            assert role in ROLE_PERMISSIONS
            assert len(ROLE_PERMISSIONS[role]) > 0


class TestAgentIdentity:
    def test_create_identity(self):
        identity = AgentIdentity(
            agent_id=uuid.uuid4(),
            name="test-agent",
            role=AgentRole.CODER,
        )
        assert identity.name == "test-agent"
        assert identity.role == AgentRole.CODER
        assert identity.is_active is True
        assert identity.trust_score == 1.0

    def test_has_permission_true(self):
        identity = AgentIdentity(
            agent_id=uuid.uuid4(),
            name="test",
            role=AgentRole.CODER,
        )
        assert identity.has_permission(Permission.READ) is True
        assert identity.has_permission(Permission.WRITE) is True

    def test_has_permission_false(self):
        identity = AgentIdentity(
            agent_id=uuid.uuid4(),
            name="test",
            role=AgentRole.RESEARCHER,
        )
        assert identity.has_permission(Permission.WRITE) is False

    def test_can_use_tool_allowed(self):
        identity = AgentIdentity(
            agent_id=uuid.uuid4(),
            name="test",
            role=AgentRole.CODER,
            allowed_tools=["read", "write"],
        )
        assert identity.can_use_tool("read") is True

    def test_can_use_tool_denied(self):
        identity = AgentIdentity(
            agent_id=uuid.uuid4(),
            name="test",
            role=AgentRole.CODER,
            denied_tools=["delete"],
        )
        assert identity.can_use_tool("delete") is False

    def test_can_use_tool_not_in_lists(self):
        identity = AgentIdentity(
            agent_id=uuid.uuid4(),
            name="test",
            role=AgentRole.CODER,
        )
        assert identity.can_use_tool("anything") is True

    def test_can_access_data_domain(self):
        identity = AgentIdentity(
            agent_id=uuid.uuid4(),
            name="test",
            role=AgentRole.CODER,
            allowed_data_domains=["code", "tests"],
        )
        assert identity.can_access_data_domain("code") is True
        assert identity.can_access_data_domain("pii") is False

    def test_can_use_environment(self):
        identity = AgentIdentity(
            agent_id=uuid.uuid4(),
            name="test",
            role=AgentRole.CODER,
            allowed_environments=["development", "staging"],
        )
        assert identity.can_use_environment("development") is True
        assert identity.can_use_environment("production") is False


class TestAgentIAM:
    def test_create_identity(self, iam):
        identity = iam.create_identity(name="agent-1", role=AgentRole.CODER)
        assert identity.name == "agent-1"
        assert identity.role == AgentRole.CODER
        assert identity.api_key_hash is not None

    def test_authenticate(self, iam):
        identity = iam.create_identity(name="agent-1", role=AgentRole.CODER)
        result = iam.authenticate(identity.api_key)
        assert result is not None
        assert result.name == "agent-1"

    def test_authenticate_invalid(self, iam):
        result = iam.authenticate("invalid_key")
        assert result is None

    def test_authorize(self, iam):
        identity = iam.create_identity(name="agent-1", role=AgentRole.CODER)
        assert iam.authorize(identity, Permission.READ) is True

    def test_authorize_denied(self, iam):
        identity = iam.create_identity(name="agent-1", role=AgentRole.RESEARCHER)
        assert iam.authorize(identity, Permission.WRITE) is False

    def test_get_identity(self, iam):
        identity = iam.create_identity(name="agent-1", role=AgentRole.CODER)
        retrieved = iam.get_identity(identity.agent_id)
        assert retrieved is not None
        assert retrieved.name == "agent-1"

    def test_get_identity_not_found(self, iam):
        result = iam.get_identity(uuid.uuid4())
        assert result is None

    def test_revoke_identity(self, iam):
        identity = iam.create_identity(name="agent-1", role=AgentRole.CODER)
        result = iam.revoke_identity(identity.agent_id)
        assert result is True
        retrieved = iam.get_identity(identity.agent_id)
        assert retrieved.is_active is False

    def test_revoke_not_found(self, iam):
        result = iam.revoke_identity(uuid.uuid4())
        assert result is False

    def test_rotate_api_key(self, iam):
        identity = iam.create_identity(name="agent-1", role=AgentRole.CODER)
        old_hash = identity.api_key_hash
        new_key = iam.rotate_api_key(identity.agent_id)
        assert new_key is not None
        assert new_key != old_hash

    def test_rotate_not_found(self, iam):
        result = iam.rotate_api_key(uuid.uuid4())
        assert result is None

    def test_update_trust_score(self, iam):
        identity = iam.create_identity(name="agent-1", role=AgentRole.CODER)
        iam.update_trust_score(identity.agent_id, 0.5)
        updated = iam.get_identity(identity.agent_id)
        assert updated.trust_score == 0.5

    def test_low_trust_deactivates(self, iam):
        identity = iam.create_identity(name="agent-1", role=AgentRole.CODER)
        iam.update_trust_score(identity.agent_id, 0.1)
        updated = iam.get_identity(identity.agent_id)
        assert updated.is_active is False

    def test_list_identities(self, iam):
        iam.create_identity(name="agent-1", role=AgentRole.CODER)
        iam.create_identity(name="agent-2", role=AgentRole.TESTER)
        result = iam.list_identities()
        assert len(result) == 2

    def test_list_active_only(self, iam):
        identity1 = iam.create_identity(name="agent-1", role=AgentRole.CODER)
        iam.create_identity(name="agent-2", role=AgentRole.TESTER)
        iam.revoke_identity(identity1.agent_id)
        result = iam.list_identities(active_only=True)
        assert len(result) == 1
