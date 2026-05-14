"""Tests for resource permission models."""

import pytest
from django.core.files.base import ContentFile
from django.core.exceptions import ValidationError

from files.access import (
    can_access_file,
    can_access_folder,
    can_manage_folder,
    can_upload_to_folder,
    get_accessible_files,
    get_accessible_folders,
)
from files.encryption import compute_checksum, encrypt_file
from files.models import File, FilePermission, Folder, FolderPermission
from users.models import Department, DepartmentMembership
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


@pytest.mark.django_db
class TestFolderPermissionAccess:
    def test_user_permission_allows_folder_view(self, regular_user, another_user):
        folder = Folder.objects.create(name="Shared", owner=regular_user)
        FolderPermission.objects.create(
            folder=folder,
            user=another_user,
            access=PermissionAction.VIEW,
            granted_by=regular_user,
        )

        assert can_access_folder(another_user, folder) is True
        assert folder in get_accessible_folders(another_user)

    def test_department_permission_allows_upload_for_members(
        self, regular_user, another_user, department
    ):
        folder = Folder.objects.create(name="Department shared", owner=regular_user)
        DepartmentMembership.objects.create(user=another_user, department=department)
        FolderPermission.objects.create(
            folder=folder,
            department=department,
            access=PermissionAction.UPLOAD,
            granted_by=regular_user,
        )

        assert can_upload_to_folder(another_user, folder) is True

    def test_department_role_permission_is_limited_to_that_role(
        self, regular_user, another_user, department
    ):
        folder = Folder.objects.create(name="Heads only", owner=regular_user)
        DepartmentMembership.objects.create(
            user=another_user,
            department=department,
            role=DepartmentMembership.Role.MEMBER,
        )
        FolderPermission.objects.create(
            folder=folder,
            department=department,
            department_role=DepartmentMembership.Role.HEAD,
            access=PermissionAction.MANAGE,
            granted_by=regular_user,
        )

        assert can_manage_folder(another_user, folder) is False

    def test_deny_overrides_department_membership(self, regular_user, another_user, department):
        folder = Folder.objects.create(
            name="Denied department folder",
            owner=regular_user,
            department=department,
        )
        DepartmentMembership.objects.create(user=another_user, department=department)
        FolderPermission.objects.create(
            folder=folder,
            user=another_user,
            access=PermissionAction.VIEW,
            effect=PermissionEffect.DENY,
            granted_by=regular_user,
        )

        assert can_access_folder(another_user, folder) is False

    def test_parent_permission_is_inherited_by_child_folder(
        self, regular_user, another_user
    ):
        parent = Folder.objects.create(name="Parent", owner=regular_user)
        child = Folder.objects.create(name="Child", owner=regular_user, parent=parent)
        FolderPermission.objects.create(
            folder=parent,
            user=another_user,
            access=PermissionAction.VIEW,
            granted_by=regular_user,
        )

        assert can_access_folder(another_user, child) is True
        assert child in get_accessible_folders(another_user, parent=parent)

    def test_child_deny_overrides_parent_allow(self, regular_user, another_user):
        parent = Folder.objects.create(name="Parent allow", owner=regular_user)
        child = Folder.objects.create(name="Child deny", owner=regular_user, parent=parent)
        FolderPermission.objects.create(
            folder=parent,
            user=another_user,
            access=PermissionAction.VIEW,
            effect=PermissionEffect.ALLOW,
            granted_by=regular_user,
        )
        FolderPermission.objects.create(
            folder=child,
            user=another_user,
            access=PermissionAction.VIEW,
            effect=PermissionEffect.DENY,
            granted_by=regular_user,
        )

        assert can_access_folder(another_user, child) is False
        assert child not in get_accessible_folders(another_user, parent=parent)

    def test_child_allow_overrides_parent_deny(self, regular_user, another_user):
        parent = Folder.objects.create(name="Parent deny", owner=regular_user)
        child = Folder.objects.create(name="Child allow", owner=regular_user, parent=parent)
        FolderPermission.objects.create(
            folder=parent,
            user=another_user,
            access=PermissionAction.VIEW,
            effect=PermissionEffect.DENY,
            granted_by=regular_user,
        )
        FolderPermission.objects.create(
            folder=child,
            user=another_user,
            access=PermissionAction.VIEW,
            effect=PermissionEffect.ALLOW,
            granted_by=regular_user,
        )

        assert can_access_folder(another_user, child) is True

    def test_file_inherits_download_permission_from_folder(self, regular_user, another_user):
        folder = Folder.objects.create(name="Folder download", owner=regular_user)
        raw = b"folder inherited file"
        file_obj = File.objects.create(
            owner=regular_user,
            folder=folder,
            original_name="inherited.txt",
            encrypted_file=ContentFile(encrypt_file(raw), name="inherited.txt"),
            mime_type="text/plain",
            size=len(raw),
            checksum=compute_checksum(raw),
        )
        FolderPermission.objects.create(
            folder=folder,
            user=another_user,
            access=PermissionAction.DOWNLOAD,
            granted_by=regular_user,
        )

        assert can_access_file(another_user, file_obj) is True
        assert file_obj in get_accessible_files(another_user)
