from django.urls import path

from . import portal_views

app_name = "portal_invoices"

urlpatterns = [
    path("", portal_views.invoice_list, name="invoice_list"),
    path("<int:pk>/", portal_views.invoice_detail, name="invoice_detail"),
    path("<int:pk>/print/", portal_views.invoice_print, name="invoice_print"),
]
