from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Any

import yaml
from pydantic import BaseModel, Field

from packages.logging.structured import get_logger

logger = get_logger("swarm")


class SwarmTopology(str, Enum):
    HIERARCHICAL = "hierarchical"
    MESH = "mesh"
    ADAPTIVE = "adaptive"
    RING = "ring"


class AgentRole(str, Enum):
    RESEARCHER = "researcher"
    PLANNER = "planner"
    CODER = "coder"
    REFACTORER = "refactorer"
    TESTER = "tester"
    SECURITY_REVIEWER = "security_reviewer"
    GOVERNANCE_REVIEWER = "governance_reviewer"
    CHECKER = "checker"
    DOC_WRITER = "doc_writer"
    ARCHITECT = "architect"


class AgentDefinition(BaseModel):
    role: AgentRole
    model: str = "claude-sonnet-4-20250514"
    tools: list[str] = Field(default_factory=list)
    allowed_environments: list[str] = Field(default_factory=lambda: ["dev"])
    max_tokens: int = 4096
    temperature: float = 0.7
    system_prompt: str | None = None
    policy_scope: list[str] = Field(default_factory=list)


class SwarmConfig(BaseModel):
    name: str
    topology: SwarmTopology = SwarmTopology.HIERARCHICAL
    agents: list[AgentDefinition] = Field(default_factory=list)
    budget_limit: float = 10.0
    max_concurrent: int = 5
    timeout_seconds: int = 300
    retry_count: int = 2
    metadata: dict[str, Any] = Field(default_factory=dict)


class SwarmState(str, Enum):
    CREATED = "created"
    INITIALIZING = "initializing"
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"


class SwarmInstance(BaseModel):
    swarm_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    config: SwarmConfig
    state: SwarmState = SwarmState.CREATED
    ruflo_swarm_id: str | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    agent_assignments: dict[str, str] = Field(default_factory=dict)


DEFAULT_SWARM_CONFIGS: dict[str, SwarmConfig] = {
    "code-swarm": SwarmConfig(
        name="code-swarm",
        topology=SwarmTopology.HIERARCHICAL,
        agents=[
            AgentDefinition(
                role=AgentRole.PLANNER,
                tools=["read", "search", "analyze"],
                system_prompt="You break down coding tasks into clear, executable sub-tasks.",
            ),
            AgentDefinition(
                role=AgentRole.CODER,
                tools=["read", "write", "edit", "search", "bash"],
                system_prompt="You write production-quality code following project conventions.",
            ),
            AgentDefinition(
                role=AgentRole.TESTER,
                tools=["read", "write", "bash"],
                system_prompt="You write comprehensive tests for code changes.",
            ),
            AgentDefinition(
                role=AgentRole.CHECKER,
                tools=["read", "bash", "search"],
                system_prompt="You validate that code changes meet quality standards.",
            ),
        ],
        budget_limit=15.0,
    ),
    "research-swarm": SwarmConfig(
        name="research-swarm",
        topology=SwarmTopology.MESH,
        agents=[
            AgentDefinition(
                role=AgentRole.RESEARCHER,
                tools=["read", "search", "web_fetch"],
                system_prompt="You gather factual evidence and source citations.",
            ),
            AgentDefinition(
                role=AgentRole.PLANNER,
                tools=["read", "search"],
                system_prompt="You synthesize research findings into actionable plans.",
            ),
        ],
        budget_limit=8.0,
    ),
    "security-swarm": SwarmConfig(
        name="security-swarm",
        topology=SwarmTopology.HIERARCHICAL,
        agents=[
            AgentDefinition(
                role=AgentRole.SECURITY_REVIEWER,
                tools=["read", "search", "bash"],
                system_prompt="You perform security audits, find vulnerabilities, and recommend fixes.",
                policy_scope=["security:read", "security:audit"],
            ),
            AgentDefinition(
                role=AgentRole.GOVERNANCE_REVIEWER,
                tools=["read", "search"],
                system_prompt="You verify compliance with governance policies.",
                policy_scope=["governance:read", "governance:audit"],
            ),
        ],
        budget_limit=10.0,
    ),
    "governance-swarm": SwarmConfig(
        name="governance-swarm",
        topology=SwarmTopology.HIERARCHICAL,
        agents=[
            AgentDefinition(
                role=AgentRole.GOVERNANCE_REVIEWER,
                tools=["read", "search"],
                system_prompt="You enforce governance policies and compliance requirements.",
                policy_scope=["governance:read", "governance:write", "governance:audit"],
            ),
        ],
        budget_limit=5.0,
    ),
}


