from django.urls import path

from . import views

app_name = "billing"

urlpatterns = [
    path("invoices/", views.invoice_list, name="invoice_list"),
    path("invoices/<int:pk>/", views.invoice_detail, name="invoice_detail"),
    path("invoices/<int:pk>/print/", views.invoice_print, name="invoice_print"),
    path("invoices/<int:pk>/actions/<slug:action>/", views.invoice_action, name="invoice_action"),
    path("runs/", views.run_list, name="run_list"),
    path("runs/start/", views.run_start, name="run_start"),
    path("runs/<int:pk>/", views.run_detail, name="run_detail"),
    path("runs/<int:pk>/continue/", views.run_continue, name="run_continue"),
    path("cron/run/", views.billing_cron, name="billing_cron"),
]
