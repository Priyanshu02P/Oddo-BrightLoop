from django.urls import path

from . import portal_views

app_name = "portal_subscriptions"

urlpatterns = [
    path("", portal_views.subscription_list, name="subscription_list"),
    path("<int:pk>/", portal_views.subscription_detail, name="subscription_detail"),
    path(
        "<int:pk>/actions/<slug:action>/",
        portal_views.subscription_action,
        name="subscription_action",
    ),
]
