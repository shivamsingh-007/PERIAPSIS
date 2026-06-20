from __future__ import annotations
"""Tests for packages.intelligence.prompt_versioning - PromptVersionManager."""

import pytest

from packages.intelligence.prompt_versioning import PromptVersion, PromptVersionManager


class TestPromptVersionManager:
    def setup_method(self):
        self.manager = PromptVersionManager()

    def test_create_version(self):
        version = self.manager.create_version(
            "greeting", "Hello {name}!", variables=["name"]
        )
        assert version.prompt_name == "greeting"
        assert version.version == "v1"
        assert version.is_active is True

    def test_create_multiple_versions(self):
        self.manager.create_version("greeting", "Hello {name}!")
        self.manager.create_version("greeting", "Hi {name}!")
        versions = self.manager.list_versions("greeting")
        assert len(versions) == 2
        assert versions[0].version == "v1"
        assert versions[1].version == "v2"

    def test_previous_version_deactivated(self):
        v1 = self.manager.create_version("test", "template1")
        assert v1.is_active is True
        v2 = self.manager.create_version("test", "template2")
        assert v2.is_active is True
        assert v1.is_active is False

    def test_get_active(self):
        self.manager.create_version("test", "old")
        self.manager.create_version("test", "new")
        active = self.manager.get_active("test")
        assert active.template == "new"

    def test_get_active_not_found(self):
        assert self.manager.get_active("nonexistent") is None

    def test_get_version(self):
        self.manager.create_version("test", "template1")
        v = self.manager.get_version("test", "v1")
        assert v is not None
        assert v.template == "template1"

    def test_get_version_not_found(self):
        assert self.manager.get_version("test", "v99") is None

    def test_render(self):
        self.manager.create_version("greeting", "Hello {name}, welcome to {place}!")
        result = self.manager.render("greeting", {"name": "Alice", "place": "Wonderland"})
        assert result == "Hello Alice, welcome to Wonderland!"

    def test_render_no_variables(self):
        self.manager.create_version("static", "No variables here")
        result = self.manager.render("static")
        assert result == "No variables here"

    def test_render_not_found(self):
        with pytest.raises(ValueError, match="No active prompt found"):
            self.manager.render("nonexistent")

    def test_list_versions(self):
        self.manager.create_version("test", "v1")
        self.manager.create_version("test", "v2")
        versions = self.manager.list_versions("test")
        assert len(versions) == 2

    def test_list_versions_empty(self):
        assert self.manager.list_versions("nonexistent") == []

    def test_list_all_prompts(self):
        self.manager.create_version("greeting", "Hello!")
        self.manager.create_version("farewell", "Bye!")
        prompts = self.manager.list_all_prompts()
        assert "greeting" in prompts
        assert "farewell" in prompts

    def test_content_hash(self):
        v = self.manager.create_version("test", "Hello!")
        assert v.hash
        assert len(v.hash) == 12
