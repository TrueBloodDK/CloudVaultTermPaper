"""Настройки для запуска тестов — используют SQLite вместо PostgreSQL."""

from .settings import *  # noqa

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

# Убираем логирование во время тестов
LOGGING = {}
