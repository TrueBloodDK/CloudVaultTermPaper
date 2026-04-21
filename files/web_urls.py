from django.urls import path
from .web_views import (
    FileListView, FileUploadView, FileDownloadView,
    FileDeleteView, FileShareView,
)

app_name = "files"

urlpatterns = [
    path("",                    FileListView.as_view(),     name="list"),
    path("upload/",             FileUploadView.as_view(),   name="upload"),
    path("<uuid:pk>/download/", FileDownloadView.as_view(), name="download"),
    path("<uuid:pk>/delete/",   FileDeleteView.as_view(),   name="delete"),
    path("<uuid:pk>/share/",    FileShareView.as_view(),    name="share"),
]
