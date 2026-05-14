"""API permission tests for centralized RBAC checks."""

import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from files.models import File, Folder, FolderPermission, FilePermission
from users.rbac import PermissionAction


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def folder_with_file(db, regular_user, sample_file):
    folder = Folder.objects.create(name="API shared", owner=regular_user)
    sample_file.folder = folder
    sample_file.save(update_fields=["folder"])
    return folder, sample_file


@pytest.mark.django_db
class TestApiRbacPermissions:
    def test_folder_delete_permission_allows_api_file_delete(
        self, api_client, another_user, regular_user, folder_with_file
    ):
        folder, file_obj = folder_with_file
        FolderPermission.objects.create(
            folder=folder,
            user=another_user,
            access=PermissionAction.DELETE,
            granted_by=regular_user,
        )
        api_client.force_authenticate(user=another_user)

        resp = api_client.delete(reverse("file-delete", args=[file_obj.id]))

        assert resp.status_code == 200
        file_obj.refresh_from_db()
        assert file_obj.status == File.Status.DELETED

    def test_folder_share_permission_allows_api_file_share(
        self, api_client, another_user, regular_user, django_user_model, folder_with_file
    ):
        folder, file_obj = folder_with_file
        target_user = django_user_model.objects.create_user(
            email="target@test.ru",
            full_name="Получатель Доступа",
            password="targetpass123",
        )
        FolderPermission.objects.create(
            folder=folder,
            user=another_user,
            access=PermissionAction.SHARE,
            granted_by=regular_user,
        )
        FolderPermission.objects.create(
            folder=folder,
            user=another_user,
            access=PermissionAction.READ,
            granted_by=regular_user,
        )
        api_client.force_authenticate(user=another_user)

        resp = api_client.post(
            reverse("file-share", args=[file_obj.id]),
            {"user_email": target_user.email, "access": FilePermission.Access.READ},
            format="json",
        )

        assert resp.status_code == 200
        assert FilePermission.objects.filter(file=file_obj, user=target_user).exists()

    def test_cannot_grant_permission_above_own_access(
        self, api_client, another_user, regular_user, django_user_model, folder_with_file
    ):
        folder, file_obj = folder_with_file
        target_user = django_user_model.objects.create_user(
            email="limited-target@test.ru",
            full_name="Ограниченный Получатель",
            password="targetpass123",
        )
        FolderPermission.objects.create(
            folder=folder,
            user=another_user,
            access=PermissionAction.SHARE,
            granted_by=regular_user,
        )
        api_client.force_authenticate(user=another_user)

        resp = api_client.post(
            reverse("file-share", args=[file_obj.id]),
            {"user_email": target_user.email, "access": FilePermission.Access.DOWNLOAD},
            format="json",
        )

        assert resp.status_code == 403
        assert not FilePermission.objects.filter(file=file_obj, user=target_user).exists()
