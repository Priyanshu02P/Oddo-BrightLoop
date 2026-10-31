from django.db.models import Count

from .models import Product, Tax

STATUS_ACTIVE = "active"
STATUS_ARCHIVED = "archived"


def list_products(status=None):
    """Catalog list: tax joined and variants counted in the same query."""
    products = Product.objects.select_related("tax").annotate(variant_count=Count("variants"))
    if status == STATUS_ACTIVE:
        products = products.filter(is_archived=False)
    elif status == STATUS_ARCHIVED:
        products = products.filter(is_archived=True)
    return products.order_by("is_archived", "name", "id")


def product_detail_queryset():
    return Product.objects.select_related("tax").prefetch_related("variants")


def list_products_for_new_subscription_lines():
    """Active products offered to the subscription-line workflow (FR-2.4); archived excluded."""
    return Product.objects.available_for_new_lines().select_related("tax").order_by("name", "id")


def tax_exists():
    return Tax.objects.exists()
