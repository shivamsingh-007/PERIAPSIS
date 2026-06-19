from __future__ import annotations

import hashlib
import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from packages.logging.structured import get_logger

logger = get_logger("prompt_versioning")


class PromptVersion(BaseModel):
    version_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    prompt_name: str
    version: str
    template: str
    variables: list[str] = Field(default_factory=list)
    hash: str = ""
    created_at: datetime = Field(default_factory=datetime.utcnow)
    created_by: str = "system"
    is_active: bool = True
    metrics: dict[str, Any] = Field(default_factory=dict)


class PromptVersionManager:
    def __init__(self):
        self._versions: dict[str, list[PromptVersion]] = {}

    def create_version(
        self,
        prompt_name: str,
        template: str,
        variables: list[str] | None = None,
        created_by: str = "system",
    ) -> PromptVersion:
        if prompt_name not in self._versions:
            self._versions[prompt_name] = []

        for v in self._versions[prompt_name]:
            v.is_active = False

        version_num = len(self._versions[prompt_name]) + 1
        version_str = f"v{version_num}"

        content_hash = hashlib.sha256(template.encode()).hexdigest()[:12]

        prompt = PromptVersion(
            prompt_name=prompt_name,
            version=version_str,
            template=template,
            variables=variables or [],
            hash=content_hash,
            created_by=created_by,
        )

        self._versions[prompt_name].append(prompt)
        logger.info(f"Created prompt version: {prompt_name}:{version_str}")
        return prompt

    def get_active(self, prompt_name: str) -> PromptVersion | None:
        versions = self._versions.get(prompt_name, [])
        for v in reversed(versions):
            if v.is_active:
                return v
        return None

    def get_version(self, prompt_name: str, version: str) -> PromptVersion | None:
        for v in self._versions.get(prompt_name, []):
            if v.version == version:
                return v
        return None

    def render(self, prompt_name: str, variables: dict[str, str] | None = None) -> str:
        prompt = self.get_active(prompt_name)
        if not prompt:
            raise ValueError(f"No active prompt found: {prompt_name}")

        template = prompt.template
        if variables:
            for key, value in variables.items():
                template = template.replace(f"{{{key}}}", value)
        return template

    def list_versions(self, prompt_name: str) -> list[PromptVersion]:
        return self._versions.get(prompt_name, [])

    def list_all_prompts(self) -> list[str]:
        return list(self._versions.keys())


prompt_version_manager = PromptVersionManager()
