from django.contrib import admin
from .models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ["timestamp", "user", "action", "object_type", "object_repr", "ip_address"]
    list_filter = ["action", "object_type"]
    search_fields = ["user__email", "ip_address", "object_repr"]
    readonly_fields = ["id", "user", "action", "object_type", "object_id",
                       "object_repr", "ip_address", "user_agent", "extra", "timestamp"]
    ordering = ["-timestamp"]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
