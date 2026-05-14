"""API для просмотра журнала аудита (только администратор безопасности)."""

from rest_framework import generics, filters
from rest_framework.permissions import IsAuthenticated
from .models import AuditLog
from .serializers import AuditLogSerializer
from users.permissions import IsSecurityAdmin


class AuditLogListView(generics.ListAPIView):
    """GET /api/v1/audit/ — список записей журнала."""

    permission_classes = [IsAuthenticated, IsSecurityAdmin]
    serializer_class = AuditLogSerializer
    queryset = AuditLog.objects.select_related("user").all()
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["user__email", "action", "ip_address", "object_repr"]
    ordering_fields = ["timestamp"]
    ordering = ["-timestamp"]
