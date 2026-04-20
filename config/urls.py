"""Корневые URL-маршруты проекта."""

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path("admin/", admin.site.urls),

    # API v1
    path("api/v1/auth/", include("users.urls")),
    path("api/v1/files/", include("files.urls")),
    path("api/v1/audit/", include("audit.urls")),
]

# В режиме разработки — раздаём медиафайлы через Django
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
