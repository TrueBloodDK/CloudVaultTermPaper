"""Tests for resource permission models."""

import pytest
from django.core.exceptions import ValidationError

from files.models import FilePermission, Folder, FolderPermission
from users.models import Department
from users.rbac import PermissionAction, PermissionEffect


@pytest.fixture
def department(db):
    return Department.objects.create(name="Бухгалтерия")


@pytest.fixture
def folder(db, regular_user, department):
    return Folder.objects.create(
        name="Отчёты",
        owner=regular_user,
        department=department,
    )


@pytest.mark.django_db
class TestFolderPermission:
    def test_user_permission_is_valid(self, folder, regular_user, admin_user):
        permission = FolderPermission.objects.create(
            folder=folder,
            user=regular_user,
            access=PermissionAction.VIEW,
            effect=PermissionEffect.ALLOW,
            granted_by=admin_user,
        )

        assert permission.subject_label == str(regular_user)
        assert permission.is_allow is True
        assert permission.is_deny is False

    def test_department_permission_is_valid(self, folder, department, admin_user):
        permission = FolderPermission.objects.create(
            folder=folder,
            department=department,
            access=PermissionAction.UPLOAD,
            granted_by=admin_user,
        )

        assert permission.subject_label == department.name
        assert permission.access == PermissionAction.UPLOAD

    def test_department_role_permission_is_valid(self, folder, department, admin_user):
        permission = FolderPermission.objects.create(
            folder=folder,
            department=department,
            department_role="head",
            access=PermissionAction.MANAGE,
            granted_by=admin_user,
        )

        assert "Руководитель отдела" in permission.subject_label

    def test_permission_requires_exactly_one_subject(self, folder):
        permission = FolderPermission(folder=folder, access=PermissionAction.VIEW)

        with pytest.raises(ValidationError):
            permission.full_clean()

    def test_user_permission_cannot_have_department_role(self, folder, regular_user):
        permission = FolderPermission(
            folder=folder,
            user=regular_user,
            department_role="head",
            access=PermissionAction.VIEW,
        )

        with pytest.raises(ValidationError):
            permission.full_clean()


@pytest.mark.django_db
class TestFilePermission:
    def test_file_permission_can_target_department(self, sample_file, department, admin_user):
        permission = FilePermission.objects.create(
            file=sample_file,
            department=department,
            access=PermissionAction.DOWNLOAD,
            effect=PermissionEffect.DENY,
            granted_by=admin_user,
        )

        assert permission.subject_label == department.name
        assert permission.is_deny is True
