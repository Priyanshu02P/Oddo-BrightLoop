from datetime import date
from decimal import Decimal

import pytest

from apps.accounts.tests.factories import CustomerFactory
from apps.billing.tests.factories import InvoiceLineFactory
from apps.catalog.tests.factories import ProductFactory
from apps.discounts import services
from apps.discounts.tests.factories import (
    DiscountFactory,
    DiscountRedemptionFactory,
    SelectedProductsDiscountFactory,
)
from apps.subscriptions.tests.factories import SubscriptionFactory


@pytest.mark.django_db
class TestDiscountEligibility:
    def test_eligible_on_boundary_dates(self):
        start = date(2026, 6, 1)
        end = date(2026, 6, 30)
        discount = DiscountFactory(start_date=start, end_date=end)
        customer = CustomerFactory()
        subscription = SubscriptionFactory(customer=customer)
        line = InvoiceLineFactory(amount=Decimal("100.00"), quantity=1)

        # On start date
        eligible = services.get_eligible_discounts(
            customer=customer, subscription=subscription, invoice_lines=[line], as_of=start
        )
        assert discount in eligible

        # On end date
        eligible = services.get_eligible_discounts(
            customer=customer, subscription=subscription, invoice_lines=[line], as_of=end
        )
        assert discount in eligible

    def test_ineligible_before_start_and_after_end(self):
        start = date(2026, 6, 1)
        end = date(2026, 6, 30)
        DiscountFactory(start_date=start, end_date=end)
        customer = CustomerFactory()
        subscription = SubscriptionFactory(customer=customer)
        line = InvoiceLineFactory(amount=Decimal("100.00"), quantity=1)

        assert not services.get_eligible_discounts(
            customer=customer,
            subscription=subscription,
            invoice_lines=[line],
            as_of=date(2026, 5, 31),
        )
        assert not services.get_eligible_discounts(
            customer=customer,
            subscription=subscription,
            invoice_lines=[line],
            as_of=date(2026, 7, 1),
        )

    def test_inactive_discount_ineligible(self):
        discount = DiscountFactory(is_active=False)
        customer = CustomerFactory()
        subscription = SubscriptionFactory(customer=customer)
        line = InvoiceLineFactory(amount=Decimal("100.00"), quantity=1)

        eligible = services.get_eligible_discounts(
            customer=customer,
            subscription=subscription,
            invoice_lines=[line],
            as_of=date(2026, 6, 15),
        )
        assert discount not in eligible

    def test_usage_limit_per_customer(self):
        discount = DiscountFactory(usage_limit_per_customer=2)
        customer_a = CustomerFactory()
        customer_b = CustomerFactory()
        subscription_a = SubscriptionFactory(customer=customer_a)
        subscription_b = SubscriptionFactory(customer=customer_b)
        line = InvoiceLineFactory(amount=Decimal("100.00"), quantity=1)
        today = date(2026, 6, 15)

        # Customer A has used it 2 times (reached limit)
        DiscountRedemptionFactory(discount=discount, customer=customer_a, usage_count=2)

        # Customer A should be ineligible
        assert not services.get_eligible_discounts(
            customer=customer_a, subscription=subscription_a, invoice_lines=[line], as_of=today
        )

        # Customer B has 0 redemptions, should be eligible
        eligible_b = services.get_eligible_discounts(
            customer=customer_b, subscription=subscription_b, invoice_lines=[line], as_of=today
        )
        assert discount in eligible_b

    def test_minimum_purchase_amount_condition(self):
        discount = DiscountFactory(minimum_purchase_amount=Decimal("500.00"))
        customer = CustomerFactory()
        subscription = SubscriptionFactory(customer=customer)
        today = date(2026, 6, 15)

        # Below threshold
        line_below = InvoiceLineFactory(amount=Decimal("499.99"), quantity=1)
        assert not services.get_eligible_discounts(
            customer=customer,
            subscription=subscription,
            invoice_lines=[line_below],
            as_of=today,
        )

        # At threshold
        line_at = InvoiceLineFactory(amount=Decimal("500.00"), quantity=1)
        assert discount in services.get_eligible_discounts(
            customer=customer, subscription=subscription, invoice_lines=[line_at], as_of=today
        )

        # Above threshold
        line_above = InvoiceLineFactory(amount=Decimal("600.00"), quantity=1)
        assert discount in services.get_eligible_discounts(
            customer=customer, subscription=subscription, invoice_lines=[line_above], as_of=today
        )

    def test_minimum_quantity_condition(self):
        discount = DiscountFactory(minimum_quantity=5)
        customer = CustomerFactory()
        subscription = SubscriptionFactory(customer=customer)
        today = date(2026, 6, 15)

        # Below threshold
        line_below = InvoiceLineFactory(amount=Decimal("1000.00"), quantity=4)
        assert not services.get_eligible_discounts(
            customer=customer,
            subscription=subscription,
            invoice_lines=[line_below],
            as_of=today,
        )

        # At threshold
        line_at = InvoiceLineFactory(amount=Decimal("1000.00"), quantity=5)
        assert discount in services.get_eligible_discounts(
            customer=customer, subscription=subscription, invoice_lines=[line_at], as_of=today
        )

    def test_both_minimum_conditions_and_logic(self):
        discount = DiscountFactory(
            minimum_purchase_amount=Decimal("500.00"),
            minimum_quantity=5,
        )
        customer = CustomerFactory()
        subscription = SubscriptionFactory(customer=customer)
        today = date(2026, 6, 15)

        # Meets amount, but fails quantity
        line1 = InvoiceLineFactory(amount=Decimal("600.00"), quantity=4)
        assert not services.get_eligible_discounts(
            customer=customer, subscription=subscription, invoice_lines=[line1], as_of=today
        )

        # Meets quantity, but fails amount
        line2 = InvoiceLineFactory(amount=Decimal("400.00"), quantity=6)
        assert not services.get_eligible_discounts(
            customer=customer, subscription=subscription, invoice_lines=[line2], as_of=today
        )

        # Meets both
        line3 = InvoiceLineFactory(amount=Decimal("550.00"), quantity=5)
        assert discount in services.get_eligible_discounts(
            customer=customer, subscription=subscription, invoice_lines=[line3], as_of=today
        )

    def test_selected_products_scope(self):
        product_a = ProductFactory(name="Software Pro")
        product_b = ProductFactory(name="Consulting")
        discount = SelectedProductsDiscountFactory(products=[product_a])
        customer = CustomerFactory()
        subscription = SubscriptionFactory(customer=customer)
        today = date(2026, 6, 15)

        line_a = InvoiceLineFactory(product=product_a, amount=Decimal("100.00"), quantity=1)
        line_b = InvoiceLineFactory(product=product_b, amount=Decimal("200.00"), quantity=1)

        # Only line_b (unrelated product) -> ineligible
        assert not services.get_eligible_discounts(
            customer=customer, subscription=subscription, invoice_lines=[line_b], as_of=today
        )

        # line_a present -> eligible
        eligible = services.get_eligible_discounts(
            customer=customer,
            subscription=subscription,
            invoice_lines=[line_a, line_b],
            as_of=today,
        )
        assert discount in eligible
