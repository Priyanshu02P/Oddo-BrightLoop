"""URL configuration for the Brightloop project."""

from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("apps.accounts.urls")),
    path("app/catalog/", include("apps.catalog.urls")),
    path("app/plans/", include("apps.plans.urls")),
]