class SwarmManager:
    def __init__(self):
        self._active_swarms: dict[uuid.UUID, SwarmInstance] = {}
        self._configs: dict[str, SwarmConfig] = dict(DEFAULT_SWARM_CONFIGS)

    def register_config(self, config: SwarmConfig) -> None:
        self._configs[config.name] = config
        logger.info(f"Registered swarm config: {config.name}")

    def get_config(self, name: str) -> SwarmConfig | None:
        return self._configs.get(name)

    def list_configs(self) -> list[SwarmConfig]:
        return list(self._configs.values())

    async def create_swarm(
        self,
        config_name: str,
        custom_agents: list[AgentDefinition] | None = None,
        budget_limit: float | None = None,
    ) -> SwarmInstance:
        config = self._configs.get(config_name)
        if not config:
            raise ValueError(f"Swarm config '{config_name}' not found")

        if custom_agents:
            config = config.model_copy(update={"agents": custom_agents})
        if budget_limit is not None:
            config = config.model_copy(update={"budget_limit": budget_limit})

        instance = SwarmInstance(config=config, state=SwarmState.CREATED)
        self._active_swarms[instance.swarm_id] = instance

        logger.info(f"Created swarm {instance.swarm_id} using config '{config_name}'")
        return instance

    async def initialize_swarm(self, swarm_id: uuid.UUID, ruflo_client: Any) -> SwarmInstance:
        instance = self._active_swarms.get(swarm_id)
        if not instance:
            raise ValueError(f"Swarm {swarm_id} not found")

        instance.state = SwarmState.INITIALIZING

        try:
            result = await ruflo_client.swarm_init(
                topology=instance.config.topology.value,
                agents=[a.role.value for a in instance.config.agents],
            )
            instance.ruflo_swarm_id = result.get("swarmId")
            instance.state = SwarmState.ACTIVE
            logger.info(f"Swarm {swarm_id} initialized with Ruflo ID: {instance.ruflo_swarm_id}")
        except Exception as e:
            instance.state = SwarmState.FAILED
            logger.error(f"Failed to initialize swarm {swarm_id}: {e}")
            raise

        return instance

    def get_swarm(self, swarm_id: uuid.UUID) -> SwarmInstance | None:
        return self._active_swarms.get(swarm_id)

    def list_active_swarms(self) -> list[SwarmInstance]:
        return [
            s for s in self._active_swarms.values()
            if s.state in (SwarmState.ACTIVE, SwarmState.INITIALIZING)
        ]

    def remove_swarm(self, swarm_id: uuid.UUID) -> bool:
        if swarm_id in self._active_swarms:
            del self._active_swarms[swarm_id]
            return True
        return False

    def load_from_yaml(self, yaml_path: str) -> None:
        with open(yaml_path) as f:
            data = yaml.safe_load(f)

        for name, config_data in data.get("swarms", {}).items():
            agents = [
                AgentDefinition(**a) for a in config_data.get("agents", [])
            ]
            config = SwarmConfig(
                name=name,
                topology=SwarmTopology(config_data.get("topology", "hierarchical")),
                agents=agents,
                budget_limit=config_data.get("budget_limit", 10.0),
                max_concurrent=config_data.get("max_concurrent", 5),
                timeout_seconds=config_data.get("timeout_seconds", 300),
            )
            self.register_config(config)

        logger.info(f"Loaded swarm configs from {yaml_path}")


swarm_manager = SwarmManager()
