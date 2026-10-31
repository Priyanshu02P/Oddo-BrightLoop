from django.urls import path

from . import views

app_name = "subscriptions"

urlpatterns = [
    path("", views.subscription_list, name="subscription_list"),
    path("new/", views.subscription_create, name="subscription_create"),
    path("<int:pk>/", views.subscription_detail, name="subscription_detail"),
    path("<int:pk>/actions/<slug:action>/", views.subscription_action, name="subscription_action"),
    path("<int:pk>/lines/new/", views.line_form, name="line_add"),
    path("<int:pk>/lines/<int:line_pk>/edit/", views.line_form, name="line_edit"),
    path("<int:pk>/lines/<int:line_pk>/remove/", views.line_remove, name="line_remove"),
    path("templates/", views.template_list, name="template_list"),
    path("templates/new/", views.template_create, name="template_create"),
    path("templates/<int:pk>/edit/", views.template_edit, name="template_edit"),
    path("cron/daily/", views.daily_cron, name="daily_cron"),
]
