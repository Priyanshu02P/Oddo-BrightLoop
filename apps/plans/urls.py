from django.urls import path

from . import views

app_name = "plans"

urlpatterns = [
    path("", views.plan_list, name="plan_list"),
    path("new/", views.plan_create, name="plan_create"),
    path("<int:pk>/", views.plan_detail, name="plan_detail"),
    path("<int:pk>/edit/", views.plan_edit, name="plan_edit"),
    path("cron/auto-close/", views.auto_close_cron, name="auto_close_cron"),
]
