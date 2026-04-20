from django.contrib import admin
from .models import File, FilePermission


@admin.register(File)
class FileAdmin(admin.ModelAdmin):
    list_display = ["original_name", "owner", "mime_type", "size_kb", "status", "created_at"]
    list_filter = ["status", "mime_type"]
    search_fields = ["original_name", "owner__email"]
    readonly_fields = ["id", "checksum", "created_at", "updated_at"]
    ordering = ["-created_at"]


@admin.register(FilePermission)
class FilePermissionAdmin(admin.ModelAdmin):
    list_display = ["file", "user", "access", "granted_by", "granted_at"]
    list_filter = ["access"]
    search_fields = ["file__original_name", "user__email"]
