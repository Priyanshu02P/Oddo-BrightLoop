from datetime import date
from decimal import Decimal

import pytest

from apps.accounts.tests.factories import AdminFactory, CustomerFactory
from apps.billing import services as billing_services
from apps.billing.models import Invoice
from apps.discounts.exceptions import DiscountRedemptionConflict
from apps.discounts.models import DiscountRedemption
from apps.discounts.tests.factories import DiscountFactory
from apps.subscriptions.tests.factories import SubscriptionFactory, SubscriptionLineFactory


@pytest.mark.django_db
class TestDiscountRedemptions:
    def test_draft_generation_does_not_increment_redemption(self):
        admin = AdminFactory()
        discount = DiscountFactory(usage_limit_per_customer=3)
        customer = CustomerFactory()
        subscription = SubscriptionFactory(
            customer=customer,
            status="active",
            next_billing_date=date(2026, 6, 1),
            start_date=date(2026, 6, 1),
            expiry_date=date(2026, 12, 31),
        )
        SubscriptionLineFactory(subscription=subscription, unit_price=Decimal("200.00"), quantity=1)

        # Generate draft invoice
        invoice = billing_services.generate_invoice(
            subscription, today=date(2026, 6, 1), actor=admin
        )

        assert invoice.status == Invoice.Status.DRAFT
        assert invoice.discount_amount == Decimal("50.00")
        assert invoice.discount_snapshots.count() == 1
        snapshot = invoice.discount_snapshots.first()
        assert not snapshot.redemption_confirmed

        # No redemption record yet (or 0 uses)
        usage = DiscountRedemption.objects.filter(discount=discount, customer=customer).first()
        assert usage is None or usage.usage_count == 0

    def test_confirm_invoice_increments_redemption(self):
        admin = AdminFactory()
        discount = DiscountFactory(usage_limit_per_customer=3)
        customer = CustomerFactory()
        subscription = SubscriptionFactory(
            customer=customer,
            status="active",
            next_billing_date=date(2026, 6, 1),
            start_date=date(2026, 6, 1),
            expiry_date=date(2026, 12, 31),
        )
        SubscriptionLineFactory(subscription=subscription, unit_price=Decimal("200.00"), quantity=1)

        invoice = billing_services.generate_invoice(
            subscription, today=date(2026, 6, 1), actor=admin
        )
        assert invoice.discount_snapshots.filter(redemption_confirmed=False).count() == 1

        # Confirm the invoice
        billing_services.confirm_invoice(actor=admin, invoice=invoice)

        snapshot = invoice.discount_snapshots.first()
        assert snapshot.redemption_confirmed

        redemption = DiscountRedemption.objects.get(discount=discount, customer=customer)
        assert redemption.usage_count == 1

    def test_confirmation_is_idempotent(self):
        admin = AdminFactory()
        discount = DiscountFactory(usage_limit_per_customer=3)
        customer = CustomerFactory()
        subscription = SubscriptionFactory(
            customer=customer,
            status="active",
            next_billing_date=date(2026, 6, 1),
            start_date=date(2026, 6, 1),
            expiry_date=date(2026, 12, 31),
        )
        SubscriptionLineFactory(subscription=subscription, unit_price=Decimal("200.00"), quantity=1)

        invoice = billing_services.generate_invoice(
            subscription, today=date(2026, 6, 1), actor=admin
        )
        billing_services.confirm_invoice(actor=admin, invoice=invoice)

        redemption = DiscountRedemption.objects.get(discount=discount, customer=customer)
        assert redemption.usage_count == 1

        # Calling record_confirmed_redemptions again should not increment
        from apps.discounts.services import record_confirmed_redemptions

        record_confirmed_redemptions(invoice=invoice, actor=admin)
        redemption.refresh_from_db()
        assert redemption.usage_count == 1

    def test_exhausted_at_confirmation_raises_conflict(self):
        admin = AdminFactory()
        discount = DiscountFactory(usage_limit_per_customer=1)
        customer = CustomerFactory()
        subscription = SubscriptionFactory(
            customer=customer,
            status="active",
            next_billing_date=date(2026, 6, 1),
            start_date=date(2026, 6, 1),
            expiry_date=date(2026, 12, 31),
        )
        SubscriptionLineFactory(subscription=subscription, unit_price=Decimal("200.00"), quantity=1)

        # Generate draft invoice when usage is 0
        invoice = billing_services.generate_invoice(
            subscription, today=date(2026, 6, 1), actor=admin
        )

        # Now simulate another invoice consumed the only allowed usage in the meantime
        redemption, _ = DiscountRedemption.objects.get_or_create(
            discount=discount, customer=customer, defaults={"usage_count": 0}
        )
        redemption.usage_count = 1
        redemption.save()

        # Confirmation must raise DiscountRedemptionConflict
        with pytest.raises(DiscountRedemptionConflict):
            billing_services.confirm_invoice(actor=admin, invoice=invoice)

    def test_cancelling_invoice_does_not_decrement_usage(self):
        admin = AdminFactory()
        discount = DiscountFactory(usage_limit_per_customer=3)
        customer = CustomerFactory()
        subscription = SubscriptionFactory(
            customer=customer,
            status="active",
            next_billing_date=date(2026, 6, 1),
            start_date=date(2026, 6, 1),
            expiry_date=date(2026, 12, 31),
        )
        SubscriptionLineFactory(subscription=subscription, unit_price=Decimal("200.00"), quantity=1)

        invoice = billing_services.generate_invoice(
            subscription, today=date(2026, 6, 1), actor=admin
        )
        billing_services.confirm_invoice(actor=admin, invoice=invoice)

        redemption = DiscountRedemption.objects.get(discount=discount, customer=customer)
        assert redemption.usage_count == 1

        # Cancel the invoice
        billing_services.cancel_invoice(actor=admin, invoice=invoice)
        redemption.refresh_from_db()
        # Usage must remain 1 (cancellation does not restore usage, per open item policy)
        assert redemption.usage_count == 1
