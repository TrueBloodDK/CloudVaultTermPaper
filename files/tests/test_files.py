"""Тесты загрузки, скачивания, удаления и доступа к файлам."""

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from files.models import File, FilePermission
from files.encryption import decrypt_file, compute_checksum


@pytest.mark.django_db
class TestFileUpload:
    """Тесты загрузки файлов."""

    def _make_file(self, content=b"test content", name="doc.txt", mime="text/plain"):
        return SimpleUploadedFile(name, content, content_type=mime)

    def test_upload_requires_login(self, client):
        url = reverse("files:upload")
        resp = client.post(url, {"file": self._make_file()})
        assert resp.status_code == 302
        assert "/auth/login/" in resp["Location"]

    def test_upload_success(self, auth_client, regular_user):
        url = reverse("files:upload")
        uploaded = self._make_file(b"important document", "report.txt")
        resp = auth_client.post(url, {"file": uploaded, "description": "Отчёт"})

        assert resp.status_code == 302
        assert File.objects.filter(owner=regular_user, original_name="report.txt").exists()

    def test_upload_encrypts_file(self, auth_client, regular_user):
        """Содержимое на диске не совпадает с оригиналом."""
        raw_content = b"TOP SECRET DOCUMENT CONTENT"
        url = reverse("files:upload")
        uploaded = self._make_file(raw_content, "secret.txt")
        auth_client.post(url, {"file": uploaded})

        file_obj = File.objects.get(owner=regular_user, original_name="secret.txt")
        stored = file_obj.encrypted_file.read()
        assert stored != raw_content  # на диске — зашифрованные данные

    def test_upload_stores_correct_checksum(self, auth_client, regular_user):
        raw_content = b"checksum test data"
        url = reverse("files:upload")
        uploaded = self._make_file(raw_content, "checksum_test.txt")
        auth_client.post(url, {"file": uploaded})

        file_obj = File.objects.get(owner=regular_user)
        assert file_obj.checksum == compute_checksum(raw_content)

    def test_upload_forbidden_mime_type(self, auth_client):
        """Исполняемые файлы — запрещены."""
        exe_file = SimpleUploadedFile(
            "virus.exe", b"MZ\x90\x00", content_type="application/x-msdownload"
        )
        url = reverse("files:upload")
        resp = auth_client.post(url, {"file": exe_file})
        assert resp.status_code == 302
        assert not File.objects.filter(original_name="virus.exe").exists()

    def test_upload_creates_audit_record(self, auth_client, regular_user):
        from audit.models import AuditLog
        url = reverse("files:upload")
        uploaded = self._make_file(b"audited content", "audit_test.txt")
        auth_client.post(url, {"file": uploaded})

        assert AuditLog.objects.filter(
            user=regular_user,
            action=AuditLog.Action.FILE_UPLOAD,
        ).exists()


@pytest.mark.django_db
class TestFileDownload:
    """Тесты скачивания файлов."""

    def test_download_requires_login(self, client, sample_file):
        url = reverse("files:download", args=[sample_file.id])
        resp = client.get(url)
        assert resp.status_code == 302

    def test_owner_can_download(self, auth_client, sample_file):
        url = reverse("files:download", args=[sample_file.id])
        resp = auth_client.get(url)
        assert resp.status_code == 200

    def test_download_decrypts_correctly(self, auth_client, sample_file):
        """Скачанный файл совпадает с оригиналом."""
        url = reverse("files:download", args=[sample_file.id])
        resp = auth_client.get(url)

        content = b"".join(resp.streaming_content)
        assert content == b"Hello, SecureVault! This is test file content."

    def test_download_has_checksum_header(self, auth_client, sample_file):
        url = reverse("files:download", args=[sample_file.id])
        resp = auth_client.get(url)
        assert "X-Checksum-SHA256" in resp
        assert resp["X-Checksum-SHA256"] == sample_file.checksum

    def test_other_user_cannot_download(self, client, another_user, sample_file):
        """Чужой пользователь без прав — получает редирект."""
        client.force_login(another_user)
        url = reverse("files:download", args=[sample_file.id])
        resp = client.get(url)
        assert resp.status_code == 302

    def test_admin_can_download_any_file(self, admin_client, sample_file):
        url = reverse("files:download", args=[sample_file.id])
        resp = admin_client.get(url)
        assert resp.status_code == 200

    def test_download_with_permission(self, client, another_user, sample_file):
        """Пользователь с явным разрешением может скачать."""
        FilePermission.objects.create(
            file=sample_file,
            user=another_user,
            access=FilePermission.Access.DOWNLOAD,
            granted_by=sample_file.owner,
        )
        client.force_login(another_user)
        url = reverse("files:download", args=[sample_file.id])
        resp = client.get(url)
        assert resp.status_code == 200

    def test_download_creates_audit_record(self, auth_client, regular_user, sample_file):
        from audit.models import AuditLog
        url = reverse("files:download", args=[sample_file.id])
        auth_client.get(url)

        assert AuditLog.objects.filter(
            user=regular_user,
            action=AuditLog.Action.FILE_DOWNLOAD,
            object_id=str(sample_file.id),
        ).exists()


