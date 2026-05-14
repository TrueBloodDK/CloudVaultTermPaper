"""Tests for folder permission management UI."""

import pytest
from django.urls import reverse

from audit.models import AuditLog
from files.models import Folder, FolderPermission
from users.models import Department, DepartmentMembership
from users.rbac import PermissionAction, PermissionEffect


@pytest.fixture
def manage_folder(db, regular_user):
    return Folder.objects.create(name="Managed", owner=regular_user)


@pytest.fixture
def manage_department(db):
    return Department.objects.create(name="Разработка")


@pytest.mark.django_db
class TestManageFolderPermissions:
    def test_system_admin_can_grant_user_folder_permission(
        self, admin_client, manage_folder, another_user, admin_user
    ):
        resp = admin_client.post(
            reverse("manage:folder-permission-create", args=[manage_folder.id]),
            {
                "subject_type": "user",
                "user_email": another_user.email,
                "access": PermissionAction.VIEW,
                "effect": PermissionEffect.ALLOW,
            },
        )

        assert resp.status_code == 302
        assert FolderPermission.objects.filter(
            folder=manage_folder,
            user=another_user,
            access=PermissionAction.VIEW,
            effect=PermissionEffect.ALLOW,
        ).exists()
        assert AuditLog.objects.filter(
            user=admin_user,
            action=AuditLog.Action.PERMISSION_GRANT,
            extra__subject=str(another_user),
            extra__access=PermissionAction.VIEW,
        ).exists()

    def test_system_admin_can_grant_department_role_permission(
        self, admin_client, manage_folder, manage_department
    ):
        resp = admin_client.post(
            reverse("manage:folder-permission-create", args=[manage_folder.id]),
            {
                "subject_type": "department_role",
                "department": manage_department.id,
                "department_role": DepartmentMembership.Role.HEAD,
                "access": PermissionAction.MANAGE,
                "effect": PermissionEffect.ALLOW,
            },
        )

        assert resp.status_code == 302
        assert FolderPermission.objects.filter(
            folder=manage_folder,
            department=manage_department,
            department_role=DepartmentMembership.Role.HEAD,
            access=PermissionAction.MANAGE,
        ).exists()

    def test_system_admin_can_revoke_folder_permission(
        self, admin_client, manage_folder, another_user, admin_user
    ):
        permission = FolderPermission.objects.create(
            folder=manage_folder,
            user=another_user,
            access=PermissionAction.VIEW,
            granted_by=admin_user,
        )

        resp = admin_client.post(
            reverse("manage:folder-permission-delete", args=[permission.id])
        )

        assert resp.status_code == 302
        assert not FolderPermission.objects.filter(pk=permission.pk).exists()
        assert AuditLog.objects.filter(
            user=admin_user,
            action=AuditLog.Action.PERMISSION_REVOKE,
            extra__subject=str(another_user),
            extra__access=PermissionAction.VIEW,
        ).exists()

    def test_regular_user_cannot_grant_folder_permission(
        self, auth_client, manage_folder, another_user
    ):
        resp = auth_client.post(
            reverse("manage:folder-permission-create", args=[manage_folder.id]),
            {
                "subject_type": "user",
                "user_email": another_user.email,
                "access": PermissionAction.VIEW,
                "effect": PermissionEffect.ALLOW,
            },
        )

        assert resp.status_code == 302
        assert not FolderPermission.objects.filter(folder=manage_folder).exists()
