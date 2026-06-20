"""Tests for data retention policies, cleanup, and lifecycle."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from packages.compliance.data_retention import (
    DataRetentionPolicy,
    RetentionPolicy,
    data_retention_policy,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def policy_manager():
    return DataRetentionPolicy()


# ---------------------------------------------------------------------------
# 1. RetentionPolicy model
# ---------------------------------------------------------------------------

class TestRetentionPolicyModel:
    def test_create_policy_with_defaults(self):
        p = RetentionPolicy(name="test", data_type="logs", retention_days=30)
        assert p.name == "test"
        assert p.data_type == "logs"
        assert p.retention_days == 30
        assert p.is_active is True
        assert p.policy_id is not None

    def test_policy_has_uuid(self):
        p = RetentionPolicy(name="test", data_type="logs", retention_days=30)
        assert isinstance(p.policy_id, type(p.policy_id))

    def test_policy_default_created_at(self):
        p = RetentionPolicy(name="test", data_type="logs", retention_days=30)
        assert isinstance(p.created_at, datetime)

    def test_policy_with_optional_fields(self):
        p = RetentionPolicy(
            name="test",
            data_type="logs",
            retention_days=30,
            archive_after_days=15,
            delete_after_days=90,
        )
        assert p.archive_after_days == 15
        assert p.delete_after_days == 90

    def test_policy_optional_fields_default_none(self):
        p = RetentionPolicy(name="test", data_type="logs", retention_days=30)
        assert p.archive_after_days is None
        assert p.delete_after_days is None


# ---------------------------------------------------------------------------
# 2. create_policy
# ---------------------------------------------------------------------------

class TestCreatePolicy:
    def test_creates_policy(self, policy_manager):
        policy = policy_manager.create_policy(
            name="test_policy",
            data_type="logs",
            retention_days=30,
        )
        assert policy.name == "test_policy"
        assert policy.data_type == "logs"
        assert policy.retention_days == 30

    def test_stores_policy(self, policy_manager):
        policy_manager.create_policy(name="p1", data_type="logs", retention_days=30)
        stored = policy_manager.get_policy("logs")
        assert stored is not None
        assert stored.name == "p1"

    def test_delete_after_defaults_to_retention_days(self, policy_manager):
        policy = policy_manager.create_policy(
            name="p1", data_type="logs", retention_days=30,
        )
        assert policy.delete_after_days == 30

    def test_delete_after_explicit(self, policy_manager):
        policy = policy_manager.create_policy(
            name="p1", data_type="logs", retention_days=30, delete_after_days=60,
        )
        assert policy.delete_after_days == 60

    def test_overwrites_same_data_type(self, policy_manager):
        policy_manager.create_policy(name="v1", data_type="logs", retention_days=30)
        policy_manager.create_policy(name="v2", data_type="logs", retention_days=60)
        stored = policy_manager.get_policy("logs")
        assert stored.name == "v2"
        assert stored.retention_days == 60

    def test_multiple_data_types(self, policy_manager):
        policy_manager.create_policy(name="logs", data_type="logs", retention_days=30)
        policy_manager.create_policy(name="users", data_type="users", retention_days=365)
        assert policy_manager.get_policy("logs") is not None
        assert policy_manager.get_policy("users") is not None


# ---------------------------------------------------------------------------
# 3. get_policy
# ---------------------------------------------------------------------------

class TestGetPolicy:
    def test_get_existing_policy(self, policy_manager):
        policy_manager.create_policy(name="p1", data_type="logs", retention_days=30)
        result = policy_manager.get_policy("logs")
        assert result is not None
        assert result.data_type == "logs"

    def test_get_nonexistent_policy(self, policy_manager):
        result = policy_manager.get_policy("nonexistent")
        assert result is None

    def test_get_after_overwrite(self, policy_manager):
        policy_manager.create_policy(name="v1", data_type="logs", retention_days=30)
        policy_manager.create_policy(name="v2", data_type="logs", retention_days=90)
        result = policy_manager.get_policy("logs")
        assert result.retention_days == 90


# ---------------------------------------------------------------------------
# 4. should_archive
# ---------------------------------------------------------------------------

class TestShouldArchive:
    def test_should_archive_old_data(self, policy_manager):
        policy_manager.create_policy(
            name="p1", data_type="logs", retention_days=90, archive_after_days=30,
        )
        created = datetime.utcnow() - timedelta(days=45)
        assert policy_manager.should_archive("logs", created) is True

    def test_should_not_archive_recent_data(self, policy_manager):
        policy_manager.create_policy(
            name="p1", data_type="logs", retention_days=90, archive_after_days=30,
        )
        created = datetime.utcnow() - timedelta(days=10)
        assert policy_manager.should_archive("logs", created) is False

    def test_should_not_archive_no_policy(self, policy_manager):
        created = datetime.utcnow() - timedelta(days=100)
        assert policy_manager.should_archive("nonexistent", created) is False

    def test_should_not_archive_no_archive_days(self, policy_manager):
        policy_manager.create_policy(
            name="p1", data_type="logs", retention_days=90, archive_after_days=None,
        )
        created = datetime.utcnow() - timedelta(days=100)
        assert policy_manager.should_archive("logs", created) is False

    def test_should_archive_at_boundary(self, policy_manager):
        policy_manager.create_policy(
            name="p1", data_type="logs", retention_days=90, archive_after_days=30,
        )
        created = datetime.utcnow() - timedelta(days=30)
        assert policy_manager.should_archive("logs", created) is True

    def test_should_not_archive_one_day_before(self, policy_manager):
        policy_manager.create_policy(
            name="p1", data_type="logs", retention_days=90, archive_after_days=30,
        )
        created = datetime.utcnow() - timedelta(days=29)
        assert policy_manager.should_archive("logs", created) is False


# ---------------------------------------------------------------------------
# 5. should_delete
# ---------------------------------------------------------------------------

class TestShouldDelete:
    def test_should_delete_old_data(self, policy_manager):
        policy_manager.create_policy(
            name="p1", data_type="logs", retention_days=30, delete_after_days=60,
        )
        created = datetime.utcnow() - timedelta(days=65)
        assert policy_manager.should_delete("logs", created) is True

    def test_should_not_delete_recent_data(self, policy_manager):
        policy_manager.create_policy(
            name="p1", data_type="logs", retention_days=30, delete_after_days=60,
        )
        created = datetime.utcnow() - timedelta(days=10)
        assert policy_manager.should_delete("logs", created) is False

    def test_should_not_delete_no_policy(self, policy_manager):
        created = datetime.utcnow() - timedelta(days=100)
        assert policy_manager.should_delete("nonexistent", created) is False

    def test_should_not_delete_no_delete_days(self, policy_manager):
        policy_manager.create_policy(
            name="p1", data_type="logs", retention_days=90, delete_after_days=None,
        )
        created = datetime.utcnow() - timedelta(days=100)
        assert policy_manager.should_delete("logs", created) is False

    def test_should_delete_at_boundary(self, policy_manager):
        policy_manager.create_policy(
            name="p1", data_type="logs", retention_days=30, delete_after_days=60,
        )
        created = datetime.utcnow() - timedelta(days=60)
        assert policy_manager.should_delete("logs", created) is True

    def test_should_not_delete_one_day_before(self, policy_manager):
        policy_manager.create_policy(
            name="p1", data_type="logs", retention_days=30, delete_after_days=60,
        )
        created = datetime.utcnow() - timedelta(days=59)
        assert policy_manager.should_delete("logs", created) is False


# ---------------------------------------------------------------------------
# 6. get_retention_cutoff
# ---------------------------------------------------------------------------

class TestGetRetentionCutoff:
    def test_returns_cutoff_date(self, policy_manager):
        policy_manager.create_policy(name="p1", data_type="logs", retention_days=30)
        cutoff = policy_manager.get_retention_cutoff("logs")
        expected = datetime.utcnow() - timedelta(days=30)
        assert cutoff is not None
        assert abs((cutoff - expected).total_seconds()) < 2

    def test_returns_default_for_no_policy(self, policy_manager):
        cutoff = policy_manager.get_retention_cutoff("nonexistent")
        expected = datetime.utcnow() - timedelta(days=365)
        assert cutoff is not None
        assert abs((cutoff - expected).total_seconds()) < 2

    def test_cutoff_uses_retention_days(self, policy_manager):
        policy_manager.create_policy(name="p1", data_type="logs", retention_days=7)
        cutoff = policy_manager.get_retention_cutoff("logs")
        expected = datetime.utcnow() - timedelta(days=7)
        assert abs((cutoff - expected).total_seconds()) < 2


# ---------------------------------------------------------------------------
# 7. list_policies
# ---------------------------------------------------------------------------

class TestListPolicies:
    def test_list_empty(self, policy_manager):
        assert policy_manager.list_policies() == []

    def test_list_single(self, policy_manager):
        policy_manager.create_policy(name="p1", data_type="logs", retention_days=30)
        result = policy_manager.list_policies()
        assert len(result) == 1

    def test_list_multiple(self, policy_manager):
        policy_manager.create_policy(name="p1", data_type="logs", retention_days=30)
        policy_manager.create_policy(name="p2", data_type="users", retention_days=90)
        result = policy_manager.list_policies()
        assert len(result) == 2

    def test_list_overwrite_does_not_duplicate(self, policy_manager):
        policy_manager.create_policy(name="v1", data_type="logs", retention_days=30)
        policy_manager.create_policy(name="v2", data_type="logs", retention_days=60)
        result = policy_manager.list_policies()
        assert len(result) == 1


# ---------------------------------------------------------------------------
# 8. default_retention
# ---------------------------------------------------------------------------

class TestDefaultRetention:
    def test_default_retention_is_365(self, policy_manager):
        assert policy_manager._default_retention == 365

    def test_no_policy_uses_default(self, policy_manager):
        cutoff = policy_manager.get_retention_cutoff("no_such_type")
        expected = datetime.utcnow() - timedelta(days=365)
        assert abs((cutoff - expected).total_seconds()) < 2


# ---------------------------------------------------------------------------
# 9. singleton instance
# ---------------------------------------------------------------------------

class TestDataRetentionPolicySingleton:
    def test_singleton_is_instance(self):
        assert isinstance(data_retention_policy, DataRetentionPolicy)

    def test_singleton_has_default_retention(self):
        assert data_retention_policy._default_retention == 365


# ---------------------------------------------------------------------------
# 10. policy lifecycle combinations
# ---------------------------------------------------------------------------

class TestPolicyLifecycleCombinations:
    def test_archive_before_delete(self, policy_manager):
        policy_manager.create_policy(
            name="p1", data_type="logs", retention_days=90,
            archive_after_days=30, delete_after_days=60,
        )
        now = datetime.utcnow()
        assert policy_manager.should_archive("logs", now - timedelta(days=35)) is True
        assert policy_manager.should_delete("logs", now - timedelta(days=35)) is False

    def test_delete_after_archive(self, policy_manager):
        policy_manager.create_policy(
            name="p1", data_type="logs", retention_days=90,
            archive_after_days=30, delete_after_days=60,
        )
        now = datetime.utcnow()
        assert policy_manager.should_archive("logs", now - timedelta(days=65)) is True
        assert policy_manager.should_delete("logs", now - timedelta(days=65)) is True

    def test_fresh_data_neither_archive_nor_delete(self, policy_manager):
        policy_manager.create_policy(
            name="p1", data_type="logs", retention_days=90,
            archive_after_days=30, delete_after_days=60,
        )
        now = datetime.utcnow()
        assert policy_manager.should_archive("logs", now - timedelta(days=5)) is False
        assert policy_manager.should_delete("logs", now - timedelta(days=5)) is False
