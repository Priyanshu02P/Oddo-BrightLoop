from datetime import date
from decimal import Decimal

import pytest

from apps.accounts.tests.factories import CustomerFactory
from apps.billing.tests.factories import InvoiceLineFactory
from apps.catalog.tests.factories import ProductFactory
from apps.discounts import services
from apps.discounts.models import Discount
from apps.discounts.tests.factories import (
    DiscountFactory,
    PercentageDiscountFactory,
    SelectedProductsDiscountFactory,
)
from apps.subscriptions.tests.factories import SubscriptionFactory


@pytest.mark.django_db
class TestDiscountStacking:
    def test_fixed_first_then_percentage_on_remainder(self):
        """FR-6.9 & CURRENT_FEATURE.md §6.6:
        Eligible amount: 1000.00
        Fixed discount: 100.00
        Percentage discount: 10%
        Calculation:
          After fixed: 900.00
          10% of remaining 900.00: 90.00
          Total discount: 190.00
          Remaining: 810.00
        """
        fixed = DiscountFactory(
            discount_type=Discount.DiscountType.FIXED_AMOUNT,
            value=Decimal("100.00"),
        )
        pct = PercentageDiscountFactory(
            discount_type=Discount.DiscountType.PERCENTAGE,
            value=Decimal("10.00"),
        )
        customer = CustomerFactory()
        subscription = SubscriptionFactory(customer=customer)
        line = InvoiceLineFactory(amount=Decimal("1000.00"), quantity=1)

        result = services.apply_stacked_discounts(
            subscription=subscription,
            customer=customer,
            invoice_lines=[line],
            as_of=date(2026, 6, 15),
        )

        assert len(result.applications) == 2
        # First applied is fixed
        assert result.applications[0].discount == fixed
        assert result.applications[0].amount_applied == Decimal("100.00")
        # Second applied is percentage on remainder
        assert result.applications[1].discount == pct
        assert result.applications[1].amount_applied == Decimal("90.00")
        # Total discount
        assert result.total_discount == Decimal("190.00")
        assert result.line_discounts[0] == Decimal("190.00")

    def test_cap_prevents_negative_total(self):
        """CURRENT_FEATURE.md §6.7 & BR-9:
        Starting amount: 500.00
        Fixed discount: 400.00
        Percentage discount: 50%
        After fixed: 100.00
        50% of remaining: 50.00
        Total discount: 450.00
        Remaining: 50.00
        """
        DiscountFactory(
            discount_type=Discount.DiscountType.FIXED_AMOUNT,
            value=Decimal("400.00"),
        )
        PercentageDiscountFactory(
            discount_type=Discount.DiscountType.PERCENTAGE,
            value=Decimal("50.00"),
        )
        customer = CustomerFactory()
        subscription = SubscriptionFactory(customer=customer)
        line = InvoiceLineFactory(amount=Decimal("500.00"), quantity=1)

        result = services.apply_stacked_discounts(
            subscription=subscription,
            customer=customer,
            invoice_lines=[line],
            as_of=date(2026, 6, 15),
        )

        assert len(result.applications) == 2
        assert result.applications[0].amount_applied == Decimal("400.00")
        assert result.applications[1].amount_applied == Decimal("50.00")
        assert result.total_discount == Decimal("450.00")
        assert result.line_discounts[0] == Decimal("450.00")

    def test_fixed_discount_exceeding_eligible_is_capped_at_100_percent(self):
        """If fixed discount alone exceeds eligible amount, it caps at eligible amount."""
        fixed = DiscountFactory(
            discount_type=Discount.DiscountType.FIXED_AMOUNT,
            value=Decimal("800.00"),
        )
        PercentageDiscountFactory(
            discount_type=Discount.DiscountType.PERCENTAGE,
            value=Decimal("20.00"),
        )
        customer = CustomerFactory()
        subscription = SubscriptionFactory(customer=customer)
        line = InvoiceLineFactory(amount=Decimal("500.00"), quantity=1)

        result = services.apply_stacked_discounts(
            subscription=subscription,
            customer=customer,
            invoice_lines=[line],
            as_of=date(2026, 6, 15),
        )

        # Fixed discount is capped at 500.00, remaining is 0, percentage cannot apply
        assert len(result.applications) == 1
        assert result.applications[0].discount == fixed
        assert result.applications[0].amount_applied == Decimal("500.00")
        assert result.total_discount == Decimal("500.00")
        assert result.line_discounts[0] == Decimal("500.00")

    def test_multiple_percentage_discounts_compound_on_remainder(self):
        """Two percentage discounts: 20% and 10% on 1000.00.
        First: 20% of 1000 = 200. Remaining = 800.
        Second: 10% of 800 = 80. Remaining = 720.
        Total discount = 280.
        """
        PercentageDiscountFactory(value=Decimal("20.00"))
        PercentageDiscountFactory(value=Decimal("10.00"))
        customer = CustomerFactory()
        subscription = SubscriptionFactory(customer=customer)
        line = InvoiceLineFactory(amount=Decimal("1000.00"), quantity=1)

        result = services.apply_stacked_discounts(
            subscription=subscription,
            customer=customer,
            invoice_lines=[line],
            as_of=date(2026, 6, 15),
        )

        assert len(result.applications) == 2
        assert result.applications[0].amount_applied == Decimal("200.00")
        assert result.applications[1].amount_applied == Decimal("80.00")
        assert result.total_discount == Decimal("280.00")

    def test_multi_line_proportional_allocation(self):
        """Fixed discount of 100.00 across Line 1 (600.00) and Line 2 (400.00).
        Line 1 gets 60.00, Line 2 gets 40.00. Sum = 100.00.
        """
        DiscountFactory(
            discount_type=Discount.DiscountType.FIXED_AMOUNT,
            value=Decimal("100.00"),
        )
        customer = CustomerFactory()
        subscription = SubscriptionFactory(customer=customer)
        line1 = InvoiceLineFactory(amount=Decimal("600.00"), quantity=1)
        line2 = InvoiceLineFactory(amount=Decimal("400.00"), quantity=1)

        result = services.apply_stacked_discounts(
            subscription=subscription,
            customer=customer,
            invoice_lines=[line1, line2],
            as_of=date(2026, 6, 15),
        )

        assert result.total_discount == Decimal("100.00")
        assert result.line_discounts[0] == Decimal("60.00")
        assert result.line_discounts[1] == Decimal("40.00")

    def test_product_scope_only_discounts_matching_line(self):
        prod_a = ProductFactory()
        prod_b = ProductFactory()
        SelectedProductsDiscountFactory(
            products=[prod_a],
            discount_type=Discount.DiscountType.PERCENTAGE,
            value=Decimal("50.00"),
        )
        customer = CustomerFactory()
        subscription = SubscriptionFactory(customer=customer)
        line_a = InvoiceLineFactory(product=prod_a, amount=Decimal("200.00"), quantity=1)
        line_b = InvoiceLineFactory(product=prod_b, amount=Decimal("300.00"), quantity=1)

        result = services.apply_stacked_discounts(
            subscription=subscription,
            customer=customer,
            invoice_lines=[line_a, line_b],
            as_of=date(2026, 6, 15),
        )

        assert result.total_discount == Decimal("100.00")
        assert result.line_discounts[0] == Decimal("100.00")  # 50% of 200
        assert result.line_discounts.get(1, Decimal("0.00")) == Decimal("0.00")  # untouched
