from rest_framework import serializers
from .models import AuditLog


class AuditLogSerializer(serializers.ModelSerializer):
    user_email = serializers.EmailField(source="user.email", read_only=True, default="Аноним")
    action_display = serializers.CharField(source="get_action_display", read_only=True)

    class Meta:
        model = AuditLog
        fields = [
            "id", "user_email", "action", "action_display",
            "object_type", "object_id", "object_repr",
            "ip_address", "extra", "timestamp",
        ]
