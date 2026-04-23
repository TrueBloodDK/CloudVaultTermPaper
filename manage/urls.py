"""URL-маршруты панели управления."""

from django.urls import path
from .views import (
    UserListView, UserUpdateView,
    DepartmentListView, DepartmentCreateView, DepartmentUpdateView, DepartmentDeleteView,
    CategoryListView, CategoryCreateView, CategoryUpdateView, CategoryDeleteView,
)

app_name = "manage"

urlpatterns = [
    # Пользователи
    path("users/",           UserListView.as_view(),   name="users"),
    path("users/<uuid:pk>/", UserUpdateView.as_view(), name="user-update"),

    # Отделы
    path("departments/",                    DepartmentListView.as_view(),   name="departments"),
    path("departments/create/",             DepartmentCreateView.as_view(), name="dept-create"),
    path("departments/<int:pk>/",           DepartmentUpdateView.as_view(), name="dept-update"),
    path("departments/<int:pk>/delete/",    DepartmentDeleteView.as_view(), name="dept-delete"),

    # Категории файлов
    path("categories/",                  CategoryListView.as_view(),   name="categories"),
    path("categories/create/",           CategoryCreateView.as_view(), name="cat-create"),
    path("categories/<int:pk>/",         CategoryUpdateView.as_view(), name="cat-update"),
    path("categories/<int:pk>/delete/",  CategoryDeleteView.as_view(), name="cat-delete"),
]
