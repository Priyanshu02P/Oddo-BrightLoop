from decimal import Decimal

import pytest

from apps.catalog.tests.factories import ProductFactory, ProductVariantFactory, TaxFactory
from apps.subscriptions import pricing
from apps.subscriptions.exceptions import InvalidLine

pytestmark = pytest.mark.django_db


def test_price_comes_from_product_variant_and_product_tax():
    product = ProductFactory(sales_price=Decimal("2000.00"), tax=TaxFactory(rate=Decimal("15.00")))
    variant = ProductVariantFactory(product=product, price_adjustment=Decimal("560.00"))
    values = pricing.price_line(product=product, variant=variant, quantity=3)
    assert values == {
        "unit_price": Decimal("2560.00"),
        "tax_rate": Decimal("15.00"),
        "amount": Decimal("7680.00"),
        "tax_amount": Decimal("1152.00"),
    }


def test_tax_is_rounded_half_up_to_two_decimals():
    product = ProductFactory(sales_price=Decimal("10.05"), tax=TaxFactory(rate=Decimal("10.00")))
    assert pricing.price_line(product=product, variant=None, quantity=1)["tax_amount"] == Decimal(
        "1.01"
    )


@pytest.mark.parametrize("quantity", [0, -1, None])
def test_quantity_must_be_positive(quantity):
    with pytest.raises(InvalidLine):
        pricing.price_line(product=ProductFactory(), variant=None, quantity=quantity)


def test_archived_product_is_rejected():
    with pytest.raises(InvalidLine):
        pricing.price_line(product=ProductFactory(is_archived=True), variant=None, quantity=1)


def test_variant_of_another_product_is_rejected():
    with pytest.raises(InvalidLine):
        pricing.price_line(product=ProductFactory(), variant=ProductVariantFactory(), quantity=1)
