"""Middleware для автоматической записи отказов в доступе."""

from .models import AuditLog
from .utils import log_action, get_client_ip


class AuditMiddleware:
    """
    Перехватывает HTTP 403 (Forbidden) и 401 (Unauthorized)
    и автоматически пишет их в журнал аудита.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        if response.status_code == 403:
            log_action(
                request,
                AuditLog.Action.ACCESS_DENIED,
                extra={"path": request.path, "method": request.method},
            )

        return response
