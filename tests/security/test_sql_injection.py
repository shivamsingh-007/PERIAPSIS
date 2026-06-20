"""Tests for SQL injection prevention in routes/runs.py."""

from __future__ import annotations

import pytest

from apps.api.routes.runs import ALLOWED_UPDATE_FIELDS


class TestSQLInjectionPrevention:
    def test_allowed_fields_whitelist(self):
        """Only status and terminal_state are allowed update fields."""
        assert ALLOWED_UPDATE_FIELDS == {"status", "terminal_state"}

    def test_injection_via_field_name_rejected(self):
        """Malicious field names should not be in the whitelist."""
        malicious_fields = [
            "status; DROP TABLE runs; --",
            "terminal_state OR 1=1",
            "status' UNION SELECT * FROM auth_tokens --",
            "1; DELETE FROM runs",
            "status\nWHERE 1=1",
        ]
        for field in malicious_fields:
            assert field not in ALLOWED_UPDATE_FIELDS, f"Field '{field}' should not be allowed"

    def test_normal_fields_accepted(self):
        """Valid field names should be in the whitelist."""
        assert "status" in ALLOWED_UPDATE_FIELDS
        assert "terminal_state" in ALLOWED_UPDATE_FIELDS

    def test_injection_via_value_not_in_whitelist_check(self):
        """The whitelist check is on field names, not values.
        Values are always parameterized by SQLAlchemy."""
        # This test documents that values are safe because they go through
        # SQLAlchemy's parameterized query system, not string interpolation.
        # The vulnerability was in field name interpolation, not values.
        assert "status" in ALLOWED_UPDATE_FIELDS  # Valid field
        # A value like "'; DROP TABLE runs; --" would be safely parameterized
        # as a string value, not executed as SQL.

    def test_fstring_not_used_for_update(self):
        """The update_query should not use f-strings with user input."""
        import inspect
        from apps.api.routes.runs import update_run
        source = inspect.getsource(update_run)
        # Should use SQLAlchemy update() not f-string SQL
        assert "update(Run)" in source or "session.execute" in source
        # Should NOT have f-string SQL with field concatenation
        assert "f\"UPDATE runs SET {field}" not in source
