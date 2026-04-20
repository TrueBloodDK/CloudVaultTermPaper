"""Утилиты для создания записей в журнале аудита."""

import logging
from .models import AuditLog

logger = logging.getLogger("audit")


def get_client_ip(request):
    """Извлекаем реальный IP клиента (учитываем прокси)."""
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        return x_forwarded_for.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


def log_action(request, action, obj=None, extra=None):
    """
    Создаём запись в журнале аудита.

    Args:
        request: HTTP-запрос
        action:  AuditLog.Action (строка)
        obj:     объект Django-модели (необязательно)
        extra:   словарь с доп. данными
    """
    user = request.user if request.user.is_authenticated else None
    ip = get_client_ip(request)
    user_agent = request.META.get("HTTP_USER_AGENT", "")[:500]

    object_type = ""
    object_id = ""
    object_repr = ""

    if obj is not None:
        object_type = obj.__class__.__name__
        object_id = str(getattr(obj, "pk", ""))
        object_repr = str(obj)[:255]

    AuditLog.objects.create(
        user=user,
        action=action,
        object_type=object_type,
        object_id=object_id,
        object_repr=object_repr,
        ip_address=ip,
        user_agent=user_agent,
        extra=extra or {},
    )

    logger.info(
        "AUDIT | user=%s | action=%s | obj=%s:%s | ip=%s",
        user, action, object_type, object_id, ip,
    )
