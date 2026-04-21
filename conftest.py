"""Общие фикстуры для всех тестов."""

import pytest
from django.core.files.base import ContentFile
from files.encryption import encrypt_file, compute_checksum
from files.models import File


@pytest.fixture
def admin_user(db, django_user_model):
    return django_user_model.objects.create_user(
        email="admin@test.ru",
        full_name="Администратор Системы",
        password="adminpass123",
        role="admin",
        is_staff=True,
    )


@pytest.fixture
def regular_user(db, django_user_model):
    return django_user_model.objects.create_user(
        email="user@test.ru",
        full_name="Обычный Пользователь",
        password="userpass123",
        role="user",
    )


@pytest.fixture
def another_user(db, django_user_model):
    return django_user_model.objects.create_user(
        email="another@test.ru",
        full_name="Другой Пользователь",
        password="anotherpass123",
        role="user",
    )


@pytest.fixture
def sample_file(db, regular_user):
    """Готовый зашифрованный файл в БД."""
    raw = b"Hello, SecureVault! This is test file content."
    encrypted = encrypt_file(raw)
    checksum = compute_checksum(raw)

    file_obj = File.objects.create(
        owner=regular_user,
        original_name="test_document.txt",
        encrypted_file=ContentFile(encrypted, name="test_document.txt"),
        mime_type="text/plain",
        size=len(raw),
        checksum=checksum,
        description="Тестовый файл",
    )
    return file_obj


@pytest.fixture
def auth_client(client, regular_user):
    """Клиент с авторизованным обычным пользователем."""
    client.force_login(regular_user)
    return client


@pytest.fixture
def admin_client(client, admin_user):
    """Клиент с авторизованным администратором."""
    client.force_login(admin_user)
    return client
