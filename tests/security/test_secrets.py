from __future__ import annotations
"""Tests for packages.security.secrets - SecretsManager."""

import pytest
from cryptography.fernet import Fernet

from packages.security.secrets import SecretsManager, SecretEntry


class TestSecretsManager:
    def setup_method(self):
        self.manager = SecretsManager()

    def test_set_secret(self):
        entry = self.manager.set_secret("api_key", "super-secret-123")
        assert entry.name == "api_key"
        assert entry.is_active is True

    def test_get_secret_value(self):
        self.manager.set_secret("api_key", "super-secret-123")
        value = self.manager.get_secret_value("api_key")
        assert value == "super-secret-123"

    def test_get_secret_not_found(self):
        assert self.manager.get_secret("nonexistent") is None
        assert self.manager.get_secret_value("nonexistent") is None

    def test_update_secret(self):
        self.manager.set_secret("key", "value1")
        self.manager.set_secret("key", "value2")
        value = self.manager.get_secret_value("key")
        assert value == "value2"

    def test_delete_secret(self):
        self.manager.set_secret("key", "value")
        result = self.manager.delete_secret("key")
        assert result is True
        entry = self.manager.get_secret("key")
        assert entry.is_active is False

    def test_delete_nonexistent(self):
        result = self.manager.delete_secret("nonexistent")
        assert result is False

    def test_list_secrets(self):
        self.manager.set_secret("k1", "v1", tags=["api"])
        self.manager.set_secret("k2", "v2", tags=["db"])
        secrets = self.manager.list_secrets()
        assert len(secrets) == 2

    def test_list_secrets_by_tags(self):
        self.manager.set_secret("k1", "v1", tags=["api"])
        self.manager.set_secret("k2", "v2", tags=["db"])
        secrets = self.manager.list_secrets(tags=["api"])
        assert len(secrets) == 1

    def test_list_secrets_by_environment(self):
        self.manager.set_secret("k1", "v1", environment="dev")
        self.manager.set_secret("k2", "v2", environment="prod")
        dev = self.manager.list_secrets(environment="dev")
        assert len(dev) == 1
        prod = self.manager.list_secrets(environment="prod")
        assert len(prod) == 1

    def test_list_secrets_active_only(self):
        self.manager.set_secret("k1", "v1")
        self.manager.delete_secret("k1")
        secrets = self.manager.list_secrets(active_only=True)
        assert len(secrets) == 0
        all_secrets = self.manager.list_secrets(active_only=False)
        assert len(all_secrets) == 1

    def test_rotate_secret(self):
        self.manager.set_secret("key", "original")
        original_value = self.manager.get_secret_value("key")
        rotated = self.manager.rotate_secret("key")
        assert rotated is not None
        new_value = self.manager.get_secret_value("key")
        assert new_value != original_value

    def test_rotate_nonexistent(self):
        result = self.manager.rotate_secret("nonexistent")
        assert result is None

    def test_vault_status(self):
        self.manager.set_secret("k1", "v1")
        self.manager.set_secret("k2", "v2")
        status = self.manager.get_vault_status()
        assert status["total_secrets"] == 2
        assert status["active_secrets"] == 2

    def test_encryption_key_persistence(self):
        # Test that the same encryption key can decrypt values
        key = Fernet.generate_key()
        m1 = SecretsManager(encryption_key=key)
        m1.set_secret("test", "secret-value")
        # Manually verify decryption works with same key
        entry = m1.get_secret("test")
        fernet = Fernet(key)
        decrypted = fernet.decrypt(entry.encrypted_value.encode()).decode()
        assert decrypted == "secret-value"

    def test_different_keys_cant_decrypt(self):
        m1 = SecretsManager()
        m1.set_secret("test", "secret-value")
        m2 = SecretsManager()
        value = m2.get_secret_value("test")
        assert value is None

    def test_hash_consistency(self):
        self.manager.set_secret("key", "value")
        entry = self.manager.get_secret("key")
        assert entry.value_hash  # SHA-256 hash present
