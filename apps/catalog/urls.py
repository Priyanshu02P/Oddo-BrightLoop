from django.urls import path

from . import views

app_name = "catalog"

urlpatterns = [
    path("products/", views.product_list, name="product_list"),
    path("products/new/", views.product_create, name="product_create"),
    path("products/<int:pk>/", views.product_detail, name="product_detail"),
    path("products/<int:pk>/edit/", views.product_edit, name="product_edit"),
    path("products/<int:pk>/archive/", views.product_archive, name="product_archive"),
    path("taxes/", views.tax_list, name="tax_list"),
    path("taxes/new/", views.tax_create, name="tax_create"),
    path("taxes/<int:pk>/edit/", views.tax_edit, name="tax_edit"),
    path("payment-terms/", views.payment_term_list, name="payment_term_list"),
    path("payment-terms/new/", views.payment_term_create, name="payment_term_create"),
    path("payment-terms/<int:pk>/edit/", views.payment_term_edit, name="payment_term_edit"),
]
