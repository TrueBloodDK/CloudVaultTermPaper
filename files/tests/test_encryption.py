"""Тесты модуля шифрования файлов."""

import pytest
from cryptography.fernet import InvalidToken

from files.encryption import encrypt_file, decrypt_file, compute_checksum, get_fernet


class TestEncryption:
    """Тесты шифрования и расшифровки."""

    def test_encrypt_returns_bytes(self):
        result = encrypt_file(b"test data")
        assert isinstance(result, bytes)

    def test_encrypted_differs_from_original(self):
        data = b"sensitive content"
        encrypted = encrypt_file(data)
        assert encrypted != data

    def test_decrypt_restores_original(self):
        data = b"Hello, SecureVault!"
        encrypted = encrypt_file(data)
        decrypted = decrypt_file(encrypted)
        assert decrypted == data

    def test_encrypt_decrypt_large_file(self):
        """Шифрование файла ~1 МБ."""
        data = b"X" * (1024 * 1024)
        encrypted = encrypt_file(data)
        decrypted = decrypt_file(encrypted)
        assert decrypted == data

    def test_encrypted_data_is_unique(self):
        """Два вызова encrypt дают разный результат (Fernet использует случайный IV)."""
        data = b"same content"
        enc1 = encrypt_file(data)
        enc2 = encrypt_file(data)
        assert enc1 != enc2

    def test_decrypt_wrong_data_raises(self):
        """Повреждённые данные — InvalidToken."""
        with pytest.raises(InvalidToken):
            decrypt_file(b"this is not valid fernet token")

    def test_decrypt_tampered_data_raises(self):
        """Изменение зашифрованных данных приводит к ошибке."""
        encrypted = encrypt_file(b"important data")
        tampered = bytearray(encrypted)
        tampered[20] ^= 0xFF  # инвертируем байт
        with pytest.raises(InvalidToken):
            decrypt_file(bytes(tampered))

    def test_empty_file(self):
        """Шифрование пустого файла."""
        data = b""
        encrypted = encrypt_file(data)
        decrypted = decrypt_file(encrypted)
        assert decrypted == data


class TestChecksum:
    """Тесты контрольной суммы SHA-256."""

    def test_checksum_is_hex_string(self):
        result = compute_checksum(b"test")
        assert isinstance(result, str)
        assert len(result) == 64
        assert all(c in "0123456789abcdef" for c in result)

    def test_same_data_same_checksum(self):
        data = b"consistent data"
        assert compute_checksum(data) == compute_checksum(data)

    def test_different_data_different_checksum(self):
        assert compute_checksum(b"data A") != compute_checksum(b"data B")

    def test_known_checksum(self):
        """SHA-256 от пустой строки — известное значение."""
        expected = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
        assert compute_checksum(b"") == expected
