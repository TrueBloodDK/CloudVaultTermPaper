"""
Шифрование файлов с помощью AES-256 (через библиотеку cryptography).

Схема работы:
  1. При загрузке — файл шифруется и сохраняется на диск
  2. При скачивании — читается с диска и расшифровывается в памяти
  3. Ключ шифрования берётся из SECRET_KEY Django (в prod — отдельный ключ)

Используем Fernet — симметричное шифрование на базе AES-128-CBC + HMAC-SHA256.
Для курсовой этого достаточно; в проде можно перейти на AES-256-GCM явно.
"""

import base64
import hashlib
import os
from cryptography.fernet import Fernet
from django.conf import settings


def _get_fernet_key() -> bytes:
    """
    Генерируем 32-байтовый ключ Fernet из SECRET_KEY Django.
    В реальном проекте ключ должен храниться в переменной окружения отдельно.
    """
    raw = settings.SECRET_KEY.encode()
    digest = hashlib.sha256(raw).digest()  # всегда 32 байта
    return base64.urlsafe_b64encode(digest)


def get_fernet() -> Fernet:
    """Возвращает объект Fernet с ключом проекта."""
    return Fernet(_get_fernet_key())


def encrypt_file(file_data: bytes) -> bytes:
    """
    Шифруем содержимое файла.

    Args:
        file_data: исходные байты файла

    Returns:
        зашифрованные байты
    """
    f = get_fernet()
    return f.encrypt(file_data)


def decrypt_file(encrypted_data: bytes) -> bytes:
    """
    Расшифровываем содержимое файла.

    Args:
        encrypted_data: зашифрованные байты

    Returns:
        исходные байты файла

    Raises:
        cryptography.fernet.InvalidToken: если данные повреждены или ключ неверный
    """
    f = get_fernet()
    return f.decrypt(encrypted_data)


def compute_checksum(file_data: bytes) -> str:
    """
    Вычисляем SHA-256 контрольную сумму файла (до шифрования).
    Используется для проверки целостности при скачивании.
    """
    return hashlib.sha256(file_data).hexdigest()
