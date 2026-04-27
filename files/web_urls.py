from django.urls import path
from .web_views import (
    FileListView, FileUploadView, FileDownloadView,
    FileDeleteView, FileShareView,
    FolderCreateView, FolderDeleteView, FolderRenameView,
)

app_name = "files"

urlpatterns = [
    # Файлы
    path("",                    FileListView.as_view(),     name="list"),
    path("upload/",             FileUploadView.as_view(),   name="upload"),
    path("<uuid:pk>/download/", FileDownloadView.as_view(), name="download"),
    path("<uuid:pk>/delete/",   FileDeleteView.as_view(),   name="delete"),
    path("<uuid:pk>/share/",    FileShareView.as_view(),    name="share"),

    # Папки
    path("folders/create/",              FolderCreateView.as_view(), name="folder-create"),
    path("folders/<uuid:pk>/delete/",    FolderDeleteView.as_view(), name="folder-delete"),
    path("folders/<uuid:pk>/rename/",    FolderRenameView.as_view(), name="folder-rename"),
]
