from django.urls import path

from . import views

app_name = "payments"

urlpatterns = [
    path("", views.payment_list, name="payment_list"),
    path("new/", views.payment_create, name="payment_create"),
    path("overdue/", views.overdue_list, name="overdue_list"),
    path("<int:pk>/", views.payment_detail, name="payment_detail"),
    path("<int:pk>/resolve/<slug:outcome>/", views.payment_resolve, name="payment_resolve"),
    path("cron/dunning/", views.dunning_cron, name="dunning_cron"),
]
