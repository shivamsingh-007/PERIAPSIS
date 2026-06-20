from __future__ import annotations
"""Tests for packages.security.rbac - RBACMiddleware, ROLE_PERMISSIONS."""

import pytest

from packages.security.rbac import (
    Permission,
    RBACMiddleware,
    Role,
    ROLE_PERMISSIONS,
)


class TestRoles:
    def test_all_roles(self):
        assert len(list(Role)) == 3

    def test_admin_value(self):
        assert Role.ADMIN.value == "admin"


class TestPermissions:
    def test_all_permissions(self):
        assert len(list(Permission)) == 12


class TestRolePermissions:
    def test_admin_has_all_permissions(self):
        admin_perms = ROLE_PERMISSIONS[Role.ADMIN]
        for perm in Permission:
            assert perm in admin_perms

    def test_viewer_has_limited_permissions(self):
        viewer_perms = ROLE_PERMISSIONS[Role.VIEWER]
        assert Permission.RUN_READ in viewer_perms
        assert Permission.MEMORY_READ in viewer_perms
        assert Permission.RUN_CREATE not in viewer_perms
        assert Permission.RUN_DELETE not in viewer_perms

    def test_operator_has_middle_permissions(self):
        operator_perms = ROLE_PERMISSIONS[Role.OPERATOR]
        assert Permission.RUN_CREATE in operator_perms
        assert Permission.RUN_READ in operator_perms
        assert Permission.RUN_EXECUTE in operator_perms
        assert Permission.MEMORY_WRITE in operator_perms
        assert Permission.POLICY_UPDATE not in operator_perms
        assert Permission.USER_MANAGE not in operator_perms
        assert Permission.TENANT_MANAGE not in operator_perms
