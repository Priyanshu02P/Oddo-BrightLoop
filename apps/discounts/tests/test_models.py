from datetime import date
from decimal import Decimal

import pytest
from django.db import IntegrityError, transaction

from apps.accounts.tests.factories import CustomerFactory
from apps.billing.tests.factories import InvoiceFactory
from apps.catalog.tests.factories import ProductFactory
from apps.discounts.models import (
    Discount,
    DiscountProduct,
    DiscountRedemption,
    InvoiceDiscountSnapshot,
)
from apps.discounts.tests.factories import DiscountFactory, PercentageDiscountFactory


@pytest.mark.django_db
class TestDiscountModel:
    def test_create_valid_fixed_discount(self):
        discount = DiscountFactory(
            name="Summer Sale",
            discount_type=Discount.DiscountType.FIXED_AMOUNT,
            value=Decimal("100.00"),
            usage_limit_per_customer=5,
        )
        assert discount.pk is not None
        assert str(discount) == "Summer Sale"
        assert discount.status_label(as_of=date(2026, 6, 1)) == "active"

    def test_create_valid_percentage_discount(self):
        discount = PercentageDiscountFactory(
            name="10% Off",
            value=Decimal("10.00"),
        )
        assert discount.pk is not None
        assert discount.discount_type == Discount.DiscountType.PERCENTAGE
        assert discount.value == Decimal("10.00")

    def test_status_label_upcoming_and_expired(self):
        discount = DiscountFactory(
            start_date=date(2026, 6, 1),
            end_date=date(2026, 6, 30),
            is_active=True,
        )
        assert discount.status_label(as_of=date(2026, 5, 1)) == "upcoming"
        assert discount.status_label(as_of=date(2026, 6, 15)) == "active"
        assert discount.status_label(as_of=date(2026, 7, 1)) == "expired"

    def test_status_label_inactive(self):
        discount = DiscountFactory(is_active=False)
        assert discount.status_label(as_of=date(2026, 6, 1)) == "inactive"

    def test_reject_zero_value(self):
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                DiscountFactory(value=Decimal("0.00"))

    def test_reject_negative_value(self):
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                DiscountFactory(value=Decimal("-10.00"))

    def test_reject_zero_usage_limit(self):
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                DiscountFactory(usage_limit_per_customer=0)

    def test_reject_end_date_before_start_date(self):
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                DiscountFactory(start_date=date(2026, 6, 10), end_date=date(2026, 6, 1))

    def test_unique_discount_product(self):
        discount = DiscountFactory(scope_type=Discount.ScopeType.SELECTED_PRODUCTS)
        product = ProductFactory()
        DiscountProduct.objects.create(discount=discount, product=product)
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                DiscountProduct.objects.create(discount=discount, product=product)

    def test_unique_discount_redemption(self):
        discount = DiscountFactory()
        customer = CustomerFactory()
        DiscountRedemption.objects.create(discount=discount, customer=customer, usage_count=1)
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                DiscountRedemption.objects.create(
                    discount=discount, customer=customer, usage_count=1
                )

    def test_unique_invoice_discount_snapshot(self):
        invoice = InvoiceFactory()
        discount = DiscountFactory()
        InvoiceDiscountSnapshot.objects.create(
            invoice=invoice,
            discount=discount,
            discount_name=discount.name,
            discount_type=discount.discount_type,
            discount_value=discount.value,
            scope_type=discount.scope_type,
            application_order=1,
            amount_applied=Decimal("50.00"),
        )
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                InvoiceDiscountSnapshot.objects.create(
                    invoice=invoice,
                    discount=discount,
                    discount_name=discount.name,
                    discount_type=discount.discount_type,
                    discount_value=discount.value,
                    scope_type=discount.scope_type,
                    application_order=2,
                    amount_applied=Decimal("50.00"),
                )
