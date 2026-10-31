"""URL configuration for M6 Discounts."""

from django.urls import path

from . import views

app_name = "discounts"

urlpatterns = [
    path("", views.discount_list, name="discount_list"),
    path("create/", views.discount_create, name="discount_create"),
    path("<int:pk>/", views.discount_detail, name="discount_detail"),
    path("<int:pk>/edit/", views.discount_edit, name="discount_edit"),
    path("preview/", views.discount_preview, name="discount_preview"),
]
