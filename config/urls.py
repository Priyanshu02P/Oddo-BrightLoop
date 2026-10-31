"""URL configuration for the Brightloop project."""

from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("apps.accounts.urls")),
    path("app/catalog/", include("apps.catalog.urls")),
    path("app/plans/", include("apps.plans.urls")),
    path("app/subscriptions/", include("apps.subscriptions.urls")),
    path("portal/subscriptions/", include("apps.subscriptions.portal_urls")),
    path("app/billing/", include("apps.billing.urls")),
    path("portal/invoices/", include("apps.billing.portal_urls")),
    path("app/discounts/", include("apps.discounts.urls")),
]
