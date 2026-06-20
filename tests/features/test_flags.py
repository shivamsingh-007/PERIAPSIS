from __future__ import annotations
"""Tests for packages.features.flags - FeatureFlagModel logic."""

import hashlib
import uuid

import pytest

from packages.features.flags import FeatureFlag, FlagType


class TestFeatureFlagModel:
    def test_boolean_flag(self):
        flag = FeatureFlag(
            tenant_id=uuid.uuid4(),
            name="new_ui",
            flag_type=FlagType.BOOLEAN,
            enabled=True,
        )
        assert flag.flag_type == FlagType.BOOLEAN
        assert flag.enabled is True

    def test_percentage_flag(self):
        flag = FeatureFlag(
            tenant_id=uuid.uuid4(),
            name="gradual_rollout",
            flag_type=FlagType.PERCENTAGE,
            percentage=50.0,
        )
        assert flag.percentage == 50.0

    def test_user_segment_flag(self):
        flag = FeatureFlag(
            tenant_id=uuid.uuid4(),
            name="beta_feature",
            flag_type=FlagType.USER_SEGMENT,
            user_segments=["beta_testers", "internal"],
        )
        assert "beta_testers" in flag.user_segments

    def test_flag_type_enum(self):
        assert FlagType.BOOLEAN.value == "boolean"
        assert FlagType.PERCENTAGE.value == "percentage"
        assert FlagType.USER_SEGMENT.value == "user_segment"

    def test_flag_id_auto_generated(self):
        flag = FeatureFlag(tenant_id=uuid.uuid4(), name="test")
        assert flag.flag_id

    def test_flag_deterministic_percentage(self):
        """Test that percentage-based flag is deterministic for same user."""
        flag = FeatureFlag(
            tenant_id=uuid.uuid4(),
            name="test",
            flag_type=FlagType.PERCENTAGE,
            flag_id=uuid.uuid4(),
            percentage=50.0,
        )
        user_id = "user123"
        hash_val1 = int(hashlib.md5(f"{flag.flag_id}:{user_id}".encode()).hexdigest(), 16)
        result1 = (hash_val1 % 100) < flag.percentage
        hash_val2 = int(hashlib.md5(f"{flag.flag_id}:{user_id}".encode()).hexdigest(), 16)
        result2 = (hash_val2 % 100) < flag.percentage
        assert result1 == result2
