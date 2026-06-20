from __future__ import annotations
"""Tests for packages.compliance.data_retention - DataRetentionPolicy."""

from datetime import datetime, timedelta

import pytest

from packages.compliance.data_retention import DataRetentionPolicy, RetentionPolicy


class TestDataRetentionPolicy:
    def setup_method(self):
        self.policy = DataRetentionPolicy()

    def test_create_policy(self):
        p = self.policy.create_policy("Keep Runs", "runs", retention_days=365)
        assert p.name == "Keep Runs"
        assert p.retention_days == 365
        assert p.is_active is True

    def test_get_policy(self):
        self.policy.create_policy("Keep Runs", "runs", retention_days=365)
        p = self.policy.get_policy("runs")
        assert p is not None
        assert p.retention_days == 365

    def test_get_policy_not_found(self):
        assert self.policy.get_policy("nonexistent") is None

    def test_should_archive_yes(self):
        self.policy.create_policy("Archive Logs", "logs", retention_days=365, archive_after_days=30)
        created = datetime.utcnow() - timedelta(days=31)
        assert self.policy.should_archive("logs", created) is True

    def test_should_archive_no(self):
        self.policy.create_policy("Archive Logs", "logs", retention_days=365, archive_after_days=30)
        created = datetime.utcnow() - timedelta(days=10)
        assert self.policy.should_archive("logs", created) is False

    def test_should_archive_no_policy(self):
        created = datetime.utcnow() - timedelta(days=100)
        assert self.policy.should_archive("nonexistent", created) is False

    def test_should_delete_yes(self):
        self.policy.create_policy("Delete Old", "temp", retention_days=90, delete_after_days=90)
        created = datetime.utcnow() - timedelta(days=91)
        assert self.policy.should_delete("temp", created) is True

    def test_should_delete_no(self):
        self.policy.create_policy("Delete Old", "temp", retention_days=90, delete_after_days=90)
        created = datetime.utcnow() - timedelta(days=30)
        assert self.policy.should_delete("temp", created) is False

    def test_get_retention_cutoff(self):
        self.policy.create_policy("Policy", "data", retention_days=30)
        cutoff = self.policy.get_retention_cutoff("data")
        expected = datetime.utcnow() - timedelta(days=30)
        assert abs((cutoff - expected).total_seconds()) < 2

    def test_get_retention_cutoff_default(self):
        cutoff = self.policy.get_retention_cutoff("nonexistent")
        expected = datetime.utcnow() - timedelta(days=365)
        assert abs((cutoff - expected).total_seconds()) < 2

    def test_list_policies(self):
        self.policy.create_policy("p1", "runs", 365)
        self.policy.create_policy("p2", "logs", 90)
        policies = self.policy.list_policies()
        assert len(policies) == 2
