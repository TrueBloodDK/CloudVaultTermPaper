"""URL-маршруты для файлового хранилища."""

from django.urls import path
from .views import (
    FileUploadView,
    FileListView,
    FileDetailView,
    FileDownloadView,
    FileDeleteView,
    FileShareView,
)

urlpatterns = [
    path("", FileListView.as_view(), name="file-list"),
    path("upload/", FileUploadView.as_view(), name="file-upload"),
    path("<uuid:pk>/", FileDetailView.as_view(), name="file-detail"),
    path("<uuid:pk>/download/", FileDownloadView.as_view(), name="file-download"),
    path("<uuid:pk>/delete/", FileDeleteView.as_view(), name="file-delete"),
    path("<uuid:pk>/share/", FileShareView.as_view(), name="file-share"),
]
