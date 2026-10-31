from decimal import Decimal

import pytest
from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError

from apps.catalog.models import Product

from .factories import ProductFactory, ProductVariantFactory

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize(
    "overrides",
    [
        {"name": ""},
        {"type": "subscription"},
        {"sales_price": Decimal("-0.01")},
        {"cost_price": Decimal("-0.01")},
    ],
)
def test_database_rejects_invalid_product(tax, overrides):
    with pytest.raises(IntegrityError), transaction.atomic():
        ProductFactory(tax=tax, **overrides)


@pytest.mark.parametrize(
    "overrides", [{"dimension": ""}, {"value": ""}, {"price_adjustment": Decimal("-1.00")}]
)
def test_database_rejects_invalid_variant(tax, overrides):
    product = ProductFactory(tax=tax)
    with pytest.raises(IntegrityError), transaction.atomic():
        ProductVariantFactory(product=product, **overrides)


def test_tax_in_use_cannot_be_deleted(tax):
    ProductFactory(tax=tax)
    with pytest.raises(ProtectedError):
        tax.delete()


def test_money_values_are_decimals(tax):
    variant = ProductVariantFactory(product=ProductFactory(tax=tax), price_adjustment="560")
    variant.refresh_from_db()
    product = Product.objects.get(pk=variant.product_id)
    assert isinstance(product.sales_price, Decimal)
    assert isinstance(variant.price_adjustment, Decimal)
    assert variant.adjusted_sales_price == Decimal("2560.00")
