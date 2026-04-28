from django.urls import path
from .views import (
    UserListView, UserUpdateView,
    MembershipCreateView, MembershipDeleteView,
    DepartmentListView, DepartmentCreateView, DepartmentUpdateView, DepartmentDeleteView,
    FolderListView,
)

app_name = "manage"

urlpatterns = [
    path("users/",                        UserListView.as_view(),         name="users"),
    path("users/<uuid:pk>/",              UserUpdateView.as_view(),       name="user-update"),
    path("users/<uuid:pk>/membership/",   MembershipCreateView.as_view(), name="membership-create"),
    path("membership/<int:pk>/delete/",   MembershipDeleteView.as_view(), name="membership-delete"),

    path("departments/",                 DepartmentListView.as_view(),   name="departments"),
    path("departments/create/",          DepartmentCreateView.as_view(), name="dept-create"),
    path("departments/<int:pk>/",        DepartmentUpdateView.as_view(), name="dept-update"),
    path("departments/<int:pk>/delete/", DepartmentDeleteView.as_view(), name="dept-delete"),

    path("folders/",                     FolderListView.as_view(),       name="folders"),
]
