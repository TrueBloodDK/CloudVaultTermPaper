"""Корневые URL-маршруты проекта."""

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.shortcuts import redirect

urlpatterns = [
    path("admin/", admin.site.urls),

    # Веб-интерфейс
    path("auth/",    include("users.web_urls")),
    path("files/",   include("files.web_urls")),
    path("audit/",   include("audit.web_urls")),
    path("manage/",  include("manage.urls")),

    # API v1
    path("api/v1/auth/",  include("users.urls")),
    path("api/v1/files/", include("files.urls")),
    path("api/v1/audit/", include("audit.urls")),

    path("", lambda req: redirect("files:list")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