@pytest.mark.django_db
class TestFileDelete:
    """Тесты удаления файлов (мягкое удаление)."""

    def test_owner_can_delete(self, auth_client, sample_file):
        url = reverse("files:delete", args=[sample_file.id])
        resp = auth_client.post(url)
        assert resp.status_code == 302

        sample_file.refresh_from_db()
        assert sample_file.status == File.Status.DELETED

    def test_other_user_cannot_delete(self, client, another_user, sample_file):
        client.force_login(another_user)
        url = reverse("files:delete", args=[sample_file.id])
        client.post(url)

        sample_file.refresh_from_db()
        assert sample_file.status == File.Status.ACTIVE

    def test_deleted_file_not_in_list(self, auth_client, sample_file):
        sample_file.status = File.Status.DELETED
        sample_file.save()

        resp = auth_client.get(reverse("files:list"))
        assert sample_file.original_name not in resp.content.decode()

    def test_delete_creates_audit_record(self, auth_client, regular_user, sample_file):
        from audit.models import AuditLog
        url = reverse("files:delete", args=[sample_file.id])
        auth_client.post(url)

        assert AuditLog.objects.filter(
            user=regular_user,
            action=AuditLog.Action.FILE_DELETE,
        ).exists()

    def test_admin_can_delete_any_file(self, admin_client, sample_file):
        url = reverse("files:delete", args=[sample_file.id])
        resp = admin_client.post(url)
        assert resp.status_code == 302

        sample_file.refresh_from_db()
        assert sample_file.status == File.Status.DELETED


@pytest.mark.django_db
class TestFileShare:
    """Тесты управления доступом к файлам."""

    def test_owner_can_share(self, auth_client, sample_file, another_user):
        url = reverse("files:share", args=[sample_file.id])
        resp = auth_client.post(url, {
            "user_email": another_user.email,
            "access": FilePermission.Access.DOWNLOAD,
        })
        assert resp.status_code == 302
        assert FilePermission.objects.filter(
            file=sample_file, user=another_user
        ).exists()

    def test_share_nonexistent_user(self, auth_client, sample_file):
        url = reverse("files:share", args=[sample_file.id])
        resp = auth_client.post(url, {
            "user_email": "ghost@test.ru",
            "access": "read",
        })
        assert resp.status_code == 302
        assert not FilePermission.objects.filter(file=sample_file).exists()

    def test_cannot_share_with_yourself(self, auth_client, regular_user, sample_file):
        url = reverse("files:share", args=[sample_file.id])
        auth_client.post(url, {
            "user_email": regular_user.email,
            "access": "read",
        })
        assert not FilePermission.objects.filter(
            file=sample_file, user=regular_user
        ).exists()

    def test_non_owner_cannot_share(self, client, another_user, sample_file):
        client.force_login(another_user)
        url = reverse("files:share", args=[sample_file.id])
        client.post(url, {"user_email": "x@test.ru", "access": "read"})
        assert not FilePermission.objects.filter(file=sample_file).exists()


@pytest.mark.django_db
class TestFileList:
    """Тесты страницы со списком файлов."""

    def test_list_requires_login(self, client):
        resp = client.get(reverse("files:list"))
        assert resp.status_code == 302

    def test_user_sees_own_files(self, auth_client, sample_file):
        resp = auth_client.get(reverse("files:list"))
        assert resp.status_code == 200
        assert "test_document.txt" in resp.content.decode()

    def test_user_does_not_see_others_files(self, client, another_user, sample_file):
        client.force_login(another_user)
        resp = client.get(reverse("files:list"))
        assert "test_document.txt" not in resp.content.decode()

    def test_admin_sees_all_files(self, admin_client, sample_file):
        resp = admin_client.get(reverse("files:list"))
        assert "test_document.txt" in resp.content.decode()
