from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from packages.fleet.swarm import (
    AgentDefinition,
    AgentRole,
    SwarmConfig,
    SwarmInstance,
    SwarmManager,
    SwarmState,
    SwarmTopology,
    DEFAULT_SWARM_CONFIGS,
)


@pytest.fixture
def manager():
    return SwarmManager()


@pytest.fixture
def sample_agent_def():
    return AgentDefinition(
        role=AgentRole.CODER,
        model="claude-sonnet-4-20250514",
        tools=["read", "write"],
    )


@pytest.fixture
def sample_config():
    return SwarmConfig(
        name="test-swarm",
        topology=SwarmTopology.MESH,
        agents=[],
        budget_limit=5.0,
        max_concurrent=4,
    )


class TestSwarmTopology:
    def test_all_variants(self):
        assert len(list(SwarmTopology)) == 4

    def test_values(self):
        assert SwarmTopology.HIERARCHICAL.value == "hierarchical"
        assert SwarmTopology.MESH.value == "mesh"
        assert SwarmTopology.ADAPTIVE.value == "adaptive"
        assert SwarmTopology.RING.value == "ring"


class TestAgentRole:
    def test_all_variants(self):
        assert len(list(AgentRole)) == 10

    def test_coder_value(self):
        assert AgentRole.CODER.value == "coder"


class TestSwarmState:
    def test_all_variants(self):
        assert len(list(SwarmState)) == 6

    def test_initial_state(self):
        assert SwarmState.CREATED.value == "created"


class TestAgentDefinition:
    def test_create_with_defaults(self):
        agent = AgentDefinition(role=AgentRole.RESEARCHER)
        assert agent.role == AgentRole.RESEARCHER
        assert agent.model == "claude-sonnet-4-20250514"
        assert agent.tools == []

    def test_create_with_custom(self):
        agent = AgentDefinition(
            role=AgentRole.TESTER,
            model="gpt-3.5-turbo",
            tools=["test", "lint"],
            max_tokens=2048,
            temperature=0.5,
        )
        assert agent.model == "gpt-3.5-turbo"
        assert agent.tools == ["test", "lint"]
        assert agent.max_tokens == 2048
        assert agent.temperature == 0.5


class TestSwarmConfig:
    def test_create_config(self):
        config = SwarmConfig(
            name="my-swarm",
            topology=SwarmTopology.HIERARCHICAL,
            agents=[],
        )
        assert config.name == "my-swarm"
        assert config.topology == SwarmTopology.HIERARCHICAL

    def test_default_values(self):
        config = SwarmConfig(name="test", topology=SwarmTopology.MESH, agents=[])
        assert config.budget_limit == 10.0
        assert config.max_concurrent == 5
        assert config.timeout_seconds == 300
        assert config.retry_count == 2


class TestSwarmInstance:
    def test_create_instance(self, sample_config):
        instance = SwarmInstance(
            swarm_id=uuid.uuid4(),
            config=sample_config,
            state=SwarmState.CREATED,
        )
        assert instance.state == SwarmState.CREATED
        assert instance.config.name == "test-swarm"


class TestSwarmManager:
    def test_register_config(self, manager, sample_config):
        manager.register_config(sample_config)
        retrieved = manager.get_config("test-swarm")
        assert retrieved is not None
        assert retrieved.name == "test-swarm"

    def test_get_config_not_found(self, manager):
        result = manager.get_config("nonexistent")
        assert result is None

    def test_list_configs_empty(self, manager):
        assert len(manager.list_configs()) > 0

    def test_list_configs(self, manager, sample_config):
        manager.register_config(sample_config)
        configs = manager.list_configs()
        assert len(configs) >= 1

    @pytest.mark.asyncio
    async def test_create_swarm(self, manager, sample_config):
        manager.register_config(sample_config)
        instance = await manager.create_swarm("test-swarm")
        assert instance is not None
        assert instance.state == SwarmState.CREATED
        assert instance.config.name == "test-swarm"

    @pytest.mark.asyncio
    async def test_create_swarm_not_found(self, manager):
        with pytest.raises(ValueError):
            await manager.create_swarm("nonexistent")

    @pytest.mark.asyncio
    async def test_get_swarm(self, manager, sample_config):
        manager.register_config(sample_config)
        instance = await manager.create_swarm("test-swarm")
        retrieved = manager.get_swarm(instance.swarm_id)
        assert retrieved is not None
        assert retrieved.swarm_id == instance.swarm_id

    def test_get_swarm_not_found(self, manager):
        result = manager.get_swarm(uuid.uuid4())
        assert result is None

    def test_list_active_swarms_empty(self, manager):
        assert manager.list_active_swarms() == []

    @pytest.mark.asyncio
    async def test_list_active_swarms(self, manager, sample_config):
        manager.register_config(sample_config)
        await manager.create_swarm("test-swarm")
        active = manager.list_active_swarms()
        assert len(active) == 0

    @pytest.mark.asyncio
    async def test_remove_swarm(self, manager, sample_config):
        manager.register_config(sample_config)
        instance = await manager.create_swarm("test-swarm")
        result = manager.remove_swarm(instance.swarm_id)
        assert result is True
        assert manager.get_swarm(instance.swarm_id) is None

    def test_remove_swarm_not_found(self, manager):
        result = manager.remove_swarm(uuid.uuid4())
        assert result is False

    def test_default_configs_loaded(self, manager):
        assert len(DEFAULT_SWARM_CONFIGS) == 4
        names = list(DEFAULT_SWARM_CONFIGS.keys())
        assert "code-swarm" in names
        assert "research-swarm" in names
        assert "security-swarm" in names
        assert "governance-swarm" in names

    def test_register_default_configs(self, manager):
        for config in DEFAULT_SWARM_CONFIGS.values():
            manager.register_config(config)
        assert len(manager.list_configs()) == 4

    @pytest.mark.asyncio
    async def test_create_swarm_with_custom_agents(self, manager, sample_config, sample_agent_def):
        manager.register_config(sample_config)
        instance = await manager.create_swarm("test-swarm", custom_agents=[sample_agent_def])
        assert instance is not None

    @pytest.mark.asyncio
    async def test_multiple_swarms(self, manager):
        for i in range(3):
            config = SwarmConfig(
                name=f"swarm-{i}",
                topology=SwarmTopology.MESH,
                agents=[],
            )
            manager.register_config(config)
            await manager.create_swarm(f"swarm-{i}")
        assert len(manager._active_swarms) == 3
